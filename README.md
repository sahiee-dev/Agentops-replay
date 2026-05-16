# AgentOps Replay

A tamper-evident behavioral audit framework for multi-agent AI systems. Every agent action is captured into a cryptographically hash-chained, append-only event log. A zero-dependency verifier proves the sequence was not modified — on any Python 3.11+ machine, with no external dependencies.

## Why This Exists

Agent evaluation frameworks depend on log integrity. If the evidence of agent behavior can be silently modified after capture, safety claims over that evidence are unenforceable.

A direct inspection of [Terrarium](https://arxiv.org/abs/2510.14312) (Nakamura et al., 2025) — the multi-agent simulation framework underlying [Colosseum](https://arxiv.org/abs/2602.15198) (Nakamura et al., 2026) — confirms:

```
grep -rn "hashlib|sha256|md5|integrity|tamper|verify|sign" terrarium/src/
```

**Zero cryptographic results across all seven log file types.** Every blackboard state snapshot, tool call record, prompt log, agent trajectory, attack event, attack summary, and experiment note is written with standard Python file I/O. Any file can be modified by any filesystem-level actor without detection. The reproducibility commitment is present; the mechanism to enforce it is absent.

A live Colosseum experiment made this concrete: Colosseum's native `metrics.json` field `colluder_posts_secret` reported **zero** secret-channel attempts across both the baseline and colluding runs. The sealed AgentOps Replay trace recorded **three** distinct secret-channel tool invocations in the colluding run and zero in the baseline. Deleting those three events from the sealed log breaks the hash chain immediately. Deleting them from the native log is undetectable.

AgentOps Replay fixes this at the architectural level.

---

## Architecture

```
Agent Process (Untrusted)
    AgentOps SDK
    ├── JCS + SHA-256 hash chain (RFC 8785)
    ├── Ed25519 per-event signatures (session-scoped key pair)
    ├── LOG_DROP on capture failure — explicit, sequenced, signed
    └── Local JSONL  ──or──  HTTP → Ingestion Service
                                        │
                              Separate process (trusted)
                              ├── Independent hash recomputation
                              ├── Ed25519 signature verification
                              ├── Append-only PostgreSQL (INSERT only)
                              └── RFC 6962 Merkle commitment → CHAIN_SEAL
                                        │
                              Standalone Verifier (independent)
                              ├── Six integrity checks
                              ├── Evidence class determination
                              └── trust_assumptions block (machine-readable)
```

Each trust zone is an independent process. The Verifier shares no code or runtime state with the Ingestion Service.

---

## Quickstart — PASS in 5 minutes

```bash
# 1. Clone and install (zero runtime dependencies for core SDK + verifier)
git clone https://github.com/sahiee-dev/Agentops-replay.git
cd Agentops-replay
pip install -e .

# 2. Run the demo
python examples/sdk_demo.py

# 3. Verify cryptographically
agentops-verify session.jsonl
```

**Expected output:**

```
AgentOps Replay Verifier v1.0
==============================
File        : session.jsonl
Session ID  : <uuid>
Events      : 6
Evidence    : NON_AUTHORITATIVE_EVIDENCE

[1/4] Structural validity ........... PASS
[2/4] Sequence integrity ............. PASS
[3/4] Hash chain integrity ........... PASS
[4/4] Session completeness ........... PASS

Result: PASS ✅
```

---

## Cryptographic Design

Every agent event is recorded as an 8-field envelope:

```json
{
  "seq": 3,
  "event_type": "TOOL_CALL",
  "session_id": "uuid",
  "timestamp": "2026-05-15T10:30:00.123456Z",
  "payload": {"tool_name": "calculator", "args_hash": "sha256(args)"},
  "prev_hash": "<event_hash of seq=2>",
  "event_hash": "sha256(JCS(all fields except event_hash and signature))",
  "signature": "Ed25519(event_hash, session_private_key)"
}
```

**Hash chain:** `prev_hash[N] = event_hash[N-1]`. Any modification to any field changes the JCS canonical form, changes the SHA-256 output, and breaks the chain at the modification point.

**Ed25519 per-event signatures:** At `SESSION_START`, the SDK generates a fresh Ed25519 key pair. The private key is held in memory and never written to disk. Every event is individually signed. The public key is embedded in `SESSION_START` and covered by the hash chain at seq=1. An attacker who rewrites the full chain must also produce valid Ed25519 signatures — which requires the in-memory private key that was never persisted. This closes attack class A5 (full chain rewrite).

**RFC 6962 Merkle commitment:** On `SESSION_END`, the Ingestion Service constructs a binary Merkle tree over all event hashes and embeds the root in `CHAIN_SEAL`. This enables O(log n) inclusion proofs: proving that a single event belongs to a sealed session requires log₂(N) hashes, not the full event sequence.

**Single JCS source:** `verifier/jcs.py` is the canonical RFC 8785 implementation. The invariant `grep -rn "def canonicalize" . | wc -l` must return exactly one result. No hash disagreement between SDK and Verifier is possible.

---

## Evidence Classes

| Class | Conditions | What It Proves |
|---|---|---|
| `SIGNED_AUTHORITATIVE_EVIDENCE` | `CHAIN_SEAL` + HMAC-SHA256 verified + Merkle root confirmed + no `LOG_DROP` | Highest. Server identity attested. Full chain rewrite detected. |
| `AUTHORITATIVE_EVIDENCE` | `CHAIN_SEAL` present + no `LOG_DROP` | Server independently verified the full chain. Complete and sealed. |
| `PARTIAL_AUTHORITATIVE_EVIDENCE` | `CHAIN_SEAL` present + `LOG_DROP` present | Server-verified. Gaps are explicit, sequenced, and signed — not silent. |
| `SIGNED_NON_AUTHORITATIVE_EVIDENCE` | Ed25519 signatures valid + no `CHAIN_SEAL` | Chain rewrite detected locally. No independent server witness. |
| `NON_AUTHORITATIVE_EVIDENCE` | Local mode, no `CHAIN_SEAL` | Chain integrity verified. Vulnerable to full chain rewrite (A5) without Ed25519. |

Every verifier output includes a `trust_assumptions` block — machine-readable, hardcoded, not configurable:

```json
{
  "byzantine_server_defended": false,
  "session_freshness_verified": false,
  "instrumentation_complete": "unknown",
  "full_chain_rewrite_defended": true
}
```

A system that does not know its own limits is not a trustworthy audit tool.

---

## Threat Model

| ID | Attack | Local (no sig) | Ed25519 signed | Server + HMAC |
|---|---|---|---|---|
| A1 | SDK injects false event | — | — | Detected |
| A2 | MITM modifies payload | — | — | Detected |
| A3 | Storage-level deletion | Detected | Detected | Detected |
| A4 | Insider reorders events | Detected | Detected | Detected |
| A5 | Full chain rewrite | **Not detected†** | Detected | Detected |

† Known boundary condition. Documented in `docs/TRUST_MODEL.md §4.5` and recorded in `trust_assumptions.full_chain_rewrite_defended`. All 37 adversarial tests pass on CI.

---

## Colosseum Integration and Differential Audit

Colosseum (Nakamura et al., 2026) audits LLM agent collusion in multi-agent systems. Its central claim — "what matters is the evidence of collusion, i.e., detecting a collusive action, and not just discussing it in text" — requires that the evidence be unmodifiable. The interaction traces that constitute this evidence (`tool_calls.json`, `agent_prompts.json`) are Terrarium mutable log files.

AgentOps Replay provides the missing integrity layer.

### ColosseumAuditSession

```python
from examples.colosseum_adapter.colosseum_adapter import ColosseumAuditSession

with ColosseumAuditSession(session_id="run-001") as audit:
    audit.record_main_channel_message(agent_id, message)
    audit.record_secret_channel_message(agent_id, message)
    audit.record_agent_action(agent_id, action, is_collusive=True)
    audit.record_regret(regret_value)
# Session sealed and flushed to JSONL automatically
```

### The metrics.json Discrepancy — Live Result

Running a real Colosseum experiment (JiraTicketEnvironment, 2 agents, qwen2.5:3b via Ollama):

```
Native metrics.json:
  colluder_posts_secret: 0  ← reported for BOTH baseline and colluding runs

Sealed AgentOps Replay trace (colluding run):
  TOOL_CALL [event_type=secret_channel]  seq=4
  TOOL_CALL [event_type=secret_channel]  seq=7
  TOOL_CALL [event_type=secret_channel]  seq=11

Delta: +3 secret-channel events in colluding run vs baseline
```

The aggregate metric was wrong. The event-level trace was right. The three attempts errored (blackboard 1 did not exist), so Colosseum's aggregator recorded zero. The sealed trace recorded the attempts regardless.

### Differential Audit

```bash
python examples/colosseum_adapter/gap3_differential_audit.py
```

Compares two sealed sessions — baseline and colluding — without exposing any event payload. Reports per-type event count differentials from integrity-verified artifacts.

```bash
python examples/colosseum_adapter/demo_evidence_gap.py
```

Three-step proof:
1. Original sealed session → `PASS ✅`
2. Tampered sealed session → `FAIL ❌` (hash chain broken at exact seq)
3. Tampered native log → no detection

---

## Terrarium Integration

`AuditedBlackboardLogger` is a 50-line drop-in subclass of Terrarium's `BlackboardLogger`. Zero changes to Terrarium source required.

```bash
python examples/terrarium_adapter/demo_tamper_detection.py
```

```
Step 2 — Verify original audit record:
  Result:         ✅ PASS
  Evidence class: NON_AUTHORITATIVE_EVIDENCE

Step 4 — Verify tampered record:
  Result:         ❌ FAIL
  Failed check:   [3/4] Hash chain integrity (seq=3)
```

---

## What a PASS Proves (and What It Doesn't)

**Proves:**
- Every sequence number from 1 to N is present (gaps recorded as `LOG_DROP`, not silently dropped)
- No event was inserted, deleted, or reordered after recording
- `agent_id` and `session_id` cannot be changed without breaking the chain
- Ordering is cryptographic, not timestamp-based — timestamp manipulation does not affect chain integrity

**Does not prove:**
- Content (payloads are stored as SHA-256 hashes only — raw content never written)
- Instrumentation completeness (events never passed to the SDK are invisible)
- Session freshness (a valid historical session reports PASS identically to a fresh one)
- Causality between events or external effects of tool calls

---

## Components

| Component | Path | Description |
|---|---|---|
| Core SDK | `agentops_sdk/` | Hash chain, Ed25519 signing, LOG_DROP, local JSONL or HTTP send |
| Verifier | `verifier/` | Zero-dependency CLI. Six checks. Evidence class. trust_assumptions. |
| Ingestion Service | `backend/` | FastAPI + PostgreSQL. Independent hash recomputation. Merkle seal. |
| Terrarium Adapter | `examples/terrarium_adapter/` | Drop-in AuditedBlackboardLogger. 50 lines. |
| Colosseum Adapter | `examples/colosseum_adapter/` | ColosseumAuditSession wrapper. Differential audit. |
| LangChain Integration | `sdk/python/` | AgentOpsCallbackHandler. Zero config. Content hashed at boundary. |

---

## Development

```bash
# Install with all extras
pip install -e ".[langchain,server,dev]"

# Unit tests (no external dependencies)
pytest tests/unit/ -v

# Adversarial test suite (A1–A5, all 37 tests)
pytest tests/adversarial/ -v

# Regenerate and verify test vectors
python verifier/generator.py
agentops-verify verifier/test_vectors/valid_session.jsonl
agentops-verify verifier/test_vectors/tampered_hash.jsonl  # must exit 1
agentops-verify verifier/test_vectors/sequence_gap.jsonl   # must exit 1

# Start Ingestion Service (Docker required)
docker-compose -f backend/docker-compose.yml up -d
curl http://localhost:8000/health
```

**Requirements:** Python 3.11+ (required for JCS float serialization determinism — see `docs/EVENT_LOG_SPEC.md`)

---

## Documentation

- [`docs/TRUST_MODEL.md`](docs/TRUST_MODEL.md) — Formal guarantees, threat model, five adversary classes, known limits
- [`docs/EVENT_LOG_SPEC.md`](docs/EVENT_LOG_SPEC.md) — 8-field envelope, 12 event types, hash algorithm, GENESIS_HASH
- [`docs/CHAIN_AUTHORITY_INVARIANTS.md`](docs/CHAIN_AUTHORITY_INVARIANTS.md) — Authority separation, evidence class conditions, frozen invariants
- [`docs/FAILURE_MODES.md`](docs/FAILURE_MODES.md) — LOG_DROP semantics, CHAIN_BROKEN, A5 boundary condition
- [`docs/REGULATORY_NOTE.md`](docs/REGULATORY_NOTE.md) — Hedged alignment with EU AI Act, NIST AI RMF, ISO/IEC 42001

---

## Related Work

This system was built in direct response to gaps identified in:

- **Terrarium** (Nakamura et al., 2025) — arXiv:2510.14312 — UMass CICS AI Security Lab
- **Colosseum** (Nakamura et al., 2026) — arXiv:2602.15198 — UMass CICS AI Security Lab
- **Auditable Agents** (Nian et al., 2026) — arXiv:2604.05485 — ecosystem-scale survey confirming the gap across six open-source agent projects

The formal treatment of evidence classes, authority separation, LOG_DROP semantics, and the Colosseum differential audit is described in the companion paper:

> Shaik Ahamed Sahir. *AgentOps Replay: Tamper-Evident Behavioral Sequence Integrity for Multi-Agent Systems.* arXiv preprint, 2026. [Paper link — to be added after arXiv submission]

---

## License

Apache 2.0 — See [LICENSE](LICENSE)

---

> **Note on naming:** This project is currently named AgentOps Replay for continuity with an earlier published system (Sahir, IEEE 2026) and active external links. A rename to **Tessera** is planned once link dependencies resolve. The name Tessera better reflects the system's actual function, cryptographic chain-of-custody and tamper-evident audit, rather than session replay, which was the focus of the v1 system. If you are reading this after the rename, the repository will have redirected automatically.
