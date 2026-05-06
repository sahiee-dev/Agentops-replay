from enum import Enum


class EventType(str, Enum):
    # SDK-authority events (SDK may produce these)
    SESSION_START = "SESSION_START"
    SESSION_END = "SESSION_END"
    LLM_CALL = "LLM_CALL"
    LLM_RESPONSE = "LLM_RESPONSE"
    TOOL_CALL = "TOOL_CALL"
    TOOL_RESULT = "TOOL_RESULT"
    TOOL_ERROR = "TOOL_ERROR"
    LOG_DROP = "LOG_DROP"

    # Server-authority events (SDK must NEVER produce these)
    CHAIN_SEAL = "CHAIN_SEAL"
    CHAIN_BROKEN = "CHAIN_BROKEN"
    REDACTION = "REDACTION"
    FORENSIC_FREEZE = "FORENSIC_FREEZE"

    @property
    def is_sdk_authority(self) -> bool:
        return self in {
            EventType.SESSION_START,
            EventType.SESSION_END,
            EventType.LLM_CALL,
            EventType.LLM_RESPONSE,
            EventType.TOOL_CALL,
            EventType.TOOL_RESULT,
            EventType.TOOL_ERROR,
            EventType.LOG_DROP,
        }

    @property
    def is_server_authority(self) -> bool:
        return not self.is_sdk_authority
