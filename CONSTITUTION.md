# CONSTITUTION.md (v0.1)

## 1. Purpose (Non-Negotiable)

AgentOps Replay exists to be:

> **The system of record for AI agent behavior.**

This system prioritizes:

- **Auditability** over convenience
- **Correctness** over performance
- **Evidence** over interpretation

Any feature that compromises these priorities is rejected.

## 2. Core Invariants (These Must Never Break)

### 2.1 Event Immutability

- Once an event is accepted, it can never be modified or deleted.
- Corrections must be represented as new events, never mutations.

### 2.2 Total Ordering

- Every event in a session has a deterministic position.
- Missing or duplicated sequence numbers are detectable.

### 2.3 Tamper Evidence

- Events are cryptographically linked.
- Any modification invalidates the session digest.

### 2.4 Replay Determinism

- Given the same event stream, replay output must be identical.
- UI differences must not affect semantic interpretation.

## 3. Explicit Non-Goals (Hard No)

The system will not:

- Infer intent
- Judge correctness of decisions
- Optimize prompts
- Store chain-of-thought by default
- Claim compliance certification

These are out of scope permanently unless the Constitution is amended.

## 4. Trust Boundaries (Critical)

- The **SDK** is untrusted
- The **ingestion service** is trusted but verify
- **Storage** is append-only
- **Replay** is read-only
- **Reports** are evidence, not guarantees

Any AI agent generating code must respect these trust boundaries.

## 5. Failure Semantics (Most AI Systems Ignore This)

If the system fails:

- It must **fail open** for agents (agents continue running)
- It must **fail closed** for integrity (no partial writes)
- It must **never** invent or reorder events
- Data loss is acceptable. Data corruption is not.

## 6. What Is Allowed to Change

- UI
- SDK ergonomics
- Performance optimizations
- Storage backend

## 7. What Is Frozen Forever

- Event semantics
- Ordering guarantees
- Immutability model
- Meaning of "replay"
- Meaning of "evidence"

Changing these requires a major version + migration document.

## 8. Proof Obligations

For every major component, there must exist:

- A written list of assumptions
- A list of failure modes
- A way to detect violations post hoc

If an AI agent cannot produce these, the component is invalid.
