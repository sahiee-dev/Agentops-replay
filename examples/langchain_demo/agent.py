"""
Customer Support Agent with Tools

This agent demonstrates AgentOps Replay capturing:
- Tool calls (lookup_order, issue_refund, send_email)
- LLM interactions
- Decision traces

All events are captured and can be verified for compliance/audit.

Usage:
    python3 agent.py                    # Mock mode (no API key needed)
    OPENAI_API_KEY=... python3 agent.py # Real LLM mode
"""

import os
import sys
import json

# Add project root to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "sdk", "python"))

# Mock mode detection
USE_MOCK = not (os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "langchain_session.jsonl")


def run_mock_demo():
    """
    Run a mock LangChain-style session using only the AgentOps SDK.
    Produces a verifiable JSONL with correct chain hashes.
    No LangChain or API key required.
    """
    from agentops_sdk.client import AgentOpsClient
    from agentops_sdk.events import EventType
    import hashlib

    print("=" * 60)
    print("AgentOps Replay - LangChain Demo (Mock Mode)")
    print("=" * 60)
    print()
    print("[!] No API key detected. Running in mock mode.")
    print()

    client = AgentOpsClient(local_authority=True, buffer_size=1000)
    session_id = client.start_session(agent_id="customer-support-demo-v1")
    print(f"[+] Session started: {session_id}")

    # Simulate: LLM_CALL (agent receives query)
    prompt_text = "Can you look up order ORD-001 and tell me its status?"
    prompt_hash = hashlib.sha256(prompt_text.encode()).hexdigest()
    client.record(EventType.LLM_CALL, {
        "model_id": "gpt-4o-mini",
        "provider": "openai",
        "prompt_hash": prompt_hash,
        "prompt_count": 1,
    })
    print("    - LLM_CALL recorded (prompt hashed, not stored)")

    # Simulate: TOOL_CALL (agent decides to call lookup_order)
    tool_args = {"order_id": "ORD-001"}
    args_hash = hashlib.sha256(json.dumps(tool_args, sort_keys=True).encode()).hexdigest()
    client.record(EventType.TOOL_CALL, {
        "tool_name": "lookup_order",
        "args_hash": args_hash,
    })
    print("    - TOOL_CALL recorded (args hashed)")

    # Simulate: TOOL_RESULT (tool returns order info)
    tool_result = {
        "order_id": "ORD-001",
        "status": "shipped",
        "items": ["Widget Pro", "Gadget Plus"],
        "total": 149.99,
        "refund_eligible": True,
    }
    result_hash = hashlib.sha256(json.dumps(tool_result, sort_keys=True).encode()).hexdigest()
    client.record(EventType.TOOL_RESULT, {
        "tool_name": "lookup_order",
        "result_hash": result_hash,
        "duration_ms": 12,
    })
    print("    - TOOL_RESULT recorded (result hashed, no PII)")

    # Simulate: LLM_RESPONSE (agent formulates response)
    response_text = "Order ORD-001 is currently shipped. It contains Widget Pro and Gadget Plus."
    content_hash = hashlib.sha256(response_text.encode()).hexdigest()
    client.record(EventType.LLM_RESPONSE, {
        "content_hash": content_hash,
        "finish_reason": "stop",
        "completion_token_count": 24,
    })
    print("    - LLM_RESPONSE recorded (content hashed)")

    # End session
    client.end_session(status="success", duration_ms=500)
    print("    - SESSION_END recorded")

    # Export
    client.flush_to_jsonl(OUTPUT_FILE)
    print()
    print(f"[+] Session exported to: {OUTPUT_FILE}")
    return True


def run_real_demo():
    """
    Run with real LangChain and OpenAI. Requires OPENAI_API_KEY.
    """
    try:
        from langchain.agents import AgentExecutor, create_react_agent
        from langchain_core.prompts import PromptTemplate
        from langchain_core.tools import tool
        from langchain_openai import ChatOpenAI
    except ImportError:
        print("ERROR: LangChain not installed.")
        print("Install with: pip install langchain langchain-openai langchain-core")
        return False

    from agentops_replay.integrations.langchain import AgentOpsCallbackHandler

    print("=" * 60)
    print("AgentOps Replay - LangChain Demo (Real LLM Mode)")
    print("=" * 60)
    print()

    # Initialize handler
    handler = AgentOpsCallbackHandler(
        agent_id="customer-support-demo-v1",
        local_authority=True,
        buffer_size=10000,
        redact_pii=False,
        tags=["demo", "langchain"],
    )
    handler.start_session()
    print(f"[+] Session started: {handler.client.session_id}")

    # Define tools
    @tool
    def lookup_order(order_id: str) -> str:
        """Retrieve order information by order ID."""
        orders = {
            "ORD-001": {
                "order_id": "ORD-001",
                "status": "shipped",
                "items": ["Widget Pro", "Gadget Plus"],
                "total": 149.99,
                "refund_eligible": True,
            },
        }
        order = orders.get(order_id)
        if not order:
            return json.dumps({"error": f"Order {order_id} not found"})
        return json.dumps(order)

    # Create LLM + agent
    api_key = os.environ.get("OPENAI_API_KEY")
    callbacks = [handler]
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=api_key, callbacks=callbacks)

    template = """You are a helpful customer support agent.

You have access to the following tools:
{tools}

Use the following format:
Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:{agent_scratchpad}"""

    prompt = PromptTemplate.from_template(template)
    tools = [lookup_order]
    agent = create_react_agent(llm, tools, prompt)
    executor = AgentExecutor(
        agent=agent, tools=tools, verbose=True,
        handle_parsing_errors=True, callbacks=callbacks,
    )

    # Run query
    query = "Can you look up order ORD-001 and tell me its status?"
    print(f"\n[+] Query: {query}")
    print("-" * 40)

    try:
        result = executor.invoke({"input": query}, config={"callbacks": callbacks})
        print(f"Response: {result.get('output', 'No output')}")
    except Exception as e:
        print(f"ERROR: {e}")

    # End and export
    handler.end_session(status="success")
    handler.export_to_jsonl(OUTPUT_FILE)
    print(f"\n[+] Session exported to: {OUTPUT_FILE}")
    return True


if __name__ == "__main__":
    if USE_MOCK:
        success = run_mock_demo()
    else:
        success = run_real_demo()

    if success:
        print()
        print("To verify:")
        print(f"  python3 ../../verifier/agentops_verify.py {OUTPUT_FILE}")

    sys.exit(0 if success else 1)
