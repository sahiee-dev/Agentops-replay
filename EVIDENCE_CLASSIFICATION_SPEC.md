# Evidence Classification Specification

**Status**: IMMUTABLE
**Version**: 1.0.0
**Enforcement**: MANDATORY
**Audience**: Legal, Compliance, Security, Regulators

This document defines the formal classification of evidence produced by AgentOps Replay.

## 1. Purpose

Evidence classification answers:

> **"What does this evidence mean, and where can it be used?"**

Classification is:

- **Machine-derived** (not human-assigned)
- **Immutable** (cannot be upgraded after verification)
- **Non-arguable** (deterministic from verification findings)

## 2. Evidence Classes

### Class A: AUTHORITATIVE

**Definition**: Fully sealed, verified, complete, policy-attested evidence.

**Requirements (ALL must be true)**:

- Verification Status: `PASS`
- Chain Authority: Trusted (`agentops-ingest-v*`)
- Sequence: Contiguous (no gaps)
- LOG_DROP events: ZERO
- Redaction: Declared (`verification_mode: REDACTED` or `FULL`)

**Use Cases**:

- Court proceedings
- Regulatory submissions
- External audits
- Insurance claims
- Legal discovery

**Trust Level**: MAXIMUM

---

### Class B: DEGRADED

**Definition**: Verified integrity but incomplete evidence.

**Requirements**:

- Verification Status: `DEGRADED`
- Chain Authority: Trusted
- One or more of:
  - LOG_DROP events present
  - Sequence gaps detected and logged
  - Partial session (SESSION_END missing)

**Use Cases**:

- Internal audits
- Incident investigation
- Forensic analysis
- Compliance self-assessment

**Trust Level**: HIGH (with caveats)

**Mandatory Disclosure**:
When presenting Class B evidence, the following MUST be disclosed:

- Number of LOG_DROP events
- Total dropped event count
- Gap locations (sequence numbers)

---

### Class C: NON-AUTHORITATIVE

**Definition**: Evidence with integrity issues that cannot be trusted.

**Requirements (ANY triggers Class C)**:

- Verification Status: `FAIL`
- Chain break detected
- Hash mismatch detected
- Unknown/untrusted authority
- Payload tampering detected
- **Sequence Gap / Duplication**: Any deviation from strict 0-indexed incrementing sequence.

**Use Cases**:

- Engineering debugging ONLY
- **MUST NOT** be used for audit, compliance, or incident reconstruction.
- Not presentable to third parties

**Trust Level**: NONE

**Mandatory Action**:
Class C evidence MUST trigger:

- Incident investigation
- Root cause analysis
- Potential breach notification (if tampering suspected)

---

## 3. Classification Algorithm

```
function classify(report: VerificationReport) -> EvidenceClass:
    # Normalize PASS with degradation indicators to DEGRADED
    normalized_status = report.status
    if report.status == PASS:
        if has_log_drops(report) or has_gaps(report):
            normalized_status = DEGRADED

    # Classify based on normalized status
    if normalized_status == FAIL:
        return CLASS_C

    if normalized_status == DEGRADED:
        return CLASS_B

    # PASS with no degradation indicators
    return CLASS_A
```

Classification is **deterministic** and **derived**, not asserted.

---

## 4. Policy Attestation (Extension Point)

Evidence classification can be extended with **Policy Attestation**.

### What is Policy Attestation?

A declaration that the evidence meets specific external requirements:

- GDPR compliance (PII properly redacted)
- SOC 2 control coverage
- Internal policy XYZ adherence
- Sector-specific regulations (HIPAA, FINRA, etc.)

### Attestation Structure

```json
{
  "policy_id": "gdpr-pii-redaction-v1",
  "attested": true,
  "attestation_time": "2023-10-01T12:00:00Z",
  "attestor": "agentops-verify-v1",
  "evidence_requirements": [
    "All PII fields contain [REDACTED]",
    "Redaction occurred before hashing"
  ],
  "finding_count": 0
}
```

### Attestation Rules

1. **Attestation does not upgrade class**
   - Class C with attestation is still Class C
   - Class B with attestation is still Class B

2. **Attestation is additive metadata**
   - Stored alongside verification report
   - Does not modify sealed evidence

3. **Attestation is machine-verifiable**
   - Each policy has explicit check conditions
   - Human judgment is not attestation

---

## 5. Report Extension

Verification reports MUST include evidence classification.

```json
{
  "session_id": "...",
  "status": "PASS",
  "evidence_class": "A",
  "evidence_class_rationale": "Full chain, no gaps, no drops",
  "attestations": [],
  "exit_code": 0
}
```

---

## 6. Legal Implications (IMPORTANT)

### Class A Evidence

> "This evidence is cryptographically sealed, independently verifiable,
> and represents a complete, unbroken record of agent behavior."

Suitable for:

- Affidavits
- Expert witness testimony
- Regulatory filings

### Class B Evidence

> "This evidence is cryptographically valid but incomplete.
> [X] events were dropped during recording.
> Conclusions may be limited."

Must include:

- Explicit incompleteness disclaimer
- Quantified data loss

### Class C Evidence

> "This evidence has failed integrity verification and cannot be
> relied upon for any purpose except engineering investigation."

Cannot be:

- Presented in legal proceedings
- Submitted to regulators
- Shared with external parties as fact

---

## 7. Immutability

Once classified:

- Classification CANNOT be changed
- Classification is derived from sealed verification report
- Any attempt to "upgrade" classification is fraud

---

## 8. Non-Goals

This specification does NOT define:

- Business logic validation ("was the refund correct?")
- Semantic accuracy ("did the agent understand the request?")
- Performance metrics ("was response time acceptable?")

Classification concerns **evidence integrity**, not **content correctness**.

## 9. Redaction Invariants

### Redaction Structural Invariant

If any field value is exactly equal to the literal string `"[REDACTED]"`, the corresponding `*_hash` field MUST be present and MUST correctly match the hash of the redacted original content.

Violation of this rule results in `REDACTION_INTEGRITY_VIOLATION` (Fatal).

### Redaction Policy Invariant

If verifier configuration sets `allow_redacted = false`, the presence of any `"[REDACTED]"` field MUST result in `POLICY_VIOLATION` (Fatal).

## 10. Evidence Classification Rule

If a session fails verification due to `SEQUENCE_VIOLATION`, `REDACTION_INTEGRITY_VIOLATION`, or any other fatal integrity error, the resulting evidence MUST be classified as **CLASS C (FAILED EVIDENCE)**.

**CLASS C** evidence MUST NOT be used for audit, compliance reporting, or incident reconstruction.

## 11. Verifier Failure Contract (Locked)

Each fatal verifier error MUST emit:

- A stable `error_code` (string)
- A stable process exit code (integer)
- A deterministic evidence classification

| Error Code                      | Exit Code | Evidence Class | Fatal |
| :------------------------------ | :-------- | :------------- | :---- |
| `SEQUENCE_VIOLATION`            | 2         | CLASS_C        | Yes   |
| `REDACTION_INTEGRITY_VIOLATION` | 2         | CLASS_C        | Yes   |
| `POLICY_VIOLATION`              | 2         | CLASS_C        | Yes   |
| `HASH_MISMATCH`                 | 2         | CLASS_C        | Yes   |
| `CHAIN_BREAK`                   | 2         | CLASS_C        | Yes   |
| `PAYLOAD_TAMPER`                | 2         | CLASS_C        | Yes   |
| `AUTHORITY_INVALID`             | 2         | CLASS_C        | Yes   |

**Rules:**

1. Exit codes are part of the public contract.
2. Changing them requires a major version bump.
3. Verifier MUST exit non-zero (Code 2) on any CLASS C result.
