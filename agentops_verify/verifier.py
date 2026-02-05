"""
agentops_verify/verifier.py - Production Verifier Core

The Verifier is what turns logging into evidence.

Guarantees:
- Recompute full hash chain
- Detect any mutation
- Verify authority lineage
- Produce signed verification report

Properties:
- Runs offline
- No ingestion dependency
- Deterministic
- Stateless
"""
import hashlib
import json
from typing import List, Dict, Any, Optional, Set

from .errors import (
    VerificationStatus,
    VerificationReport,
    Finding,
    FindingType,
    FindingSeverity,
)

# Import JCS from SDK (shared canonical implementation)
from agentops_sdk import jcs


# Trusted authority prefixes (can be extended via config)
TRUSTED_AUTHORITIES: Set[str] = {
    "agentops-ingest-v1",
    "agentops-ingest-v2",  # Future-proofing
}


def verify_session(
    events: List[Dict[str, Any]],
    trusted_authorities: Optional[Set[str]] = None,
    allow_redacted: bool = True,
) -> VerificationReport:
    """
    Verify a session of sealed events and produce a deterministic verification report.
    
    Validates sequence continuity, session consistency, chain authority, prev-event linkage, payload and event hashes, and detects log drops and redaction markers; accumulates findings and summarizes the outcome.
    
    Parameters:
        events (List[Dict[str, Any]]): Ordered list of sealed event objects comprising a session.
        trusted_authorities (Optional[Set[str]]): Allowed chain_authority prefixes; defaults to module TRUSTED_AUTHORITIES.
        allow_redacted (bool): If True, redacted content is treated as acceptable for the report (recorded in verification_mode); this flag does not alter the verification checks.
    
    Returns:
        VerificationReport: Report containing session_id, status (one of PASS, FAIL, DEGRADED), event_count, first_event_hash, final_event_hash, chain_authority, verification_mode, and a list of Findings describing any issues.
    """
    if trusted_authorities is None:
        trusted_authorities = TRUSTED_AUTHORITIES
    
    findings: List[Finding] = []
    
    # Empty session check
    if not events:
        return VerificationReport(
            session_id="UNKNOWN",
            status=VerificationStatus.FAIL,
            event_count=0,
            first_event_hash=None,
            final_event_hash=None,
            chain_authority=None,
            verification_mode="UNKNOWN",
            findings=[Finding(
                finding_type=FindingType.CHAIN_BREAK,
                severity=FindingSeverity.FATAL,
                message="Empty session - no events to verify"
            )]
        )
    
    session_id = events[0].get("session_id", "UNKNOWN")
    chain_authority = None
    verification_mode = "FULL"
    
    prev_expected_hash: Optional[str] = None
    first_event_hash: Optional[str] = None
    final_event_hash: Optional[str] = None
    
    for i, event in enumerate(events):
        event_seq = event.get("sequence_number", -1)
        event_id = event.get("event_id", "UNKNOWN")
        
        # 1. Verify sequence continuity
        if event_seq != i:
            findings.append(Finding(
                finding_type=FindingType.SEQUENCE_VIOLATION,
                severity=FindingSeverity.FATAL,
                message=f"Expected sequence {i}, got {event_seq}",
                sequence_number=event_seq,
                event_id=event_id,
            ))
        
        # 2. Verify session_id consistency
        if event.get("session_id") != session_id:
            findings.append(Finding(
                finding_type=FindingType.CHAIN_BREAK,
                severity=FindingSeverity.FATAL,
                message=f"Session ID mismatch at seq {event_seq}",
                sequence_number=event_seq,
                event_id=event_id,
                details={"expected": session_id, "got": event.get("session_id")}
            ))
        
        # 3. Verify authority
        event_authority = event.get("chain_authority")
        if event_authority not in trusted_authorities:
            findings.append(Finding(
                finding_type=FindingType.AUTHORITY_INVALID,
                severity=FindingSeverity.FATAL,
                message=f"Unknown authority: {event_authority}",
                sequence_number=event_seq,
                event_id=event_id,
            ))
        else:
            chain_authority = event_authority
        
        # 4. Verify prev_event_hash linkage
        recorded_prev_hash = event.get("prev_event_hash")
        if prev_expected_hash != recorded_prev_hash:
            findings.append(Finding(
                finding_type=FindingType.CHAIN_BREAK,
                severity=FindingSeverity.FATAL,
                message=f"Chain break at seq {event_seq}: prev_event_hash mismatch",
                sequence_number=event_seq,
                event_id=event_id,
                details={
                    "expected": prev_expected_hash,
                    "recorded": recorded_prev_hash
                }
            ))
        
        # 5. Recompute payload hash
        payload = event.get("payload", {})
        try:
            canonical_payload = jcs.canonicalize(payload)
            computed_payload_hash = hashlib.sha256(canonical_payload).hexdigest()
            
            if computed_payload_hash != event.get("payload_hash"):
                findings.append(Finding(
                    finding_type=FindingType.PAYLOAD_TAMPER,
                    severity=FindingSeverity.FATAL,
                    message=f"Payload hash mismatch at seq {event_seq}",
                    sequence_number=event_seq,
                    event_id=event_id,
                    details={
                        "computed": computed_payload_hash,
                        "recorded": event.get("payload_hash")
                    }
                ))
        except Exception as e:
            findings.append(Finding(
                finding_type=FindingType.PAYLOAD_TAMPER,
                severity=FindingSeverity.FATAL,
                message=f"Cannot canonicalize payload at seq {event_seq}: {e}",
                sequence_number=event_seq,
                event_id=event_id,
            ))
        
        # 6. Recompute event hash
        signed_obj = {
            "event_id": event.get("event_id"),
            "session_id": event.get("session_id"),
            "sequence_number": event.get("sequence_number"),
            "timestamp_wall": event.get("timestamp_wall"),
            "event_type": event.get("event_type"),
            "payload_hash": event.get("payload_hash"),
            "prev_event_hash": event.get("prev_event_hash"),
        }
        
        try:
            canonical_envelope = jcs.canonicalize(signed_obj)
            computed_event_hash = hashlib.sha256(canonical_envelope).hexdigest()
            
            if computed_event_hash != event.get("event_hash"):
                findings.append(Finding(
                    finding_type=FindingType.HASH_MISMATCH,
                    severity=FindingSeverity.FATAL,
                    message=f"Event hash mismatch at seq {event_seq}",
                    sequence_number=event_seq,
                    event_id=event_id,
                    details={
                        "computed": computed_event_hash,
                        "recorded": event.get("event_hash")
                    }
                ))
        except Exception as e:
            findings.append(Finding(
                finding_type=FindingType.HASH_MISMATCH,
                severity=FindingSeverity.FATAL,
                message=f"Cannot compute event hash at seq {event_seq}: {e}",
                sequence_number=event_seq,
                event_id=event_id,
            ))
        
        # 7. Check for LOG_DROP events
        if event.get("event_type") == "LOG_DROP":
            findings.append(Finding(
                finding_type=FindingType.LOG_DROP_DETECTED,
                severity=FindingSeverity.WARNING,
                message=f"LOG_DROP at seq {event_seq}: evidence incomplete",
                sequence_number=event_seq,
                event_id=event_id,
                details=payload
            ))
            verification_mode = "DEGRADED"
        
        # 8. Check for redaction markers
        if _contains_redaction(payload):
            if not allow_redacted:
                findings.append(Finding(
                    finding_type=FindingType.POLICY_VIOLATION,
                    severity=FindingSeverity.FATAL,
                    message=f"Redacted content forbidden at seq {event_seq}",
                    sequence_number=event_seq,
                    event_id=event_id,
                ))
            else:
                findings.append(Finding(
                    finding_type=FindingType.REDACTION_DETECTED,
                    severity=FindingSeverity.INFO,
                    message=f"Redacted content at seq {event_seq}",
                    sequence_number=event_seq,
                    event_id=event_id,
                ))
                verification_mode = "REDACTED"
        
        # Update chain tracking
        # CRITICAL: Use computed hash to prevent tamper propagation
        try:
            prev_expected_hash = computed_event_hash
            if first_event_hash is None:
                first_event_hash = computed_event_hash
            final_event_hash = computed_event_hash
        except NameError:
            # Fallback if computation failed
            prev_expected_hash = event.get("event_hash")
            if first_event_hash is None:
                first_event_hash = event.get("event_hash")
            final_event_hash = event.get("event_hash")
    
    # Determine final status
    fatal_count = sum(1 for f in findings if f.severity == FindingSeverity.FATAL)
    warning_count = sum(1 for f in findings if f.severity == FindingSeverity.WARNING)
    
    if fatal_count > 0:
        status = VerificationStatus.FAIL
    elif warning_count > 0:
        status = VerificationStatus.DEGRADED
    else:
        status = VerificationStatus.PASS
    
    return VerificationReport(
        session_id=session_id,
        status=status,
        event_count=len(events),
        first_event_hash=first_event_hash,
        final_event_hash=final_event_hash,
        chain_authority=chain_authority,
        verification_mode=verification_mode,
        findings=findings,
    )


def _contains_redaction(payload: Dict[str, Any]) -> bool:
    """
    Detects whether a payload contains redaction markers.
    
    Recursively inspects strings, dictionaries, and lists within the payload for the markers "[REDACTED]" or "***".
    
    Parameters:
        payload (Dict[str, Any]): The payload to inspect; may contain nested dicts and lists.
    
    Returns:
        bool: `True` if any redaction marker is found, `False` otherwise.
    """
    def check_value(v: Any) -> bool:
        """
        Detects whether a value (possibly nested) contains redaction markers.
        
        Recursively inspects strings, dicts, and lists to find the markers "[REDACTED]" or "***". Non-iterable, non-string values are treated as not containing redactions.
        
        Parameters:
            v (Any): The value to inspect; may be a string, dict, list, or other type.
        
        Returns:
            bool: `True` if a redaction marker is found anywhere in `v`, `False` otherwise.
        """
        if isinstance(v, str):
            return "[REDACTED]" in v or "***" in v
        elif isinstance(v, dict):
            return any(check_value(val) for val in v.values())
        elif isinstance(v, list):
            return any(check_value(item) for item in v)
        return False
    
    return check_value(payload)


def verify_file(filepath: str, **kwargs) -> VerificationReport:
    """
    Verify a session stored in a JSON file.
    
    Parameters:
        filepath (str): Path to a JSON file containing a list of event objects representing a session.
        **kwargs: Additional verification options forwarded to the session verifier (for example, trusted_authorities and allow_redacted).
    
    Returns:
        VerificationReport: Summary of the verification including session_id, status, event_count, first_event_hash, final_event_hash, chain_authority, verification_mode, and findings.
    """
    with open(filepath, 'r') as f:
        events = json.load(f)
    
    return verify_session(events, **kwargs)