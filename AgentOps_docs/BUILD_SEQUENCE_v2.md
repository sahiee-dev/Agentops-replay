# BUILD_SEQUENCE.md (v2)

> **For AI agents:** Do tasks in order. One task per session. Do not skip.
> **For the developer:** Check off tasks only after the verification step passes.
> **Rule:** A task is only done when its verification step passes — not when the code is written.

---

## How to Use This File

1. Find the first unchecked task `[ ]`
2. Read the full task including prerequisites and verification step
3. Do the task
4. Run the verification step exactly as written
5. If it passes: mark `[x]` here AND update `AGENT_CONTEXT_v2.md`
6. If it fails: fix it before moving on — never proceed with a broken task

---

## Phase 0: Audit (Do First — No Exceptions)

Establish ground truth. Nothing in the existing codebase is assumed to work until verified here.

- [ ] **TASK-0.1: Audit SDK demo**
  - **Action:** `python3 examples/sdk_demo.py`
  - **Verify:** Runs without error AND produces a `.jsonl` file
  - **Then:** `python3 verifier/agentops_verify.py <output_file>`
  - **Expected:** `PASS ✅`
  - **If FAIL:** Document what broke in AGENT_CONTEXT Known Issues. Do not proceed until fixed.

- [ ] **TASK-0.2: Audit Verifier test vectors**
  - **Action:** Run verifier against all files in `verifier/test_vectors/`
  - **Verify:**
    - valid file → `PASS ✅`
    - tampered hash file → `FAIL ❌`
    - sequence_gap file → `FAIL ❌` (if file exists — note if missing)
  - **Also check:** Does the verifier output an evidence class? Does exit code 0/1 work?
  - **Document:** Update AGENT_CONTEXT checkboxes based on what you find

- [ ] **TASK-0.3: Audit Ingestion Service startup**
  - **Action:** `cd backend && docker-compose up -d` (if docker-compose.yml exists)
  - **If docker-compose.yml missing:** Note it, skip to TASK-3.1
  - **Verify (if started):** `curl http://localhost:8000/health` returns `{"status": "ok"}`
  - **Document:** Update AGENT_CONTEXT

- [ ] **TASK-0.4: Audit LangChain demo**
  - **Action:** Run `examples/langchain_demo/agent.py`
  - **Verify:** Produces a `.jsonl` file AND that file passes the Verifier
  - **Document:** Update AGENT_CONTEXT

- [ ] **TASK-0.5: Audit JCS uniqueness**
  - **Action:** `grep -rn "def canonicalize" .`
  - **Verify:** Exactly one result, in `verifier/jcs.py`
  - **If multiple results:** Note which files have duplicate JCS logic — this will be fixed in Phase 2

- [ ] **TASK-0.6: Document complete audit results**
  - **Action:** Update every checkbox in AGENT_CONTEXT_v2.md "What Has Been Built" section
  - **Verify:** Every item has a `[x]` or `[ ]` based on actual testing, not assumptions

---

## Phase 1: Verifier Hardening

*Prerequisite: TASK-0.2 complete*

- [ ] **TASK-1.1: Add sequence_gap test vector and generator**
  - **What:** Create `verifier/generator.py` that generates all three test vectors deterministically. Create `verifier/test_vectors/sequence_gap.jsonl`.
  - **Spec:** See TRD_v2.md §3.7 for exact generator spec and vector contents
  - **Verify:**
    ```bash
    python3 verifier/generator.py
    python3 verifier/agentops_verify.py verifier/test_vectors/valid_session.jsonl
    # → PASS ✅
    python3 verifier/agentops_verify.py verifier/test_vectors/sequence_gap.jsonl
    # → FAIL ❌ with "sequence gap" in output
    ```

- [ ] **TASK-1.2: Confirm or add evidence class reporting**
  - **What:** Verifier must output evidence class in both text and JSON formats
  - **Spec:** See TRD_v2.md §3.2 and §3.3 for exact output format
  - **Verify:**
    ```bash
    python3 verifier/agentops_verify.py verifier/test_vectors/valid_session.jsonl --format json | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['evidence_class']=='NON_AUTHORITATIVE_EVIDENCE'"
    echo "Evidence class check passed"
    ```

- [ ] **TASK-1.3: Confirm or fix exit codes**
  - **What:** Exit code 0 = PASS, 1 = FAIL, 2 = ERROR
  - **Verify:**
    ```bash
    python3 verifier/agentops_verify.py verifier/test_vectors/valid_session.jsonl; echo "Exit: $?"
    # → Exit: 0
    python3 verifier/agentops_verify.py verifier/test_vectors/tampered_hash.jsonl; echo "Exit: $?"
    # → Exit: 1
    python3 verifier/agentops_verify.py /nonexistent_file.jsonl; echo "Exit: $?"
    # → Exit: 2
    ```

---

## Phase 2: SDK Hardening

*Prerequisite: TASK-0.1 complete*

- [ ] **TASK-2.1: Verify buffer overflow produces LOG_DROP**
  - **What:** Confirm buffer overflow emits LOG_DROP, never silently drops
  - **How:** Write `tests/unit/test_buffer.py` per TRD_v2.md §7.1
  - **Verify:** `pytest tests/unit/test_buffer.py -v` — all tests pass

- [ ] **TASK-2.2: Resolve JCS duplication**
  - **What:** If TASK-0.5 found duplicate JCS logic, remove duplicates and fix imports
  - **Spec:** Every component imports from `verifier/jcs.py`. No copies.
  - **Verify:**
    ```bash
    grep -rn "def canonicalize" .
    # → Exactly one result: verifier/jcs.py
    python3 examples/sdk_demo.py && python3 verifier/agentops_verify.py *.jsonl
    # → PASS ✅ (SDK hashes now match Verifier)
    ```

- [ ] **TASK-2.3: Create or verify sender.py**
  - **What:** HTTP sender from SDK to Ingestion Service. See TRD_v2.md §2.5
  - **If already exists:** Run the verification step; if it passes, mark done
  - **If missing:** Implement per TRD spec using only `urllib` (no requests/httpx)
  - **Verify:**
    ```bash
    python3 -c "from agentops_sdk.sender import EventSender; print('Import OK')"
    # → Import OK (no errors)
    ```

- [ ] **TASK-2.4: Write envelope unit tests**
  - **What:** `tests/unit/test_envelope.py` per TRD_v2.md §7.1
  - **Key test:** Compute hash for a known hardcoded event, compare to pre-computed expected value
  - **Verify:** `pytest tests/unit/test_envelope.py -v` — all pass

- [ ] **TASK-2.5: Add server-authority type guard in SDK**
  - **What:** Calling `client.record(EventType.CHAIN_SEAL, {...})` must be silently ignored and produce a LOG_DROP, not raise or insert a server-authority event
  - **Verify:** Unit test: record CHAIN_SEAL from SDK → flush → Verifier sees LOG_DROP, not CHAIN_SEAL

---

## Phase 3: Ingestion Service Hardening

*Prerequisite: TASK-0.3 complete*

- [ ] **TASK-3.1: Create or fix docker-compose.yml**
  - **What:** `backend/docker-compose.yml` that starts Postgres + FastAPI app cleanly
  - **Spec:** See TRD_v2.md §9.1
  - **Verify:**
    ```bash
    cd backend && docker-compose down -v && docker-compose up -d
    sleep 5
    curl http://localhost:8000/health
    # → {"status": "ok", "version": "1.0.0"}
    ```

- [ ] **TASK-3.2: Verify or add append-only DB permissions**
  - **What:** Migration that creates `agentops_app` user with INSERT+SELECT on events (no UPDATE, no DELETE)
  - **Spec:** See TRD_v2.md §4.4 — migration 002
  - **Verify:**
    ```bash
    # Connect to DB as agentops_app and attempt UPDATE
    docker exec -it backend_db_1 psql -U agentops_app -d agentops -c "UPDATE events SET event_type='TAMPERED' WHERE seq=1;"
    # → ERROR: permission denied for table events
    echo "Append-only constraint verified"
    ```

- [ ] **TASK-3.3: Implement or verify GET /v1/sessions/{id}/export**
  - **What:** Export endpoint returning JSONL ordered by seq ascending
  - **Spec:** See TRD_v2.md §4.3
  - **Verify:**
    ```bash
    # After ingesting a test session:
    SESSION_ID=$(python3 examples/sdk_demo.py --server-mode | grep session_id | awk '{print $2}')
    curl http://localhost:8000/v1/sessions/$SESSION_ID/export > /tmp/exported.jsonl
    python3 verifier/agentops_verify.py /tmp/exported.jsonl
    # → PASS ✅
    ```

- [ ] **TASK-3.4: Verify CHAIN_BROKEN detection**
  - **What:** If SDK sends events with seq gap (e.g., seq 1,2,4 missing 3), server emits CHAIN_BROKEN
  - **Verify:** Integration test: POST batch with deliberate seq gap → response includes CHAIN_BROKEN event OR it is stored in DB. Export session → Verifier reports PARTIAL_AUTHORITATIVE_EVIDENCE.

- [ ] **TASK-3.5: Full E2E server flow test**
  - **What:** SDK → POST /v1/ingest → CHAIN_SEAL → GET export → Verifier PASS AUTHORITATIVE_EVIDENCE
  - **Verify:**
    ```bash
    python3 tests/e2e/test_full_flow.py
    # All three tests pass (see TRD §7.3)
    ```
  - **Create** `tests/e2e/test_full_flow.py` per TRD_v2.md §7.3 if it doesn't exist

---

## Phase 4: Packaging

*Prerequisite: Phases 0–3 complete*

- [ ] **TASK-4.1: Create or fix pyproject.toml**
  - **What:** Proper Python packaging per TRD_v2.md §6.1
  - **Verify:**
    ```bash
    python3 -m venv /tmp/test_install_venv
    source /tmp/test_install_venv/bin/activate
    pip install -e ".[langchain]"
    python3 -c "import agentops_sdk; print('SDK import OK')"
    agentops-verify --help
    deactivate
    ```

- [ ] **TASK-4.2: Zero-dependency verification**
  - **What:** Confirm verifier runs in bare Python 3.11 with no packages
  - **Verify:**
    ```bash
    python3 -m venv /tmp/bare_venv
    source /tmp/bare_venv/bin/activate
    # Do NOT pip install anything
    python3 verifier/agentops_verify.py verifier/test_vectors/valid_session.jsonl
    # → PASS ✅ (no import errors)
    deactivate
    ```

---

## Phase 5: CI and Testing

*Prerequisite: Phase 4 complete*

- [ ] **TASK-5.1: Create GitHub Actions workflow**
  - **What:** `.github/workflows/ci.yml` per TRD_v2.md §8.1
  - **Verify:** Push a branch → GitHub Actions runs → all checks green

- [ ] **TASK-5.2: Write unit test suite**
  - **What:** All unit tests in TRD_v2.md §7.1
  - **Files:** `tests/unit/test_buffer.py`, `tests/unit/test_envelope.py`, `tests/unit/test_verifier.py`
  - **Verify:** `pytest tests/unit/ -v` — all pass, no skips

- [ ] **TASK-5.3: Write integration test suite**
  - **What:** All integration tests in TRD_v2.md §7.2
  - **File:** `tests/integration/test_ingestion_api.py`
  - **Verify:** `pytest tests/integration/ -v` with Ingestion Service running

---

## Phase 6: v1.0 Launch Readiness

*Prerequisite: All previous phases complete*

- [ ] **TASK-6.1: Rewrite README for multi-audience**
  - **What:** README that serves all three audiences with a clear quickstart
  - **Structure:**
    1. One-sentence description
    2. Three-line "Why This Exists" (one per audience)
    3. Architecture diagram (ASCII)
    4. **Quickstart: 5 minutes to PASS ✅** — works on a fresh machine
    5. Evidence class table (3 rows)
    6. Comparison table (AgentOps Replay vs alternatives)
    7. Component overview
    8. For enterprise: link to MARKET_ENTERPRISE_SECURITY.md
    9. For research: link to RESEARCH_PAPER_ROADMAP.md
    10. Development setup
  - **Hard rule:** Zero Kubernetes, zero compliance certification claims
  - **Verify:** Give README to someone unfamiliar with project → they reach PASS in under 10 minutes

- [ ] **TASK-6.2: Security audit — no secrets in repo**
  - **Action:**
    ```bash
    grep -r "sk-" . --include="*.py" --include="*.env" --include="*.yml"
    grep -rn "password\s*=\s*['\"]" . --include="*.py"
    grep -rn "api_key\s*=\s*['\"]" . --include="*.py"
    ```
  - **Verify:** No hardcoded secrets found (variable names like `API_KEY` are fine; actual values are not)

- [ ] **TASK-6.3: LICENSE file**
  - **Verify:** `cat LICENSE | head -3` contains "Apache License" and "Version 2.0"

- [ ] **TASK-6.4: Final fresh-clone smoke test**
  - **Action:**
    ```bash
    git clone <repo> /tmp/smoke_test_clone
    cd /tmp/smoke_test_clone
    pip install -e ".[langchain]"
    python3 examples/sdk_demo.py
    agentops-verify session.jsonl
    ```
  - **Verify:** Last command outputs `PASS ✅`
  - **This is the definition of v1.0 launched.**

---

## Phase 7: Enterprise Tier (v1.1 — Start Only After v1.0 Launch)

- [ ] **TASK-7.1: Forensic Freeze endpoint**
  - `POST /v1/sessions/{id}/freeze`
  - Emits FORENSIC_FREEZE event, sets session status='frozen'
  - No further events can be appended after freeze
  - **Spec:** MARKET_ENTERPRISE_SECURITY.md §3.2

- [ ] **TASK-7.2: API key authentication**
  - `X-API-Key` header validation middleware
  - API key storage in DB (hashed, not plaintext)
  - Environment variable: `AGENTOPS_API_KEY_REQUIRED=true`
  - **Spec:** MARKET_ENTERPRISE_SECURITY.md §3.6

- [ ] **TASK-7.3: SIEM webhook delivery**
  - Webhook configuration endpoint
  - CEF/LEEF format export
  - Real-time delivery on CHAIN_BROKEN, LOG_DROP, FORENSIC_FREEZE
  - **Spec:** MARKET_ENTERPRISE_SECURITY.md §3.1

- [ ] **TASK-7.4: PII redaction endpoint**
  - `POST /v1/sessions/{id}/redact`
  - Emits REDACTION event, replaces field with `REDACTED:sha256:<hash>`
  - **Spec:** MARKET_ENTERPRISE_SECURITY.md §3.3

- [ ] **TASK-7.5: Compliance report generation**
  - `GET /v1/sessions/{id}/compliance-report`
  - JSON format mapping events to EU AI Act, NIST AI RMF, ISO 42001 clauses
  - **Spec:** MARKET_ENTERPRISE_SECURITY.md §3.4

---

## Phase 8: Community Tier (v1.2 — Start Only After v1.1)

- [ ] **TASK-8.1: Open WebUI Pipeline plugin**
  - Drop-in pipeline for Open WebUI Pipelines API
  - Zero configuration (defaults to localhost:8000)
  - **Spec:** MARKET_OPENSOURCE_COMMUNITY.md §3.2

- [ ] **TASK-8.2: Multi-agent session lineage**
  - `parent_session_id` and `agent_role` fields in SESSION_START
  - `GET /v1/sessions/{id}/lineage` endpoint
  - **Spec:** MARKET_OPENSOURCE_COMMUNITY.md §3.4

- [ ] **TASK-8.3: CrewAI integration**
  - Callback handler for CrewAI agent events
  - **Spec:** MARKET_OPENSOURCE_COMMUNITY.md §2.4

---

## Phase 9: Research Tier (v2.0 — Run in Parallel with Development)

These tasks are research-track, not product-track. They can be worked on independently.

- [ ] **TASK-R1: Write formal system model**
  - Formal definitions: Event tuple, Session sequence, Chain Integrity predicate
  - Authority model: SDK principal, Server principal, Verifier (independent)
  - Evidence classification as a formal function EC(S)
  - **Spec:** RESEARCH_PAPER_ROADMAP.md §2.2, Gap J1

- [ ] **TASK-R2: Write formal failure semantics**
  - Formal LOG_DROP definition and guaranteed properties
  - Formal CHAIN_BROKEN definition
  - Fail-open vs fail-closed formal statement
  - **Spec:** RESEARCH_PAPER_ROADMAP.md §2.2, Gap J2

- [ ] **TASK-R3: Build adversarial test suite**
  - Four adversary models: A1 (compromised SDK), A2 (MITM), A3 (compromised storage), A4 (insider)
  - Test vector for each adversary showing what the system detects
  - **Spec:** RESEARCH_PAPER_ROADMAP.md §2.2, Gap J5

- [ ] **TASK-R4: Add CrewAI or AutoGen integration for evaluation**
  - Need a second framework for multi-framework evaluation
  - Measure latency overhead on both frameworks
  - **Spec:** RESEARCH_PAPER_ROADMAP.md §2.2, Gap J4

- [ ] **TASK-R5: Build benchmarking harness**
  - Measure: per-event latency (P50/P95/P99), throughput (events/sec), verification time vs session size
  - 10,000 event sessions, 3 runs, report mean ± std dev
  - **Spec:** RESEARCH_PAPER_ROADMAP.md §2.2, Gap J4

- [ ] **TASK-R6: Write journal paper draft**
  - Structure: RESEARCH_PAPER_ROADMAP.md §3
  - Target venue: IEEE TDSC or IEEE TIFS
  - Must cite all papers listed in RESEARCH_PAPER_ROADMAP.md §6

---

## Done: v1.0 Launched ✅

All Phase 0–6 tasks checked off = v1.0 launched.

**Definition of launched:** A developer clones the repo, follows the README, and reaches `PASS ✅` in under 10 minutes — without reading source code.

---

*BUILD_SEQUENCE.md v2 — Updated May 2026*
*One task per session. Verify before checking off. Update AGENT_CONTEXT_v2.md after every task.*
