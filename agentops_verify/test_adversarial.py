import pytest
from agentops_verify.verifier import verify_session, VerificationStatus
from agentops_verify.errors import FindingType

# HARCODED VECTORS TO BYPASS I/O RESTRICTIONS
VECTOR_GAP = [
    {"event_id": "evt_0", "session_id": "sess_bad_gap", "sequence_number": 0, "timestamp_wall": "2026-01-01T12:00:00Z", "event_type": "SESSION_START", "chain_authority": "server", "prev_event_hash": None, "payload_hash": "sha256:dummy", "event_hash": "sha256:valid_hash_0"},
    {"event_id": "evt_1", "session_id": "sess_bad_gap", "sequence_number": 1, "timestamp_wall": "2026-01-01T12:00:01Z", "event_type": "MODEL_REQUEST", "chain_authority": "server", "prev_event_hash": "sha256:valid_hash_0", "payload_hash": "sha256:dummy", "event_hash": "sha256:valid_hash_1"},
    {"event_id": "evt_3", "session_id": "sess_bad_gap", "sequence_number": 3, "timestamp_wall": "2026-01-01T12:00:03Z", "event_type": "MODEL_RESPONSE", "chain_authority": "server", "prev_event_hash": "sha256:valid_hash_1", "payload_hash": "sha256:dummy", "event_hash": "sha256:valid_hash_3_skip"}
]

VECTOR_DUP = [
    {"event_id": "evt_0", "session_id": "sess_bad_dup", "sequence_number": 0, "timestamp_wall": "2026-01-01T12:00:00Z", "event_type": "SESSION_START", "chain_authority": "server", "prev_event_hash": None, "payload_hash": "sha256:dummy", "event_hash": "sha256:valid_hash_0"},
    {"event_id": "evt_1", "session_id": "sess_bad_dup", "sequence_number": 1, "timestamp_wall": "2026-01-01T12:00:01Z", "event_type": "MODEL_REQUEST", "chain_authority": "server", "prev_event_hash": "sha256:valid_hash_0", "payload_hash": "sha256:dummy", "event_hash": "sha256:valid_hash_1"},
    {"event_id": "evt_2a", "session_id": "sess_bad_dup", "sequence_number": 2, "timestamp_wall": "2026-01-01T12:00:02Z", "event_type": "TOOL_CALL", "chain_authority": "server", "prev_event_hash": "sha256:valid_hash_1", "payload_hash": "sha256:dummy", "event_hash": "sha256:valid_hash_2a"},
    {"event_id": "evt_2b", "session_id": "sess_bad_dup", "sequence_number": 2, "timestamp_wall": "2026-01-01T12:00:02Z", "event_type": "TOOL_CALL", "chain_authority": "server", "prev_event_hash": "sha256:valid_hash_1", "payload_hash": "sha256:dummy", "event_hash": "sha256:valid_hash_2b"},
    {"event_id": "evt_3", "session_id": "sess_bad_dup", "sequence_number": 3, "timestamp_wall": "2026-01-01T12:00:03Z", "event_type": "TOOL_RESULT", "chain_authority": "server", "prev_event_hash": "sha256:valid_hash_2b", "payload_hash": "sha256:dummy", "event_hash": "sha256:valid_hash_3"}
]

VECTOR_REDACT = [
    {"event_id": "evt_0", "session_id": "sess_bad_redact", "sequence_number": 0, "timestamp_wall": "2026-01-01T12:00:00Z", "event_type": "SESSION_START", "chain_authority": "server", "prev_event_hash": None, "payload_hash": "sha256:dummy", "event_hash": "sha256:valid_hash_0", "payload": {"user_email": "[REDACTED]"}},
    {"event_id": "evt_1", "session_id": "sess_bad_redact", "sequence_number": 1, "timestamp_wall": "2026-01-01T12:00:01Z", "event_type": "SESSION_END", "chain_authority": "server", "prev_event_hash": "sha256:valid_hash_0", "payload_hash": "sha256:dummy", "event_hash": "sha256:valid_hash_1"}
]

def test_adversarial_gap():
    """Start=0, but 1->3 gap. Must fail with SEQUENCE_VIOLATION."""
    events = VECTOR_GAP
    report = verify_session(events, allow_redacted=False)
    
    assert report.status == VerificationStatus.FAIL, "Gap must be fatal"
    seq_findings = [f for f in report.findings if f.finding_type == FindingType.SEQUENCE_VIOLATION]
    assert len(seq_findings) > 0, f"Expected SEQUENCE_VIOLATION check, got {[f.finding_type for f in report.findings]}"

def test_adversarial_duplicate():
    """
    Verify that a session containing a duplicated sequence number fails verification due to a sequence violation.
    
    Uses VECTOR_DUP with allow_redacted=False and asserts the verification report status is VerificationStatus.FAIL and that at least one finding has FindingType.SEQUENCE_VIOLATION.
    """
    events = VECTOR_DUP
    report = verify_session(events, allow_redacted=False)
    
    assert report.status == VerificationStatus.FAIL, "Duplicate must be fatal"
    seq_findings = [f for f in report.findings if f.finding_type == FindingType.SEQUENCE_VIOLATION]
    assert len(seq_findings) > 0, f"Expected SEQUENCE_VIOLATION check, got {[f.finding_type for f in report.findings]}"

def test_adversarial_redaction_integrity():
    """
    Verify that a session containing redacted event content without corresponding integrity hashes fails verification with a REDACTION_INTEGRITY_VIOLATION.
    
    Calls verify_session with allow_redacted=True and asserts the report status is VerificationStatus.FAIL and that at least one finding has FindingType.REDACTION_INTEGRITY_VIOLATION.
    """
    events = VECTOR_REDACT
    report = verify_session(events, allow_redacted=True)
    
    assert report.status == VerificationStatus.FAIL, "Structural redaction failure must be fatal"
    
    # Strict check: Must find REDACTION_INTEGRITY_VIOLATION
    redact_findings = [f for f in report.findings if f.finding_type == FindingType.REDACTION_INTEGRITY_VIOLATION]
    assert len(redact_findings) > 0, f"Expected REDACTION_INTEGRITY_VIOLATION, got {[f.finding_type for f in report.findings]}"