"""
agentops_verify/test_verifier_coverage.py - Coverage Gap Tests

Tests specifically targeting uncovered branches in verifier.py:
- JCS canonicalization exceptions (lines 159-160, 195-196)
- NameError fallback path (lines 245-250)
- Redaction policy violation (line 221)
- List/string redaction checks (lines 306-308, 310-312)
- JSONL file parsing (lines 323-332)
"""
import json
import hashlib
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import List, Dict, Any

from .verifier import verify_session, verify_file, _check_redaction_integrity
from .errors import VerificationStatus, FindingType, FindingSeverity, Finding

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


class TestJCSCanonicalizationExceptions:
    """Test exception handling in JCS canonicalization paths."""
    
    def test_payload_canonicalization_exception(self):
        """Test that payload canonicalization exceptions are caught and reported."""
        events = make_sealed_chain(1)
        
        # Create a payload that will cause JCS to fail
        # Use a mock to force an exception
        with patch('agentops_verify.verifier.jcs.canonicalize') as mock_jcs:
            mock_jcs.side_effect = Exception("JCS canonicalization failed")
            
            report = verify_session(events)
            
            assert report.status == VerificationStatus.FAIL
            tamper_findings = [f for f in report.findings if f.finding_type == FindingType.PAYLOAD_TAMPER]
            assert len(tamper_findings) >= 1
            assert "Cannot canonicalize payload" in tamper_findings[0].message
    
    def test_event_hash_canonicalization_exception(self):
        """Test that event hash canonicalization exceptions are caught and reported."""
        events = make_sealed_chain(1)
        
        # Mock JCS to fail on second call (event hash computation)
        with patch('agentops_verify.verifier.jcs.canonicalize') as mock_jcs:
            # First call succeeds (payload), second call fails (event hash)
            mock_jcs.side_effect = [
                jcs.canonicalize(events[0]["payload"]),  # payload succeeds
                Exception("Event hash JCS failed")  # event hash fails
            ]
            
            report = verify_session(events)
            
            assert report.status == VerificationStatus.FAIL
            hash_findings = [f for f in report.findings if f.finding_type == FindingType.HASH_MISMATCH]
            assert len(hash_findings) >= 1
            assert "Cannot compute event hash" in hash_findings[0].message


class TestNameErrorFallback:
    """Test the NameError fallback path (lines 245-250)."""
    
    def test_name_error_fallback_triggered(self):
        """Test that NameError fallback uses recorded hashes when computation fails."""
        events = make_sealed_chain(2)
        
        # This is a defensive path that should rarely trigger in practice
        # We can trigger it by mocking the hash computation to raise NameError
        with patch('agentops_verify.verifier.jcs.canonicalize') as mock_jcs:
            # Make canonicalize raise NameError to trigger the fallback
            def side_effect(obj):
                # Succeed for payload, fail with NameError for event hash
                if "event_id" in obj:
                    raise NameError("computed_event_hash not defined")
                return jcs.canonicalize(obj)
            
            mock_jcs.side_effect = side_effect
            
            report = verify_session(events)
            
            # Should still complete (using fallback), but with hash mismatch findings
            assert report.final_event_hash is not None
            # The fallback uses recorded hashes, so first_event_hash should be set
            assert report.first_event_hash is not None


class TestRedactionPolicyViolation:
    """Test redaction policy violation (line 221)."""
    
    def test_redaction_forbidden_when_disallowed(self):
        """Test that redacted content causes FAIL when allow_redacted=False."""
        events = make_sealed_chain(1)
        
        # Add redacted content to payload
        events[0]["payload"]["user_email"] = "[REDACTED]"
        events[0]["payload"]["user_email_hash"] = "abc123"
        
        # Recompute hashes to make chain valid
        payload_jcs = jcs.canonicalize(events[0]["payload"])
        payload_hash = hashlib.sha256(payload_jcs).hexdigest()
        events[0]["payload_hash"] = payload_hash
        
        signed_obj = {
            "event_id": events[0]["event_id"],
            "session_id": events[0]["session_id"],
            "sequence_number": events[0]["sequence_number"],
            "timestamp_wall": events[0]["timestamp_wall"],
            "event_type": events[0]["event_type"],
            "payload_hash": payload_hash,
            "prev_event_hash": events[0]["prev_event_hash"],
        }
        canonical_env = jcs.canonicalize(signed_obj)
        events[0]["event_hash"] = hashlib.sha256(canonical_env).hexdigest()
        
        # Verify with allow_redacted=False
        report = verify_session(events, allow_redacted=False)
        
        assert report.status == VerificationStatus.FAIL
        policy_findings = [f for f in report.findings if f.finding_type == FindingType.POLICY_VIOLATION]
        assert len(policy_findings) >= 1
        assert "Redacted content forbidden" in policy_findings[0].message


class TestRedactionIntegrityChecks:
    """Test list and string redaction checks (lines 306-312)."""
    
    def test_redaction_in_list(self):
        """Test redaction detection in list payloads."""
        findings = []
        
        # Test list with redacted string
        payload = {
            "items": ["normal", "[REDACTED]", "data"]
        }
        
        result = _check_redaction_integrity(payload, findings, 0, "evt-001")
        
        assert result is True  # Redaction found
    
    def test_redaction_in_nested_string(self):
        """Test redaction detection in standalone strings."""
        findings = []
        
        # Test direct string with redaction marker
        result = _check_redaction_integrity("[REDACTED]", findings, 0, "evt-001")
        
        assert result is True
    
    def test_redaction_with_asterisks(self):
        """Test redaction detection using *** marker."""
        findings = []
        
        payload = {
            "password": "***"
        }
        
        result = _check_redaction_integrity(payload, findings, 0, "evt-001")
        
        assert result is True
    
    def test_redaction_missing_hash_in_list_item(self):
        """Test that redaction in list without sibling hash triggers violation."""
        findings = []
        
        # Redacted content in dict inside list, missing hash
        payload = {
            "users": [
                {"name": "Alice"},
                {"email": "[REDACTED]"}  # Missing email_hash
            ]
        }
        
        result = _check_redaction_integrity(payload, findings, 0, "evt-001")
        
        assert result is True
        # Should have a REDACTION_INTEGRITY_VIOLATION finding
        violations = [f for f in findings if f.finding_type == FindingType.REDACTION_INTEGRITY_VIOLATION]
        assert len(violations) >= 1


class TestJSONLFileParsing:
    """Test JSONL file parsing (lines 323-332)."""
    
    def test_verify_file_with_jsonl(self):
        """Test that verify_file correctly parses .jsonl files."""
        events = make_sealed_chain(3)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for event in events:
                f.write(json.dumps(event) + '\n')
            temp_path = f.name
        
        try:
            report = verify_file(temp_path)
            
            assert report.status == VerificationStatus.PASS
            assert report.event_count == 3
        finally:
            Path(temp_path).unlink()
    
    def test_verify_file_with_json(self):
        """Test that verify_file correctly parses .json files."""
        events = make_sealed_chain(2)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(events, f)
            temp_path = f.name
        
        try:
            report = verify_file(temp_path)
            
            assert report.status == VerificationStatus.PASS
            assert report.event_count == 2
        finally:
            Path(temp_path).unlink()
    
    def test_verify_file_jsonl_with_empty_lines(self):
        """Test that JSONL parsing skips empty lines."""
        events = make_sealed_chain(2)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write(json.dumps(events[0]) + '\n')
            f.write('\n')  # Empty line
            f.write(json.dumps(events[1]) + '\n')
            f.write('  \n')  # Whitespace-only line
            temp_path = f.name
        
        try:
            report = verify_file(temp_path)
            
            assert report.event_count == 2
        finally:
            Path(temp_path).unlink()


class TestErrorsModuleCoverage:
    """Test uncovered paths in errors.py."""
    
    def test_finding_without_optional_fields(self):
        """Test Finding creation without optional fields."""
        from .errors import Finding, FindingType, FindingSeverity
        
        finding = Finding(
            finding_type=FindingType.CHAIN_BREAK,
            severity=FindingSeverity.FATAL,
            message="Test finding"
        )
        
        assert finding.sequence_number is None
        assert finding.event_id is None
        assert finding.details is None
    
    def test_verification_report_to_dict(self):
        """Test VerificationReport.to_dict() method."""
        from .errors import VerificationReport, VerificationStatus, EvidenceClass
        
        report = VerificationReport(
            session_id="test-123",
            status=VerificationStatus.PASS,
            event_count=5,
            first_event_hash="abc",
            final_event_hash="def",
            chain_authority="agentops-ingest-v1",
            verification_mode="FULL",
            findings=[]
        )
        
        report_dict = report.to_dict()
        
        assert report_dict["session_id"] == "test-123"
        assert report_dict["status"] == "PASS"
        assert report_dict["evidence_class"] == "A"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
