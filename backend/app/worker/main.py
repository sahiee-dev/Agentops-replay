from __future__ import annotations

"""
main.py - Async ingestion worker with policy enforcement.

Consumes event batches from Redis Stream, processes them via IngestService,
evaluates policies, and persists violations atomically.

CONSTITUTIONAL GUARANTEES:
- Reuses IngestService exactly — no duplication of validation or hashing logic
- At-least-once delivery: XACK only on successful processing
- Dead Letter Queue (DLQ) after MAX_RETRIES failed attempts
- Graceful shutdown on SIGTERM/SIGINT
- ATOMIC TRANSACTION: events + violations commit together or both rollback
- Policy evaluation failure → full batch rollback (CONSTITUTION §5)

TRUST BOUNDARY:
- Worker is inside the server trust boundary
- Worker calls IngestService which is the authoritative sealer
- No external input after Redis deserialization
"""

import json
import logging
import os
import signal
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

# Ensure backend is on path when run as module
_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)

from app.core.redis import (
    CONSUMER_GROUP,
    DLQ_STREAM_NAME,
    MAX_RETRIES,
    STREAM_NAME,
    ensure_consumer_group,
    get_redis_client,
)
from app.database import SessionLocal
from app.ingestion import IngestService, SequenceViolation
from app.models import EventChain
from app.models.violation import Violation
from app.services.policy.engine import CanonicalEvent, PolicyEngine
from app.services.policy.gdpr_policy import GDPRPolicy
from app.services.policy.tool_audit_policy import ToolAuditPolicy

UTC = timezone.utc
logger = logging.getLogger(__name__)

# Worker identity
CONSUMER_NAME = os.environ.get("WORKER_CONSUMER_NAME", "worker-01")

# Batch read settings
BLOCK_MS = 5000  # Block for 5s waiting for new messages
BATCH_COUNT = 10  # Process up to 10 messages per read

# Policy config path (relative to working directory)
POLICY_CONFIG_PATH = os.environ.get("POLICY_CONFIG_PATH", "policy.yaml")


class IngestionWorker:
    """
    Consumes batches from Redis Stream, processes via IngestService + PolicyEngine.

    Lifecycle:
    1. Connect to Redis, ensure consumer group exists
    2. Load PolicyEngine, log PolicySet identity
    3. Loop: XREADGROUP → process → evaluate policies → XACK
    4. On failure: retry up to MAX_RETRIES, then DLQ
    5. On SIGTERM: finish current batch, exit cleanly

    ATOMIC TRANSACTION (per POLICY_SEMANTICS.md §4.1):
    1. Persist events (IngestService, external DB session)
    2. Evaluate policies (pure function, no DB)
    3. Persist violations (same DB session)
    4. Single atomic commit
    5. XACK
    """

    def __init__(self) -> None:
        self.running = False
        self.redis = get_redis_client()
        self.ingest_service = IngestService(service_id="worker-ingest-01")

        # Initialize PolicyEngine
        self.policy_engine = self._init_policy_engine()

    def _init_policy_engine(self) -> PolicyEngine:
        """
        Initialize and configure the PolicyEngine.

        Logs PolicySet version + config_hash at startup for audit trail.
        """
        engine = PolicyEngine(config_path=POLICY_CONFIG_PATH)

        # Register policies
        gdpr = GDPRPolicy()
        engine.register(gdpr)

        tool_audit = ToolAuditPolicy()
        tool_config = engine.get_config("tool_audit")
        tool_audit.configure(tool_config)
        engine.register(tool_audit)

        # Log PolicySet identity at startup (POLICY_SEMANTICS.md requirement)
        ps = engine.policy_set()
        logger.info(
            "PolicyEngine initialized: version=%s, config_hash=%s, active_policies=%d",
            ps.version,
            ps.config_hash,
            len(ps.policies),
        )
        for p in ps.policies:
            logger.info(
                "  Policy: %s (version=%s, source_hash=%s)",
                p.name,
                p.version,
                p.source_hash[:16] + "...",
            )

        return engine

    def start(self) -> None:
        """Start the worker loop."""
        self.running = True

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._shutdown_handler)
        signal.signal(signal.SIGINT, self._shutdown_handler)

        # Ensure consumer group exists
        ensure_consumer_group(self.redis)

        logger.info(
            "Worker '%s' started. Consuming from '%s' (group: '%s')",
            CONSUMER_NAME,
            STREAM_NAME,
            CONSUMER_GROUP,
        )

        # First: claim any pending messages from previous crashes
        self._process_pending()

        # Main loop: read new messages
        while self.running:
            try:
                messages = self.redis.xreadgroup(
                    groupname=CONSUMER_GROUP,
                    consumername=CONSUMER_NAME,
                    streams={STREAM_NAME: ">"},
                    count=BATCH_COUNT,
                    block=BLOCK_MS,
                )

                if not messages:
                    continue

                for stream_name, stream_messages in messages:
                    for message_id, fields in stream_messages:
                        self._process_message(message_id, fields)

            except Exception:
                logger.exception("Error in worker loop")
                time.sleep(1)  # Back off on unexpected errors

        logger.info("Worker '%s' stopped gracefully.", CONSUMER_NAME)

    def _process_pending(self) -> None:
        """Process any pending messages from previous crashes (at-least-once)."""
        logger.info("Checking for pending messages...")
        try:
            messages = self.redis.xreadgroup(
                groupname=CONSUMER_GROUP,
                consumername=CONSUMER_NAME,
                streams={STREAM_NAME: "0"},
                count=BATCH_COUNT,
            )

            if not messages:
                logger.info("No pending messages.")
                return

            for stream_name, stream_messages in messages:
                for message_id, fields in stream_messages:
                    if not fields:
                        # Already acknowledged but still in PEL — skip
                        continue
                    logger.info("Re-processing pending message: %s", message_id)
                    self._process_message(message_id, fields)

        except Exception:
            logger.exception("Error processing pending messages")

    def _process_message(self, message_id: str, fields: dict[str, Any]) -> None:
        """
        Process a single batch message with atomic policy enforcement.

        ATOMIC SEQUENCE (POLICY_SEMANTICS.md §4.1):
        1. Persist events (IngestService uses Worker's DB session)
        2. Evaluate policies (pure function over committed events)
        3. Persist violations (same DB session)
        4. Single atomic commit (events + violations)
        5. XACK

        On policy evaluation failure: full batch rollback.
        Evidence without governance metadata is incomplete.
        """
        batch_id = fields.get("batch_id", "unknown")
        session_id = fields.get("session_id")
        seal_requested = fields.get("seal", "False").lower() == "true"
        events_json = fields.get("events", "[]")

        try:
            events = json.loads(events_json)
        except json.JSONDecodeError:
            logger.error(
                "Batch %s: invalid JSON in events field. Moving to DLQ.", batch_id
            )
            self._move_to_dlq(message_id, fields, "INVALID_JSON")
            return

        if not session_id or not events:
            logger.error(
                "Batch %s: missing session_id or empty events. Moving to DLQ.",
                batch_id,
            )
            self._move_to_dlq(message_id, fields, "MISSING_REQUIRED_FIELD")
            return

        # Worker controls the transaction boundary
        db = SessionLocal()
        try:
            # Convert Pydantic model_dump format back to IngestService format
            raw_events = []
            for event in events:
                raw_events.append(
                    {
                        "event_type": event["event_type"],
                        "sequence_number": event["sequence_number"],
                        "timestamp_monotonic": event["timestamp_monotonic"],
                        # timestamp_wall: use SDK value if present, else generate
                        # server-side (consistent with server authority model).
                        "timestamp_wall": event.get(
                            "timestamp_wall",
                            datetime.now(UTC).isoformat(),
                        ),
                        "payload": event.get("payload", {}),
                        "event_hash": event.get("event_hash"),
                        "prev_event_hash": event.get("prev_event_hash"),
                    }
                )

            # STEP 1: Persist events (IngestService uses Worker's DB session)
            # IngestService does NOT commit — Worker owns the transaction.
            result = self.ingest_service.append_events(
                session_id=session_id, events=raw_events, db=db
            )

            # STEP 2: Evaluate policies (pure function, no DB)
            # Use committed_events returned by IngestService — no requery.
            committed_events = result.get("committed_events", [])
            canonical_events = [
                CanonicalEvent(
                    event_id=e["event_id"],
                    session_id=e["session_id"],
                    sequence_number=e["sequence_number"],
                    event_type=e["event_type"],
                    payload_canonical=e["payload_canonical"],
                    payload_hash=e["payload_hash"],
                    event_hash=e["event_hash"],
                    chain_authority=e["chain_authority"],
                )
                for e in committed_events
            ]

            violations = self.policy_engine.evaluate(canonical_events)

            # STEP 3: Persist violations in same transaction
            now = datetime.now(UTC)
            for v in violations:
                db.add(
                    Violation(
                        id=v.id,
                        session_id=v.session_id,
                        event_id=v.event_id,
                        event_sequence_number=v.event_sequence_number,
                        policy_name=v.policy_name,
                        policy_version=v.policy_version,
                        policy_hash=v.policy_hash,
                        severity=v.severity,
                        description=v.description,
                        metadata_json=json.dumps(v.metadata) if v.metadata else None,
                        created_at=now,
                    )
                )

            # STEP 4: Atomic commit (events + violations)
            db.commit()

            logger.info(
                "Batch %s processed: %d events, %d violations for session %s (hash: %s)",
                batch_id,
                result.get("accepted_count", 0),
                len(violations),
                session_id,
                result.get("final_hash", "N/A"),
            )

            # Seal if requested (separate transaction — seal is idempotent)
            if seal_requested:
                try:
                    seal_result = self.ingest_service.seal_session(session_id)
                    logger.info(
                        "Batch %s: session %s sealed (digest: %s)",
                        batch_id,
                        session_id,
                        seal_result.get("session_digest", "N/A"),
                    )
                except Exception:
                    # Seal failure is not a processing failure — log but don't retry
                    logger.warning(
                        "Batch %s: seal requested but failed for session %s",
                        batch_id,
                        session_id,
                        exc_info=True,
                    )

            # STEP 5: XACK (only after successful commit)
            self.redis.xack(STREAM_NAME, CONSUMER_GROUP, message_id)

        except SequenceViolation:
            # Possible replay after crash (commit succeeded, XACK failed).
            # Guard: verify the first batch sequence already exists in DB.
            db.rollback()
            first_seq = events[0].get("sequence_number") if events else None
            if first_seq is not None:
                check_db = SessionLocal()
                try:
                    exists = (
                        check_db.query(EventChain.event_id)
                        .filter(
                            EventChain.session_id == session_id,
                            EventChain.sequence_number == first_seq,
                        )
                        .first()
                        is not None
                    )
                finally:
                    check_db.close()

                if exists:
                    logger.warning(
                        "Batch %s: Duplicate replay detected for session %s "
                        "(seq %d exists). ACKing.",
                        batch_id,
                        session_id,
                        first_seq,
                    )
                    self.redis.xack(STREAM_NAME, CONSUMER_GROUP, message_id)
                    return

            # Not a replay — real sequence corruption. DLQ.
            logger.error(
                "Batch %s: SequenceViolation without prior commit for session %s. "
                "Sending to DLQ.",
                batch_id,
                session_id,
            )
            self._move_to_dlq(message_id, fields, "SEQUENCE_VIOLATION")

        except Exception:
            # Full rollback: events + violations + LOG_DROP
            db.rollback()
            logger.exception(
                "Batch %s: processing failed for session %s (rolled back)",
                batch_id,
                session_id,
            )
            self._handle_retry(message_id, fields, batch_id)
        finally:
            db.close()

    def _handle_retry(
        self, message_id: str, fields: dict[str, Any], batch_id: str
    ) -> None:
        """Increment retry counter. Move to DLQ after MAX_RETRIES."""
        retry_count = int(fields.get("_retry_count", "0")) + 1

        if retry_count >= MAX_RETRIES:
            logger.error(
                "Batch %s: exceeded %d retries. Moving to DLQ.",
                batch_id,
                MAX_RETRIES,
            )
            self._move_to_dlq(message_id, fields, f"MAX_RETRIES_EXCEEDED({retry_count})")
        else:
            # Update retry count on the message
            # Note: Redis Streams don't support in-place field updates.
            # We acknowledge the old message and re-add with incremented retry count.
            self.redis.xack(STREAM_NAME, CONSUMER_GROUP, message_id)
            fields["_retry_count"] = str(retry_count)
            self.redis.xadd(STREAM_NAME, fields)
            logger.warning(
                "Batch %s: retry %d/%d re-queued.",
                batch_id,
                retry_count,
                MAX_RETRIES,
            )

    def _move_to_dlq(
        self, message_id: str, fields: dict[str, Any], reason: str
    ) -> None:
        """Move failed message to Dead Letter Queue with failure metadata."""
        dlq_fields = {**fields, "_dlq_reason": reason, "_original_id": message_id}
        self.redis.xadd(DLQ_STREAM_NAME, dlq_fields)
        self.redis.xack(STREAM_NAME, CONSUMER_GROUP, message_id)
        logger.warning(
            "Message %s moved to DLQ '%s' (reason: %s)",
            message_id,
            DLQ_STREAM_NAME,
            reason,
        )

    def _shutdown_handler(self, signum: int, frame: Any) -> None:
        """Handle SIGTERM/SIGINT for graceful shutdown."""
        logger.info(
            "Received signal %d. Finishing current batch and shutting down...", signum
        )
        self.running = False


def main() -> None:
    """Entry point for worker process."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("Starting AgentOps Replay Ingestion Worker...")
    worker = IngestionWorker()
    worker.start()


if __name__ == "__main__":
    main()
