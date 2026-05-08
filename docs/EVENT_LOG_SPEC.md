# AgentOps Replay — Event Log Specification (ELS v1.0)

Version: 1.0
Status: Stable
Last Updated: May 2026
This document is the authoritative specification for the event log format.

---

## 1. The 7-Field Envelope

Every event stored in an AgentOps Replay session log is represented as a JSON object with exactly seven fields. No additional fields are permitted at the envelope level. Payload-specific data is carried inside the `payload` field.

### 1.1 `seq` (integer, required)

A monotonically increasing, strictly positive integer that uniquely identifies the position of this event within its session. The first event in a session must have `seq = 1`. Each subsequent event must have `seq = prev_event.seq + 1`. Gaps, duplicates, or non-integer values constitute a chain integrity violation.

### 1.2 `event_type` (string, required)

A string identifier for the event category. Must be one of the 12 canonical values defined in Section 2. Values not in that list must be rejected by the ingestion service with HTTP 400.

### 1.3 `session_id` (string, required)

A UUID string (version 4) that identifies the session to which this event belongs. All events in a single JSONL file must share the same `session_id`. Mixed-session files are invalid and must be rejected.

### 1.4 `timestamp` (string, required)

An ISO 8601 UTC timestamp with microsecond precision, formatted as `YYYY-MM-DDTHH:MM:SS.ffffffZ`. The timestamp is set by the SDK at the moment the event is built. Server-side timestamps are stored separately and are never substituted for this field. Timestamps are informational only — they do not participate in hash computation or ordering (ordering is defined by `seq`).

### 1.5 `payload` (object, required)

A JSON object containing event-specific data. The payload schema varies by event type. The payload must be JSON-serializable. Chain-of-thought data, raw prompt content, and personally identifiable information must never appear verbatim in the payload; callers must hash such data before including it.

### 1.6 `prev_hash` (string, required)

The `event_hash` value of the immediately preceding event in the session. For the first event (`seq = 1`), `prev_hash` must equal the GENESIS_HASH (64 hexadecimal zero characters). Any other value for `seq = 1` is a structural violation. For all subsequent events, the ingestion service independently recomputes and verifies this linkage before accepting the batch.

### 1.7 `event_hash` (string, required)

A SHA-256 hex digest computed over the canonical JSON representation of the event, excluding the `event_hash` field itself. See Section 3 for the exact computation algorithm. The event_hash binds all six other fields together into a tamper-evident unit. The ingestion service recomputes this value server-side and rejects any event whose provided hash does not match the server's computation.

---

## 2. Event Type Catalogue

AgentOps Replay defines exactly 12 event types, divided into two authority classes. The SDK may only produce SDK-authority events. Server-authority events may only be produced by the ingestion service. An SDK that emits a server-authority event must be rejected.

### 2.1 SDK-Authority Events

These eight event types represent facts observed by the SDK in the agent process.

- **SESSION_START**: Marks the beginning of a session. Must be the first event (`seq = 1`). The payload must include `agent_id` and should include `model_id` and any session-level tags.

- **SESSION_END**: Marks the end of a session. Must be the last SDK-authority event. The payload must include a `status` field (`"success"` or `"error"`). The verifier requires SESSION_END for a complete chain.

- **LLM_CALL**: Records the invocation of a language model. The payload must include a `prompt_hash` (SHA-256 of the prompt content) and `model_id`. Raw prompt text must never appear.

- **LLM_RESPONSE**: Records the completion returned by a language model. The payload must include a `content_hash` (SHA-256 of the response content) and a `finish_reason`.

- **TOOL_CALL**: Records the invocation of a tool or function. The payload must include `tool_name` and `args_hash` (SHA-256 of the serialized arguments).

- **TOOL_RESULT**: Records the output of a tool invocation. The payload must include `tool_name` and `result_hash` (SHA-256 of the result).

- **TOOL_ERROR**: Records a failure during a tool invocation or LLM call. The payload must include `error_type` and a truncated `error_message` (maximum 500 characters). Full stack traces must not be stored.

- **LOG_DROP**: Records that one or more events were lost due to buffer overflow or an SDK internal error. The payload must include `count`, `reason`, `seq_range_start`, and `seq_range_end`. LOG_DROP is itself a chain event and participates in hash linking. It must never be omitted to conceal data loss.

### 2.2 Server-Authority Events

These four event types may only be produced by the ingestion service after independent verification.

- **CHAIN_SEAL**: Appended by the ingestion service after successfully verifying and storing a complete session. Its payload includes `final_hash`, `authority`, `event_count`, `server_timestamp`, and `server_version`. The presence of CHAIN_SEAL without LOG_DROP elevates the evidence class to AUTHORITATIVE_EVIDENCE.

- **CHAIN_BROKEN**: Appended by the ingestion service when a sequence gap is detected in an incoming batch that cannot be resolved. It records the gap and degrades evidence class accordingly.

- **REDACTION**: Records a legally compliant redaction of a previously stored event payload. The original event remains in the chain; only the payload is replaced. The event_hash of the original event is preserved as a reference.

- **FORENSIC_FREEZE**: Records an administrative lock applied to a session that prevents any further modification or redaction. Used in legal hold scenarios.

---

## 3. Hash Computation Algorithm

The `event_hash` field is computed using the following deterministic algorithm. Implementations must follow these steps exactly to ensure cross-implementation compatibility.

**Step 1 — Construct the hash input object.** Take the event dictionary and remove the `event_hash` key. The resulting object must contain exactly six fields: `seq`, `event_type`, `session_id`, `timestamp`, `payload`, and `prev_hash`.

**Step 2 — Canonicalize using JCS (RFC 8785).** Apply JSON Canonicalization Scheme to the six-field object. JCS sorts object keys lexicographically at all nesting levels and removes insignificant whitespace, producing a deterministic byte sequence regardless of key insertion order or whitespace conventions.

**Step 3 — Compute SHA-256.** Apply the SHA-256 hash function to the UTF-8 encoded canonical bytes produced in Step 2.

**Step 4 — Encode as hex digest.** Encode the 32-byte SHA-256 output as a lowercase hexadecimal string of exactly 64 characters. This string is the `event_hash`.

The canonical implementation is located at `verifier/jcs.py` and is the single authoritative copy. The SDK imports JCS from this file via `sys.path.insert`. No duplicate or alternative JCS implementation is permitted in this repository.

---

## 4. GENESIS_HASH

The first event in any session (`seq = 1`) has no predecessor. Its `prev_hash` must be set to the GENESIS_HASH, which is defined as a string of 64 ASCII zero characters:

```
0000000000000000000000000000000000000000000000000000000000000000
```

This value is a sentinel, not a hash of any real data. The verifier checks that `seq = 1` events have exactly this `prev_hash` value. Any other value constitutes a structural violation and results in a FAIL with exit code 1.

---

## 5. Evidence Class Determination

The verifier determines the evidence class of a session after all four integrity checks pass. The evidence class reflects the strength of the evidentiary guarantee the chain provides.

```
function determine_evidence_class(events):
    has_chain_seal  = any event has event_type == "CHAIN_SEAL"
    has_log_drop    = any event has event_type == "LOG_DROP"
    has_chain_broken = any event has event_type == "CHAIN_BROKEN"

    if has_chain_seal and not has_log_drop and not has_chain_broken:
        return "AUTHORITATIVE_EVIDENCE"
    elif has_chain_seal and (has_log_drop or has_chain_broken):
        return "PARTIAL_AUTHORITATIVE_EVIDENCE"
    else:
        return "NON_AUTHORITATIVE_EVIDENCE"
```

A session that fails any integrity check has `evidence_class = null`. Evidence class is only meaningful for passing sessions.
