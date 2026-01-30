"""
replay_v2.py - Pydantic schemas for replay API responses.

All schemas preserve raw payloads. No derived fields.
Payloads are VERBATIM canonical JSON, not reformatted.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict


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
    sequence_number: int | None = None
    timestamp: str | None = None
    event_type: str | None = None
    payload: str | None = None  # VERBATIM RFC-8785 canonical JSON string
    event_hash: str | None = None

    # GAP fields
    gap_start: int | None = None
    gap_end: int | None = None

    # LOG_DROP fields
    dropped_count: int | None = None
    drop_reason: str | None = None

    # REDACTION fields
    redaction_hash: str | None = None
    redacted_fields: list[str] | None = None

    model_config = ConfigDict(use_enum_values=True)


class ReplayWarningSchema(BaseModel):
    """Schema for a replay warning."""
    severity: WarningSeveritySchema
    code: str  # Stable warning code
    message: str
    frame_position: int | None = None

    model_config = ConfigDict(use_enum_values=True)


class ReplayResponseSchema(BaseModel):
    """
    Full replay response for a verified session.
    
    INVARIANT: This response is ONLY generated from verified chains.
    """
    session_id: str
    evidence_class: str
    seal_present: bool
    verification_status: VerificationStatusSchema

    frames: list[ReplayFrameSchema]
    warnings: list[ReplayWarningSchema]

    event_count: int
    total_drops: int
    first_timestamp: str | None = None
    last_timestamp: str | None = None
    final_hash: str

    model_config = ConfigDict(use_enum_values=True)


class VerificationResponseSchema(BaseModel):
    """Response for verification-only endpoint."""
    session_id: str
    verification_status: VerificationStatusSchema
    evidence_class: str | None = None
    seal_present: bool | None = None
    event_count: int | None = None
    warning_count: int | None = None

    # On failure
    error_code: str | None = None
    error_message: str | None = None


    model_config = ConfigDict(use_enum_values=True)


class ReplayFailureSchema(BaseModel):
    """
    Explicit failure response when verification fails.
    
    CRITICAL: No frames, no partial data, no metadata.
    """
    session_id: str
    verification_status: VerificationStatusSchema  # Always INVALID
    error_code: str
    error_message: str

    model_config = ConfigDict(use_enum_values=True)


class FrameResponseSchema(BaseModel):
    """Response for single frame endpoint."""
    session_id: str
    requested_sequence: int
    frame: ReplayFrameSchema

    model_config = ConfigDict(use_enum_values=True)
