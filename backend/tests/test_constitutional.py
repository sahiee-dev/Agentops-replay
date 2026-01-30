"""
Test suite for constitutional guarantees.

Tests validate:
- Append-only enforcement
- Server-side hash recomputation
- SESSION_END enforcement
- Binary evidence classification
- CHAIN_SEAL authority gate
"""

import os
import sys

import pytest

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../verifier"))

import uuid
from datetime import UTC, datetime

from app.database import SessionLocal
from app.ingestion import AuthorityViolation, IngestService, SequenceViolation
from app.models import ChainAuthority, ChainSeal, EventChain, Session, SessionStatus

import verifier_core


@pytest.fixture
def db_session():
    """Test database session."""
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def ingest_service():
    """Ingestion service instance."""
    return IngestService(service_id="test-ingest-01")


class TestConstitutionalGuarantees:
    """Test constitutional requirements."""

    def test_server_side_hash_recomputation(self, ingest_service):
        """
        CRITICAL: Server MUST recompute hashes, ignoring SDK hashes.
        """
        # Start session
        session_id = ingest_service.start_session(authority="server")

        # Create event with WRONG hash (SDK lie)
        events = [
            {
                "sequence_number": 0,
                "timestamp_wall": datetime.now(UTC).isoformat(),
                "event_type": "TEST",
                "payload": {"data": "test"},
                # Intentionally wrong hashes (should be ignored)
                "payload_hash": "WRONG_HASH",
                "event_hash": "WRONG_HASH",
            }
        ]

        # Server should accept and recompute
        result = ingest_service.append_events(session_id, events)
        assert result["status"] == "success"

        # Verify server recomputed correct hash
        db = SessionLocal()
        session = (
            db.query(Session)
            .filter(Session.session_id_str == uuid.UUID(session_id))
            .first()
        )

        event = db.query(EventChain).filter(EventChain.session_id == session.id).first()

        # Hash should be correct, not "WRONG_HASH"
        assert event.payload_hash != "WRONG_HASH"
        assert len(event.payload_hash) == 64  # Valid SHA-256

        # Verify using verifier_core
        assert verifier_core.verify_payload_hash(
            {"payload": event.payload_jsonb, "payload_hash": event.payload_hash}
        )

        db.close()

    def test_sequence_gap_rejection(self, ingest_service):
        """
        CRITICAL: Sequence gaps MUST be hard-rejected with LOG_DROP.
        """
        session_id = ingest_service.start_session(authority="server")

        # First event (seq 0)
        events = [
            {
                "sequence_number": 0,
                "timestamp_wall": datetime.now(UTC).isoformat(),
                "event_type": "TEST",
                "payload": {"data": "event0"},
            }
        ]
        ingest_service.append_events(session_id, events)

        # Gap: Jump to seq 5 (missing 1-4)
        events = [
            {
                "sequence_number": 5,
                "timestamp_wall": datetime.now(UTC).isoformat(),
                "event_type": "TEST",
                "payload": {"data": "event5"},
            }
        ]

        # MUST reject
        with pytest.raises(SequenceViolation) as exc_info:
            ingest_service.append_events(session_id, events)

        assert "Sequence gap" in str(exc_info.value)

        # Verify LOG_DROP was emitted
        db = SessionLocal()
        session = (
            db.query(Session)
            .filter(Session.session_id_str == uuid.UUID(session_id))
            .first()
        )

        assert session.total_drops > 0

        # Verify LOG_DROP event exists with sequence range
        log_drop = (
            db.query(EventChain)
            .filter(
                EventChain.session_id == session.id, EventChain.event_type == "LOG_DROP"
            )
            .first()
        )

        assert log_drop is not None
        assert log_drop.payload_jsonb["first_missing_sequence"] == 1
        assert log_drop.payload_jsonb["last_missing_sequence"] == 4

        db.close()

    def test_seal_requires_session_end(self, ingest_service):
        """
        CRITICAL: Seal MUST fail if SESSION_END not present.
        """
        session_id = ingest_service.start_session(authority="server")

        # Add some events but NO SESSION_END
        events = [
            {
                "sequence_number": 0,
                "timestamp_wall": datetime.now(UTC).isoformat(),
                "event_type": "TEST",
                "payload": {"data": "test"},
            }
        ]
        ingest_service.append_events(session_id, events)

        # Attempt to seal WITHOUT SESSION_END
        with pytest.raises(ValueError) as exc_info:
            ingest_service.seal_session(session_id)

        assert "SESSION_END" in str(exc_info.value)
        assert "constitutional requirement" in str(exc_info.value).lower()

    def test_seal_authority_gate(self, ingest_service):
        """
        CRITICAL: Only SERVER authority sessions can be sealed.
        """
        # Create SDK authority session
        session_id = ingest_service.start_session(authority="sdk")

        # Add SESSION_END
        events = [
            {
                "sequence_number": 0,
                "timestamp_wall": datetime.now(UTC).isoformat(),
                "event_type": "SESSION_START",
                "payload": {},
            },
            {
                "sequence_number": 1,
                "timestamp_wall": datetime.now(UTC).isoformat(),
                "event_type": "SESSION_END",
                "payload": {},
            },
        ]
        ingest_service.append_events(session_id, events)

        # Attempt to seal SDK session
        with pytest.raises(AuthorityViolation) as exc_info:
            ingest_service.seal_session(session_id)

        assert "server authority" in str(exc_info.value).lower()

    def test_binary_evidence_classification(self, ingest_service):
        """
        CRITICAL: Evidence MUST be AUTHORITATIVE or NON_AUTHORITATIVE only.
        """
        # Test AUTHORITATIVE path (all conditions met)
        result = verifier_core.classify_evidence(
            authority="server", sealed=True, complete=True, has_drops=False
        )
        assert result == "AUTHORITATIVE_EVIDENCE"

        # Test NON_AUTHORITATIVE (any condition fails)

        # SDK authority
        result = verifier_core.classify_evidence(
            authority="sdk", sealed=True, complete=True, has_drops=False
        )
        assert result == "NON_AUTHORITATIVE_EVIDENCE"

        # Server but not sealed
        result = verifier_core.classify_evidence(
            authority="server", sealed=False, complete=True, has_drops=False
        )
        assert result == "NON_AUTHORITATIVE_EVIDENCE"

        # Server but has drops
        result = verifier_core.classify_evidence(
            authority="server", sealed=True, complete=True, has_drops=True
        )
        assert result == "NON_AUTHORITATIVE_EVIDENCE"

        # Server but incomplete
        result = verifier_core.classify_evidence(
            authority="server", sealed=True, complete=False, has_drops=False
        )
        assert result == "NON_AUTHORITATIVE_EVIDENCE"

    def test_seal_idempotency(self, ingest_service):
        """
        CRITICAL: Second seal call MUST return original seal.
        """
        session_id = ingest_service.start_session(authority="server")

        # Add SESSION_END
        events = [
            {
                "sequence_number": 0,
                "timestamp_wall": datetime.now(UTC).isoformat(),
                "event_type": "SESSION_END",
                "payload": {},
            }
        ]
        ingest_service.append_events(session_id, events)

        # First seal
        result1 = ingest_service.seal_session(session_id)
        assert result1["status"] == "sealed"
        digest1 = result1["session_digest"]

        # Second seal (should return same)
        result2 = ingest_service.seal_session(session_id)
        assert result2["status"] == "already_sealed"
        assert result2["session_digest"] == digest1


class TestEndToEndFlow:
    """Test complete AUTHORITATIVE_EVIDENCE flow."""

    def test_full_authoritative_flow(self, ingest_service):
        """
        End-to-end test: SDK → Server → AUTHORITATIVE_EVIDENCE
        """
        # 1. Start server authority session
        session_id = ingest_service.start_session(
            authority="server", agent_name="test-agent", user_id=None
        )

        # 2. Append events with perfect sequence
        events = [
            {
                "sequence_number": 0,
                "timestamp_wall": datetime.now(UTC).isoformat(),
                "event_type": "TOOL_CALL",
                "payload": {"tool": "search", "query": "test"},
            },
            {
                "sequence_number": 1,
                "timestamp_wall": datetime.now(UTC).isoformat(),
                "event_type": "TOOL_RESULT",
                "payload": {"result": "data"},
            },
            {
                "sequence_number": 2,
                "timestamp_wall": datetime.now(UTC).isoformat(),
                "event_type": "SESSION_END",
                "payload": {"status": "SUCCESS"},
            },
        ]

        result = ingest_service.append_events(session_id, events)
        assert result["status"] == "success"
        assert result["accepted_count"] == 3

        # 3. Seal session
        seal_result = ingest_service.seal_session(session_id)
        assert seal_result["status"] == "sealed"
        assert seal_result["event_count"] == 3

        # 4. Verify session achieves AUTHORITATIVE_EVIDENCE
        db = SessionLocal()
        session = (
            db.query(Session)
            .filter(Session.session_id_str == uuid.UUID(session_id))
            .first()
        )

        # Check all conditions
        assert session.chain_authority == ChainAuthority.SERVER
        assert session.status == SessionStatus.SEALED
        assert session.total_drops == 0

        # Has seal
        seal = db.query(ChainSeal).filter(ChainSeal.session_id == session.id).first()
        assert seal is not None

        # Has SESSION_END
        has_end = (
            db.query(EventChain)
            .filter(
                EventChain.session_id == session.id,
                EventChain.event_type == "SESSION_END",
            )
            .count()
            > 0
        )
        assert has_end

        # Classify evidence
        evidence_class = verifier_core.classify_evidence(
            authority="server", sealed=True, complete=True, has_drops=False
        )
        assert evidence_class == "AUTHORITATIVE_EVIDENCE"

        db.close()
