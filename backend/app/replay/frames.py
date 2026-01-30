"""
frames.py - Frame data structures for replay system.

SINGLE-ORIGIN FRAME INVARIANT:
A ReplayFrame MUST be derivable from exactly one of:
1. A recorded event
2. A detected structural absence (gap/drop)

No frame may exist without a single, traceable origin.
This prevents future additions like "CONTEXT", "SUMMARY", or "STATE" frames.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional


class VerificationStatus(Enum):
    """
    Verification status of a session chain.
    REQUIRED: Must be enum, not free string. Enums enforce invariant boundaries.
    """
    VALID = "VALID"
    INVALID = "INVALID"


class FrameType(Enum):
    """
    Types of frames in a replay.
    
    Each frame type has exactly one origin:
    - EVENT: A recorded event from the chain
    - GAP: A detected missing sequence range
    - LOG_DROP: An explicit drop marker from the chain
    - REDACTION: A redacted content notice from the chain
    """
    EVENT = "EVENT"           # Normal recorded event
    GAP = "GAP"              # Missing sequence range
    LOG_DROP = "LOG_DROP"    # Explicit drop marker
    REDACTION = "REDACTION"  # Redacted content notice


@dataclass
class ReplayFrame:
    """
    A single frame in a replay timeline.
    
    INVARIANT: Every frame must have exactly one traceable origin.
    - EVENT frames come from recorded events
    - GAP frames come from detected sequence absences
    - LOG_DROP frames come from recorded LOG_DROP events
    - REDACTION frames come from recorded events with [REDACTED] fields
    """
    frame_type: FrameType
    
    # Position (required for all frames)
    position: int  # Frame position in the replay
    
    # For EVENT frames - from recorded event
    sequence_number: Optional[int] = None
    timestamp: Optional[str] = None
    event_type: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None  # VERBATIM from chain
    event_hash: Optional[str] = None
    
    # For GAP frames - detected structural absence
    gap_start: Optional[int] = None  # First missing sequence
    gap_end: Optional[int] = None    # Last missing sequence
    
    # For LOG_DROP frames - from recorded LOG_DROP
    dropped_count: Optional[int] = None
    drop_reason: Optional[str] = None
    
    # For REDACTION frames - from recorded redaction
    redacted_fields: Optional[list] = None
    redaction_hash: Optional[str] = None
    
    def validate_single_origin(self) -> bool:
        """
        Ensure the frame has exactly one origin group populated and that the populated origin corresponds to the frame's declared FrameType.
        
        An origin is considered present if:
        - EVENT: both `event_type` and `event_hash` are set.
        - GAP: both `gap_start` and `gap_end` are set.
        - LOG_DROP: `dropped_count` is set.
        - REDACTION: `redaction_hash` is set.
        
        Returns:
            True if exactly one origin group is present and that origin matches `frame_type`, False otherwise.
        """
        # Compute presence flags for each origin group
        event_present = self.event_type is not None and self.event_hash is not None
        gap_present = self.gap_start is not None and self.gap_end is not None
        log_drop_present = self.dropped_count is not None
        redaction_present = self.redaction_hash is not None
        
        # Count how many origin groups are present
        origin_count = sum([event_present, gap_present, log_drop_present, redaction_present])
        
        # Exactly one origin must be present
        if origin_count != 1:
            return False
        
        # Validate that the declared frame_type matches the present origin
        if self.frame_type == FrameType.EVENT:
            return event_present
        elif self.frame_type == FrameType.GAP:
            return gap_present
        elif self.frame_type == FrameType.LOG_DROP:
            return log_drop_present
        elif self.frame_type == FrameType.REDACTION:
            return redaction_present
        
        return False