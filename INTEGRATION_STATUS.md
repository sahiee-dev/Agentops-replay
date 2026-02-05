# Integration Status: LangChain

> **Status**: PARTIALLY VERIFIED
> **Date**: 2026-02-04
> **Verifier**: Frozen (NO CHANGES)

## Verified Capabilities ✅

1.  **SDK Authority Emission**
    - The SDK correctly emits `chain_authority: "agentops-ingest-v1"` when configured for local authority mode.
    - This satisfies the frozen verifier's requirement for trusted authorities.
    - Passes `agentops_verify` checks (Class A Evidence).

2.  **Infrastructure Integrity**
    - SDK core files (`client.py`, `envelope.py`, `buffer.py`, `remote_client.py`) fixed for Python 3.9 compatibility.
    - Mock demo generates structurally valid session events.

## Pending Verification ⚠️

1.  **Framework Semantics**
    - **NOT VERIFIED** against a running LangChain instance (library not installed in current environment).
    - `AgentOpsCallbackHandler` logic has only been static-analyzed and mock-tested.

## Next Steps

1.  Install pinned LangChain version.
2.  Run real agent demo.
3.  Verify output against frozen verifier.
4.  **Only then** formalize `INTEGRATION_CONTRACT.md`.
