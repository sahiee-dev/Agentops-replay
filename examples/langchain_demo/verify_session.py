#!/usr/bin/env python3
"""
Verify Session - Verify the captured session using AgentOps verifier

This script demonstrates the verification workflow:
1. Load the session JSONL
2. Run cryptographic verification
3. Display evidence classification
"""

import sys
import os
import json
import subprocess

# Add project paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# Default session file
DEFAULT_SESSION_FILE = os.path.join(os.path.dirname(__file__), "session_output.jsonl")


def verify_session(session_file: str = DEFAULT_SESSION_FILE, reject_local: bool = False):
    """
    Verify a captured session JSONL file and report cryptographic verification results.
    
    Parameters:
        session_file (str): Path to the session JSONL file to verify (defaults to DEFAULT_SESSION_FILE).
        reject_local (bool): If True, instruct the verifier to reject sessions signed by a local authority.
    
    Returns:
        bool: `True` if the external verifier reports success (verification passed), `False` otherwise.
    """
    print("=" * 60)
    print("AgentOps Replay - Session Verification")
    print("=" * 60)
    print()
    
    # Check if file exists
    if not os.path.exists(session_file):
        print(f"ERROR: Session file not found: {session_file}")
        print()
        print("Run the demo first:")
        print("  python run_demo.py --mock")
        return False
    
    # Load and preview session
    print(f"[+] Loading session from: {session_file}")
    try:
        events = []
        with open(session_file, 'r') as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        print(f"    Events loaded: {len(events)}")
    except Exception as e:
        print(f"ERROR: Failed to load session: {e}")
        return False
    
    print()
    
    # Display event summary
    print("[+] Event Summary:")
    event_types = {}
    for e in events:
        et = e.get("event_type", "UNKNOWN")
        event_types[et] = event_types.get(et, 0) + 1
    
    for et, count in sorted(event_types.items()):
        print(f"    {et}: {count}")
    
    print()
    
    # Run verifier
    print("[+] Running cryptographic verification...")
    print()
    
    verifier_path = os.path.join(PROJECT_ROOT, "verifier", "agentops_verify.py")
    
    cmd = [sys.executable, verifier_path, session_file, "--format", "text"]
    if reject_local:
        cmd.append("--reject-local-authority")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        print()
        print("=" * 60)
        
        if result.returncode == 0:
            print("✓ VERIFICATION PASSED")
            print()
            print("This session is cryptographically intact and can be used as evidence.")
        else:
            print("✗ VERIFICATION FAILED")
            print()
            print("This session has integrity issues and should not be trusted.")
        
        print("=" * 60)
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"ERROR: Failed to run verifier: {e}")
        return False


def get_session_details(session_file: str = DEFAULT_SESSION_FILE):
    """Display detailed session information."""
    if not os.path.exists(session_file):
        print(f"Session file not found: {session_file}")
        return
    
    print()
    print("=" * 60)
    print("SESSION DETAILS")
    print("=" * 60)
    print()
    
    with open(session_file, 'r') as f:
        events = [json.loads(line) for line in f if line.strip()]
    
    if not events:
        print("No events found")
        return
    
    # Session info
    session_id = events[0].get("session_id", "unknown")
    first_ts = events[0].get("timestamp_wall", "unknown")
    last_ts = events[-1].get("timestamp_wall", "unknown")
    
    print(f"Session ID: {session_id}")
    print(f"Event Count: {len(events)}")
    print(f"First Event: {first_ts}")
    print(f"Last Event: {last_ts}")
    print(f"Authority: {events[-1].get('chain_authority', 'unknown')}")
    print()
    
    # Event timeline
    print("EVENT TIMELINE:")
    print("-" * 40)
    for i, e in enumerate(events):
        et = e.get("event_type", "UNKNOWN")
        seq = e.get("sequence_number", "?")
        
        # Extract key info based on event type
        detail = ""
        if et == "TOOL_CALL":
            detail = f"→ {e.get('payload', {}).get('tool_name', '?')}"
        elif et == "MODEL_REQUEST":
            detail = f"→ {e.get('payload', {}).get('model', '?')}"
        elif et == "ERROR":
            detail = f"→ {e.get('payload', {}).get('error_type', '?')}"
        
        print(f"[{seq:2}] {et} {detail}")
    
    print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Verify AgentOps Replay session")
    parser.add_argument("--file", default=DEFAULT_SESSION_FILE,
                       help="Session JSONL file to verify")
    parser.add_argument("--reject-local", action="store_true",
                       help="Reject local authority sessions")
    parser.add_argument("--details", action="store_true",
                       help="Show detailed session information")
    
    args = parser.parse_args()
    
    if args.details:
        get_session_details(args.file)
    
    success = verify_session(args.file, reject_local=args.reject_local)
    sys.exit(0 if success else 1)