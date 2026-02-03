# Production Evidence Contract

**Status**: ACTIVE
**Scope**: Legal / Audit / Compliance

This document defines what constitutes **Authoritative Evidence** within the AgentOps ecosystem. This is the standard used for liability protection, dispute resolution, and compliance audits.

## 1. Definition of Evidence

A Session Log is considered **EVIDENCE** if and only if:

1.  It contains a valid partial or complete **Causal Hash Chain**.
2.  It has been processed by the **Ingestion Service** without fatal errors.
3.  It culminates in a `SESSION_END` (with status) or `SESSION_FAIL` (if supported by schema, otherwise `SESSION_END` with failure status) event.

4.  It strictly adheres to the **JSON Canonicalization Scheme (JCS - RFC 8785)**.

## 2. Classification of Trust

### Class A: Authoritative Evidence (Gold Standard)

- **Requirements**:
  - Full cryptographic chain integrity (Genesis to End).
  - Verified by `agentops-verify`.
  - Hosted on immutable storage.
- **Completeness Levels**:
  - **COMPLETE**: No `LOG_DROP` events (zero data loss).
  - **DEGRADED**: `LOG_DROP` events present. Must be explicitly disclosed.
- **Usage**: Legal defense, automated compliance, root cause analysis.

### Class B: Partial Evidence (Operational)

- **Requirements**:
  - Valid chain segments.
  - Signatures valid for available blocks.
- **Usage**: Debugging, monitoring. **NOT** sufficient for non-repudiation.

### Class C: Non-Authoritative (Development)

- **Characteristics**:
  - SDK-local logs (never ingested).
  - Broken chain links.
  - Unverified properties.
- **Usage**: **DISCARD**. Zero value for audit.

## 3. The Verification Gate

**Rule**: No human or system shall accept a session as "fact" without a passing Verification Report.

### Verification Matrix

| Condition                                 | Verdict     | operational Action                                  |
| :---------------------------------------- | :---------- | :-------------------------------------------------- |
| **Missing Chain Seal**                    | **REJECT**  | Flag as potential tampering.                        |
| **Hash Mismatch**                         | **REJECT**  | **CRITICAL SECURITY ALERT**. Evidence corrupted.    |
| **Sequence Gap**                          | **PARTIAL** | Flag as "Incomplete Dataset".                       |
| **Schema Violation**                      | **REJECT**  | Ingestion should have blocked this. System failure. |
| **Signature Valid (+ Structural Checks)** | **PASS**    | Admissible as Evidence.                             |

## 4. Defensibility Limits

- **We ensure**: The agent _attempted_ Action X and received Result Y.
- **We do NOT ensure**: Result Y was "correct" (business logic).
- **We ensure**: The logs have not been altered since Ingestion (via Hashing).
- **We do NOT ensure**: The SDK host machine was not compromised _before_ emission (Endpoint Security scope).

## 5. Redaction Policy

- Redacted fields MUST be replaced with `[REDACTED]` or a hash.
- Redaction MUST preserve the JSON structure (keys remain, values change).
- **Verification Mode**: The verification report MUST declare the mode used:
  - `verification_mode: "REDACTED"` (Production Standard) - verify against redacted stream.
  - `verification_mode: "FULL"` (Internal Only) - verify against original raw stream.
