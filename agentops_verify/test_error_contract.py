import pytest
import json
from agentops_verify.verifier import verify_session, VerificationStatus
from agentops_verify.errors import FindingType, EvidenceClass

# Reuse existing vector logic (hardcoded here to be self-contained/robust)
VECTOR_GAP = [
    {"event_id": "evt_0", "session_id": "sess_bad_gap", "sequence_number": 0, "timestamp_wall": "2026-01-01T12:00:00Z", "event_type": "SESSION_START", "chain_authority": "server", "prev_event_hash": None, "payload_hash": "sha256:dummy", "event_hash": "sha256:valid_hash_0"},
    {"event_id": "evt_1", "session_id": "sess_bad_gap", "sequence_number": 1, "timestamp_wall": "2026-01-01T12:00:01Z", "event_type": "MODEL_REQUEST", "chain_authority": "server", "prev_event_hash": "sha256:valid_hash_0", "payload_hash": "sha256:dummy", "event_hash": "sha256:valid_hash_1"},
    {"event_id": "evt_3", "session_id": "sess_bad_gap", "sequence_number": 3, "timestamp_wall": "2026-01-01T12:00:03Z", "event_type": "MODEL_RESPONSE", "chain_authority": "server", "prev_event_hash": "sha256:valid_hash_1", "payload_hash": "sha256:dummy", "event_hash": "sha256:valid_hash_3_skip"}
]

def test_verifier_error_contract_sequence():
    """Contract: SEQUENCE_VIOLATION -> Exit Code 2 -> CLASS_C"""
    report = verify_session(VECTOR_GAP, allow_redacted=False)
    
    # Assert Contract
    assert report.status == VerificationStatus.FAIL
    assert report.exit_code == 2, "Exit code MUST be 2 for SEQUENCE_VIOLATION"
    assert report.evidence_class == EvidenceClass.CLASS_C, "Evidence class MUST be C for SEQUENCE_VIOLATION"
    
    # Assert specific error code
    findings = [f for f in report.findings if f.finding_type == FindingType.SEQUENCE_VIOLATION]
    assert len(findings) > 0

def test_verifier_error_contract_redaction_integrity():
    """Contract: REDACTION_INTEGRITY_VIOLATION -> Exit Code 2 -> CLASS_C"""
    # Use allow_redacted=True (Policy pass) to ensure Integrity Check drives the failure
    vector = [
        {"event_id": "evt_0", "session_id": "sess_bad", "sequence_number": 0, "timestamp_wall": "2026-01-01T12:00:00Z", "event_type": "TEST", "chain_authority": "server", "prev_event_hash": None, "payload_hash": "d", "event_hash": "d", "payload": {"k": "[REDACTED]"}}
    ]
    
    report = verify_session(vector, allow_redacted=True)
    
    # Assert Contract
    assert report.status == VerificationStatus.FAIL, "Must fail integrity check even if policy allowed"
    assert report.exit_code == 2, "Exit code MUST be 2 for REDACTION_INTEGRITY_VIOLATION"
    assert report.evidence_class == EvidenceClass.CLASS_C, "Evidence class MUST be C for REDACTION_INTEGRITY_VIOLATION"
    
    findings = [f for f in report.findings if f.finding_type == FindingType.REDACTION_INTEGRITY_VIOLATION]
    assert len(findings) > 0
