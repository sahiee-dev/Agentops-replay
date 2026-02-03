# Day 3: LangChain Integration & Validation

**Date:** January 24, 2026  
**Focus:** Bridging SDK to Real Agents + Production Validation

---

## 🎯 Today's Objective

Transform AgentOps Replay from a validated spec into a **working agent integration**. By end of day, we should have:

1. A LangChain agent emitting properly formatted events
2. Manual validation proving the verifier works end-to-end
3. A compelling demo: "Agent action → Replay log → Verification"

---

## 📋 Execution Plan

### Block 1: Validation of Day 2 Work (30 min)

Before building more, confirm what we have actually works.

- [ ] **1.1** Run verifier on `sdk_session.jsonl` with `--reject-local-authority`
- [ ] **1.2** Confirm `NON_AUTHORITATIVE_EVIDENCE` classification appears
- [ ] **1.3** Create a test with server-authority events (CHAIN_SEAL)
- [ ] **1.4** Verify evidence classification changes to `AUTHORITATIVE_EVIDENCE`

**Exit Criteria:** Verifier correctly classifies evidence and rejects local authority when policy requires.

---

### Block 2: LangChain Integration Core (2-3 hours)

Build the callback handler that makes LangChain agents emit AgentOps events.

#### 2.1 Create Integration Package

```
sdk/python/agentops_replay/integrations/
├── __init__.py
├── langchain/
│   ├── __init__.py
│   ├── callback.py      # LangChain callback handler
│   ├── version.py       # Version compatibility tracking
│   └── README.md        # Integration docs
```

#### 2.2 Implement Callback Handler

- [ ] **2.2.1** Create `AgentOpsCallbackHandler` extending LangChain's `BaseCallbackHandler`
- [ ] **2.2.2** Capture events:
  - `on_llm_start` → `LLM_CALL` event
  - `on_llm_end` → `LLM_RESPONSE` event
  - `on_tool_start` → `TOOL_CALL` event
  - `on_tool_end` → `TOOL_RESULT` event
  - `on_chain_error` → `ERROR` event
- [ ] **2.2.3** Emit version metadata (LangChain version, integration version)
- [ ] **2.2.4** Handle serialization of complex objects (safely)
- [ ] **2.2.5** Implement PII redaction hooks

#### 2.3 Version Compatibility

- [ ] **2.3.1** Pin to LangChain `>=0.1.0,<0.3.0` (or current stable)
- [ ] **2.3.2** Emit `framework_version` in session metadata
- [ ] **2.3.3** Add compatibility warning system

**Exit Criteria:** LangChain agent using our callback handler emits valid AgentOps events.

---

### Block 3: Demo Agent (1 hour)

Build a simple but realistic agent that demonstrates the value.

#### 3.1 Create Demo Directory

```
examples/
├── langchain_demo/
│   ├── agent.py           # Simple ReAct agent
│   ├── run_demo.py        # Demo runner
│   ├── verify_session.py  # Verification script
│   └── README.md          # How to run
```

#### 3.2 Demo Scenario: Customer Support Agent

- [ ] **3.2.1** Agent with tools: `lookup_order`, `issue_refund`, `send_email`
- [ ] **3.2.2** Run agent with sample queries
- [ ] **3.2.3** Export session to JSONL
- [ ] **3.2.4** Verify with `agentops_verify.py`
- [ ] **3.2.5** Show evidence classification in output

**Exit Criteria:** `python run_demo.py && python verify_session.py` produces verified replay.

---

### Block 4: First "Incident" Simulation (1 hour)

The real test: can we use this for incident investigation?

#### 4.1 Simulate PII Leak Scenario

- [ ] **4.1.1** Agent accidentally logs customer email in tool args
- [ ] **4.1.2** Show how replay captures the exact action
- [ ] **4.1.3** Demonstrate redaction hook (hash preservation)
- [ ] **4.1.4** Export as compliance artifact

#### 4.2 Document the Flow

Create `examples/langchain_demo/INCIDENT_INVESTIGATION.md`:

```markdown
## Incident: Agent Exposed Customer PII

### Timeline

1. Agent received query at T+0
2. Tool call `lookup_customer` at T+1 (with email in args)
3. Tool result contained PII at T+2

### Evidence

- Session ID: abc-123
- Evidence Class: AUTHORITATIVE_EVIDENCE
- Verification: VALID (hash chain intact)

### Resolution

Applied redaction policy, re-exported for compliance.
```

**Exit Criteria:** Complete incident investigation workflow documented with real output.

---

### Block 5: Integration Tests (30 min)

- [ ] **5.1** Test callback handler with mock LangChain components
- [ ] **5.2** Test event emission format matches SCHEMA.md
- [ ] **5.3** Test version metadata is captured
- [ ] **5.4** Test graceful handling of serialization failures

**Exit Criteria:** `pytest` passes on integration tests.

---

### Block 6: Documentation Update (30 min)

- [ ] **6.1** Update progress.md with Day 3 accomplishments
- [ ] **6.2** Add LangChain quickstart to README.md
- [ ] **6.3** Document any spec changes needed

---

## 🚫 Explicitly NOT Doing Today

- Multiple framework integrations (CrewAI, AutoGen)
- Ingestion service implementation
- Frontend/dashboard work
- PDF export implementation
- Advanced policy engine

---

## 📁 Files to Create/Modify

| Action | File                                                            |
| ------ | --------------------------------------------------------------- |
| CREATE | `sdk/python/agentops_replay/integrations/langchain/callback.py` |
| CREATE | `sdk/python/agentops_replay/integrations/langchain/__init__.py` |
| CREATE | `sdk/python/agentops_replay/integrations/langchain/version.py`  |
| CREATE | `examples/langchain_demo/agent.py`                              |
| CREATE | `examples/langchain_demo/run_demo.py`                           |
| CREATE | `examples/langchain_demo/verify_session.py`                     |
| CREATE | `examples/langchain_demo/README.md`                             |
| MODIFY | `progress.md` (end of day update)                               |
| MODIFY | `README.md` (add quickstart)                                    |

---

## ✅ Success Criteria

By end of Day 3:

1. ✅ Verifier manual validation complete
2. ✅ LangChain callback handler implemented
3. ✅ Demo agent running and producing verified logs
4. ✅ Incident simulation documented
5. ✅ Integration tests passing
6. ✅ progress.md updated

---

## 🔥 The One Thing That Matters

> **If we can show: Agent → Event Log → Verified Replay, we have product-market fit proof.**

Everything else is optimization.

---

## Dependencies

- Python 3.10+
- LangChain (`pip install langchain langchain-openai`)
- OpenAI API key (for demo agent)
- Existing SDK and verifier from Days 1-2

---

## How to Proceed

Start with Block 1 (validation). If verifier has issues, fix before moving forward.

Then proceed sequentially through Blocks 2-6.

**Target completion:** ~6 hours of focused work.

---

_Execute with audit-grade precision._
