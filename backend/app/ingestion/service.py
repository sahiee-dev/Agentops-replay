"""
service.py - Production ingestion service with constitutional guarantees.

CRITICAL REQUIREMENTS:
1. Server-side hash recomputation (ignore SDK hashes)
2. Hard sequence rejection rules (no auto-heal)
3. Authority gate for CHAIN_SEAL
4. Atomic batch commits
"""

import sys
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session as DBSession
from sqlalchemy.exc import IntegrityError
import uuid

# Add verifier to Python path for shared hash functions
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../verifier'))
import verifier_core

from app.models import Session, EventChain, ChainSeal, ChainAuthority, SessionStatus
from app.database import SessionLocal


class SequenceViolation(Exception):
    """Raised when sequence validation fails."""
    pass


class AuthorityViolation(Exception):
    """Raised when authority checks fail."""
    pass


class IngestService:
    """
    Production ingestion service implementing EVENT_LOG_SPEC.md v0.6.
    
    Constitutional guarantees:
    - Server-side hash recomputation
    - Hard sequence rejection
    - Authority enforcement
    - Append-only storage
    """
    
    def __init__(self, service_id: Optional[str] = None):
        """
        Create an IngestService and set its immutable service identifier used for CHAIN_SEAL records.
        
        Parameters:
            service_id (Optional[str]): Static ingestion service identifier set at startup. If omitted, the value is read from the INGESTION_SERVICE_ID environment variable or defaults to "default-ingest-01". This identifier is immutable for the lifetime of the service.
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
        session_id_str: Optional[str] = None,
        authority: str = "server",
        agent_name: Optional[str] = None,
        user_id: Optional[int] = None
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
            raise ValueError(f"Invalid authority: {authority}. Must be 'server' or 'sdk'")
        
        db = SessionLocal()
        try:
            # Create session
            session_uuid = uuid.UUID(session_id_str) if session_id_str else uuid.uuid4()
            
            chain_auth = ChainAuthority.SERVER if authority == "server" else ChainAuthority.SDK
            
            session = Session(
                session_id_str=session_uuid,
                chain_authority=chain_auth,
                status=SessionStatus.ACTIVE,
                agent_name=agent_name,
                user_id=user_id,
                ingestion_service_id=self.service_id if authority == "server" else None
            )
            
            db.add(session)
            db.commit()
            db.refresh(session)
            
            return str(session.session_id_str)
        
        finally:
            db.close()
    
    def append_events(
        self,
        session_id: str,
        events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Append a batch of events to an active session while enforcing server-side hash recomputation, strict sequence validation, and atomic commit semantics.
        
        Returns:
            dict: {
                'status': 'success',
                'accepted_count': int,   # number of events persisted
                'final_hash': Optional[str]  # event hash of the last persisted event or None if no prior events
            }
        
        Raises:
            SequenceViolation: If incoming events contain duplicate sequence numbers or gaps.
            ValueError: If the session is not found, not active, or a database integrity error occurs.
        """
        db = SessionLocal()
        try:
            # Get session
            session = db.query(Session).filter(
                Session.session_id_str == uuid.UUID(session_id)
            ).first()
            
            if not session:
                raise ValueError(f"Session {session_id} not found")
            
            if session.status != SessionStatus.ACTIVE:
                raise ValueError(f"Session {session_id} is not active (status: {session.status})")
            
            # Validate sequence continuity
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
                    "prev_event_hash": prev_hash
                }
                
                # Compute event hash
                event_hash = verifier_core.compute_event_hash(event_envelope)
                
                # Store in database
                event_chain = EventChain(
                    event_id=uuid.UUID(event_envelope["event_id"]),
                    session_id=session.id,
                    sequence_number=event_envelope["sequence_number"],
                    timestamp_wall=datetime.fromisoformat(event_envelope["timestamp_wall"].replace('Z', '+00:00')),
                    timestamp_monotonic=event_data.get("timestamp_monotonic", 0),
                    event_type=event_envelope["event_type"],
                    source_sdk_ver=event_data.get("source_sdk_ver"),
                    schema_ver=event_data.get("schema_ver", "v0.6"),
                    payload_canonical=verifier_core.jcs.canonicalize(payload).decode('utf-8'),
                    payload_hash=payload_hash,
                    payload_jsonb=payload,
                    prev_event_hash=prev_hash,
                    event_hash=event_hash
                )
                
                db.add(event_chain)
                stored_events.append(event_chain)
                
                # Update for next iteration
                prev_hash = event_hash
                
                # Track LOG_DROP events
                if event_data["event_type"] == "LOG_DROP":
                    dropped_count = payload.get("dropped_count", 0)
                    session.total_drops += dropped_count
            
            # Atomic commit
            db.commit()
            
            return {
                "status": "success",
                "accepted_count": len(events),
                "final_hash": prev_hash
            }
        
        except IntegrityError as e:
            db.rollback()
            raise ValueError(f"Database integrity error: {e}")
        
        finally:
            db.close()
    
    def seal_session(self, session_id: str) -> Dict[str, Any]:
        """
        Create a ChainSeal for the given session and mark the session as sealed.
        
        If the session is already sealed, return the existing seal metadata; sealing is allowed only for sessions with server authority and requires a prior SESSION_END event.
        
        Parameters:
            session_id (str): Session UUID string.
        
        Returns:
            dict: Seal metadata with keys:
                - "status": "sealed" or "already_sealed"
                - "seal_timestamp": ISO 8601 UTC timestamp of the seal
                - "session_digest": final event hash used as the session digest
                - "event_count": number of events in the session
        
        Raises:
            AuthorityViolation: If the session's authority is not SERVER.
            ValueError: If the session does not exist, is empty, or lacks a SESSION_END event.
        """
        db = SessionLocal()
        try:
            # Get session
            session = db.query(Session).filter(
                Session.session_id_str == uuid.UUID(session_id)
            ).first()
            
            if not session:
                raise ValueError(f"Session {session_id} not found")
            
            # AUTHORITY GATE
            if session.chain_authority != ChainAuthority.SERVER:
                raise AuthorityViolation(
                    f"Only server authority sessions can be sealed. "
                    f"Session {session_id} has authority: {session.chain_authority}"
                )
            
            # IDEMPOTENCY CHECK
            existing_seal = db.query(ChainSeal).filter(
                ChainSeal.session_id == session.id
            ).first()
            
            if existing_seal:
                # Return existing seal
                return {
                    "status": "already_sealed",
                    "seal_timestamp": existing_seal.seal_timestamp.isoformat(),
                    "session_digest": existing_seal.session_digest,
                    "event_count": existing_seal.event_count
                }
            
            # CHECK FOR SESSION_END (CONSTITUTIONAL REQUIREMENT)
            has_session_end = db.query(EventChain).filter(
                EventChain.session_id == session.id,
                EventChain.event_type == "SESSION_END"
            ).first() is not None
            
            if not has_session_end:
                raise ValueError(
                    f"Cannot seal session {session_id} without SESSION_END event. "
                    f"This is a constitutional requirement for AUTHORITATIVE_EVIDENCE."
                )
            
            # Get final event
            final_event = db.query(EventChain).filter(
                EventChain.session_id == session.id
            ).order_by(EventChain.sequence_number.desc()).first()
            
            if not final_event:
                raise ValueError(f"Cannot seal empty session {session_id}")
            
            # Count events
            event_count = db.query(EventChain).filter(
                EventChain.session_id == session.id
            ).count()
            
            # Create seal
            seal_timestamp = datetime.now(timezone.utc)
            session_digest = final_event.event_hash  # Final hash is session digest
            
            chain_seal = ChainSeal(
                session_id=session.id,
                ingestion_service_id=self.service_id,
                seal_timestamp=seal_timestamp,
                session_digest=session_digest,
                final_event_hash=final_event.event_hash,
                event_count=event_count
            )
            
            db.add(chain_seal)
            
            # Update session status
            session.status = SessionStatus.SEALED
            session.sealed_at = seal_timestamp
            
            db.commit()
            
            return {
                "status": "sealed",
                "seal_timestamp": seal_timestamp.isoformat(),
                "session_digest": session_digest,
                "event_count": event_count
            }
        
        finally:
            db.close()
    
    # --- Private helper methods ---
    
    def _get_last_event_hash(self, db: DBSession, session: Session) -> Optional[str]:
        """
        Return the `event_hash` of the most recent EventChain for the given session, or `None` if the session has no events.
        
        Returns:
            str | None: The `event_hash` of the last event for the session, or `None` when no events exist.
        """
        last_event = db.query(EventChain).filter(
            EventChain.session_id == session.id
        ).order_by(EventChain.sequence_number.desc()).first()
        
        return last_event.event_hash if last_event else None
    
    def _get_last_sequence(self, db: DBSession, session: Session) -> int:
        """
        Return the highest sequence number recorded for the given session.
        
        Returns:
            int: The highest sequence number present for the session, or -1 if the session has no events.
        """
        last_event = db.query(EventChain).filter(
            EventChain.session_id == session.id
        ).order_by(EventChain.sequence_number.desc()).first()
        
        return last_event.sequence_number if last_event else -1
    
    def _validate_sequence(
        self,
        db: DBSession,
        session: Session,
        events: List[Dict[str, Any]]
    ):
        """
        Enforce strict sequence continuity for a batch of incoming events and raise on any violation.
        
        Validates that each event's `sequence_number` equals the previous stored sequence plus one. On a duplicate or gap, records a corresponding `LOG_DROP` event and raises `SequenceViolation`. If an event is missing `sequence_number`, raises `SequenceViolation`.
        
        Parameters:
            events (List[Dict[str, Any]]): Incoming events; each dict must include a `sequence_number` key.
        
        Raises:
            SequenceViolation: If an event is missing `sequence_number`, if a duplicate sequence is detected, or if a sequence gap is detected.
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
                    db, session, 
                    reason="DUPLICATE_SEQUENCE", 
                    dropped_count=0,
                    first_missing_seq=seq,
                    last_missing_seq=seq
                )
                raise SequenceViolation(
                    f"Duplicate sequence: expected {expected}, got {seq}"
                )
            elif seq > expected:
                # Gap detected - record range
                gap_size = seq - expected
                self._emit_log_drop(
                    db, session, 
                    reason="SEQUENCE_GAP", 
                    dropped_count=gap_size,
                    first_missing_seq=expected,
                    last_missing_seq=seq - 1
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
        first_missing_seq: Optional[int] = None,
        last_missing_seq: Optional[int] = None
    ):
        """
        Create and persist a LOG_DROP meta-event and update the session's drop counter.
        
        This records a forensics-friendly representation of dropped or duplicate sequences, consumes the next sequence number for the session, increments session.total_drops by `dropped_count`, and persists the LOG_DROP EventChain to the database.
        
        Parameters:
            db (DBSession): Active database session used for persistence.
            session (Session): Session model to which the LOG_DROP belongs.
            reason (str): Drop reason identifier (e.g., "DUPLICATE_SEQUENCE", "SEQUENCE_GAP").
            dropped_count (int): Number of events that were dropped or considered missing.
            first_missing_seq (Optional[int]): First sequence number in a missing range, if known.
            last_missing_seq (Optional[int]): Last sequence number in a missing range, if known.
        """
        # Increment session drop counter
        session.total_drops += dropped_count
        
        # Create LOG_DROP event in chain
        # NOTE: This should consume a sequence number itself
        last_seq = self._get_last_sequence(db, session)
        next_seq = last_seq + 1
        
        log_drop_payload = {
            "dropped_count": dropped_count,
            "drop_reason": reason,
            "first_missing_sequence": first_missing_seq,
            "last_missing_sequence": last_missing_seq,
            "cumulative_drops": session.total_drops
        }
        
        # Compute hashes
        payload_hash = verifier_core.compute_payload_hash(log_drop_payload)
        prev_hash = self._get_last_event_hash(db, session)
        
        event_envelope = {
            "event_id": str(uuid.uuid4()),
            "session_id": str(session.session_id_str),
            "sequence_number": next_seq,
            "timestamp_wall": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "event_type": "LOG_DROP",
            "payload_hash": payload_hash,
            "prev_event_hash": prev_hash
        }
        
        event_hash = verifier_core.compute_event_hash(event_envelope)
        
        # Store LOG_DROP event
        log_drop_event = EventChain(
            event_id=uuid.UUID(event_envelope["event_id"]),
            session_id=session.id,
            sequence_number=next_seq,
            timestamp_wall=datetime.now(timezone.utc),
            timestamp_monotonic=0,  # Not critical for LOG_DROP
            event_type="LOG_DROP",
            source_sdk_ver="ingestion-service",
            schema_ver="v0.6",
            payload_canonical=verifier_core.jcs.canonicalize(log_drop_payload).decode('utf-8'),
            payload_hash=payload_hash,
            payload_jsonb=log_drop_payload,
            prev_event_hash=prev_hash,
            event_hash=event_hash
        )
        
        db.add(log_drop_event)
        db.commit()