"""
replay_v2.py - Pydantic schemas for replay API responses.

All schemas preserve raw payloads. No derived fields.
Payloads are VERBATIM canonical JSON, not reformatted.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from enum import Enum


class VerificationStatusSchema(str, Enum):
    """Verification status enum for API responses."""
    VALID = "VALID"
    INVALID = "INVALID"


class FrameTypeSchema(str, Enum):
    """Frame type enum for API responses."""
    EVENT = "EVENT"
    GAP = "GAP"
    LOG_DROP = "LOG_DROP"
    REDACTION = "REDACTION"


class WarningSeveritySchema(str, Enum):
    """Warning severity enum for API responses."""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ReplayFrameSchema(BaseModel):
    """Schema for a single replay frame."""
    frame_type: FrameTypeSchema
    position: int
    
    # EVENT fields
    sequence_number: Optional[int] = None
    timestamp: Optional[str] = None
    event_type: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None  # VERBATIM canonical JSON
    event_hash: Optional[str] = None
    
    # GAP fields
    gap_start: Optional[int] = None
    gap_end: Optional[int] = None
    
    # LOG_DROP fields
    dropped_count: Optional[int] = None
    drop_reason: Optional[str] = None
    
    class Config:
        use_enum_values = True


class ReplayWarningSchema(BaseModel):
    """Schema for a replay warning."""
    severity: WarningSeveritySchema
    code: str  # Stable warning code
    message: str
    frame_position: Optional[int] = None
    
    class Config:
        use_enum_values = True


class ReplayResponseSchema(BaseModel):
    """
    Full replay response for a verified session.
    
    INVARIANT: This response is ONLY generated from verified chains.
    """
    session_id: str
    evidence_class: str
    seal_present: bool
    verification_status: VerificationStatusSchema
    
    frames: List[ReplayFrameSchema]
    warnings: List[ReplayWarningSchema]
    
    event_count: int
    total_drops: int
    first_timestamp: Optional[str] = None
    last_timestamp: Optional[str] = None
    final_hash: str
    
    class Config:
        use_enum_values = True


class VerificationResponseSchema(BaseModel):
    """Response for verification-only endpoint."""
    session_id: str
    verification_status: VerificationStatusSchema
    evidence_class: Optional[str] = None
    seal_present: Optional[bool] = None
    event_count: Optional[int] = None
    warning_count: Optional[int] = None
    
    # On failure
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    
    class Config:
        use_enum_values = True


class ReplayFailureSchema(BaseModel):
    """
    Explicit failure response when verification fails.
    
    CRITICAL: No frames, no partial data, no metadata.
    """
    session_id: str
    verification_status: VerificationStatusSchema  # Always INVALID
    error_code: str
    error_message: str
    
    class Config:
        use_enum_values = True


class FrameResponseSchema(BaseModel):
    """Response for single frame endpoint."""
    session_id: str
    requested_sequence: int
    frame: ReplayFrameSchema
    
    class Config:
        use_enum_values = True
