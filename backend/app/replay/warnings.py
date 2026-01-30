"""
warnings.py - Warning system for replay transparency.

Warnings make explicit all issues in a replay:
- Dropped events
- Sequence gaps
- Timestamp anomalies
- Missing seals
- Partial evidence

Warnings are NOT hidden. They ARE the evidence.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class WarningSeverity(Enum):
    """Severity levels for replay warnings."""
    INFO = "INFO"          # Metadata notes
    WARNING = "WARNING"    # Potential issues
    CRITICAL = "CRITICAL"  # Evidence problems


class WarningCode(Enum):
    """
    Standard warning codes.
    
    These codes are STABLE and machine-readable.
    Auditors and tooling rely on code stability.
    """
    EVENTS_DROPPED = "EVENTS_DROPPED"           # LOG_DROP detected
    SEQUENCE_GAP = "SEQUENCE_GAP"               # Non-contiguous sequence numbers
    TIMESTAMP_ANOMALY = "TIMESTAMP_ANOMALY"     # Timestamps out of order with sequences
    CHAIN_NOT_SEALED = "CHAIN_NOT_SEALED"       # No CHAIN_SEAL present
    PARTIAL_EVIDENCE = "PARTIAL_EVIDENCE"       # Evidence class is PARTIAL
    VERIFICATION_FAILED = "VERIFICATION_FAILED" # Chain verification failed
    REDACTION_PRESENT = "REDACTION_PRESENT"     # Redacted content in chain


# Human-readable messages for each warning code
WARNING_MESSAGES = {
    WarningCode.EVENTS_DROPPED: "{count} event(s) lost due to {reason}",
    WarningCode.SEQUENCE_GAP: "Missing sequence(s) {start} to {end}",
    WarningCode.TIMESTAMP_ANOMALY: "Timestamp at position {pos} is earlier than previous event",
    WarningCode.CHAIN_NOT_SEALED: "Chain has no CHAIN_SEAL event",
    WarningCode.PARTIAL_EVIDENCE: "Evidence class is PARTIAL_AUTHORITATIVE_EVIDENCE",
    WarningCode.VERIFICATION_FAILED: "Chain verification failed: {reason}",
    WarningCode.REDACTION_PRESENT: "Redacted content detected at position {pos}",
}


@dataclass
class ReplayWarning:
    """A warning about replay evidence quality."""
    severity: WarningSeverity
    code: WarningCode
    message: str
    frame_position: Optional[int] = None  # If warning relates to specific frame
    
    @classmethod
    def events_dropped(cls, count: int, reason: str, position: int) -> 'ReplayWarning':
        """
        Create a ReplayWarning indicating that one or more events were dropped.
        
        Parameters:
            count (int): Number of events that were dropped.
            reason (str): Human-readable explanation for the drop.
            position (int): Frame position associated with the dropped events.
        
        Returns:
            ReplayWarning: Warning with severity WARNING and code EVENTS_DROPPED; its message is formatted using `count` and `reason`, and `frame_position` is set to `position`.
        """
        return cls(
            severity=WarningSeverity.WARNING,
            code=WarningCode.EVENTS_DROPPED,
            message=WARNING_MESSAGES[WarningCode.EVENTS_DROPPED].format(
                count=count, reason=reason
            ),
            frame_position=position
        )
    
    @classmethod
    def sequence_gap(cls, start: int, end: int, position: int) -> 'ReplayWarning':
        """
        Create a warning for a gap in sequence numbers.
        
        Parameters:
            start (int): Start of the missing sequence range.
            end (int): End of the missing sequence range.
            position (int): Frame position associated with the gap.
        
        Returns:
            ReplayWarning: Warning with severity WARNING, code SEQUENCE_GAP, a message formatted with `start` and `end`, and `frame_position` set to `position`.
        """
        return cls(
            severity=WarningSeverity.WARNING,
            code=WarningCode.SEQUENCE_GAP,
            message=WARNING_MESSAGES[WarningCode.SEQUENCE_GAP].format(
                start=start, end=end
            ),
            frame_position=position
        )
    
    @classmethod
    def timestamp_anomaly(cls, position: int) -> 'ReplayWarning':
        """
        Create a ReplayWarning for an out-of-order timestamp at a specific frame position.
        
        Parameters:
            position (int): Frame position where the timestamp anomaly was observed.
        
        Returns:
            ReplayWarning: A warning with severity `INFO`, code `TIMESTAMP_ANOMALY`, a message formatted with `position`, and `frame_position` set to `position`.
        """
        return cls(
            severity=WarningSeverity.INFO,
            code=WarningCode.TIMESTAMP_ANOMALY,
            message=WARNING_MESSAGES[WarningCode.TIMESTAMP_ANOMALY].format(pos=position),
            frame_position=position
        )
    
    @classmethod
    def chain_not_sealed(cls) -> 'ReplayWarning':
        """
        Create a ReplayWarning indicating the chain is not sealed.
        
        Returns:
            ReplayWarning: A warning with severity CRITICAL, code CHAIN_NOT_SEALED, and the corresponding message from WARNING_MESSAGES. The warning has no frame_position set.
        """
        return cls(
            severity=WarningSeverity.CRITICAL,
            code=WarningCode.CHAIN_NOT_SEALED,
            message=WARNING_MESSAGES[WarningCode.CHAIN_NOT_SEALED]
        )
    
    @classmethod
    def partial_evidence(cls) -> 'ReplayWarning':
        """
        Create a warning indicating the chain's evidence is partial.
        
        Returns:
            ReplayWarning: A warning with severity WARNING and code PARTIAL_EVIDENCE.
        """
        return cls(
            severity=WarningSeverity.WARNING,
            code=WarningCode.PARTIAL_EVIDENCE,
            message=WARNING_MESSAGES[WarningCode.PARTIAL_EVIDENCE]
        )
    
    @classmethod
    def verification_failed(cls, reason: str) -> 'ReplayWarning':
        """
        Create a ReplayWarning for a chain verification failure.
        
        Parameters:
        	reason (str): Human-readable explanation of why verification failed; interpolated into the warning message.
        
        Returns:
        	ReplayWarning: A warning with severity CRITICAL, code VERIFICATION_FAILED, and a message containing the provided reason.
        """
        return cls(
            severity=WarningSeverity.CRITICAL,
            code=WarningCode.VERIFICATION_FAILED,
            message=WARNING_MESSAGES[WarningCode.VERIFICATION_FAILED].format(reason=reason)
        )