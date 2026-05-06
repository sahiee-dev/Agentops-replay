"""
verifier/generator.py — Generates all test vectors deterministically.

TRD §3.7: Running this always produces the same files (given the same
Python version and JCS implementation).

Usage:
    python3 verifier/generator.py

Produces:
    verifier/test_vectors/valid_session.jsonl   — Expected: PASS
    verifier/test_vectors/tampered_hash.jsonl   — Expected: FAIL, hash mismatch at seq=5
    verifier/test_vectors/sequence_gap.jsonl    — Expected: FAIL, sequence gap at seq=4
"""

import json
import os
import sys

# Allow running from repo root or from verifier/ directory
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _repo_root)

from agentops_sdk.envelope import build_event, GENESIS_HASH

_OUT_DIR = os.path.join(os.path.dirname(__file__), "test_vectors")

SESSION_ID = "550e8400-e29b-41d4-a716-446655440000"


def _build_valid_session() -> list[dict]:
    """
    8-event session per TRD §3.7:
    seq=1 SESSION_START  seq=2 LLM_CALL      seq=3 LLM_RESPONSE
    seq=4 TOOL_CALL      seq=5 TOOL_RESULT   seq=6 LLM_CALL
    seq=7 LLM_RESPONSE   seq=8 SESSION_END
    """
    events = []
    prev_hash = GENESIS_HASH

    specs = [
        (1, "SESSION_START",  {"agent_id": "test-agent", "model_id": "test-model"}),
        (2, "LLM_CALL",       {"model_id": "test-model", "prompt": "Hello"}),
        (3, "LLM_RESPONSE",   {"model_id": "test-model", "content": "Hi there"}),
        (4, "TOOL_CALL",      {"tool_name": "calculator", "args": {"x": 1, "y": 2}}),
        (5, "TOOL_RESULT",    {"tool_name": "calculator", "result": 3}),
        (6, "LLM_CALL",       {"model_id": "test-model", "prompt": "What is 2+2?"}),
        (7, "LLM_RESPONSE",   {"model_id": "test-model", "content": "4"}),
        (8, "SESSION_END",    {"status": "success"}),
    ]

    for seq, event_type, payload in specs:
        event = build_event(
            seq=seq,
            event_type=event_type,
            session_id=SESSION_ID,
            payload=payload,
            prev_hash=prev_hash,
        )
        events.append(event)
        prev_hash = event["event_hash"]

    return events


def _build_tampered_hash() -> list[dict]:
    """
    Identical to valid_session but seq=5 (TOOL_RESULT) has
    its event_hash last character corrupted.
    """
    import copy
    events = copy.deepcopy(_build_valid_session())
    for event in events:
        if event["seq"] == 5:
            original = event["event_hash"]
            # Flip the last character: 0→1, anything-else→0
            last = original[-1]
            corrupted_last = "1" if last != "1" else "0"
            event["event_hash"] = original[:-1] + corrupted_last
            break
    return events


def _build_sequence_gap() -> list[dict]:
    """
    Identical to valid_session but seq=4 (TOOL_CALL) is removed,
    creating a gap from seq=3 to seq=5.
    """
    events = _build_valid_session()
    return [e for e in events if e["seq"] != 4]


def _write_jsonl(events: list[dict], filename: str) -> None:
    path = os.path.join(_OUT_DIR, filename)
    with open(path, "w") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")
    print(f"  wrote {path}  ({len(events)} events)")


if __name__ == "__main__":
    os.makedirs(_OUT_DIR, exist_ok=True)

    print("Generating test vectors...")
    _write_jsonl(_build_valid_session(),    "valid_session.jsonl")
    _write_jsonl(_build_tampered_hash(),    "tampered_hash.jsonl")
    _write_jsonl(_build_sequence_gap(),     "sequence_gap.jsonl")
    print("Done.")
