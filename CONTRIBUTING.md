# Contributing to AgentOps Replay

Thank you for your interest in contributing to AgentOps Replay. This project is built around strict principles to ensure audit-grade reliability.

## Before You Contribute

Read these documents in order:

1. [CONSTITUTION.md](CONSTITUTION.md) - Non-negotiable principles
2. [EVENT_LOG_SPEC.md](EVENT_LOG_SPEC.md) - The technical truth
3. [SCHEMA.md](SCHEMA.md) - Payload definitions

**Critical Rule**: Any PR that violates the Constitution or breaks `agentops-verify` will be rejected, regardless of intent.

## Development Setup

```bash
# 1. Clone and install in editable mode with all dependencies
git clone https://github.com/sahiee-dev/Agentops-replay.git
cd Agentops-replay
pip install -e ".[langchain,server,dev]"

# 2. Verify your environment
python3 --version  # Must be 3.11+ (CI uses 3.11)
```

## Running the Test Suite

We use `pytest` for all testing.

```bash
# Run fast unit tests (local only)
pytest tests/unit/

# Run integration tests (requires SQLite, no network)
pytest tests/integration/

# Run full E2E suite (requires local backend)
pytest tests/e2e/

# Run with coverage
pytest --cov=agentops_sdk --cov=verifier --cov-fail-under=90
```

## The Frozen Fields Rule

**CRITICAL**: Event envelope fields (`seq`, `event_type`, `session_id`, `timestamp`, `payload`, `prev_hash`, `event_hash`) are strictly frozen. They participate in the cryptographic hash chain. Never rename, remove, or change the type of these fields. Doing so constitutes a breaking change to the protocol and requires a major version bump and a migration of all existing logs.

## Verification of Test Vectors

Before submitting a PR, you must verify that the standalone verifier still correctly identifies the canonical test vectors.

```bash
# Should PASS
python3 verifier/agentops_verify.py verifier/test_vectors/valid_session.jsonl

# Should FAIL
python3 verifier/agentops_verify.py verifier/test_vectors/tampered_hash.jsonl
python3 verifier/agentops_verify.py verifier/test_vectors/sequence_gap.jsonl
```

## PR Checklist

- [ ] Unit tests pass (`pytest tests/unit/`)
- [ ] No new copies of JCS (import from `verifier/jcs.py`)
- [ ] No hardcoded secrets or API keys
- [ ] `from __future__ import annotations` added for Python 3.9 compatibility
- [ ] Documentation updated if schemas changed
- [ ] You have read and understood [CONSTITUTION.md](CONSTITUTION.md)
