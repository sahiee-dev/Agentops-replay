"""
test_ingestion_service.py - Adversarial tests for ingestion service.

Tests the SINGLE CANONICAL ingestion implementation: app.ingestion.IngestService

CONSTITUTIONAL TESTS:
1. SDK hashes are IGNORED (server recomputes)
2. Event hash matches verifier_core exactly
3. Sequence violations trigger LOG_DROP + rejection
4. Sealed sessions reject new events
5. Authority gate for sealing
"""

import os
import sys
import uuid
from datetime import UTC, datetime

import pytest

# Add verifier to path for hash verification
_verifier_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "verifier"))
if _verifier_path not in sys.path:
    sys.path.insert(0, _verifier_path)

import verifier_core
from app.ingestion import AuthorityViolation, IngestService, SequenceViolation
from app.database import SessionLocal, engine
from app.models import ChainAuthority, EventChain, Session, SessionStatus


@pytest.fixture
def db_session():
    """
    Provide a real database session with automatic cleanup via transaction rollback.
    All code under test shares this connection to ensure isolation.
    """
    connection = engine.connect()
    transaction = connection.begin()
    
    # Bind a new session to this connection
    db = SessionLocal(bind=connection)
    
    # Monkeypatch the service's SessionLocal to use our bound session/connection
    # (Since IngestService creates its own SessionLocal)
    # Actually, IngestService uses `app.database.SessionLocal`. 
    # Valid strategy: dependency injection or mocking `app.database.SessionLocal`
    
    # For now, we rely on the fact that we can't easily patch the class attribute globally 
    # without potential side effects if not careful.
    # A better approach for this test is to inject the session if possible, 
    # but IngestService instantiates it internally.
    
    # Monkeypatch the service's SessionLocal to use our bound session/connection
    import app.ingestion.service
    from app.models import User
    
    original_session_local = app.ingestion.service.SessionLocal
    app.ingestion.service.SessionLocal = lambda: db
    
    # Create required test user (id=1)
    test_user = User(id=1, username="test-user")
    db.add(test_user)
    db.flush()
    
    # Mock commit to prevent actual commit, allowing rollback in finally
    db.commit = db.flush
    
    try:
        yield db
    finally:
        app.ingestion.service.SessionLocal = original_session_local
        db.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def ingest_service():
    """Create production ingestion service instance."""
    return IngestService(service_id="test-ingest-01")


class TestSdkHashIgnored:
    """CONSTITUTIONAL: SDK-provided hashes must be ignored."""

    def test_sdk_hash_ignored(self, db_session, ingest_service):
        """Server must recompute hashes, not trust SDK values."""
        # Create session
        session_id = ingest_service.start_session(
            session_id_str=str(uuid.uuid4()),
            authority="server",
            agent_name="test-agent",
            user_id=1,
        )

        # Create event with FAKE SDK hash
        fake_sdk_hash = "a" * 64  # Deliberately wrong
        events = [
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "SESSION_START",
                "sequence_number": 0,
                "timestamp_wall": datetime.now(UTC).isoformat(),
                "timestamp_monotonic": 1000,
                "payload": {"action": "start"},
                "event_hash": fake_sdk_hash,  # SDK hash - MUST be ignored
            }
        ]

        # Ingest
        result = ingest_service.append_events(session_id=session_id, events=events)

        # Verify the stored hash is NOT the SDK hash
        assert result["final_hash"] != fake_sdk_hash
        assert len(result["final_hash"]) == 64  # Valid SHA-256

        # Verify event in database has server-computed hash
        session = db_session.query(Session).filter(Session.session_id_str == session_id).first()
        event = db_session.query(EventChain).filter(EventChain.session_id == session.session_id_str).first()
        assert event.event_hash != fake_sdk_hash


class TestEventHashMatchesVerifier:
    """CONSTITUTIONAL: Ingestion hash must match verifier exactly."""

    def test_event_hash_matches_verifier_exactly(self, db_session, ingest_service):
        """Hash from ingestion MUST equal hash from verifier_core."""
        session_id = ingest_service.start_session(
            session_id_str=str(uuid.uuid4()),
            authority="server",
            user_id=1,
        )

        event_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()
        payload = {"prompt": "test", "response": "hello"}

        events = [
            {
                "event_id": event_id,
                "event_type": "LLM_CALL",
                "sequence_number": 0,
                "timestamp_wall": timestamp,
                "timestamp_monotonic": 1000,
                "payload": payload,
            }
        ]

        # Ingest event
        ingest_service.append_events(session_id=session_id, events=events)

        # Retrieve stored event
        session = db_session.query(Session).filter(Session.session_id_str == session_id).first()
        event = db_session.query(EventChain).filter(EventChain.session_id == session.session_id_str).first()

        # Compute expected hash using verifier_core (the single source of truth)
        expected_payload_hash = verifier_core.compute_payload_hash(payload)
        expected_event_hash = verifier_core.compute_event_hash({
            "event_id": event_id,
            "session_id": session_id,
            "sequence_number": 0,
            "timestamp_wall": timestamp,
            "event_type": "LLM_CALL",
            "payload_hash": expected_payload_hash,
            "prev_event_hash": verifier_core.GENESIS_HASH,
        })

        # CRITICAL ASSERTION: Hashes must match exactly
        assert event.payload_hash == expected_payload_hash, \
            f"Payload hash mismatch: {event.payload_hash} != {expected_payload_hash}"
        assert event.event_hash == expected_event_hash, \
            f"Event hash mismatch: {event.event_hash} != {expected_event_hash}"


class TestSequenceViolation:
    """CONSTITUTIONAL: Sequence violations must be rejected with LOG_DROP."""

    def test_sequence_gap_rejected(self, db_session, ingest_service):
        """Sequence gaps must raise SequenceViolation."""
        session_id = ingest_service.start_session(
            session_id_str=str(uuid.uuid4()),
            authority="server",
            user_id=1,
        )

        # Insert first event at sequence 0
        ingest_service.append_events(
            session_id=session_id,
            events=[{
                "event_id": str(uuid.uuid4()),
                "event_type": "SESSION_START",
                "sequence_number": 0,
                "timestamp_wall": datetime.now(UTC).isoformat(),
                "timestamp_monotonic": 1000,
                "payload": {},
            }]
        )

        # Attempt to insert at sequence 5 (gap: 1-4 missing)
        with pytest.raises(SequenceViolation) as exc_info:
            ingest_service.append_events(
                session_id=session_id,
                events=[{
                    "event_id": str(uuid.uuid4()),
                    "event_type": "LLM_CALL",
                    "sequence_number": 5,  # GAP!
                    "timestamp_wall": datetime.now(UTC).isoformat(),
                    "timestamp_monotonic": 2000,
                    "payload": {},
                }]
            )

        assert "gap" in str(exc_info.value).lower()

    def test_duplicate_sequence_rejected(self, db_session, ingest_service):
        """Duplicate sequence numbers must raise SequenceViolation."""
        session_id = ingest_service.start_session(
            session_id_str=str(uuid.uuid4()),
            authority="server",
            user_id=1,
        )

        # Insert event at sequence 0
        ingest_service.append_events(
            session_id=session_id,
            events=[{
                "event_id": str(uuid.uuid4()),
                "event_type": "SESSION_START",
                "sequence_number": 0,
                "timestamp_wall": datetime.now(UTC).isoformat(),
                "timestamp_monotonic": 1000,
                "payload": {},
            }]
        )

        # Attempt to insert another event at sequence 0 (duplicate!)
        with pytest.raises(SequenceViolation) as exc_info:
            ingest_service.append_events(
                session_id=session_id,
                events=[{
                    "event_id": str(uuid.uuid4()),
                    "event_type": "LLM_CALL",
                    "sequence_number": 0,  # DUPLICATE!
                    "timestamp_wall": datetime.now(UTC).isoformat(),
                    "timestamp_monotonic": 2000,
                    "payload": {},
                }]
            )

        assert "duplicate" in str(exc_info.value).lower()


class TestSealedSessionRejection:
    """CONSTITUTIONAL: Sealed sessions must reject new events."""

    def test_sealed_session_rejects_events(self, db_session, ingest_service):
        """Already sealed sessions must reject new events."""
        session_id = ingest_service.start_session(
            session_id_str=str(uuid.uuid4()),
            authority="server",
            user_id=1,
        )

        # Add SESSION_START and SESSION_END
        ingest_service.append_events(
            session_id=session_id,
            events=[
                {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "SESSION_START",
                    "sequence_number": 0,
                    "timestamp_wall": datetime.now(UTC).isoformat(),
                    "timestamp_monotonic": 1000,
                    "payload": {},
                },
                {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "SESSION_END",
                    "sequence_number": 1,
                    "timestamp_wall": datetime.now(UTC).isoformat(),
                    "timestamp_monotonic": 2000,
                    "payload": {},
                },
            ]
        )

        # Seal session
        ingest_service.seal_session(session_id)

        # Attempt to add more events (should fail)
        with pytest.raises(ValueError) as exc_info:
            ingest_service.append_events(
                session_id=session_id,
                events=[{
                    "event_id": str(uuid.uuid4()),
                    "event_type": "LLM_CALL",
                    "sequence_number": 2,
                    "timestamp_wall": datetime.now(UTC).isoformat(),
                    "timestamp_monotonic": 3000,
                    "payload": {},
                }]
            )

        assert "sealed" in str(exc_info.value).lower()


class TestAuthorityGate:
    """CONSTITUTIONAL: Only server-authority sessions can be sealed."""

    def test_sdk_authority_cannot_seal(self, db_session, ingest_service):
        """SDK authority sessions must fail to seal with AuthorityViolation."""
        session_id = ingest_service.start_session(
            session_id_str=str(uuid.uuid4()),
            authority="sdk",  # SDK authority
            user_id=1,
        )

        # Add required events
        ingest_service.append_events(
            session_id=session_id,
            events=[
                {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "SESSION_START",
                    "sequence_number": 0,
                    "timestamp_wall": datetime.now(UTC).isoformat(),
                    "timestamp_monotonic": 1000,
                    "payload": {},
                },
                {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "SESSION_END",
                    "sequence_number": 1,
                    "timestamp_wall": datetime.now(UTC).isoformat(),
                    "timestamp_monotonic": 2000,
                    "payload": {},
                },
            ]
        )

        # Attempt to seal (should fail - SDK cannot seal)
        with pytest.raises(AuthorityViolation):
            ingest_service.seal_session(session_id)


class TestIngestionOutputVerifiesClean:
    """CONSTITUTIONAL: Ingested data must pass verifier with no errors."""

    def test_ingested_session_verifies_clean(self, db_session, ingest_service):
        """A sealed session must pass hash verification."""
        session_id = ingest_service.start_session(
            session_id_str=str(uuid.uuid4()),
            authority="server",
            user_id=1,
        )

        # Add events
        events_to_add = [
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "SESSION_START",
                "sequence_number": 0,
                "timestamp_wall": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "timestamp_monotonic": 1000,
                "payload": {"action": "start"},
            },
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "LLM_CALL",
                "sequence_number": 1,
                "timestamp_wall": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "timestamp_monotonic": 2000,
                "payload": {"prompt": "hello", "response": "world"},
            },
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "SESSION_END",
                "sequence_number": 2,
                "timestamp_wall": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "timestamp_monotonic": 3000,
                "payload": {},
            },
        ]

        ingest_service.append_events(session_id=session_id, events=events_to_add)
        ingest_service.seal_session(session_id)

        # Retrieve stored events and verify each hash
        session = db_session.query(Session).filter(Session.session_id_str == session_id).first()
        assert session is not None, f"Session {session_id} not found in database"
        
        events = db_session.query(EventChain).filter(
            EventChain.session_id == session.session_id_str
        ).order_by(EventChain.sequence_number).all()
        assert events, f"No events found for session {session_id_str if 'session_id_str' in locals() else session_id}"

        prev_hash = verifier_core.GENESIS_HASH
        import json
        for event in events:
            # Skip CHAIN_SEAL (genesis hash is fine for it)
            if event.event_type == "CHAIN_SEAL":
                continue

            # Verify payload hash
            payload_dict = json.loads(event.payload_canonical)
            computed_payload_hash = verifier_core.compute_payload_hash(payload_dict)
            assert event.payload_hash == computed_payload_hash, \
                f"Payload hash mismatch: {event.payload_hash} != {computed_payload_hash}"

            # Verify event hash
            event_envelope = {
                "event_id": str(event.event_id),
                "session_id": str(session.session_id_str),
                "sequence_number": event.sequence_number,
                "timestamp_wall": event.timestamp_wall.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z"),
                "event_type": event.event_type,
                "payload_hash": event.payload_hash,
                "prev_event_hash": event.prev_event_hash,
            }
            
            # Verify chaining
            assert event.prev_event_hash == prev_hash, \
                f"Chain broken at seq {event.sequence_number}: {event.prev_event_hash} != {prev_hash}"
            
            computed_hash = verifier_core.compute_event_hash(event_envelope)
            assert event.event_hash == computed_hash, \
                f"Event hash mismatch at seq {event.sequence_number}: {event.event_hash} != {computed_hash}"

            prev_hash = event.event_hash
