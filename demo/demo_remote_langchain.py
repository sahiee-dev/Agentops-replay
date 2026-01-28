"""
Demo: LangChain agent with AgentOps remote mode.

Tests complete trust boundary: SDK → Server → AUTHORITATIVE_EVIDENCE
"""

import sys
import os

# Add SDK to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from agentops_sdk.remote_client import RemoteAgentOpsClient
from agentops_sdk.events import EventType
import time


def main():
    """
    Run a demo LangChain-style agent that records events to a remote AgentOps server.
    
    Requires a running AgentOps server at http://localhost:8000 (start with: uvicorn app.main:app --reload).
    Starts a remote session, records tool call/result events, an LLM call, and an agent output event, ends the session, and prints the remote session ID along with example curl commands for verification and export.
    """
    print("=" * 60)
    print("AgentOps Remote Mode Demo - LangChain Agent")
    print("=" * 60)
    print()
    
    # Initialize remote client (server authority)
    client = RemoteAgentOpsClient(
        server_url="http://localhost:8000",
        batch_size=5,  # Small batches for demo
        max_retries=5
    )
    
    # Start session
    print("Starting session...")
    client.start_session(agent_id="langchain-demo-agent", tags=["demo", "langchain"])
    print()
    
    # Simulate agent execution
    print("Simulating agent execution...")
    
    # Tool calls
    for i in range(3):
        print(f"  Tool call {i+1}: web_search")
        client.record(EventType.TOOL_CALL, {
            "tool_name": "web_search",
            "args": {"query": f"test query {i+1}"},
            "start_time": time.time()
        })
        time.sleep(0.1)
        
        client.record(EventType.TOOL_RESULT, {
            "tool_name": "web_search",
            "result": {"items": [f"result_{i+1}"]},
            "duration_ms": 100,
            "success": True
        })
    
    # LLM calls
    print("  LLM call: GPT-4")
    client.record(EventType.MODEL_CALL, {  # Use MODEL_CALL not LLM_CALL
        "model": "gpt-4",
        "prompt_tokens": 150,
        "completion_tokens": 75,
        "total_tokens": 225
    })
    
    # Agent output
    print("  Agent output generated")
    client.record(EventType.MODEL_RESPONSE, {  # Use MODEL_RESPONSE not AGENT_OUTPUT
        "output": "Based on the search results, here is my answer...",
        "confidence": 0.95
    })
    
    print()
    print("Ending session...")
    client.end_session(status="SUCCESS", duration_ms=5000)
    
    print()
    print("=" * 60)
    print("Session complete!")
    print()
    print(f"Session ID: {client.remote_session_id}")
    print()
    print("Next steps:")
    print(f"  1. Verify: curl http://localhost:8000/api/v1/ingest/sessions/{client.remote_session_id}")
    print(f"  2. Export JSON: curl http://localhost:8000/api/v1/export/sessions/{client.remote_session_id}/export?format=json")
    print(f"  3. Export PDF: curl http://localhost:8000/api/v1/export/sessions/{client.remote_session_id}/export?format=pdf -o compliance.pdf")
    print("=" * 60)


if __name__ == "__main__":
    main()