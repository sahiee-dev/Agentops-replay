# AgentOps Replay — Failure Modes and Semantics

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

### 2.2 What CHAIN_BROKEN Means for Evidence Class

The presence of `CHAIN_BROKEN` in a sealed session results in `PARTIAL_AUTHORITATIVE_EVIDENCE`. This is the same evidence class as a sealed session with `LOG_DROP`. Both indicate that the server verified what it received, but acknowledges that the record is not complete.

The key distinction between `LOG_DROP` and `CHAIN_BROKEN` is their origin: `LOG_DROP` means the SDK knew it was dropping events and recorded the loss in the outgoing chain; `CHAIN_BROKEN` means the server detected the gap at ingestion and the SDK may not have been aware of it. Both are legitimate, visible records of incompleteness.

### 2.3 The Broken Chain Invariant

A broken chain that carries a `CHAIN_BROKEN` marker is more trustworthy than a chain that hides its breaks. `CHAIN_BROKEN` does not mean the session is worthless — it means the session record is honest about its limitations. Downstream systems interpreting AgentOps Replay evidence must treat `CHAIN_BROKEN` as a signal that a specific portion of the session history is absent, not that the entire session is invalid.

---

## 3. Fail-Open vs. Fail-Closed

AgentOps Replay applies asymmetric failure semantics to its two principal components. This asymmetry is not accidental; it reflects the different consequences of failure at each layer.

### 3.1 The SDK Must Fail Open

The SDK runs inside the agent process and is responsible for capturing observability data without interfering with the agent's primary function. Under all error conditions — buffer overflow, serialization failure, network unavailability, internal exceptions — the SDK must never raise an exception that could propagate to the agent and crash it or interrupt its operation. This is the fail-open principle: when in doubt, the SDK records the failure as data (`LOG_DROP` or `TOOL_ERROR`) and continues running.

The SDK achieves this through three mechanisms: `push()` returns `bool` rather than raising on full buffer; `_append_event()` wraps all event construction in a `try/except`; and `end_session()` explicitly catches all exceptions. The agent's execution is never sacrificed for the sake of perfect observability.

### 3.2 The Ingestion Service Must Fail Closed

The ingestion service is responsible for the integrity of the persistent event record. Unlike the SDK, it has no agent process to protect. Under any error condition — hash mismatch, sequence gap, malformed payload, database write failure — the ingestion service must reject the entire batch atomically and return an appropriate error code. It must never write a partial batch to the database, as this would produce a chain whose integrity cannot be independently verified.

This is the fail-closed principle: when in doubt, reject. A rejected batch that the client must retry is always preferable to a stored batch with corrupted or missing events. The ingestion service is the last line of defence for evidence integrity, and it must err on the side of rejection over acceptance whenever evidence correctness is in question.
