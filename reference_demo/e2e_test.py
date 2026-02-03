#!/usr/bin/env python3
"""
End-to-end test: Ingest events and verify the result.

This script demonstrates the full production flow:
1. Generate test events (simulating SDK output)
2. Ingest them through the production ingestion service
3. Export sealed session
4. Verify with the production verifier
"""
import json
import os
import sys

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentops_ingest.validator import validate_claim
from agentops_ingest.sealer import seal_event, ChainState, CHAIN_AUTHORITY
from agentops_verify.verifier import verify_session
from agentops_verify.errors import VerificationStatus


def generate_test_events() -> list:
    """Generate test events simulating SDK output (before ingestion)."""
    session_id = "e2e-test-session-001"
    
    events = [
        {
            "event_id": "evt-001",
            "session_id": session_id,
            "sequence_number": 0,
            "timestamp_wall": "2023-10-01T12:00:00Z",
            "event_type": "SESSION_START",
            "payload": {
                "agent_id": "test-agent",
                "environment": "e2e-test"
            }
        },
        {
            "event_id": "evt-002",
            "session_id": session_id,
            "sequence_number": 1,
            "timestamp_wall": "2023-10-01T12:00:01Z",
            "event_type": "AGENT_DECISION",
            "payload": {
                "input_facts": ["user_query"],
                "outcome": "PROCESS_REQUEST"
            }
        },
        {
            "event_id": "evt-003",
            "session_id": session_id,
            "sequence_number": 2,
            "timestamp_wall": "2023-10-01T12:00:02Z",
            "event_type": "TOOL_CALL",
            "payload": {
                "tool_name": "lookup_user",
                "arguments": {"user_id": "[REDACTED]"}
            }
        },
        {
            "event_id": "evt-004",
            "session_id": session_id,
            "sequence_number": 3,
            "timestamp_wall": "2023-10-01T12:00:03Z",
            "event_type": "SESSION_END",
            "payload": {
                "status": "success",
                "duration_ms": 3000
            }
        },
    ]
    
    return events


def ingest_events(raw_events: list) -> list:
    """Ingest events through production pipeline (in-memory for test)."""
    sealed_events = []
    chain_state = None
    
    for raw in raw_events:
        # 1. Validate
        claim = validate_claim(raw)
        
        # 2. Seal
        sealed = seal_event(claim, chain_state, strict_mode=True)
        
        # 3. Update chain state
        chain_state = ChainState(
            session_id=claim.session_id,
            last_sequence=sealed.sequence_number,
            last_event_hash=sealed.event_hash,
            is_closed=(raw["event_type"] == "SESSION_END"),
        )
        
        # 4. Convert to dict for export
        sealed_dict = {
            "event_id": sealed.event_id,
            "session_id": sealed.session_id,
            "sequence_number": sealed.sequence_number,
            "timestamp_wall": sealed.timestamp_wall,
            "event_type": sealed.event_type,
            "payload": json.loads(sealed.payload_jcs.decode('utf-8')),
            "payload_hash": sealed.payload_hash,
            "prev_event_hash": sealed.prev_event_hash,
            "event_hash": sealed.event_hash,
            "chain_authority": sealed.chain_authority,
        }
        sealed_events.append(sealed_dict)
    
    return sealed_events


def main():
    print("=" * 60)
    print("END-TO-END INGESTION + VERIFICATION TEST")
    print("=" * 60)
    
    # 1. Generate test events
    print("\n[1] Generating test events...")
    raw_events = generate_test_events()
    print(f"    Generated {len(raw_events)} events")
    
    # 2. Ingest through production pipeline
    print("\n[2] Ingesting through production pipeline...")
    sealed_events = ingest_events(raw_events)
    print(f"    Sealed {len(sealed_events)} events")
    print(f"    Chain Authority: {CHAIN_AUTHORITY}")
    print(f"    Final Hash: {sealed_events[-1]['event_hash']}")
    
    # 3. Export to JSON
    output_path = "reference_demo/expected_output/session_golden_verified.json"
    print(f"\n[3] Exporting to {output_path}...")
    with open(output_path, 'w') as f:
        json.dump(sealed_events, f, indent=2)
    print(f"    Written {len(sealed_events)} events")
    
    # 4. Verify with production verifier
    print("\n[4] Verifying with production verifier...")
    report = verify_session(sealed_events)
    
    print(f"\n{'=' * 60}")
    print(f"VERIFICATION RESULT: {report.status.value}")
    print(f"{'=' * 60}")
    print(f"Session ID:       {report.session_id}")
    print(f"Event Count:      {report.event_count}")
    print(f"Chain Authority:  {report.chain_authority}")
    print(f"Verification Mode: {report.verification_mode}")
    print(f"First Hash:       {report.first_event_hash[:16]}...")
    print(f"Final Hash:       {report.final_event_hash[:16]}...")
    
    if report.findings:
        print(f"\nFindings ({len(report.findings)}):")
        for f in report.findings:
            print(f"  [{f.severity.value}] {f.finding_type.value}: {f.message}")
    else:
        print("\nNo findings - chain integrity verified!")
    
    print(f"\nExit Code: {report.exit_code}")
    
    # Return exit code
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
