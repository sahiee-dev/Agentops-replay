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
    
    # Degrading (cause DEGRADED)
    LOG_DROP_DETECTED = "LOG_DROP_DETECTED"
    REDACTION_DETECTED = "REDACTION_DETECTED"
    
    # Informational
    INFO = "INFO"


class FindingSeverity(str, Enum):
    FATAL = "FATAL"  # Causes FAIL
    WARNING = "WARNING"  # Causes DEGRADED
    INFO = "INFO"  # No status impact


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
        """
        Convert the Finding into a dictionary representation.
        
        Returns:
            dict: Dictionary with keys:
                - "type": string value of the finding type enum.
                - "severity": string value of the finding severity enum.
                - "message": the finding message.
                - "sequence_number": the sequence number or None.
                - "event_id": the event identifier or None.
                - "details": a dict of additional details (empty dict if no details were provided).
        """
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
        """
        Classify the verification report into an evidence class.
        
        Determines the report's EvidenceClass according to the following rules:
        - `EvidenceClass.CLASS_C` when status is `VerificationStatus.FAIL`.
        - `EvidenceClass.CLASS_B` when status is `VerificationStatus.DEGRADED`.
        - `EvidenceClass.CLASS_B` when status is `VerificationStatus.PASS` but one or more `FindingType.LOG_DROP_DETECTED` findings are present.
        - `EvidenceClass.CLASS_A` when status is `VerificationStatus.PASS` and no log-drop findings are present.
        
        Returns:
            EvidenceClass: The derived evidence class (`CLASS_A`, `CLASS_B`, or `CLASS_C`) for this report.
        """
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
        """
        Provide a human-readable rationale explaining why the report was assigned its evidence class.
        
        For CLASS_A returns "Full chain, no gaps, no drops, trusted authority".
        For CLASS_B returns "Verified but X LOG_DROP event(s) detected" when LOG_DROP_DETECTED findings exist, otherwise "Verified but degraded (incomplete evidence)".
        For CLASS_C (or other non-passing classes) returns "Integrity failure: N fatal finding(s)", where N is the count of findings with fatal severity.
        
        Returns:
            rationale (str): The rationale message corresponding to the report's evidence class.
        """
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
        """
        Serialize the VerificationReport into a plain dictionary suitable for JSON or programmatic consumption.
        
        Returns:
            report_dict (Dict[str, Any]): Dictionary with keys:
                - "session_id": str session identifier.
                - "status": str enum value of the verification status.
                - "evidence_class": str enum value of the derived evidence class.
                - "evidence_class_rationale": str human-readable rationale for the evidence class.
                - "event_count": int number of events processed.
                - "first_event_hash": Optional[str] hash of the first event, or None.
                - "final_event_hash": Optional[str] hash of the final event, or None.
                - "chain_authority": Optional[str] authoritative chain identifier, or None.
                - "verification_mode": str verification mode (e.g., "FULL" or "REDACTED").
                - "findings": List[Dict[str, Any]] list of findings serialized via each Finding.to_dict().
                - "exit_code": int machine-friendly exit code (0 = PASS, 1 = DEGRADED, 2 = other).
        """
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
        """
        Map the report's verification status to a machine-friendly exit code.
        
        Returns:
            int: Exit code where 0 = PASS, 1 = DEGRADED, 2 = any other status.
        """
        if self.status == VerificationStatus.PASS:
            return 0
        elif self.status == VerificationStatus.DEGRADED:
            return 1
        else:
            return 2