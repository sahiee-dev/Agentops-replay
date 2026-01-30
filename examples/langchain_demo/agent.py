"""
Customer Support Agent with Tools

This agent demonstrates AgentOps Replay capturing:
- Tool calls (lookup_order, issue_refund, send_email)
- LLM interactions
- Decision traces

All events are captured and can be verified for compliance/audit.
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "sdk", "python")
    ),
)

import json
from datetime import datetime
from decimal import Decimal

# Try LangChain imports
try:
    from langchain.agents import AgentExecutor, create_react_agent
    from langchain_core.prompts import PromptTemplate
    from langchain_core.tools import tool
    from langchain_openai import ChatOpenAI

    LANGCHAIN_INSTALLED = True
except ImportError:
    LANGCHAIN_INSTALLED = False
    print(
        "Warning: LangChain not installed. Install with: pip install langchain langchain-openai"
    )

# Simulated database
ORDERS_DB = {
    "ORD-001": {
        "customer_id": "C-12345",
        "customer_email": "john.doe@example.com",
        "status": "shipped",
        "items": ["Widget Pro", "Gadget Plus"],
        "total": 149.99,
        "refund_eligible": True,
        "shipped_date": "2026-01-20",
    },
    "ORD-002": {
        "customer_id": "C-67890",
        "customer_email": "jane.smith@example.com",
        "status": "delivered",
        "items": ["Super Deluxe Package"],
        "total": 299.99,
        "refund_eligible": False,
        "delivered_date": "2026-01-22",
    },
    "ORD-003": {
        "customer_id": "C-11111",
        "customer_email": "bob.johnson@example.com",
        "status": "processing",
        "items": ["Basic Kit"],
        "total": 49.99,
        "refund_eligible": True,
    },
}

REFUNDS_ISSUED = []
EMAILS_SENT = []


# Define tools
if LANGCHAIN_INSTALLED:

    @tool
    def lookup_order(order_id: str) -> str:
        """
        Retrieve order information by order ID.

        Returns:
                A JSON-formatted string. On success the JSON contains the fields:
                - `order_id`: the requested order identifier
                - `status`: current order status
                - `items`: list of items on the order
                - `total`: order total amount
                - `refund_eligible`: whether the order is eligible for refunds
                - `customer_email`: customer's email address (PII; will be captured)
                On failure the JSON contains an `error` field with an explanatory message.
        """
        order = ORDERS_DB.get(order_id)
        if not order:
            return json.dumps({"error": f"Order {order_id} not found"})

        # Return order info (note: includes PII - email)
        return json.dumps(
            {
                "order_id": order_id,
                "status": order["status"],
                "items": order["items"],
                "total": order["total"],
                "refund_eligible": order["refund_eligible"],
                "customer_email": order["customer_email"],  # PII - will be captured!
            }
        )

    @tool
    def issue_refund(order_id: str, amount: float, reason: str) -> str:
        """
        Create and record a refund for an eligible order.

        Parameters:
            order_id (str): Identifier of the order to refund.
            amount (float): Refund amount in USD.
            reason (str): Reason for issuing the refund.

        Returns:
            str: A JSON-encoded string describing the outcome.
                 - Success: {"success": True, "refund_id": <id>, "amount_refunded": <amount>, "message": <text>}
                 - Order not found: {"error": "Order <id> not found"}
                 - Not eligible: {"error": "Order <id> is not eligible for refund", "status": <order_status>}
                 - Amount exceeds total: {"error": "Refund amount $<amount> exceeds order total $<total>"}
        """
        order = ORDERS_DB.get(order_id)
        if not order:
            return json.dumps({"error": f"Order {order_id} not found"})

        if not order.get("refund_eligible"):
            return json.dumps(
                {
                    "error": f"Order {order_id} is not eligible for refund",
                    "status": order["status"],
                }
            )

        # Use Decimal for safe monetary comparison
        refund_amount = Decimal(str(amount))
        order_total = Decimal(str(order["total"]))
        
        if refund_amount > order_total:
            return json.dumps(
                {
                    "error": f"Refund amount ${refund_amount} exceeds order total ${order_total}"
                }
            )

        refund_record = {
            "refund_id": f"REF-{len(REFUNDS_ISSUED) + 1:04d}",
            "order_id": order_id,
            "amount": amount,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        }
        REFUNDS_ISSUED.append(refund_record)

        return json.dumps(
            {
                "success": True,
                "refund_id": refund_record["refund_id"],
                "amount_refunded": amount,
                "message": f"Refund of ${amount} issued for order {order_id}",
            }
        )

    @tool
    def send_email(to_email: str, subject: str, body: str) -> str:
        """
        Send an email record to the specified recipient and append it to the in-memory email store.

        Parameters:
            to_email (str): Recipient email address (contains PII).
            subject (str): Email subject line.
            body (str): Email body content.

        Returns:
            str: JSON string with keys `success` (`True` on success), `email_id` (the created email identifier), and `message` (human-readable confirmation).
        """
        email_record = {
            "email_id": f"EMAIL-{len(EMAILS_SENT) + 1:04d}",
            "to": to_email,  # PII!
            "subject": subject,
            "body": body,
            "timestamp": datetime.now().isoformat(),
        }
        EMAILS_SENT.append(email_record)

        return json.dumps(
            {
                "success": True,
                "email_id": email_record["email_id"],
                "message": f"Email sent to {to_email}",
            }
        )


def get_tools():
    """
    List the tool callables exposed for agent use.

    Returns:
        A list of tool callables (lookup_order, issue_refund, send_email) when LangChain is installed, or an empty list if LangChain is not available.
    """
    if not LANGCHAIN_INSTALLED:
        return []
    return [lookup_order, issue_refund, send_email]


def create_agent(api_key: str | None = None, callbacks=None):
    """
    Create and return a configured customer support agent executor.

    Parameters:
        api_key (str | None): OpenAI API key to use; if omitted, the `OPENAI_API_KEY` environment variable is used.
        callbacks (optional): Iterable of LangChain callback handlers to attach to the LLM and agent.

    Returns:
        AgentExecutor: A configured agent executor that exposes the customer support agent with the registered tools and prompt.

    Raises:
        ImportError: If required LangChain components are not available.
    """
    if not LANGCHAIN_INSTALLED:
        raise ImportError("LangChain not installed")

    # Create LLM
    llm = ChatOpenAI(
        model="gpt-4o-mini", temperature=0, api_key=api_key, callbacks=callbacks
    )

    # Create tools
    tools = get_tools()

    # Create prompt
    template = """You are a helpful customer support agent. You help customers with their orders.

You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:{agent_scratchpad}"""

    prompt = PromptTemplate.from_template(template)

    # Create agent
    agent = create_react_agent(llm, tools, prompt)

    # Create executor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        callbacks=callbacks,
    )

    return agent_executor


def get_refunds():
    """
    Retrieve a copy of all refund records issued by the agent.

    Each refund record is a dict containing keys such as `refund_id`, `order_id`, `amount`, `reason`, and `timestamp`.

    Returns:
        list: A shallow copy of the list of refund record dictionaries; modifying the returned list does not affect the internal store.
    """
    return REFUNDS_ISSUED.copy()


def get_emails():
    """
    Retrieve a copy of all email records sent by the agent.

    Returns:
        list: A list of email record dictionaries, each containing keys such as `email_id`, `to`, `subject`, `body`, and `timestamp`.
    """
    return EMAILS_SENT.copy()
