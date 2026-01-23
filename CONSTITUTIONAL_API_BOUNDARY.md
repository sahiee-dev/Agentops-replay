# CONSTITUTIONAL_API_BOUNDARY.md (v1.0)

## Purpose

This document defines the **Constitutional API Boundary** - the interface contract between the AgentOps Replay core and external adapters (e.g., LangChain, LlamaIndex, CrewAI).

**Critical:** Adapters MUST NOT bypass constitutional invariants. This boundary prevents gradual erosion of guarantees.

---

## 1. Adapter Responsibilities

Adapters (e.g., LangChain integration) are **event producers**, not **chain authorities**.

### What Adapters MAY Do

✅ **Emit Events:**

- Call `client.record(EventType.TOOL_CALL, payload)`
- Provide payload data (tool names, arguments, results)
- Set timestamps (wall clock)

✅ **Request Session Management:**

- `client.start_session(agent_id="...")`
- `client.end_session(status="success")`

✅ **Configure SDK Behavior:**

- Set buffer size
- Set flush intervals
- Choose local vs. server authority mode

### What Adapters MUST NOT Do

❌ **Bypass Chain Integrity:**

- MUST NOT compute `prev_event_hash` manually
- MUST NOT set `event_hash` directly
- MUST NOT modify event envelopes after emission

❌ **Forge Authority:**

- MUST NOT set `chain_authority` field (SDK controls this)
- MUST NOT emit `CHAIN_SEAL` events (SDK or server only)
- MUST NOT claim server authority in local mode

❌ **Violate Immutability:**

- MUST NOT delete emitted events
- MUST NOT modify event payloads after emission
- MUST NOT reorder events

❌ **Access Internal SDK State:**

- MUST NOT read ring buffer directly
- MUST NOT manipulate sequence numbers
- MUST NOT access hash chain internals

---

## 2. Adapter API Surface

### Permitted SDK Methods

```python
# Session management
client.start_session(agent_id: str, metadata: Dict = None) -> str
client.end_session(status: str, duration_ms: int = None) -> None

# Event emission
client.record(event_type: EventType, payload: Dict) -> None

# Convenience methods (sugar over record())
client.record_tool_call(tool_name: str, args: Dict) -> None
client.record_tool_result(tool_name: str, result: Any) -> None
client.record_model_request(model: str, prompt: str) -> None
client.record_model_response(model: str, response: str, tokens: int) -> None

# Flush control
client.flush() -> None  # Force immediate flush (if applicable)
client.flush_to_jsonl(filename: str) -> None  # Local mode only
```

### Forbidden SDK Methods (Internal Only)

```python
# These exist but are INTERNAL USE ONLY
# Adapters MUST NOT call these

client._emit_raw_event(envelope: Dict) -> None  # Bypass envelope construction
client._set_prev_hash(prev_hash: str) -> None  # Manual chain manipulation
client._compute_event_hash(event: Dict) -> str  # Hash computation exposed
client.buffer._evict_event(index: int) -> None  # Buffer manipulation
```

**Enforcement:**

- Internal methods prefixed with `_` (Python convention)
- Future: Use `@internal` decorator for runtime checks
- Documentation explicitly marks forbidden methods

---

## 3. Payload Constraints

### What Adapters MAY Include in Payloads

✅ **Domain-Specific Data:**

```json
{
  "tool_name": "web_search",
  "query": "capital of France",
  "results": [{ "title": "...", "url": "..." }],
  "execution_time_ms": 150
}
```

✅ **Metadata:**

```json
{
  "framework": "langchain",
  "framework_version": "0.1.0",
  "adapter_version": "1.2.3"
}
```

✅ **PII (with redaction support):**

```json
{
  "user_query": "[REDACTED]",
  "user_query_hash": "sha256:...",
  "response": "The capital of France is Paris."
}
```

### What Adapters MUST NOT Include

❌ **Chain Metadata (Reserved):**

- `event_id` - SDK generates
- `sequence_number` - SDK manages
- `prev_event_hash` - SDK computes
- `event_hash` - SDK computes
- `chain_authority` - SDK enforces

❌ **Envelope Fields:**

- `timestamp_monotonic` - SDK provides
- `schema_ver` - SDK enforces
- `source_sdk_ver` - SDK provides

**Rationale:** These fields are **cryptographically significant**. Allowing adapters to set them would break chain integrity.

---

## 4. Authority Mode Selection

### Adapter Configuration

```python
# Local authority mode (testing, development)
client = AgentOpsClient(local_authority=True)

# Server authority mode (production)
client = AgentOpsClient(
    local_authority=False,
    ingestion_endpoint="https://ingest.example.com"
)
```

### Adapter Constraints

1. **Local Mode:**
   - Adapter MUST NOT claim this is production evidence
   - Adapter SHOULD log warnings if used in production
   - Evidence classification: `NON_AUTHORITATIVE_EVIDENCE`

2. **Server Mode:**
   - Adapter MUST send events to ingestion service
   - Adapter MUST NOT bypass ingestion
   - Adapter MUST handle network failures (SDK buffers)

---

## 5. Invariant Enforcement

### Adapter-Facing Invariants

Adapters MUST respect:

1. **Event Ordering:**
   - Events emitted in order A, B, C will appear in that order in the log
   - No reordering allowed

2. **Payload Immutability:**
   - Once `client.record()` returns, payload is frozen
   - No editing, no deletion

3. **Single Session:**
   - One `start_session()` per client instance
   - No session nesting or parallelism

4. **Event Type Constraints:**
   - `SESSION_START` emitted automatically by `start_session()`
   - `SESSION_END` emitted automatically by `end_session()`
   - Adapters MUST NOT emit these manually

---

## 6. Failure Semantics

### What Happens When Adapters Misbehave

| Violation                   | Detection                 | Consequence                           |
| --------------------------- | ------------------------- | ------------------------------------- |
| **Manual hash computation** | Verifier detects mismatch | Session fails verification            |
| **Authority forgery**       | Missing CHAIN_SEAL        | Evidence class: PARTIAL_AUTHORITATIVE |
| **Sequence manipulation**   | Sequence gap              | Verification fails                    |
| **Duplicate session start** | SDK rejects               | Exception raised                      |
| **Payload mutation**        | Hash mismatch             | Verification fails                    |

**Key Principle:** SDK and verifier are **defensive**. Adapter bugs cannot silently corrupt the chain.

---

## 7. LangChain-Specific Guidance

### LangChain Adapter Design

```python
from langchain.callbacks import BaseCallbackHandler
from agentops_sdk.client import AgentOpsClient

class AgentOpsCallbackHandler(BaseCallbackHandler):
    def __init__(self, local_authority=False):
        self.client = AgentOpsClient(local_authority=local_authority)
        self.session_id = None

    def on_chain_start(self, serialized, inputs, **kwargs):
        self.session_id = self.client.start_session(agent_id="langchain-agent")

    def on_llm_start(self, serialized, prompts, **kwargs):
        self.client.record_model_request(
            model=serialized.get("model_name", "unknown"),
            prompt=prompts[0]
        )

    def on_llm_end(self, response, **kwargs):
        self.client.record_model_response(
            model=response.llm_output.get("model_name"),
            response=response.generations[0][0].text,
            tokens=response.llm_output.get("token_usage", {}).get("total_tokens")
        )

    def on_tool_start(self, serialized, input_str, **kwargs):
        self.client.record_tool_call(
            tool_name=serialized.get("name"),
            args={"input": input_str}
        )

    def on_tool_end(self, output, **kwargs):
        self.client.record_tool_result(
            tool_name=kwargs.get("name"),
            result=output
        )

    def on_chain_end(self, outputs, **kwargs):
        self.client.end_session(status="success")
```

### What This Gets Right

✅ Uses public SDK API only  
✅ Doesn't touch chain metadata  
✅ Respects session lifecycle  
✅ Payloads are domain-specific (LangChain tool names, prompts)

### What Would Be Wrong

❌ `self.client._set_prev_hash(...)` - Internal API  
❌ `self.client.record(EventType.CHAIN_SEAL, ...)` - Forbidden event type  
❌ `self.client.buffer._evict_event(0)` - Buffer manipulation

---

## 8. Testing Adapter Compliance

### Adapter Certification Checklist

Before merging a new adapter:

- [ ] Adapter uses only public SDK methods
- [ ] Adapter does not set chain metadata fields
- [ ] Adapter does not emit `CHAIN_SEAL` or internal event types
- [ ] Adapter respects session lifecycle (start → events → end)
- [ ] Adapter payloads are domain-specific (no envelope pollution)
- [ ] Generated sessions pass verifier with appropriate evidence class
- [ ] Adapter handles SDK buffer overflow gracefully (no crash)
- [ ] Adapter documentation warns about local vs. server authority

### Test Vectors

```bash
# Run adapter, export session
python examples/langchain_adapter_example.py

# Verify session
python3 verifier/agentops_verify.py langchain_session.jsonl --format json

# Expected:
# - status: PASS
# - evidence_class: NON_AUTHORITATIVE_EVIDENCE (if local) or PARTIAL_AUTHORITATIVE (if server, unsealed)
# - violations: [] (no chain integrity errors)
```

---

## 9. Explicit Non-Goals

Adapters are **NOT** expected to:

- **Handle seal generation** (server responsibility)
- **Manage key rotation** (infrastructure responsibility)
- **Implement custom verification** (use standalone verifier)
- **Provide compliance reporting** (use report generators)

---

## 10. Amendment Process

This boundary is **frozen at v1.0** for EVENT_LOG_SPEC v0.6.

Changes require:

1. Constitutional approval (CONSTITUTION.md amendment)
2. Proof that change does not weaken invariants
3. Test vectors demonstrating adapter compliance

---

**Status:** FROZEN (v1.0)  
**Effective:** Event Log Spec v0.6+  
**Applies To:** All framework adapters (LangChain, LlamaIndex, CrewAI, etc.)
