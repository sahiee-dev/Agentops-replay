# AGENT_CONTEXT.md (v2)

> **READ THIS FIRST. EVERY SESSION. NO EXCEPTIONS.**
> This file tells you what exists, what the rules are, and what you must never do.
> If you haven't read this, stop and read it before touching any code.

---

## What This Project Is (Two Paragraphs)

AgentOps Replay records what an AI agent does — every LLM call, every tool use — into a hash-chained, tamper-evident log. A standalone Verifier CLI can prove the log hasn't been modified. That proof is what turns a log into evidence.

The project serves three audiences simultaneously: (1) **Enterprise security teams** who need cryptographically verifiable audit trails for EU AI Act / NIST AI RMF compliance, (2) **Self-hosted AI users** (Open WebUI, LangChain, CrewAI) who have zero audit infrastructure today, and (3) **Researchers** building on or comparing against formally specified accountability systems. The core product is the same for all three — the audiences determine how it's documented and positioned, not what gets built.

---

## Document Map (Read the Right One for Your Task)

| Document | What It Contains | When to Read It |
|---|---|---|
| `CONSTITUTION.md` | Frozen invariants — never changes | When you're unsure if something is allowed |
| `PRD_v5.md` | What the product is, scope per version, event schema, evidence classes | When making product/scope decisions |
| `TRD_v2.md` | Full technical spec — interfaces, DB schema, API contracts, test requirements | When writing any code |
| `AGENT_CONTEXT.md` | What's built, what's not, rules for agents | **Every session, first** |
| `BUILD_SEQUENCE.md` | Ordered task list with verification steps | **Every session, after this file** |
| `MARKET_ENTERPRISE_SECURITY.md` | Enterprise buyer, GTM, enterprise product requirements | When working on compliance/enterprise features |
| `MARKET_OPENSOURCE_COMMUNITY.md` | OSS community adoption, Open WebUI integration | When working on community integrations |
| `RESEARCH_PAPER_ROADMAP.md` | Related work survey, journal paper plan, novelty claims | When working on research/formal spec |

---

## What Has Been Built (Update After Every Completed Task)

> **IMPORTANT:** This reflects what was reported as built. Phase 0 audit tasks will confirm actual status. Update checkboxes only after running the verification step.

### Component 1: SDK (`agentops_sdk/`)
- [x] `client.py` — AgentOpsClient with start_session, record, end_session, flush_to_jsonl
- [x] `events.py` — EventType enum
- [x] `envelope.py` — Event envelope + hash computation
- [x] `buffer.py` — Ring buffer with LOG_DROP on overflow
- [ ] `sender.py` — HTTP sender to Ingestion Service *(confirm existence before building)*

### Component 2: Verifier (`verifier/`)
- [x] `agentops_verify.py` — CLI verifier
- [x] `jcs.py` — JCS canonicalization (RFC 8785)
- [x] `test_vectors/valid_session.jsonl`
- [x] `test_vectors/invalid_hash.jsonl` *(may be named tampered_hash.jsonl — check)*
- [ ] `test_vectors/sequence_gap.jsonl` *(confirm existence)*
- [ ] `verifier/generator.py` *(confirm existence)*
- [ ] Evidence class reporting in output *(confirm: does it output evidence class?)*
- [ ] Exit codes correct: 0=PASS, 1=FAIL, 2=ERROR *(confirm)*

### Component 3: Ingestion Service (`backend/`)
- [x] FastAPI app structure
- [x] `POST /v1/ingest` endpoint
- [x] ORM models (sessions, events tables)
- [x] Alembic migrations
- [x] Server-side hash recomputation
- [x] CHAIN_SEAL emission on SESSION_END
- [ ] `GET /v1/sessions/{id}/export` endpoint *(confirm existence)*
- [ ] `GET /health` endpoint *(confirm existence)*
- [ ] `backend/docker-compose.yml` *(confirm existence and that it starts clean)*
- [ ] Append-only DB user setup in migrations *(confirm migration 002 exists)*

### Component 4: LangChain Integration
- [x] `AgentOpsCallbackHandler`
- [x] `examples/langchain_demo/` working demo
- [x] End-to-end verified: demo produces JSONL that passes Verifier

### Infrastructure
- [ ] `pyproject.toml` with correct packaging *(confirm)*
- [ ] `tests/unit/` directory with tests *(confirm which tests exist)*
- [ ] `tests/e2e/test_full_flow.py` *(confirm)*
- [ ] GitHub Actions CI workflow *(confirm)*
- [ ] README quickstart that actually works *(confirm: does it run end-to-end?)*

---

## The Five Rules You Must Never Break

### Rule 1: Fail Open for Agents, Fail Closed for Integrity
- The SDK **never** raises an exception that crashes the agent process
- The Ingestion Service **never** writes a partial batch (all or nothing)
- Buffer overflow → LOG_DROP event, not silent loss

### Rule 2: Never Modify Events
- No UPDATE path for the events table. No DELETE path.
- DB user has INSERT + SELECT only on events
- If you find yourself writing `UPDATE events` for anything: stop

### Rule 3: JCS Canonicalization Lives in Exactly One Place
- `verifier/jcs.py` is the single source of truth
- The SDK imports from it. The Ingestion Service imports from it.
- `grep -r "def canonicalize" .` must return exactly one result
- Any divergence between SDK hashes and Verifier output = duplicated JCS logic

### Rule 4: The Verifier Has Zero Dependencies
- `verifier/agentops_verify.py` uses Python stdlib only
- Zero pip installs required to run it
- This is what makes it a neutral third-party tool

### Rule 5: Three Audiences, One Codebase
- All three audiences (enterprise, community, research) use the same SDK, Verifier, and Ingestion Service
- Audience differences live in: documentation, additional enterprise endpoints (v1.1+), and integrations
- Do not create separate codebases or forks for different audiences
- If a feature only makes sense for one audience, it's an optional extension, not a core change

---

## What You Must Not Build in v1.0

These are out of scope until explicitly moved into v1.1 or v1.2:

- Web UI or dashboard
- SIEM webhook delivery
- Forensic Freeze endpoint
- Compliance report PDF generation
- PII redaction endpoint
- Role-based access control (RBAC)
- API key authentication for ingestion service
- Open WebUI Pipeline plugin
- CrewAI / AutoGen integrations
- Go, Rust, or C++ verifier port
- Kubernetes / Helm charts
- Any governance or policy engine

If an agent starts building any of these: **stop it, redirect to BUILD_SEQUENCE.md.**

---

## How to Start Any Coding Session

1. **Read this file** (done ✓)
2. **Find the first unchecked task** in BUILD_SEQUENCE.md
3. **Read the TRD section** for the component you're working on
4. **Verify prerequisites are actually done** — run the test or check the file exists
5. **Do only that task** — do not combine tasks
6. **Run the verification step** specified in BUILD_SEQUENCE.md
7. **Update checkboxes** in this file and BUILD_SEQUENCE.md
8. **Run this sanity check before finishing:**
   ```bash
   python3 verifier/agentops_verify.py verifier/test_vectors/valid_session.jsonl
   # Must output PASS ✅
   ```

---

## Diagnostic Guide: When Things Break

### "Verifier fails on SDK output"
Most likely: SDK is computing hashes differently from the Verifier.
Check: `grep -r "def canonicalize" .` — if more than one result, you have duplicate JCS logic. Remove the duplicate and import from `verifier/jcs.py`.

### "Ingestion Service returns 400 on valid events"
Most likely: Server-side hash recomputation failing.
Check: Is `backend/app/services/ingestion/chain.py` importing from `verifier/jcs.py`? If it has its own JCS implementation, delete it and fix the import.

### "AUTHORITATIVE_EVIDENCE not appearing after server ingest"
Most likely: SESSION_END is not being sent to the server before `send_to_server()` is called, or the sealer isn't triggering on SESSION_END.
Check: Is `end_session()` called before `send_to_server()`? Does `backend/app/services/ingestion/sealer.py` exist and get called from `service.py`?

### "LangChain demo doesn't produce verifiable output"
Isolate: Run `examples/sdk_demo.py` first.
If sdk_demo passes Verifier → the SDK is fine → bug is in the callback handler.
If sdk_demo fails Verifier → the SDK is broken → fix the SDK first.

### "Test vector fails unexpectedly"
First: regenerate test vectors — `python3 verifier/generator.py`.
If it still fails: the verifier or jcs.py has a bug. Do not touch the test vectors — fix the verifier.

---

## File Ownership Map

| File | Can Be Modified? | Notes |
|---|---|---|
| `CONSTITUTION.md` | **NO** | Frozen forever |
| `verifier/jcs.py` | Bug fixes only | Never change the algorithm |
| `agentops_sdk/envelope.py` | Bug fixes only | Never change hash computation |
| `PRD_v5.md` | Scope decisions only | Developer updates this, not agents |
| `TRD_v2.md` | Technical decisions only | Developer updates this, not agents |
| `AGENT_CONTEXT.md` | **YES — update checkboxes** | After every completed task |
| `BUILD_SEQUENCE.md` | **YES — check off tasks** | After every completed task |
| Everything else | YES | Normal development |

---

## Current Known Issues

*(Update when found. Delete when fixed.)*

- [ ] `sender.py` existence unconfirmed — do TASK-0.1 before assuming
- [ ] `GET /v1/sessions/{id}/export` existence unconfirmed
- [ ] `docker-compose.yml` existence and functionality unconfirmed
- [ ] Evidence class reporting in Verifier output unconfirmed
- [ ] Verifier exit codes (0/1/2) unconfirmed
- [ ] End-to-end AUTHORITATIVE_EVIDENCE flow unconfirmed
- [ ] `pyproject.toml` packaging unconfirmed
- [ ] CI workflow existence unconfirmed

---

*AGENT_CONTEXT.md v2 — Updated May 2026*
*Companion to PRD_v5.md + TRD_v2.md*
*An outdated AGENT_CONTEXT is worse than no AGENT_CONTEXT. Keep it current.*
