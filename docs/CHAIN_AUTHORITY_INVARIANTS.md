# AgentOps Replay — Chain Authority Invariants

This document specifies the trust model and authority separation rules that govern event production in AgentOps Replay. These invariants are not optional; they are enforced by the ingestion service and verified by the standalone verifier. Any implementation that violates these rules produces evidence that cannot be trusted.

---

## 1. The Two Principals

AgentOps Replay operates under a two-principal trust model. Understanding the asymmetry between these principals is essential for understanding what evidence guarantees the system can and cannot provide.

**Principal 1 — The SDK (Untrusted Producer).** The SDK runs inside the agent process, in the same memory space as the agent being observed. It is subject to all the same faults, crashes, corruptions, and intentional manipulations that could affect the agent itself. For this reason, the SDK is treated as an untrusted producer. Its output is always verified server-side before being accepted as a record of fact. The SDK is not inherently malicious; it is simply not in a position to make authoritative claims about its own output.

**Principal 2 — The Ingestion Service (Trusted Authority).** The ingestion service runs outside the agent process, in a controlled server environment with independent access to time, cryptographic keys, and the persistent event store. It is the only entity authorized to make authoritative claims about the integrity of a session chain. The ingestion service independently recomputes all hashes, verifies sequence ordering, and appends server-authority events only after passing all integrity checks.

---

## 2. Authority Separation Rules

The distinction between SDK-authority and server-authority event types is fundamental to the evidence model. These rules must be enforced at the protocol boundary.

**The SDK may produce:** `SESSION_START`, `SESSION_END`, `LLM_CALL`, `LLM_RESPONSE`, `TOOL_CALL`, `TOOL_RESULT`, `TOOL_ERROR`, `LOG_DROP`.

**The ingestion service may produce:** `CHAIN_SEAL`, `CHAIN_BROKEN`, `REDACTION`, `FORENSIC_FREEZE`.

**Rule 1 — SDK events are claims, not facts.** When the SDK submits a batch, the ingestion service treats every field — including `event_hash` and `prev_hash` — as a claim to be verified, not a fact to be trusted. The ingestion service recomputes every `event_hash` using its own canonical JCS implementation. Any mismatch results in HTTP 400.

**Rule 2 — The SDK must never emit server-authority events.** An SDK that constructs and submits a `CHAIN_SEAL` event is violating the trust boundary. The ingestion service must reject such a batch. Detection of this pattern is grounds for treating the entire session as tampered.

**Rule 3 — Mixed-authority chains are invalid.** A chain that contains both SDK-produced and server-produced `CHAIN_SEAL` events, or that shows evidence of authority confusion, must be rejected in its entirety. Partial acceptance of a mixed-authority chain is not permitted.

**Rule 4 — Server timestamps are never substituted for SDK timestamps.** The `timestamp` field in each event is set by the SDK at the moment of event construction. The ingestion service records its own `server_timestamp` separately (in the `CHAIN_SEAL` payload). These two timestamps serve different evidentiary purposes and must not be conflated.

---

## 3. Evidence Class Definitions

The evidence class of a session is a structured claim about the strength of the evidentiary guarantee the chain provides. It is determined by the verifier after all integrity checks pass and depends on which server-authority events are present.

### AUTHORITATIVE_EVIDENCE

A session achieves `AUTHORITATIVE_EVIDENCE` when: (1) all four integrity checks pass, (2) a `CHAIN_SEAL` event is present and its hash matches the chain's final hash, and (3) no `LOG_DROP` or `CHAIN_BROKEN` events are present in the chain.

This is the strongest evidence class. It means the ingestion service has independently verified the complete chain, no events were lost in transit, and the chain has not been broken at any point. Sessions with `AUTHORITATIVE_EVIDENCE` are suitable for use in legal and compliance contexts where completeness can be asserted.

### PARTIAL_AUTHORITATIVE_EVIDENCE

A session achieves `PARTIAL_AUTHORITATIVE_EVIDENCE` when: (1) all four integrity checks pass, (2) a `CHAIN_SEAL` is present, but (3) one or more `LOG_DROP` or `CHAIN_BROKEN` events are also present.

This class indicates that the ingestion service has verified the integrity of the events it received, but some events were lost before reaching the server (indicated by `LOG_DROP`) or a sequence gap was detected at ingestion time (indicated by `CHAIN_BROKEN`). The events that are present are cryptographically sound, but the record is known to be incomplete. The `LOG_DROP` payload specifies which sequence range was affected.

### NON_AUTHORITATIVE_EVIDENCE

A session achieves `NON_AUTHORITATIVE_EVIDENCE` when: (1) all four integrity checks pass, but (2) no `CHAIN_SEAL` event is present.

This is the evidence class produced by the SDK in `local_authority=True` mode, where events are written directly to a JSONL file without passing through the ingestion service. The chain is internally consistent and cryptographically sound, but no independent server-side verification has occurred. This class is appropriate for development, testing, and debugging. It is not suitable for compliance or legal use.

---

## 4. What CHAIN_SEAL Guarantees

The `CHAIN_SEAL` event, when present and valid, provides the following specific guarantees:

The ingestion service received every event in the chain from `seq = 1` through the event immediately preceding the seal. It independently recomputed the `event_hash` of each event using its own JCS implementation and confirmed that each `prev_hash` matched the preceding event's `event_hash`. It confirmed that the sequence was strictly monotonic and continuous. It wrote the events atomically — either all events in the batch were written, or none were. The `final_hash` in the `CHAIN_SEAL` payload is the server's independently computed hash of the last event before the seal, providing a cryptographic anchor for the entire chain.

---

## 5. What CHAIN_SEAL Does NOT Guarantee

`CHAIN_SEAL` does not guarantee that the session record is complete in the sense of capturing every event that occurred in the agent process. It guarantees only that the events the ingestion service received are intact. If the SDK dropped events due to buffer overflow before they reached the server, those events are permanently lost.

The presence of `LOG_DROP` events within a sealed chain is the evidence of this loss. The `LOG_DROP` payload records the range of sequence numbers that were dropped (`seq_range_start` through `seq_range_end`) and the count of dropped events. A sealed chain with `LOG_DROP` events is `PARTIAL_AUTHORITATIVE_EVIDENCE`, not `AUTHORITATIVE_EVIDENCE`. This distinction must be respected in any system that makes compliance assertions based on AgentOps Replay sessions.
