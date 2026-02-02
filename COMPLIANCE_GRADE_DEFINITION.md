# COMPLIANCE_GRADE_DEFINITION.md (v1.0)

## Purpose

This document explicitly locks the meaning of "compliance-grade" evidence to prevent future marketing or product erosion of the term.

---

## Definition

**Compliance-grade evidence** is defined as:

> **AUTHORITATIVE_EVIDENCE produced under Event Log Specification v0.6+ with valid CHAIN_SEAL.**

---

## Requirements

For a session to be classified as compliance-grade, ALL of the following MUST be true:

1. **Server Authority:**
   - `chain_authority = "server"` for ALL events in session

2. **Valid CHAIN_SEAL:**
   - Session contains `CHAIN_SEAL` event
   - CHAIN_SEAL has required metadata:
     - `ingestion_service_id` (matches known ingestion service)
     - `seal_timestamp` (server-authoritative timestamp)
     - `session_digest` (final chain hash)
   - v1.0+: CHAIN_SEAL has valid cryptographic signature

3. **Complete Session:**
   - Session has `SESSION_END` event
   - No sequence gaps
   - No `LOG_DROP` events (zero cumulative drops)

4. **Chain Integrity:**
   - All payload hashes valid
   - All event hashes valid
   - `prev_event_hash` chain unbroken
   - Verifier status: `PASS`

5. **Spec Compliance:**
   - `schema_ver >= "v0.6"`
   - All events conform to EVENT_LOG_SPEC.md

---

## Evidence Classification Mapping

| Evidence Class                     | Compliance-Grade? | Use Case                                                     |
| ---------------------------------- | ----------------- | ------------------------------------------------------------ |
| **AUTHORITATIVE_EVIDENCE**         | ✅ Yes            | Regulatory reporting, compliance attestation, legal evidence |
| **PARTIAL_AUTHORITATIVE_EVIDENCE** | ❌ No             | Incident analysis, debugging, operational forensics          |
| **NON_AUTHORITATIVE_EVIDENCE**     | ❌ No             | Testing, development, local validation                       |

---

## What Is NOT Compliance-Grade

The following are explicitly **NOT** compliance-grade, regardless of how complete or correct they appear:

❌ **Unsealed Sessions:**

- Server authority but missing CHAIN_SEAL
- Classification: `PARTIAL_AUTHORITATIVE_EVIDENCE`
- Use case: Incident analysis only

❌ **Sessions with Data Loss:**

- Server authority with CHAIN_SEAL
- Contains `LOG_DROP` events (any cumulative drops > 0)
- Classification: `PARTIAL_AUTHORITATIVE_EVIDENCE`
- Use case: Partial evidence for incidents

❌ **Incomplete Sessions:**

- Missing `SESSION_END`
- Classification: `PARTIAL_AUTHORITATIVE_EVIDENCE`
- Use case: Crash analysis, interrupted sessions

❌ **SDK/Local Authority:**

- `chain_authority = "sdk"` (regardless of completeness)
- Classification: `NON_AUTHORITATIVE_EVIDENCE`
- Use case: Testing and development only

❌ **Mixed Authority:**

- Session with both `"server"` and `"sdk"` events
- Classification: INVALID (verification fails)
- Use case: None (configuration error)

---

## Verifier Output

Compliance-grade sessions produce:

```json
{
  "session_id": "...",
  "status": "PASS",
  "evidence_class": "AUTHORITATIVE_EVIDENCE",
  "authority": "server",
  "sealed": true,
  "complete": true,
  "total_drops": 0,
  "partial_reasons": [],
  "replay_fingerprint": "sha256:..."
}
```

**Critical Fields:**

- `evidence_class == "AUTHORITATIVE_EVIDENCE"` (required)
- `sealed == true` (required)
- `complete == true` (required)
- `total_drops == 0` (required)
- `partial_reasons == []` (empty, no degradation)

---

## Policy Enforcement

### Automated Filtering

```bash
# Accept only compliance-grade evidence
python3 verifier/agentops_verify.py session.jsonl \
  --require-authoritative \
  --format json
```

Future flag (not yet implemented):

- `--require-authoritative`: Fail verification if evidence_class != AUTHORITATIVE_EVIDENCE

### Programmatic Check

```python
import json

report = json.load(open("verification_report.json"))

if report["evidence_class"] == "AUTHORITATIVE_EVIDENCE":
    print("✅ Compliance-grade evidence")
else:
    print(f"❌ Not compliance-grade: {report['evidence_class']}")
    print(f"   Reasons: {report.get('partial_reasons', [])}")
```

---

## Marketing and Product Constraints

### What Product Teams MAY Say

✅ "AgentOps Replay provides compliance-grade evidence for AI agents"  
✅ "Server-authoritative sessions with cryptographic seals are compliance-grade"  
✅ "Unsealed or incomplete sessions are suitable for incident analysis, not compliance attestation"

### What Product Teams MUST NOT Say

❌ "All AgentOps sessions are compliance-grade"  
❌ "PARTIAL_AUTHORITATIVE_EVIDENCE is good enough for compliance"  
❌ "Local authority mode can be used in production for compliance"  
❌ "Compliance-grade evidence is anything that passes verification"

**Rationale:**  
Weakening the definition undermines trust and creates legal liability. The term "compliance-grade" is **frozen** and **non-negotiable**.

---

## Regulatory Mapping

### SOC 2

- **Requirement:** Audit trail of system changes
- **Mapping:** AUTHORITATIVE_EVIDENCE provides tamper-evident audit trail
- **Acceptable:** Server authority with CHAIN_SEAL
- **Not Acceptable:** PARTIAL_AUTHORITATIVE (unsealed) or NON_AUTHORITATIVE (local)

### GDPR Article 5(2) (Accountability)

- **Requirement:** Demonstrate compliance with data processing principles
- **Mapping:** AUTHORITATIVE_EVIDENCE provides verifiable processing logs
- **Acceptable:** Sealed, complete sessions showing data access and transformations
- **Not Acceptable:** Sessions with LOG_DROP (data loss) or incomplete records

### HIPAA (45 CFR § 164.312(b))

- **Requirement:** Audit controls to record and examine activity
- **Mapping:** AUTHORITATIVE_EVIDENCE provides immutable audit logs
- **Acceptable:** Cryptographically sealed event logs with complete chain
- **Not Acceptable:** SDK/local authority (unverified source)

---

## Future Evolution

### Strengthening (Allowed)

✅ Adding cryptographic signatures (v1.0+)  
✅ Requiring stronger metadata validation  
✅ Adding post-quantum resistant algorithms

**Principle:** Tightening requirements strengthens guarantee, does not invalidate definition.

### Weakening (Forbidden)

❌ Accepting unsealed sessions as compliance-grade  
❌ Allowing LOG_DROP events in compliance-grade sessions  
❌ Reclassifying PARTIAL_AUTHORITATIVE as compliance-grade

**Principle:** Weakening definition breaks trust and creates retroactive liability.

---

## Auditor Talking Points

**Question:** "What makes your evidence compliance-grade?"

**Answer:**

- "Server-authoritative sessions with cryptographic seals"
- "Complete chain integrity (no gaps, no drops)"
- "Independent verifier validation"
- "Explicit classification in verification reports"

**Question:** "Can dev/test logs be used for compliance?"

**Answer:**

- "No. SDK/local authority is explicitly NON_AUTHORITATIVE_EVIDENCE"
- "Compliance requires server authority with valid CHAIN_SEAL"
- "Development logs are suitable for testing, not attestation"

**Question:** "What if a session is 99% complete but missing one event?"

**Answer:**

- "Not compliance-grade. Evidence classification: PARTIAL_AUTHORITATIVE_EVIDENCE"
- "Suitable for incident analysis, not compliance attestation"
- "All-or-nothing: completeness is binary, not probabilistic"

---

## Commitment

AgentOps Replay **will not** weaken the definition of "compliance-grade" for convenience, adoption, or marketing.

This definition is **frozen** and protected by the Constitutional layer.

---

**Status:** FROZEN (v1.0)  
**Effective:** Event Log Spec v0.6+  
**Protected By:** CONSTITUTION.md Section 2 (Core Invariants)
