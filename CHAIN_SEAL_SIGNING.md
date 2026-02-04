# CHAIN_SEAL_SIGNING.md (v0.1 - Stub)

## Status: FUTURE WORK (Not Yet Implemented)

**Current State:** CHAIN_SEAL uses metadata validation only  
**Target State:** Cryptographic signing with public/private keys  
**Timeline:** Before production server deployment

---

## 1. Threat Model

### Current Defense (v0.6)

CHAIN_SEAL enforcement relies on:

- SDK architectural constraint (cannot emit server CHAIN_SEAL)
- Metadata validation (`ingestion_service_id`, `seal_timestamp`, `session_digest`)
- Assumption: Ingestion service credentials are secure

**Weakness:** If ingestion service credentials leak, attacker could forge CHAIN_SEAL.

### Target Defense (v1.0+)

CHAIN_SEAL will include cryptographic signature:

- Ingestion service signs CHAIN_SEAL with private key
- Verifier validates signature with public key
- Key compromise detectable, rotatable

---

## 2. Signing Scheme (Planned)

### Algorithm

**EdDSA (Ed25519)** - Chosen for:

- Deterministic signatures (no nonce risk)
- Small signature size (64 bytes)
- Fast verification
- Wide library support

**Alternative Considered:** ECDSA (P-256)

- Rejected: Non-deterministic, larger signatures

### Signature Payload

```json
{
  "event_type": "CHAIN_SEAL",
  "chain_authority": "server",
  "payload": {
    "ingestion_service_id": "prod-ingest-01",
    "seal_timestamp": "2026-01-23T12:00:00.000Z",
    "session_digest": "sha256:abc123...",
    "signature": "base64-encoded-ed25519-signature",
    "signer_key_id": "key-2026-01-v1"
  }
}
```

**Signed Fields (Canonical Order):**

```json
{
  "ingestion_service_id": "...",
  "seal_timestamp": "...",
  "session_digest": "...",
  "session_id": "...",
  "spec_version": "v1.0"
}
```

**Signature Computation:**

```
signature = Ed25519.sign(private_key, JCS(signed_fields))
```

---

## 3. Key Management

### Key Ownership

- **Private Key:** Held ONLY by ingestion service
- **Public Key:** Embedded in verifier, published openly
- **SDK:** MUST NOT have access to private key (architectural constraint)

### Key Storage

**Ingestion Service:**

- Private key stored in HSM (Hardware Security Module) or KMS
- Key never leaves secure boundary
- Signing happens server-side only

**Verifier:**

- Public keys embedded in code or config
- Multiple public keys supported (for rotation)
- Key ID used to select verification key

### Key Rotation

**Rotation Trigger:**

- Scheduled (annually)
- Compromise suspected
- Algorithm upgrade

**Rotation Process:**

1. Generate new keypair (`key-2027-01-v2`)
2. Deploy new public key to verifiers
3. Ingestion switches to new private key
4. Old public keys remain valid for historical sessions
5. After grace period, retire old private key

**Backward Compatibility:**

- Verifier MUST support multiple public keys simultaneously
- Sessions sealed with old keys remain valid indefinitely
- Key ID in CHAIN_SEAL payload maps to verification key

---

## 4. Verification Logic

### Current (v0.6) - Metadata Only

```python
if event["event_type"] == "CHAIN_SEAL":
    payload = event["payload"]
    required = ["ingestion_service_id", "seal_timestamp", "session_digest"]
    if all(field in payload for field in required):
        report["sealed"] = True
    else:
        raise VerificationError("INVALID_SEAL", "Missing required metadata")
```

### Future (v1.0+) - Cryptographic Signature

```python
if event["event_type"] == "CHAIN_SEAL":
    payload = event["payload"]

    # Metadata validation (still required)
    required = ["ingestion_service_id", "seal_timestamp", "session_digest", "signature", "signer_key_id"]
    if not all(field in payload for field in required):
        raise VerificationError("INVALID_SEAL", "Missing required fields")

    # Signature validation (new)
    signer_key_id = payload["signer_key_id"]
    public_key = get_public_key(signer_key_id)
    if public_key is None:
        raise VerificationError("UNKNOWN_KEY", f"Key {signer_key_id} not recognized")

    signed_fields = {
        "ingestion_service_id": payload["ingestion_service_id"],
        "seal_timestamp": payload["seal_timestamp"],
        "session_digest": payload["session_digest"],
        "session_id": event["session_id"],
        "spec_version": event["schema_ver"]
    }
    canonical = jcs.canonicalize(signed_fields)
    signature = base64.b64decode(payload["signature"])

    if not Ed25519.verify(public_key, canonical, signature):
        raise VerificationError("INVALID_SIGNATURE", "CHAIN_SEAL signature verification failed")

    report["sealed"] = True
    report["cryptographically_signed"] = True
```

---

## 5. Migration Path

### Phase 1: v0.6 (Current)

- ✅ Metadata validation only
- ✅ Evidence classification based on seal presence
- ⚠️ Trust-anchored, not cryptographically anchored

### Phase 2: v0.7 (Transition)

- Add `signature` and `signer_key_id` as OPTIONAL fields
- Verifier validates signature if present
- Sessions without signature remain `AUTHORITATIVE_EVIDENCE` (legacy)
- New sessions encouraged to include signature

### Phase 3: v1.0 (Cryptographic Requirement)

- `signature` becomes REQUIRED for `AUTHORITATIVE_EVIDENCE`
- Sessions without signature downgrade to `PARTIAL_AUTHORITATIVE_EVIDENCE`
- Legacy v0.6 sessions grandfathered via explicit policy flag

### Backward Compatibility Guarantee

**Historical Sessions:**

- v0.6 sessions without signatures remain valid
- Evidence classification frozen at time of creation
- No retroactive invalidation

**Verifier Behavior:**

```python
if schema_ver == "v0.6":
    # Legacy: metadata validation only
    validate_metadata_only()
elif schema_ver >= "v1.0":
    # Modern: require signature
    validate_cryptographic_signature()
```

---

## 6. Explicit Non-Goals

This signing scheme will **NOT**:

- **Prevent ingestion service compromise** (defense-in-depth, not silver bullet)
- **Sign individual events** (only CHAIN_SEAL, to avoid bloat)
- **Support client-side signing** (SDK remains untrusted)
- **Guarantee non-repudiation** (system goal is auditability, not legal non-repudiation)

---

## 7. Open Questions (To Be Resolved)

1. **Key Rotation Grace Period:** How long before old keys are retired?
   - **Proposal:** 1 year minimum

2. **Key Compromise Response:** What if private key leaks?
   - **Proposal:** Revocation list + retroactive evidence class downgrade

3. **Multi-Signer Support:** Can multiple ingestion services sign?
   - **Proposal:** Yes, each has unique `ingestion_service_id` + `signer_key_id`

4. **Offline Verification:** Should public keys be embeddable?
   - **Proposal:** Yes, verifier MUST work without network

---

## 8. Implementation Checklist

When implementing cryptographic signing:

- [ ] Define canonical signing payload (JCS order)
- [ ] Choose KMS provider (AWS KMS, HashiCorp Vault, etc.)
- [ ] Generate initial keypair (`key-2026-01-v1`)
- [ ] Update ingestion service to sign CHAIN_SEAL
- [ ] Update verifier to validate signatures
- [ ] Add public key management to verifier
- [ ] Write key rotation runbook
- [ ] Add test vectors for signature validation
- [ ] Document key compromise incident response
- [ ] Update CHAIN_AUTHORITY_INVARIANTS.md to reference signing

---

## 9. Auditor Talking Points

When asked: **"What if ingestion service credentials leak?"**

**Current Answer (v0.6):**

- "Credential leak would allow CHAIN_SEAL forgery (acknowledged risk)"
- "Mitigation: Procedural controls, access logging, key rotation"
- "Evidence classification would not detect compromise"

**Future Answer (v1.0+):**

- "Credential leak does not give signing capability (private key in HSM)"
- "Compromise detectable via key ID + public key validation"
- "Revocation list downgrades compromised sessions retroactively"

---

## 10. Technical Debt Acknowledgment

**Current State:**

> Until signing exists, AUTHORITATIVE_EVIDENCE is **trust-anchored**, not **cryptographically anchored**.

This is **acceptable temporarily** but MUST be treated as **technical debt with a deadline**.

**Commitment:**

- Signing MUST be implemented before production server deployment
- v0.6 sessions will be grandfathered, not invalidated
- Migration path is backward-compatible

---

**Status:** STUB (Intent and Constraints Documented)  
**Effective:** v0.6 (metadata validation only)  
**Target:** v1.0 (cryptographic signing required)
