# LangChain Demo Agent

This demo shows AgentOps Replay capturing a LangChain agent's behavior
for audit-grade verification.

## Prerequisites

```bash
pip install langchain langchain-openai
export OPENAI_API_KEY="your-api-key"
```

## Files

| File                | Description                                         |
| ------------------- | --------------------------------------------------- |
| `agent.py`          | Customer support agent with tools                   |
| `run_demo.py`       | Demo runner that executes agent and exports session |
| `verify_session.py` | Verification script using the verifier              |

## Quick Start

```bash
# Run the demo agent
python run_demo.py

# Verify the session
python verify_session.py

# Or use the verifier directly
python ../../verifier/agentops_verify.py session_output.jsonl --format text
```

## What This Demonstrates

1. **Automatic Event Capture**: LangChain callbacks → AgentOps events
2. **Tool Invocation Recording**: Every tool call is logged with args/results
3. **LLM Call Tracking**: All prompts and responses captured
4. **Verification**: Cryptographic proof of what happened
5. **Evidence Classification**: Session classified as AUTHORITATIVE/NON_AUTHORITATIVE

## Sample Output

```
Session: abc-123
Status: PASS
Evidence Class: NON_AUTHORITATIVE_EVIDENCE (local authority mode)
Sealed: True
Complete: True
Authority: sdk

Fingerprint: 9f8e7d...
```
