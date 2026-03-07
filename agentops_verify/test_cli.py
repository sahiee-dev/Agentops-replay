"""
agentops_verify/test_cli.py - CLI Coverage Tests

Tests for cli.py to ensure argument parsing and output formatting work correctly.
"""
import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch
import sys

from .cli import main, run_verify
from .errors import VerificationStatus

# Import JCS from SDK
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from agentops_sdk import jcs
import hashlib


def make_sealed_chain_for_cli(count: int = 3, session_id: str = "test-session"):
    """Create a valid sealed event chain for CLI testing."""
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


class TestCLIBasicVerify:
    """Test basic CLI verification flow."""
    
    def test_cli_verify_valid_session(self, capsys):
        """Test CLI with valid session file."""
        events = make_sealed_chain_for_cli(3)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for event in events:
                f.write(json.dumps(event) + '\n')
            temp_path = f.name
        
        try:
            with patch('sys.argv', ['agentops-verify', 'verify', temp_path]):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                assert exc_info.value.code == 0  # PASS
                
                captured = capsys.readouterr()
                assert "VERIFICATION RESULT: PASS" in captured.out
                assert "EVIDENCE CLASS: A" in captured.out
        finally:
            Path(temp_path).unlink()
    
    def test_cli_verify_with_output_file(self):
        """Test CLI with --output flag."""
        events = make_sealed_chain_for_cli(2)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for event in events:
                f.write(json.dumps(event) + '\n')
            temp_path = f.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as out_f:
            output_path = out_f.name
        
        try:
            with patch('sys.argv', ['agentops-verify', 'verify', temp_path, '--output', output_path]):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                assert exc_info.value.code == 0
                
                # Verify output file was created
                with open(output_path, 'r') as f:
                    report_data = json.load(f)
                    assert report_data["status"] == "PASS"
        finally:
            Path(temp_path).unlink()
            Path(output_path).unlink()
    
    def test_cli_verify_quiet_mode(self, capsys):
        """Test CLI with --quiet flag."""
        events = make_sealed_chain_for_cli(2)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for event in events:
                f.write(json.dumps(event) + '\n')
            temp_path = f.name
        
        try:
            with patch('sys.argv', ['agentops-verify', 'verify', temp_path, '--quiet']):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                assert exc_info.value.code == 0
                
                captured = capsys.readouterr()
                # In quiet mode, should have minimal output
                assert "VERIFICATION RESULT" not in captured.out
        finally:
            Path(temp_path).unlink()
    
    def test_cli_file_not_found(self, capsys):
        """Test CLI with non-existent file."""
        with patch('sys.argv', ['agentops-verify', 'verify', '/nonexistent/file.jsonl']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            assert exc_info.value.code == 2  # FAIL
            
            captured = capsys.readouterr()
            assert "File not found" in captured.err
    
    def test_cli_custom_authorities(self, capsys):
        """Test CLI with custom --authorities flag."""
        events = make_sealed_chain_for_cli(2)
        
        # Change authority to custom value
        for event in events:
            event["chain_authority"] = "my-custom-authority"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for event in events:
                f.write(json.dumps(event) + '\n')
            temp_path = f.name
        
        try:
            with patch('sys.argv', ['agentops-verify', 'verify', temp_path, '--authorities', 'my-custom-authority']):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                # Should fail due to hash mismatches (we changed authority after sealing)
                # but authority check should pass
                captured = capsys.readouterr()
                assert "AUTHORITY_INVALID" not in captured.out
        finally:
            Path(temp_path).unlink()


class TestCLIFailureCases:
    """Test CLI failure scenarios."""
    
    def test_cli_verify_tampered_session(self, capsys):
        """Test CLI with tampered session."""
        events = make_sealed_chain_for_cli(3)
        
        # Tamper with payload
        events[1]["payload"]["data"] = "TAMPERED"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for event in events:
                f.write(json.dumps(event) + '\n')
            temp_path = f.name
        
        try:
            with patch('sys.argv', ['agentops-verify', 'verify', temp_path]):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                assert exc_info.value.code == 2  # FAIL
                
                captured = capsys.readouterr()
                assert "VERIFICATION RESULT: FAIL" in captured.out
                assert "PAYLOAD_TAMPER" in captured.out
        finally:
            Path(temp_path).unlink()
    
    def test_cli_verification_exception(self, capsys):
        """Test CLI handling of verification exceptions."""
        # Create a malformed file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write("not valid json\n")
            temp_path = f.name
        
        try:
            with patch('sys.argv', ['agentops-verify', 'verify', temp_path]):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                assert exc_info.value.code == 2
                
                captured = capsys.readouterr()
                assert "Verification failed" in captured.err
        finally:
            Path(temp_path).unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
