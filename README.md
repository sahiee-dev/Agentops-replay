# AgentOps Replay

AgentOps Replay is a cryptographically verifiable, immutable event logging system for AI agents.

## Why This Exists

* **For Developers:** Debug agent failures with deterministic replay and zero guesswork.
* **For Enterprise Security:** Guarantee tamper-evident audit trails and fail-closed compliance for AI workflows.
* **For Researchers:** Establish a formal system model and benchmark for AI agent accountability.

## Architecture

```text
Agent SDK (Untrusted Producer)
    ↓  (Hash-Chained Events)
Local JSONL / Ingestion Service
    ↓  (Immutable Log)
Standalone Verifier (Independent Validation)
    ↓
Evidence Class + Trust Assumptions (PASS / FAIL)
```

## Quickstart — 5 minutes to PASS

Get a local-authority session running and verified in under 5 minutes on a fresh machine.

```bash
# 1. Clone and install
git clone https://github.com/sahiee-dev/Agentops-replay.git
cd Agentops-replay
pip install -e .

# 2. Run the demo to generate a session log
python examples/sdk_demo.py

# 3. Verify the output cryptographically
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

Result: PASS
```

## Evidence Classes

| Evidence Class | Condition | Trust Guarantee |
|---|---|---|
| `SIGNED_AUTHORITATIVE_EVIDENCE` | `CHAIN_SEAL` present + HMAC verified + no `LOG_DROP` | Strongest. Server identity cryptographically attested via HMAC-SHA256. |
| `AUTHORITATIVE_EVIDENCE` | `CHAIN_SEAL` present + no `LOG_DROP` | High. Log complete and independently verified by server process. |
| `PARTIAL_AUTHORITATIVE_EVIDENCE` | `CHAIN_SEAL` present + `LOG_DROP` present | Server-verified, but some events were not captured (gaps are explicit and sequenced). |
| `NON_AUTHORITATIVE_EVIDENCE` | No `CHAIN_SEAL` (local mode) | Chain integrity verified; not independently witnessed by a separate process. |

## What It Proves

A `PASS` result proves **behavioral sequence integrity**: the structure, ordering, and completeness of agent behavior events — not their content. Specifically:

- Every event in the sequence is present with no unexplained gaps
- No event was inserted, deleted, or reordered after the session was recorded
- The `agent_id` and `session_id` fields cannot be changed without breaking the chain

A `PASS` result does not prove content (payloads are stored as SHA-256 hashes only), instrumentation completeness, or session freshness. See [Trust Model](docs/TRUST_MODEL.md) for the full formal specification.

## Terrarium Integration

`AuditedBlackboardLogger` is a drop-in replacement for Terrarium's `BlackboardLogger` that makes every blackboard state hash-chained and tamper-evident. Zero changes to Terrarium source required.

```bash
python3 examples/terrarium_adapter/demo_tamper_detection.py
```

**Output:**

```
2. Verifying original audit record:
   Result:         ✅ PASS
   Evidence class: NON_AUTHORITATIVE_EVIDENCE

4. Verifying tampered record:
   Result:         ❌ FAIL
```

A direct inspection of Terrarium's source confirms `grep -rn "hashlib|sha256" terrarium/src/` returns zero cryptographic results across all seven log file types. The adapter closes this gap with no modifications to Terrarium code.

See [`examples/terrarium_adapter/`](examples/terrarium_adapter/) for the full adapter, meeting scheduling demo, and integration tests.

## AgentOps Replay vs Alternatives

| Feature | AgentOps Replay | Traditional Observability |
|---|---|---|
| **Immutability** | Hash-chained events (RFC 8785 JCS) | Mutable logs |
| **Verification** | Independent zero-dependency CLI (`agentops-verify`) | Trust the vendor |
| **Evidence classes** | Four formal classes with trust assumptions | None |
| **Authority separation** | SDK / Server / Verifier — three trust levels | Client-side only |
| **Capture failure** | `LOG_DROP` — explicit, sequenced, tamper-evident | Silent or crash |
| **Redaction** | PII-safe with hash integrity intact | Delete = evidence loss |

## Component Overview

1. **`agentops_sdk`** — Core Python SDK. Computes JCS+SHA-256 hash chain, emits `LOG_DROP` on capture failure, outputs JSONL or sends to Ingestion Service.
2. **`verifier`** — Standalone zero-dependency CLI. Recomputes full hash chain, determines evidence class, outputs `trust_assumptions` block. Runs on any Python 3.11+ machine including air-gapped.
3. **`backend`** — FastAPI + PostgreSQL Ingestion Service. Independently recomputes every event hash, enforces append-only DB permissions, emits `CHAIN_SEAL` with HMAC-SHA256.
4. **`examples/terrarium_adapter`** — Drop-in adapter for Terrarium's `BlackboardLogger`. See Terrarium Integration above.
5. **`sdk/` (Legacy/Integrations)** — LangChain callback handler (`AgentOpsCallbackHandler`) and direct SDK integration examples.

## Documentation

- [Trust Model](docs/TRUST_MODEL.md) — formal guarantees, threat model, trust assumptions, and known limitations
- [Event Log Spec](docs/EVENT_LOG_SPEC.md) — 7-field envelope, 12 event types, hash algorithm, what is and is not proven
- [Chain Authority Invariants](docs/CHAIN_AUTHORITY_INVARIANTS.md) — authority separation, trust levels, frozen invariants
- [Failure Modes](docs/FAILURE_MODES.md) — LOG_DROP, CHAIN_BROKEN, adversary models A1–A5
- [Regulatory Note](docs/REGULATORY_NOTE.md) — hedged alignment with EU AI Act, NIST AI RMF, ISO/IEC 42001

## Development Setup

**Requirements:** Python 3.11+ (required for JCS float serialization determinism — see [Event Log Spec](docs/EVENT_LOG_SPEC.md))

```bash
# Install with all extras
pip install -e ".[langchain,server,dev]"

# Run unit tests (no external dependencies)
pytest tests/unit/ -v

# Run adversarial test suite (A1–A5)
pytest tests/adversarial/ -v

# Regenerate and verify test vectors
python3 verifier/generator.py
agentops-verify verifier/test_vectors/valid_session.jsonl
agentops-verify verifier/test_vectors/signed_authoritative_session.jsonl \
  --hmac-key test-hmac-key-32bytes-long

# Verify with trust assumptions visible
agentops-verify session.jsonl --verbose

# Start the Ingestion Service (Docker required)
cd backend && docker-compose up -d
curl http://localhost:8000/health
```

## License

Apache 2.0 — See [LICENSE](LICENSE)
