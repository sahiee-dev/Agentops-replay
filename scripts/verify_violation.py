"""
verify_violation.py - End-to-End Verification of Violation API.

Steps:
1. Create a session via /api/v1/ingest/sessions
2. Ingest a batch with PII via /api/v1/ingest/batch
3. Wait for Worker to process.
4. Verify violation exists via /api/v1/violations/{session_id}
"""

import json
import time
import uuid
import urllib.request
import urllib.error
import sys

API_URL = "http://localhost:8000/api/v1"

def post(endpoint, data):
    url = f"{API_URL}{endpoint}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"HTTPError {e.code}: {e.read().decode('utf-8')}")
        raise

def get(endpoint):
    url = f"{API_URL}{endpoint}"
    try:
        with urllib.request.urlopen(url) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"HTTPError {e.code}: {e.read().decode('utf-8')}")
        raise

def main():
    print("Starting E2E Verification...")
    
    # 1. Create Session
    session_id = str(uuid.uuid4())
    print(f"Creating session {session_id}...")
    post("/ingest/sessions", {
        "session_id": session_id,
        "authority": "server",
        "agent_name": "e2e-verifier"
    })
    
    # 2. Ingest Batch with PII
    print("Ingesting PII event...")
    post("/ingest/batch", {
        "session_id": session_id,
        "events": [
            {
                "event_type": "LLM_CALL",
                "sequence_number": 0,
                "timestamp_monotonic": 123456,
                "payload": {
                    "user_query": "My email is test@example.com",  # Should trigger GDPR
                    "action": "test"
                }
            }
        ]
    })
    
    # 3. Wait
    print("Waiting for worker processing (5s)...")
    time.sleep(5)
    
    # 4. Verify Violation
    print("Checking for violations...")
    violations = get(f"/violations/{session_id}")
    
    if not violations:
        print("FAILURE: No violations found!")
        sys.exit(1)
        
    print(f"Found {len(violations)} violations:")
    for v in violations:
        print(f"- {v['severity']}: {v['policy_name']} - {v['description']}")
        
    # Assert
    gdpr_violations = [v for v in violations if v["policy_name"] == "GDPR_PII_DETECTED"]
    if not gdpr_violations:
        print("FAILURE: GDPR violation not found!")
        sys.exit(1)
        
    print("SUCCESS: E2E Verification Passed!")

if __name__ == "__main__":
    main()
