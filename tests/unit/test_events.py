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
