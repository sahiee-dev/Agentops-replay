# Goals: Post-Launch Deep Hardening

**Date:** February 03, 2026
**Theme:** "Undeniable Forward Progress" (Auditability & Determinism)

> **The Bar for Today:**
> Today is **not** about polishing. It counts as a win **only if** we enforce a new invariant, explicate an implicit guarantee, or make the system objectively harder to break.

---

## 🎯 Primary Goal: Lock Down Verifier Integrity (Adversarial)

**Objective:** Lock down the Verifier against subtle adversarial attacks targeting sequence gaps and redaction ambiguity.

**Selected Threat:**

- **Scenario:** An attacker submits a chain with subtle sequence gaps or malformed redaction markers to hide malicious activity.
- **Risk:** The verifier might misclassify these as benign data issues rather than active tampering.

**Definition of Done:**

1.  **Threat Described:** Clearly documented in `EVIDENCE_CLASSIFICATION_SPEC.md`. (DONE)
2.  **Invariant Stated:** "Any sequence gap MUST result in a specific failure mode." (DONE)
3.  **Code Enforces It:** `verifier.py` updated to strictly classify these edge cases. (DONE)
4.  **Test Proves It:** New adversarial test vectors (`agentops_verify/test_adversarial.py`) pass. (DONE)

---

## 🚀 Secondary Goals

### 1. Verifier Hardening (Evidence > Code)

- **Task:** Add **2 new adversarial test vectors**.
  - Target: Ordering / Gaps / Sealing Semantics.
  - Target: Redaction + Hash Integrity.
- **Outcome:** Verifier failure modes become predictable and boring.

### 2. Spec Tightening (Zero Ambiguity)

- **Task:** Identify one ambiguous paragraph in `EVENT_LOG_SPEC.md` or `PRODUCTION_INGESTION_CONTRACT.md`.
- **Action:** Surgical rewrite to remove interpretation room.

### 3. Adoption Without Weakening Guarantees

- **Task:** Improve `reference_demo` or add "Cold Start" note.
- **Outcome:** Integration in <10 minutes without added flexibility.

---

## 🚫 Out of Scope

- New integrations
- UI / Dashboards
- Performance optimizations
- "Nice to have" refactors

---

## ✅ Previous Goals: V1 Launch Readiness (LOCKED)

**Date:** February 01, 2026
**Status:** COMPLETE (See below)

### 🔒 Goal 1: Spec-Lock Failure Semantics [x]

- [x] Ordering defined.
- [x] Hashing rules explicit.
- [x] Verifier handling specified.

### 📉 Goal 2: Demote PDF Artifact [x]

- [x] Spec states PDF is non-authoritative.
- [x] logic is deterministic.

### 🔁 Goal 3: Prove Replay Determinism [x]

- [x] Test created and passing.

### 🌍 Goal 4: External "Cold Start" Verification [x]

- [x] `COLD_START_VERIFICATION.md` created.
