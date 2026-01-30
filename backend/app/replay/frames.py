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
from typing import Any


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
    sequence_number: int | None = None
    timestamp: str | None = None
    event_type: str | None = None
    payload: dict[str, Any] | None = None  # VERBATIM from chain
    event_hash: str | None = None

    # For GAP frames - detected structural absence
    gap_start: int | None = None  # First missing sequence
    gap_end: int | None = None    # Last missing sequence

    # For LOG_DROP frames - from recorded LOG_DROP
    dropped_count: int | None = None
    drop_reason: str | None = None

    # For REDACTION frames - from recorded redaction
    redacted_fields: list | None = None
    redaction_hash: str | None = None

    def validate_single_origin(self) -> bool:
        """
        Validate that this frame has exactly one origin.
        
        INVARIANT: Exactly one origin group must be populated.
        Returns False if more than one group is present.
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
