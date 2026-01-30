# AgentOps Replay — Development Progress

> Continuous progress tracker for the AgentOps Replay project.  
> **Mission:** Become the system of record for AI agent behavior.

---

## Current Status

| Metric           | Value                   |
| ---------------- | ----------------------- |
| **Phase**        | Phase 7 — Replay System |
| **Spec Version** | v0.6                    |
| **Status**       | Completed               |
| **Last Updated** | January 29, 2026        |

---

## Completed Milestones

### ✅ Phase 1-2: Constitutional Foundation

**Date:** January 22, 2026

Established the immutable core — "The Moat"

**Artifacts Created:**

- [CONSTITUTION.md](CONSTITUTION.md) — Non-negotiable laws (Immutable Logs, Verifiable Evidence)
- [EVENT_LOG_SPEC.md](EVENT_LOG_SPEC.md) (v0.5) — Technical implementation with hash-chaining
- [SCHEMA.md](SCHEMA.md) — Event type definitions with field-level documentation
- [agentops_events.schema.json](agentops_events.schema.json) — JSON Schema for validation

**Key Decisions:**

- Rejected "move fast and break things" for cryptographic auditability
- Built verifier BEFORE SDK to grade own homework
- RFC 8785 (JCS) canonicalization with UTF-16BE sorting

---

### ✅ Phase 3: SDK Implementation

**Date:** January 22, 2026

**Artifacts Created:**

- `agentops_sdk/` — Python SDK (untrusted producer)
- `sdk/python/` — Production Python SDK
- `verifier/agentops_verify.py` — Reference verifier (zero-dependency)
- `verifier/jcs.py` — RFC 8785 canonicalization
- `verifier/test_vectors/` — Canonical valid/invalid test logs

**SDK Features:**

- Local authority mode (testing only)
- Ring buffer with `LOG_DROP` meta-events
- Strict types via Pydantic/dataclasses
- Vendored dependencies (standalone)

**Technical Fixes:**

- RFC 8785 compliance (UTF-16BE code unit sorting)
- Added `content_hash`, `args_hash`, `result_hash` for redaction
- Fixed Server Mode `prev_hash` tracking
- Buffer safety for `LOG_DROP` counters

---

### ✅ Phase 3.5: Constitutional Hardening

**Date:** January 23, 2026

Addressed three existential risks identified in feedback.

**Artifacts Created:**

- [CHAIN_AUTHORITY_INVARIANTS.md](CHAIN_AUTHORITY_INVARIANTS.md) (v1.0) — Evidence classification rules
- [FAILURE_MODES.md](FAILURE_MODES.md) (v1.0) — Component failure documentation
- [EVENT_LOG_SPEC.md](EVENT_LOG_SPEC.md) (v0.5 → v0.6) — Hardened specification

**Key Changes:**

| Aspect                  | Before (v0.5)         | After (v0.6)                          |
| ----------------------- | --------------------- | ------------------------------------- |
| Evidence Classification | None                  | 3-state (AUTHORITATIVE, PARTIAL, NON) |
| Authority Separation    | Semantic label        | Cryptographic (CHAIN_SEAL)            |
| `prev_hash` Semantics   | "hint" (ambiguous)    | "MUST recompute" (strict)             |
| LOG_DROP Spec           | Basic mention         | Forensic specification                |
| Failure Modes           | Implicit              | Explicit tables per component         |
| Language Precision      | "allows", "exception" | RFC 2119 (MUST, SHALL, MAY)           |

**Three-State Evidence Classification:**

- `AUTHORITATIVE_EVIDENCE` — Server authority, sealed, complete (compliance-grade)
- `PARTIAL_AUTHORITATIVE_EVIDENCE` — Server authority, unsealed/incomplete (incident analysis)
- `NON_AUTHORITATIVE_EVIDENCE` — SDK/local authority (testing only)

**Verifier Updates:**

- Evidence classification in output
- `--reject-local-authority` policy flag
- CHAIN_SEAL metadata validation
- LOG_DROP tracking with `total_drops`

---

### ✅ Phase 4: LangChain Integration

**Date:** January 24, 2026

**Artifacts Created:**

- `sdk/python/agentops_replay/integrations/langchain/` — LangChain integration package
- `sdk/python/agentops_replay/integrations/langchain/callback.py` — Callback handler
- `sdk/python/agentops_replay/integrations/langchain/version.py` — Version compatibility
- `examples/langchain_demo/` — Demo agent with verification workflow
- `examples/langchain_demo/INCIDENT_INVESTIGATION.md` — PII incident simulation

**Integration Features:**

- `AgentOpsCallbackHandler` extends LangChain's `BaseCallbackHandler`
- Captures: LLM calls, tool invocations, agent actions, errors
- Version pinning and compatibility warnings
- PII redaction with hash preservation
- Safe serialization of complex objects

**Demo Agent:**

- Customer support agent with tools: `lookup_order`, `issue_refund`, `send_email`
- Mock mode for testing without API keys
- Full verification workflow documented

**Validation Results:**

```
Session: 88f970ff-22d6-47fd-850f-01d4aed5140f
Status: PASS
Evidence Class: NON_AUTHORITATIVE_EVIDENCE
Sealed: True
Complete: True
Fingerprint: 4272bdc7...
```

---

## Upcoming Milestones

### ✅ Phase 5: Compliance Artifacts

**Date:** January 29, 2026

**Artifacts Created:**

- `backend/app/compliance/json_export.py` — RFC 8785 canonical JSON export (locked to verifier's JCS)
- `backend/app/compliance/pdf_export.py` — Human-readable PDF from verified JSON
- `backend/app/compliance/gdpr.py` — PII detection (WARNING) + redaction validation (ERROR)

**Key Changes:**

- [x] JSON export locked to verifier's JCS implementation
- [x] Strict ISO 8601 formatting (YYYY-MM-DDTHH:MM:SS.sssZ)
- [x] Explicit `evidence_class` field in export header
- [x] PDF consumes verified JSON, not raw DB
- [x] GDPR severity levels (ERROR/WARNING)

---

### ✅ Phase 6: Ingestion Service (Core)

**Date:** January 29, 2026

**Artifacts Created:**

- `backend/app/services/ingestion/hasher.py` — Server-side hash recomputation
- `backend/app/services/ingestion/sealer.py` — Chain sealing with authority invariants

**Key Changes:**

- [x] Server-side hash recomputation (never trust SDK)
- [x] Rejection invariants: non-monotonic, gaps, duplicates
- [x] CHAIN_SEAL emission logic
- [x] No re-sealing invariant
- [x] PARTIAL_AUTHORITATIVE for incomplete chains

**Tests:**

- `backend/tests/compliance/test_jcs_canonicalization.py` — Adversarial whitespace test

---

### ⏳ Phase 6: Remaining Work

**Requirements:**

- [ ] Ingestion service HTTP endpoints (FastAPI)
- [ ] Immutable event store (PostgreSQL + append-only)
- [ ] Atomic batch commits
- [ ] Queue worker integration

### ✅ Phase 7: Replay System

**Date:** January 29, 2026

**Artifacts Created:**

- `backend/app/replay/` — Core replay package
- `backend/app/replay/frames.py` — Frame types with single-origin invariant
- `backend/app/replay/warnings.py` — Warning system with stable codes
- `backend/app/replay/engine.py` — Verified-first replay engine
- `backend/app/schemas/replay_v2.py` — Pydantic response models

**Key Changes:**

- [x] Verified-first: Replay only serves verified chains
- [x] Frame-based: EVENT, GAP, LOG_DROP, REDACTION types
- [x] VerificationStatus as enum (not string)
- [x] Single-origin frame invariant enforced
- [x] No-bypass constraint on frame endpoint
- [x] Explicit gap marking (no smoothing)
- [x] Anti-inference: No synthetic events

**Tests:**

- `backend/tests/replay/test_replay_engine.py` — All 5 core tests passing

---

## Architecture Overview

```
Agent SDK (Untrusted)
    |
    |  (batched events)
    v
Ingestion Service (Authoritative) ---> Queue
    |                                    |
    v                                    v
Append-only Event Store           Policy Engine
    |                                    |
    v                                    v
Replay API                        Violation Store
    |
    v
Compliance Export (JSON/PDF)
```

**Trust Boundaries:**

- SDK → Ingestion: **UNTRUSTED**
- Ingestion → Store: **AUTHORITATIVE**
- Store → Verifier: **VERIFIED**
- Store → Replay: **AUTHORITATIVE**

---

## Key Documents

| Document                                                       | Purpose                              |
| -------------------------------------------------------------- | ------------------------------------ |
| [agentops_prd_v2.md](agentops_prd_v2.md)                       | Product Requirements (authoritative) |
| [goal.md](goal.md)                                             | Win-or-Die Execution Plan            |
| [CONSTITUTION.md](CONSTITUTION.md)                             | Inviolable system rules              |
| [EVENT_LOG_SPEC.md](EVENT_LOG_SPEC.md)                         | Technical specification (v0.6)       |
| [CHAIN_AUTHORITY_INVARIANTS.md](CHAIN_AUTHORITY_INVARIANTS.md) | Evidence classification              |
| [FAILURE_MODES.md](FAILURE_MODES.md)                           | Component failure tables             |
| [SCHEMA.md](SCHEMA.md)                                         | Event type definitions               |

---

## Success Criteria (v1.0 Launch)

From PRD:

1. ✅ Verifier passes 100% of adversarial tests
2. [ ] System survives simulated network partition
3. [ ] Compliance export accepted by legal team
4. [ ] Security audit complete (internal)
5. [ ] Incident response playbook validated
6. [ ] Reference deployment on production agent (internal)

**Blockers:** Any verifier bug, any silent data loss, any chain repair.

---

## Notes

### Principles

- **Constitution-First:** All features start with constitutional review
- **Verifier-Driven:** Implementation follows verifier specification
- **Fail Loudly:** Never silently lose evidence
- **Evidence > Interpretation:** Record facts, not narratives

### What Kills This

- Overbuilding
- Vague language
- Logging "thoughts" (Legal blocker)
- Trying to impress Twitter instead of security teams

---

_Built for production. Designed for trust._
