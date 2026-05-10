"""
Direct SDK Integration Example
Shows how to instrument ANY Python framework — not just LangChain —
by calling the SDK directly.

This is the pattern for integrating with Terrarium, CrewAI, AutoGen,
or any other framework that doesn't have a pre-built adapter.
"""
import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentops_sdk.client import AgentOpsClient
from agentops_sdk.events import EventType


class MyCustomAgent:
    """Example: wrapping any agent class with AgentOps Replay."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self._recorder = AgentOpsClient(local_authority=True)

    def run(self, user_input: str) -> str:
        self._recorder.start_session(
            agent_id=self.agent_id,
            metadata={"model_id": "any-model", "framework": "custom"}
        )
        try:
            # Before LLM call
            self._recorder.record(EventType.LLM_CALL, {
                "model_id": "any-model",
                "prompt_hash": hashlib.sha256(user_input.encode()).hexdigest(),
                "prompt_token_count": len(user_input.split())
            })

            response = f"Processed: {user_input}"  # Your actual LLM call here

            # After LLM response
            self._recorder.record(EventType.LLM_RESPONSE, {
                "model_id": "any-model",
                "content_hash": hashlib.sha256(response.encode()).hexdigest(),
                "completion_token_count": len(response.split()),
                "finish_reason": "stop"
            })

            self._recorder.end_session(status="success")
            return response
        except Exception as e:
            self._recorder.end_session(status="error", exit_reason=str(e))
            raise

    def export_session(self, path: str):
        self._recorder.flush_to_jsonl(path)


if __name__ == "__main__":
    agent = MyCustomAgent("demo-agent")
    agent.run("Hello, world!")
    agent.export_session("direct_sdk_session.jsonl")

    import subprocess
    r = subprocess.run(
        ["python3", "verifier/agentops_verify.py", "direct_sdk_session.jsonl"],
        capture_output=True, text=True)
    print(r.stdout)
    os.unlink("direct_sdk_session.jsonl")
