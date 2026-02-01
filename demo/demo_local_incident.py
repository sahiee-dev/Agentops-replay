import os
import sys
import time

# Add SDK path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agentops_sdk.client import AgentOpsClient
from agentops_sdk.events import EventType

def main():
    print("="*60)
    print("AgentOps LOCAL INCIDENT SIMULATION")
    print("Scenario: PII Leak in Tool Output")
    print("="*60)
    
    # 1. Initialize Local Client (Local Authority Mode)
    client = AgentOpsClient(local_authority=True)
    
    # 2. Start Session
    client.start_session(agent_id="support-bot-v1", tags=["incident-sim", "dev"])
    session_id = client.session_id
    print(f"Session Started: {session_id}")
    
    # 3. User Interaction
    query = "Please find the email address for user ID 12345."
    print(f"User Query: {query}")
    
    # 4. Tool Call (User Lookup)
    print("Executing Tool: user_lookup...")
    client.record(EventType.TOOL_CALL, {
        "tool_name": "user_lookup",
        "args": {"user_id": "12345"},
        "start_time": time.time()
    })
    
    # 5. Tool Result (Contains PII - Incident!)
    print("Tool Returned PII (Incident!)")
    pii_data = {
        "user_id": "12345",
        "name": "John Doe",
        "email": "john.doe@example.com", # PII
        "ssn": "000-00-0000" # Severe PII
    }
    client.record(EventType.TOOL_RESULT, {
        "tool_name": "user_lookup",
        "result": pii_data,
        "success": True,
        "duration_ms": 150
    })
    
    # 6. Agent Action on PII
    print("Agent processing PII...")
    client.record(EventType.MODEL_REQUEST, {
        "model": "gpt-4",
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150
    })
    
    # 7. Error (Simulated crash or detection)
    print("Simulating System Error...")
    client.record(EventType.ERROR, {
        "error_type": "PIIDetectionWarning",
        "message": "Potential PII detected in output stream.",
        "stack_trace": "Traceback (most recent call last):..."
    })
    
    # 8. End Session
    client.end_session(status="FAILED", duration_ms=2000)
    print("Session Ended.")
    
    # 9. Flush to Disk
    filename = f"incident_log_{session_id}.jsonl"
    client.flush_to_jsonl(filename)
    print(f"Log flushed to {filename}")
    
    # 10. Verify
    print("\nVerifying Log...")
    verifier_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../verifier/agentops_verify.py"))
    
    import subprocess
    result = subprocess.run(
        [sys.executable, verifier_path, filename, "--format", "text"],
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    if result.returncode != 0:
        print("Verification FAILED!")
        print(result.stderr)
        sys.exit(1)
    else:
        print("Verification PASSED!")
        
    # Clean up
    # os.remove(filename) # Keep it for inspection

if __name__ == "__main__":
    main()
