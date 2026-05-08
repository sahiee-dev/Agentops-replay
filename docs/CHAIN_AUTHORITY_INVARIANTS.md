# AgentOps Replay — Chain Authority Invariants

Version: 1.0
Status: Stable
Last Updated: May 2026
This document is the authoritative specification for chain authority and principal invariants.

---

This document specifies the trust model and authority separation rules that govern event production in AgentOps Replay. These invariants are not optional; they are enforced by the ingestion service and verified by the standalone verifier. Any implementation that violates these rules produces evidence that cannot be trusted.

---

## 1. The Three Principals

AgentOps Replay operates under a three-principal trust model. Understanding the asymmetry between these principals is essential for understanding what evidence guarantees the system can and cannot provide.

| Principal | Role | Trust Level | Responsibility |
| :--- | :--- | :--- | :--- |
| **SDK** | Untrusted Producer | **Untrusted** | Captures events from the agent process. Subject to client-side compromise. |
| **Ingestion Service** | Trusted Authority | **Trusted-Verify** | Recomputes hashes, enforces continuity, and seals valid chains. |
| **Verifier** | Independent Validator | **Independent** | Standalone tool that verifies the chain without external dependencies. |

### 1.1 The SDK (Untrusted Producer)
The SDK runs inside the agent process, in the same memory space as the agent being observed. It is subject to all the same faults, crashes, corruptions, and intentional manipulations that could affect the agent itself. For this reason, the SDK is treated as an untrusted producer. Its output is always verified server-side before being accepted as a record of fact.

### 1.2 The Ingestion Service (Trusted Authority)
The ingestion service runs outside the agent process, in a controlled server environment. It is the only entity authorized to make authoritative claims about the integrity of a session chain. It independently recomputes all hashes and appends server-authority events (like `CHAIN_SEAL`) only after passing all integrity checks.

### 1.3 The Verifier (Independent Validator)
The verifier is a zero-dependency script designed to run in any environment (including air-gapped forensic workstations). Its role is to provide a "second opinion" on the chain's integrity, completely independent of the SDK or the Ingestion Service's internal state.

---

## 2. Authority Separation Rules

The distinction between SDK-authority and server-authority event types is fundamental to the evidence model.

### 2.1 Authority Table

| Event Type | Producer | Authority | Rationale |
| :--- | :--- | :--- | :--- |
| `SESSION_START` | SDK | SDK | Fact of agent starting. |
| `SESSION_END` | SDK | SDK | Fact of agent stopping. |
| `LLM_CALL` | SDK | SDK | Observed interaction. |
| `LLM_RESPONSE` | SDK | SDK | Observed interaction. |
| `TOOL_CALL` | SDK | SDK | Observed interaction. |
| `TOOL_RESULT` | SDK | SDK | Observed interaction. |
| `TOOL_ERROR` | SDK | SDK | Observed interaction. |
| `LOG_DROP` | SDK | SDK | Evidence of client-side loss. |
| `CHAIN_SEAL` | Server | Server | Authoritative closing of the chain. |
| `CHAIN_BROKEN` | Server | Server | Authoritative record of ingestion gap. |
| `REDACTION` | Server | Server | Authorized modification record. |
| `FORENSIC_FREEZE` | Server | Server | Administrative integrity lock. |

---

## 3. Core Invariants

### Invariant 1: SDK-Authority Isolation
The SDK must never produce server-authority events. Any batch containing a server-authority event (`CHAIN_SEAL`, etc.) sent from a client must be rejected with HTTP 403. This prevents "authority spoofing" where a compromised SDK attempts to seal its own tampered chain.

### Invariant 2: Server-Authority Immutability
The ingestion service must never modify the payload or metadata of an SDK-produced event. The server recomputes the hash to *verify* it, but the data itself remains as the SDK reported it. Even in the case of `REDACTION`, the original event remains in the chain; only a specific redacted payload version is served, and the `REDACTION` event itself documents the change.

### Invariant 3: Verifier Determinism
The verifier output must be strictly deterministic. For a given input file, the verifier must produce the same `Result` (PASS/FAIL) and `Evidence Class` regardless of the platform, time, or environment in which it is run. It must rely only on the cryptographic properties of the JSONL file.

---

## 4. The Independence Requirement

The Verifier must be implementation-independent. It cannot share configuration, database access, or non-standard libraries with the Ingestion Service. This independence ensures that a bug or compromise in the Ingestion Service's persistence layer cannot be hidden from a reviewer using the standalone verifier.

---

## 5. Trust Levels and Rationale

1. **Untrusted (SDK):** Because it is co-located with the adversary (the agent code).
2. **Trusted-Verify (Server):** Because it is the system's "root of trust" for ingestion. We trust the server to verify the client, but we verify the server's work via the chain.
3. **Independent (Verifier):** Because it is the final auditor. It has no skin in the game and no state to protect.

---

## 6. Formal Verification Logic

The Verifier implements the following logic to enforce these invariants:

```python
def verify_authority(event, expected_authority):
    actual_authority = event.get("chain_authority", "sdk")
    if actual_authority != expected_authority:
        return FAIL, f"Authority mismatch: expected {expected_authority}, got {actual_authority}"
    
    # Check if event type is allowed for this authority
    if actual_authority == "sdk" and event["event_type"] in SERVER_TYPES:
        return FAIL, f"SDK spoofing server event: {event['event_type']}"
    
    return PASS

def verify_session(events):
    # Principal Check
    for event in events:
        if event["event_type"] == "CHAIN_SEAL":
            if not verify_authority(event, "server"): return FAIL
        else:
            if not verify_authority(event, "sdk"): return FAIL
            
    # Independence Check
    # (Verified by running in isolated environment)
    return PASS
```

## 7. Strategic Importance of Invariants

These invariants transform AgentOps Replay from a simple logging tool into a cryptographic system of record. By strictly separating the producer of the data (the SDK) from the authority that certifies its integrity (the Ingestion Service), we create a check-and-balance system.

Even if an attacker gains control of the SDK, they cannot seal the chain. Even if an attacker gains control of the server, they cannot modify the SDK's history without breaking the cryptographic linkage that is verifiable by the independent auditor. This "defense in depth" through authority separation is the core research contribution of this work.

## 8. Compliance Mapping

| Requirement | Implementation | Invariant |
| :--- | :--- | :--- |
| **Auditability** | Hash Chain | Invariant 2 |
| **Non-Repudiation** | Server Authority | Invariant 1 |
| **Integrity** | Standalone Verifier | Invariant 3 |

By adhering to these invariants, AgentOps Replay meets the "Authoritative System of Record" requirements for AI agent deployments in regulated industries.
