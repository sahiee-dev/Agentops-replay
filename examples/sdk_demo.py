"""
examples/sdk_demo.py — Minimal working example (local authority mode).

Demonstrates the AgentOps Replay SDK end-to-end:
  SDK → JSONL → Verifier

Usage:
    python3 examples/sdk_demo.py
"""

import os
import sys

# Allow running from any directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agentops_sdk.client import AgentOpsClient
from agentops_sdk.events import EventType


def main() -> None:
    print("Initializing AgentOps Client (local_authority=True)...")
    client = AgentOpsClient(local_authority=True, buffer_size=1000)

    print("Starting session...")
    session_id = client.start_session(agent_id="demo-agent-01")
    print(f"  session_id: {session_id}")

    print("Recording events...")

    client.record(
        EventType.LLM_CALL,
        {
            "model_id": "gpt-4",
            "prompt": "What is the capital of France?",
        },
    )

    client.record(
        EventType.LLM_RESPONSE,
        {
            "model_id": "gpt-4",
            "content": "The capital of France is Paris.",
        },
    )

    client.record(
        EventType.TOOL_CALL,
        {
            "tool_name": "calculator",
            "args": {"expression": "2 + 2"},
        },
    )

    client.record(
        EventType.TOOL_RESULT,
        {
            "tool_name": "calculator",
            "result": 4,
        },
    )

    print("Ending session...")
    client.end_session(status="success")

    outfile = "session.jsonl"
    print(f"Flushing to {outfile}...")
    client.flush_to_jsonl(outfile)
    print(f"Done. Output: {os.path.abspath(outfile)}")


if __name__ == "__main__":
    main()
