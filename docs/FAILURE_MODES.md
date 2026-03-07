# FAILURE_MODES.md (v1.0)

> **Classification: AUTHORITATIVE.**
> **Required by CONSTITUTION.md §5.1: Every major component must carry a Failure Mode Catalog.**

---

## 1. Purpose

This document enumerates every known failure mode for each major component, the expected system behavior, the invariant impacted, and the post-hoc detection mechanism.

---

## 2. SDK (Untrusted Producer)

| #   | Failure Mode                | Expected Behavior                             | Invariant Impacted                 | Detection Mechanism                                        |
| --- | --------------------------- | --------------------------------------------- | ---------------------------------- | ---------------------------------------------------------- |
| S1  | Buffer overflow             | Emit `LOG_DROP` event, continue recording     | §2.2 Total Ordering                | `LOG_DROP` events present in chain                         |
| S2  | Network partition           | Buffer locally, retry with backoff            | §4.1 Fail open for agent           | Events arrive late but ordered; `LOG_DROP` if buffer fills |
| S3  | Kill switch activated       | SDK silently stops recording                  | §1.3 Non-goal: SDK may be disabled | No events emitted; detectable by session gap               |
| S4  | Host application crash      | Incomplete session, no `SESSION_END`          | §2.1 Immutability (partial chain)  | Missing `SESSION_END` → `PARTIAL_AUTHORITATIVE_EVIDENCE`   |
| S5  | SDK emits `CHAIN_SEAL`      | Ingestion service MUST reject the batch       | §3.1 Trust: SDK is untrusted       | Verifier detects mixed authority                           |
| S6  | Malformed event payload     | Ingestion rejects at schema validation        | §3.3 SDK boundary                  | HTTP 422 response, event not persisted                     |
| S7  | PII in payload (unredacted) | Policy engine flags as violation post-persist | §10.2 PRD: Redaction               | `GDPR_PII_DETECTED` violation record                       |

---

## 3. Ingestion Service (Authoritative)

| #   | Failure Mode                   | Expected Behavior                        | Invariant Impacted             | Detection Mechanism                                                    |
| --- | ------------------------------ | ---------------------------------------- | ------------------------------ | ---------------------------------------------------------------------- |
| I1  | Sequence gap in batch          | Reject entire batch, emit `CHAIN_BROKEN` | §2.2 Total Ordering            | HTTP 400/409 response, no events persisted                             |
| I2  | Hash mismatch (SDK vs server)  | Ignore SDK hash, recompute server-side   | §2.3 Tamper Evidence           | Server recomputes; mismatch is logged but not fatal (SDK is untrusted) |
| I3  | Duplicate sequence number      | Reject batch (possible replay attack)    | §2.2 Total Ordering            | HTTP 409, security alert                                               |
| I4  | Database write failure         | Reject batch, return retriable error     | §4.2 No partial writes         | HTTP 503, batch not committed                                          |
| I5  | Mixed authority in batch       | Reject entire batch                      | §3.1 Trust hierarchy           | HTTP 400, `MIXED_AUTHORITY` violation                                  |
| I6  | Redis unavailable (async path) | Return HTTP 503, batch not queued        | §4.1 Fail closed for integrity | HTTP 503 response                                                      |

---

## 4. Worker (Queue Consumer)

| #   | Failure Mode                | Expected Behavior                          | Invariant Impacted      | Detection Mechanism                               |
| --- | --------------------------- | ------------------------------------------ | ----------------------- | ------------------------------------------------- |
| W1  | Worker crash mid-processing | Message not ACKed → redelivered on restart | §4.2 Atomic commits     | Pending message count in Redis consumer group     |
| W2  | Database unavailable        | NACK message, retry with backoff           | §4.2 No partial writes  | Retry counter in Redis message metadata           |
| W3  | Max retries exceeded        | Move to Dead Letter Queue                  | §4.1 Fail closed        | DLQ length > 0, monitoring alert                  |
| W4  | Deserialization failure     | Move to DLQ immediately (non-retriable)    | §4.2 No ambiguous state | DLQ entry with `reason: "deserialization_failed"` |
| W5  | Policy evaluation exception | ROLLBACK event batch, NACK, retry          | §POLICY_SEMANTICS §4.2  | Retry counter; DLQ after max retries              |
| W6  | Violation persistence fails | ROLLBACK event batch, NACK, retry          | §POLICY_SEMANTICS §4.2  | Same as W5                                        |

---

## 5. Policy Engine (Derived)

| #   | Failure Mode                    | Expected Behavior                        | Invariant Impacted     | Detection Mechanism                             |
| --- | ------------------------------- | ---------------------------------------- | ---------------------- | ----------------------------------------------- |
| P1  | Policy config missing           | Worker refuses to start                  | §POLICY_SEMANTICS §4.3 | Worker startup failure log                      |
| P2  | Policy config corrupt           | Worker refuses to start                  | §POLICY_SEMANTICS §4.3 | Worker startup failure log                      |
| P3  | Policy rule raises exception    | Batch rollback, retry                    | §POLICY_SEMANTICS §4.2 | Worker retry counter, DLQ                       |
| P4  | Policy version mismatch         | Log warning, use loaded version          | §POLICY_SEMANTICS §5.1 | `policy_version` in violation records           |
| P5  | Non-deterministic policy output | Constitutional violation — DEFECT        | §POLICY_SEMANTICS §3.3 | Re-run evaluation on same batch, compare output |
| P6  | Policy attempts event mutation  | Type system prevents (events are frozen) | §2.1 Immutability      | Code review + frozen dataclass enforcement      |

---

## 6. Replay Engine (Read-Only)

| #   | Failure Mode                | Expected Behavior                         | Invariant Impacted      | Detection Mechanism                          |
| --- | --------------------------- | ----------------------------------------- | ----------------------- | -------------------------------------------- |
| R1  | Missing events in chain     | Display GAP frame with warning            | §2.4 Replay Determinism | `LOG_DROP` or sequence gap visible in output |
| R2  | Hash verification failure   | Return error, do not serve replay         | §2.3 Tamper Evidence    | HTTP 500 with `INTEGRITY_VIOLATION` code     |
| R3  | Incomplete session (no end) | Render with `PARTIAL_AUTHORITATIVE` badge | §2.4 Replay Determinism | Evidence class in response metadata          |

---

## 7. Verifier (System Arbiter)

| #   | Failure Mode           | Expected Behavior                            | Invariant Impacted           | Detection Mechanism      |
| --- | ---------------------- | -------------------------------------------- | ---------------------------- | ------------------------ |
| V1  | Hash chain broken      | Exit 1, output violation list                | §2.3 Tamper Evidence         | Non-zero exit code       |
| V2  | Missing `CHAIN_SEAL`   | Classify as `NON_AUTHORITATIVE` or `PARTIAL` | §8.2 Evidence classification | Evidence class in output |
| V3  | Schema version unknown | Reject with `SCHEMA_VERSION_MISMATCH`        | §EVENT_LOG_SPEC §1           | Violation in output      |
| V4  | Corrupted input file   | Exit 1 with `LOAD_ERROR`                     | N/A (pre-verification)       | Non-zero exit code       |

---

## 8. Cross-Component: Verifier ↔ Ingestion Cross-Check

**Before v1.0 release:**

Any event chain produced by the Ingestion Service MUST pass `agentops-verify` without violations. If the Ingestion Service emits output that the Verifier rejects, **the system has forked the truth** and the release is blocked.

**Detection:** Run `agentops-verify` on every server-exported JSONL as part of CI.

---

_FAILURE_MODES.md v1.0 — Required by CONSTITUTION.md §5.1._
