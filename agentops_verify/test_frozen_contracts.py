"""
agentops_verify/test_frozen_contracts.py - Regression Guard for Frozen Verifier

This file enforces the VERIFIER FREEZE.
It tests against the constitutional artifact `verifier/test_vectors/valid_session.jsonl`.

RULES:
1. This test MUST pass.
2. The expected hash values defined here MUST NOT change.
3. If this test fails, you have broken the verifier freeze.
"""
import pytest
import json
from pathlib import Path
from .verifier import verify_session, VerificationStatus

# CONSTANTS - THESE ARE IMMUTABLE
# Derived from `verifier/test_vectors/valid_session.jsonl`
FROZEN_SESSION_ID = "0f076f86-63df-44ea-9eeb-11ffd6a808be"
FROZEN_FIRST_HASH = "6b7f7fa9ba8c7f921c0a24c801ecb62a05a3fafb8f7cd1119e13c47684673f24"
FROZEN_FINAL_HASH = "32a410de908b0fd9f8465f8df7761890541b27673b4adefe8c7e802a6817245f"
FROZEN_EVENT_COUNT = 4

def test_frozen_contract_valid_session():
    """
    Validates that the verifier's behavior on the constitutional test vector
    has not changed.
    """
    # Locate the frozen vector
    vector_path = Path("verifier/test_vectors/valid_session.jsonl")
    if not vector_path.exists():
        pytest.fail(f"Constitutional artifact missing: {vector_path}")

    # Parse JSONL manually to respect VERIFIER FREEZE (verifier.py only supports JSON array)
    events = []
    with open(vector_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    # Run verification (using default trusted authorities, which must include 'server')
    # Since verifier.py doesn't trust 'server' by default (strict mode), we inject it here
    # to validate the constitutional vector which uses 'server'.
    report = verify_session(events, trusted_authorities={"server"})

    # Assert START - failure here means FREEZE VIOLATION
    
    # 1. Status must be PASS
    assert report.status == VerificationStatus.PASS, \
        f"Frozen vector failed verification. Findings: {report.findings}"

    # 2. Session ID must match
    assert report.session_id == FROZEN_SESSION_ID, \
        f"Session ID changed. Expected {FROZEN_SESSION_ID}, got {report.session_id}"

    # 3. First Event Hash (Genesis) must match exactly
    assert report.first_event_hash == FROZEN_FIRST_HASH, \
        f"Genesis hash changed! Logic alteration detected. Expected {FROZEN_FIRST_HASH}, got {report.first_event_hash}"

    # 4. Final Event Hash (Tip) must match exactly
    assert report.final_event_hash == FROZEN_FINAL_HASH, \
        f"Final hash changed! Logic alteration detected. Expected {FROZEN_FINAL_HASH}, got {report.final_event_hash}"

    # 5. Event Count must match
    assert report.event_count == FROZEN_EVENT_COUNT, \
        f"Event count mismatch. Expected {FROZEN_EVENT_COUNT}, got {report.event_count}"

    # Assert END

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
