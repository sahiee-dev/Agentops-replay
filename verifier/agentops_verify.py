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
from typing import Any

import jcs  # Local module

# --- Constants ---
SPEC_VERSION = "v0.6"
SIGNED_FIELDS = [
    "event_id",
    "session_id",
    "sequence_number",
    "timestamp_wall",
    "event_type",
    "payload_hash",
    "prev_event_hash",
]


class VerificationError(Exception):
    def __init__(self, code: str, message: str, context: dict[str, Any] | None = None):
        """
        Initialize the VerificationError with a machine-readable code, a human-readable message, and optional contextual data.
        
        Parameters:
            code (str): Short machine-readable error code identifying the verification failure.
            message (str): Human-readable description of the error.
            context (dict[str, Any] | None): Optional additional context (metadata) about the error; defaults to an empty dict.
        """
        self.code = code
        self.message = message
        self.context = context or {}


def sha256(data: bytes) -> str:
    """
    Compute the SHA-256 hexadecimal digest of the given bytes.
    
    Parameters:
        data (bytes): Input data to hash.
    
    Returns:
        str: Hexadecimal SHA-256 digest of `data`.
    """
    return hashlib.sha256(data).hexdigest()


def classify_evidence(authority: str, sealed: bool, complete: bool) -> str:
    """
    Classify session evidence based on the producing authority, whether the chain is sealed, and whether the session is complete.
    
    Parameters:
        authority (str): The source of the session (commonly "server" or "sdk").
        sealed (bool): True if the session chain is cryptographically sealed.
        complete (bool): True if the session contains a proper session end and no unresolved drops.
    
    Returns:
        str: One of:
            - "AUTHORITATIVE_EVIDENCE" when produced by a server and both sealed and complete.
            - "PARTIAL_AUTHORITATIVE_EVIDENCE" when produced by a server but unsealed or incomplete.
            - "NON_AUTHORITATIVE_EVIDENCE" when produced by an SDK authority.
            - "UNKNOWN_EVIDENCE" for any other authority values.
    """
    if authority == "server":
        if sealed and complete:
            return "AUTHORITATIVE_EVIDENCE"
        else:
            # Unsealed or incomplete server sessions are still valuable but not compliance-grade
            return "PARTIAL_AUTHORITATIVE_EVIDENCE"
    elif authority == "sdk":
        return "NON_AUTHORITATIVE_EVIDENCE"
    else:
        return "UNKNOWN_EVIDENCE"


def verify_session(
    events: list[dict[str, Any]], policy: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Verify a sequence of replay events and produce a structured verification report.
    
    Performs structural, sequence, chain-integrity, payload- and event-hash validation, detects sealing and log-drop conditions, and classifies evidence according to spec v0.6. The pipeline stops at the first verification failure (fail-fast). If a policy is provided with "reject_local_authority": True, sessions signed by the local SDK authority will be marked as policy violations and fail.
    
    Parameters:
        events (list[dict[str, Any]]): Ordered list of event envelopes to verify; each envelope must include the required signed fields and payload.
        policy (dict[str, Any] | None): Optional policy controls (supported key: "reject_local_authority").
    
    Returns:
        dict[str, Any]: Verification report with keys including:
            - session_id: session identifier extracted from the events.
            - status: "PASS" or "FAIL".
            - violations: list of violation objects recorded on failure or policy enforcement.
            - sealed: boolean indicating whether a valid CHAIN_SEAL was observed.
            - authority: detected chain authority ("server", "sdk", or "unknown").
            - evidence_class: one of the evidence classification strings (e.g., "AUTHORITATIVE_EVIDENCE").
            - partial_reasons: list of reasons the session is considered partial.
            - replay_fingerprint: calculated chain hash when verification passes, otherwise None.
            - event_count: number of input events.
            - complete: boolean indicating whether the session appears complete (session end present, no drops, passing verification).
            - total_drops: cumulative dropped event count from LOG_DROP events.
            - partial: boolean set when evidence has been degraded (e.g., due to LOG_DROP).
            - warnings: optional list of non-fatal warnings (e.g., invalid drop counts).
    """
    report: dict[str, Any] = {
        "session_id": None,
        "status": "PASS",
        "violations": [],
        "sealed": False,
        "authority": "unknown",
        "evidence_class": "UNKNOWN_EVIDENCE",
        "partial_reasons": [],  # Why session is PARTIAL_AUTHORITATIVE
        "replay_fingerprint": None,
        "event_count": len(events),
        "complete": False,
        "total_drops": 0,
        "partial": False,
    }

    if not events:
        report["status"] = "FAIL"
        report["violations"].append(
            {"type": "EMPTY_LOG", "message": "Log file is empty"}
        )
        return report

    # 0. SINGLE AUTHORITY CHECK (Spec v0.6)
    authorities = set()
    for event in events:
        if event.get("chain_authority"):
            authorities.add(event["chain_authority"])

    if len(authorities) > 1:
        report["status"] = "FAIL"
        report["violations"].append(
            {
                "type": "MIXED_AUTHORITY",
                "message": f"Session has mixed authorities: {authorities}. Spec v0.6 requires single authority per session.",
            }
        )
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
                raise VerificationError(
                    "SESSION_MISMATCH",
                    f"Event session_id {event.get('session_id')} does not match session {session_id}",
                )

            # B. Canonicalization & Payload Hash
            payload = event.get("payload")
            # Note: In a real JSONL, payload is likely a dictionary loaded from JSON.
            # We canonicalize it back to bytes to verify hash.
            canonical_payload = jcs.canonicalize(payload)
            expected_payload_hash = sha256(canonical_payload)

            if event["payload_hash"] != expected_payload_hash:
                raise VerificationError(
                    "PAYLOAD_HASH_MISMATCH",
                    "Payload hash mismatch",
                    {
                        "expected": expected_payload_hash,
                        "actual": event["payload_hash"],
                    },
                )

            # C. Sequence Monotonicity
            if event["sequence_number"] != expected_seq:
                raise VerificationError(
                    "SEQUENCE_GAP",
                    f"Expected sequence {expected_seq}, got {event['sequence_number']}",
                )

            # D. Chain Integrity
            # Check prev_event_hash
            if i == 0:
                if event["prev_event_hash"] is not None:
                    raise VerificationError(
                        "INVALID_GENESIS", "First event must have null prev_event_hash"
                    )
            elif event["prev_event_hash"] != prev_hash:
                raise VerificationError(
                    "CHAIN_BROKEN",
                    "prev_event_hash does not match previous event_hash",
                    {"expected": prev_hash, "actual": event["prev_event_hash"]},
                )

            # CHECKPOINT: Update authority if provided (last win)
            if "chain_authority" in event:
                report["authority"] = event["chain_authority"]

            # Calculate current event hash
            # Create object with ONLY signed fields
            signed_obj = {k: event[k] for k in SIGNED_FIELDS if k in event}
            # Spec v0.5: All signed fields must be present (prev_event_hash can be null but must exist)
            for f in SIGNED_FIELDS:
                if f not in event:
                    raise VerificationError(
                        "MISSING_SIGNED_FIELD", f"Required signed field missing: {f}"
                    )

            canonical_envelope = jcs.canonicalize(signed_obj)
            calculated_hash = sha256(canonical_envelope)

            if event["event_hash"] != calculated_hash:
                raise VerificationError(
                    "EVENT_HASH_MISMATCH",
                    "Event hash signature invalid",
                    {"expected": calculated_hash, "actual": event["event_hash"]},
                )

            # Prepare for next iteration
            prev_hash = calculated_hash
            expected_seq += 1
            calculated_chain_hash = calculated_hash

            # E. Check for Seal and Validate Metadata (Spec v0.6)
            if event["event_type"] == "CHAIN_SEAL":
                # Validate server authority CHAIN_SEAL has required metadata
                if event.get("chain_authority") == "server":
                    payload = event.get("payload", {})
                    required_fields = [
                        "ingestion_service_id",
                        "seal_timestamp",
                        "session_digest",
                    ]
                    if all(field in payload for field in required_fields):
                        report["sealed"] = True
                    else:
                        missing = [f for f in required_fields if f not in payload]
                        raise VerificationError(
                            "INVALID_SEAL",
                            "Server CHAIN_SEAL missing required metadata",
                            {"missing_fields": missing},
                        )
                elif event.get("chain_authority") == "sdk":
                    # SDK CHAIN_SEAL is valid for local authority mode
                    report["sealed"] = True
                else:
                    raise VerificationError(
                        "INVALID_SEAL",
                        f"CHAIN_SEAL authority '{event.get('chain_authority')}' is not valid (must be 'server' or 'sdk')",
                    )

            # F. Track LOG_DROP events
            # F. Track LOG_DROP events
            if event["event_type"] == "LOG_DROP":
                # Always degrade evidence class if LOG_DROP is present
                report["partial_reasons"].append("LOG_DROP_PRESENT")
                report["partial"] = True

                drop_payload = event.get("payload", {})
                dropped_count = drop_payload.get("dropped_count")

                if isinstance(dropped_count, int) and dropped_count > 0:
                    report["total_drops"] += dropped_count
                else:
                    # Invalid/missing count still degrades evidence, but we log warning
                    report["warnings"] = report.get("warnings", [])
                    report["warnings"].append(
                        {
                            "type": "INVALID_DROP_COUNT",
                            "message": f"LOG_DROP at seq {i} has invalid dropped_count: {dropped_count}",
                        }
                    )

        except VerificationError as e:
            report["status"] = "FAIL"
            report["violations"].append(
                {
                    "type": e.code,
                    "message": e.message,
                    "event_sequence": i,
                    "event_id": event.get("event_id"),
                    "context": e.context,
                }
            )
            # Fail-fast?
            # User request said: "Fail-Fast: Verification pipeline stops at the first failure."
            break
        except Exception as e:
            report["status"] = "FAIL"
            report["violations"].append(
                {"type": "INTERNAL_ERROR", "message": str(e), "event_sequence": i}
            )
            break

    # Determine session completeness and partial reasons
    has_session_end = any(e.get("event_type") == "SESSION_END" for e in events)

    # Track why session might be partial
    if report["authority"] == "server":
        if not report["sealed"]:
            report["partial_reasons"].append("UNSEALED_SESSION")
        if not has_session_end:
            report["partial_reasons"].append("MISSING_SESSION_END")
        if report["total_drops"] > 0:
            if "LOG_DROP_PRESENT" not in report["partial_reasons"]:
                report["partial_reasons"].append("LOG_DROP_PRESENT")
        if report["status"] == "FAIL":
            report["partial_reasons"].append("CHAIN_VALIDATION_FAILED")

    report["complete"] = (
        has_session_end
        and report["status"] == "PASS"
        and report["total_drops"] == 0
        and not report["partial"]
    )

    # Classify evidence
    # Classify evidence
    if report["status"] == "PASS":
        evidence_class = classify_evidence(
            authority=report["authority"],
            sealed=report["sealed"],
            complete=report["complete"],
        )
    else:
        # Failed verification cannot be authoritative
        evidence_class = "NON_AUTHORITATIVE_EVIDENCE"
        if report["status"] == "FAIL":
            report["partial_reasons"].append("VERIFICATION_FAILED")

    report["evidence_class"] = evidence_class

    # Policy enforcement
    policy = policy or {}
    if policy.get("reject_local_authority", False) and report["authority"] == "sdk":
        report["status"] = "FAIL"
        report["violations"].append(
            {
                "type": "POLICY_VIOLATION",
                "message": "Local authority sessions are rejected by policy",
                "evidence_class": evidence_class,
            }
        )
        return report

    if report["status"] == "PASS":
        report["replay_fingerprint"] = calculated_chain_hash

    return report


def _validate_envelope(event: dict[str, Any], index: int):
    """
    Validate that an event envelope contains required fields and an allowed schema version.
    
    Checks that the event dict includes the required envelope keys and that `schema_ver`
    is either the current SPEC_VERSION or "v0.5". Raises a VerificationError with a
    specific error code when a required field is missing or when the schema version
    is not allowed.
    
    Parameters:
        event (dict[str, Any]): The event envelope to validate.
        index (int): The event's index in the input sequence (used for contextual errors).
    
    Raises:
        VerificationError: With code `MISSING_FIELD` if a required key is absent.
        VerificationError: With code `SCHEMA_VERSION_MISMATCH` if `schema_ver` is not allowed.
    """
    required = [
        "event_id",
        "session_id",
        "sequence_number",
        "event_type",
        "payload_hash",
        "event_hash",
        "payload",
        "schema_ver",
    ]
    for field in required:
        if field not in event:
            raise VerificationError("MISSING_FIELD", f"Missing required field: {field}")

    # Spec v0.6: strict schema_ver matching
    if event["schema_ver"] not in [SPEC_VERSION, "v0.5"]:
        raise VerificationError(
            "SCHEMA_VERSION_MISMATCH",
            f"Expected {SPEC_VERSION} or v0.5, got {event['schema_ver']}",
        )


def main():
    """
    Run the AgentOps Replay Verifier command-line tool (Spec v0.6).
    
    Parses a log file (Compliance Export JSON, JSON array, or JSON Lines), verifies the replay using the verifier pipeline, and prints the verification report in either human-readable text or JSON. Exits with code 0 on success and 1 on failure (including load errors and verification failures).
    
    Command-line arguments:
      file
        Path to the input log file (supports Compliance Export JSON, JSON array, or JSONL).
      --format
        Output format: "text" (default) or "json".
      --reject-local-authority
        When present, treat sessions with SDK/local authority as policy violations that cause failure.
    
    Behavior notes:
      - If the input is a Compliance Export, the tool performs an additional metadata check and emits a METADATA_MISMATCH warning if the export's claimed evidence_class differs from the verifier's result (does not convert to failure).
      - When formatting as text, prints a concise summary including session id, status, evidence class, sealed/complete flags, authority, total drops, violations, policy-violation details, and the replay fingerprint on successful verification.
    """
    parser = argparse.ArgumentParser(description="AgentOps Replay Verifier (Spec v0.6)")
    parser.add_argument("file", help="Path to .jsonl log file")
    parser.add_argument(
        "--format", choices=["json", "text"], default="text", help="Output format"
    )
    parser.add_argument(
        "--reject-local-authority",
        action="store_true",
        help="Reject sessions with local (SDK) authority",
    )

    args = parser.parse_args()

    events = []
    export_metadata = None
    try:
        # Try reading as full JSON first (Export format)
        with open(args.file) as f:
            content = f.read()
            try:
                data = json.loads(content)
                if isinstance(data, dict) and "events" in data and isinstance(data["events"], list):
                    # It is a Compliance Export
                    events = data["events"]
                    export_metadata = data
                    print(f"Detected Compliance Export (Format v{data.get('export_version', 'unknown')})")
                else:
                    # It might be a single event or other JSON? Treat as line? 
                    # If it's a list, maybe it's a list of events (not export format but valid JSON array)
                    if isinstance(data, list):
                        events = data
                    else:
                        # Fallback to lines if it was just one JSON object that wasn't an export
                        # But read() consumed it.
                        pass
            except json.JSONDecodeError:
                # Not a single JSON files, try JSONL
                pass
            
            if not events:
                # Try JSONL
                events = []
                for line in content.splitlines():
                    if line.strip():
                        events.append(json.loads(line))
                        
    except Exception as e:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "violations": [{"type": "LOAD_ERROR", "message": str(e)}],
                }
            )
        )
        sys.exit(1)

    policy = {"reject_local_authority": args.reject_local_authority}
    report = verify_session(events, policy)
    
    # If using Export format, verify the summary matches
    if export_metadata and report["status"] == "PASS":
        # Meta-Verification: Does export claim match reality?
        claimed_class = export_metadata.get("evidence_class")
        actual_class = report["evidence_class"]
        
        if claimed_class != actual_class:
            report["warnings"] = report.get("warnings", [])
            report["warnings"].append({
                "type": "METADATA_MISMATCH",
                "message": f"Export claims {claimed_class} but verifier found {actual_class}"
            })
            # Should this fail verification? 
            # Ideally yes, if the evidence is lying about itself.
            # But let's keep it as warning for now unless intended otherwise.

    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(f"Session: {report['session_id']}")
        print(f"Status: {report['status']}")
        print(f"Evidence Class: {report.get('evidence_class', 'UNKNOWN')}")
        print(f"Sealed: {report['sealed']}")
        print(f"Complete: {report['complete']}")
        print(f"Authority: {report['authority']}")
        if report["total_drops"] > 0:
            print(f"Total Drops: {report['total_drops']}")

        # FAIL LOUDLY for policy violations
        if report["status"] == "FAIL":
            policy_violations = [
                v for v in report["violations"] if v.get("type") == "POLICY_VIOLATION"
            ]
            if policy_violations:
                print("\n⚠️  POLICY VIOLATION ⚠️")
                for v in policy_violations:
                    print(f"Reason: {v['message']}")
                    print(f"Evidence Class: {v.get('evidence_class')}")

        if report["violations"]:
            print("\nViolations:")
            for v in report["violations"]:
                print(
                    f"  - [{v['type']}] Seq {v.get('event_sequence')}: {v['message']}"
                )
        elif report["status"] == "PASS":
            print(f"\nFingerprint: {report['replay_fingerprint']}")

    if report["status"] == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()