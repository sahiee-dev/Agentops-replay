# AUTHORITY_SOURCE_OF_TRUTH.md (v1.0)

## Purpose

This document formally defines how `chain_authority` is determined for each event, resolving ambiguity in adversarial edge cases.

**Context:** CHAIN_AUTHORITY_INVARIANTS.md defines _what_ authority means. This document defines _how_ it is determined.

---

## 1. Authority Determination Rules

### Rule 1: Authority Is Event-Level Metadata

Every event MUST have a `chain_authority` field with one of these values:

- `"server"` - Server-authoritative chain
- `"sdk"` - SDK/local-authoritative chain (testing only)
- `"unknown"` - Authority cannot be determined (session INVALID)

### Rule 2: Authority Source of Truth Per Event Type

| Event Type               | Authority Source             | Can SDK Set?     | Can Ingestion Override? |
| ------------------------ | ---------------------------- | ---------------- | ----------------------- |
| **SESSION_START**        | SDK proposal                 | Yes              | Yes (server mode)       |
| **SESSION_END**          | SDK proposal                 | Yes              | Yes (server mode)       |
| **MODEL_REQUEST**        | SDK proposal                 | Yes              | Yes (server mode)       |
| **MODEL_RESPONSE**       | SDK proposal                 | Yes              | Yes (server mode)       |
| **TOOL_CALL**            | SDK proposal                 | Yes              | Yes (server mode)       |
| **TOOL_RESULT**          | SDK proposal                 | Yes              | Yes (server mode)       |
| **AGENT_STATE_SNAPSHOT** | SDK proposal                 | Yes              | Yes (server mode)       |
| **DECISION_TRACE**       | SDK proposal                 | Yes              | Yes (server mode)       |
| **ERROR**                | SDK proposal                 | Yes              | Yes (server mode)       |
| **ANNOTATION**           | SDK or Server                | Yes              | Yes (always)            |
| **CHAIN_SEAL**           | MUST match session authority | SDK (local mode) | Server (server mode)    |
| **LOG_DROP**             | SDK or Server                | Yes              | Yes (server mode)       |

### Rule 3: Server Mode Authority Override

**Server Mode Behavior:**

1. SDK proposes events with `chain_authority` field
2. Ingestion service MUST rewrite `chain_authority = "server"` for ALL events
3. SDK-provided authority value is IGNORED
4. Ingestion MUST enforce single-authority invariant

**Local Mode Behavior:**

1. SDK sets `chain_authority = "sdk"` for ALL events
2. No ingestion service involvement (direct JSONL export)
3. SDK MUST enforce single-authority invariant locally

### Rule 4: Single Authority Invariant

All events in a session MUST have the SAME `chain_authority` value.

**Enforcement:**

- Ingestion service MUST reject events with mismatched authority
- Verifier MUST fail verification if mixed authority detected
- No migration between authority modes mid-session

---

## 2. Adversarial Edge Cases

### Case 1: SDK Sends `authority="server"` Without Ingestion

**Scenario:**

- SDK creates events with `chain_authority = "server"`
- Events written directly to JSONL (bypass ingestion)
- No CHAIN_SEAL present

**Expected Behavior:**

- Verifier classifies as `PARTIAL_AUTHORITATIVE_EVIDENCE` (unsealed)
- `partial_reasons`: `["UNSEALED_SESSION"]`
- Evidence class indicates missing seal, not fraud

**Why This Is Safe:**

- AUTHORITATIVE_EVIDENCE requires valid CHAIN_SEAL
- SDK cannot forge `ingestion_service_id` metadata
- Classification degrades gracefully, not catastrophically

### Case 2: Ingestion Overwrites Some Events, Not Others

**Scenario:**

- Ingestion receives 10 events
- Rewrites `chain_authority = "server"` for events 0-7
- Events 8-9 keep `chain_authority = "sdk"` (bug)

**Expected Behavior:**

- Verifier detects `len(authorities) > 1`
- Fails with `MIXED_AUTHORITY` violation
- Session classified as INVALID

**Why This Is Safe:**

- Single-authority invariant is enforced early (before chain validation)
- Fail-fast prevents partial acceptance
- No ambiguous "mostly server" state

### Case 3: Authority Field Missing

**Scenario:**

- Event has no `chain_authority` field
- Could be legacy v0.4 log or corrupted event

**Expected Behavior:**

- Verifier uses `"unknown"` as default
- If multiple authorities (including "unknown"), fails with `MIXED_AUTHORITY`
- If all events are "unknown", authority report shows "unknown"

**Why This Is Safe:**

- Unknown authority downgrades evidence classification
- No false confidence in authority provenance
- Explicit handling of missing metadata

### Case 4: CHAIN_SEAL Authority Mismatch

**Scenario:**

- Session has `chain_authority = "server"` for all events
- CHAIN_SEAL event has `chain_authority = "sdk"`

**Expected Behavior:**

- Single-authority check fails before seal validation
- `MIXED_AUTHORITY` violation
- Session INVALID

**Why This Is Safe:**

- Authority consistency checked before seal validation
- Cannot use SDK seal to "upgrade" server session
- Prevents authority laundering

---

## 3. Authority Lifecycle

### Server Mode Lifecycle

```
SDK Creates Event
  ↓
  chain_authority = "server" (proposed)
  ↓
Network Transport
  ↓
Ingestion Receives Event
  ↓
Ingestion Overwrites: chain_authority = "server" (enforced)
  ↓
Ingestion Validates Single Authority
  ↓
Ingestion Stores Event
  ↓
Verifier Reads Event
  ↓
Verifier Validates: authority == "server" for ALL events
  ↓
Verifier Checks: CHAIN_SEAL present with valid metadata
  ↓
Evidence Class: AUTHORITATIVE_EVIDENCE (if sealed + complete)
```

### Local Mode Lifecycle

```
SDK Creates Event
  ↓
  chain_authority = "sdk" (set locally)
  ↓
SDK Validates Single Authority
  ↓
SDK Writes to JSONL
  ↓
Verifier Reads Event
  ↓
Verifier Validates: authority == "sdk" for ALL events
  ↓
Evidence Class: NON_AUTHORITATIVE_EVIDENCE
```

---

## 4. Verifier Implementation

### Authority Determination Logic

```python
def determine_authority(events: List[Dict[str, Any]]) -> str:
    """
    Determine session authority from events.
    Returns "server", "sdk", or "unknown".
    Fails if mixed authority detected.
    """
    authorities = set()
    for event in events:
        authority = event.get("chain_authority", "unknown")
        authorities.add(authority)

    if len(authorities) > 1:
        raise VerificationError(
            "MIXED_AUTHORITY",
            f"Session has mixed authorities: {authorities}"
        )

    return authorities.pop() if authorities else "unknown"
```

### Authority Validation Per Event

```python
# For each event during chain validation:
event_authority = event.get("chain_authority", "unknown")

# Check consistency
if event_authority != session_authority:
    raise VerificationError(
        "AUTHORITY_MISMATCH",
        f"Event authority '{event_authority}' does not match session authority '{session_authority}'"
    )
```

---

## 5. Explicit Non-Goals

This specification does NOT:

- **Allow authority transitions mid-session** (session is server OR sdk, never both)
- **Support "hybrid" modes** (some events server, some SDK - explicitly forbidden)
- **Infer authority from context** (authority MUST be explicit in metadata)
- **Trust SDK-claimed server authority without seal** (requires CHAIN_SEAL for AUTHORITATIVE)

---

## 6. Auditor Talking Points

**Question:** "What if ingestion service has a bug and doesn't rewrite authority?"

**Answer:**

- Verifier detects mixed authority and fails verification
- Session classified as INVALID, not partially valid
- Fail-safe: no ambiguous states

**Question:** "Can SDK impersonate server authority?"

**Answer:**

- SDK can claim `authority="server"` but cannot forge CHAIN_SEAL
- Without valid CHAIN_SEAL, session downgrades to PARTIAL_AUTHORITATIVE
- AUTHORITATIVE_EVIDENCE requires both server authority AND valid seal

**Question:** "How do you handle legacy logs without authority metadata?"

**Answer:**

- Authority defaults to "unknown"
- All events with "unknown" passes single-authority check
- Evidence classification: depends on seal presence, likely PARTIAL or NON_AUTHORITATIVE

---

## 7. Authority Design Principles

1. **Explicit Over Implicit:** Authority MUST be in event metadata, never inferred
2. **Fail-Safe Over Fail-Secure:** Unknown authority downgrades classification, doesn't block
3. **All-Or-Nothing:** Session is entirely one authority, no hybrid modes
4. **Server Wins:** Ingestion service always overwrites authority in server mode
5. **Seal Required:** Server authority alone insufficient for AUTHORITATIVE_EVIDENCE

---

**Status:** FROZEN (v1.0)  
**Effective:** EVENT_LOG_SPEC v0.6+  
**Supersedes:** Implicit authority determination from v0.5
