"""
Multi-agent lineage demo.
Demonstrates parent_session_id for tracking agent-to-agent delegation.

Scenario: Orchestrator agent spawns two subagents.
- Session A: Orchestrator receives user request, calls planning tool
- Session B: Subagent-1 executes retrieval (parent=Session A)
- Session C: Subagent-2 executes analysis (parent=Session A)
- Verifier confirms all three sessions independently
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentops_sdk.client import AgentOpsClient
from agentops_sdk.events import EventType

def run_orchestrator():
    client = AgentOpsClient(local_authority=True)
    session_id = client.start_session(
        agent_id="orchestrator-agent",
        metadata={
            "model_id": "claude-sonnet-4-6",
            "agent_role": "orchestrator",
            "framework": "custom"
        }
    )
    client.record(EventType.LLM_CALL, {
        "model_id": "claude-sonnet-4-6",
        "prompt_hash": "a" * 64,
        "prompt_token_count": 50
    })
    client.record(EventType.LLM_RESPONSE, {
        "model_id": "claude-sonnet-4-6",
        "content_hash": "b" * 64,
        "completion_token_count": 30,
        "finish_reason": "stop"
    })
    client.record(EventType.TOOL_CALL, {
        "tool_name": "spawn_subagent",
        "args_hash": "c" * 64,
        "args_summary": "Spawn retrieval subagent"
    })
    client.record(EventType.TOOL_RESULT, {
        "tool_name": "spawn_subagent",
        "result_hash": "d" * 64,
        "result_summary": "Subagent session initiated"
    })
    client.end_session(status="success")
    client.flush_to_jsonl("session_orchestrator.jsonl")
    return session_id

def run_subagent(parent_session_id: str, agent_name: str, output_file: str):
    client = AgentOpsClient(local_authority=True)
    client.start_session(
        agent_id=agent_name,
        metadata={
            "model_id": "claude-haiku-4-5",
            "agent_role": "subagent",
            "parent_session_id": parent_session_id,
            "framework": "custom"
        }
    )
    client.record(EventType.TOOL_CALL, {
        "tool_name": "search_documents" if "retrieval" in agent_name else "analyze_data",
        "args_hash": "e" * 64,
        "args_summary": f"{agent_name} primary action"
    })
    client.record(EventType.TOOL_RESULT, {
        "tool_name": "search_documents" if "retrieval" in agent_name else "analyze_data",
        "result_hash": "f" * 64,
        "result_summary": "Task completed"
    })
    client.end_session(status="success")
    client.flush_to_jsonl(output_file)

if __name__ == "__main__":
    print("Running multi-agent lineage demo...")

    orchestrator_session_id = run_orchestrator()
    run_subagent(orchestrator_session_id, "retrieval-subagent", "session_subagent_1.jsonl")
    run_subagent(orchestrator_session_id, "analysis-subagent", "session_subagent_2.jsonl")

    print("\nVerifying all three sessions:")
    import subprocess
    for f in ["session_orchestrator.jsonl", "session_subagent_1.jsonl", "session_subagent_2.jsonl"]:
        r = subprocess.run(
            ["python3", "verifier/agentops_verify.py", f, "--format", "json"],
            capture_output=True, text=True)
        data = json.loads(r.stdout)
        print(f"  {f}: {data['result']} ({data['evidence_class']})")

    # Verify lineage: subagent sessions reference orchestrator
    for f in ["session_subagent_1.jsonl", "session_subagent_2.jsonl"]:
        events = [json.loads(l) for l in open(f)]
        start = events[0]
        parent = start["payload"].get("parent_session_id")
        assert parent == orchestrator_session_id, f"Lineage broken in {f}"
        print(f"  {f} lineage verified: parent_session_id matches orchestrator")

    print("\nMulti-agent lineage demo complete.")
    for f in ["session_orchestrator.jsonl", "session_subagent_1.jsonl", "session_subagent_2.jsonl"]:
        os.unlink(f)
