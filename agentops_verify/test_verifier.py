"""
agentops_verify/test_verifier.py - Verifier Test Vectors

Tests:
- Valid chain passes
- Tampered payload detected
- Chain break detected
- Unknown authority detected
- LOG_DROP causes DEGRADED
- Redaction detected
"""
import json
import hashlib
import pytest
from typing import List, Dict, Any

from .verifier import verify_session, TRUSTED_AUTHORITIES
from .errors import VerificationStatus, FindingType

# Import JCS from SDK
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from agentops_sdk import jcs


def make_sealed_chain(count: int = 3, session_id: str = "test-session") -> List[Dict[str, Any]]:
    """Create a valid sealed event chain for testing."""
    events = []
    prev_hash = None
    
    for i in range(count):
        payload = {"action": f"step_{i}", "data": i}
        payload_jcs = jcs.canonicalize(payload)
        payload_hash = hashlib.sha256(payload_jcs).hexdigest()
        
        signed_obj = {
            "event_id": f"evt-{i:03d}",
            "session_id": session_id,
            "sequence_number": i,
            "timestamp_wall": f"2023-10-01T12:{i:02d}:00Z",
            "event_type": "AGENT_DECISION",
            "payload_hash": payload_hash,
            "prev_event_hash": prev_hash,
        }
        
        canonical_env = jcs.canonicalize(signed_obj)
        event_hash = hashlib.sha256(canonical_env).hexdigest()
        
        event = {
            **signed_obj,
            "event_hash": event_hash,
            "chain_authority": "agentops-ingest-v1",
            "payload": payload,
        }
        
        events.append(event)
        prev_hash = event_hash
    
    return events


class TestValidChain:
    
    def test_valid_chain_passes(self):
        """Valid chain should produce PASS status."""
        events = make_sealed_chain(5)
        report = verify_session(events)
        
        assert report.status == VerificationStatus.PASS
        assert report.event_count == 5
        assert report.exit_code == 0
    
    def test_empty_session_fails(self):
        """Empty session should produce FAIL status."""
        report = verify_session([])
        
        assert report.status == VerificationStatus.FAIL
        assert report.exit_code == 2


class TestChainIntegrity:
    
    def test_tampered_payload_detected(self):
        """Tampered payload should be detected."""
        events = make_sealed_chain(3)
        
        # Tamper with middle event's payload
        events[1]["payload"]["data"] = "TAMPERED"
        
        report = verify_session(events)
        
        assert report.status == VerificationStatus.FAIL
        fatal_findings = [f for f in report.findings if f.finding_type == FindingType.PAYLOAD_TAMPER]
        assert len(fatal_findings) >= 1
    
    def test_chain_break_detected(self):
        """Chain break (wrong prev_hash) should be detected."""
        events = make_sealed_chain(3)
        
        # Break chain by modifying prev_event_hash
        events[2]["prev_event_hash"] = "0" * 64
        
        report = verify_session(events)
        
        assert report.status == VerificationStatus.FAIL
        chain_findings = [f for f in report.findings if f.finding_type == FindingType.CHAIN_BREAK]
        assert len(chain_findings) >= 1
    
    def test_hash_mismatch_detected(self):
        """Wrong event_hash should be detected."""
        events = make_sealed_chain(3)
        
        # Corrupt event hash
        events[1]["event_hash"] = "badhash" + "0" * 57
        
        report = verify_session(events)
        
        assert report.status == VerificationStatus.FAIL
        hash_findings = [f for f in report.findings if f.finding_type == FindingType.HASH_MISMATCH]
        assert len(hash_findings) >= 1
    
    def test_sequence_violation_detected(self):
        """Out-of-order sequence should be detected."""
        events = make_sealed_chain(3)
        
        # Swap sequence numbers
        events[1]["sequence_number"] = 5
        
        report = verify_session(events)
        
        assert report.status == VerificationStatus.FAIL
        seq_findings = [f for f in report.findings if f.finding_type == FindingType.SEQUENCE_VIOLATION]
        assert len(seq_findings) >= 1


class TestAuthority:
    
    def test_unknown_authority_rejected(self):
        """Unknown authority should cause FAIL."""
        events = make_sealed_chain(3)
        
        # Change authority to unknown
        events[0]["chain_authority"] = "evil-authority"
        
        report = verify_session(events)
        
        assert report.status == VerificationStatus.FAIL
        auth_findings = [f for f in report.findings if f.finding_type == FindingType.AUTHORITY_INVALID]
        assert len(auth_findings) >= 1
    
    def test_custom_trusted_authority_works(self):
        """Custom trusted authority should be accepted."""
        events = make_sealed_chain(3)
        
        # Use custom authority
        for e in events:
            e["chain_authority"] = "my-custom-ingest"
        
        # Verify with custom trusted set
        report = verify_session(events, trusted_authorities={"my-custom-ingest"})
        
        # Should pass (authority is trusted)
        # Note: hashes will be wrong because we changed authority after sealing
        # This test is about authority check specifically
        auth_findings = [f for f in report.findings if f.finding_type == FindingType.AUTHORITY_INVALID]
        assert len(auth_findings) == 0


class TestDegradedStatus:
    
    def test_log_drop_causes_degraded(self):
        """LOG_DROP event should cause DEGRADED status."""
        events = make_sealed_chain(2)
        
        # Add a LOG_DROP event
        drop_payload = {"dropped_events": 5, "reason": "buffer_overflow"}
        payload_jcs = jcs.canonicalize(drop_payload)
        payload_hash = hashlib.sha256(payload_jcs).hexdigest()
        
        signed_obj = {
            "event_id": "evt-002",
            "session_id": "test-session",
            "sequence_number": 2,
            "timestamp_wall": "2023-10-01T12:02:00Z",
            "event_type": "LOG_DROP",
            "payload_hash": payload_hash,
            "prev_event_hash": events[-1]["event_hash"],
        }
        
        canonical_env = jcs.canonicalize(signed_obj)
        event_hash = hashlib.sha256(canonical_env).hexdigest()
        
        drop_event = {
            **signed_obj,
            "event_hash": event_hash,
            "chain_authority": "agentops-ingest-v1",
            "payload": drop_payload,
        }
        
        events.append(drop_event)
        
        report = verify_session(events)
        
        assert report.status == VerificationStatus.DEGRADED
        assert report.exit_code == 1
        drop_findings = [f for f in report.findings if f.finding_type == FindingType.LOG_DROP_DETECTED]
        assert len(drop_findings) == 1


# --- EVIDENCE CLASSIFICATION TESTS ---
class TestEvidenceClassification:
    """Tests for formal evidence classification (A/B/C)."""
    
    def test_valid_chain_is_class_a(self):
        """Valid chain with no issues should be Class A."""
        from .errors import EvidenceClass
        events = make_sealed_chain(5)
        report = verify_session(events)
        
        assert report.evidence_class == EvidenceClass.CLASS_A
        assert "Full chain" in report.evidence_class_rationale
    
    def test_log_drop_is_class_b(self):
        """Chain with LOG_DROP should be Class B."""
        from .errors import EvidenceClass
        events = make_sealed_chain(2)
        
        # Add LOG_DROP
        drop_payload = {"dropped_events": 3, "reason": "buffer_overflow"}
        payload_jcs = jcs.canonicalize(drop_payload)
        payload_hash = hashlib.sha256(payload_jcs).hexdigest()
        
        signed_obj = {
            "event_id": "evt-002",
            "session_id": "test-session",
            "sequence_number": 2,
            "timestamp_wall": "2023-10-01T12:02:00Z",
            "event_type": "LOG_DROP",
            "payload_hash": payload_hash,
            "prev_event_hash": events[-1]["event_hash"],
        }
        canonical_env = jcs.canonicalize(signed_obj)
        event_hash = hashlib.sha256(canonical_env).hexdigest()
        
        events.append({
            **signed_obj,
            "event_hash": event_hash,
            "chain_authority": "agentops-ingest-v1",
            "payload": drop_payload,
        })
        
        report = verify_session(events)
        
        assert report.evidence_class == EvidenceClass.CLASS_B
        assert "LOG_DROP" in report.evidence_class_rationale
    
    def test_integrity_failure_is_class_c(self):
        """Chain with integrity failure should be Class C."""
        from .errors import EvidenceClass
        events = make_sealed_chain(3)
        
        # Tamper with payload
        events[1]["payload"]["data"] = "TAMPERED"
        
        report = verify_session(events)
        
        assert report.evidence_class == EvidenceClass.CLASS_C
        assert "fatal" in report.evidence_class_rationale.lower()


class TestDeterminism:
    
    def test_verification_is_deterministic(self):
        """Same input should always produce same result."""
        events = make_sealed_chain(5)
        
        report1 = verify_session(events)
        report2 = verify_session(events)
        
        assert report1.status == report2.status
        assert report1.final_event_hash == report2.final_event_hash
        assert len(report1.findings) == len(report2.findings)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
