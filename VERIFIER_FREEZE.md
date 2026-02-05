# VERIFIER FREEZE DECLARATION

> **Status**: FROZEN
> **Since**: 2026-02-04
> **Authority**: Constitutional

## 1. The Freeze

The core semantics of `agentops_verify` are hereby **frozen**.
This module is no longer "software" that evolves; it is **infrastructure** that endures.

## 2. Immutable Semantics

The following behaviors must NEVER change without a formal spec version bump (e.g., v1 -> v2):

- **Canonicalization (JCS)**: The exact byte-for-byte output of `jcs.canonicalize`.
- **Hash Algorithm**: SHA-256 must remain the sole hashing primitive.
- **Chain Logic**: The `prev_event_hash` linkage rules are absolute.
- **Authority Policy**: The definition of a "trusted authority" (must match `chain_authority` field).
- **Failure Modes**: A failure condition today must remain a failure condition forever. **Loosening checks is forbidden.**

## 3. Contribution Rules

Any changes to `verifier/` or `agentops_verify/` must adhere to these strict constraints:

1.  **No New Flags**: Do not add runtime toggles that alter verification logic.
2.  **No New Dependencies**: The verifier must remain zero-dependency (standard library only).
3.  **Behavior-Preserving Only**: Bug fixes are allowed ONLY if they align the code with the existing `EVENT_LOG_SPEC.md`.
    - If the code disagrees with the spec, the **spec wins**.
    - If the spec is ambiguous, the **most restrictive interpretation wins**.
4.  **No "Convenience" Features**: The verifier is not for user experience; it is for evidence integrity.

## 4. Regression Guards

The file `verifier/test_vectors/valid_session.jsonl` is a **Constitutional Artifact**.

- It must ALWAYS verify as `PASS`.
- Its calculated hashes (`first_event_hash`, `final_event_hash`) must NEVER change.
- Any code change that alters the verification result of this file is **rejected by definition**.

## 5. Violation Consequences

Breaking this freeze is not a "bug"; it is a **breach of the system's core promise**.
Such changes effectively fork the chain of evidence and invalidate all prior logs.

---

**Signed**,
_The AgentOps Replay Maintainers_
