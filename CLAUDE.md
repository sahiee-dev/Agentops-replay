# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with the AgentOps Replay repository.

## Repository Overview

**AgentOps Replay** is the system of record for AI agent behavior. It provides cryptographically verifiable, immutable event logs for incident investigation and compliance.

### Core Principles

1. **Auditability** over convenience.
2. **Correctness** over performance.
3. **Evidence** over interpretation.

> **CRITICAL**: The verifier must remain **ZERO-DEPENDENCY**. Do not import external packages in `verifier/`.

## Critical Documentation

Before proposing significant changes, you MUST understand:

- **[CONSTITUTION.md](CONSTITUTION.md)**: Non-negotiable principles. If a change violates this, it is invalid.
- **[EVENT_LOG_SPEC.md](EVENT_LOG_SPEC.md)**: The technical truth of the log format.
- **[CHAIN_AUTHORITY_INVARIANTS.md](CHAIN_AUTHORITY_INVARIANTS.md)**: Cryptographic authority rules.

## Environment Setup

### Core / SDK / Verifier

- **Python**: 3.11+ (Required for float determinism)
- **Dependencies**: No external dependencies for `verifier/`.

### Backend

- **Path**: `backend/`
- **Setup**: `pip install -r backend/requirements.txt`

### Frontend

- **Path**: `frontend/`
- **Setup**: `npm install` (in `frontend/` directory)

## Essential Commands

### Core & Verification

- **Verify Logs**: `python3 verifier/agentops_verify.py <logfile.jsonl>`
- **Generate Test Vectors**: `python3 verifier/generator.py`
- **Run SDK Demo**: `python3 examples/sdk_demo.py`

### Backend Development

- **Start Server**: `cd backend && uvicorn app.main:app --reload`
- **Database Migrations**: `cd backend && alembic upgrade head`

### Frontend Development

- **Start Dev Server**: `cd frontend && npm run dev`
- **Build**: `cd frontend && npm run build`

### Full System

- **Docker Compose**: `docker-compose up --build`

## Architecture Overview

1.  **Agent SDK (Untrusted Producer)**:
    - Generates events.
    - located in `agentops_sdk/`.
    - _Constraint_: Output must pass `agentops-verify` unchanged.

2.  **Event Log**:
    - Immutable, hash-chained JSONL files.
    - Adheres to `EVENT_LOG_SPEC.md`.

3.  **Verifier (Independent Validation)**:
    - located in `verifier/`.
    - Standalone, zero-dependency Python script.
    - Validates JCS canonicalization and hash chains.

## Coding Standards

### Python (SDK & Verifier)

- Follow **PEP 8**.
- **Explicit is better than implicit**.
- **Fail loudly**, never silently.
- **Float Determinism**: Be extremely careful with floating point operations; use canonical string representations where necessary.

### General

- **Commits**: Use descriptive commit messages.
- **PRs**: Must include verification output if touching SDK/verifier.

## Important Instructions for Agent

- **NEVER** introduce external dependencies to the `verifier/` directory.
- **ALWAYS** check `CONSTITUTION.md` before suggesting architectural changes.
- **ALWAYS** run `verifier/generator.py` and `verifier/agentops_verify.py` after modifying SDK or Verifier logic to ensure no regression.
