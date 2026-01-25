"""
ingestion.py - Pydantic schemas for ingestion API.

Request/response models for session creation, event batching, and sealing.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class AuthorityType(str, Enum):
    """Authority types for sessions"""
    SERVER = "server"
    SDK = "sdk"


# --- Session Start ---

class SessionStartRequest(BaseModel):
    """Request to start a new session"""
    session_id: Optional[str] = Field(None, description="Optional UUID from SDK")
    authority: AuthorityType = Field(AuthorityType.SERVER, description="Authority type")
    agent_name: Optional[str] = Field(None, description="Agent identifier")
    user_id: Optional[int] = Field(None, description="User ID (legacy)")


class SessionStartResponse(BaseModel):
    """Response from session creation"""
    session_id: str = Field(..., description="Session UUID")
    authority: str = Field(..., description="Authority type")
    status: str = Field(..., description="Session status")
    ingestion_service_id: Optional[str] = Field(None, description="Service ID for server authority")


# --- Event Batch ---

class EventBatch(BaseModel):
    """Batch of events to append to session"""
    session_id: str = Field(..., description="Session UUID")
    events: List[Dict[str, Any]] = Field(..., description="List of event dictionaries")


class EventBatchResponse(BaseModel):
    """Response from event batch ingestion"""
    status: str = Field(..., description="success or error")
    accepted_count: int = Field(..., description="Number of events accepted")
    final_hash: Optional[str] = Field(None, description="Final event hash after batch")
    message: Optional[str] = Field(None, description="Error message if failed")


# --- Seal Request ---

class SealRequest(BaseModel):
    """Request to seal a session"""
    session_id: str = Field(..., description="Session UUID")


class SealResponse(BaseModel):
    """Response from session sealing"""
    status: str = Field(..., description="sealed or already_sealed")
    seal_timestamp: str = Field(..., description="ISO 8601 timestamp")
    session_digest: str = Field(..., description="Final session hash")
    event_count: int = Field(..., description="Total events in session")


# --- Session Retrieval ---

class SessionMetadata(BaseModel):
    """Session metadata response"""
    session_id: str
    authority: str
    status: str
    evidence_class: Optional[str]
    started_at: datetime
    sealed_at: Optional[datetime]
    total_drops: int
    event_count: int
    
    class Config:
        from_attributes = True
