# ATTEMPTED_EVIDENCE_FORGERY.md

**Subtitle:** Why It Fails

## Purpose

This document walks through adversarial scenarios where an attacker attempts to forge evidence and demonstrates why the AgentOps Replay constitutional layer prevents success.

**Audience:** Enterprise auditors, security teams, legal counsel

---

## Scenario 1: Modified SDK Claiming Server Authority

### Attack

**Attacker Goal:** Make a locally-generated log appear as production server evidence.

**Attack Steps:**

1. Fork AgentOps SDK
2. Modify SDK to set `chain_authority = "server"` for all events
3. Run agent locally with modified SDK
4. Export JSONL with `authority="server"` labels
5. Submit to auditors as "production evidence"

### Why It Fails

**Detection Point 1: Missing CHAIN_SEAL**

```json
{
  "session_id": "attacker-session",
  "evidence_class": "PARTIAL_AUTHORITATIVE_EVIDENCE",
  "sealed": false,
  "partial_reasons": ["UNSEALED_SESSION"]
}
```

- Server authority requires valid `CHAIN_SEAL` for `AUTHORITATIVE_EVIDENCE`
- Modified SDK cannot forge `ingestion_service_id` (never receives this value)
- Evidence classification downgrades to `PARTIAL_AUTHORITATIVE_EVIDENCE`

**Detection Point 2: Auditor Question**

> "Where is the ingestion service seal?"

**Attacker Response Options:**

1. "There is no seal" → Auditor rejects (not compliance-grade)
2. "I added a seal" → Auditor validates metadata:
   - `ingestion_service_id` doesn't match known service IDs
   - `seal_timestamp` doesn't match server logs
   - Future (v1.0+): Signature verification fails

### Outcome

❌ Attack fails  
✅ Session correctly classified as `PARTIAL_AUTHORITATIVE_EVIDENCE`  
✅ Auditor can distinguish from genuine production evidence

---

## Scenario 2: Fake CHAIN_SEAL Injection

### Attack

**Attacker Goal:** Add a fabricated `CHAIN_SEAL` to bypass authority checks.

**Attack Steps:**

1. Run agent with modified SDK
2. Before `SESSION_END`, inject a `CHAIN_SEAL` event:
   ```json
   {
     "event_type": "CHAIN_SEAL",
     "chain_authority": "server",
     "payload": {
       "ingestion_service_id": "fake-prod-ingest-01",
       "seal_timestamp": "2026-01-23T12:00:00.000Z",
       "session_digest": "sha256:fabricated..."
     }
   }
   ```
3. Submit to verifier

### Why It Fails (v0.6 - Metadata Validation)

**Detection Point: Metadata Validation**

```python
# Verifier checks
required_fields = ["ingestion_service_id", "seal_timestamp", "session_digest"]
if all(field in payload for field in required_fields):
    # Metadata present, but...
    # Auditor cross-references ingestion_service_id with infrastructure records
```

**Auditor Question:**

> "Show me logs from `fake-prod-ingest-01`"

**Attacker Response:**

- "I don't have those logs" → Auditor rejects
- "Here are fake logs" → Timeline inconsistencies detected

### Why It Fails (v1.0+ - Cryptographic Signature)

**Detection Point: Signature Verification**

```python
# Verifier checks
public_key = get_public_key(payload["signer_key_id"])
if not Ed25519.verify(public_key, canonical_payload, signature):
    raise VerificationError("INVALID_SIGNATURE", "CHAIN_SEAL signature verification failed")
```

**Attacker Cannot:**

- Forge signature without private key
- Private key never leaves ingestion service HSM
- SDK never has access to private key

### Outcome

❌ v0.6: Metadata validation + manual audit catches forgery  
❌ v1.0+: Cryptographic signature verification automatically fails  
✅ System degrades gracefully (v0.6) and hardens over time (v1.0+)

---

## Scenario 3: Hash Chain Manipulation

### Attack

**Attacker Goal:** Modify event payloads after the fact without breaking chain.

**Attack Steps:**

1. Generate valid session with SDK
2. After export, edit payload of event #5:
   ```json
   {
     "tool_name": "web_search",
     "query": "sensitive data" → "harmless query"
   }
   ```
3. Recompute `payload_hash` for event #5
4. Recompute `event_hash` for event #5
5. Update `prev_event_hash` for event #6
6. Continue recomputing for all subsequent events

### Why It Fails

**Detection Point 1: Server Mode Authority**

- In server mode, SDK does not compute hashes
- Ingestion service computes all hashes server-side
- Attacker would need to compromise ingestion service, not just modify JSONL

**Detection Point 2: CHAIN_SEAL Digest Mismatch**

Even if attacker recomputes entire chain:

```json
{
  "event_type": "CHAIN_SEAL",
  "payload": {
    "session_digest": "sha256:original-final-hash"
  }
}
```

- `session_digest` in CHAIN_SEAL must match final `event_hash`
- Attacker must either:
  1. Not modify CHAIN_SEAL → digest mismatch
  2. Modify CHAIN_SEAL → requires forging seal (see Scenario 2)

**Detection Point 3: Verifier Recomputes Hashes**

```python
# Verifier does not trust event-provided hashes
canonical_payload = jcs.canonicalize(payload)
expected_payload_hash = sha256(canonical_payload)

if event["payload_hash"] != expected_payload_hash:
    raise VerificationError("PAYLOAD_HASH_MISMATCH")
```

Verifier independently recomputes all hashes. Modified payloads fail verification.

### Outcome

❌ Attack fails at multiple layers  
✅ Chain integrity prevents post-hoc modification  
✅ CHAIN_SEAL locks final state

---

## Scenario 4: Sequence Gap Injection

### Attack

**Attacker Goal:** Hide events by creating gaps in sequence numbers.

**Attack Steps:**

1. Generate session with events 0-9
2. Delete event #5 from JSONL
3. Submit to verifier

### Why It Fails

**Detection Point: Sequence Monotonicity Check**

```python
expected_seq = 0
for event in events:
    if event["sequence_number"] != expected_seq:
        raise VerificationError("SEQUENCE_GAP", f"Expected {expected_seq}, got {event['sequence_number']}")
    expected_seq += 1
```

Verifier enforces strict monotonic sequence: 0, 1, 2, 3, ...  
Gap detected immediately.

**Detection Point: Chain Hash Mismatch**

Event #6's `prev_event_hash` points to event #5.  
If event #5 is missing, `prev_event_hash` does not match event #4's `event_hash`.

```python
if event["prev_event_hash"] != prev_hash:
    raise VerificationError("CHAIN_BROKEN")
```

### Outcome

❌ Attack fails (sequence gap + chain break)  
✅ Missing events are detectable  
✅ Verifier enforces completeness

---

## Scenario 5: LOG_DROP Fabrication

### Attack

**Attacker Goal:** Claim data was "lost" to hide malicious events.

**Attack Steps:**

1. Generate session with events 0-4
2. Events 5-9 contain evidence of policy violation
3. Delete events 5-9
4. Insert fake `LOG_DROP`:
   ```json
   {
     "event_type": "LOG_DROP",
     "sequence_number": 5,
     "payload": {
       "dropped_count": 5,
       "cumulative_drops": 5,
       "drop_reason": "BUFFER_FULL"
     }
   }
   ```
5. Continue with event #10

### Why It Fails

**Detection Point 1: Evidence Classification**

```json
{
  "evidence_class": "PARTIAL_AUTHORITATIVE_EVIDENCE",
  "partial_reasons": ["LOG_DROP_PRESENT"]
}
```

- LOG_DROP downgrades evidence to `PARTIAL_AUTHORITATIVE`
- Not suitable for compliance attestation
- Auditor scrutiny increases for partial evidence

**Detection Point 2: Auditor Questions**

> "Why did the buffer overflow at exactly this point?"  
> "What was the agent doing before the drop?"  
> "Do server logs show corresponding network issues?"

Fabricated LOG_DROP creates timeline inconsistencies.

**Detection Point 3: Chain Seal**

If attacker modifies chain to hide events, CHAIN_SEAL digest no longer matches.  
Attacker cannot forge new seal (see Scenario 2).

### Outcome

❌ LOG_DROP fabrication downgrades evidence class  
❌ Timeline inconsistencies raise auditor suspicion  
✅ System correctly labels session as incomplete

---

## Scenario 6: Mixed Authority Confusion

### Attack

**Attacker Goal:** Claim some events are server-authoritative, others are SDK-authoritative.

**Attack Steps:**

1. Run agent with server authority for events 0-5
2. Run agent with local authority for events 6-9
3. Concatenate JSONL files
4. Submit as single session

### Why It Fails

**Detection Point: Single Authority Invariant**

```python
authorities = set()
for event in events:
    authorities.add(event.get("chain_authority"))

if len(authorities) > 1:
    raise VerificationError("MIXED_AUTHORITY", f"Session has mixed authorities: {authorities}")
```

Verifier detects `{"server", "sdk"}` and fails verification immediately.

### Outcome

❌ Mixed authority is explicitly forbidden  
✅ Sessions are all-or-nothing (server OR sdk, never both)  
✅ No hybrid or transitional states allowed

---

## Defense in Depth

### Layer 1: SDK Constraints

- SDK cannot directly set `event_hash`, `prev_event_hash`
- SDK cannot emit `CHAIN_SEAL` in server mode (architectural constraint)

### Layer 2: Ingestion Service

- Overwrites `chain_authority` in server mode
- Recomputes all hashes server-side
- Emits CHAIN_SEAL with unforgeable metadata

### Layer 3: Verifier

- Independently recomputes all hashes (does not trust event-provided values)
- Validates CHAIN_SEAL metadata
- Enforces single-authority invariant
- Classifies evidence based on seal presence

### Layer 4: Evidence Classification

- `AUTHORITATIVE_EVIDENCE` requires seal + complete + no drops
- `PARTIAL_AUTHORITATIVE_EVIDENCE` downgrades incomplete sessions
- `NON_AUTHORITATIVE_EVIDENCE` flags local authority explicitly

### Layer 5: Human Audit

- Metadata cross-reference (ingestion_service_id vs. infrastructure logs)
- Timeline consistency checks
- Policy-based rejection flags (`--reject-local-authority`)

---

## Auditor Talking Points

**Question:** "Can a malicious SDK forge production evidence?"

**Answer:**

- "No. Server authority requires CHAIN_SEAL from ingestion service."
- "SDK cannot forge `ingestion_service_id` (never receives this value)."
- "Without valid seal, session downgrades to PARTIAL_AUTHORITATIVE at best."

**Question:** "What if the ingestion service is compromised?"

**Answer:**

- "v0.6: Metadata validation + manual audit (trust-anchored)"
- "v1.0+: Cryptographic signatures (cryptographically-anchored)"
- "Key rotation + revocation list for detected compromises"

**Question:** "Can events be modified after logging?"

**Answer:**

- "No. Verifier recomputes all hashes independently."
- "Payload modification causes hash mismatch."
- "Chain structure prevents silent edits."

**Question:** "How do you prevent hiding events?"

**Answer:**

- "Sequence gaps fail verification immediately."
- "Chain hash linkage detects missing events."
- "LOG_DROP events are forensically visible and downgrade evidence class."

---

## Conclusion

The AgentOps Replay constitutional layer is designed with **adversarial resistance** as a first principle.

**Key Properties:**

1. **Forgery-Resistant:** CHAIN_SEAL enforcement prevents authority impersonation
2. **Tamper-Evident:** Hash chains detect post-hoc modifications
3. **Completeness-Verifiable:** Sequence numbers + chain linkage detect gaps
4. **Gracefully Degrading:** Invalid attempts result in lower evidence classification, not silent success

**Trust Model:**

- SDK is untrusted (can be modified, can lie)
- Ingestion service is trusted (but verifiable via seal metadata)
- Verifier is trusted (independent validation logic)
- Adversaries cannot silently upgrade evidence class

---

**Status:** Living Document  
**Effective:** Event Log Spec v0.6+  
**Audience:** Enterprise auditors, security teams, legal counsel
