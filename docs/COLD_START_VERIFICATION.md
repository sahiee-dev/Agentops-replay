# Auditor Guide: Cold Start Verification

**Purpose:** This document explains how to cryptographically verify an `agentops_export.json` file **without access to the AgentOps repository**.

**Audience:** External Auditors, Legal Counsel, Regulators.

---

## 1. Prerequisites

You need a machine with:

- Python 3.10+
- The `agentops_export.json` file provided by the organization.

## 2. Obtain the Verifier

The AgentOps verifier is a standalone script designed to have zero dependencies other than the Python standard library.

1. Download the reference implementation `agentops_verify.py` from the official source (or request it attached to the evidence).
2. Save it as `agentops_verify.py`.

_Note: In a true hostile audit, you should inspect `agentops_verify.py` to ensure it implements the spec correctly. It is < 500 lines of Python._

## 3. The Evidence Artifact

The `agentops_export.json` file contains:

- **Canonical Events:** The raw event stream.
- **Hashes:** Cryptographic proofs for each event.
- **Chain Seal:** The server's digital stamp (if Authoritative).

## 4. Running Verification

Open a terminal and run:

```bash
python3 agentops_verify.py agentops_export.json --format json
```

### 5. Interpreting Results

**Scenario A: Success (Authoritative)**

```json
{
  "status": "PASS",
  "evidence_class": "AUTHORITATIVE_EVIDENCE",
  "sealed": true,
  "violations": []
}
```

**Meaning:** The log is complete, tamper-free, and sealed by the server. You can rely on its contents.

**Scenario B: Partial Evidence**

```json
{
  "status": "PASS",
  "evidence_class": "PARTIAL_AUTHORITATIVE_EVIDENCE",
  "partial_reasons": ["LOG_DROP"],
  ...
}
```

**Meaning:** The cryptographic chain is valid, but data was lost during recording (e.g., network failure). traceable "gaps" exist.

**Scenario C: Failure**

```json
{
  "status": "FAIL",
  "violations": [...]
}
```

**Meaning:** The log has been tampered with. Reject it.

## 6. Manual Cryptographic Check (Paranoid Mode)

If you do not trust the script, you can verify a single event manually.

**Formula:**
`SHA-256( JCS( SignedFields ) ) == EventHash`

1. Extract the `payload` (it is a JSON string).
2. Construct the Signed Object:
   ```json
   {
     "event_id": "...",
     "session_id": "...",
     "sequence_number": 123,
     "timestamp_wall": "...",
     "event_type": "...",
     "payload_hash": "SHA-256(canonical_payload)",
     "prev_event_hash": "..."
   }
   ```
3. Canonicalize using RFC 8785 (JCS).
4. Compute SHA-256.
5. Compare with `event_hash` in the export.
