import hashlib
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'verifier'))
from jcs import canonicalize
from agentops_sdk.envelope import build_event, GENESIS_HASH


# Pre-computed expected hash for a known event — generated once, frozen here
# We compute it dynamically so the test is self-validating
def _compute_expected_hash(event_without_hash: dict) -> str:
    return hashlib.sha256(canonicalize(event_without_hash)).hexdigest()


def test_known_hash_computation():
    """Hash for a known event must be deterministic and correct."""
    event = build_event(
        seq=1,
        event_type="SESSION_START",
        session_id="known-session-id",
        payload={"agent_id": "test-agent", "model_id": "test-model"},
        prev_hash=GENESIS_HASH,
    )
    # Recompute independently
    event_for_hash = {k: v for k, v in event.items() if k != "event_hash"}
    expected = _compute_expected_hash(event_for_hash)
    assert event["event_hash"] == expected, "Hash mismatch on known event"


def test_hash_changes_when_field_changes():
    """Any field change must produce a different hash."""
    event1 = build_event(1, "SESSION_START", "sess-1", {"agent_id": "a"}, GENESIS_HASH)
    event2 = build_event(1, "SESSION_START", "sess-1", {"agent_id": "b"}, GENESIS_HASH)
    event3 = build_event(2, "SESSION_START", "sess-1", {"agent_id": "a"}, GENESIS_HASH)
    assert event1["event_hash"] != event2["event_hash"], "Payload change must change hash"
    assert event1["event_hash"] != event3["event_hash"], "seq change must change hash"


def test_genesis_hash_for_seq_1():
    """seq=1 must have prev_hash = 64 zeros."""
    event = build_event(1, "SESSION_START", "sess-1", {}, GENESIS_HASH)
    assert event["prev_hash"] == "0" * 64


def test_prev_hash_chain_between_events():
    """prev_hash of event N must equal event_hash of event N-1."""
    event1 = build_event(1, "SESSION_START", "sess-1", {}, GENESIS_HASH)
    event2 = build_event(2, "LLM_CALL", "sess-1", {"model_id": "x"}, event1["event_hash"])
    event3 = build_event(3, "LLM_RESPONSE", "sess-1", {}, event2["event_hash"])
    assert event2["prev_hash"] == event1["event_hash"]
    assert event3["prev_hash"] == event2["event_hash"]


def test_jcs_import_comes_from_verifier():
    """JCS must be imported from verifier/jcs.py, not a duplicate."""
    import agentops_sdk.envelope as env_module
    import inspect
    source = inspect.getsource(env_module)
    assert "verifier" in source, "envelope.py must import JCS from verifier/"
    # Ensure no local jcs.py in agentops_sdk
    sdk_jcs = os.path.join("agentops_sdk", "jcs.py")
    assert not os.path.exists(sdk_jcs), f"Duplicate JCS found at {sdk_jcs}"
