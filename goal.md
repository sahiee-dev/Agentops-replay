# AgentOps Replay — Win or Die Execution Plan

**Mission:** Become the **system of record for AI agent behavior** before incumbents realize this is a category.

> This is not an observability tool. This is institutional memory for AI agents.

---

## 0. The Core Insight

The moment an org uses your system for **audits, post-mortems, or compliance**, they cannot remove you easily.

This is why GitHub owns code history, Datadog owns metrics, Sentry owns incident traces.

**You're not competing on dashboards. You're competing on institutional memory.**

---

## 1. Positioning (Frozen)

### You ARE:

> **The system of record for AI agent behavior**

### You are NOT:

- An observability tool
- A prompt playground
- An eval framework

### Why Engineers Adopt You:

- Incidents are expensive
- Agents are unpredictable
- Compliance teams demand evidence
- Replay saves hours of debugging

You sell **peace of mind and audit trails**, not dashboards.

---

## 2. The Real Win Condition

> **Your first win is not adoption. It's inclusion in post-mortems.**

If within 2 months:

- A team pastes an AgentOps Replay link into an incident doc
- Or attaches your PDF to a compliance ticket

**You are in.**

That's the atomic unit of success. Optimize for that, not GitHub stars.

---

## 3. The Moat

| Asymmetry Lever                 | Why It Works                                    |
| ------------------------------- | ----------------------------------------------- |
| **Hash-chained immutable logs** | Tamper-evident by design — can't retrofit later |
| **Compliance-first exports**    | Security/Legal teams become internal advocates  |
| **Deep framework hooks**        | Removal is painful once embedded                |
| **Governance primitives**       | You own the policy layer, not just metrics      |

### Why Big Players Can't Copy This Easily:

| Competitor           | Their Weakness                                                                       |
| -------------------- | ------------------------------------------------------------------------------------ |
| **LangSmith**        | Optimized for experimentation, not governance. Compliance breaks their mental model. |
| **Weights & Biases** | ML lifecycle focus. Agents are a side quest.                                         |
| **Datadog**          | Excellent infra tooling. Terrible at opinionated AI semantics.                       |

LangSmith wins with engineers.
**You win when Legal says "don't remove this".**

---

## 4. Event Schema (Constitutional Layer)

> ⚠️ **CRITICAL FIX:** No "thoughts" logging. Enterprises reject chain-of-thought capture. EU AI Act explicitly warns against storing internal reasoning.

### Schema (Final):

```json
{
  "event_id": "uuid",
  "session_id": "uuid",
  "sequence": 42,
  "event_type": "tool_call | decision_trace | error",
  "tool_name": "db_query",
  "payload": {
    "inputs": {...},
    "outputs": {...},
    "justification": "policy_applied | rule_id | tool_result"
  },
  "timestamp": "utc",
  "hash": "sha256(prev_hash + payload)"
}
```

### Event Type Rules:

| Type             | What It Captures                 | Enterprise Safe |
| ---------------- | -------------------------------- | --------------- |
| `tool_call`      | External tool invocations        | ✅ Yes          |
| `decision_trace` | Inputs → Outputs → Justification | ✅ Yes          |
| `error`          | Failures and exceptions          | ✅ Yes          |
| ~~`thought`~~    | ❌ **REMOVED** — Legal blocker   | ❌ No           |

### Reasoning Capture Policy:

- SDK defaults to **no reasoning capture**
- Reasoning capture is **explicit opt-in only**
- Docs state this clearly

---

## 5. Auto-Instrumentation Risk Mitigation

### The Danger:

Framework updates change callback semantics → your replay lies.

A replay that is _slightly wrong_ is worse than no replay.

### Required Safeguards:

1. **Version-pin integrations**
2. **Emit per session:**
   - Framework version
   - Integration version
3. **Add semantic compatibility warnings in UI:**

> ⚠️ Replay accuracy not guaranteed for LangChain ≥ 0.2.9

This builds trust. Sentry does this. You should too.

---

## 6. Compliance Report Disclaimer (Legal Safety)

### Required Language In Every Report:

- "Evidence support"
- "Audit aid"
- "Non-certifying"

**Never say:**

- "SOC2 certified"
- "GDPR compliant"
- "Compliance guaranteed"

### Why:

Enterprises love compliance evidence.
Their lawyers kill deals if you imply certification.

Build the disclaimer **into the product UI**.

---

## 7. SDK Principles

### Core:

- Zero-config defaults
- Works with any agent framework
- No vendor lock-in
- Local buffering (won't kill prod if server is down)

### Usage Bar (Must Feel Clean and Boring):

```python
from agentops import session, log_event, tool

with session(name="customer-support", user_id="u_123") as s:
    with tool("database_query", args={"order_id": 42}):
        result = db.fetch_order(42)

    log_event(
        type="decision_trace",
        payload={
            "inputs": {"order_id": 42},
            "outputs": {"status": "refunded"},
            "justification": "refund_policy_applied"
        }
    )
```

### SDK Non-Negotiables:

- Local event buffer
- Background flush thread
- Retry + exponential backoff
- Hard memory limits
- Graceful shutdown
- Kill-switch: `AGENTOPS_DISABLED=true`
- Explicit redaction hook

---

## 8. V1 Scope (Cut One Thing)

To hit timeline, **dropped from v1:**

- ~~Replay diff~~ (add after schema is battle-tested)

### V1 Ships:

- SDK (Python only)
- LangChain integration (one framework)
- Ingestion service
- Replay API
- Compliance export (JSON + barebones PDF)
- Policy engine (rules only)
- GDPR exposure report + tool audit

### V1 Does NOT Ship:

- Replay diff
- Multiple framework integrations
- SOC2 report (only GDPR + tool audit)
- Fancy UI

---

## 9. The Next 14 Days (Exact Actions)

No more strategy. Execution only.

---

### Day 1–3: Freeze the Constitution

- [ ] Finalize event schema (no "thoughts")
- [ ] Define allowed event types
- [ ] Write `SCHEMA.md` explaining _why_ each field exists
- [ ] Add "never breaking" promise
- [ ] Write JSON Schema for validation

**If this isn't rock solid, stop everything else.**

---

### Day 4–7: SDK or Death

- [ ] Python SDK only
- [ ] Local buffer implementation
- [ ] Background flush thread
- [ ] Kill-switch env var (`AGENTOPS_DISABLED=true`)
- [ ] Explicit redaction hook
- [ ] Retry + exponential backoff
- [ ] Hard memory limits
- [ ] Graceful shutdown

**No integrations yet. SDK first.**
**If SDK feels clunky, restart.**

---

### Day 8–10: LangChain Integration (Only One)

- [ ] One framework
- [ ] One happy path
- [ ] One real example:
  > "Agent leaked PII → replay → report"
- [ ] Version pinning
- [ ] Semantic compatibility metadata

**Do not add more frameworks yet.**

---

### Day 11–14: Compliance Artifact

- [ ] Session digest (hash chain verification)
- [ ] JSON export
- [ ] Barebones PDF (ugly is fine)
- [ ] Non-certifying disclaimer built into output
- [ ] GDPR exposure detection
- [ ] Tool access audit

**If you can't export evidence, nothing else matters.**

---

## 10. Architecture

```
Agent SDK
    |
    |  (batched, signed events)
    v
Ingestion Service  --->  Queue (Redis Streams)
    |                         |
    v                         v
Append-only Event Store   Policy Engine
    |                         |
    v                         v
Replay API             Violation Store
    |
    v
Compliance Export (JSON/PDF)
```

### Key Decisions:

- Split ingestion-service and query-service early
- Phase 1: PostgreSQL + partitioned tables
- If writes block, you fail

---

## 11. Monetization

You monetize **risk reduction**, not features.

| Tier             | What's Included                                                                            |
| ---------------- | ------------------------------------------------------------------------------------------ |
| **Free (OSS)**   | SDK, Self-hosted replay, Basic policies                                                    |
| **Paid (Cloud)** | Hosted immutable storage, Long-term retention, Compliance exports, Org-wide access control |

This mirrors GitHub / Sentry model.
It works because **removal is painful**.

---

## 12. Open Source Strategy

### Open (Day 1):

- SDKs
- Event schema
- Ingestion service
- Policy engine
- Integrations

### License:

- Apache 2.0 or MIT
- **Avoid AGPL** (kills enterprise adoption)

---

## 13. What Kills This

Not LangSmith. Not Datadog. Not W&B.

What kills this:

- Overbuilding
- Vague language
- Trying to impress Twitter instead of security teams
- Logging "thoughts" and getting blocked by Legal

---

## 14. What "Win" Looks Like

- Your SDK is "obvious" to include
- Your replay logs show up in incident reviews
- Compliance teams ask for your exports
- Engineers say "check the agent replay"

You're no longer building a tool.

**You're building AI accountability infrastructure.**

---

## Final Truth

> Go deeper into governance + replay than anyone else is willing to.

When agents crash, cause incidents, or face audits — you are the source of truth.

**That's the whole game.**
