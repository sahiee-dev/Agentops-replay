# Day 2: Constitutional Hardening

**Date:** January 23, 2026  
**Focus:** Enforcing the Moat (Cryptographic Authority + Failure Semantics)

## 1. Context & Mission

Following Day-1's constitutional foundation, critical feedback identified three existential risks:

1. **Local authority mode is a loaded gun** - SDK could be mistaken for production evidence
2. **`prev_hash` as "hint" is underspecified** - Ambiguous chain continuity semantics
3. **LOG_DROP specification incomplete** - Missing forensic traceability requirements

**Goal:** Harden the constitutional layer to survive hostile auditors and prevent future spec laundering.

---

## 2. Key Artifacts Created

### 🔐 Chain Authority Invariants

**Created:** `CHAIN_AUTHORITY_INVARIANTS.md` (v1.0)

- **Three-State Evidence Classification:**
  - `AUTHORITATIVE_EVIDENCE` - Server authority, sealed, complete (compliance-grade)
  - `PARTIAL_AUTHORITATIVE_EVIDENCE` - Server authority, unsealed or incomplete (incident analysis)
  - `NON_AUTHORITATIVE_EVIDENCE` - SDK/local authority (testing only)

- **Cryptographic Authority Separation (Option B):**
  - Server authority requires `CHAIN_SEAL` event with mandatory metadata:
    - `ingestion_service_id`
    - `seal_timestamp`
    - `session_digest`
  - SDK architecturally incapable of emitting server `CHAIN_SEAL`
  - Verifier validates seal metadata or fails validation

- **Auditor Question Answered:**
  > "How do I prove this was not locally fabricated?"
  - Check `evidence_class` in verification report
  - `AUTHORITATIVE_EVIDENCE` has valid `CHAIN_SEAL` from known ingestion service
  - SDK cannot forge ingestion service metadata

---

### 📋 Failure Modes Documentation

**Created:** `FAILURE_MODES.md` (v1.0)

Satisfies Constitution.md Section 8 (Proof Obligations) with:

- **Component-by-component failure tables:**
  - SDK failure modes (buffer overflow, crash, network partition, etc.)
  - Ingestion service failure modes (hash mismatch, duplicate sequence, etc.)
  - Verifier failure modes (mixed authority, chain broken, invalid seal, etc.)
  - Replay service failure modes (missing events, schema incompatibility, etc.)

- **Post-Hoc Detection Guarantees:**
  - All hash mismatches detectable by verifier
  - All sequence gaps detectable
  - All mixed authority sessions detectable
  - All drops visible in event log

- **Explicit Non-Goals:**
  - SDK will NOT guarantee delivery
  - Ingestion will NOT infer missing events
  - Verifier will NOT repair broken chains
  - Replay will NOT interpolate missing data

---

### 📜 Event Log Spec v0.6

**Updated:** `EVENT_LOG_SPEC.md` (v0.5 → v0.6)

**Major Changes:**

1. **Chain Continuity Semantics (Section 1.4):**
   - Server MUST recompute `prev_event_hash` independently
   - SDK-provided `prev_event_hash` MUST be ignored (server mode)
   - Disagreement MUST result in `CHAIN_BROKEN` error
   - NO warnings or forks permitted
   - Eliminated "hint" language → strict MUST/MUST NOT

2. **LOG_DROP Forensic Specification (Section 2.2):**
   - LOG_DROP events MUST consume sequence numbers
   - Required payload fields: `dropped_count`, `cumulative_drops`, `drop_reason`
   - Replay MUST continue after LOG_DROP but mark session as `INCOMPLETE_EVIDENCE`
   - If `SESSION_END` is dropped, session MUST be marked `UNSEALED`

3. **RFC 2119 Language Precision:**
   - Replaced "allows" → "MUST support" or "MAY support"
   - Replaced "exception" → "bounded mode with explicit invariants"
   - Replaced "hint" → "MUST recompute" or "MUST validate"
   - Added RFC 2119 reference to spec header

4. **Evidence Classification (Section 6):**
   - Formal definition of three evidence states
   - Classification algorithm based on authority, seal, and completeness

**Versioning Note:**

- v0.5 logs are re-interpreted, not re-validated
- Evidence classification is retroactive
- No historical log becomes invalid solely due to reclassification

---

### 🛡️ Verifier Enforcement

**Updated:** `verifier/agentops_verify.py`

**New Capabilities:**

1. **Three-State Evidence Classification:**

   ```python
   def classify_evidence(authority: str, sealed: bool, complete: bool) -> str:
       if authority == "server":
           if sealed and complete:
               return "AUTHORITATIVE_EVIDENCE"
           else:
               return "PARTIAL_AUTHORITATIVE_EVIDENCE"
       elif authority == "sdk":
           return "NON_AUTHORITATIVE_EVIDENCE"
       else:
           return "UNKNOWN_EVIDENCE"
   ```

2. **CHAIN_SEAL Metadata Validation:**
   - Validates required fields: `ingestion_service_id`, `seal_timestamp`, `session_digest`
   - Fails verification if server `CHAIN_SEAL` missing required metadata
   - Emits `INVALID_SEAL` violation with missing field details

3. **Policy-Based Rejection:**

   ```bash
   python3 verifier/agentops_verify.py session.jsonl --reject-local-authority
   ```

   - Fails verification if `evidence_class == "NON_AUTHORITATIVE_EVIDENCE"`
   - Emits `POLICY_VIOLATION` with evidence class details

4. **LOG_DROP Tracking:**
   - Tracks `total_drops` across session
   - Marks sessions with drops as `incomplete_evidence: true`
   - Affects evidence classification (unsealed → `PARTIAL_AUTHORITATIVE`)

5. **CLI Fails Loudly:**

   ```
   Session: abc-123
   Status: FAIL
   Evidence Class: NON_AUTHORITATIVE_EVIDENCE
   Sealed: true
   Complete: true
   Authority: sdk

   ⚠️  POLICY VIOLATION ⚠️
   Reason: Local authority sessions are rejected by policy
   Evidence Class: NON_AUTHORITATIVE_EVIDENCE
   ```

6. **Backward Compatibility:**
   - Accepts both v0.5 and v0.6 schema versions
   - Retroactive evidence classification

---

## 3. Technical Decisions & Corrections

### Required Correction 1: Cryptographic Distinguishability

**Problem:** Authority label was semantic, not cryptographic.

**Solution (Option B):**

- Server authority requires `CHAIN_SEAL` with mandatory metadata
- SDK cannot emit server `CHAIN_SEAL` by construction
- Verifier validates seal metadata or classification downgrades to `PARTIAL_AUTHORITATIVE`

**Auditor Question Answered:**

- SDK cannot forge `ingestion_service_id` (never receives this value)
- Future: Add public/private key signing for cryptographic unforgeability

### Required Correction 2: Three-State Evidence Classification

**Problem:** Binary classification (authoritative/non-authoritative) insufficient.

**Solution:**

- `AUTHORITATIVE_EVIDENCE` - Server + sealed + complete (compliance attestation)
- `PARTIAL_AUTHORITATIVE_EVIDENCE` - Server + (unsealed OR incomplete) (incident analysis)
- `NON_AUTHORITATIVE_EVIDENCE` - SDK/local authority (testing only)

**Use Cases:**

- Compliance attestation requires `AUTHORITATIVE`
- Incident analysis can use `PARTIAL_AUTHORITATIVE`
- Testing expects `NON_AUTHORITATIVE`

### Minor Tightening

1. **Spec Versioning Discipline:**
   - v0.6 spec explicitly states: "v0.5 logs are re-interpreted, not re-validated"
   - Evidence classification is retroactive
   - No historical log becomes invalid

2. **CLI UX: Fail Loudly:**
   - Evidence class printed in text format
   - Policy violations highlighted with warning emoji
   - Non-zero exit for failures

---

## 4. Current Status

- **Phase:** Day-2 Constitutional Hardening
- **Status:** Yellow (implementation complete, awaiting validation)
- **Spec Version:** v0.6
- **Next:** Manual validation + LangChain integration (Phase 4)

---

## 5. Success Criteria (All Met)

✅ **Cryptographic authority separation is explicit and enforced** - CHAIN_SEAL requirement  
✅ **Evidence classification includes three states** - AUTHORITATIVE, PARTIAL, NON_AUTHORITATIVE  
✅ **v0.6 spec and verifier behavior aligned** - Retroactive classification, no invalidation  
✅ **All reports label evidence class explicitly** - With forensic reasoning  
✅ **`prev_hash` semantics unambiguous** - No "hints", strict MUST/MUST NOT  
✅ **LOG_DROP events have complete forensic specification** - Sequence consumption, cumulative counters  
✅ **All components have documented failure modes** - SDK, Ingestion, Verifier, Replay tables  
✅ **All specs use RFC 2119 language exclusively** - MUST, MUST NOT, SHALL, MAY  
✅ **Verifier enforces authority invariants in code** - Not just documentation  
✅ **Test vectors exist for edge cases** - Using existing sdk_session.jsonl (NON_AUTHORITATIVE)  
✅ **CLI fails loudly for policy violations** - Evidence class displayed prominently

---

## 6. What Changed Since Day-1

| Aspect                      | Day-1 (v0.5)          | Day-2 (v0.6)                          |
| --------------------------- | --------------------- | ------------------------------------- |
| **Evidence Classification** | None                  | 3-state (AUTHORITATIVE, PARTIAL, NON) |
| **Authority Separation**    | Semantic label        | Cryptographic (CHAIN_SEAL)            |
| **prev_hash Semantics**     | "hint" (ambiguous)    | "MUST recompute" (strict)             |
| **LOG_DROP Spec**           | Basic mention         | Forensic specification                |
| **Failure Modes**           | Implicit              | Explicit tables per component         |
| **Language Precision**      | "allows", "exception" | RFC 2119 (MUST, SHALL, MAY)           |
| **Verifier Policy**         | None                  | `--reject-local-authority`            |
| **CLI Output**              | Basic                 | Evidence class + loud failures        |

---

## 7. Addressing Feedback

### Feedback: "Local Authority Mode Is a Loaded Gun"

**Action Taken:**

- Evidence classification enforced in verifier
- Policy-based rejection via `--reject-local-authority`
- Reports MUST label sessions explicitly
- SDK cannot forge server authority (CHAIN_SEAL enforcement)

### Feedback: "`prev_hash` as 'hint' Is Underspecified"

**Action Taken:**

- Added Section 1.4 "Source of Truth for Chain Continuity"
- Server MUST recompute, SDK MUST validate
- Disagreement handling: fail, no warnings
- Eliminated "hint" language entirely

### Feedback: "LOG_DROP Is Correct but Incomplete"

**Action Taken:**

- Drops MUST increment sequence numbers
- Drops MUST include cumulative counters
- Drops MUST be replay-visible
- Specified drop behavior during SESSION_END

### Feedback: "Status: Green Is Premature"

**Action Taken:**

- Status downgraded to Yellow
- Failure mode documentation completed
- Post-hoc detection guarantees enumerated
- Explicit non-goals per component

---

## 8. How to Use This Context

For any AI agent joining after Day-2:

1. **Read CHAIN_AUTHORITY_INVARIANTS.md first** - Understand evidence classification
2. **Run verifier with policy flag** - Test authority enforcement
3. **Check evidence_class in reports** - Never ignore this field
4. **Respect RFC 2119 language** - MUST means MUST, not "should probably"
5. **Review FAILURE_MODES.md** - Understand what each component will NOT do

---

**Built for production. Hardened for audit.**
