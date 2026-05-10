# AgentOps Replay — Failure Modes and Semantics

Version: 1.0
Status: Stable
Last Updated: May 2026
This document is the authoritative specification for system behavior under failure and adversarial conditions.

---

This document specifies the failure modes that AgentOps Replay is designed to handle, the mechanisms by which failures are recorded in the event chain, and the invariants that must hold under all failure conditions. Understanding these failure modes is essential for correctly interpreting session evidence and for building systems that rely on AgentOps Replay for auditability.

The governing principle across all failure modes is: **visible failure is always preferable to silent failure.** A chain that explicitly records what was lost is more trustworthy than a chain that conceals its gaps.

---

## 1. LOG_DROP

### 1.1 When LOG_DROP Is Triggered

A `LOG_DROP` event is emitted by the SDK whenever events are lost before they can be included in the persistent chain. There are two primary causes:

**Buffer overflow.** The SDK maintains an in-memory ring buffer of configurable capacity. If the agent produces events faster than they can be flushed — or if the total number of events in a session exceeds the buffer size — new events cannot be pushed. Rather than silently discarding these events, the SDK accumulates a drop record tracking the sequence range and count of lost events. When `end_session()` is called, if a drop record exists, the SDK emits a single `LOG_DROP` event summarizing all accumulated losses before writing `SESSION_END`. This ensures that the existence of data loss is recorded in the chain, not hidden.

**SDK internal error.** If an unexpected exception occurs during event construction — for example, a serialization failure in the payload — the SDK emits a `LOG_DROP` with `reason = "internal_error"` to record that an event was intended but could not be constructed.

### 1.2 LOG_DROP Payload Fields

The `LOG_DROP` payload contains the following required fields:

- `count` (integer): The total number of events that were lost.
- `reason` (string): Either `"buffer_overflow"` or `"internal_error"`.
- `seq_range_start` (integer): The sequence number of the first event that was dropped.
- `seq_range_end` (integer): The sequence number of the last event that was dropped.

Together, these fields allow a reviewer to determine precisely which portion of the event history is missing.

### 1.3 How the Verifier Responds to LOG_DROP

The verifier does not fail a chain that contains `LOG_DROP` events. `LOG_DROP` is a first-class chain event and participates in hash linking in the same way as any other event. Its presence does not trigger a chain integrity failure. However, the verifier's evidence class determination algorithm accounts for `LOG_DROP`: a sealed chain containing one or more `LOG_DROP` events is classified as `PARTIAL_AUTHORITATIVE_EVIDENCE` rather than `AUTHORITATIVE_EVIDENCE`.

### 1.4 The Silent Loss Invariant

The core invariant governing `LOG_DROP` is: **it is always worse to silently drop events than to visibly record the loss.** A chain with a `LOG_DROP` at `seq_range_start=50` through `seq_range_end=75` tells a reviewer exactly what happened and when. A chain that simply skips those sequence numbers without explanation provides no such information and looks identical to a tampered chain. The SDK is designed to make the former impossible: the ring buffer cannot silently discard events, and the `LOG_DROP` mechanism exists precisely to surface every instance of loss.

---

## 2. CHAIN_BROKEN

### 2.1 When CHAIN_BROKEN Is Emitted

`CHAIN_BROKEN` is a server-authority event emitted by the ingestion service when it detects a sequence gap in an incoming event batch that it cannot resolve. This occurs when the ingestion service receives a batch where `seq` values are not strictly continuous — for example, receiving events with `seq = 1, 2, 5, 6` with no events for `seq = 3` and `seq = 4`.

Unlike a `LOG_DROP` (which is emitted by the SDK and signals client-side loss), `CHAIN_BROKEN` is emitted by the server and signals that the gap is detected at the point of ingestion. The ingestion service writes the events it did receive atomically, then appends `CHAIN_BROKEN` to document the gap. It does not fabricate or infer the missing events.

---

## 3. Fail-Open vs. Fail-Closed

AgentOps Replay applies asymmetric failure semantics to its two principal components.

### 3.1 The SDK Must Fail Open

The SDK runs inside the agent process and is responsible for capturing observability data without interfering with the agent's primary function. Under all error conditions — buffer overflow, serialization failure, network unavailability, internal exceptions — the SDK must never raise an exception that could propagate to the agent and crash it or interrupt its operation. This is the fail-open principle: when in doubt, the SDK records the failure as data (`LOG_DROP` or `TOOL_ERROR`) and continues running.

### 3.2 The Ingestion Service Must Fail Closed

The ingestion service is responsible for the integrity of the persistent event record. Under any error condition — hash mismatch, sequence gap, malformed payload, database write failure — the ingestion service must reject the entire batch atomically and return an appropriate error code. It must never write a partial batch to the database, as this would produce a chain whose integrity cannot be independently verified.

---

## 4. Adversary Models

AgentOps Replay is designed to provide specific integrity guarantees against four classes of adversaries.

### A1: Compromised SDK (Malicious Producer)
**Capability:** The adversary has full control over the agent process and the SDK. They can omit events, fabricate fake events, or attempt to modify the sequence.
**Defense:** The hash chain ensures that any omission or fabrication results in a `prev_hash` mismatch. The ingestion service recomputes all hashes server-side, so the adversary cannot spoof hashes. The verifier detects any inconsistency in the exported JSONL.

### A2: Man-in-the-Middle (MITM)
**Capability:** The adversary can intercept, modify, or drop network packets between the SDK and the Ingestion Service.
**Defense:** While TLS prevents most MITM attacks, the cryptographic chain provides a second layer of defense. If the adversary drops packets, the server detects a sequence gap and emits `CHAIN_BROKEN`. If they modify packets, the server's hash recomputation fails.

### A3: Compromised Storage (Malicious Auditor)
**Capability:** The adversary has read/write access to the database or the persistent storage where event logs are kept. They want to "rewrite history" by deleting or modifying past events.
**Defense:** Because the chain is anchored by the `CHAIN_SEAL` (which contains the `final_hash` of the session), any modification to a stored event breaks the cryptographic link to the seal. A reviewer running the verifier against the exported log will immediately detect the tampering.

### A4: Insider (Malicious Admin)
**Capability:** The adversary is a system administrator with root access to the Ingestion Service.
**Defense:** While an admin can delete entire sessions, they cannot *silently* modify them. The existence of the standalone verifier allows third-party auditors to verify logs exported from the system. If the admin attempts to forge a `CHAIN_SEAL` for a modified chain, they would need to compromise the server's signing key (if implemented) or produce a hash collision. The independent verifier remains the final check.

The four adversary models A1–A4 are formally analyzed in [docs/TRUST_MODEL.md](TRUST_MODEL.md) §4.1–4.4. Adversary A5 (full chain rewrite) is documented as a known limitation in §4.5.

---

## 5. Security Objectives

1. **Tamper-Evident:** Any modification to an event or its position in the sequence must be detectable by the verifier.
2. **Immutable History:** Once a session is sealed, the server provides no mechanism to modify it (except for documented `REDACTION`).
3. **Attributable Loss:** All data loss must be recorded as either `LOG_DROP` or `CHAIN_BROKEN`.

---

## 6. Implementation Checklist for Fail-Open/Fail-Closed

To ensure these failure semantics are maintained, all implementations must satisfy the following:

- **SDK (Fail-Open):**
    - [ ] `AgentOpsClient.push()` must be wrapped in `try/except Exception`.
    - [ ] If the buffer is full, `push()` must return `False` immediately, not block.
    - [ ] Background sender threads must not exit on network errors; they must use exponential backoff.
    - [ ] If a session end fails to reach the server, the SDK must flush to a local `session.jsonl` as a fallback.

- **Ingestion Service (Fail-Closed):**
    - [ ] `POST /ingest` must use database transactions.
    - [ ] Any `HashMismatch` or `SequenceGap` must trigger a `ROLLBACK`.
    - [ ] The service must return `HTTP 409 Conflict` for duplicate sequence numbers.
    - [ ] `CHAIN_SEAL` must only be written if `SESSION_END` is present in the current batch or database.

## 7. Practical Recovery Scenarios

### Scenario 1: Intermittent Network Outage
The SDK buffer fills up. It records a `LOG_DROP`. Once the network returns, the SDK flushes the `LOG_DROP` followed by `SESSION_END`. The server verifies the chain up to the drop, appends the drop, and seals the session as `PARTIAL_AUTHORITATIVE_EVIDENCE`. The record remains sound.

### Scenario 2: Database Server Crash
The ingestion service is halfway through writing a batch. The transaction rolls back. The SDK receives a 500 error. The SDK retries. No partial or corrupted chains are ever persisted.

### Scenario 3: Malicious sequence injection
An attacker sends `seq=1, 2, 10`. The server detects the gap between 2 and 10, rejects the batch, or (if configured) appends `CHAIN_BROKEN` to the last valid point (seq=2) and refuses the jump. The cryptographic anchor at `seq=2` prevents the attacker from retroactively modifying events 1 and 2.
