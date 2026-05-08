import subprocess
import sys
import os
import json
import tempfile
import pytest

VERIFIER = os.path.join("verifier", "agentops_verify.py")
VECTORS = os.path.join("verifier", "test_vectors")


def run_verifier(path: str, fmt: str = "text"):
    result = subprocess.run(
        [sys.executable, VERIFIER, path, "--format", fmt],
        capture_output=True, text=True
    )
    return result


def test_valid_session_passes():
    r = run_verifier(os.path.join(VECTORS, "valid_session.jsonl"), "json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["result"] == "PASS"
    assert data["evidence_class"] == "NON_AUTHORITATIVE_EVIDENCE"


def test_tampered_hash_fails():
    r = run_verifier(os.path.join(VECTORS, "tampered_hash.jsonl"), "json")
    assert r.returncode == 1
    data = json.loads(r.stdout)
    assert data["result"] == "FAIL"
    assert data["checks"]["hash_chain_integrity"]["status"] == "FAIL"


def test_sequence_gap_fails():
    r = run_verifier(os.path.join(VECTORS, "sequence_gap.jsonl"), "json")
    assert r.returncode == 1
    data = json.loads(r.stdout)
    assert data["result"] == "FAIL"
    assert data["checks"]["sequence_integrity"]["status"] == "FAIL"


def test_exit_code_2_on_missing_file():
    r = run_verifier("/nonexistent_file_xyz_abc.jsonl")
    assert r.returncode == 2, f"Expected exit 2, got {r.returncode}"


def test_authoritative_evidence_with_chain_seal():
    """A session with CHAIN_SEAL and no LOG_DROP → AUTHORITATIVE_EVIDENCE"""
    from agentops_sdk.envelope import build_event, GENESIS_HASH

    events = []
    prev = GENESIS_HASH
    session_id = "auth-test-session"

    for seq, etype, payload in [
        (1, "SESSION_START", {"agent_id": "test"}),
        (2, "LLM_CALL", {"model_id": "test"}),
        (3, "SESSION_END", {"status": "success"}),
    ]:
        e = build_event(seq, etype, session_id, payload, prev)
        events.append(e)
        prev = e["event_hash"]

    # Add CHAIN_SEAL as server event
    seal = build_event(4, "CHAIN_SEAL", session_id,
                       {"final_hash": prev, "authority": "ingestion_service",
                        "event_count": 4, "server_timestamp": "2026-01-01T00:00:00.000000Z",
                        "server_version": "1.0.0"}, prev)
    events.append(seal)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
        tmp = f.name

    try:
        r = run_verifier(tmp, "json")
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["evidence_class"] == "AUTHORITATIVE_EVIDENCE"
    finally:
        os.unlink(tmp)


def test_partial_authoritative_with_log_drop():
    """CHAIN_SEAL + LOG_DROP → PARTIAL_AUTHORITATIVE_EVIDENCE"""
    from agentops_sdk.envelope import build_event, GENESIS_HASH

    events = []
    prev = GENESIS_HASH
    session_id = "partial-test-session"

    specs = [
        (1, "SESSION_START", {"agent_id": "test"}),
        (2, "LOG_DROP", {"count": 3, "reason": "buffer_overflow",
                         "seq_range_start": 2, "seq_range_end": 4}),
        (3, "SESSION_END", {"status": "success"}),
    ]
    for seq, etype, payload in specs:
        e = build_event(seq, etype, session_id, payload, prev)
        events.append(e)
        prev = e["event_hash"]

    seal = build_event(4, "CHAIN_SEAL", session_id,
                       {"final_hash": prev, "authority": "ingestion_service",
                        "event_count": 4, "server_timestamp": "2026-01-01T00:00:00.000000Z",
                        "server_version": "1.0.0"}, prev)
    events.append(seal)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
        tmp = f.name

    try:
        r = run_verifier(tmp, "json")
        data = json.loads(r.stdout)
        assert data["evidence_class"] == "PARTIAL_AUTHORITATIVE_EVIDENCE"
    finally:
        os.unlink(tmp)


def test_missing_session_start_fails():
    """Session without SESSION_START → FAIL (session_completeness)."""
    from agentops_sdk.envelope import build_event, GENESIS_HASH

    events = []
    prev = GENESIS_HASH
    session_id = "no-start-test"

    # Skip SESSION_START — go directly to LLM_CALL and SESSION_END
    for seq, etype, payload in [
        (1, "LLM_CALL", {"model_id": "test"}),
        (2, "SESSION_END", {"status": "success"}),
    ]:
        e = build_event(seq, etype, session_id, payload, prev)
        events.append(e)
        prev = e["event_hash"]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
        tmp = f.name

    try:
        r = run_verifier(tmp, "json")
        assert r.returncode == 1, f"Expected exit 1, got {r.returncode}"
        data = json.loads(r.stdout)
        assert data["result"] == "FAIL"
        assert data["checks"]["session_completeness"]["status"] == "FAIL"
        assert data["checks"]["session_completeness"]["has_session_start"] is False
    finally:
        os.unlink(tmp)
