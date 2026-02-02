# Reference Deployment Contract

**Status**: IMMUTABLE
**Version**: 1.0.0
**Enforcement**: STRICT

This document defines the **only** supported configuration for a production AgentOps Replay deployment. Any deviation from this spec renders the system **unsupported** and **audit-unsafe**.

## 1. Supported Runtime Environment

- **Language Runtime**: Python 3.11 (Explicitly Pinned)
  - _Rationale_: Determinism guarantees rely on Python 3.11 dictionary ordering and async task scheduling behaviors.
  - _Rejected_: Python 3.12+ (Scheduling changes), Python <3.11.
- **OS Architecture**: Linux `x86_64` or `arm64` (Dockerized)
- **Database**: PostgreSQL 15+ (Required for JSONB strictness)

## 2. Required System Components

A valid deployment MUST consist of these four isolated components:

1.  **Agent SDK (Untrusted)**
    - Embeds in the user agent.
    - **Role**: Emits events.
    - **Constraint**: NEVER trusted by the Ingestion service.

2.  **Ingestion Service (Authoritative Write)**
    - Receives raw event streams.
    - **Role**: Validates schema, timestamps, and causal chains.
    - **Constraint**: Must reject invalid payloads immediately (400 Bad Request). Never "fix" bad data.

3.  **The Verifier (The Gate)**
    - Runs in a separate security context.
    - **Role**: Cryptographically verifies chain seals and session integrity.
    - **Constraint**: A session is **NOT** evidence until the Verifier outputs `PASS`.

4.  **Replay API (Read Model)**
    - Queries the specific session state.
    - **Role**: Reproduces the exact state from the event log.
    - **Constraint**: Read-only. Side effects mocked by default.

### Verifier Supremacy (Hard Invariant)

- Replay APIs MUST refuse to serve sessions that have not passed verification.
- Compliance exports (JSON/PDF) MUST ONLY be generated from verified sessions.
- Any system that allows interaction with unverified sessions MUST mark them as `UNVERIFIED` and prohibit their use as evidence.

## 3. Trust Boundaries

| Component                             | Trust Level       | Security Responsibility                                                                            |
| :------------------------------------ | :---------------- | :------------------------------------------------------------------------------------------------- |
| **User Agent / SDK**                  | **UNTRUSTED**     | Can lie, drop packets, or crash. System must survive malicious inputs.                             |
| **Ingestion API**                     | **HIGH**          | Sanitizes inputs, enforces schema. The "front door."                                               |
| **Database**                          | **MEDIUM**        | Append-only store; integrity NOT trusted without verification, treated as potentially compromised. |
| **Verifier**                          | **MAXIMUM**       | The only component allowed to certify a session as "True".                                         |
| **Replay Engine (Pre-Verification)**  | **FORBIDDEN**     | Allowed only for debugging with explicit NON-EVIDENCE labeling.                                    |
| **Replay Engine (Post-Verification)** | **AUTHORITATIVE** | Authoritative Read Model. Input: Verified event chains only.                                       |

## 4. Operational strictness

### A. No Inference

The system **shall not** infer missing data.

- If a tool output is missing → **FAIL**.
- If a timestamp is ambiguous → **REJECT**.

### B. No Mutation

Once ingested, a session is **IMMUTABLE**.

- No "fixing" logs post-facto.
- No "re-ordering" events.

### C. No Backfill

Late-arriving events MUST be rejected, not merged. This prevents ingestion "optimizations" from breaking ordering guarantees.

### D. No Side Effects

Replay must be **HERMETIC**.

- Network calls: **MOCKED** (via recorded outputs).
- Randomness: **SEEDED** (if captured) or **DETERMINISTIC**.
- Dates/Times: **FROZEN** to recorded timestamps.

## 5. Out of Scope

The following are explicitly **NOT** guaranteed by this deployment contract:

- Replaying side effects (e.g., actually charging a credit card again).
- Correctness of the _Agent's_ logic (we only guarantee we recorded what it did).
- Real-time latency limits (Correctness > Speed).
