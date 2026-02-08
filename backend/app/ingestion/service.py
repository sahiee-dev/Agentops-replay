"""
service.py - Production ingestion service with constitutional guarantees.

CRITICAL REQUIREMENTS:
1. Server-side hash recomputation (ignore SDK hashes)
2. Hard sequence rejection rules (no auto-heal)
3. Authority gate for CHAIN_SEAL
4. Atomic batch commits
"""

import os
import sys
import uuid
from datetime import datetime, timezone
UTC = timezone.utc
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

# Add verifier to Python path for shared hash functions
# Support both local dev (relative) and Docker (/app/verifier)
_verifier_paths = [
    os.path.join(os.path.dirname(__file__), "../../../verifier"),  # Local dev
    "/app/verifier",  # Docker
]
for _path in _verifier_paths:
    if os.path.isdir(_path) and _path not in sys.path:
        sys.path.insert(0, _path)
        break

import verifier_core
from app.database import SessionLocal
from app.models import ChainAuthority, ChainSeal, EventChain, Session, SessionStatus


class SequenceViolation(Exception):
    """Raised when sequence validation fails."""

    pass


class AuthorityViolation(Exception):
    """Raised when authority checks fail."""

    pass

def _parse_wall_timestamp(ts: str) -> datetime:
    """
    Normalizes a wall timestamp from the SDK.
    Rejects ambiguous timestamps (no timezone) and returns naive UTC.
    """
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"Ambiguous timestamp (no timezone): {ts}")
    return dt.astimezone(UTC).replace(tzinfo=None)


class IngestService:
    """
    Production ingestion service implementing EVENT_LOG_SPEC.md v0.6.

    Constitutional guarantees:
    - Server-side hash recomputation
    - Hard sequence rejection
    - Authority enforcement
    - Append-only storage
    """

    def __init__(self, service_id: str | None = None):
        """
        Initialize ingestion service.

        CONSTITUTIONAL REQUIREMENT: service_id is IMMUTABLE.
        - Set once at service startup
        - NOT configurable per request
        - Ideally derived from deployment identity

        Args:
            service_id: Static ingestion service identifier for CHAIN_SEAL.
                       If not provided, reads from INGESTION_SERVICE_ID env var.
                       Defaults to "default-ingest-01" if neither provided.
        """
        # Freeze service identity at startup
        if service_id:
            self.service_id = service_id
        else:
            # Read from environment (set once at deployment)
            import os

            self.service_id = os.getenv("INGESTION_SERVICE_ID", "default-ingest-01")

        # Log service identity for audit trail
        import logging

        logging.info(f"IngestService initialized with service_id: {self.service_id}")

        # CRITICAL: This value CANNOT change during service lifetime
        # Any attempt to modify will break seal integrity

    def start_session(
        self,
        session_id_str: str | None = None,
        authority: str = "server",
        agent_name: str | None = None,
        user_id: int | None = None,
    ) -> str:
        """
        Start a new session with specified authority.

        Args:
            session_id_str: UUID string from SDK (optional, will generate if not provided)
            authority: "server" or "sdk"
            agent_name: Optional agent identifier
            user_id: Optional user ID for legacy compatibility

        Returns:
            session_id as string (UUID)

        Raises:
            ValueError: If authority is invalid
        """
        # Validate authority
        if authority not in ["server", "sdk"]:
            raise ValueError(
                f"Invalid authority: {authority}. Must be 'server' or 'sdk'"
            )

        db = SessionLocal()
        try:
            # Create session
            session_uuid = uuid.UUID(session_id_str) if session_id_str else uuid.uuid4()

            chain_auth = (
                ChainAuthority.SERVER if authority == "server" else ChainAuthority.SDK
            )

            session = Session(
                session_id_str=session_uuid,
                chain_authority=chain_auth,
                status=SessionStatus.ACTIVE,
                agent_name=agent_name,
                user_id=user_id,
                ingestion_service_id=self.service_id if authority == "server" else None,
            )

            db.add(session)
            db.commit()
            db.refresh(session)

            return str(session.session_id_str)

        finally:
            db.close()

    def append_events(
        self, session_id: str, events: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Append events to session with constitutional validation.

        CRITICAL OPERATIONS:
        1. Server-side hash recomputation (ignore SDK hashes)
        2. Strict sequence validation (hard rejection)
        3. Atomic commit (all or none)

        Args:
            session_id: Session UUID string
            events: List of event dictionaries from SDK

        Returns:
            dict with 'status', 'accepted_count', 'final_hash'

        Raises:
            SequenceViolation: On sequence gaps/duplicates
            ValueError: On validation failures
        """
        db = SessionLocal()
        try:
            # CRITICAL: Acquire row-level lock to prevent race conditions
            # FOR UPDATE ensures last_seq cannot change between validation and insert
            session = (
                db.query(Session)
                .filter(Session.session_id_str == session_id)
                .with_for_update()
                .first()
            )

            if not session:
                raise ValueError(f"Session {session_id} not found")

            if session.status != SessionStatus.ACTIVE:
                raise ValueError(
                    f"Session {session_id} is not active (status: {session.status})"
                )

            # Validate sequence continuity (session is locked, no races possible)
            self._validate_sequence(db, session, events)

            # Recompute hashes and store events
            stored_events = []
            prev_hash = self._get_last_event_hash(db, session)

            for event_data in events:
                # CONSTITUTIONAL: Server-side hash recomputation
                # Ignore SDK-provided hashes completely
                payload = event_data.get("payload", {})
                payload_hash = verifier_core.compute_payload_hash(payload)

                # Create event envelope for hash computation
                event_envelope = {
                    "event_id": event_data.get("event_id", str(uuid.uuid4())),
                    "session_id": session_id,
                    "sequence_number": event_data["sequence_number"],
                    "timestamp_wall": event_data["timestamp_wall"],
                    "event_type": event_data["event_type"],
                    "payload_hash": payload_hash,
                    "prev_event_hash": prev_hash,
                }

                # Compute event hash
                event_hash = verifier_core.compute_event_hash(event_envelope)

                # Store in database
                event_chain = EventChain(
                    event_id=uuid.UUID(event_envelope["event_id"]),
                    session_id=session.session_id_str,
                    sequence_number=event_envelope["sequence_number"],
                    timestamp_wall=_parse_wall_timestamp(event_envelope["timestamp_wall"]),
                    timestamp_monotonic=event_data.get("timestamp_monotonic", 0),
                    event_type=event_envelope["event_type"],
                    source_sdk_ver=event_data.get("source_sdk_ver"),
                    schema_ver=event_data.get("schema_ver", "v0.6"),
                    payload_canonical=verifier_core.jcs.canonicalize(payload).decode(
                        "utf-8"
                    ),
                    payload_hash=payload_hash,
                    prev_event_hash=prev_hash,
                    event_hash=event_hash,
                    chain_authority=session.chain_authority,
                )

                db.add(event_chain)
                stored_events.append(event_chain)

                # Update for next iteration
                prev_hash = event_hash

                # Track LOG_DROP events
                if event_data["event_type"] == "LOG_DROP":
                    dropped_count = payload.get("dropped_count", 0)
                    current_drops = (
                        int(session.total_drops) if session.total_drops else 0
                    )
                    # SQLAlchemy Column at runtime holds int, type checker sees Column[int]
                    session.total_drops = current_drops + dropped_count

            # Atomic commit
            db.commit()

            return {
                "status": "success",
                "accepted_count": len(events),
                "final_hash": prev_hash,
            }

        except IntegrityError as e:
            db.rollback()
            raise ValueError(f"Database integrity error: {e}")

        finally:
            db.close()

    def seal_session(self, session_id: str) -> dict[str, Any]:
        """
        Seal session with CHAIN_SEAL event.

        AUTHORITY GATE (MANDATORY):
        - Only server authority sessions can be sealed
        - Seal is idempotent (returns existing seal if already sealed)

        SESSION_END ENFORCEMENT (CONSTITUTIONAL):
        - Seal FAILS if SESSION_END event not present
        - This is a HARD requirement for AUTHORITATIVE_EVIDENCE

        Args:
            session_id: Session UUID string

        Returns:
            dict with seal metadata

        Raises:
            AuthorityViolation: If session is not server authority
            ValueError: If SESSION_END not present or session empty
        """
        db = SessionLocal()
        try:
            # Get session
            session = (
                db.query(Session)
                .filter(Session.session_id_str == session_id)
                .first()
            )

            if not session:
                raise ValueError(f"Session {session_id} not found")

            # AUTHORITY GATE
            if session.chain_authority != ChainAuthority.SERVER:
                raise AuthorityViolation(
                    f"Only server authority sessions can be sealed. "
                    f"Session {session_id} has authority: {session.chain_authority}"
                )

            # IDEMPOTENCY CHECK
            existing_seal = (
                db.query(ChainSeal).filter(ChainSeal.session_id == session.id).first()
            )

            if existing_seal:
                # Return existing seal
                return {
                    "status": "already_sealed",
                    "seal_timestamp": existing_seal.seal_timestamp.isoformat(),
                    "session_digest": existing_seal.session_digest,
                    "event_count": existing_seal.event_count,
                }

            # CHECK FOR SESSION_END (CONSTITUTIONAL REQUIREMENT)
            has_session_end = (
                db.query(EventChain)
                .filter(
                    EventChain.session_id == session.session_id_str,
                    EventChain.event_type == "SESSION_END",
                )
                .first()
                is not None
            )

            if not has_session_end:
                raise ValueError(
                    f"Cannot seal session {session_id} without SESSION_END event. "
                    f"This is a constitutional requirement for AUTHORITATIVE_EVIDENCE."
                )

            # Get final event
            final_event = (
                db.query(EventChain)
                .filter(EventChain.session_id == session.session_id_str)
                .order_by(EventChain.sequence_number.desc())
                .first()
            )

            if not final_event:
                raise ValueError(f"Cannot seal empty session {session_id}")

            # Count events
            event_count = (
                db.query(EventChain).filter(EventChain.session_id == session.session_id_str).count()
            )

            # Create seal
            seal_timestamp = datetime.now(UTC)
            session_digest = final_event.event_hash  # Final hash is session digest

            chain_seal = ChainSeal(
                session_id=session.id,
                ingestion_service_id=self.service_id,
                seal_timestamp=seal_timestamp,
                session_digest=session_digest,
                final_event_hash=final_event.event_hash,
                event_count=event_count,
            )

            db.add(chain_seal)

            # Update session status
            # Note: status is Mapped, sealed_at still needs ignore (Column)
            session.status = SessionStatus.SEALED
            session.sealed_at = seal_timestamp  # type: ignore[assignment]

            db.commit()

            return {
                "status": "sealed",
                "seal_timestamp": seal_timestamp.isoformat(),
                "session_digest": session_digest,
                "event_count": event_count,
            }

        finally:
            db.close()

    # --- Private helper methods ---

    def _get_last_event_hash(self, db: DBSession, session: Session) -> str | None:
        """Get hash of last event in session, or None if no events."""
        last_event = (
            db.query(EventChain)
            .filter(EventChain.session_id == session.session_id_str)
            .order_by(EventChain.sequence_number.desc())
            .first()
        )

        # Cast Column to runtime str (ORM returns actual value at runtime)
        return str(last_event.event_hash) if last_event else verifier_core.GENESIS_HASH

    def _get_last_sequence(self, db: DBSession, session: Session) -> int:
        """Get last sequence number in session, or -1 if no events."""
        last_event = (
            db.query(EventChain)
            .filter(EventChain.session_id == session.session_id_str)
            .order_by(EventChain.sequence_number.desc())
            .first()
        )

        # Cast Column to runtime int (ORM returns actual value at runtime)
        return int(last_event.sequence_number) if last_event else -1

    def _validate_sequence(
        self, db: DBSession, session: Session, events: list[dict[str, Any]]
    ) -> None:
        """
        Validate sequence continuity with HARD REJECTION RULES.

        Rules:
        - Next sequence MUST equal (last_sequence + 1)
        - Duplicate → emit LOG_DROP + reject
        - Gap → emit LOG_DROP with sequence range + reject
        - NO auto-heal, NO reordering

        Raises:
            SequenceViolation: On any violation
        """
        last_seq = self._get_last_sequence(db, session)

        for event in events:
            seq = event.get("sequence_number")
            if seq is None:
                raise SequenceViolation("Missing sequence_number")

            expected = last_seq + 1

            if seq < expected:
                # Duplicate or replay
                self._emit_log_drop(
                    db,
                    session,
                    reason="DUPLICATE_SEQUENCE",
                    dropped_count=0,
                    first_missing_seq=seq,
                    last_missing_seq=seq,
                )
                raise SequenceViolation(
                    f"Duplicate sequence: expected {expected}, got {seq}"
                )
            elif seq > expected:
                # Gap detected - record range
                gap_size = seq - expected
                self._emit_log_drop(
                    db,
                    session,
                    reason="SEQUENCE_GAP",
                    dropped_count=gap_size,
                    first_missing_seq=expected,
                    last_missing_seq=seq - 1,
                )
                raise SequenceViolation(
                    f"Sequence gap: expected {expected}, got {seq}. Gap size: {gap_size}"
                )

            # Valid - advance
            last_seq = seq

    def _emit_log_drop(
        self,
        db: DBSession,
        session: Session,
        reason: str,
        dropped_count: int,
        first_missing_seq: int | None = None,
        last_missing_seq: int | None = None,
    ) -> None:
        """
        Emit LOG_DROP meta-event and increment session drop counter.

        CONSTITUTIONAL REQUIREMENT: Record sequence ranges for forensic traceability.

        AUDIT GUARANTEE: This function commits immediately to ensure LOG_DROP is
        persisted even when the batch is subsequently rejected via SequenceViolation.
        This is INTENTIONAL for audit integrity - we must record WHY a batch was
        rejected, not just silently discard it.

        The session row lock (acquired via with_for_update() in append_events)
        prevents race conditions during concurrent writes.

        Args:
            db: Database session (with row lock held on session)
            session: Session model (locked)
            reason: Drop reason (DUPLICATE_SEQUENCE, SEQUENCE_GAP, etc.)
            dropped_count: Number of events dropped
            first_missing_seq: First sequence number in gap (if known)
            last_missing_seq: Last sequence number in gap (if known)
        """
        # Increment session drop counter
        # Cast Column to int and back for type checker
        current_drops: int = int(session.total_drops) if session.total_drops else 0
        session.total_drops = current_drops + dropped_count  # type: ignore[assignment]

        # Create LOG_DROP event in chain
        # NOTE: This should consume a sequence number itself
        last_seq = self._get_last_sequence(db, session)
        next_seq = last_seq + 1

        log_drop_payload = {
            "dropped_count": dropped_count,
            "drop_reason": reason,
            "first_missing_sequence": first_missing_seq,
            "last_missing_sequence": last_missing_seq,
            "cumulative_drops": session.total_drops,
        }

        # Compute hashes
        payload_hash = verifier_core.compute_payload_hash(log_drop_payload)
        prev_hash = self._get_last_event_hash(db, session)

        # Compute single timestamp for consistency
        now_ts = datetime.now(UTC).replace(microsecond=0)
        timestamp_iso = now_ts.isoformat().replace("+00:00", "Z")

        event_envelope = {
            "event_id": str(uuid.uuid4()),
            "session_id": str(session.session_id_str),
            "sequence_number": next_seq,
            "timestamp_wall": timestamp_iso,
            "event_type": "LOG_DROP",
            "payload_hash": payload_hash,
            "prev_event_hash": prev_hash,
        }

        event_hash = verifier_core.compute_event_hash(event_envelope)

        # Store LOG_DROP event
        log_drop_event = EventChain(
            event_id=uuid.UUID(str(event_envelope["event_id"])),
            session_id=session.session_id_str,
            sequence_number=next_seq,
            timestamp_wall=now_ts.replace(tzinfo=None),
            timestamp_monotonic=0,  # Not critical for LOG_DROP
            event_type="LOG_DROP",
            source_sdk_ver="ingestion-service",
            schema_ver="v0.6",
            payload_canonical=verifier_core.jcs.canonicalize(log_drop_payload).decode(
                "utf-8"
            ),
            payload_hash=payload_hash,
            prev_event_hash=prev_hash,
            event_hash=event_hash,
            chain_authority=session.chain_authority,
        )

        db.add(log_drop_event)
        db.commit()
