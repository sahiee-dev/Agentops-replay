# Single Golden Path Demo Scope

**Status**: ACTIVE
**Scenario**: "The Unverified Refund"
**Goal**: Demonstrate an immutable, auditable chain of events leading to a business decision, verified by the strict AgentOps Gate.

## 1. The Scenario

A Customer Support Agent (AI) receives a request from a user to process a refund. The agent:

1.  **Decision Event**:
    - type: `AGENT_DECISION`
    - input_facts: `["user_request"]`
    - policy_version: `refund_v1`
    - outcome: `LOOKUP_TRANSACTION`
2.  **Tool Call**: Queries the `transaction_db` (mocked) with PII (Email).
3.  **Tool Result**: Receives transaction details (including sensitive data).
4.  **Decision Event**:
    - type: `AGENT_DECISION`
    - input_facts: `["transaction_amount", "user_status"]`
    - policy_version: `refund_v1`
    - outcome: `APPROVE_REFUND` (Intentional business logic mistake, but correctly recorded)
5.  **Action**: Calls `refund_payment` API.
6.  **Termination**: Ends session.

## 2. The Golden Path Components

### A. The Agent (`agent.py`)

- **Runtime**: Python 3.11
- **Library**: `agentops-sdk` (Untrusted)
- **Behavior**: Deterministic execution of the above trace.
- **Output**: Emits **UNSIGNED** or **SDK-SIGNED** events (Untrusted). The agent is NOT the authoritative signer.

### B. The Ingestion

- **Component**: `ingest.sh` -> `backend`
- **Role**: Validates schema, JCS, and timestamps.
- **Responsibility**: Applies **Authoritative Chain Seal**. Rejects any client-asserted authority.
- **Output**: Stored Session in Postgres with authoritative sequence.

### C. The Gate (`verify.sh`)

- **Component**: `agentops-verify`
- **Input**: The stored JSON export.
- **Criteria**:
  - Chain Seal: VALID (Server Authority)
  - Tamper Check: PASS
  - Redaction: VERIFIED
- **Invariant**: `verification_mode = "REDACTED"` (MANDATORY).
- **Output**: `verification_report.json` (PASS).

### D. The Replay (`replay.sh`)

- **Input**: Verified Session.
- **Behavior**: Re-executes the trace.
- **Constraint**: Mocks `transaction_db` and `refund_payment` with recorded values.
- **Success**: Final State Hash matches Recorded Final State Hash.
- **Hard Invariant**: This demo **MUST FAIL** if replay is attempted on an unverified session.

## 3. Redaction & Hashing Rules

- Raw PII MAY be present in tool call results at runtime.
- Session logs **MUST store redacted values** prior to hashing.
- Hash chain is computed over the **redacted canonical form**.
- **verification_mode** must be strictly set to verify the redacted stream.

## 4. Required Artifacts

The demo MUST produce:

1.  `session_golden.json`: The raw, signed, canonicalized session log.
2.  `verification_report.json`: The "PASS" certificate from the Verifier.
3.  `replay_trace.log`: Proof of deterministic re-execution.

## 5. Failure Modes (Must Fail Loudly)

| Deviation                              | Result              |
| :------------------------------------- | :------------------ |
| Any missing link in hash chain         | `VERIFY_FAIL`       |
| Any signature mismatch                 | `VERIFY_FAIL`       |
| Replay execution divergence            | `REPLAY_DIVERGENCE` |
| Replay attempted on unverified session | `REPLAY_REFUSED`    |
| Python < 3.11                          | `startup_error`     |

## 6. Directory Layout

```text
reference_demo/
├── DEMO_SCOPE.md           # This file
├── agent.py                # Source of Truth (The Incident)
├── requirements.txt        # Frozen dependencies
├── env.prod                # Strict production config
├── ingest.sh               # Simulates ingestion pipeline
├── verify.sh               # The "Gate" script
├── replay.sh               # The deterministic replay script
└── expected_output/        # The "Golden" artifacts
    ├── session_golden.json
    └── verification_report.json
```
