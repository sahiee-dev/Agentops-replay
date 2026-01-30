"""
service.py - Ingestion Service orchestrator.

CRITICAL INVARIANTS (violations result in IMMEDIATE REJECTION):
1. SDK hashes are NEVER trusted — all hashes recomputed server-side
2. Sequence is the ONLY ordering authority — timestamps are opaque
3. Sealed sessions CANNOT accept new events
4. seal=true requires SESSION_END as last event
5. All writes are ATOMIC (full batch or nothing)
6. All ingested events stamped chain_authority=SERVER

FAILURE SEMANTICS:
- State conflicts (sealed, sequence issues) → 409
- Bad input (malformed, invalid seal) → 400
- DB failures → 500 + full rollback
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.models import ChainSeal, EventChain, Session, SessionStatus
from app.services.ingestion.hasher import (
    GENESIS_HASH,
    ChainResult,
    RejectionReason,
    recompute_chain,
)
from app.services.ingestion.sealer import (
    SealStatus,
    seal_chain,
)

logger = logging.getLogger(__name__)

# Ingestion service identifier (for seal attribution)
INGESTION_SERVICE_ID = "ingestion-service-v1"


class IngestionError(Exception):
    """Base exception for ingestion failures."""

    pass


class StateConflictError(IngestionError):
    """409 Conflict - state conflicts (sealed session, sequence issues)."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class BadRequestError(IngestionError):
    """400 Bad Request - invalid input (malformed, invalid seal)."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


@dataclass
class IngestionResultData:
    """Internal result of batch ingestion."""

    accepted_count: int
    final_hash: str
    sealed: bool = False
    seal_timestamp: str | None = None
    session_digest: str | None = None
    evidence_class: str | None = None


class IngestionService:
    """
    Authoritative ingestion service.

    Establishes SERVER authority for all ingested events.
    Enforces constitutional invariants.
    """

    def __init__(self, db: DBSession):
        self.db = db

    def ingest_batch(
        self, session_id_str: str, events: list[dict[str, Any]], seal: bool = False
    ) -> IngestionResultData:
        """
        Ingest a batch of events into a session.

        INVARIANTS ENFORCED:
        - Session must exist and not be sealed
        - Sequence must be strictly monotonic and continuous with existing chain
        - seal=true requires SESSION_END as last event
        - All writes are atomic

        Args:
            session_id_str: Session UUID string
            events: List of raw events (untrusted)
            seal: Whether to seal after ingestion

        Returns:
            IngestionResultData on success

        Raises:
            StateConflictError: 409 - sealed session or sequence conflict
            BadRequestError: 400 - invalid input or seal request
        """
        # =========================================================
        # SINGLE TRANSACTION BLOCK - ALL OR NOTHING
        # =========================================================

        # 1. Lock session (SELECT FOR UPDATE)
        session = self._lock_session(session_id_str)

        # 2. Validate session state
        self._validate_session_not_sealed(session)

        # 3. Get existing chain state
        last_sequence, last_hash = self._get_chain_state(int(session.id))

        # 4. Validate sequence continuity
        self._validate_sequence_continuity(events, last_sequence)

        # 5. Validate seal request (if requested)
        if seal:
            self._validate_seal_request(events)

        # 6. Recompute hashes (SERVER AUTHORITY)
        chain_result = self._recompute_and_validate(events, last_hash)

        # 7. Persist events (atomic)
        if chain_result.recomputed_events is None:
            raise BadRequestError(code="EMPTY_CHAIN", message="No events to persist")
        self._persist_events(session, chain_result.recomputed_events)

        # 8. Seal if requested
        seal_data = None
        if seal:
            seal_data = self._seal_session(session, chain_result)

        # 9. Commit (happens when transaction context exits)
        self.db.flush()

        # 10. Log seal event (single line, operational visibility)
        if seal_data:
            final_hash = chain_result.final_hash
            if final_hash is None:
                raise BadRequestError(
                    code="MISSING_HASH", message="Chain result missing final hash"
                )
            logger.info(
                "SESSION SEALED — session_id=%s, event_count=%d, final_hash=%s",
                session_id_str,
                chain_result.event_count,
                final_hash[:16] + "...",
            )

        final_hash = chain_result.final_hash
        if final_hash is None:
            raise BadRequestError(
                code="MISSING_HASH", message="Chain result missing final hash"
            )

        return IngestionResultData(
            accepted_count=chain_result.event_count,
            final_hash=final_hash,
            sealed=seal_data is not None,
            seal_timestamp=seal_data.seal_timestamp if seal_data else None,
            session_digest=seal_data.session_digest if seal_data else None,
            evidence_class=seal_data.evidence_class if seal_data else None,
        )

    # =========================================================
    # PRIVATE METHODS - INVARIANT ENFORCEMENT
    # =========================================================

    def _lock_session(self, session_id_str: str) -> Session:
        """Lock session for exclusive access (SELECT FOR UPDATE)."""
        stmt = (
            select(Session)
            .where(Session.session_id_str == session_id_str)
            .with_for_update()
        )
        session = self.db.execute(stmt).scalar_one_or_none()

        if session is None:
            raise BadRequestError(
                code="SESSION_NOT_FOUND", message=f"Session {session_id_str} not found"
            )

        return session

    def _validate_session_not_sealed(self, session: Session) -> None:
        """INVARIANT: Sealed sessions cannot accept new events."""
        if session.status == SessionStatus.SEALED:
            raise StateConflictError(
                code="ALREADY_SEALED",
                message="Session is already sealed. Sealed sessions cannot accept new events.",
                details={
                    "sealed_at": str(session.sealed_at) if session.sealed_at else None
                },
            )

    def _get_chain_state(self, session_id: int) -> tuple[int, str]:
        """Get last sequence number and hash from existing chain."""
        stmt = (
            select(EventChain.sequence_number, EventChain.event_hash)
            .where(EventChain.session_id == session_id)
            .order_by(EventChain.sequence_number.desc())
            .limit(1)
        )
        result = self.db.execute(stmt).first()

        if result is None:
            # No events yet - genesis state
            return -1, GENESIS_HASH

        return result.sequence_number, result.event_hash

    def _validate_sequence_continuity(
        self, events: list[dict[str, Any]], last_sequence: int
    ) -> None:
        """
        INVARIANT: Sequence must be strictly monotonic and continuous.

        New batch must start at last_sequence + 1.
        """
        if not events:
            raise BadRequestError(
                code="MISSING_REQUIRED_FIELD", message="Events list cannot be empty"
            )

        first_seq = events[0].get("sequence_number")
        if first_seq is None:
            raise BadRequestError(
                code="MISSING_REQUIRED_FIELD",
                message="First event missing sequence_number",
            )

        expected_first = last_sequence + 1

        if first_seq < expected_first:
            raise StateConflictError(
                code="DUPLICATE_SEQUENCE",
                message=f"Sequence {first_seq} already exists. Expected >= {expected_first}",
                details={"first_event_sequence": first_seq, "expected": expected_first},
            )

        if first_seq > expected_first:
            raise StateConflictError(
                code="SEQUENCE_GAP",
                message=f"Sequence gap detected. Expected {expected_first}, got {first_seq}",
                details={"first_event_sequence": first_seq, "expected": expected_first},
            )

    def _validate_seal_request(self, events: list[dict[str, Any]]) -> None:
        """
        INVARIANT: seal=true requires SESSION_END as last event.

        This prevents:
        - Mid-stream sealing
        - Truncated evidence
        - Accidental premature finalization
        """
        if not events:
            raise BadRequestError(
                code="INVALID_SEAL_REQUEST",
                message="Cannot seal with empty events batch",
            )

        last_event_type = events[-1].get("event_type")

        if last_event_type != "SESSION_END":
            raise BadRequestError(
                code="INVALID_SEAL_REQUEST",
                message=f"Cannot seal: last event must be SESSION_END, got {last_event_type}",
                details={"last_event_type": last_event_type, "required": "SESSION_END"},
            )

    def _recompute_and_validate(
        self, events: list[dict[str, Any]], prev_hash: str
    ) -> ChainResult:
        """
        Recompute hash chain server-side.

        SDK hashes are logged but NEVER trusted.
        """
        chain_result = recompute_chain(events, expected_genesis_hash=prev_hash)

        if not chain_result.valid:
            # Map hasher rejection reasons to service errors
            reason = chain_result.rejection_reason

            if reason in (
                RejectionReason.SEQUENCE_GAP,
                RejectionReason.DUPLICATE_SEQUENCE,
                RejectionReason.NON_MONOTONIC_SEQUENCE,
            ):
                raise StateConflictError(
                    code=reason.value if reason else "SEQUENCE_ERROR",
                    message=chain_result.rejection_details
                    or "Sequence validation failed",
                )
            else:
                raise BadRequestError(
                    code=reason.value if reason else "INVALID_PAYLOAD",
                    message=chain_result.rejection_details or "Chain validation failed",
                )

        return chain_result

    def _persist_events(
        self, session: Session, recomputed_events: list[dict[str, Any]]
    ) -> None:
        """Persist all events atomically."""

        for event_data in recomputed_events:
            # Parse timestamp
            ts_mono = event_data.get("timestamp_monotonic", 0)

            # Create wall timestamp (use current time as server receipt time)
            now = datetime.now(UTC)

            event = EventChain(
                session_id=session.id,
                session_id_str=str(session.session_id_str),
                sequence_number=event_data["sequence_number"],
                timestamp_wall=now,
                timestamp_monotonic=ts_mono,
                event_type=event_data["event_type"],
                payload_canonical=event_data["payload_canonical"],
                payload_hash=event_data["payload_hash"],
                payload_jsonb=event_data.get("payload"),
                prev_event_hash=event_data["prev_event_hash"],
                event_hash=event_data["event_hash"],
                chain_authority="SERVER",  # INVARIANT: Always SERVER
            )

            self.db.add(event)

    def _seal_session(self, session: Session, chain_result: ChainResult) -> Any:
        """Seal the session and create ChainSeal record."""

        # Get all events for seal computation
        stmt = (
            select(EventChain)
            .where(EventChain.session_id == session.id)
            .order_by(EventChain.sequence_number)
        )
        all_events = list(self.db.execute(stmt).scalars())

        # Convert to dicts for sealer
        event_dicts = [
            {"event_hash": e.event_hash, "sequence_number": e.sequence_number}
            for e in all_events
        ]

        # Add newly ingested events (already validated in caller via _persist_events check)
        recomputed = chain_result.recomputed_events
        if recomputed is not None:
            for evt in recomputed:
                event_dicts.append(
                    {
                        "event_hash": evt["event_hash"],
                        "sequence_number": evt["sequence_number"],
                    }
                )

        # Seal
        total_drops = int(session.total_drops) if session.total_drops else 0
        seal_result = seal_chain(
            session_id=str(session.session_id_str),
            events=event_dicts,
            ingestion_service_id=INGESTION_SERVICE_ID,
            existing_seal=None,  # We already validated not sealed
            total_drops=total_drops,
        )

        if seal_result.status != SealStatus.SEALED:
            raise BadRequestError(
                code="SEAL_FAILED",
                message=seal_result.rejection_reason or "Sealing failed",
            )

        # Create ChainSeal record
        chain_seal = ChainSeal(
            session_id=session.id,
            ingestion_service_id=INGESTION_SERVICE_ID,
            seal_timestamp=seal_result.seal_timestamp,
            session_digest=seal_result.session_digest,
            final_event_hash=seal_result.final_event_hash,
            event_count=seal_result.event_count,
        )
        self.db.add(chain_seal)

        # Update session status
        session.status = SessionStatus.SEALED
        # Parse ISO-8601 timestamp string to datetime (handle trailing Z for UTC)
        if seal_result.seal_timestamp:
            ts_str = seal_result.seal_timestamp.replace("Z", "+00:00")
            session.sealed_at = datetime.fromisoformat(ts_str)
        else:
            session.sealed_at = datetime.now(UTC)
        # evidence_class may be None if the column is nullable
        session.evidence_class = seal_result.evidence_class

        return seal_result
