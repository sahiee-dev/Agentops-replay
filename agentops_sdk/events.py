"""
agentops_sdk/events.py - Strict Event Definitions from Spec v0.5
"""
from enum import Enum
from typing import Dict, Any, Optional

SCHEMA_VER = "v0.5"

class EventType(str, Enum):
    SESSION_START = "SESSION_START"
    SESSION_END = "SESSION_END"
    MODEL_REQUEST = "MODEL_REQUEST"
    MODEL_RESPONSE = "MODEL_RESPONSE"
    TOOL_CALL = "TOOL_CALL"
    TOOL_RESULT = "TOOL_RESULT"
    AGENT_STATE_SNAPSHOT = "AGENT_STATE_SNAPSHOT"
    DECISION_TRACE = "DECISION_TRACE"
    ERROR = "ERROR"
    ANNOTATION = "ANNOTATION"
    CHAIN_SEAL = "CHAIN_SEAL"
    LOG_DROP = "LOG_DROP"
    AGENT_DECISION = "AGENT_DECISION"

# Strict Schema Validation Helpers (Scaffold for now to enforce types)
REQUIRED_FIELDS = {
    EventType.SESSION_START: ["agent_id", "environment", "framework", "framework_version", "sdk_version"],
    EventType.SESSION_END: ["status", "duration_ms"],
    EventType.LOG_DROP: ["dropped_count", "cumulative_drops", "drop_reason"],
    EventType.CHAIN_SEAL: ["final_event_hash"], 
}

def validate_payload(event_type: EventType, payload: Dict[str, Any]):
    """Strictly checks for required fields. Raises ValueError on failure."""
    req = REQUIRED_FIELDS.get(event_type)
    if req:
        missing = [f for f in req if f not in payload]
        if missing:
            raise ValueError(f"Event {event_type} missing required fields: {missing}")
