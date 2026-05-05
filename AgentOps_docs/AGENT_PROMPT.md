# AGENT_PROMPT.md

> **How to use this file:**  
> Copy the prompt below and paste it at the START of every AI coding session (Claude, Gemini, etc.)  
> Replace the [TASK] placeholder with the current task from BUILD_SEQUENCE.md  
> That's it. Do this every time. Never start a session without it.

---

## The Prompt (Copy Everything Below This Line)

---

You are working on AgentOps Replay, a Python library and server that records AI agent behavior into tamper-evident, cryptographically verifiable logs.

**Before writing any code, read these files in this order:**
1. `AGENT_CONTEXT.md` — what exists, what's done, what the rules are
2. `BUILD_SEQUENCE.md` — find the current task
3. `TRD_v1.md` — technical spec for the component you're working on

**The task for this session:**
[PASTE THE SPECIFIC TASK FROM BUILD_SEQUENCE.md HERE — e.g., "TASK-3.3: Implement GET /v1/sessions/{id}/export"]

**Four rules you must never break:**
1. The SDK never raises exceptions that crash the agent process (fail open)
2. The Ingestion Service never writes partial batches (fail closed)
3. `verifier/jcs.py` is the ONLY place JCS canonicalization logic lives — never duplicate it
4. `verifier/agentops_verify.py` has zero external dependencies — never add pip imports to it

**After completing the task:**
- Run the verification step specified in BUILD_SEQUENCE.md
- Update the checkboxes in AGENT_CONTEXT.md
- Update the checkboxes in BUILD_SEQUENCE.md
- Do not start the next task in the same session

**Out of scope for this entire project right now:**
- Web UI / dashboard
- Kubernetes
- Compliance PDF generation
- Go/C++ verifier
- Multi-tenant SaaS
Do not build any of these even if it seems like a natural next step.

Now read `AGENT_CONTEXT.md` and confirm what's already built before writing any code.

---

## End of Prompt

---

## Tips for Using AI Agents Effectively on This Project

### Start every session fresh
Don't rely on the AI "remembering" previous sessions. Always paste the prompt above. The context window is the agent's entire memory.

### One task per session
AI agents get confused when asked to do multiple things. Pick one task from BUILD_SEQUENCE.md. Finish it. Verify it. Start a new session for the next task.

### Always run the verification step
The task isn't done until the verification passes. If you skip verification, you might have broken something and not know it until three tasks later.

### When the agent goes off-track
Signs it's going off track:
- It starts talking about Kubernetes
- It starts adding imports to `agentops_verify.py`
- It suggests a UI component
- It proposes a new architecture that doesn't match the four components
- It starts modifying `verifier/jcs.py` logic instead of just importing it

**Response:** Paste this: *"Stop. Read AGENT_CONTEXT.md again. The task is only [TASK]. Do not add anything else."*

### When the agent breaks something
If the agent breaks existing functionality:
1. Don't panic
2. Run: `python3 verifier/agentops_verify.py verifier/test_vectors/valid_session.jsonl`
3. If that fails, the hash chain logic is broken — revert to the last working state
4. The JCS logic in `verifier/jcs.py` is almost always the culprit — check if it was modified

### Using Claude Sonnet 4.6 vs Gemini
- **Claude** is better for: understanding the Constitution constraints, careful code that doesn't over-engineer
- **Gemini** is better for: large file operations, holding more context at once
- Both need the AGENT_PROMPT above. Neither remembers previous sessions.

---

## Session Log (Keep Track of What You Did)

Use this table to track your sessions. Update it after each session.

| Date | Task | Agent Used | Result | Notes |
|---|---|---|---|---|
| | TASK-0.1: Audit SDK | | | |
| | TASK-0.2: Audit Verifier | | | |
| | TASK-0.3: Audit Ingestion | | | |
| | TASK-0.4: Audit LangChain | | | |
| | TASK-0.5: Document audit | | | |
| | TASK-1.1: sequence_gap vector | | | |
| | TASK-1.2: Evidence class reporting | | | |
| | TASK-1.3: Exit codes | | | |
| | TASK-2.1: LOG_DROP on overflow | | | |
| | TASK-2.2: JCS not duplicated | | | |
| | TASK-2.3: sender.py | | | |
| | TASK-2.4: Thread safety | | | |
| | TASK-3.1: docker-compose | | | |
| | TASK-3.2: Append-only DB | | | |
| | TASK-3.3: Export endpoint | | | |
| | TASK-3.4: E2E server flow | | | |
| | TASK-4.1: pyproject.toml | | | |
| | TASK-4.2: Zero-dependency check | | | |
| | TASK-4.3: Install verification | | | |
| | TASK-5.1: GitHub Actions | | | |
| | TASK-5.2: Unit test coverage | | | |
| | TASK-6.1: README quickstart | | | |
| | TASK-6.2: No secrets audit | | | |
| | TASK-6.3: LICENSE file | | | |
| | TASK-6.4: Final smoke test | | | |

---

*AGENT_PROMPT.md — The most important operational file in the project.*
