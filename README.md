# AgentOps Replay

> **The system of record for AI agent behavior**

AgentOps Replay is an open-source, production-grade observability and audit system for AI agents. Unlike traditional monitoring tools, AgentOps Replay provides **cryptographically verifiable, immutable event logs** designed for incident investigation, compliance, and post-mortems.

## Why AgentOps Replay?

When your AI agent crashes, leaks PII, or makes an unexpected decision, you need more than logs—you need **evidence**.

AgentOps Replay is built for:

- **Incident Response**: Step-by-step replay of agent behavior
- **Compliance**: Audit-grade timelines with tamper-evident integrity
- **Governance**: Policy violation detection and reporting
- **Trust**: Cryptographic proof that logs haven't been modified

## Core Principles

1. **Auditability** over convenience
2. **Correctness** over performance
3. **Evidence** over interpretation

## Architecture

```
Agent SDK (Untrusted Producer)
    ↓
Event Log (Immutable, Hash-Chained)
    ↓
Verifier (Independent Validation)
    ↓
Compliance Reports (Evidence)
```

## Quickstart — 5 minutes to PASS ✅

```bash
# Install
pip install agentops-replay

# Run the demo
python examples/sdk_demo.py

# Verify the output
agentops-verify session.jsonl
```

Expected output:
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
Evidence: NON_AUTHORITATIVE_EVIDENCE
```

## Project Structure

```
├── agentops_sdk/
│   ├── client.py            # Main SDK entry point
│   ├── events.py            # 12 canonical EventType values
│   ├── envelope.py          # 7-field envelope + JCS hash
│   └── buffer.py            # Thread-safe ring buffer + LOG_DROP
├── verifier/
│   ├── agentops_verify.py   # Standalone CLI verifier
│   ├── jcs.py               # RFC 8785 canonical JSON (authoritative copy)
│   └── test_vectors/        # valid_session, tampered_hash, sequence_gap
├── backend/
│   ├── app/                 # FastAPI ingestion service
│   ├── alembic/             # DB migrations (001 schema, 002 permissions)
│   └── docker-compose.yml   # Postgres + app deployment
├── sdk/python/agentops_replay/
│   └── integrations/langchain/handler.py  # LangChain callback handler
├── tests/
│   ├── unit/                # test_buffer, test_envelope, test_events, test_verifier
│   ├── integration/         # test_ingestion_api (requires Docker)
│   └── e2e/                 # test_full_flow
├── docs/
│   ├── EVENT_LOG_SPEC.md              # 7-field envelope, 12 event types, hash algorithm
│   ├── CHAIN_AUTHORITY_INVARIANTS.md  # Trust model, evidence classes
│   └── FAILURE_MODES.md              # LOG_DROP, CHAIN_BROKEN, fail-open/closed
├── .github/workflows/ci.yml  # CI: unit + integration + E2E
└── examples/sdk_demo.py      # Working local-authority demo
```

## What Makes This Different?

| Feature          | AgentOps Replay         | Traditional Observability |
| ---------------- | ----------------------- | ------------------------- |
| **Immutability** | Hash-chained events     | Mutable logs              |
| **Verification** | Independent CLI tool    | Trust the vendor          |
| **Compliance**   | Audit-grade exports     | Dashboard screenshots     |
| **Authority**    | Server-authoritative    | Client-side only          |
| **Redaction**    | PII-safe with integrity | Delete = evidence loss    |

## Current Status

**Phase 11 Complete** — Full repair and hardening against TRD v2.0 ✅

| Component | Status |
|---|---|
| SDK (client, buffer, envelope, events) | ✅ TRD-compliant |
| Verifier (agentops_verify.py) | ✅ Exit codes 0/1/2, JSON + text output |
| Test vectors (valid, tampered, gap) | ✅ Regenerated |
| Backend router (health, ingest, export) | ✅ 3 endpoints only |
| Alembic migrations (001 + 002) | ✅ Append-only permissions |
| Docker Compose | ✅ Postgres + app |
| LangChain handler | ✅ Privacy-by-design, canonical event types |
| Unit tests (19 tests) | ✅ All passing |
| Integration tests | ✅ Structured (requires Docker for DB tests) |
| E2E tests | ✅ Local authority + buffer overflow |
| CI workflow | ✅ .github/workflows/ci.yml |
| Documentation | ✅ EVENT_LOG_SPEC, CHAIN_AUTHORITY_INVARIANTS, FAILURE_MODES |

## Development

### Requirements

- Python 3.11+ (pinned for float determinism)
- No external dependencies for verification

### Run Tests

```bash
# Unit tests (no dependencies required)
pytest tests/unit/ -v

# E2E tests — local authority mode
pytest tests/e2e/ -v -k "not server_authority"

# Integration tests — requires Docker
cd backend && docker-compose up -d
pytest tests/integration/ -v

# Regenerate and verify test vectors
python3 verifier/generator.py
agentops-verify verifier/test_vectors/valid_session.jsonl
```

## Roadmap

- [x] Constitutional layer (CONSTITUTION.md)
- [x] Chain authority invariants (CHAIN_AUTHORITY_INVARIANTS.md)
- [x] Failure mode documentation (FAILURE_MODES.md)
- [x] Event Log Spec v0.6
- [x] Standalone verifier (`agentops-verify`)
- [x] Python SDK (local authority mode)
- [x] LangChain integration
- [ ] Ingestion service (server authority)
- [ ] Compliance report generators
- [ ] Long-term storage backend

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

**Key principle**: If a change violates the Constitution or breaks the verifier, it's invalid—even if it "works."

## License

Apache 2.0 - See [LICENSE](LICENSE)

## Citation

```bibtex
@software{agentops_replay,
  title = {AgentOps Replay: Immutable Event Logging for AI Agents},
  author = {Sahir},
  year = {2026},
  url = {https://github.com/sahiee-dev/Agentops-replay}
}
```

---

**Built for production. Designed for trust.**
