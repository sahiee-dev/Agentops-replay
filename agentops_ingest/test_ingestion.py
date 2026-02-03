"""
agentops_ingest/test_ingestion.py - Ingestion Test Vectors

Tests:
- Valid event sealing
- Authority spoof rejection
- Payload hash mismatch rejection
- Sequence rewind rejection
- Timestamp ambiguity rejection
"""
import json
import pytest
from datetime import datetime, timezone

from .validator import validate_claim, ValidatedClaim
from .sealer import seal_event, ChainState
from .store import EventStore
from .errors import IngestException, IngestErrorCode


# --- VALID EVENT FIXTURE ---
def make_valid_event(seq: int = 0, session_id: str = "test-session-001") -> dict:
    return {
        "event_id": f"evt-{seq:03d}",
        "session_id": session_id,
        "sequence_number": seq,
        "timestamp_wall": "2023-10-01T12:00:00Z",
        "event_type": "AGENT_DECISION",
        "payload": {
            "input_facts": ["user_request"],
            "policy_version": "refund_v1",
            "outcome": "LOOKUP_TRANSACTION"
        },
    }


# --- VALIDATION TESTS ---
class TestValidator:
    
    def test_valid_event_passes(self):
        """Valid event should produce ValidatedClaim."""
        event = make_valid_event()
        claim = validate_claim(event)
        assert isinstance(claim, ValidatedClaim)
        assert claim.event_id == "evt-000"
        assert claim.sequence_number == 0
        assert claim.payload_hash is not None
    
    def test_authority_leak_event_hash_rejected(self):
        """Client-provided event_hash should be rejected."""
        event = make_valid_event()
        event["event_hash"] = "fake-hash"
        
        with pytest.raises(IngestException) as exc_info:
            validate_claim(event)
        
        assert exc_info.value.error.error_code == IngestErrorCode.AUTHORITY_LEAK
    
    def test_authority_leak_chain_authority_rejected(self):
        """Client-provided chain_authority should be rejected."""
        event = make_valid_event()
        event["chain_authority"] = "fake-authority"
        
        with pytest.raises(IngestException) as exc_info:
            validate_claim(event)
        
        assert exc_info.value.error.error_code == IngestErrorCode.AUTHORITY_LEAK
    
    def test_payload_hash_mismatch_rejected(self):
        """Mismatched payload_hash should be rejected."""
        event = make_valid_event()
        event["payload_hash"] = "0000000000000000000000000000000000000000000000000000000000000000"
        
        with pytest.raises(IngestException) as exc_info:
            validate_claim(event)
        
        assert exc_info.value.error.error_code == IngestErrorCode.PAYLOAD_HASH_MISMATCH
    
    def test_missing_required_field_rejected(self):
        """Missing required field should be rejected."""
        event = make_valid_event()
        del event["event_type"]
        
        with pytest.raises(IngestException) as exc_info:
            validate_claim(event)
        
        assert exc_info.value.error.error_code == IngestErrorCode.SCHEMA_INVALID
    
    def test_invalid_timestamp_rejected(self):
        """Invalid timestamp format should be rejected."""
        event = make_valid_event()
        event["timestamp_wall"] = "2023-10-01 12:00:00"  # No T, no timezone
        
        with pytest.raises(IngestException) as exc_info:
            validate_claim(event)
        
        assert exc_info.value.error.error_code == IngestErrorCode.TIMESTAMP_INVALID
    
    def test_timestamp_without_timezone_rejected(self):
        """Timestamp without timezone should be rejected."""
        event = make_valid_event()
        event["timestamp_wall"] = "2023-10-01T12:00:00"  # No Z or offset
        
        with pytest.raises(IngestException) as exc_info:
            validate_claim(event)
        
        assert exc_info.value.error.error_code == IngestErrorCode.TIMESTAMP_INVALID


# --- SEALER TESTS ---
class TestSealer:
    
    def test_first_event_seals_correctly(self):
        """First event (seq=0) should seal with prev_event_hash=None."""
        event = make_valid_event(seq=0)
        claim = validate_claim(event)
        sealed = seal_event(claim, chain_state=None, strict_mode=True)
        
        assert sealed.prev_event_hash is None
        assert sealed.event_hash is not None
        assert sealed.chain_authority == "agentops-ingest-v1"
    
    def test_second_event_links_to_first(self):
        """Second event should have prev_event_hash = first event's hash."""
        event1 = make_valid_event(seq=0)
        claim1 = validate_claim(event1)
        sealed1 = seal_event(claim1, chain_state=None, strict_mode=True)
        
        chain_state = ChainState(
            session_id="test-session-001",
            last_sequence=0,
            last_event_hash=sealed1.event_hash,
            is_closed=False,
        )
        
        event2 = make_valid_event(seq=1)
        claim2 = validate_claim(event2)
        sealed2 = seal_event(claim2, chain_state=chain_state, strict_mode=True)
        
        assert sealed2.prev_event_hash == sealed1.event_hash
        assert sealed2.event_hash != sealed1.event_hash
    
    def test_sequence_rewind_rejected(self):
        """Sequence rewind (seq <= last) should be rejected."""
        chain_state = ChainState(
            session_id="test-session-001",
            last_sequence=5,
            last_event_hash="abc123",
            is_closed=False,
        )
        
        event = make_valid_event(seq=3)  # Rewind
        claim = validate_claim(event)
        
        with pytest.raises(IngestException) as exc_info:
            seal_event(claim, chain_state=chain_state, strict_mode=True)
        
        assert exc_info.value.error.error_code == IngestErrorCode.SEQUENCE_REWIND
    
    def test_sequence_gap_rejected_strict_mode(self):
        """Sequence gap should be rejected in strict mode."""
        chain_state = ChainState(
            session_id="test-session-001",
            last_sequence=5,
            last_event_hash="abc123",
            is_closed=False,
        )
        
        event = make_valid_event(seq=10)  # Gap
        claim = validate_claim(event)
        
        with pytest.raises(IngestException) as exc_info:
            seal_event(claim, chain_state=chain_state, strict_mode=True)
        
        assert exc_info.value.error.error_code == IngestErrorCode.LOG_GAP
    
    def test_closed_session_rejected(self):
        """Event to closed session should be rejected."""
        chain_state = ChainState(
            session_id="test-session-001",
            last_sequence=5,
            last_event_hash="abc123",
            is_closed=True,  # Session closed
        )
        
        event = make_valid_event(seq=6)
        claim = validate_claim(event)
        
        with pytest.raises(IngestException) as exc_info:
            seal_event(claim, chain_state=chain_state, strict_mode=True)
        
        assert exc_info.value.error.error_code == IngestErrorCode.SESSION_CLOSED


# --- DETERMINISM TESTS ---
class TestDeterminism:
    
    def test_same_input_same_hash(self):
        """Same input must produce same event_hash (determinism)."""
        event = make_valid_event()
        
        claim1 = validate_claim(event)
        sealed1 = seal_event(claim1, chain_state=None, strict_mode=True)
        
        claim2 = validate_claim(event)
        sealed2 = seal_event(claim2, chain_state=None, strict_mode=True)
        
        assert sealed1.event_hash == sealed2.event_hash
        assert sealed1.payload_hash == sealed2.payload_hash


# --- CROSS-SESSION POISONING TESTS ---
class TestCrossSessionPoisoning:
    """
    Attack vector: Attempt to poison one session with data from another.
    """
    
    def test_same_event_id_different_sessions_isolated(self):
        """Same event_id in different sessions should be independently sealed."""
        event1 = make_valid_event(seq=0, session_id="session-A")
        event2 = make_valid_event(seq=0, session_id="session-B")
        # Same event_id by our fixture
        
        claim1 = validate_claim(event1)
        sealed1 = seal_event(claim1, chain_state=None, strict_mode=True)
        
        claim2 = validate_claim(event2)
        sealed2 = seal_event(claim2, chain_state=None, strict_mode=True)
        
        # Hashes must differ because session_id is part of signed preimage
        assert sealed1.event_hash != sealed2.event_hash
    
    def test_sequence_isolation_across_sessions(self):
        """Sequence numbers are per-session, not global."""

        
        # Session B at seq 0 (new session)
        # Attempting seq 0 should work for B, even though A is at 5
        event_b = make_valid_event(seq=0, session_id="session-B")
        claim_b = validate_claim(event_b)
        
        # This should succeed - B has no chain state
        sealed_b = seal_event(claim_b, chain_state=None, strict_mode=True)
        assert sealed_b.sequence_number == 0
    
    def test_cross_session_chain_state_rejected(self):
        """Cannot use session A's chain state to seal session B's event."""
        chain_a = ChainState(
            session_id="session-A",
            last_sequence=0,
            last_event_hash="aaa",
            is_closed=False,
        )
        
        # Event for session B
        event_b = make_valid_event(seq=1, session_id="session-B")
        claim_b = validate_claim(event_b)
        
        # Sealing B with A's chain state MUST fail now (Guard added)
        with pytest.raises(IngestException) as exc_info:
            seal_event(claim_b, chain_state=chain_a, strict_mode=True)
        
        # Check error message
        assert "Session ID mismatch" in str(exc_info.value)
        # assert sealed_b.session_id == "session-B"  # No longer reachable


# --- REPLAY ATTACK TESTS ---
class TestReplayAttacks:
    """
    Attack vector: Resubmit previously sealed events to corrupt the chain.
    """
    
    def test_resubmit_sealed_event_rejected_authority_leak(self):
        """Resubmitting a sealed event (with event_hash) should be rejected."""
        event = make_valid_event(seq=0)
        claim = validate_claim(event)
        sealed = seal_event(claim, chain_state=None, strict_mode=True)
        
        # Now try to resubmit the sealed event as raw input
        replay_attempt = {
            "event_id": sealed.event_id,
            "session_id": sealed.session_id,
            "sequence_number": sealed.sequence_number,
            "timestamp_wall": sealed.timestamp_wall,
            "event_type": sealed.event_type,
            "payload": json.loads(sealed.payload_jcs.decode('utf-8')),
            "event_hash": sealed.event_hash,  # AUTHORITY LEAK
            "chain_authority": sealed.chain_authority,  # AUTHORITY LEAK
        }
        
        with pytest.raises(IngestException) as exc_info:
            validate_claim(replay_attempt)
        
        assert exc_info.value.error.error_code == IngestErrorCode.AUTHORITY_LEAK
    
    def test_altered_payload_same_sequence_rejected(self):
        """Submitting altered payload at same sequence should be rejected."""
        # First, seal the original event
        original = make_valid_event(seq=0)
        claim1 = validate_claim(original)
        sealed1 = seal_event(claim1, chain_state=None, strict_mode=True)
        
        # Create chain state as if seq 0 was already ingested
        chain_state = ChainState(
            session_id="test-session-001",
            last_sequence=0,
            last_event_hash=sealed1.event_hash,
            is_closed=False,
        )
        
        # Now try to submit altered payload at seq 0 (rewind)
        altered = make_valid_event(seq=0)
        altered["payload"]["outcome"] = "TAMPERED_OUTCOME"
        
        claim2 = validate_claim(altered)
        
        with pytest.raises(IngestException) as exc_info:
            seal_event(claim2, chain_state=chain_state, strict_mode=True)
        
        assert exc_info.value.error.error_code == IngestErrorCode.SEQUENCE_REWIND
    
    def test_duplicate_sequence_different_payload_rejected(self):
        """Submitting different payload at already-ingested sequence is rewind."""
        chain_state = ChainState(
            session_id="test-session-001",
            last_sequence=5,
            last_event_hash="abc123",
            is_closed=False,
        )
        
        # Try to submit at seq 5 (already exists)
        event = make_valid_event(seq=5)
        claim = validate_claim(event)
        
        with pytest.raises(IngestException) as exc_info:
            seal_event(claim, chain_state=chain_state, strict_mode=True)
        
        assert exc_info.value.error.error_code == IngestErrorCode.SEQUENCE_REWIND
