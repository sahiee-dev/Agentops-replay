"""
ingestion.py - Pydantic schemas for ingestion API.

HARD INVARIANTS:
- Sequence is the ONLY ordering authority
- Timestamps are opaque metadata (stored verbatim, never validated for ordering)
- seal=true only honored if last event is SESSION_END
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class AuthorityType(str, Enum):
    """Authority types for sessions"""

    SERVER = "server"
    SDK = "sdk"


class RejectionCode(str, Enum):
    """Rejection codes for ingestion failures"""

    ALREADY_SEALED = "ALREADY_SEALED"
    SEQUENCE_GAP = "SEQUENCE_GAP"
    DUPLICATE_SEQUENCE = "DUPLICATE_SEQUENCE"
    NON_MONOTONIC_SEQUENCE = "NON_MONOTONIC_SEQUENCE"
    INVALID_SEAL_REQUEST = "INVALID_SEAL_REQUEST"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    INVALID_PAYLOAD = "INVALID_PAYLOAD"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"


# --- Raw Event Input ---


class RawEventCreate(BaseModel):
    """
    Single event from SDK (untrusted).

    INVARIANT: timestamp_monotonic is OPAQUE METADATA.
    It is stored but NEVER used for ordering validation.
    """

    event_type: str = Field(
        ..., description="Event type (SESSION_START, LLM_CALL, etc.)"
    )
    sequence_number: int = Field(
        ..., ge=0, description="Monotonic sequence (ORDERING AUTHORITY)"
    )
    timestamp_monotonic: int = Field(
        ..., ge=0, description="Client timestamp (OPAQUE, stored verbatim)"
    )
    payload: dict[str, Any] = Field(default_factory=dict, description="Event payload")

    # Optional SDK-provided fields (NEVER TRUSTED for authority)
    event_hash: str | None = Field(None, description="SDK hash (logged, never trusted)")
    prev_event_hash: str | None = Field(
        None, description="SDK prev_hash (logged, never trusted)"
    )


# --- Batch Ingestion Request ---


class IngestBatchRequest(BaseModel):
    """
    Unified batch ingestion request.

    INVARIANT: seal=true is only honored if last event is SESSION_END.
    """

    session_id: str = Field(..., description="Session UUID string")
    events: list[RawEventCreate] = Field(
        ..., min_length=1, description="Events to ingest"
    )
    seal: bool = Field(
        False, description="Request sealing (requires SESSION_END as last event)"
    )

    @field_validator("events")
    @classmethod
    def events_must_not_be_empty(cls, v: list[RawEventCreate]) -> list[RawEventCreate]:
        if not v:
            raise ValueError("events must not be empty")
        return v


# --- Ingestion Response ---


class IngestionResult(BaseModel):
    """Successful ingestion response"""

    status: str = Field("success", description="Always 'success' for 201")
    accepted_count: int = Field(..., description="Number of events accepted")
    final_hash: str = Field(..., description="Final event hash after batch")
    chain_authority: str = Field(
        "SERVER", description="Always SERVER for ingested events"
    )

    # Seal metadata (only present if seal=true was honored)
    sealed: bool = Field(False, description="Whether session was sealed")
    seal_timestamp: str | None = Field(None, description="ISO 8601 seal timestamp")
    session_digest: str | None = Field(None, description="Session digest hash")
    evidence_class: str | None = Field(None, description="Evidence classification")


# --- Rejection Response ---


class RejectionResponse(BaseModel):
    """
    Error response for rejected batches.

    HTTP 409: State conflicts (sealed, sequence issues)
    HTTP 400: Bad input (malformed, invalid seal request)
    """

    status: str = Field("rejected", description="Always 'rejected'")
    code: RejectionCode = Field(..., description="Machine-readable rejection code")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, Any] | None = Field(None, description="Additional context")


# --- Session Start (legacy compatibility) ---


class SessionStartRequest(BaseModel):
    """Request to start a new session"""

    session_id: str | None = Field(None, description="Optional UUID from SDK")
    authority: AuthorityType = Field(AuthorityType.SERVER, description="Authority type")
    agent_name: str | None = Field(None, description="Agent identifier")
    user_id: int | None = Field(None, description="User ID (legacy)")


class SessionStartResponse(BaseModel):
    """Response from session creation"""

    session_id: str = Field(..., description="Session UUID")
    authority: str = Field(..., description="Authority type")
    status: str = Field(..., description="Session status")
    ingestion_service_id: str | None = Field(
        None, description="Service ID for server authority"
    )


# --- Legacy Event Batch (backward compatibility) ---


class EventBatch(BaseModel):
    """Batch of events to append to session (legacy API)"""

    session_id: str = Field(..., description="Session UUID")
    events: list[dict[str, Any]] = Field(..., description="List of event dictionaries")


class EventBatchResponse(BaseModel):
    """Response from event batch ingestion (legacy API)"""

    status: str = Field(..., description="success or error")
    accepted_count: int = Field(..., description="Number of events accepted")
    final_hash: str | None = Field(None, description="Final event hash after batch")
    message: str | None = Field(None, description="Error message if failed")


# --- Legacy Seal Request (backward compatibility) ---


class SealRequest(BaseModel):
    """Request to seal a session (legacy API)"""

    session_id: str = Field(..., description="Session UUID")


class SealResponse(BaseModel):
    """Response from session sealing (legacy API)"""

    status: str = Field(..., description="sealed or already_sealed")
    seal_timestamp: str = Field(..., description="ISO 8601 timestamp")
    session_digest: str = Field(..., description="Final session hash")
    event_count: int = Field(..., description="Total events in session")


# --- Session Metadata ---


class SessionMetadata(BaseModel):
    """Session metadata response"""

    session_id: str
    authority: str
    status: str
    evidence_class: str | None
    started_at: datetime
    sealed_at: datetime | None
    total_drops: int
    event_count: int

    class Config:
        from_attributes = True
