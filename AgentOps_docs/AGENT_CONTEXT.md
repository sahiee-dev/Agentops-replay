# AGENT_CONTEXT.md

> **READ THIS FIRST. EVERY SESSION. NO EXCEPTIONS.**  
> This file tells you what exists, what the rules are, and what you must never do.  
> If you haven't read this, stop and read it before touching any code.

---

## What This Project Is (One Paragraph)

AgentOps Replay records what an AI agent does — every LLM call, every tool use — into a hash-chained, tamper-evident log. A standalone Verifier CLI can prove the log hasn't been modified. That's the whole product. Four components: SDK, Verifier, Ingestion Service, LangChain Integration.

---

## What Has Been Built (Update This Section When Work Is Done)

> **IMPORTANT:** This section must be kept current. After completing any task from BUILD_SEQUENCE.md, update this section before ending your session.

### Component 1: SDK (`agentops_sdk/`)
- [x] `client.py` — AgentOpsClient with start_session, record, end_session, flush_to_jsonl
- [x] `events.py` — EventType enum
- [x] `envelope.py` — Event envelope + hash computation
- [x] `buffer.py` — Ring buffer with LOG_DROP on overflow
- [ ] `sender.py` — HTTP sender to Ingestion Service *(status: unknown — verify before building)*

### Component 2: Verifier (`verifier/`)
- [x] `agentops_verify.py` — CLI verifier
- [x] `jcs.py` — JCS canonicalization (RFC 8785)
- [x] `test_vectors/valid_session.jsonl`
- [x] `test_vectors/invalid_hash.jsonl` (may be called `tampered_hash.jsonl`)
- [ ] `test_vectors/sequence_gap.jsonl` *(status: unknown — check if it exists)*
- [ ] `verifier/generator.py` *(status: unknown)*

### Component 3: Ingestion Service (`backend/`)
- [x] FastAPI app structure
- [x] `POST /v1/ingest` endpoint
- [x] ORM models (sessions, events tables)
- [x] Alembic migrations
- [x] Server-side hash recomputation
- [x] CHAIN_SEAL emission on SESSION_END
- [ ] `GET /v1/sessions/{id}/export` endpoint *(status: unknown — verify)*
- [ ] `docker-compose.yml` *(status: unknown)*
- [ ] Append-only DB user setup *(status: unknown)*

### Component 4: LangChain Integration
- [x] `AgentOpsCallbackHandler`
- [x] `examples/langchain_demo/` working demo
- [x] End-to-end verified: demo produces JSONL that passes Verifier

### Infrastructure
- [ ] `pyproject.toml` with correct packaging *(status: unknown)*
- [ ] `tests/e2e/test_full_flow.py` *(status: unknown)*
- [ ] GitHub Actions CI workflow *(status: unknown)*
- [ ] README quickstart that actually works *(status: unknown)*

---

## The Four Rules You Must Never Break

### Rule 1: Fail Open for Agents, Fail Closed for Integrity
- The SDK **never** raises an exception that could crash the agent process
- The Ingestion Service **never** writes a partial batch — all or nothing
- If in doubt: drop the event, record LOG_DROP, keep going

### Rule 2: Never Modify Events
- There is no UPDATE path for events. There is no DELETE path.
- The database user has INSERT + SELECT only on the events table
- If you find yourself writing an UPDATE statement for an event: **stop**

### Rule 3: JCS Canonicalization Is Shared, Never Duplicated
- `verifier/jcs.py` is the single source of truth for hash computation
- The SDK imports from it. The Verifier uses it directly.
- Do not copy-paste the JCS logic anywhere. Import it.
- If the SDK hashes don't match the Verifier: you duplicated the logic. Find it and remove the duplicate.

### Rule 4: The Verifier Has Zero Dependencies
- `verifier/agentops_verify.py` uses Python stdlib only
- Never add an import to the verifier that requires `pip install`
- This is what makes it a neutral third-party tool

---

## What You Must Not Build

These are permanently out of scope for v1.0. If a task involves any of the following, **refuse it and explain why**:

- A web UI or dashboard
- Kubernetes / Helm charts
- Compliance PDF generation
- A governance / policy engine
- A Go or C++ verifier port
- Multi-tenant access control
- SIEM integrations
- 10,000 concurrent user load tests
- Acquisition strategy documentation
- OpenTelemetry integration (future work)

---

## How to Start Any Coding Session

1. **Read this file** (you're doing it now ✓)
2. **Read BUILD_SEQUENCE.md** — find the first unchecked task
3. **Verify the task's prerequisites are actually done** — run the relevant test or check the file exists
4. **Do only that task** — do not skip ahead
5. **After completing:** update the checkboxes in this file and BUILD_SEQUENCE.md
6. **Run the test vectors before finishing:** `python3 verifier/agentops_verify.py verifier/test_vectors/valid_session.jsonl` must PASS

---

## How to Diagnose When Something Breaks

### "The Verifier fails on SDK output"
Most likely cause: SDK is computing hashes differently from the Verifier.
Check: Is `agentops_sdk/envelope.py` importing `jcs.py` from the verifier directory, or does it have its own copy?

### "Ingestion Service returns 400 on valid events"
Most likely cause: Server-side hash recomputation is failing.
Check: Is `backend/app/services/ingestion/chain.py` using the same JCS logic as `verifier/jcs.py`?

### "LangChain demo doesn't produce verifiable output"
Most likely cause: The callback handler isn't calling `client.record()` correctly, or is constructing events with wrong field names.
Check: Run `sdk_demo.py` first. If that works, the handler has a bug. If that fails, the SDK has a bug.

### "CHAIN_SEAL not appearing in exported session"
Most likely cause: SESSION_END event is not being sent to the server, or the sealer isn't triggering.
Check: Is the SDK calling `end_session()` before `send_to_server()`?

---

## File Ownership Map

| File | Owner | Can be modified? |
|---|---|---|
| `CONSTITUTION.md` | Frozen | NO |
| `PRD_v4.md` | Developer | Only to update scope decisions |
| `TRD_v1.md` | Developer | Only to update technical decisions |
| `AGENT_CONTEXT.md` | AI Agent + Developer | YES — update checkboxes after each task |
| `BUILD_SEQUENCE.md` | AI Agent + Developer | YES — check off completed tasks |
| `verifier/jcs.py` | Frozen logic | Only bug fixes, never algorithm changes |
| `agentops_sdk/envelope.py` | Frozen logic | Only bug fixes, never hash algorithm changes |
| Everything else | Actively developed | YES |

---

## The Evidence Class Contract (Frozen)

These three classes and their conditions are frozen. Do not change them.

| Class | Conditions |
|---|---|
| `AUTHORITATIVE_EVIDENCE` | CHAIN_SEAL present AND no LOG_DROP events |
| `PARTIAL_AUTHORITATIVE_EVIDENCE` | CHAIN_SEAL present AND LOG_DROP events present |
| `NON_AUTHORITATIVE_EVIDENCE` | No CHAIN_SEAL (SDK-only / local mode) |

The Verifier must report this class. The Ingestion Service must persist it on the session record.

---

## Current Known Issues

*(Update this section when you find bugs. Delete entries when fixed.)*

- [ ] `sender.py` may not exist — check before assuming it does
- [ ] `GET /v1/sessions/{id}/export` endpoint existence is unconfirmed
- [ ] CI workflow existence is unconfirmed
- [ ] `pyproject.toml` packaging is unconfirmed
- [ ] It is unknown whether the end-to-end flow (SDK → Ingestion → Export → Verify) produces AUTHORITATIVE_EVIDENCE correctly

---

*AGENT_CONTEXT.md — Keep this current. An outdated AGENT_CONTEXT is worse than no AGENT_CONTEXT.*
