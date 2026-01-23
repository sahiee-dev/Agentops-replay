# EVENT_LOG_SPEC.md (v0.6)

## 0. Purpose

This document defines the **Event Log Specification (ELS) v0.6** for AgentOps Replay.
This specification is the Constitutional Spine of the project.

**Versioning Note:**

- v0.5 logs are re-interpreted, not re-validated
- Evidence classification is retroactive
- No historical log becomes invalid solely due to reclassification

**Language Convention:**
This specification uses RFC 2119 keywords: MUST, MUST NOT, SHOULD, SHOULD NOT, MAY.

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
  string schema_ver = 8;        // "v0.6" (Canonical; "v0.5" accepted for legacy re-interpretation)
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

**Bounded Modes:**

1.  **Server Authority Mode (Default):**
    - `chain_authority == "server"` for ALL events in session
    - Ingestion service MUST recompute `prev_event_hash` independently
    - SDK-provided `prev_event_hash` MUST be ignored
    - Server MUST emit `CHAIN_SEAL` to achieve `AUTHORITATIVE_EVIDENCE` status

2.  **Local Authority Mode (Testing Only):**
    - `chain_authority == "sdk"` for ALL events in session
    - SDK computes `event_hash` and `prev_event_hash`
    - SDK MAY emit `CHAIN_SEAL` for local testing
    - Sessions MUST be labeled `NON_AUTHORITATIVE_EVIDENCE`

3.  **Mixed Authority:**
    - REJECTED. Session with both "sdk" and "server" events MUST fail verification.
    - Verifier MUST emit `MIXED_AUTHORITY` violation.

### 1.3 Payload Canonicalization

- **RFC 8785 (JCS)** - REQUIRED for all payload hashing
- **Floats:** IEEE-754 double
- **Strings:** UTF-8 NFC
- **Integers:** Signed 64-bit
- **Redaction:** `[REDACTED]` + `_hash` (MAY be salted)

### 1.4 Source of Truth for Chain Continuity

**SERVER AUTHORITY MODE:**

- The server MUST recompute `prev_event_hash` independently
- SDK-provided `prev_event_hash` MUST be ignored
- Disagreement between SDK and server MUST result in `CHAIN_BROKEN` error
- Chain state is server-authoritative
- NO warnings or forks are permitted

**LOCAL AUTHORITY MODE:**

- The SDK computes `prev_event_hash`
- Server MUST validate but MUST NOT recompute
- This mode is ONLY for testing and development
- Sessions MUST be labeled `NON_AUTHORITATIVE_EVIDENCE`

**MIXED AUTHORITY:**

- REJECTED. Session MUST fail verification.

**Disagreement Handling:**

- Error: Verification MUST fail
- Chain is either valid or invalid, no gray area

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

- **Server Mode:** Server MUST emit `CHAIN_SEAL` for `AUTHORITATIVE_EVIDENCE` status
- **Local Mode:** SDK MAY emit `CHAIN_SEAL` if `chain_authority == "sdk"` for entire session
- **Mixed authority sessions:** INVALID, MUST fail verification

**Required CHAIN_SEAL Payload (Server Authority):**

```json
{
  "ingestion_service_id": "prod-ingest-01",
  "seal_timestamp": "2026-01-23T12:00:00.000Z",
  "session_digest": "sha256:abc123..."
}
```

All three fields are REQUIRED for server authority `CHAIN_SEAL`. Missing fields MUST cause `INVALID_SEAL` violation.

### 2.2 LOG_DROP Semantics

**Purpose:** `LOG_DROP` events represent buffer overflow or network loss. They MUST be forensically traceable.

**Sequence Space:**

- LOG_DROP events MUST consume a sequence number
- Sequence MUST remain monotonic: if event N is dropped, LOG_DROP appears at sequence N

**Payload Requirements:**

```json
{
  "event_type": "LOG_DROP",
  "payload": {
    "dropped_count": 5, // REQUIRED: events lost in this drop
    "cumulative_drops": 12, // REQUIRED: total drops in session
    "drop_reason": "BUFFER_FULL", // REQUIRED: SDK_CRASH | BUFFER_FULL | NETWORK_LOSS
    "sequence_range": [100, 104] // OPTIONAL: if known
  }
}
```

**Replay Behavior:**

- Replay MUST continue after LOG_DROP
- Replay MUST mark the session as `PARTIAL_AUTHORITATIVE_EVIDENCE`
- Auditors MUST be shown cumulative drop count

**SESSION_END Behavior:**

- LOG_DROP MAY occur before SESSION_END
- If SESSION_END is dropped, session MUST be marked `UNSEALED`

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

| Scenario               | Behavior           | Detectable? | Evidence Class        |
| ---------------------- | ------------------ | ----------- | --------------------- |
| **Mixed Authority**    | Session INVALID    | Yes         | FAIL                  |
| **SDK Crash**          | No `SESSION_END`   | Yes         | PARTIAL_AUTHORITATIVE |
| **Network Loss**       | Emit `LOG_DROP`    | Yes         | PARTIAL_AUTHORITATIVE |
| **Missing CHAIN_SEAL** | Unsealed           | Yes         | PARTIAL_AUTHORITATIVE |
| **Invalid CHAIN_SEAL** | Malformed metadata | Yes         | FAIL                  |

## 6. Evidence Classification

Every session MUST be classified into exactly one of three states:

**AUTHORITATIVE_EVIDENCE:**

- Server authority (`chain_authority="server"`)
- Valid `CHAIN_SEAL` with required metadata
- Complete session (has `SESSION_END`)
- No `LOG_DROP` events
- Chain cryptographically valid

**PARTIAL_AUTHORITATIVE_EVIDENCE:**

- Server authority (`chain_authority="server"`)
- Cryptographically valid chain
- BUT one or more of:
  - Missing `CHAIN_SEAL` (unsealed)
  - Missing `SESSION_END` (incomplete)
  - Contains `LOG_DROP` events (data loss occurred)

**NON_AUTHORITATIVE_EVIDENCE:**

- SDK/local authority (`chain_authority="sdk"`)
- Chain may be cryptographically valid
- Explicitly flagged as testing/development only

See CHAIN_AUTHORITY_INVARIANTS.md for full specification.
