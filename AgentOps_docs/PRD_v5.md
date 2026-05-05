# AgentOps Replay — Product Requirements Document (v5.0)

> **Status:** Active — Single Source of Truth  
> **Replaces:** PRD v4.0 and all prior versions  
> **Rule:** If it's not in this document, it doesn't exist yet.  
> **Last Updated:** May 2026

---

## 1. Product Identity

### 1.1 What This Product Is

AgentOps Replay is an **open-source accountability layer for AI agents**. It records everything an AI agent does — every LLM call, every tool invocation, every result — into a cryptographically hash-chained, append-only event log. A standalone verifier can then prove the log is complete and unmodified. That proof is what makes the log evidence rather than just debugging output.

### 1.2 What "Evidence" Means Here

A standard application log says "this happened." An AgentOps Replay log says "this happened, in this order, and I can prove no one has modified or deleted anything since." The difference is the cryptographic chain — each event contains the hash of the previous event, making tampering detectable by anyone with the verifier.

### 1.3 What This Product Is Not

- Not an observability dashboard (no charts, no UI in v1.0)
- Not a policy engine or guardrails system
- Not an LLM evaluation or prompt optimization tool
- Not a compliance certification (it produces evidence toward compliance; it does not certify)
- Not a vendor-controlled black box (open source core, open specification, open verifier)

---

## 2. Three Audiences, Three Value Propositions

This product serves three distinct audiences simultaneously. Understanding which audience you're talking to determines how you describe the product.

### 2.1 Audience A: Enterprise Security Teams

**Who:** CISOs, security architects, and compliance engineers at Fortune 1000 companies deploying AI agents in regulated industries (finance, healthcare, legal, insurance, government contracting).

**Their Problem:** AI agents are running in production, touching sensitive data, making consequential decisions — and the logs that record this activity are mutable, vendor-controlled, and cannot be independently verified. When an incident occurs, or when an auditor asks for evidence, they have nothing admissible.

**What They Need:** An accountability layer that is architecturally independent from the vendor, produces cryptographically verifiable event chains, maps to EU AI Act / NIST AI RMF / ISO 42001 requirements, and can be verified by a neutral third party.

**Why They Can't Build This:** Getting cryptographic chain integrity right requires specialized expertise. Building a standalone independent verifier (by definition separate from the system being audited) requires sustained engineering investment. Most importantly: building a proprietary internal system cannot create the neutral ground that external auditors, regulators, and counterparties require.

**Their Value Proposition:** "Your AI agent's actions are now independently verifiable evidence. Your auditor can run the verifier themselves. Your lawyers can reference a formal specification. Your regulators can see the chain of what happened."

### 2.2 Audience B: Open-Source / Self-Hosted AI Users

**Who:** Developers, researchers, and small/medium teams using self-hosted AI infrastructure: Open WebUI, LibreChat, LangChain, CrewAI, AutoGen. They chose self-hosting because they don't want their data going to cloud providers.

**Their Problem:** Their self-hosted AI systems have zero audit infrastructure. They can see what their agents output but have no way to reconstruct what happened in between. Multi-agent pipelines are especially blind — the communication between agents is completely unmonitored. If something goes wrong, they have no evidence.

**What They Need:** A lightweight, self-hostable accountability layer with zero cloud dependencies. Something they can run locally with one Docker command, instrument with three lines of Python, and use to prove their agent did what they think it did.

**Why They Can't Build This:** JCS canonicalization is non-trivial to implement correctly. The failure semantics (LOG_DROP when buffer fills) require explicit design. The independent verifier requires careful packaging. Getting this wrong means the logs appear valid but can actually be modified without detection.

**Their Value Proposition:** "Add cryptographic proof to your self-hosted AI setup. Nothing leaves your machine. Run the verifier yourself. No account required."

### 2.3 Audience C: Researchers and Academic Community

**Who:** Researchers working on AI agent safety, accountability, governance, and security. Looking for prior work in their area and for reference implementations to build on or compare against.

**Their Problem:** The existing literature on AI agent accountability is fragmented. Multiple papers propose theoretical frameworks but few provide both a formal specification and a working reference implementation evaluated on production frameworks.

**What They Need:** A formally specified, open, evaluable system with published test vectors, reproducible benchmarks, and a clear positioning against related work.

**Their Value Proposition:** "A formally specified event log with authority separation, evidence classification, and LOG_DROP semantics — the first to address the accountability gap under failure conditions. Open spec, open implementation, open verifier. Build on it or compare against it."

---

## 3. The Four Core Components

Everything in this product maps to exactly one of these four components. No exceptions. No new components without updating this document.

### 3.1 Component 1: SDK (`agentops_sdk/`)

**Definition:** A Python library that runs inside the agent's process. It records events into a local ring buffer, constructs the hash chain, and can output to a JSONL file (local authority mode) or POST to the Ingestion Service (server authority mode).

**Users:** Agent developers — they import and use this in their code.

**Core design principle:** The SDK must never crash the agent process. If something goes wrong — buffer overflow, network failure, exception in hash computation — the SDK handles it silently and records a LOG_DROP event. The agent continues.

**Key behaviors:**
- Records the complete event chain: SESSION_START through SESSION_END
- Assigns monotonically increasing sequence numbers starting at 1
- Computes prev_hash → event_hash chain using JCS + SHA-256
- On buffer overflow: emits LOG_DROP (never silently discards)
- On network failure to server: retries 3 times, then records ConnectionError in session metadata
- Thread-safe buffer suitable for multi-threaded agent architectures

**What the SDK does NOT do:**
- Modify events after they are accepted into the buffer
- Skip sequence numbers
- Invent events that didn't happen
- Block the agent process under any failure condition

### 3.2 Component 2: Verifier (`verifier/`)

**Definition:** A standalone CLI tool that validates an exported session JSONL file. It recomputes the hash chain, checks sequence ordering, determines evidence class, and reports PASS or FAIL with specific reasons. It has zero external dependencies.

**Users:** Anyone — agent developers, security teams, auditors, regulators, legal teams, counterparties. The point is that anyone can run this without trusting AgentOps.

**Core design principle:** Independence. The verifier must be runnable by a third party on an air-gapped machine with only a Python 3.11+ installation. It must produce deterministic output for the same input. It must never require network access.

**Key behaviors:**
- Parses JSONL, validates every event field
- Recomputes hash chain from scratch
- Checks: sequence monotonicity, prev_hash chain, hash correctness, SESSION_START/END presence
- Determines and reports evidence class
- Reports detailed failure information (which event, which field, what was expected vs. found)
- Exit code 0 = PASS, 1 = FAIL, 2 = ERROR (bad file, parse error)

**What the verifier does NOT do:**
- Require network access
- Modify the file
- Produce different output on different machines for the same input
- Import any package that requires pip install

### 3.3 Component 3: Ingestion Service (`backend/`)

**Definition:** A Python HTTP server (FastAPI) that receives event batches from the SDK, re-verifies the hash chain server-side, persists events to an append-only PostgreSQL store, and emits a CHAIN_SEAL on session completion. This is the component that upgrades a log from NON_AUTHORITATIVE to AUTHORITATIVE evidence.

**Users:** Agent developers who want AUTHORITATIVE evidence (required for compliance use). Also enterprise security teams who need a centralized, governed audit store.

**Core design principle:** Fail closed for integrity. A partial write that corrupts the chain is worse than a rejected batch. The server must operate atomically — accept all events in a batch, or reject all of them. No partial success.

**Key behaviors:**
- Validates event structure on receipt
- Re-computes hash chain server-side (does not trust SDK-computed hashes)
- Detects sequence gaps → emits CHAIN_BROKEN event
- Persists atomically (all-or-nothing per batch, using DB transactions)
- Emits CHAIN_SEAL when SESSION_END arrives — this is the server's cryptographic stamp of approval
- Exports complete sessions as JSONL via GET endpoint
- Append-only storage enforced at DB permission level (INSERT + SELECT only, no UPDATE or DELETE)

**What the ingestion service does NOT do:**
- Accept mutations to existing events
- Silently drop events (always records LOG_DROP or CHAIN_BROKEN)
- Write partial batches
- Trust SDK-computed hash values (always recomputes independently)

### 3.4 Component 4: Integrations (`sdk/python/agentops_replay/integrations/`)

**Definition:** Pre-built adapters for popular AI frameworks that automatically instrument them without requiring manual event recording in the user's code.

**Current (v1.0):** LangChain callback handler.

**Users:** Developers using specific frameworks who want zero-instrumentation setup.

**Core design principle:** An integration is a thin wrapper over the SDK. It maps framework-specific events to the standard event types. It should not contain logic that belongs in the SDK or Ingestion Service.

**v1.0 integrations:** LangChain only.
**v2.0 target integrations:** CrewAI, AutoGen/Microsoft Agents, Open WebUI Pipeline.

---

## 4. The Event Schema (Frozen)

### 4.1 Event Envelope

Every event produced by any component has this exact structure. These field names and types are frozen — changing them requires a major version and migration document.

```json
{
  "seq": 1,
  "event_type": "TOOL_CALL",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-05-05T10:30:00.000000Z",
  "payload": { },
  "prev_hash": "a3f1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1",
  "event_hash": "b4g2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2"
}
```

**Field definitions:**
- `seq`: Integer. Monotonically increasing from 1. Never skipped. Never duplicated within a session.
- `event_type`: String. One of the allowed types defined in §4.2.
- `session_id`: String. UUID v4. Same value for every event in a session.
- `timestamp`: String. ISO 8601 UTC with microsecond precision. Format: `"YYYY-MM-DDTHH:MM:SS.ffffffZ"`.
- `payload`: Object. Event-specific data. See §4.3 for payload schemas per event type.
- `prev_hash`: String. 64-character lowercase hex SHA-256 digest. For seq=1: `"0" * 64`. For all others: the `event_hash` of the previous event.
- `event_hash`: String. 64-character lowercase hex SHA-256 digest of the event's JCS canonical form (with `event_hash` field excluded from the hash input).

### 4.2 Allowed Event Types

**SDK-produced events (authority: SDK):**

| Type | When Emitted | Authority |
|---|---|---|
| `SESSION_START` | When `client.start_session()` is called | SDK |
| `SESSION_END` | When `client.end_session()` is called | SDK |
| `LLM_CALL` | Before each LLM inference request | SDK |
| `LLM_RESPONSE` | After each LLM inference response | SDK |
| `TOOL_CALL` | Before each tool invocation | SDK |
| `TOOL_RESULT` | After successful tool invocation | SDK |
| `TOOL_ERROR` | After failed tool invocation | SDK |
| `LOG_DROP` | When events cannot be captured (buffer overflow) | SDK |

**Server-produced events (authority: Server):**

| Type | When Emitted | Authority |
|---|---|---|
| `CHAIN_SEAL` | When SESSION_END arrives at ingestion service | Server only |
| `CHAIN_BROKEN` | When sequence gap detected by ingestion service | Server only |
| `REDACTION` | When PII redaction is applied to a field | Server only |
| `FORENSIC_FREEZE` | When a session is frozen for incident investigation | Server only |

**Rules:**
- An SDK must never produce a server-authority event
- A server must never modify SDK-produced events
- The Verifier must flag any CHAIN_SEAL or CHAIN_BROKEN present in a file that lacks a corresponding server signature (future: when signing is added)

### 4.3 Payload Schemas Per Event Type

**SESSION_START:**
```json
{
  "agent_id": "string (required)",
  "agent_version": "string (semver, optional)",
  "model_id": "string (required, e.g., 'claude-sonnet-4-6')",
  "model_provider": "string (required, e.g., 'anthropic')",
  "prompt_version": "string (optional)",
  "framework": "string (optional, e.g., 'langchain')",
  "framework_version": "string (optional)",
  "tools": [{"name": "string", "version": "string"}],
  "policy_version": "string (optional)",
  "environment": "string (optional, 'production' | 'staging' | 'development')",
  "parent_session_id": "string (optional, UUID v4, for multi-agent lineage)",
  "agent_role": "string (optional, 'orchestrator' | 'subagent' | 'tool')"
}
```

**SESSION_END:**
```json
{
  "status": "string (required, 'success' | 'failure' | 'error' | 'timeout')",
  "duration_ms": "integer (optional)",
  "final_tool_call_seq": "integer (optional, seq of last TOOL_CALL if any)",
  "exit_reason": "string (optional)"
}
```

**LLM_CALL:**
```json
{
  "model_id": "string (required)",
  "prompt_hash": "string (SHA-256 of prompt content — never store raw prompt)",
  "prompt_token_count": "integer (required)",
  "temperature": "number (optional)",
  "max_tokens": "integer (optional)",
  "system_prompt_hash": "string (SHA-256 of system prompt, optional)"
}
```

**LLM_RESPONSE:**
```json
{
  "model_id": "string (required)",
  "content_hash": "string (SHA-256 of response content — never store raw response)",
  "completion_token_count": "integer (required)",
  "total_token_count": "integer (optional)",
  "finish_reason": "string (optional, 'stop' | 'length' | 'tool_calls' | 'error')",
  "latency_ms": "integer (optional)"
}
```

**TOOL_CALL:**
```json
{
  "tool_name": "string (required)",
  "tool_version": "string (optional)",
  "args_hash": "string (SHA-256 of serialized args — store hash, not args, for privacy)",
  "args_summary": "string (short human-readable description, optional)",
  "call_id": "string (optional, for correlating with TOOL_RESULT)"
}
```

**TOOL_RESULT:**
```json
{
  "tool_name": "string (required)",
  "call_id": "string (correlates with TOOL_CALL.call_id, optional)",
  "result_hash": "string (SHA-256 of serialized result)",
  "result_summary": "string (short human-readable description, optional)",
  "latency_ms": "integer (optional)"
}
```

**TOOL_ERROR:**
```json
{
  "tool_name": "string (required)",
  "call_id": "string (optional)",
  "error_type": "string (required, e.g., 'TimeoutError', 'PermissionError')",
  "error_message": "string (required, sanitized — no PII)",
  "latency_ms": "integer (optional)"
}
```

**LOG_DROP:**
```json
{
  "count": "integer (required, number of dropped events)",
  "reason": "string (required, 'BUFFER_OVERFLOW' | 'NETWORK_FAILURE' | 'SERIALIZATION_ERROR')",
  "seq_range_start": "integer (required, first dropped seq number)",
  "seq_range_end": "integer (required, last dropped seq number)",
  "buffer_size_at_drop": "integer (optional)"
}
```

**CHAIN_SEAL:**
```json
{
  "final_hash": "string (event_hash of the SESSION_END event)",
  "event_count": "integer (total events in the session including this CHAIN_SEAL)",
  "server_timestamp": "string (ISO 8601 UTC)",
  "authority": "string ('ingestion_service')",
  "server_version": "string (version of the ingestion service that sealed this)"
}
```

**CHAIN_BROKEN:**
```json
{
  "expected_seq": "integer (what the server expected next)",
  "received_seq": "integer (what the server actually received)",
  "gap_size": "integer (expected - received, may be negative for overlap)",
  "detection_method": "string ('sequence_gap' | 'hash_mismatch')"
}
```

---

## 5. The Authority Model

### 5.1 Why Authority Separation Matters

The SDK runs inside the agent's process. If the agent is compromised, the SDK is compromised. A compromised SDK could inject false events, delete events, or reorder them. This is the fundamental problem with purely client-side audit systems.

The solution is to make the server-authoritative layer independent. The Ingestion Service runs separately, re-computes the hash chain independently (it does not trust the SDK's hash values), and only emits CHAIN_SEAL after successful independent verification. A CHAIN_SEAL means: "This server has independently verified the event sequence."

### 5.2 Trust Levels

| Component | Trust Level | Reason |
|---|---|---|
| SDK | Untrusted | Runs in agent process; could be compromised |
| Agent Process | Untrusted | Produces the events; has conflict of interest |
| Ingestion Service | Trusted (verify) | Separate process; re-verifies; append-only DB |
| Append-Only Storage | Trusted (by design) | DB-level enforcement; application cannot mutate |
| Verifier | Independent | Runs anywhere; no connection to the system |

### 5.3 What Each Trust Level Implies

**Untrusted (SDK):**
- Server re-computes all hashes independently
- Server does not accept SDK claims about sequence numbers without verification
- Server detects and records any discrepancy

**Trusted (verify) (Ingestion Service):**
- Server is the authority for CHAIN_SEAL
- Server is the authority for CHAIN_BROKEN
- Server is the authority for REDACTION and FORENSIC_FREEZE
- Server's append-only DB is the ground truth for sealed sessions

**Independent (Verifier):**
- Can be run by any party
- Requires no connection to any AgentOps infrastructure
- Produces the same result as any other correctly implemented ELS verifier

---

## 6. Evidence Classification

### 6.1 The Three Classes

| Class | Conditions | Suitable For |
|---|---|---|
| `AUTHORITATIVE_EVIDENCE` | CHAIN_SEAL present AND no LOG_DROP events | Legal proceedings, regulatory compliance, external audit |
| `PARTIAL_AUTHORITATIVE_EVIDENCE` | CHAIN_SEAL present AND LOG_DROP events present | Internal audit, incident investigation, root cause analysis |
| `NON_AUTHORITATIVE_EVIDENCE` | No CHAIN_SEAL (SDK-only / local mode) | Development, debugging, testing |

### 6.2 Implications of Each Class

**AUTHORITATIVE_EVIDENCE** means:
- An independent server has verified and sealed the chain
- No events were lost (no LOG_DROP)
- The chain is complete from SESSION_START to CHAIN_SEAL
- Any tampering after sealing is detectable by the Verifier
- This is the class that matters for compliance and legal use

**PARTIAL_AUTHORITATIVE_EVIDENCE** means:
- A server sealed the chain, so the captured events are verified
- But some events were dropped (LOG_DROP present)
- The exact content of the dropped events is unknown
- The chain is verifiably complete for the events it contains, but not for all agent actions

**NON_AUTHORITATIVE_EVIDENCE** means:
- Only the SDK was involved; no server verification occurred
- The SDK could have been compromised
- The chain could have been generated after the fact
- Useful for development and debugging, not for compliance

### 6.3 How to Achieve Each Class

| Class | What You Need | How |
|---|---|---|
| NON_AUTHORITATIVE | SDK only | `flush_to_jsonl()` |
| PARTIAL_AUTHORITATIVE | SDK + Server + any LOG_DROP | `send_to_server()` — chain sealed but some events dropped |
| AUTHORITATIVE | SDK + Server + no drops | `send_to_server()` with `buffer_size` large enough for session |

---

## 7. Failure Semantics

These are architectural invariants. They must hold under all conditions.

### 7.1 Fail Open for Agents (SDK)

The agent must never be blocked by AgentOps Replay. If the SDK fails for any reason — buffer overflow, hash computation error, network partition, disk full — the agent continues running. The SDK handles the failure internally and records what happened (LOG_DROP or similar).

**Implementation:** All SDK methods are wrapped in try/except. No exception propagates to the caller.

### 7.2 Fail Closed for Integrity (Ingestion Service)

The Ingestion Service must never write a partial batch. Either all events in a batch are persisted, or none are. A partial write would produce a chain that appears valid but is missing events.

**Implementation:** All batch persistence is wrapped in a DB transaction. On any failure, the transaction is rolled back. The SDK receives a 500 error and can retry the full batch.

### 7.3 LOG_DROP Semantics

When the SDK cannot capture an event (buffer overflow is the primary case), it must:
1. Note the sequence range of dropped events
2. Emit a LOG_DROP event in the chain
3. Continue the chain from the LOG_DROP event

The LOG_DROP is itself part of the chain — it has a seq number, prev_hash, and event_hash like any other event. This means: even in failure mode, the chain remains verifiable. The Verifier can detect LOG_DROP events and report `PARTIAL_AUTHORITATIVE_EVIDENCE`.

**What is never acceptable:** Silently skipping events. A gap in sequence numbers without a corresponding LOG_DROP event is a chain integrity violation.

### 7.4 Data Loss vs. Data Corruption

Data loss is acceptable; data corruption is not.

- **Acceptable:** A LOG_DROP event records that 50 events were lost
- **Unacceptable:** An event appears in the chain with a forged hash that makes it appear valid when it isn't
- **Acceptable:** The Ingestion Service rejects a batch due to network error (no write occurs)
- **Unacceptable:** The Ingestion Service writes 7 of 10 events and then crashes (partial write)

---

## 8. Privacy Design

### 8.1 What Is Never Stored Verbatim

- LLM prompt content → stored as SHA-256 hash only
- LLM response content → stored as SHA-256 hash only
- Tool arguments → stored as SHA-256 hash only
- Tool results → stored as SHA-256 hash only
- User identity → stored as SHA-256 hash only (optional field)

**Rationale:** The event chain is evidence of what happened, not a transcript of what was said. Hashes allow correlation ("was the same prompt used in two sessions?") without exposing content.

### 8.2 PII Redaction

For fields that do end up containing PII (e.g., error messages, args_summary), the server can apply a REDACTION operation:

- Original field value is replaced with `"REDACTED:sha256:<hash>"`
- A REDACTION event is emitted, recording which field in which event was redacted
- The hash allows correlation without re-exposure
- REDACTION is irreversible — no unredaction endpoint exists
- The chain integrity is preserved after redaction (the REDACTION event is part of the chain)

### 8.3 Local Authority Mode as Privacy Guarantee

In local authority mode (default), nothing leaves the machine. The JSONL file stays local. This is the key feature for self-hosted users who chose self-hosting precisely because they don't want data leaving their infrastructure.

---

## 9. Regulatory Alignment

This section explains how AgentOps Replay's components map to regulatory requirements. This is informational — not a compliance certification.

### 9.1 EU AI Act

| Article | Requirement | AgentOps Component |
|---|---|---|
| Article 12 | Record-keeping for high-risk AI | AUTHORITATIVE_EVIDENCE chains |
| Article 13 | Transparency and information provision | Deployment fingerprint in SESSION_START |
| Article 14 | Human oversight | APPROVAL_GRANTED / APPROVAL_DENIED events (v2.0) |
| Article 15 | Cybersecurity | Complete tool call chain with hash integrity |
| Article 73 | Incident reporting | FORENSIC_FREEZE event (enterprise tier) |

### 9.2 NIST AI RMF

| Function | Requirement | AgentOps Component |
|---|---|---|
| GOVERN | Establish AI risk governance | Deployment fingerprint, session metadata |
| MAP | Identify AI risks | LOG_DROP, CHAIN_BROKEN events |
| MEASURE | Measure AI risks | Evidence classification, verification output |
| MANAGE | Manage AI risks | FORENSIC_FREEZE, compliance report (enterprise) |

### 9.3 ISO/IEC 42001

| Clause | Requirement | AgentOps Component |
|---|---|---|
| 8.4 | AI system operational controls | TOOL_CALL + TOOL_RESULT chain |
| 9.1 | Non-repudiation | CHAIN_SEAL + independent Verifier |
| 10.1 | Continual improvement records | Session history with evidence class |

---

## 10. Scope Definition: What Gets Built When

### 10.1 v1.0 Scope (Current Target)

**Must have for launch:**
- SDK with all 8 SDK event types working
- Verifier with all validation checks + evidence class reporting
- Ingestion Service with POST /v1/ingest and GET /v1/sessions/{id}/export
- LangChain integration producing verifiable JSONL
- Docker-compose local setup working
- `pip install agentops-replay` working
- README quickstart that works in under 10 minutes
- Three test vectors (valid, tampered, sequence_gap) all producing correct Verifier output
- CI passing on all three test vectors

**Explicitly excluded from v1.0:**
- Web UI or dashboard
- SIEM webhooks
- Forensic Freeze endpoint
- Compliance report generation
- PII redaction endpoint
- Role-based access control
- CrewAI / AutoGen / Open WebUI integrations
- Go or Rust verifier port

### 10.2 v1.1 Scope (Enterprise Tier — 6-8 weeks post launch)

- SIEM webhook delivery (CEF/LEEF format)
- Forensic Freeze endpoint
- PII redaction with integrity preservation
- API key authentication for Ingestion Service
- Basic compliance report (JSON format, EU AI Act / NIST mapping)

### 10.3 v1.2 Scope (Community Tier — 3-4 months post launch)

- Open WebUI Pipeline plugin
- CrewAI callback integration
- Multi-agent session lineage (parent_session_id)
- Simple local web dashboard (read-only, localhost only)

### 10.4 v2.0 Scope (Formal Research / Journal)

- Formal specification document (ELS v1.0 as a citable document)
- Comprehensive benchmarking suite
- AutoGen integration
- Adversarial test suite covering the four adversary models

---

## 11. Success Metrics

### 11.1 v1.0 Launch Success

- A developer unfamiliar with the codebase can follow the README and achieve PASS ✅ in under 10 minutes
- The verifier correctly identifies all three test vector cases (valid, tampered, gap)
- LangChain demo produces AUTHORITATIVE_EVIDENCE when using the Ingestion Service
- No sensitive data (API keys, PII, passwords) in any committed file
- CI passes on every push to main

### 11.2  30-Day Post-Launch Success

- GitHub stars: 200+ (indicates community discovery)
- At least one external issue filed (indicates someone used it)
- Verifier download count: 50+ (indicates standalone verifier is being used)

### 11.3 Research Success

- Conference paper accepted at IEEE/ACM venue
- Journal submission with 30%+ new technical content beyond conference paper
- All experiments reproducible from artifact package

---

## 12. Constraints and Guardrails

### 12.1 Non-Negotiable Constraints

1. **Python 3.11+ only.** Float representation changed in 3.11; pinning to 3.11+ ensures hash determinism across machines.

2. **JCS (RFC 8785) for canonicalization.** Do not use `json.dumps(sort_keys=True)` or any other serialization. JCS defines the canonical form used for hash computation. Any deviation from JCS produces hashes that will not match the Verifier.

3. **SHA-256 for hashing.** Do not change the hash algorithm. Changing it requires a major version.

4. **Append-only storage enforced at DB permission level.** Application-level enforcement (no UPDATE in code) is insufficient; it must be enforced by the database user's permissions.

5. **Verifier must have zero dependencies.** Any external dependency makes it non-neutral. A verifier that requires `pip install` can be tampered with by manipulating the installed package.

### 12.2 Decisions That Are Allowed to Change

- SDK ergonomics (method names, parameter names)
- Ingestion Service internal implementation (storage engine, API framework)
- LangChain integration implementation details
- Docker/deployment configuration
- Performance optimizations

### 12.3 Decisions That Are Frozen Forever

- Event envelope field names and types
- Allowed event_type values
- Hash computation algorithm
- Evidence classification conditions
- Authority model (which components produce which event types)
- Meaning of AUTHORITATIVE_EVIDENCE, PARTIAL_AUTHORITATIVE_EVIDENCE, NON_AUTHORITATIVE_EVIDENCE

---

*PRD v5.0 — Last Updated May 2026*  
*This document supersedes all previous PRD versions.*  
*Constitutional violations invalidate all derived work. This PRD does not violate the Constitution.*
