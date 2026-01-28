#!/usr/bin/env python3
"""
Run Demo - Execute the customer support agent and capture events

This script demonstrates the full AgentOps Replay workflow:
1. Initialize AgentOps callback handler
2. Run LangChain agent with various queries
3. Export session to JSONL for verification
"""

import sys
import os

# Add project paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'sdk', 'python'))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'agentops_sdk'))

import json
from datetime import datetime

# Check for LangChain
try:
    from agent import create_agent, get_refunds, get_emails, LANGCHAIN_INSTALLED
except ImportError as e:
    print(f"Error importing agent: {e}")
    sys.exit(1)

# Check for AgentOps SDK
try:
    from agentops_replay.integrations.langchain import AgentOpsCallbackHandler
    AGENTOPS_AVAILABLE = True
except ImportError:
    print("Warning: AgentOps integration not available, running without callbacks")
    AGENTOPS_AVAILABLE = False

# Demo queries to run
DEMO_QUERIES = [
    "Can you look up order ORD-001 and tell me its status?",
    "I want a refund for order ORD-001. The reason is that the item arrived damaged.",
    "Please send an email to the customer for order ORD-001 confirming their refund.",
]


def run_demo(use_agentops: bool = True, output_file: str = "session_output.jsonl"):
    """
    Run a demonstration of the AgentOps Replay workflow using a LangChain-based agent.
    
    Runs a sequence of predefined demo queries against a customer-support agent, optionally records an AgentOps session via a callback handler, and may export session events to a JSONL file when AgentOps is enabled.
    
    Parameters:
        use_agentops (bool): If True and AgentOps is available, attach an AgentOps callback handler and record a session.
        output_file (str): Path to write exported session JSONL when AgentOps recording is active.
    
    Returns:
        bool: `True` if the demo completed successfully, `False` if an error occurred or required configuration was missing.
    """
    print("=" * 60)
    print("AgentOps Replay - LangChain Demo")
    print("=" * 60)
    print()
    
    if not LANGCHAIN_INSTALLED:
        print("ERROR: LangChain not installed.")
        print("Install with: pip install langchain langchain-openai")
        return False
    
    # Check for OpenAI API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable not set")
        print("Set with: export OPENAI_API_KEY='your-key'")
        return False
    
    # Initialize callbacks
    callbacks = []
    handler = None
    
    if use_agentops and AGENTOPS_AVAILABLE:
        print("[+] Initializing AgentOps Replay callback handler...")
        handler = AgentOpsCallbackHandler(
            agent_id="customer-support-demo-v1",
            local_authority=True,  # Testing mode - SDK seals chain
            buffer_size=10000,
            redact_pii=False,  # Set to True to redact PII
            tags=["demo", "langchain", "customer-support"]
        )
        handler.start_session(additional_tags=["day-3-demo"])
        callbacks = [handler]
        print(f"    Session started with ID: {handler.client.session_id}")
    else:
        print("[!] Running without AgentOps callback handler")
    
    print()
    
    # Create agent
    print("[+] Creating customer support agent...")
    try:
        agent = create_agent(api_key=api_key, callbacks=callbacks)
        print("    Agent created successfully")
    except Exception as e:
        print(f"ERROR: Failed to create agent: {e}")
        if handler:
            handler.end_session(status="error")
            handler.export_to_jsonl(output_file)
        return False
    
    print()
    
    # Run queries
    results = []
    for i, query in enumerate(DEMO_QUERIES, 1):
        print(f"[{i}/{len(DEMO_QUERIES)}] Query: {query}")
        print("-" * 40)
        
        try:
            result = agent.invoke(
                {"input": query},
                config={"callbacks": callbacks}
            )
            output = result.get("output", "No output")
            print(f"Response: {output}")
            results.append({
                "query": query,
                "response": output,
                "success": True
            })
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({
                "query": query,
                "error": str(e),
                "success": False
            })
        
        print()
    
    # End session and export
    if handler:
        print("[+] Ending session and exporting...")
        
        # Derive session status from results
        if all(r['success'] for r in results):
            status = "success"
        elif any(r['success'] for r in results):
            status = "partial_failure"
        else:
            status = "failure"
        
        handler.end_session(status=status)
        handler.export_to_jsonl(output_file)
        print(f"    Session exported to: {output_file}")

    
    # Summary
    print()
    print("=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    print()
    print(f"Queries executed: {len(DEMO_QUERIES)}")
    print(f"Successful: {sum(1 for r in results if r['success'])}")
    print(f"Refunds issued: {len(get_refunds())}")
    print(f"Emails sent: {len(get_emails())}")
    print()
    
    if handler:
        print("Session data exported to:", output_file)
        print()
        print("To verify the session, run:")
        print("  python verify_session.py")
        print("  # or")
        print(f"  python ../../verifier/agentops_verify.py {output_file}")
    
    return True


def run_mock_demo(output_file: str = "session_output.jsonl"):
    """
    Run a mock AgentOps Replay session and export generated events to a JSONL file.
    
    Parameters:
        output_file (str): Path to write the exported JSONL session (default "session_output.jsonl").
    
    Returns:
        success (bool): True if the mock session was created and exported successfully; False on import or runtime errors.
    """
    print("=" * 60)
    print("AgentOps Replay - Mock Demo (No API Key Required)")
    print("=" * 60)
    print()
    
    try:
        from agentops_sdk.client import AgentOpsClient
        from agentops_sdk.events import EventType
    except ImportError as e:
        print(f"ERROR: Could not import AgentOps SDK: {e}")
        return False
    
    print("[+] Creating mock session...")
    client = AgentOpsClient(local_authority=True, buffer_size=1000)
    client.start_session(
        agent_id="customer-support-demo-v1",
        tags=["demo", "mock", "day-3"]
    )
    print(f"    Session ID: {client.session_id}")
    
    # Simulate events
    print()
    print("[+] Recording mock events...")
    
    # 1. Model request/response
    client.record(EventType.MODEL_REQUEST, {
        "model": "gpt-4o-mini",
        "provider": "openai",
        "messages": [{"role": "user", "content": "Look up order ORD-001"}],
        "parameters": {"temperature": 0}
    })
    print("    - MODEL_REQUEST recorded")
    
    # 2. Tool call
    client.record(EventType.TOOL_CALL, {
        "tool_name": "lookup_order",
        "args": {"order_id": "ORD-001"}
    })
    print("    - TOOL_CALL recorded")
    
    # 3. Tool result
    client.record(EventType.TOOL_RESULT, {
        "tool_name": "lookup_order",
        "result": {
            "order_id": "ORD-001",
            "status": "shipped",
            "customer_email": "john.doe@example.com",  # PII included
            "refund_eligible": True
        },
        "duration_ms": 50
    })
    print("    - TOOL_RESULT recorded")
    
    # 4. Decision trace
    client.record(EventType.DECISION_TRACE, {
        "decision_id": "dec-001",
        "inputs": {"query": "Look up order ORD-001"},
        "outputs": {"action": "lookup_order", "order_found": True},
        "justification": "customer_query_policy"
    })
    print("    - DECISION_TRACE recorded")
    
    # 5. End session
    client.end_session(status="success", duration_ms=1500)
    print("    - SESSION_END recorded")
    
    # Export
    print()
    print(f"[+] Exporting to {output_file}...")
    client.flush_to_jsonl(output_file)
    
    print()
    print("=" * 60)
    print("MOCK DEMO COMPLETE")
    print("=" * 60)
    print()
    print("To verify the session, run:")
    print("  python verify_session.py")
    
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run AgentOps Replay LangChain Demo")
    parser.add_argument("--mock", action="store_true", 
                       help="Run mock demo without API key")
    parser.add_argument("--no-agentops", action="store_true",
                       help="Run without AgentOps callback")
    parser.add_argument("--output", default="session_output.jsonl",
                       help="Output JSONL file path")
    
    args = parser.parse_args()
    
    if args.mock:
        success = run_mock_demo(output_file=args.output)
    else:
        success = run_demo(use_agentops=not args.no_agentops, output_file=args.output)
    
    sys.exit(0 if success else 1)