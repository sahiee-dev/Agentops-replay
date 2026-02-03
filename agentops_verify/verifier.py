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
    Verify a session's integrity.
    
    Args:
        events: List of sealed events (from session_golden.json)
        trusted_authorities: Set of allowed chain_authority values
        allow_redacted: Whether REDACTED mode is acceptable
    
    Returns:
        VerificationReport with PASS/FAIL/DEGRADED status
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
        
        # 8. Check for redaction (Structural + Policy)
        redaction_findings = _check_redaction_integrity(payload, event_seq, event_id)
        findings.extend(redaction_findings)
        
        has_redaction = any(f.finding_type == FindingType.REDACTION_DETECTED or f.finding_type == FindingType.REDACTION_INTEGRITY_VIOLATION for f in redaction_findings)
        
        if has_redaction:
            if not allow_redacted:
                findings.append(Finding(
                    finding_type=FindingType.POLICY_VIOLATION,
                    severity=FindingSeverity.FATAL,
                    message=f"Redacted content forbidden at seq {event_seq}",
                    sequence_number=event_seq,
                    event_id=event_id,
                ))
            else:
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


def _check_redaction_integrity(payload: Any, seq: int, event_id: str) -> List[Finding]:
    """
    Recursively check for redaction markers and enforce integrity:
    If value is "[REDACTED]", sibling/parent must have corresponding *_hash.
    """
    findings = []
    
    def walk(obj: Any, parent: Optional[Dict] = None):
        if isinstance(obj, dict):
            for k, v in obj.items():
                # Check for [REDACTED] value
                if isinstance(v, str) and (v == "[REDACTED]" or v == "***"):
                    # Structural Integrity Check
                    # Expect corresponding hash field, e.g., "email" -> "email_hash"
                    hash_key = f"{k}_hash"
                    has_hash = False
                    
                    if parent and hash_key in parent: 
                        # This works if the hash is in the parent object (unlikely for nested dicts usually, strictness varies)
                        # Wait, standard pattern: 
                        # {"user": {"email": "[REDACTED]", "email_hash": "..."}} (Sibling)
                        # OR {"user": {"email": "[REDACTED]"}, "user_hash": "..."} (Parent)
                        # User Spec: "corresponding *_hash field MUST be present"
                        pass
                    
                    # Check sibling (in the same dict 'obj')
                    if hash_key in obj:
                        has_hash = True
                        # Verify it's a valid hash string (basic check)
                        if not isinstance(obj[hash_key], str) or len(obj[hash_key]) < 64:
                             findings.append(Finding(
                                finding_type=FindingType.REDACTION_INTEGRITY_VIOLATION,
                                severity=FindingSeverity.FATAL,
                                message=f"Redaction hash malformed for field '{k}' at seq {seq}",
                                sequence_number=seq,
                                event_id=event_id,
                                details={"field": k, "hash_key": hash_key}
                            ))
                    else:
                        # Missing hash
                         findings.append(Finding(
                            finding_type=FindingType.REDACTION_INTEGRITY_VIOLATION,
                            severity=FindingSeverity.FATAL,
                            message=f"Redaction integrity failure: Missing hash for field '{k}' at seq {seq}",
                            sequence_number=seq,
                            event_id=event_id,
                            details={"field": k, "missing_key": hash_key}
                        ))
                    
                    # Always log detection
                    findings.append(Finding(
                        finding_type=FindingType.REDACTION_DETECTED,
                        severity=FindingSeverity.INFO,
                        message=f"Redacted content found in field '{k}'",
                        sequence_number=seq,
                        event_id=event_id,
                        details={"field": k}
                    ))
                
                else:
                    walk(v, obj)
                    
        elif isinstance(obj, list):
            for item in obj:
                walk(item, parent) # Parent remains same for list items? Or None? List items don't have keys.
    
    walk(payload)
    return findings


def verify_file(filepath: str, **kwargs) -> VerificationReport:
    """
    Verify a session from a JSON file.
    
    Convenience wrapper for verify_session.
    """
    with open(filepath, 'r') as f:
        events = json.load(f)
    
    return verify_session(events, **kwargs)
