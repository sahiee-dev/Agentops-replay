import sys
import os
import json
import uuid
import random
import datetime
from unittest.mock import patch, MagicMock

# Add repo root to path to import agentops_sdk
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- COLD START: INTEGRATE IN <10 MINUTES ---
# You do NOT need to read the full specs to start using AgentOps.
# 4 Lines of Code:
# 1. client = AgentOpsClient()
# 2. client.start_session(agent_id="...", tags=[...])
# 3. client.record(EventType.AGENT_DECISION | TOOL_CALL | ..., payload={...})
# 4. client.end_session(status="success")
#
# GUARANTEES:
# - All events are cryptographically chained (tamper-proof).
# - Sequence gaps are detected immediately.
# - Redaction is enforced (fail strict if [REDACTED] hash missing).
# - Zero-config local buffering.
# --------------------------------------------

from agentops_sdk.client import AgentOpsClient
from agentops_sdk.events import EventType
import agentops_sdk.envelope  # Import to patch datetime here

# --- DETERMINISM ENFORCEMENT ---
random.seed(42)

class DeterministicUUID:
    def __init__(self):
        self.count = 0
    
    def __call__(self):
        self.count += 1
        return uuid.UUID(int=self.count, version=4)

# Fixed start time: 2023-10-01T12:00:00Z
START_TIME = datetime.datetime(2023, 10, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
current_time = START_TIME
monotonic_time = 1000.0

def deterministic_now(tz=None):
    global current_time, monotonic_time
    # Advance time by 100ms for every call
    step = datetime.timedelta(milliseconds=100)
    current_time += step
    monotonic_time += 0.1
    # print(f"DEBUG: Time advanced to {current_time}", file=sys.stderr)
    return current_time

def deterministic_utcnow():
    return deterministic_now(datetime.timezone.utc).replace(tzinfo=None)

def deterministic_monotonic():
    global monotonic_time
    return monotonic_time

# --- THE AGENT ---

def run_golden_path():
    # Patching where it is used in the SDK
    with patch('uuid.uuid4', side_effect=DeterministicUUID()), \
         patch('agentops_sdk.envelope.datetime.datetime') as mock_env_datetime, \
         patch('time.monotonic', side_effect=deterministic_monotonic):
        
        # Configure the mock for envelope.py
        mock_env_datetime.utcnow.side_effect = deterministic_utcnow
        mock_env_datetime.now.side_effect = deterministic_now
        
        # Initialize Client
        client = AgentOpsClient(local_authority=False)
        client.start_session(agent_id="support-agent-001", tags=["refund_bot", "incident_repro"])
        
        # 1. Start Session (handled by start_session)
        
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
