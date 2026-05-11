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
Compliance Reports (PASS)
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
| --- | --- | --- |
| `AUTHORITATIVE_EVIDENCE` | Server emitted `CHAIN_SEAL`, zero `LOG_DROP` | Highest. Log is complete, verified by server. |
| `PARTIAL_AUTHORITATIVE_EVIDENCE` | Server emitted `CHAIN_SEAL`, but contains `LOG_DROP` | High integrity, but some events were lost (e.g. buffer overflow). |
| `NON_AUTHORITATIVE_EVIDENCE` | No `CHAIN_SEAL` (Local mode) | Cryptographically valid sequence, but vulnerable to truncation. |

## AgentOps Replay vs Alternatives

| Feature | AgentOps Replay | Traditional Observability |
| --- | --- | --- |
| **Immutability** | Hash-chained events (RFC 8785) | Mutable logs |
| **Verification** | Independent CLI tool (`agentops-verify`) | Trust the vendor |
| **Compliance** | Audit-grade exports | Dashboard screenshots |
| **Authority** | Server-authoritative | Client-side only |
| **Redaction** | PII-safe with hash integrity intact | Delete = evidence loss |

## Component Overview

1. **`agentops_sdk`**: The core dependency-free Python client that computes hashes and writes the event envelope.
2. **`verifier`**: The standalone CLI tool to validate sequence and hash integrity. Uses zero external dependencies.
3. **`backend`**: FastAPI ingestion service providing authoritative chain seals and append-only database storage.
4. **`sdk/` (Legacy/Integrations)**: Contains integrations such as the LangChain callback handler. 

## Documentation

- [Trust Model](docs/TRUST_MODEL.md) — formal guarantees, threat model, trust assumptions, and known limitations

## Deep Dives

* **Enterprise & Security:** See [MARKET_ENTERPRISE_SECURITY.md](MARKET_ENTERPRISE_SECURITY.md) for API key auth, SIEM webhooks, and compliance mappings.
* **Research Roadmap:** See [RESEARCH_PAPER_ROADMAP.md](RESEARCH_PAPER_ROADMAP.md) for our formal system model, adversarial test suites, and academic roadmap.

## Development Setup

**Requirements:**
- Python 3.11+ (Pinned for float determinism in JCS canonicalization)

```bash
# Run unit tests (no dependencies required)
pytest tests/unit/ -v

# Regenerate and verify test vectors
python3 verifier/generator.py
agentops-verify verifier/test_vectors/valid_session.jsonl

# Start the Ingestion Service (Docker required)
cd backend && docker-compose up -d
```

## License
Apache 2.0 - See [LICENSE](LICENSE)
