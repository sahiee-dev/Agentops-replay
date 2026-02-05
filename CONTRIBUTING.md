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
# Clone the repo
git clone https://github.com/sahiee-dev/Agentops-replay.git
cd Agentops-replay

# Verify your environment
python3 --version  # Must be 3.11+

# Run the verifier
python3 verifier/agentops_verify.py verifier/test_vectors/valid_session.jsonl
```

## Quality Gate Contract

> **A PR is invalid if:**
>
> - Ruff fails (`ruff check .`)
> - MyPy strict fails (`mypy .`)
> - **Verifier coverage < 90%** (`pytest --cov=agentops_verify --cov-fail-under=90 agentops_verify/`)
> - Verifier output changes without spec update
> - `# type: ignore` added without inline justification

**Coverage Scope**: Quality gates enforce 90% coverage on `agentops_verify` only. This is the critical evidence infrastructure where untested branches = unproven integrity paths. Backend and SDK coverage is tracked but not gated to allow rapid iteration on non-authoritative code.

**Rationale**: The verifier is the arbiter of truth. Error paths, malformed input handling, and authority validation must be proven through tests. Coverage gaps here are integrity risks, not aesthetics.

**Python Version**: 3.11 is canonical. See `.python-version`. CI is the source of truth.

**Tool Versions**: Pinned in `pyproject.toml [project.optional-dependencies.dev]`. Do not upgrade without testing.

**Do not relax the gates to make CI green. Make the code earn the green.**

## Contribution Areas

### 1. Verifier Improvements

- Add test vectors for edge cases
- Improve error messages
- Add performance benchmarks

**Constraint**: Verifier must remain zero-dependency.

### 2. SDK Enhancements

- Add redaction helpers
- Improve buffer strategies
- Add retry logic

**Constraint**: SDK output must pass `agentops-verify` unchanged.

### 3. Framework Integrations

- LangChain integration (in progress)
- CrewAI integration
- AutoGen integration

**Constraint**: Deterministic payload extraction only.

### 4. Documentation

- Improve examples
- Add tutorials
- Fix typos

## Pull Request Process

1. **Create a branch**: `git checkout -b feature/your-feature`
2. **Make changes**: Follow existing code style
3. **Test**: Run `agentops-verify` on generated logs
4. **Commit**: Use descriptive commit messages
5. **Push**: `git push origin feature/your-feature`
6. **PR**: Include:
   - What changed
   - Why it's needed
   - Verification output (if applicable)

## Code Style

- Python: Follow PEP 8
- No external dependencies for core verifier
- Explicit is better than implicit
- Fail loudly, never silently

## Testing Requirements

All PRs must:

1. Pass existing test vectors
2. Not introduce spec drift
3. Include verification output if touching SDK/verifier

## Questions?

Open an issue with the `question` label.

## License

By contributing, you agree that your contributions will be licensed under Apache 2.0.
