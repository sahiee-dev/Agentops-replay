# AgentOps Replay — Event Payload Schema

This document defines the exact payload schemas for the 12 canonical event types in AgentOps Replay. All implementations must adhere to these schemas to ensure interoperability and verifiability.

---

## SDK-Authority Events

### SESSION_START
Marks the beginning of a session.
```json
{
  "agent_id": "string (required)",
  "model_id": "string (optional)",
  "tags": "list of strings (optional)"
}
```

### SESSION_END
Marks the end of a session.
```json
{
  "status": "string (required, 'success' or 'error')"
}
```

### LLM_CALL
Records an invocation of an LLM.
```json
{
  "prompt_hash": "string (required, SHA-256 hex)",
  "model_id": "string (required)"
}
```

### LLM_RESPONSE
Records a completion from an LLM.
```json
{
  "content_hash": "string (required, SHA-256 hex)",
  "finish_reason": "string (required)"
}
```

### TOOL_CALL
Records a tool invocation.
```json
{
  "tool_name": "string (required)",
  "args_hash": "string (required, SHA-256 hex)"
}
```

### TOOL_RESULT
Records a tool output.
```json
{
  "tool_name": "string (required)",
  "result_hash": "string (required, SHA-256 hex)"
}
```

### TOOL_ERROR
Records a tool or LLM error.
```json
{
  "error_type": "string (required)",
  "error_message": "string (required, max 500 chars)"
}
```

### LOG_DROP
Records data loss.
```json
{
  "count": "integer (required)",
  "reason": "string (required, 'buffer_overflow' or 'internal_error')",
  "seq_range_start": "integer (required)",
  "seq_range_end": "integer (required)"
}
```

---

## Server-Authority Events

### CHAIN_SEAL
Records the authoritative closing of a valid chain.
```json
{
  "final_hash": "string (required, SHA-256 hex)",
  "authority": "string (required, 'server')",
  "event_count": "integer (required)",
  "server_timestamp": "string (required, ISO 8601)",
  "server_version": "string (required)"
}
```

### CHAIN_BROKEN
Records a detected sequence gap.
```json
{
  "gap_start": "integer (required)",
  "gap_end": "integer (required)"
}
```

### REDACTION
Records a payload modification for compliance.
```json
{
  "original_event_id": "string (required, UUID)",
  "redaction_reason": "string (required)"
}
```

### FORENSIC_FREEZE
Records an administrative integrity lock.
```json
{
  "freeze_id": "string (required, UUID)",
  "freeze_reason": "string (required)"
}
```

## Trust Model

The formal guarantee provided by each evidence class when verifying sessions conforming to this schema is documented in [docs/TRUST_MODEL.md](docs/TRUST_MODEL.md).
