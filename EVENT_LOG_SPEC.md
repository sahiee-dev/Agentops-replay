# EVENT_LOG_SPEC.md (v0.5)

## 0. Purpose

This document defines the **Event Log Specification (ELS) v0.5** for AgentOps Replay.
This specification is the Constitutional Spine of the project.

## 1. Event Envelope (Frozen Forever)

```protobuf
message EventEnvelope {
  string event_id = 1;
  string session_id = 2;
  uint64 sequence_number = 3;
  string timestamp_wall = 4;
  uint64 timestamp_monotonic = 5;
  EventType event_type = 6;
  string source_sdk_ver = 7;
  string schema_ver = 8;        // "v0.5" (MUST match ELS version)
  string payload_hash = 9;
  string prev_event_hash = 10;
  string event_hash = 11;
  bytes payload = 12;
  string chain_authority = 13;  // "sdk" | "server" | "unknown"
  string authority_id = 14;
}
```

### 1.1 Hashing & Signing Rules

- **Signed Fields:** `event_id`, `session_id`, `sequence_number`, `timestamp_wall`, `event_type`, `payload_hash`, `prev_event_hash`
- **Event Hash:** `SHA-256(JCS(signed_fields_object))`

### 1.2 Chain Authority Model

The **Ingestion Service** is the default Chain Authority.

**Local Authority Mode Exception:**

1.  If `chain_authority == "sdk"` for **all events** in a session, the SDK is the authority.
2.  In this mode, the SDK computes `event_hash` and may emit `CHAIN_SEAL`.
3.  **Mixed authority is INVALID:** A session with both "sdk" and "server" events fails verification.

### 1.3 Payload Canonicalization

- **RFC 8785 (JCS)**
- **Floats:** IEEE-754 double
- **Strings:** UTF-8 NFC
- **Integers:** Signed 64-bit
- **Redaction:** `[REDACTED]` + `_hash` (optionally salted)

## 2. Event Types (Closed Set)

```protobuf
enum EventType {
  SESSION_START = 0;
  SESSION_END = 1;
  MODEL_REQUEST = 2;
  MODEL_RESPONSE = 3;
  TOOL_CALL = 4;
  TOOL_RESULT = 5;
  AGENT_STATE_SNAPSHOT = 6;
  DECISION_TRACE = 7;
  ERROR = 8;
  ANNOTATION = 9;
  CHAIN_SEAL = 10;  // Server-generated OR SDK in Local Authority Mode
  LOG_DROP = 11;
}
```

### 2.1 CHAIN_SEAL Authority Rules

- **Default:** Server-generated only (`chain_authority == "server"`).
- **Local Authority Exception:** SDK may emit `CHAIN_SEAL` if `chain_authority == "sdk"` for the entire session.
- **Mixed authority sessions:** INVALID.

## 3. Ordering & Causality

- `sequence_number` starts at 0, increments by 1.
- Gaps detectable via `prev_event_hash` mismatch.

## 4. Cryptographic Guarantees

To verify session `S`:

1.  **Consistency Check:** All events must have the same `chain_authority`. Mixed = INVALID.
2.  **Hash Check:** `SHA-256(canonical(payload[i])) == payload_hash[i]`
3.  **Chain Check:** `prev_event_hash[i] == event_hash[i-1]`
4.  **Envelope Check:** `SHA-256(JCS(signed_fields[i])) == event_hash[i]`
5.  **Seal Check:** If `CHAIN_SEAL` present, verify `chain_authority` matches session authority.

## 5. Failure Semantics

| Scenario            | Behavior         | Detectable? |
| ------------------- | ---------------- | ----------- |
| **Mixed Authority** | Session INVALID  | Yes         |
| **SDK Crash**       | No `SESSION_END` | Yes         |
| **Network Loss**    | Emit `LOG_DROP`  | Yes         |
