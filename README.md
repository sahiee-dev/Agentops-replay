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

## Quick Start

### 1. Verify Existing Logs

```bash
python3 verifier/agentops_verify.py session.jsonl --format json
```

### 2. Record Agent Events

```python
from agentops_sdk.client import AgentOpsClient
from agentops_sdk.events import EventType

# Local authority mode for testing
client = AgentOpsClient(local_authority=True)
client.start_session(agent_id="my-agent")

# Record events
client.record(EventType.TOOL_CALL, {
    "tool_name": "calculator",
    "args": {"expression": "2 + 2"}
})

client.end_session(status="success", duration_ms=150)
client.flush_to_jsonl("my_session.jsonl")
```

### 3. Verify Your Session

```bash
python3 verifier/agentops_verify.py my_session.jsonl
# Output: PASS ✅
```

## Project Structure

```
├── CONSTITUTION.md                  # Immutable project principles
├── CHAIN_AUTHORITY_INVARIANTS.md    # v1.0 - Cryptographic authority separation
├── FAILURE_MODES.md                 # v1.0 - Component failure semantics
├── EVENT_LOG_SPEC.md                # v0.6 - The truth
├── SCHEMA.md                        # Strict payload definitions
├── verifier/
│   ├── agentops_verify.py   # Standalone verification tool
│   ├── jcs.py               # RFC 8785 canonicalization
│   └── test_vectors/        # Canonical valid/invalid logs
├── agentops_sdk/
│   ├── client.py            # Main SDK entry point
│   ├── events.py            # Strict event types
│   ├── envelope.py          # Event proposals
│   └── buffer.py            # Ring buffer + LOG_DROP
└── examples/
    └── sdk_demo.py          # Working example
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

**Phase 3 Complete**: Python SDK functional ✅  
**Phase 3.5 In Progress**: Constitutional Hardening (Day-2) 🟡  
**Status**: Yellow (not green) - Awaiting failure mode validation

### Recent Updates (Day-2)

- Event Log Spec bumped to **v0.6**
- Added **three-state evidence classification**:
  - `AUTHORITATIVE_EVIDENCE` (compliance-grade)
  - `PARTIAL_AUTHORITATIVE_EVIDENCE` (incident analysis)
  - `NON_AUTHORITATIVE_EVIDENCE` (testing only)
- Cryptographic authority separation via CHAIN_SEAL enforcement
- Comprehensive failure mode documentation
- Verifier supports policy-based rejection

**Next**: Phase 4 (LangChain Integration) after Day-2 validation

## Development

### Requirements

- Python 3.11+ (pinned for float determinism)
- No external dependencies for verification

### Run Tests

```bash
# Generate test vectors
python3 verifier/generator.py

# Verify all test cases
python3 verifier/agentops_verify.py verifier/test_vectors/valid_session.jsonl
python3 verifier/agentops_verify.py verifier/test_vectors/invalid_hash.jsonl  # Should fail
```

## Roadmap

- [x] Constitutional layer (CONSTITUTION.md)
- [x] Chain authority invariants (CHAIN_AUTHORITY_INVARIANTS.md)
- [x] Failure mode documentation (FAILURE_MODES.md)
- [x] Event Log Spec v0.6
- [x] Standalone verifier (`agentops-verify`)
- [x] Python SDK (local authority mode)
- [ ] Day-2 validation complete
- [ ] LangChain integration
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
