#!/usr/bin/env python3
"""
agentops_verify.py - Standalone Verifier for AgentOps Replay logs.
Strictly implements checks defined in EVENT_LOG_SPEC.md v0.5.

Usage:
  python3 agentops_verify.py <session.jsonl> --format json
"""

import argparse
import hashlib
import json
import sys
from typing import Dict, Any, List, Optional
import jcs  # Local module

# --- Constants ---
SPEC_VERSION = "v0.5"
SIGNED_FIELDS = [
    "event_id", 
    "session_id", 
    "sequence_number", 
    "timestamp_wall", 
    "event_type", 
    "payload_hash", 
    "prev_event_hash"
]

class VerificationError(Exception):
    def __init__(self, code: str, message: str, context: Dict[str, Any] = None):
        self.code = code
        self.message = message
        self.context = context or {}

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def verify_session(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Core verification pipeline.
    Returns structured report.
    """
    report = {
        "session_id": None,
        "status": "PASS",
        "violations": [],
        "sealed": False,
        "authority": "unknown",
        "replay_fingerprint": None,
        "event_count": len(events)
    }

    if not events:
        report["status"] = "FAIL"
        report["violations"].append({"type": "EMPTY_LOG", "message": "Log file is empty"})
        return report

    # 0. SINGLE AUTHORITY CHECK (Spec v0.5)
    authorities = set()
    for event in events:
        if "chain_authority" in event and event["chain_authority"]:
            authorities.add(event["chain_authority"])
    
    if len(authorities) > 1:
        report["status"] = "FAIL"
        report["violations"].append({
            "type": "MIXED_AUTHORITY",
            "message": f"Session has mixed authorities: {authorities}. Spec v0.5 requires single authority per session."
        })
        return report

    # 1. Structural & Sequence Checks
    prev_hash = None
    expected_seq = 0
    calculated_chain_hash = None
    
    session_id = events[0].get("session_id")
    report["session_id"] = session_id

    for i, event in enumerate(events):
        try:
            # A. Structure
            _validate_envelope(event, i)
            
            # Check Session Consistency
            if event.get("session_id") != session_id:
                raise VerificationError("SESSION_MISMATCH", f"Event session_id {event.get('session_id')} does not match session {session_id}")

            # B. Canonicalization & Payload Hash
            payload = event.get("payload")
            # Note: In a real JSONL, payload is likely a dictionary loaded from JSON.
            # We canonicalize it back to bytes to verify hash.
            canonical_payload = jcs.canonicalize(payload)
            expected_payload_hash = sha256(canonical_payload)
            
            if event["payload_hash"] != expected_payload_hash:
                raise VerificationError("PAYLOAD_HASH_MISMATCH", "Payload hash mismatch", {
                    "expected": expected_payload_hash,
                    "actual": event["payload_hash"]
                })

            # C. Sequence Monotonicity
            if event["sequence_number"] != expected_seq:
                raise VerificationError("SEQUENCE_GAP", f"Expected sequence {expected_seq}, got {event['sequence_number']}")
            
            # D. Chain Integrity
            # Check prev_event_hash
            if i == 0:
                if event["prev_event_hash"] is not None:
                     raise VerificationError("INVALID_GENESIS", "First event must have null prev_event_hash")
            else:
                if event["prev_event_hash"] != prev_hash:
                    raise VerificationError("CHAIN_BROKEN", "prev_event_hash does not match previous event_hash", {
                        "expected": prev_hash,
                        "actual": event["prev_event_hash"]
                    })
            
            # CHECKPOINT: Update authority if provided (last win)
            if "chain_authority" in event:
                report["authority"] = event["chain_authority"]

            # Calculate current event hash
            # Create object with ONLY signed fields
            signed_obj = {k: event[k] for k in SIGNED_FIELDS if k in event}
            # Spec v0.5: All signed fields must be present (prev_event_hash can be null but must exist)
            for f in SIGNED_FIELDS:
                if f not in event:
                    raise VerificationError("MISSING_SIGNED_FIELD", f"Required signed field missing: {f}") 

            canonical_envelope = jcs.canonicalize(signed_obj)
            calculated_hash = sha256(canonical_envelope)
            
            if event["event_hash"] != calculated_hash:
                 raise VerificationError("EVENT_HASH_MISMATCH", "Event hash signature invalid", {
                     "expected": calculated_hash,
                     "actual": event["event_hash"]
                 })

            # Prepare for next iteration
            prev_hash = calculated_hash
            expected_seq += 1
            calculated_chain_hash = calculated_hash

            # E. Check for Seal (Spec v0.5 compliant)
            if event["event_type"] == "CHAIN_SEAL":
                report["sealed"] = True
                # Spec v0.5: CHAIN_SEAL authority must match session authority
                if report["authority"] not in ["server", "sdk"]:
                    raise VerificationError("INVALID_SEAL", f"CHAIN_SEAL authority '{report['authority']}' is not valid (must be 'server' or 'sdk')")


        except VerificationError as e:
            report["status"] = "FAIL"
            report["violations"].append({
                "type": e.code,
                "message": e.message,
                "event_sequence": i,
                "event_id": event.get("event_id"),
                "context": e.context
            })
            # Fail-fast?
            # User request said: "Fail-Fast: Verification pipeline stops at the first failure."
            break
        except Exception as e:
             report["status"] = "FAIL"
             report["violations"].append({
                "type": "INTERNAL_ERROR",
                "message": str(e),
                "event_sequence": i
            })
             break

    if report["status"] == "PASS":
        report["replay_fingerprint"] = calculated_chain_hash
    
    return report

def _validate_envelope(event: Dict[str, Any], index: int):
    required = ["event_id", "session_id", "sequence_number", "event_type", "payload_hash", "event_hash", "payload", "schema_ver"]
    for field in required:
        if field not in event:
            raise VerificationError("MISSING_FIELD", f"Missing required field: {field}")
    
    # Spec v0.5: strict schema_ver matching
    if event["schema_ver"] != SPEC_VERSION:
         raise VerificationError("SCHEMA_VERSION_MISMATCH", f"Expected {SPEC_VERSION}, got {event['schema_ver']}")


def main():
    parser = argparse.ArgumentParser(description="AgentOps Replay Verifier")
    parser.add_argument("file", help="Path to .jsonl log file")
    parser.add_argument("--format", choices=["json", "text"], default="text", help="Output format")
    
    args = parser.parse_args()
    
    events = []
    try:
        with open(args.file, 'r') as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
    except Exception as e:
        print(json.dumps({"status": "FAIL", "violations": [{"type": "LOAD_ERROR", "message": str(e)}]}))
        sys.exit(1)
        
    report = verify_session(events)
    
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(f"Session: {report['session_id']}")
        print(f"Status: {report['status']}")
        print(f"Sealed: {report['sealed']}")
        print(f"Authority: {report['authority']}")
        if report['violations']:
            print("Violations:")
            for v in report['violations']:
                print(f"  - [{v['type']}] Seq {v.get('event_sequence')}: {v['message']}")
        else:
            print(f"Fingerprint: {report['replay_fingerprint']}")

    if report["status"] == "FAIL":
        sys.exit(1)

if __name__ == "__main__":
    main()
