# AgentOps Replay — Product Requirements Document (v2.0)

## 1. Product Overview

### 1.1 Product Name

**AgentOps Replay**

### 1.2 One‑Line Description

AgentOps Replay is the **mandatory system of record for AI agent behavior**, providing immutable, cryptographically verifiable, replayable evidence of what an AI agent did, in what order, and with what external effects—because when agents fail, speculation is not an option.

### 1.3 Product Category

- Critical Evidence Infrastructure
- AI Governance & Accountability (Required)
- Incident Response & Audit Systems (Authoritative)

> AgentOps Replay is **not** an observability dashboard, experimentation platform, or evaluation framework. It is the foundational evidence layer that these tools depend on.

---

## 2. The Inevitability Problem

### 2.1 The Reality

AI agents **will** cause incidents. This is not a question of if, but when.

Today's agents:

- Execute financial transactions
- Modify production databases
- Send customer communications
- Access sensitive records
- Make irreversible decisions

When (not if) they:

- Leak PII or trade secrets
- Execute unauthorized transactions
- Cause regulatory violations
- Delete critical data
- Make discriminatory decisions

**You will be asked: "What exactly happened?"**

And you will have no defensible answer.

### 2.2 Why Current Solutions Fail

Every existing approach breaks under pressure:

| Approach                  | Fatal Flaw                                                |
| ------------------------- | --------------------------------------------------------- |
| Application logs          | Mutable, incomplete, reorderable                          |
| LLM provider logs         | Missing tool calls, redacted content, provider-controlled |
| Observability platforms   | Sampling, aggregation, inference-based reconstruction     |
| Manual transcripts        | Non-verifiable, post-hoc narratives                       |
| "We'll just reproduce it" | Non-deterministic systems cannot be reproduced            |

**When your CFO, CISO, or legal counsel asks for evidence, approximations end careers.**

### 2.3 The Gap

There is currently **no system of record** for agent behavior that can withstand:

- Legal discovery
- Security forensics
- Regulatory audit
- Insurance claims
- Root cause analysis

AgentOps Replay exists because this gap is unacceptable.

---

## 3. Goals and Non‑Goals

### 3.1 Product Goals (Non-Negotiable)

The system MUST:

- **Produce append‑only, tamper‑evident event logs** — Any modification is cryptographically detectable
- **Enable deterministic replay** — Reproduce exact agent behavior, not approximations
- **Support independent verification** — Third parties can validate integrity without trusting us
- **Survive adversarial scrutiny** — Legal, security, and compliance challenges
- **Fail loudly and safely** — Never silently lose critical evidence

### 3.2 Explicit Non‑Goals

The system WILL NOT:

- Interpret agent intent (we record facts, not narratives)
- Judge decision correctness (we provide evidence for others to judge)
- Optimize prompts or models (use evaluation tools for that)
- Store chain‑of‑thought by default (legal liability)
- Claim regulatory certification (we provide evidence for certification)
- Make incidents less likely (we make investigation possible)

---

## 4. Target Users

### 4.1 Primary Users (Decision Makers)

- **Chief Information Security Officers** — Need forensic evidence for breaches
- **General Counsel / Legal Teams** — Need defensible evidence for litigation
- **Compliance Officers** — Need audit trails for regulators
- **Incident Response Teams** — Need accurate timelines for post-mortems

### 4.2 Implementation Users

- **Platform Engineers** — Integrate and operate the system
- **AI Infrastructure Teams** — Deploy agents with evidence collection
- **Security Engineers** — Investigate incidents using replay
- **Internal Audit Teams** — Validate controls and evidence

### 4.3 Anti‑Users (Not Optimized For)

- Prompt engineers seeking fast iteration (use dev tools)
- Pure research workflows (use notebooks)
- Dashboard-first observability users (use APM tools)

**Critical Distinction:** These users still _need_ AgentOps Replay as foundational infrastructure—they just interact with it indirectly.

---

## 5. Core Value Proposition

### 5.1 By Stakeholder

| Stakeholder            | Without AgentOps Replay                                                            | With AgentOps Replay                                                                                 |
| ---------------------- | ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| **CISO**               | "We think the agent accessed customer data, but logs were rotated"                 | "Here is cryptographically verified evidence of every data access, with timestamps and full context" |
| **Legal**              | "Our vendor claims the agent didn't send that email, but we can't prove otherwise" | "Here is the immutable event chain showing the exact prompt, tool call, and response"                |
| **Compliance**         | "The auditor rejected our incident report because we couldn't verify the timeline" | "Here is an independently verifiable export that passed cryptographic verification"                  |
| **Engineering**        | "We can't reproduce the bug because the agent was non-deterministic"               | "Here is a deterministic replay showing exactly what the agent did"                                  |
| **Board / Executives** | "We face regulatory penalties because we cannot document AI system behavior"       | "We have forensic-grade evidence infrastructure for all AI agents"                                   |

### 5.2 The Institutional Memory Principle

Once AgentOps Replay is used in **one critical incident**, it becomes permanently embedded in your organization's risk management framework.

It transitions from "infrastructure" to "institutional requirement."

---

## 6. Why This Must Be Mandatory

### 6.1 The Opt-In Fallacy

Optional compliance tools fail because:

- They're disabled under pressure ("slows us down")
- They're enabled too late ("we didn't think we'd need it")
- They're inconsistently applied ("only on production agents")
- They're removed during incidents ("it's probably not important")

**By the time you know you need evidence, it's too late to collect it.**

### 6.2 The Cost of Absence

Without AgentOps Replay, organizations face:

- **Legal liability** — Inability to defend against claims
- **Regulatory penalties** — Failure to demonstrate controls
- **Insurance exclusions** — Policies require incident documentation
- **Reputational damage** — Public incidents without explanations
- **Operational paralysis** — Cannot safely deploy agents at scale

### 6.3 The Mandate

AgentOps Replay should be:

- **Required by security policy** (like audit logging)
- **Enforced at infrastructure level** (like TLS)
- **Non-bypassable by developers** (like authentication)
- **Verified in CI/CD** (like security scans)

It is not a feature. It is a control.

---

## 7. System Architecture (High‑Level)

```text
┌─────────────────────────────────────────────────────────┐
│                   Untrusted Agent Runtime                │
│  ┌──────────────────────────────────────────────────┐  │
│  │          AgentOps SDK (Untrusted Producer)        │  │
│  │   • Ring buffer                                   │  │
│  │   • Best-effort transmission                      │  │
│  │   • Explicit drop events                          │  │
│  │   • NEVER emits CHAIN_SEAL                        │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                            │
                            │ (Untrusted events)
                            ▼
┌─────────────────────────────────────────────────────────┐
│              Ingestion Service (Authoritative)           │
│  • Recomputes all hashes server-side                    │
│  • Establishes total ordering                           │
│  • Emits cryptographic CHAIN_SEAL                       │
│  • Rejects mixed authority                              │
└─────────────────────────────────────────────────────────┘
                            │
                            │ (Sealed events)
                            ▼
┌─────────────────────────────────────────────────────────┐
│          Append-Only Event Store (Immutable)             │
│  • Write-once storage                                    │
│  • Cryptographic integrity                               │
│  • Retention policies                                    │
└─────────────────────────────────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                ▼                       ▼
┌──────────────────────────┐ ┌─────────────────────────┐
│  Independent Verifier     │ │   Replay Engine         │
│  • Zero trust             │ │   • Read-only           │
│  • Detects tampering      │ │   • Deterministic       │
│  • Policy enforcement     │ │   • No inference        │
└──────────────────────────┘ └─────────────────────────┘
                │                       │
                ▼                       ▼
┌──────────────────────────────────────────────────────┐
│              Compliance & Evidence Exports            │
│  • JSON (canonical, verifiable)                       │
│  • PDF (human-readable, auditor-friendly)             │
│  • Chain-of-custody metadata                          │
└──────────────────────────────────────────────────────┘
```

**Trust Boundaries:**

- SDK → Ingestion: UNTRUSTED
- Ingestion → Store: AUTHORITATIVE
- Store → Verifier: VERIFIED
- Store → Replay: AUTHORITATIVE

---

## 8. Core Components & Requirements

### 8.1 Event Log & Constitution Layer

**Purpose:** Define immutable, non-negotiable system rules that cannot be violated without breaking the entire system.

**Hard Requirements:**

- Append‑only event model (deletions/updates invalidate the chain)
- Total ordering via monotonic sequence numbers
- Hash‑chained integrity (SHA-256 minimum)
- RFC 8785 canonical JSON serialization
- Explicit failure semantics (no silent degradation)

**Artifacts:**

- `CONSTITUTION.md` — Inviolable system rules
- `EVENT_LOG_SPEC.md` (v0.6+) — Technical specification
- `SCHEMA.md` — Event type definitions

**Enforcement:** Violations detected by the Verifier result in COMPLETE REJECTION of the event chain.

---

### 8.2 Authority Model & Evidence Classification

**Authority Types:**

1. **Server Authority (AUTHORITATIVE)**
   - Events sealed by Ingestion Service
   - Includes cryptographic CHAIN_SEAL
   - Suitable for compliance and legal use

2. **SDK / Local Authority (NON-AUTHORITATIVE)**
   - Events from agent runtime
   - No server seal
   - Development/debugging only

**Evidence Classes:**

| Class                            | Description                     | Use Case                                |
| -------------------------------- | ------------------------------- | --------------------------------------- |
| `AUTHORITATIVE_EVIDENCE`         | Server-sealed, complete chain   | Production incidents, compliance, legal |
| `PARTIAL_AUTHORITATIVE_EVIDENCE` | Server-sealed, incomplete chain | Degraded operations, partial recovery   |
| `NON_AUTHORITATIVE_EVIDENCE`     | SDK-only, no seal               | Development, testing, simulation        |

**Hard Requirements:**

- Authority MUST be cryptographically distinguishable (not just metadata)
- Server authority MUST include CHAIN_SEAL event type
- SDK authority MUST never be mistaken for production evidence
- Evidence class MUST appear in all exports, reports, and UI
- Mixed authority in a single chain MUST be rejected

**Why This Matters:** In legal proceedings, non-authoritative evidence can be dismissed as fabricated. Clear classification prevents catastrophic misuse.

---

### 8.3 SDK (Untrusted Producer)

**Purpose:** Emit events from agent runtime without blocking execution or assuming trust.

**Design Philosophy:** The SDK is **adversarial by design**. It may be:

- Buggy
- Malicious
- Compromised
- Misconfigured
- Running in a hostile environment

**Hard Requirements:**

- **Untrusted by design** — Server MUST re-verify everything
- **Local ring buffer** — Bounded memory (prevent OOM attacks)
- **Explicit LOG_DROP events** — Lost data MUST be recorded
- **Retry with exponential backoff** — Network resilience
- **Kill‑switch via environment variable** — Emergency disable
- **Redaction with hash preservation** — PII removal without breaking chains
- **MUST NOT emit CHAIN_SEAL** — Only server can seal
- **Fail open for agents** — Never crash the agent process
- **Fail closed for integrity** — Never silently lose events

**Failure Philosophy:**

```text
Agent crashes → Acceptable (business continuity)
Silent data loss → NEVER ACCEPTABLE (evidence integrity)
```

**Implementation Requirements:**

```python
# SDK MUST implement
class AgentOpsSDK:
    def __init__(self, api_key: str, buffer_size: int = 10000):
        self.buffer = RingBuffer(buffer_size)
        self.dead = os.getenv("AGENTOPS_KILL_SWITCH") == "1"

    def record(self, event: Event) -> None:
        if self.dead:
            return  # Fail open

        if self.buffer.is_full():
            dropped = self.buffer.oldest()
            self.buffer.add(LogDropEvent(dropped_event_id=dropped.id))

        self.buffer.add(event)
        self.async_send()  # Non-blocking
```

---

### 8.4 Ingestion Service (Authoritative)

**Purpose:** Establish server authority, enforce ordering, and seal event chains.

**Hard Requirements:**

- **Recompute chain hashes server‑side** — Never trust SDK hashes
- **Reject mixed authority** — SDK-sealed events MUST be rejected
- **Emit CHAIN_SEAL events** — Cryptographic finalization
- **Never reorder events** — Sequence violations MUST reject the batch
- **Append‑only writes** — No updates, no deletes
- **Atomic batch commits** — All events or none
- **Monotonic sequence numbers** — Per session, globally unique

**Sealing Process:**

```text
1. Receive batch from SDK
2. Validate session_id, sequence continuity
3. Recompute hash chain (ignore SDK hashes)
4. Assign server timestamp
5. Append to immutable store
6. Emit CHAIN_SEAL(session_id, final_hash, count)
7. Return success
```

**Failure Modes:**

- Sequence gap → Reject batch, emit CHAIN_BROKEN event
- Hash mismatch → Reject batch, alert security team
- Duplicate sequence → Reject batch, possible replay attack
- Storage failure → Reject batch, trigger incident

**Why This Matters:** The Ingestion Service is the **single point of truth**. If it lies, the entire system is compromised.

---

### 8.5 Verifier (System Arbiter)

**Purpose:** Independently validate event chains without trusting any prior component.

**Design Philosophy:** The Verifier is **maximally paranoid**. It assumes:

- The SDK is compromised
- The Ingestion Service may have bugs
- The storage layer may be corrupted
- Humans will try to fake evidence

**Hard Requirements:**

- **Zero external dependencies** — Self-contained binary
- **Deterministic verification** — Same input → same output, always
- **Detect all integrity violations:**
  - Hash mismatches
  - Sequence gaps
  - Timestamp inconsistencies
  - Missing CHAIN_SEAL
  - Invalid evidence class
  - Mixed authority
- **Policy‑based rejection** — Configurable failure thresholds
- **Loud failures** — Non-zero exit codes, stderr output
- **No repairs** — Never "fix" broken chains

**Verification Algorithm:**

```text
1. Load event chain
2. Check for CHAIN_SEAL (required for AUTHORITATIVE)
3. Recompute hash chain from genesis
4. Compare computed vs. claimed hashes
5. Verify sequence monotonicity
6. Check timestamp ordering
7. Validate schema compliance
8. Apply policy rules
9. Exit 0 (valid) or 1 (invalid) with detailed report
```

**Policy Examples:**

```yaml
# policy.yaml
require_seal: true # Reject unsealed chains
max_sequence_gap: 0 # No gaps allowed
max_time_skew: 60s # Clock drift tolerance
allow_sdk_authority: false # Production only
```

**Output Format:**

```json
{
  "status": "INVALID",
  "evidence_class": "NON_AUTHORITATIVE_EVIDENCE",
  "violations": [
    {
      "type": "MISSING_SEAL",
      "severity": "CRITICAL",
      "message": "Chain lacks required CHAIN_SEAL event"
    },
    {
      "type": "HASH_MISMATCH",
      "severity": "CRITICAL",
      "event_index": 42,
      "expected": "abc123...",
      "actual": "def456..."
    }
  ],
  "recommendation": "REJECT_CHAIN"
}
```

**Why This Matters:** The Verifier is the final arbiter. If it accepts a chain, that chain is defensible. If it rejects, the chain is worthless.

---

### 8.6 Replay System

**Purpose:** Deterministically reconstruct agent behavior from sealed event chains.

**Hard Requirements:**

- **Read‑only access** — Cannot modify events
- **No inference or interpolation** — Only replay recorded events
- **Explicit marking of incomplete evidence** — Show gaps clearly
- **Deterministic playback** — Same events → same replay
- **UI differences must not affect semantics** — Visual changes OK, logical changes forbidden

**Replay Guarantees:**

| Guarantee        | Meaning                                             |
| ---------------- | --------------------------------------------------- |
| **Fidelity**     | Replayed events match original events byte-for-byte |
| **Completeness** | All events are shown (including LOG_DROP)           |
| **Ordering**     | Events appear in sequence order                     |
| **Transparency** | Gaps and uncertainties are visible                  |

**Anti-Requirements (MUST NOT):**

- Infer missing tool calls
- Smooth over sequence gaps
- Reorder events for "better UX"
- Hide redacted fields
- Simulate non-deterministic behavior

**Example Replay Output:**

```
Session: abc-123
Evidence Class: AUTHORITATIVE_EVIDENCE
Seal: PRESENT (hash: 9f8e7d...)

[0] SESSION_START
    timestamp: 2026-01-23T10:00:00Z
    agent_id: customer-support-bot-v2

[1] LLM_CALL
    model: claude-sonnet-4
    prompt: "Customer asks: Can you refund my order?"

[2] LLM_RESPONSE
    content: "I'll check your order status"

[3] TOOL_CALL
    tool: database.query
    args: {"customer_id": "C-12345"}

⚠️  [4] LOG_DROP
    reason: BUFFER_FULL
    dropped_count: 2

[5] TOOL_RESULT
    result: {"status": "shipped", "refund_eligible": false}

[6] SESSION_END
    reason: TIMEOUT

⚠️  WARNING: 2 events lost due to buffer overflow
✓  Chain verified: VALID
```

**Why This Matters:** Replay is how humans understand what happened. If it's misleading, the entire evidence infrastructure fails.

---

### 8.7 Compliance & Evidence Exports

**Purpose:** Produce audit‑grade artifacts suitable for legal, regulatory, and compliance use.

**Hard Requirements:**

**JSON Export:**

- RFC 8785 canonical serialization
- Includes verification metadata
- Embedded hash chain
- Evidence class prominently displayed
- Cryptographic signature (future)

**PDF Export:**

- Human-readable timeline
- Non-technical executive summary
- Technical verification section
- Chain-of-custody statement
- Disclaimer section

**Required Disclaimers:**

```
EVIDENCE SUPPORT STATEMENT

This export is provided as EVIDENCE ONLY. It is not:
• A certification of compliance
• A guarantee of agent correctness
• Legal or regulatory advice
• A complete record (if evidence class is PARTIAL)

Evidence Class: [AUTHORITATIVE_EVIDENCE]
Verification Status: [VALID]
Export Date: [ISO 8601 timestamp]
Export Authority: [Organization name]

For questions about this evidence, contact: [contact info]
```

**Export Metadata:**

```json
{
  "export_version": "1.0",
  "export_timestamp": "2026-01-23T15:30:00Z",
  "session_id": "abc-123",
  "evidence_class": "AUTHORITATIVE_EVIDENCE",
  "verification_result": {
    "status": "VALID",
    "verifier_version": "2.1.0",
    "verification_timestamp": "2026-01-23T15:29:45Z"
  },
  "chain_summary": {
    "first_event": "2026-01-23T10:00:00Z",
    "last_event": "2026-01-23T10:15:23Z",
    "event_count": 342,
    "seal_present": true,
    "final_hash": "9f8e7d..."
  }
}
```

**Why This Matters:** Auditors, lawyers, and regulators work with documents, not APIs. The export format determines whether evidence is accepted or rejected.

---

## 9. Failure Semantics

### 9.1 Global Failure Principles

**Inviolable Rules:**

1. **No silent data loss** — Lost events MUST be recorded as LOG_DROP
2. **No repair of broken chains** — Corruption MUST be detected, not fixed
3. **No inference of missing data** — Gaps remain gaps
4. **All failures must be detectable post‑hoc** — Evidence of failure is evidence

### 9.2 Failure Mode Catalog

| Component | Failure         | System Response                              |
| --------- | --------------- | -------------------------------------------- |
| SDK       | Buffer overflow | Emit LOG_DROP, continue                      |
| SDK       | Network failure | Retry with backoff, emit LOG_DROP if timeout |
| Ingestion | Sequence gap    | Reject batch, emit CHAIN_BROKEN              |
| Ingestion | Hash mismatch   | Reject batch, alert security                 |
| Storage   | Write failure   | Reject batch, trigger incident               |
| Verifier  | Invalid chain   | Exit 1, output violations                    |
| Replay    | Missing events  | Display gap with warning                     |

### 9.3 Degradation Hierarchy

```text
FULL OPERATION (AUTHORITATIVE)
    ↓ (network partition)
LOCAL BUFFERING (degraded, NON_AUTHORITATIVE)
    ↓ (buffer full)
LOG_DROP RECORDING (degraded, evidence of loss)
    ↓ (kill switch)
DISABLED (explicit, no evidence)
```

**Critical Point:** Each degradation level MUST be visible in the final evidence class and verification output.

---

## 10. Security & Compliance Requirements

### 10.1 Cryptographic Requirements

- **Hash Algorithm:** SHA-256 minimum (SHA-3 future)
- **Canonicalization:** RFC 8785 (deterministic JSON)
- **Signature:** Ed25519 for CHAIN_SEAL (future)
- **Key Management:** Dedicated signing keys, rotated quarterly

### 10.2 Privacy & Redaction

**Redaction Principles:**

- Redacted content is **replaced with hash**
- Redaction is **cryptographically auditable**
- Redaction **does not break chain integrity**
- Redaction **is irreversible**

**Example:**

```json
// Original
{"customer_email": "john@example.com"}

// Redacted
{
  "customer_email": "[REDACTED]",
  "customer_email_hash": "sha256:9f8e7d...",
  "redaction_reason": "PII"
}
```

**Why This Matters:** GDPR, CCPA, and other privacy laws require PII minimization. Redaction must preserve evidence integrity.

### 10.3 Chain-of-Thought Exclusion

**Policy:** Chain-of-thought (extended reasoning) is **never stored by default**.

**Rationale:**

- Legal liability (reasoning can be subpoenaed)
- Privacy risk (may contain PII inference)
- Irrelevance (we record actions, not thoughts)

**Exception:** If explicitly enabled AND customer accepts legal risk.

### 10.4 Test vs. Production Separation

**Hard Requirements:**

- Production chains MUST use `production: true` flag
- Test chains MUST use different session_id namespace
- Evidence exports MUST display environment prominently
- Verifier MUST reject test chains in production policy mode

---

## 11. MVP Scope (v1.0)

### 11.1 Included (Non-Negotiable)

**Core Infrastructure:**

- Python SDK (production-ready)
- Ingestion service (horizontally scalable)
- Immutable event store (PostgreSQL + append-only)
- Verifier CLI (zero-dependency binary)
- Replay API (read-only GraphQL)

**Integrations:**

- LangChain (latest stable version)
- OpenAI SDK wrapper
- Anthropic SDK wrapper

**Compliance:**

- JSON export (canonical)
- PDF export (auditor-friendly)
- Verification report generation
- Chain-of-custody documentation

**Documentation:**

- Security architecture
- Integration guide
- Incident response playbook
- Compliance export guide

### 11.2 Explicitly Excluded (Future Versions)

- Multiple framework integrations (CrewAI, AutoGPT)
- Replay diffing / comparison
- Advanced dashboard UI
- Real-time alerting
- Automated compliance reports
- Cryptographic signing (hardware security modules)
- Multi-region replication

### 11.3 Launch Criteria

AgentOps Replay v1.0 ships when:

1. ✅ Verifier passes 100% of adversarial tests
2. ✅ System survives simulated network partition
3. ✅ Compliance export accepted by legal team
4. ✅ Security audit complete (internal)
5. ✅ Incident response playbook validated
6. ✅ Reference deployment on production agent (internal)

**Blockers:** Any verifier bug, any silent data loss, any chain repair.

---

## 12. Success Metrics (Reality-Based)

### 12.1 Leading Indicators (Pre-Incident)

- **Deployment Rate:** % of production agents with AgentOps enabled
- **Evidence Quality:** % of chains passing strict verification
- **Policy Enforcement:** % of CI/CD pipelines requiring verification
- **Security Integration:** # of incident response runbooks citing AgentOps

### 12.2 Lagging Indicators (Post-Incident)

- **Incident Attachment Rate:** % of incident reports including replay logs
- **Compliance Export Usage:** # of exports requested by legal/audit
- **Verifier Reliance:** # of security investigations using verifier output
- **Regulatory Acceptance:** # of audits where exports were accepted

### 12.3 The Ultimate Success Metric

**AgentOps Replay has succeeded when:**

> Removing it from production is considered a **critical security incident**.

Not when it's popular. Not when it's fast. When it's **irreplaceable**.

### 12.4 Anti-Metrics (Vanity Metrics to Ignore)

- GitHub stars
- Dashboard logins
- API request volume
- SDK downloads (without production usage)

**Why:** These measure interest, not dependence.

---

## 13. Constraints & Guardrails

### 13.1 Constitution Supremacy

**Rule:** Constitution violations invalidate ALL subsequent work.

**Examples:**

- Adding event mutation → Constitution violation → Feature rejected
- Allowing hash chain repair → Constitution violation → Feature rejected
- Inferring missing events → Constitution violation → Feature rejected

**Enforcement:** All PRs must include constitutional compliance section.

### 13.2 Verifier Correctness > Everything Else

**Priority Order:**

1. Verifier correctness
2. Evidence integrity
3. System availability
4. Developer ergonomics
5. Performance
6. User experience

**Example:** If a performance optimization risks silent data loss, it is **permanently rejected**.

### 13.3 Determinism > Performance

**Rule:** Non-deterministic behavior is never acceptable.

**Examples:**

- Parallel event processing → Only if ordering is preserved
- Async verification → Only if result is identical to sync
- Caching → Only if cache invalidation is deterministic

### 13.4 Evidence > Interpretation

**Rule:** The system records what happened, not why it happened.

**Examples:**

- "Agent was confused" → Interpretation, excluded
- "Agent called tool X with args Y" → Evidence, included
- "Prompt was unclear" → Interpretation, excluded
- "LLM returned response Z" → Evidence, included

---

## 14. Risks & Mitigations

| Risk                                                       | Impact   | Likelihood | Mitigation                                            |
| ---------------------------------------------------------- | -------- | ---------- | ----------------------------------------------------- |
| **Spec drift** (implementation diverges from constitution) | CRITICAL | Medium     | Verifier enforcement, automated compliance tests      |
| **SDK misuse** (developers bypass system)                  | HIGH     | Medium     | Untrusted producer model, server re-verification      |
| **Legal rejection** (evidence deemed inadmissible)         | CRITICAL | Low        | No reasoning capture, canonical exports, legal review |
| **Data loss** (events disappear silently)                  | CRITICAL | Low        | LOG_DROP semantics, loud failures, monitoring         |
| **Performance impact** (SDK slows agent)                   | MEDIUM   | Medium     | Async buffering, kill-switch, resource limits         |
| **False confidence** (users trust bad evidence)            | HIGH     | Medium     | Evidence class visibility, verifier warnings          |
| **Competitive lock-in** (vendor resistance)                | LOW      | High       | Open specification, independent verifier              |

### 14.1 Existential Risk

**Risk:** Legal precedent establishes that AI agent evidence is inadmissible.

**Mitigation:**

- Work with legal scholars on evidence standards
- Publish white papers on chain-of-custody
- Engage with regulatory bodies early
- Build coalition of adopters

**Contingency:** Pivot to pure incident response (non-legal use cases).

---

## 15. Open Questions (Explicit Deferrals)

### 15.1 Cryptographic Signing

**Question:** When to introduce hardware-backed signatures for CHAIN_SEAL?

**Trade-offs:**

- ✅ Stronger non-repudiation
- ✅ Regulatory preference (digital signatures)
- ❌ Operational complexity (key management)
- ❌ Single point of failure (HSM outage)

**Decision:** Defer to v2.0 after legal precedent is established.

### 15.2 Retention Policies

**Question:** How long to retain event chains?

**Considerations:**

- Legal: 7 years (typical statute of limitations)
- Compliance: Varies by regulation (GDPR, HIPAA, SOX)
- Cost: Storage grows linearly with agent usage
- Privacy: Right to be forgotten (GDPR Article 17)

**Decision:** Customer-configurable, default 7 years, with documented deletion process.

### 15.3 Multi-Tenancy & Access Control

**Question:** How to isolate evidence in shared deployments?

**Options:**

1. Physical separation (dedicated instances)
2. Cryptographic isolation (per-tenant keys)
3. Policy-based access control (RBAC)

**Decision:** Defer to v1.5, start with dedicated instances.

### 15.4 Real-Time Verification

**Question:** Should verification happen during ingestion or post-hoc?

**Trade-offs:**

- Real-time: Immediate feedback, slower ingestion
- Post-hoc: Faster ingestion, delayed failure detection

**Decision:** Post-hoc for v1.0, real-time for v2.0 (optional).

---

## 16. Organizational Requirements

### 16.1 Team Structure

**Required Roles:**

- **Security Lead** — Constitution enforcement, threat modeling
- **Compliance Engineer** — Export formats, regulatory liaison
- **Infrastructure Engineer** — Ingestion, storage, scaling
- **SDK Engineer** — Client libraries, integrations
- **Verifier Engineer** — Independent verification logic

**Anti-Roles (Do Not Hire):**

- "Growth hacker" (wrong incentives)
- "UX optimizer" (wrong priority)
- "Prompt engineer" (wrong product)

### 16.2 Development Principles

1. **Constitution-First:** All features start with constitutional review
2. **Verifier-Driven:** Implementation follows verifier specification
