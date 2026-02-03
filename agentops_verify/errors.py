"""
agentops_verify/errors.py - Verification Error Taxonomy

Machine-readable verification outcomes.
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


class VerificationStatus(str, Enum):
    """Final verification outcome."""
    PASS = "PASS"
    FAIL = "FAIL"
    DEGRADED = "DEGRADED"


class EvidenceClass(str, Enum):
    """Formal evidence classification per EVIDENCE_CLASSIFICATION_SPEC.md"""
    CLASS_A = "A"  # Authoritative: Court/regulator grade
    CLASS_B = "B"  # Degraded: Internal audit grade
    CLASS_C = "C"  # Non-authoritative: Engineering only


class FindingType(str, Enum):
    """Classification of individual findings."""
    # Fatal (cause FAIL)
    CHAIN_BREAK = "CHAIN_BREAK"
    HASH_MISMATCH = "HASH_MISMATCH"
    PAYLOAD_TAMPER = "PAYLOAD_TAMPER"
    AUTHORITY_INVALID = "AUTHORITY_INVALID"
    SEQUENCE_VIOLATION = "SEQUENCE_VIOLATION"
    REDACTION_INTEGRITY_VIOLATION = "REDACTION_INTEGRITY_VIOLATION"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    
    # Degrading (cause DEGRADED)
    LOG_DROP_DETECTED = "LOG_DROP_DETECTED"
    REDACTION_DETECTED = "REDACTION_DETECTED"
    
    # Informational
    INFO = "INFO"


class FindingSeverity(str, Enum):
    FATAL = "FATAL"  # Causes FAIL
    WARNING = "WARNING"  # Causes DEGRADED
    INFO = "INFO"  # No status impact


# Strict Exit Code Contract
EXIT_CODES = {
    VerificationStatus.PASS: 0,
    VerificationStatus.DEGRADED: 1,
    VerificationStatus.FAIL: 2,
}

@dataclass
class Finding:
    """Individual verification finding."""
    finding_type: FindingType
    severity: FindingSeverity
    message: str
    sequence_number: Optional[int] = None
    event_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.finding_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "sequence_number": self.sequence_number,
            "event_id": self.event_id,
            "details": self.details or {}
        }


@dataclass
class VerificationReport:
    """Complete verification report."""
    session_id: str
    status: VerificationStatus
    event_count: int
    first_event_hash: Optional[str]
    final_event_hash: Optional[str]
    chain_authority: Optional[str]
    verification_mode: str  # "FULL" or "REDACTED"
    findings: List[Finding] = field(default_factory=list)
    
    @property
    def evidence_class(self) -> EvidenceClass:
        """Derive evidence class per EVIDENCE_CLASSIFICATION_SPEC.md"""
        if self.status == VerificationStatus.FAIL:
            return EvidenceClass.CLASS_C
        
        if self.status == VerificationStatus.DEGRADED:
            return EvidenceClass.CLASS_B
        
        # PASS status - check for log drops or gaps
        has_log_drops = any(
            f.finding_type == FindingType.LOG_DROP_DETECTED 
            for f in self.findings
        )
        if has_log_drops:
            return EvidenceClass.CLASS_B
        
        return EvidenceClass.CLASS_A
    
    @property
    def evidence_class_rationale(self) -> str:
        """Human-readable rationale for classification."""
        if self.evidence_class == EvidenceClass.CLASS_A:
            return "Full chain, no gaps, no drops, trusted authority"
        elif self.evidence_class == EvidenceClass.CLASS_B:
            log_drops = [f for f in self.findings if f.finding_type == FindingType.LOG_DROP_DETECTED]
            if log_drops:
                return f"Verified but {len(log_drops)} LOG_DROP event(s) detected"
            return "Verified but degraded (incomplete evidence)"
        else:
            fatal = [f for f in self.findings if f.severity == FindingSeverity.FATAL]
            return f"Integrity failure: {len(fatal)} fatal finding(s)"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "evidence_class": self.evidence_class.value,
            "evidence_class_rationale": self.evidence_class_rationale,
            "event_count": self.event_count,
            "first_event_hash": self.first_event_hash,
            "final_event_hash": self.final_event_hash,
            "chain_authority": self.chain_authority,
            "verification_mode": self.verification_mode,
            "findings": [f.to_dict() for f in self.findings],
            "exit_code": self.exit_code
        }
    
    @property
    def exit_code(self) -> int:
        """Machine-verifiable exit code (Contract Locked)."""
        return EXIT_CODES.get(self.status, 2)  # Default to FAIL (2) if undefined status
