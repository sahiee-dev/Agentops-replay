# AgentOps Replay — Incident Response Playbook

> **Purpose:** When the evidence chain breaks, this playbook defines how to investigate, document, and recover.

---

## Severity Classification

| Severity          | Description                    | Example                           | Response Time |
| ----------------- | ------------------------------ | --------------------------------- | ------------- |
| **P1 - Critical** | Evidence integrity compromised | Hash mismatch, tampering detected | Immediate     |
| **P2 - High**     | Evidence incomplete            | Sequence gaps, LOG_DROP detected  | < 4 hours     |
| **P3 - Medium**   | Evidence degraded              | Partial authority, unsealed chain | < 24 hours    |
| **P4 - Low**      | Operational issue              | Performance degradation           | Best effort   |

---

## Incident 1: Hash Mismatch Detected

### Symptoms

- Verifier reports `HASH_MISMATCH` violation
- `expected` and `actual` hashes differ for an event

### Root Causes

1. **Tampering:** Data was modified after ingestion (P1)
2. **Canonicalization Bug:** JCS implementation inconsistency (P1)
3. **Serialization Error:** Payload encoding mismatch (P2)

### Investigation Steps

```bash
# 1. Export the session for offline analysis
curl -o session.jsonl "http://api:8000/api/v1/sessions/<session_id>/export"

# 2. Run verifier in verbose mode
docker-compose run --rm verifier --verbose session.jsonl

# 3. Check specific event
jq 'select(.sequence_number == <index>)' session.jsonl
```

### Resolution

1. **If tampering confirmed:**
   - Do NOT attempt repair (Constitution: "No repair of broken chains")
   - Preserve evidence of tampering
   - Escalate to security team
   - Document in incident report

2. **If canonicalization bug:**
   - Compare JCS output between SDK and verifier
   - Check RFC 8785 compliance
   - File bug report with reproduction steps

### Documentation Required

- [ ] Affected session_id
- [ ] Event index with mismatch
- [ ] Expected vs actual hash values
- [ ] Root cause determination
- [ ] Resolution or escalation path

---

## Incident 2: Sequence Gap Detected

### Symptoms

- Verifier reports `SEQUENCE_GAP` violation
- Evidence class is `PARTIAL_AUTHORITATIVE_EVIDENCE`
- Missing events between sequence numbers

### Root Causes

1. **Network Partition:** SDK lost connectivity (P2)
2. **Buffer Overflow:** SDK ring buffer dropped events (P2)
3. **Ingestion Failure:** Batch was partially rejected (P2)
4. **Bug:** SDK sequence counter inconsistency (P2)

### Investigation Steps

```bash
# 1. Check for LOG_DROP events
jq 'select(.event_type == "LOG_DROP")' session.jsonl

# 2. List all sequence numbers
jq '.sequence_number' session.jsonl | sort -n

# 3. Identify the gap
# If sequence goes 0,1,2,5,6 -> gap is 3,4
```

### Resolution

1. **If LOG_DROP exists:**
   - Gap is expected and documented
   - Evidence class correctly reflects partial evidence
   - No further action required (Constitution: "No inference of missing data")

2. **If no LOG_DROP:**
   - Investigate SDK logs for errors
   - Check ingestion service logs for rejected batches
   - This is a bug — file with reproduction steps

### Documentation Required

- [ ] Affected session_id
- [ ] Gap range (which sequence numbers missing)
- [ ] LOG_DROP presence (Yes/No)
- [ ] Estimated data loss impact
- [ ] Root cause if determinable

---

## Incident 3: PII Exposure Detected

### Symptoms

- GDPR compliance check reports unredacted PII
- Evidence export contains personal data

### Root Causes

1. **Redaction Failure:** SDK did not redact field (P1)
2. **New PII Pattern:** Detection heuristics missed new format (P2)
3. **Configuration Error:** Redaction rules misconfigured (P2)

### Investigation Steps

```bash
# 1. Run PII scan on export
docker-compose run --rm verifier --scan-pii session.jsonl

# 2. Check redaction status
jq 'select(.payload | contains("[REDACTED]"))' session.jsonl

# 3. Verify hash preservation for redacted fields
# Redacted fields should have companion hash field
```

### Resolution

1. **Immediate containment:**
   - Restrict access to affected export
   - Do NOT distribute to external parties

2. **Redaction:**
   - Cannot modify existing events (immutable)
   - Issue new redacted export if possible
   - Document exposure in incident report

3. **Prevention:**
   - Update redaction rules
   - Add PII pattern to detection heuristics
   - Review SDK configuration

### Documentation Required

- [ ] Affected session_id
- [ ] PII type exposed (email, phone, SSN, etc.)
- [ ] Number of affected events
- [ ] Exposure scope (who received the data)
- [ ] Remediation steps taken

---

## Incident 4: Chain Seal Missing

### Symptoms

- Verifier reports `MISSING_SEAL` violation
- Evidence class is `NON_AUTHORITATIVE_EVIDENCE` or `PARTIAL_AUTHORITATIVE_EVIDENCE`

### Root Causes

1. **Session Not Finalized:** SESSION_END never sent (P3)
2. **Ingestion Failure:** Seal request failed (P2)
3. **SDK Misconfiguration:** Local authority mode in production (P2)

### Investigation Steps

```bash
# 1. Check session status in database
SELECT status, sealed_at FROM sessions WHERE session_id_str = '<session_id>';

# 2. Check for SESSION_END event
jq 'select(.event_type == "SESSION_END")' session.jsonl

# 3. Check chain seals table
SELECT * FROM chain_seals WHERE session_id = <int_id>;
```

### Resolution

1. **If session still active:**
   - Send SESSION_END to complete session
   - Request seal via ingestion API

2. **If ingestion failure:**
   - Check ingestion service logs
   - Retry seal if SESSION_END exists

3. **If fundamentally broken:**
   - Document as non-authoritative
   - Evidence unusable for compliance/legal

### Documentation Required

- [ ] Affected session_id
- [ ] Session status (ACTIVE, SEALED, etc.)
- [ ] SESSION_END presence
- [ ] Resolution path

---

## Post-Incident Checklist

After resolving any incident:

- [ ] **Timeline:** Document exact sequence of events
- [ ] **Root Cause:** Identify underlying issue
- [ ] **Impact:** Quantify data loss or exposure
- [ ] **Evidence:** Preserve all related logs and exports
- [ ] **Prevention:** Identify systemic improvements
- [ ] **Communication:** Notify affected stakeholders

---

## Emergency Contacts

| Role             | Responsibility                             |
| ---------------- | ------------------------------------------ |
| On-Call Engineer | First responder, initial triage            |
| Security Team    | Tampering, PII exposure                    |
| Legal/Compliance | Regulatory reporting, legal hold           |
| Platform Lead    | System-wide issues, architecture decisions |

---

## Constitution Reminders

When handling incidents, remember:

1. **No silent data loss** — All gaps must be documented
2. **No repair of broken chains** — Corruption is evidence, not error
3. **No inference of missing data** — Gaps remain gaps
4. **Fail closed for integrity** — Reject uncertain data
5. **Evidence > Interpretation** — Record facts, not narratives
