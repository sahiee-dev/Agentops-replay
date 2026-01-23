# CHAIN_AUTHORITY_INVARIANTS.md (v1.0)

## Purpose

This document establishes **hard invariants** that make local authority mode cryptographically and semantically distinguishable from server authority. These invariants are enforceable in code and provide legal armor for enterprise audit compliance.

## Invariant 1: Evidence Classification

Every session MUST be classified into exactly one of three evidence states:

### AUTHORITATIVE_EVIDENCE

- Server authority (`chain_authority="server"`)
- Contains valid `CHAIN_SEAL` event with required metadata
- Session is complete (has `SESSION_END`)
- Chain cryptographically valid

**Use Case:** Compliance attestation, regulatory reporting, legal evidence

### PARTIAL_AUTHORITATIVE_EVIDENCE

- Server authority (`chain_authority="server"`)
- Cryptographically valid chain
- **BUT** one or more of:
  - Missing `CHAIN_SEAL` (unsealed)
  - Missing `SESSION_END` (incomplete)
  - Contains `LOG_DROP` events (data loss occurred)

**Use Case:** Incident analysis, debugging, operational forensics (not compliance-grade)

### NON_AUTHORITATIVE_EVIDENCE

- SDK/local authority (`chain_authority="sdk"`)
- Chain may be cryptographically valid
- Explicitly flagged as testing/development only

**Use Case:** Local testing, development, integration tests

---

## Invariant 2: Cryptographic Authority Separation

Server authority chains are cryptographically distinguishable from SDK chains **by construction**.

### CHAIN_SEAL Requirement

Server authority sessions MUST include a `CHAIN_SEAL` event to achieve `AUTHORITATIVE_EVIDENCE` status.

**Construction:**

```json
{
  "event_type": "CHAIN_SEAL",
  "chain_authority": "server",
  "payload": {
    "ingestion_service_id": "prod-ingest-01",
    "seal_timestamp": "2026-01-23T12:00:00.000Z",
    "session_digest": "sha256:abc123..."
  }
}
```

**Required Payload Fields:**

| Field                  | Type    | Purpose                                             |
| ---------------------- | ------- | --------------------------------------------------- |
| `ingestion_service_id` | string  | Unique identifier of the ingestion service instance |
| `seal_timestamp`       | RFC3339 | Server-authoritative timestamp of seal              |
| `session_digest`       | string  | Final chain hash (format: `sha256:<hex>`)           |

**Future Extension:**

- v1.1 MAY add `signature` field with public/private key signing
- v1.1 MAY add `signer_key_id` for key rotation

### SDK Constraint

The SDK MUST NOT contain logic to emit `CHAIN_SEAL` events in server authority mode.

**Enforcement:**

1. SDK code review MUST verify no `CHAIN_SEAL` emission in server mode
2. Verifier MUST reject `chain_authority="server"` sessions with malformed `CHAIN_SEAL`
3. Verifier MUST classify `chain_authority="server"` sessions without valid `CHAIN_SEAL` as `PARTIAL_AUTHORITATIVE_EVIDENCE`

### Auditor Question Answered

**Question:** "How do I prove this log was not locally fabricated?"

**Answer:**

1. Inspect `evidence_class` in verification report
2. If `AUTHORITATIVE_EVIDENCE`:
   - Session has valid `CHAIN_SEAL` from known ingestion service
   - `ingestion_service_id` can be cross-referenced with infrastructure records
   - Server sealed the chain, SDK cannot forge this
3. If `PARTIAL_AUTHORITATIVE_EVIDENCE`:
   - Server-managed but incomplete/unsealed
   - Suitable for incident analysis, not compliance
4. If `NON_AUTHORITATIVE_EVIDENCE`:
   - Locally generated (testing only)
   - Explicitly flagged, cannot be mistaken for production

**Cryptographic Guarantee:**
The SDK MAY fabricate `ingestion_service_id`, but without a valid cryptographic signature (v1.1+), the server authority claim is unverifiable. The `CHAIN_SEAL` metadata alone is a semantic signal, not a cryptographic proof, until signing is strictly enforced.

---

## Invariant 3: Policy-Based Rejection

Verifiers MUST support policy flags to reject evidence classes.

### Policy Interface

```python
verify_session(events, policy={
    "reject_local_authority": bool,
    "require_seal": bool,  # Future: reject PARTIAL_AUTHORITATIVE
})
```

### CLI Interface

```bash
python3 agentops_verify.py session.jsonl \
  --reject-local-authority \
  --format json
```

**Behavior:**

- If `reject_local_authority=True` and `evidence_class="NON_AUTHORITATIVE_EVIDENCE"`, verification MUST fail with `POLICY_VIOLATION`
- Policy violations MUST be surfaced loudly in CLI output (not buried in JSON)

---

## Invariant 4: Forensic Auditability

### Verifier Output Requirements

Every verification report MUST include:

```json
{
  "session_id": "...",
  "status": "PASS" | "FAIL",
  "evidence_class": "AUTHORITATIVE_EVIDENCE" | "PARTIAL_AUTHORITATIVE_EVIDENCE" | "NON_AUTHORITATIVE_EVIDENCE",
  "authority": "server" | "sdk" | "unknown",
  "sealed": true | false,
  "complete": true | false,
  "violations": [...],
  "replay_fingerprint": "sha256:..."
}
```

### Report Labeling Rules

1. **MUST** compute `evidence_class` from:
   - `authority` (server/sdk/unknown)
   - `sealed` (has valid CHAIN_SEAL)
   - `complete` (has SESSION_END and no gaps)

2. **MUST NOT** allow UI or SDK to override `evidence_class`

3. **MUST** fail verification if:
   - `chain_authority="server"` but `CHAIN_SEAL` has missing required fields
   - Mixed authority within single session

---

## Proof Obligations

This invariant document satisfies Constitution.md Section 8 by providing:

1. **Assumptions:**
   - Ingestion service is trusted to emit CHAIN_SEAL
   - SDK is untrusted and MAY be modified by attackers
   - Verifier is trusted and runs in secure environment

2. **Failure Modes:**
   - See FAILURE_MODES.md for comprehensive tables

3. **Post-Hoc Detection:**
   - Missing CHAIN_SEAL → detectable via `evidence_class`
   - Malformed CHAIN_SEAL → detectable via `INVALID_SEAL` violation
   - Mixed authority → detectable via `MIXED_AUTHORITY` violation

---

## Amendment Process

This document is frozen at v1.0 for EVENT_LOG_SPEC v0.6.

Changes require:

1. Constitutional approval (CONSTITUTION.md amendment)
2. Major version bump
3. Migration document for existing sessions
4. Backward-compatible evidence classification

**Current Status:** FROZEN (v1.0)
**Effective:** EVENT_LOG_SPEC v0.6+
