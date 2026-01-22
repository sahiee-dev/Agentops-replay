# SCHEMA.md (v0.2)

This document defines the strict **Payload Schemas** for each `EventType` defined in `EVENT_LOG_SPEC.md` v0.2.

**STATUS: FROZEN. DO NOT MODIFY WITHOUT RFC.**

## Validation Strategy (Transparency)

All payloads must validate against the JSON Schema.
**Canonicalization:** Payloads must be serialized using RFC 8785 (JCS) before hashing.

## 1. Lifecycle Events

### SESSION_START

```json
{
  "agent_id": "string (required)",
  "tags": ["string"],
  "environment": "prod|staging|dev (required)",
  "framework": "string (required)",
  "framework_version": "string (required)",
  "sdk_version": "string (required)",
  "system_prompt_hash": "sha256 (optional)"
}
```

### SESSION_END

```json
{
  "status": "success|failure|timeout|cancelled (required)",
  "reason": "string (optional)",
  "duration_ms": "uint64 (required)",
  "total_cost_usd": "float (optional)"
}
```

## 2. Execution Events

### TOOL_CALL

```json
{
  "tool_name": "string (required)",
  "tool_id": "string (optional, for correlation)",
  "args": "object (required)",
  "args_hash": "sha256 (optional, required if args is redacted)",
  "timeout_ms": "int (optional)"
}
```

### TOOL_RESULT

```json
{
  "tool_name": "string (required)",
  "tool_id": "string (optional, must match call)",
  "result": "object|string (required)",
  "result_hash": "sha256 (optional, required if result is redacted)",
  "status": "success|error (required)",
  "duration_ms": "uint64 (required)"
}
```

## 3. Interaction Events

### MODEL_REQUEST

```json
{
  "model": "string (required)",
  "provider": "openai|anthropic|azure|... (required)",
  "messages": [
    {
      "role": "system|user|assistant|tool",
      "content": "string (required by schema, but may be '[REDACTED]')",
      "content_hash": "sha256 (optional, REQUIRED if content is '[REDACTED]')",
      "name": "string (optional)"
    }
  ],
  "parameters": {
    "temperature": "float",
    "top_p": "float",
    "max_tokens": "int"
  }
}
```

### MODEL_RESPONSE

```json
{
  "model": "string (required)",
  "content": "string (required, may be '[REDACTED]')",
  "content_hash": "sha256 (optional, REQUIRED if content is '[REDACTED]')",
  "role": "assistant (required)",
  "finish_reason": "stop|length|tool_calls|content_filter (required)",
  "usage": {
    "prompt_tokens": "int",
    "completion_tokens": "int",
    "total_tokens": "int"
  }
}
```

## 4. Governance Events (Verified)

### DECISION_TRACE

_Structured evidence of a decision. NO FREEFORM THOUGHTS._

```json
{
  "decision_id": "uuid (required)",
  "inputs": "object (required)",
  "outputs": "object (required)",
  "justification": "string (required - policy/rule/logic used)",
  "policy_version": "string (optional)"
}
```

### ERROR

```json
{
  "error_type": "string (required)",
  "message": "string (required)",
  "stack_trace": "string (optional)",
  "fatal": "boolean (required)"
}
```

### ANNOTATION

```json
{
  "annotator_id": "string (required)",
  "annotation_type": "flag|comment|rating (required)",
  "content": "object (required)",
  "target_event_id": "uuid (optional)"
}
```
