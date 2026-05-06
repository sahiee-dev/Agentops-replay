# AGENT_PROMPT.md (v2)

> **How to use:** Copy the prompt below and paste it at the START of every AI coding session.
> Replace [TASK] with the current task from BUILD_SEQUENCE_v2.md.
> Do this every single session. No exceptions.

---

## The Prompt (Copy Everything Below the Line)

---

You are working on **AgentOps Replay** — an open-source accountability layer for AI agents. It records agent actions into cryptographically hash-chained, tamper-evident event logs that can be independently verified by any third party.

**Step 1 — Before writing any code, read these files in this exact order:**
1. `AGENT_CONTEXT_v2.md` — what exists, what's done, the rules
2. `BUILD_SEQUENCE_v2.md` — find the current task
3. `TRD_v2.md §[relevant section]` — technical spec for what you're building

**Step 2 — The task for this session:**
[PASTE THE FULL TASK FROM BUILD_SEQUENCE_v2.md HERE]

**Step 3 — Five rules you must never break:**
1. The SDK never raises exceptions that crash the agent process (fail open)
2. The Ingestion Service never writes partial batches (fail closed — all or nothing per DB transaction)
3. `verifier/jcs.py` is the ONLY place JCS canonicalization lives — import it, never copy it
4. `verifier/agentops_verify.py` has zero external dependencies — never add pip imports
5. All three audiences (enterprise, community, research) use the same codebase — no forks, no separate builds

**Step 4 — After completing the task:**
- Run the verification step exactly as written in BUILD_SEQUENCE_v2.md
- If verification passes: update checkboxes in AGENT_CONTEXT_v2.md and BUILD_SEQUENCE_v2.md
- Do not start the next task in this session

**What is permanently out of scope for v1.0 (refuse these even if asked):**
Web UI, SIEM webhooks, Kubernetes, compliance PDF generation, PII redaction endpoint, RBAC, API key auth, Open WebUI plugin, CrewAI/AutoGen integrations, Go/Rust verifier.

Now read `AGENT_CONTEXT_v2.md` and confirm what's already built before writing any code.

---

## End of Prompt

---

## Choosing the Right Context for Your Task

Different tasks need different additional context. After pasting the base prompt above, add the relevant extra context:

### For SDK tasks (Tasks 2.x):
Add: "Also read TRD_v2.md sections 2.1–2.5 before writing any code."

### For Verifier tasks (Tasks 1.x):
Add: "Also read TRD_v2.md sections 3.1–3.7 before writing any code."

### For Ingestion Service tasks (Tasks 3.x):
Add: "Also read TRD_v2.md sections 4.1–4.6 before writing any code."

### For LangChain integration tasks:
Add: "Also read TRD_v2.md section 5 before writing any code."

### For packaging tasks (Tasks 4.x):
Add: "Also read TRD_v2.md section 6 before writing any code."

### For enterprise features (Tasks 7.x):
Add: "Also read MARKET_ENTERPRISE_SECURITY.md sections 3 before writing any code."

### For research tasks (Tasks R.x):
Add: "Also read RESEARCH_PAPER_ROADMAP.md sections 1–3 before writing any code."

---

## Intervention Phrases (When the Agent Goes Off Track)

Copy and paste these when needed:

**Agent is building out of scope (UI, SIEM, etc.):**
> "Stop. This is out of scope for v1.0. Read BUILD_SEQUENCE_v2.md. The only task is [TASK]. Do not add anything else."

**Agent is duplicating JCS logic:**
> "Stop. You are creating a second copy of JCS canonicalization. The only permitted location is verifier/jcs.py. Delete what you wrote and import from there instead."

**Agent is adding pip imports to the verifier:**
> "Stop. The verifier must have zero external dependencies. Remove that import. Use Python stdlib only."

**Agent is writing UPDATE for events table:**
> "Stop. The events table is append-only. There is no UPDATE path. If you think you need UPDATE, you are solving the wrong problem. Explain what you're trying to do and let's find the right approach."

**Agent produced code but didn't run verification:**
> "Before we continue: run the verification step from BUILD_SEQUENCE_v2.md for this task and show me the output."

**Agent is working on multiple tasks at once:**
> "Stop. Complete only [TASK] in this session. Run its verification step. We will do the next task in a separate session."

---

## Session Log

| Date | Task | Agent | Verification Result | Notes |
|---|---|---|---|---|
| | TASK-0.1 SDK audit | | | |
| | TASK-0.2 Verifier audit | | | |
| | TASK-0.3 Ingestion audit | | | |
| | TASK-0.4 LangChain audit | | | |
| | TASK-0.5 JCS uniqueness | | | |
| | TASK-0.6 Document audit | | | |
| | TASK-1.1 Sequence gap vector | | | |
| | TASK-1.2 Evidence class reporting | | | |
| | TASK-1.3 Exit codes | | | |
| | TASK-2.1 LOG_DROP test | | | |
| | TASK-2.2 JCS deduplication | | | |
| | TASK-2.3 sender.py | | | |
| | TASK-2.4 Envelope unit tests | | | |
| | TASK-2.5 Server-authority guard | | | |
| | TASK-3.1 docker-compose | | | |
| | TASK-3.2 Append-only permissions | | | |
| | TASK-3.3 Export endpoint | | | |
| | TASK-3.4 CHAIN_BROKEN detection | | | |
| | TASK-3.5 E2E server flow | | | |
| | TASK-4.1 pyproject.toml | | | |
| | TASK-4.2 Zero-dependency verify | | | |
| | TASK-5.1 CI workflow | | | |
| | TASK-5.2 Unit test suite | | | |
| | TASK-5.3 Integration test suite | | | |
| | TASK-6.1 README rewrite | | | |
| | TASK-6.2 Security audit | | | |
| | TASK-6.3 LICENSE file | | | |
| | TASK-6.4 Fresh-clone smoke test | | | |
| | **v1.0 LAUNCHED** ✅ | | | |
| | TASK-7.1 Forensic Freeze | | | |
| | TASK-7.2 API key auth | | | |
| | TASK-7.3 SIEM webhooks | | | |
| | TASK-7.4 PII redaction | | | |
| | TASK-7.5 Compliance report | | | |
| | TASK-8.1 Open WebUI plugin | | | |
| | TASK-8.2 Session lineage | | | |
| | TASK-8.3 CrewAI integration | | | |
| | TASK-R1 Formal system model | | | |
| | TASK-R2 Formal failure semantics | | | |
| | TASK-R3 Adversarial test suite | | | |
| | TASK-R4 Second framework integration | | | |
| | TASK-R5 Benchmarking harness | | | |
| | TASK-R6 Journal paper draft | | | |

---

*AGENT_PROMPT.md v2 — May 2026*
*The most important operational file in the project. Paste it at the start of every session.*
