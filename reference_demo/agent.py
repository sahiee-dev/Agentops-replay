import sys
import os
import json
import uuid
import random
import datetime
from unittest.mock import patch, MagicMock

# Add repo root to path to import agentops_sdk
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agentops_sdk.client import AgentOpsClient
from agentops_sdk.events import EventType
import agentops_sdk.envelope  # Import to patch datetime here

# --- DETERMINISM ENFORCEMENT ---
random.seed(42)

class DeterministicUUID:
    def __init__(self):
        """
        Initialize a DeterministicUUID instance.
        
        Create and initialize an internal counter used to produce deterministic UUIDs starting at 0.
        """
        self.count = 0
    
    def __call__(self):
        """
        Produce a deterministic UUID by advancing the instance's internal counter.
        
        Returns:
            uuid.UUID: A version 4 UUID whose 128-bit integer value is taken from the instance's incrementing counter (deterministic sequence).
        """
        self.count += 1
        return uuid.UUID(int=self.count, version=4)

# Fixed start time: 2023-10-01T12:00:00Z
START_TIME = datetime.datetime(2023, 10, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
current_time = START_TIME
monotonic_time = 1000.0

def deterministic_now(tz=None):
    """
    Advance and return the deterministic current time by 100 milliseconds.
    
    Parameters:
        tz (datetime.tzinfo | None): Accepted for compatibility but ignored; the returned datetime preserves its existing tzinfo.
    
    Returns:
        datetime.datetime: The updated global current_time after advancing by 100 milliseconds.
    """
    global current_time, monotonic_time
    # Advance time by 100ms for every call
    step = datetime.timedelta(milliseconds=100)
    current_time += step
    monotonic_time += 0.1
    # print(f"DEBUG: Time advanced to {current_time}", file=sys.stderr)
    return current_time

def deterministic_utcnow():
    """
    Return a deterministic naive UTC datetime that advances on each call.
    
    Returns:
        datetime.datetime: Naive UTC datetime (tzinfo is None) whose value progresses deterministically (advances by 100 milliseconds per invocation).
    """
    return deterministic_now(datetime.timezone.utc).replace(tzinfo=None)

def deterministic_monotonic():
    """
    Get the current deterministic monotonic time used for reproducible tests.
    
    Returns:
        monotonic (float): Current deterministic monotonic value.
    """
    global monotonic_time
    return monotonic_time

# --- THE AGENT ---

def run_golden_path():
    # Patching where it is used in the SDK
    """
    Run a deterministic, end-to-end demonstration of recording an AgentOpsClient workflow and print the recorded events as a JSON array.
    
    Patches UUID generation, envelope datetime, and monotonic time to produce repeatable output, performs a scripted sequence of events (session start, decisions, tool calls/results, and session end), flushes the client's event buffer, and writes the resulting events to stdout as a pretty-printed JSON array.
    """
    with patch('uuid.uuid4', side_effect=DeterministicUUID()), \
         patch('agentops_sdk.envelope.datetime.datetime') as mock_env_datetime, \
         patch('time.monotonic', side_effect=deterministic_monotonic):
        
        # Configure the mock for envelope.py
        mock_env_datetime.utcnow.side_effect = deterministic_utcnow
        mock_env_datetime.now.side_effect = deterministic_now
        
        # Initialize Client
        client = AgentOpsClient(local_authority=False)
        
        # 1. Start Session
        # Tags: "refund_bot", "incident_repro"
        client.record(EventType.SESSION_START, {
            "agent_id": "support-agent-001",
            "environment": "dev",
            "framework": "python-sdk-raw",
            "framework_version": "0.0.1",
            "sdk_version": "0.1.0",
            "tags": ["refund_bot", "incident_repro"]
        })
        
        # 2. Decision: LOOKUP_TRANSACTION
        client.record(EventType.AGENT_DECISION, {
            "input_facts": ["user_request"],
            "policy_version": "refund_v1",
            "outcome": "LOOKUP_TRANSACTION"
        })
        
        # 3. Tool Call: Query Transaction DB
        # REDACTION: Email is redacted before recording
        client.record(EventType.TOOL_CALL, {
            "tool_name": "transaction_db",
            "function": "query",
            "arguments": {
                "user_email": "[REDACTED]", 
                "query_type": "last_order"
            }
        })
        
        # 4. Tool Result
        # Runtime result contains PII, but we record the REDACTED version
        # Simulated raw result (internal state):
        # raw_result = {"user_email": "alice@example.com", ...}
        
        client.record(EventType.TOOL_RESULT, {
            "tool_name": "transaction_db",
            "result": {
                "transaction_id": "tx_abc123",
                "amount": 29.99,
                "user_email": "[REDACTED]",
                "status": "completed",
                "items": ["widget_pro"]
            }
        })
        
        # 5. Decision: APPROVE_REFUND
        client.record(EventType.AGENT_DECISION, {
            "input_facts": ["transaction_amount", "user_status"],
            "policy_version": "refund_v1",
            "outcome": "APPROVE_REFUND"
        })
        
        # 6. Action: Refund Payment
        client.record(EventType.TOOL_CALL, {
            "tool_name": "refund_payment",
            "function": "process_refund",
            "arguments": {
                "transaction_id": "tx_abc123",
                "reason": "customer_request"
            }
        })
        
        client.record(EventType.TOOL_RESULT, {
            "tool_name": "refund_payment",
            "result": {
                "success": True,
                "refund_id": "ref_xyz789"
            }
        })
        
        # 7. End Session
        client.end_session(status="success", duration_ms=1500)
        
        # --- OUTPUT ---
        # Flush to stdout as JSON lines
        events = client.buffer.flush()
        
        # Convert to dicts
        output_events = [e.to_dict() for e in events]
        
        # Print valid JSON array
        print(json.dumps(output_events, indent=2))

if __name__ == "__main__":
    run_golden_path()