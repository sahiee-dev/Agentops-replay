# Incident Investigation: Agent Exposed Customer PII

> **Evidence Class:** NON_AUTHORITATIVE_EVIDENCE (Local Authority)  
> **Verification:** PASS  
> **This is a SIMULATED incident for demonstration purposes**

---

## Incident Summary

**Date:** January 24, 2026  
**Session ID:** `88f970ff-22d6-47fd-850f-01d4aed5140f`  
**Agent:** customer-support-demo-v1

During routine operation, the customer support agent exposed a customer's
email address in the tool call arguments. This was captured by AgentOps
Replay and is now part of the immutable evidence chain.

---

## Timeline Reconstruction

Using the AgentOps Replay log, we can reconstruct exactly what happened:

| Seq | Event Type     | Details                                                                     |
| --- | -------------- | --------------------------------------------------------------------------- |
| 0   | SESSION_START  | Agent initialized with ID `customer-support-demo-v1`                        |
| 1   | MODEL_REQUEST  | LLM called with query "Look up order ORD-001"                               |
| 2   | TOOL_CALL      | Tool `lookup_order` invoked with `{"order_id": "ORD-001"}`                  |
| 3   | TOOL_RESULT    | **PII EXPOSED:** Result contains `"customer_email": "john.doe@example.com"` |
| 4   | DECISION_TRACE | Agent decision recorded with inputs/outputs                                 |
| 5   | SESSION_END    | Session completed successfully                                              |
| 6   | CHAIN_SEAL     | Chain sealed with fingerprint                                               |

---

## Evidence of PII Exposure

From the TOOL_RESULT event payload:

```json
{
  "tool_name": "lookup_order",
  "result": {
    "order_id": "ORD-001",
    "status": "shipped",
    "customer_email": "john.doe@example.com", // ← PII EXPOSED
    "refund_eligible": true
  },
  "duration_ms": 50
}
```

**Finding:** The customer email was returned from the `lookup_order` tool
and persisted in the event log.

---

## Verification Evidence

```
Session: 88f970ff-22d6-47fd-850f-01d4aed5140f
Status: PASS
Evidence Class: NON_AUTHORITATIVE_EVIDENCE
Sealed: True
Complete: True
Authority: sdk

Fingerprint: 4272bdc790c75c02875818bf25709eac35c58a63d5d442ad60a9e62d808705aa
```

The hash chain is cryptographically intact, proving:

- Events were not tampered with
- Timeline is accurate
- All tool call arguments and results are preserved

---

## Remediation Actions

### Immediate

1. ✅ Identified the exact event containing PII (sequence 3)
2. ✅ Hash preserved for audit trail
3. ⏳ Apply redaction policy to future sessions

### Long-term

1. Modify `lookup_order` tool to NOT return full email
2. Enable `redact_pii=True` in AgentOps callback handler
3. Implement PII detection in policy engine

---

## Redaction Demonstration

With `redact_pii=True`, the TOOL_RESULT would appear as:

```json
{
  "tool_name": "lookup_order",
  "result": "[REDACTED:tool_result]",
  "result_hash": "sha256:a1b2c3d4...", // Hash preserved for matching
  "duration_ms": 50
}
```

This allows:

- GDPR compliance (PII not stored)
- Audit capability (hash proves content existed)
- Investigation (can match hashes if original data available)

---

## How to Reproduce This Investigation

```bash
# 1. Run the mock demo
cd examples/langchain_demo
python run_demo.py --mock

# 2. Verify the session
python verify_session.py --details

# 3. Examine the raw events
cat session_output.jsonl | python -m json.tool
```

---

## Conclusion

AgentOps Replay captured the complete evidence chain for this incident:

- **What happened:** Agent called `lookup_order`, received PII in response
- **When it happened:** Exact timestamps preserved
- **Proof of accuracy:** Cryptographic verification PASSED
- **No tampering possible:** Hash chain intact

This evidence can be used for:

- Internal incident review
- Compliance documentation
- Policy improvement

---

_Evidence captured and verified by AgentOps Replay v0.6_
