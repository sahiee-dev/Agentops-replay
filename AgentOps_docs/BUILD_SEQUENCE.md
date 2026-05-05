# BUILD_SEQUENCE.md

> **For AI agents:** Do tasks in order. Do not skip. Do not do multiple tasks at once.  
> **For the developer:** Check off tasks as they're confirmed working. Update AGENT_CONTEXT.md after each.  
> **Rule:** A task is only "done" when its verification step passes.

---

## How to Use This File

1. Find the first unchecked task `[ ]`
2. Read the full task description
3. Check that all prerequisites are marked done
4. Do the task
5. Run the verification step
6. If verification passes: mark `[x]` here and update AGENT_CONTEXT.md
7. If verification fails: fix it before moving on. Do not proceed with a broken task.

---

## Phase 0: Audit (Do This Before Anything Else)

These tasks establish ground truth. Do not skip them. Do not assume anything works.

- [ ] **TASK-0.1: Audit existing SDK**
  - **Action:** Run `python3 examples/sdk_demo.py` and observe output
  - **Verify:** Script runs without error AND produces a `.jsonl` file
  - **Then:** Run `python3 verifier/agentops_verify.py <output_file>`
  - **Expected:** PASS ✅
  - **If FAIL:** Do not proceed. Document what broke in AGENT_CONTEXT.md Known Issues.

- [ ] **TASK-0.2: Audit existing Verifier test vectors**
  - **Action:** Run the verifier against all test vectors in `verifier/test_vectors/`
  - **Verify:**
    - `valid_session.jsonl` → PASS ✅
    - `tampered_hash.jsonl` (or `invalid_hash.jsonl`) → FAIL ❌
    - `sequence_gap.jsonl` → FAIL ❌ (if it exists)
  - **If `sequence_gap.jsonl` doesn't exist:** Note it in AGENT_CONTEXT.md, move to TASK-1.1

- [ ] **TASK-0.3: Audit existing Ingestion Service**
  - **Action:** `cd backend && docker-compose up -d` (if docker-compose.yml exists)
  - **If no docker-compose.yml exists:** Note it in AGENT_CONTEXT.md, move to TASK-3.1
  - **If it starts:** Run `curl http://localhost:8000/health` or equivalent
  - **Verify:** Server responds

- [ ] **TASK-0.4: Audit LangChain integration**
  - **Action:** Run `examples/langchain_demo/agent.py` (or equivalent)
  - **Verify:** It produces a `.jsonl` file AND that file passes the Verifier
  - **Expected:** PASS ✅

- [ ] **TASK-0.5: Document audit results**
  - **Action:** Update the checkboxes in AGENT_CONTEXT.md with what you found
  - **Verify:** AGENT_CONTEXT.md "What Has Been Built" section reflects reality

---

## Phase 1: Verifier Hardening

*Prerequisite: TASK-0.1 and TASK-0.2 complete*

- [ ] **TASK-1.1: Add sequence_gap test vector**
  - **What:** Create `verifier/test_vectors/sequence_gap.jsonl` — a valid session where seq jumps from 3 to 5
  - **How:** Add a `verifier/generator.py` script that generates all three test vectors programmatically
  - **Verify:** `python3 verifier/agentops_verify.py verifier/test_vectors/sequence_gap.jsonl` → FAIL ❌ with message about sequence gap at seq=4
  - **Files to create/modify:** `verifier/generator.py`, `verifier/test_vectors/sequence_gap.jsonl`

- [ ] **TASK-1.2: Verify evidence class reporting**
  - **What:** Confirm the Verifier correctly outputs evidence class in both text and JSON formats
  - **How:** Run `python3 verifier/agentops_verify.py valid_session.jsonl --format json` and check the `evidence_class` field
  - **Verify:** JSON output contains `"evidence_class": "NON_AUTHORITATIVE_EVIDENCE"` for a local session
  - **If missing:** Add evidence class detection and reporting to `agentops_verify.py`

- [ ] **TASK-1.3: Verify exit codes**
  - **What:** Confirm the Verifier returns exit code 0 on PASS and 1 on FAIL
  - **How:** `python3 verifier/agentops_verify.py valid_session.jsonl; echo $?` → should print 0
  - **Verify:** Exit code 0 for PASS, 1 for FAIL
  - **If wrong:** Fix the `sys.exit()` calls in `agentops_verify.py`

---

## Phase 2: SDK Hardening

*Prerequisite: TASK-0.1 complete*

- [ ] **TASK-2.1: Verify buffer overflow produces LOG_DROP**
  - **What:** Confirm that when the buffer fills up, a LOG_DROP event is emitted
  - **How:** Write a test that creates a client with `buffer_size=5`, records 10 events, flushes to JSONL, and checks for LOG_DROP
  - **Verify:** `tests/unit/test_buffer.py` passes
  - **If LOG_DROP logic is missing:** Implement it in `buffer.py` per TRD §2.2

- [ ] **TASK-2.2: Verify JCS import is not duplicated**
  - **What:** Confirm `agentops_sdk/envelope.py` imports JCS from `verifier/jcs.py`, not its own copy
  - **How:** Search the codebase: `grep -r "def jcs_canonicalize" .`
  - **Verify:** Only one definition exists, in `verifier/jcs.py`
  - **If duplicate found:** Remove the duplicate, fix the import

- [ ] **TASK-2.3: Create sender.py (HTTP sender)**
  - **What:** Implement `agentops_sdk/sender.py` — sends events to Ingestion Service via HTTP POST
  - **Prerequisite:** TASK-3.x (Ingestion Service) should be functional
  - **Interface:**
    ```python
    class EventSender:
        def __init__(self, server_url: str): ...
        def send_batch(self, session_id: str, events: list[dict]) -> dict: ...
        # Returns {"status": "ok", "session_id": ..., "events_accepted": N}
        # Raises ConnectionError after 3 retries
        # Never mutates the events list
    ```
  - **Verify:** Unit test with a mock server passes. `AgentOpsClient(local_authority=False, server_url=...)` works.

- [ ] **TASK-2.4: Verify thread safety of buffer**
  - **What:** Run a test that records events from 10 concurrent threads
  - **Verify:** No race conditions, sequence numbers are unique, no events lost (or LOG_DROP if buffer fills)
  - **File:** `tests/unit/test_buffer_threading.py`

---

## Phase 3: Ingestion Service Hardening

*Prerequisite: TASK-0.3 complete*

- [ ] **TASK-3.1: Create or fix docker-compose.yml**
  - **What:** Ensure `backend/docker-compose.yml` exists and works
  - **Verify:** `docker-compose up -d` in `backend/` starts Postgres + the FastAPI app with no errors
  - **Check:** `curl http://localhost:8000/docs` shows the OpenAPI docs

- [ ] **TASK-3.2: Verify append-only database setup**
  - **What:** Confirm the application DB user cannot UPDATE or DELETE events
  - **How:** Check the migration files for `GRANT` statements OR add them
  - **Verify:** Attempting `UPDATE events SET event_type='TAMPERED' WHERE id=...` as the app user fails with permission error
  - **Files:** `backend/alembic/versions/` — add a migration that sets up the restricted user if not present

- [ ] **TASK-3.3: Implement or verify GET /v1/sessions/{id}/export**
  - **What:** The export endpoint must exist and return JSONL ordered by seq
  - **How:** Check if `backend/app/api/v1/endpoints/sessions.py` exists and has this endpoint
  - **Verify:** After ingesting a session, `curl http://localhost:8000/v1/sessions/{id}/export` returns newline-delimited JSON
  - **Then:** Run the exported output through the Verifier and confirm PASS

- [ ] **TASK-3.4: End-to-end server flow test**
  - **What:** Confirm the full server flow works: SDK → POST /v1/ingest → CHAIN_SEAL emitted → GET export → Verifier PASS with AUTHORITATIVE_EVIDENCE
  - **How:** Run `examples/sdk_demo.py` in server mode, then export and verify
  - **Verify:** Verifier output shows `AUTHORITATIVE_EVIDENCE`
  - **File:** Create `tests/e2e/test_full_flow.py`

---

## Phase 4: Packaging

*Prerequisite: All Phase 0-3 tasks complete*

- [ ] **TASK-4.1: Create pyproject.toml**
  - **What:** Proper Python packaging so `pip install agentops-replay` works (at least locally)
  - **Verify:** `pip install -e .` from repo root works. `import agentops_sdk` works in a fresh Python environment.
  - **Verify:** `agentops-verify --help` works as a CLI command after install
  - **Spec:** See TRD §8.1 for the pyproject.toml template

- [ ] **TASK-4.2: Zero-dependency verification**
  - **What:** Confirm `verifier/agentops_verify.py` has no third-party imports
  - **How:** `python3 -c "import verifier.agentops_verify"` in a fresh virtualenv with no packages installed
  - **Verify:** No ImportError

- [ ] **TASK-4.3: Install verification**
  - **What:** Create a clean virtualenv and install from source
  - **How:**
    ```bash
    python3 -m venv /tmp/test-install
    source /tmp/test-install/bin/activate
    pip install -e ".[langchain]"
    python3 examples/sdk_demo.py
    agentops-verify output.jsonl
    ```
  - **Verify:** Every step works without error

---

## Phase 5: CI and Testing

*Prerequisite: TASK-4.x complete*

- [ ] **TASK-5.1: Create GitHub Actions workflow**
  - **What:** `.github/workflows/ci.yml` that runs on every push to `main`
  - **Steps:**
    1. Checkout
    2. Set up Python 3.11
    3. `pip install -e ".[langchain]"`
    4. `pytest tests/unit/ -v`
    5. `python3 verifier/agentops_verify.py verifier/test_vectors/valid_session.jsonl` (must exit 0)
    6. `python3 verifier/agentops_verify.py verifier/test_vectors/tampered_hash.jsonl` (must exit 1)
    7. `python3 verifier/agentops_verify.py verifier/test_vectors/sequence_gap.jsonl` (must exit 1)
  - **Verify:** Push to a branch, workflow passes

- [ ] **TASK-5.2: Unit test coverage**
  - **What:** Ensure these specific behaviors are tested:
    - Buffer overflow → LOG_DROP event emitted
    - Hash chain computation matches Verifier
    - Sequence numbers are monotonic
    - SESSION_START is always first event
    - SESSION_END is always last event
  - **Verify:** `pytest tests/unit/ -v` all pass

---

## Phase 6: Launch Readiness

*Prerequisite: All previous phases complete*

- [ ] **TASK-6.1: README quickstart**
  - **What:** Write (or rewrite) `README.md` with a quickstart that:
    1. `pip install agentops-replay`
    2. 3 lines of code to record a session
    3. `agentops-verify session.jsonl` → PASS
  - **Verify:** Give the README to someone unfamiliar with the project. They can get to PASS in under 10 minutes.
  - **Hard constraint:** No Kubernetes, no compliance, no acquisition strategy in the README

- [ ] **TASK-6.2: No secrets audit**
  - **What:** Confirm no API keys, passwords, or PII are in any committed file
  - **How:** `grep -r "sk-" . && grep -r "password" . && grep -r "secret" .`
  - **Verify:** No sensitive values found (only variable names like `DB_PASSWORD`, not actual values)

- [ ] **TASK-6.3: LICENSE file**
  - **What:** `LICENSE` file exists with Apache 2.0 text
  - **Verify:** File exists, contains Apache 2.0

- [ ] **TASK-6.4: Final end-to-end smoke test**
  - **What:** On a fresh clone of the repo, follow the README exactly
  - **Verify:** Reach PASS ✅ without reading any source code
  - **If anything fails:** Fix the README or the code — they must match

---

## Done: Launch ✅

When all tasks above are checked, the project is launched.

**What "launched" means:** A developer can find your GitHub repo, follow the README, and have a cryptographically verified agent session in under 10 minutes. That's it.

---

## Future Work (v2.0 — Do Not Start Until All Above Is Done)

- [ ] Web UI for session replay visualization
- [ ] OpenAI Agents SDK integration
- [ ] Cloud-hosted ingestion endpoint
- [ ] Compliance report PDF export
- [ ] CrewAI / AutoGen integrations

---

*BUILD_SEQUENCE.md — Updated May 2026*  
*Rule: Never skip a task. A broken prerequisite produces broken work downstream.*
