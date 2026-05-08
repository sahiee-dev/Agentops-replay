import pytest
from agentops_sdk.events import EventType


def test_sdk_authority_types():
    sdk_types = [
        EventType.SESSION_START, EventType.SESSION_END,
        EventType.LLM_CALL, EventType.LLM_RESPONSE,
        EventType.TOOL_CALL, EventType.TOOL_RESULT,
        EventType.TOOL_ERROR, EventType.LOG_DROP,
    ]
    for et in sdk_types:
        assert et.is_sdk_authority == True, f"{et} should be SDK authority"
        assert et.is_server_authority == False, f"{et} should not be server authority"


def test_server_authority_types():
    server_types = [
        EventType.CHAIN_SEAL, EventType.CHAIN_BROKEN,
        EventType.REDACTION, EventType.FORENSIC_FREEZE,
    ]
    for et in server_types:
        assert et.is_server_authority == True, f"{et} should be server authority"
        assert et.is_sdk_authority == False, f"{et} should not be SDK authority"


def test_event_type_count():
    all_types = list(EventType)
    assert len(all_types) == 12, f"Expected 12 EventTypes, got {len(all_types)}"


def test_server_authority_types_rejected_by_sdk():
    from agentops_sdk.client import AgentOpsClient
    client = AgentOpsClient(local_authority=True)
    client.start_session(agent_id="test")
    client.record(EventType.CHAIN_SEAL, {"final_hash": "abc"})
    client.end_session()
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = f.name
    client.flush_to_jsonl(path)
    lines = open(path).readlines()
    import json
    events = [json.loads(l) for l in lines]
    types = [e["event_type"] for e in events]
    assert "CHAIN_SEAL" not in types, "SDK must never produce CHAIN_SEAL"
    assert "LOG_DROP" in types, "Rejected server-authority event must become LOG_DROP"
    os.unlink(path)


def test_event_type_string_literals():
    """EventType values must be the correct string literals."""
    expected = {
        "SESSION_START": EventType.SESSION_START,
        "SESSION_END": EventType.SESSION_END,
        "LLM_CALL": EventType.LLM_CALL,
        "LLM_RESPONSE": EventType.LLM_RESPONSE,
        "TOOL_CALL": EventType.TOOL_CALL,
        "TOOL_RESULT": EventType.TOOL_RESULT,
        "TOOL_ERROR": EventType.TOOL_ERROR,
        "LOG_DROP": EventType.LOG_DROP,
        "CHAIN_SEAL": EventType.CHAIN_SEAL,
        "CHAIN_BROKEN": EventType.CHAIN_BROKEN,
        "REDACTION": EventType.REDACTION,
        "FORENSIC_FREEZE": EventType.FORENSIC_FREEZE,
    }
    for literal, enum_val in expected.items():
        assert enum_val.value == literal, f"{enum_val} should have value '{literal}', got '{enum_val.value}'"
        assert enum_val == literal, f"{enum_val} should equal string '{literal}'"
