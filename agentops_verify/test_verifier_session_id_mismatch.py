"""
agentops_verify/test_verifier_session_id_mismatch.py - Session ID Mismatch Coverage

Test to cover line 104 in verifier.py (session_id consistency check).
"""
import hashlib
import pytest
from typing import List, Dict, Any

from .verifier import verify_session
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


def test_session_id_mismatch_detected():
    """Test that session_id mismatch is detected (covers line 104)."""
    events = make_sealed_chain(3, session_id="session-A")
    
    # Change session_id in middle event
    events[1]["session_id"] = "session-B"
    
    report = verify_session(events)
    
    assert report.status == VerificationStatus.FAIL
    chain_findings = [f for f in report.findings if f.finding_type == FindingType.CHAIN_BREAK]
    session_findings = [f for f in chain_findings if "Session ID mismatch" in f.message]
    assert len(session_findings) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
