"""
examples/sdk_demo.py - Prove SDK Compliance via Verification
"""

import os
import sys

# Add root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agentops_sdk.client import AgentOpsClient
from agentops_sdk.events import EventType


def main():
    print("Initializing AgentOps Client (Local Authority Mode)...")
    # Enable local authority to generate verifiable hashes locally
    client = AgentOpsClient(local_authority=True)

    print("Starting Session...")
    client.start_session(agent_id="demo-agent-01", tags=["verification-test"])

    print("Recording Events...")
    # 1. Model Request
    client.record(
        EventType.MODEL_REQUEST,
        {
            "model": "gpt-4",
            "provider": "openai",
            "messages": [{"role": "user", "content": "Hello"}],
            "parameters": {"temperature": 0.7},
        },
    )

    # 2. Tool Call
    client.record(
        EventType.TOOL_CALL,
        {"tool_name": "calculator", "args": {"expression": "2 + 2"}},
    )

    # 3. Decision Trace (Governance)
    client.record(
        EventType.DECISION_TRACE,
        {
            "decision_id": "dec-123",
            "inputs": {"expression": "2 + 2"},
            "outputs": {"result": 4},
            "justification": "math_policy_v1",
        },
    )

    print("Ending Session...")
    client.end_session(status="success", duration_ms=150)

    # Flush
    outfile = "sdk_session.jsonl"
    print(f"Flushing to {outfile}...")
    client.flush_to_jsonl(outfile)
    print("Done.")


if __name__ == "__main__":
    main()
