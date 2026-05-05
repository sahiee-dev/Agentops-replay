# AgentOps Replay — Research Paper Roadmap
## IEEE Conference Paper → Journal Paper Upgrade Plan

> **Document Type:** Research Strategy + Technical Novelty Analysis  
> **Audience:** You (the researcher/builder)  
> **Standard:** IEEE Transactions level (strict)  
> **Last Updated:** May 2026

---

## ⚠️ Preface: What This Document Will Tell You

This document is written under the assumption that you want a rigorous, publishable journal paper — not a repackaged conference paper. IEEE Transactions reviewers are unforgiving. They will reject a paper that is "just a longer version of the conference paper" with an extended evaluation. This document identifies where your current work sits in the research landscape, what specifically is missing for journal-level contribution, and a concrete work plan to close those gaps.

Read this as a strict external reviewer would. That is the only way to make it useful.

---

## Section 1: The Research Landscape (What Exists)

Before claiming novelty, you must know what has already been published. This is what the current literature contains:

### 1.1 Directly Related Work (Your Competition)

**"Right to History: A Sovereignty Kernel for Verifiable AI Agent Execution"** (Zhang, February 2026, arXiv:2602.20214)
- Proposes Merkle tree audit logs + capability-based isolation + energy-budget governance
- Formalizes five system invariants with structured proof sketches
- Implements in Rust, reports sub-1.3ms median latency, ~400 actions/sec, 448-byte Merkle inclusion proofs
- **Gap it leaves:** Focuses on single-agent, personal hardware deployment. Does not address multi-agent delegation chains, enterprise ingestion service authority model, or the SDK-vs-server trust boundary problem.

**"Creating Characteristically Auditable Agentic AI Systems"** (ACM Intelligent Robotics FAIR 2025, September 2025)
- Proposes eight auditability axioms for multi-agent systems
- Proves that hash-linked per-action entries with principal signatures achieve the axioms
- **Gap it leaves:** Theoretical framework without a reference implementation. No empirical evaluation. No evidence classification system. No treatment of the ingestion service authority model.

**"Governing Dynamic Capabilities: Cryptographic Binding and Reproducibility Verification for AI Agent Tool Use"** (arXiv:2603.14332)
- Formalizes three Agent Governance Requirements (G1: capability integrity, G2: behavioral verifiability, G3: interaction auditability)
- Proposes capability-context separation
- **Gap it leaves:** No implementation. No evaluation. Does not address the LOG_DROP problem (what happens when events are lost). Does not define evidence classification.

**"Constant-Size Cryptographic Evidence Structures for Regulated AI Workflows"** (arXiv:2511.17118)
- Proposes fixed-size evidence tuples for regulated AI
- Proves asymptotic complexity bounds
- Integrates with hash-chained logs and Merkle trees
- **Gap it leaves:** Focused on clinical trials / pharmaceutical compliance. Not designed for real-time agent event capture. No multi-agent treatment. No open reference implementation.

**"HDP: A Lightweight Cryptographic Protocol for Human Delegation Provenance in Agentic AI Systems"** (Dalugoda, March 2026, arXiv:2604.04522)
- Addresses the multi-agent delegation chain problem specifically
- Cryptographically captures human authorization context across agent hops
- Offline verification via Ed25519 signatures
- **Gap it leaves:** Focused exclusively on authorization delegation, not complete event logging. No treatment of event ordering, sequence gaps, buffer overflow semantics, or evidence classification.

**"MAIF: Enforcing AI Trust and Provenance with an Artifact-Centric Agentic Paradigm"** (arXiv:2511.15097)
- Artifact-centric architecture with formal security model
- Ultra-high-speed streaming (2,720.7 MB/s), massive compression (up to 225×)
- Formal tamper detection and provenance integrity proofs
- **Gap it leaves:** Artifact-centric (focused on data artifacts), not event-log-centric. Does not address the authority separation problem between SDK and ingestion service.

**"AgentLeak: A Full-Stack Benchmark for Privacy Leakage in Multi-Agent LLM Systems"** (arXiv:2602.11510)
- Demonstrates that inter-agent messages leak at 68.8% vs 27.2% on output channels
- **Gap it leaves:** This is a benchmarking paper, not an accountability system. It proves the problem exists; it doesn't solve it. Your work is complementary: AgentOps Replay is the system that would catch these leaks.

### 1.2 Related But Distinct Work (Understand the Boundary)

- **Certificate Transparency (RFC 6962):** Hash-chained logs for TLS certificates. Related technique, different domain, not agent-specific.
- **Blockchain audit logs (BlockA2A):** Decentralized identity + blockchain for agent-to-agent accountability. Much higher overhead, requires consensus mechanism, not suitable for per-event real-time logging.
- **auditd / eBPF tracing:** OS-level audit mechanisms. Operate at syscall granularity, cannot attribute actions to agent-level semantics.
- **OpenTelemetry:** Distributed tracing standard. Observability, not accountability. Mutable, no cryptographic guarantees.

### 1.3 The Gap Your Work Occupies

After surveying the literature, the specific combination that AgentOps Replay provides — and that no existing published work provides — is:

1. **A formally specified, open event log specification** (ELS) that any framework can implement
2. **A precisely defined authority separation model** (SDK-untrusted, server-trusted) with formal failure semantics
3. **An evidence classification system** (AUTHORITATIVE vs PARTIAL vs NON-AUTHORITATIVE) with formal definitions
4. **A LOG_DROP semantics treatment** — what happens when events are lost (existing work ignores this)
5. **An independently distributable verifier** (zero-dependency, runs without any account or infrastructure)
6. **An empirical evaluation** on real multi-agent frameworks (LangChain) with measured overhead
7. **A formal failure mode taxonomy** — an explicit treatment of what must fail closed vs. fail open

**The "no existing work has done X" claims you can defensibly make:**
- No existing work defines a formal authority separation model for AI agent audit logs that distinguishes SDK-produced (untrusted) from server-sealed (trusted) events
- No existing work defines evidence classification tiers (AUTHORITATIVE / PARTIAL / NON-AUTHORITATIVE) with formal definitions
- No existing work treats LOG_DROP semantics formally — the behavior of an accountability system when events cannot be captured
- No existing work provides both a formal specification AND an open reference implementation with empirical evaluation on production frameworks

---

## Section 2: What Must Change from Conference to Journal

### 2.1 What Typically Distinguishes a Conference Paper from a Journal Paper

IEEE Transactions reviewers expect:
1. **30–40% new technical content** beyond the conference paper — not just "extended evaluation"
2. **Formal definitions** — if you claim something, define it mathematically
3. **Proofs or proof sketches** for all claimed properties
4. **Significantly more comprehensive evaluation** — multiple frameworks, adversarial testing, performance benchmarks with statistical rigor
5. **Positioning against all related work** — every paper in Section 1.1 above must be cited and explicitly compared
6. **Reproducibility** — all experiments must be reproducible from provided artifacts

### 2.2 Specific Gaps You Must Close

Based on the research landscape, here are the specific technical contributions you need to add for journal publication:

#### Gap J1: Formal System Model

The conference paper likely describes the system in prose. The journal paper needs:

- **Formal definition of an Event:** A tuple `E = (seq, type, session_id, ts, payload, prev_hash, hash)` with formally defined domains for each field
- **Formal definition of a Session:** An ordered sequence of events `S = (E_1, E_2, ..., E_n)` satisfying the chain integrity predicate
- **Formal definition of Chain Integrity predicate:** `∀i ∈ [2,n]: E_i.prev_hash = H(E_{i-1})` where `H` is JCS-SHA256
- **Formal definition of Evidence Class:** A function `EC: S → {AUTHORITATIVE, PARTIAL, NON-AUTHORITATIVE}` with formally stated conditions
- **Formal definition of the Authority Model:** Two principals (SDK, Server) with formally defined capabilities and trust assumptions

#### Gap J2: Formal Failure Mode Analysis

Define failure modes formally, not just in prose:

- **LOG_DROP semantics:** What the system guarantees when buffer overflow occurs. Formally: if `n` events cannot be captured, a single `LOG_DROP(n, seq_start, seq_end)` event is emitted, and the chain integrity predicate must hold for the resulting sequence including the LOG_DROP
- **CHAIN_BROKEN semantics:** When the server detects a sequence gap, what it emits, and what properties the resulting chain has
- **Fail-open vs fail-closed:** Formally state under which conditions the SDK must fail open (never crash the agent) and under which conditions the ingestion service must fail closed (never partial write)

This extends the existing work (which largely ignores failure semantics) with a formally stated, evaluated failure model.

#### Gap J3: Evidence Classification Formal Definition

Define the evidence classification system rigorously:

```
Let S = (E_1, ..., E_n) be a session.
Let seal(S) = ∃i: E_i.type = CHAIN_SEAL
Let intact(S) = ¬∃i: E_i.type = LOG_DROP

EC(S) = AUTHORITATIVE_EVIDENCE     iff seal(S) ∧ intact(S)
EC(S) = PARTIAL_AUTHORITATIVE      iff seal(S) ∧ ¬intact(S)
EC(S) = NON_AUTHORITATIVE          iff ¬seal(S)
```

Then prove: if `EC(S) = AUTHORITATIVE_EVIDENCE`, then `S` cannot be modified without invalidating the chain integrity predicate (tamper-evident guarantee). The proof is straightforward by the collision-resistance of SHA-256 under the cryptographic hash function assumption.

#### Gap J4: Multi-Framework Empirical Evaluation

The conference paper likely evaluated on one framework. Journal level requires:

- Minimum three frameworks: LangChain (done), one more (CrewAI or AutoGen), and a synthetic workload
- Metrics to measure and report:
  - **Latency overhead per event type** (µs): median, P95, P99 across 10,000 samples
  - **Throughput:** maximum events/second under sustained load
  - **Memory overhead:** RSS increase with buffer size variation
  - **Verification time:** time for verifier to validate sessions of 100, 1,000, 10,000 events
  - **Hash chain computation:** per-event time (µs) for JCS canonicalization + SHA-256
- Statistical rigor: report mean ± standard deviation, include hardware specifications
- Show that the fail-open property holds empirically: measure agent process latency with and without AgentOps Replay under various failure modes (network partition, disk full, buffer overflow)

#### Gap J5: Adversarial Security Analysis

Conference papers often only test the happy path. Journal-level security evaluation requires:

- **Threat model:** Formally define the adversary. What can they control? What are they trying to achieve?
  - Adversary A1: Compromised SDK (runs in agent's process, can inject events)
  - Adversary A2: Man-in-the-middle between SDK and ingestion service
  - Adversary A3: Compromised storage backend (direct DB access)
  - Adversary A4: Insider threat (has admin access to ingestion service)
  
- **For each adversary:** What can they do? What can they not do? What does the system detect?

- **Test vectors for each attack:**
  - A1 can inject events → server re-computes chain independently, detects if SDK-computed hashes were wrong
  - A2 can replay events → sequence numbers and timestamps prevent replay; server detects gaps
  - A3 can modify stored events → database-level append-only + immutable triggers, detected by verifier
  - A4 can delete sessions → audit log of audit system, CHAIN_SEAL already distributed

#### Gap J6: Formal Comparison with Related Work

A rigorous comparison table showing, for each related paper (Section 1.1), which properties they achieve and which AgentOps Replay achieves that they don't:

| Property | Zhang 2026 | ACM FAIR 2025 | Governing Dyn. Cap. | AgentOps Replay |
|---|---|---|---|---|
| Formal specification | Partial | Axioms only | Partial | Full ELS |
| Reference implementation | Yes (Rust) | No | No | Yes (Python) |
| Authority separation model | No | No | No | Yes (formal) |
| Evidence classification | No | No | No | Yes (3 tiers) |
| LOG_DROP semantics | No | No | No | Yes (formal) |
| Multi-framework evaluation | No | No | No | Yes |
| Adversarial testing | Yes | No | No | Yes |
| Zero-dependency verifier | No | No | No | Yes |
| Open specification | No | No | No | Yes (ELS) |

---

## Section 3: Proposed Journal Paper Structure

**Target venue:** IEEE Transactions on Dependable and Secure Computing (TDSC) or IEEE Transactions on Information Forensics and Security (TIFS). Both are appropriate for this work. TIFS is higher impact for the forensics angle; TDSC is higher impact for the dependability/correctness angle.

**Alternative venues:** ACM Transactions on Privacy and Security (TOPS), Journal of Systems and Software (Elsevier, easier to get into but lower impact).

---

### Title (Proposed)

**"AgentOps Replay: A Formally Specified, Independently Verifiable Accountability Layer for Autonomous AI Agent Systems"**

Or alternatively, emphasizing the failure semantics contribution:

**"Tamper-Evident Event Logging for AI Agents: Formal Specification, Authority Separation, and Evidence Classification"**

---

### Abstract (Draft)

Autonomous AI agents executing consequential actions in production environments require accountability infrastructure that produces evidence, not merely logs. Existing approaches — application logging, vendor telemetry, and observability platforms — share a structural limitation: they are mutable, vendor-controlled, or lack the cryptographic properties required for independent third-party verification. We present AgentOps Replay, a formally specified accountability system for AI agents that combines: (i) an open Event Log Specification (ELS) defining hash-chained event sequences with JCS canonicalization; (ii) a formally defined authority separation model distinguishing SDK-produced (untrusted) from server-sealed (trusted) events; (iii) a three-tier evidence classification system (AUTHORITATIVE, PARTIAL-AUTHORITATIVE, NON-AUTHORITATIVE) with formal definitions and tamper-evidence proofs; and (iv) LOG_DROP semantics that guarantee chain transparency under event loss. We prove that sealed chains satisfy tamper-evidence under SHA-256 collision resistance, formally characterize failure modes under four adversary models, and evaluate the system on [N] agent frameworks including LangChain and [X]. Empirical results show per-event overhead of [X] µs median with [Y] µs P99, [Z] events/sec throughput, and verification of 10,000-event sessions in [W] ms. AgentOps Replay ships with a zero-dependency standalone verifier that any party can run against exported chains without an account or network access.

---

### Proposed Sections

**1. Introduction**
- The accountability gap: why logs are insufficient for AI agent evidence
- The three requirements: tamper evidence, independent verification, authority separation
- Contributions (bulleted, precise)
- Paper organization

**2. Background and Motivation**
- AI agent execution model (LLM + tool calls + delegation)
- The multi-agent privacy leak problem (cite AgentLeak)
- Regulatory requirements: EU AI Act, NIST AI RMF, ISO 42001
- Why existing tools fail (systematic comparison)

**3. Formal System Model**
- Event definition
- Session definition
- Chain integrity predicate
- Authority model (SDK, Ingestion Service, Verifier principals)
- Evidence classification formal definition

**4. The Event Log Specification (ELS)**
- Schema (all fields, all event types)
- Hash computation algorithm (JCS + SHA-256)
- Ingestion protocol (batch semantics, atomicity)
- CHAIN_SEAL construction and semantics

**5. Failure Semantics**
- LOG_DROP: formal definition, guaranteed properties
- CHAIN_BROKEN: server detection, formal treatment
- Fail-open vs fail-closed: formal statement
- Comparison with related work's failure handling (or lack thereof)

**6. Security Analysis**
- Threat model (four adversaries)
- Security properties and proofs
- Adversarial test results

**7. Implementation**
- Architecture (SDK, Ingestion Service, Verifier)
- JCS canonicalization: implementation challenges
- Append-only enforcement (database level, not application level)
- Zero-dependency verifier: design choices

**8. Evaluation**
- Experimental setup (hardware, frameworks tested)
- Latency overhead: per event type, P50/P95/P99
- Throughput
- Verification performance vs session size
- Fail-open validation (agent not impacted by AgentOps failures)

**9. Related Work**
- Systematic comparison against all papers in Section 1.1 of this document
- Positioning table (Gap J6 above)

**10. Discussion**
- Limitations
- What AgentOps Replay does NOT provide (important: don't overclaim)
- Future work: governance layer, multi-agent delegation tracking, hardware attestation integration

**11. Conclusion**

---

## Section 4: Work Plan to Get There

### Milestone R1: Formal Specification Writing (Weeks 1–3)
- Write Section 3 (Formal System Model) — all formal definitions
- Write Section 5 (Failure Semantics) — LOG_DROP and CHAIN_BROKEN formal treatment
- Write Section 6 threat model — define the four adversaries
- **Deliverable:** Formal definitions document (can be shared with advisors for review before implementation)

### Milestone R2: Implementation Gaps (Weeks 3–6)
- Confirm LOG_DROP implementation matches formal definition
- Confirm CHAIN_BROKEN detection and emission is correctly implemented
- Write adversarial test suite (test vectors for each of the four adversaries)
- **Deliverable:** All adversarial tests pass

### Milestone R3: Evaluation (Weeks 6–10)
- Add CrewAI integration (or AutoGen — pick one)
- Build benchmarking harness: measure latency overhead on 10,000 events per framework
- Measure verification time vs session size
- Run fail-open tests under simulated network partition and disk full conditions
- Run all adversarial tests, record results
- **Deliverable:** All measurements recorded with statistics; hardware config documented

### Milestone R4: Paper Writing (Weeks 10–16)
- Write full paper following the structure above
- Comparison table against all related work
- Submit to advisor/co-author for review
- **Target venue decision:** IEEE TDSC or TIFS

### Milestone R5: Artifact Package (Weeks 14–16, parallel with writing)
- Prepare artifact submission: code, test vectors, evaluation scripts, instructions
- Ensure all experiments are reproducible from a fresh clone
- IEEE Transactions increasingly requires artifact evaluation; this is not optional

---

## Section 5: Claims to Make vs. Claims to Avoid

### Safe Claims (Make These)
- "AgentOps Replay is the first open specification with a reference implementation that defines evidence classification tiers for AI agent audit logs"
- "We are the first to formally specify LOG_DROP semantics — the behavior of an accountability system under event loss"
- "Our authority separation model (SDK-untrusted, server-trusted) is the first formal treatment of this distinction in the AI agent accountability literature"
- "Our standalone, zero-dependency verifier enables third-party verification without infrastructure dependencies"

### Dangerous Claims (Avoid or Qualify Carefully)
- ❌ "The first tamper-evident log for AI agents" — Zhang (2026) beats you to this claim
- ❌ "Provides formal guarantees of completeness" — LOG_DROP means completeness is not guaranteed; you can only guarantee that gaps are detected and recorded
- ❌ "Suitable for legal proceedings" — you are not a lawyer; never make this claim in a paper
- ❌ "Compliant with EU AI Act" — compliance is a legal determination; you can claim "designed to satisfy the audit trail requirements of Article 12 and 13"

---

## Section 6: Key References to Cite

Your paper must cite and engage with all of the following. Any reviewer familiar with the area will check for these:

1. Zhang, J. (2026). "Right to History: A Sovereignty Kernel for Verifiable AI Agent Execution." arXiv:2602.20214
2. "Creating Characteristically Auditable Agentic AI Systems." ACM FAIR 2025. DOI:10.1145/3759355.3759356
3. "Governing Dynamic Capabilities: Cryptographic Binding and Reproducibility Verification for AI Agent Tool Use." arXiv:2603.14332
4. "Constant-Size Cryptographic Evidence Structures for Regulated AI Workflows." arXiv:2511.17118
5. Dalugoda, A. (2026). "HDP: A Lightweight Cryptographic Protocol for Human Delegation Provenance." arXiv:2604.04522
6. "AgentLeak: A Full-Stack Benchmark for Privacy Leakage in Multi-Agent LLM Systems." arXiv:2602.11510
7. Schneier, B. & Kelsey, J. (1999). "Secure Audit Logs to Support Computer Forensics." ACM TISSEC.
8. Laurie, B. et al. (2013). "Certificate Transparency." RFC 6962. IETF.
9. Merkle, R.C. (1980). "Protocols for Public Key Cryptosystems." IEEE S&P.
10. Haber, S. & Stornetta, W.S. (1991). "How to Time-Stamp a Digital Document." Journal of Cryptology.
11. OWASP Agentic Security Initiative Top 10. (2025). OWASP Foundation.
12. European Commission. (2024). "Regulation (EU) 2024/1689 of the European Parliament and of the Council." (EU AI Act)
13. NIST. (2023). "AI Risk Management Framework (AI RMF 1.0)." NIST AI 100-1.
14. "Accountability of Things: Large-Scale Tamper-Evident Logging for Smart Devices." arXiv:2308.05557

---

*Research Roadmap Document — May 2026*  
*This document is a planning tool. Claims about related work are based on publicly available papers as of May 2026 and must be verified before submission.*
