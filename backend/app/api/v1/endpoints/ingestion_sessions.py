"""
ingestion_sessions.py - Ingestion service API endpoints.

Constitutional session management for event ingestion.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session as DBSession
from typing import List
import uuid

from app.database import get_db
from app.ingestion import IngestService, SequenceViolation, AuthorityViolation
from app.schemas.ingestion import (
    SessionStartRequest,
    SessionStartResponse,
    EventBatch,
    EventBatchResponse,
    SealRequest,
    SealResponse,
    SessionMetadata
)
from app.models import Session, EventChain

router = APIRouter()

# Initialize ingestion service
ingest_service = IngestService(service_id="prod-ingest-01")


@router.post("/sessions", response_model=SessionStartResponse, status_code=status.HTTP_201_CREATED)
async def start_session(request: SessionStartRequest):
    """
    Start a new ingestion session for the given authority.
    
    Creates a session and returns its identifying metadata. When the authority equals "server", the returned response includes the ingestion service identifier.
    
    Parameters:
        request (SessionStartRequest): Payload containing session_id, authority, agent_name, and user_id.
    
    Returns:
        SessionStartResponse: Contains session_id, authority, status ("active"), and ingestion_service_id when authority is "server".
    
    Raises:
        HTTPException: Raised with status code 400 if the request is invalid (e.g., duplicate session or invalid fields).
    """
    try:
        session_id = ingest_service.start_session(
            session_id_str=request.session_id,
            authority=request.authority.value,
            agent_name=request.agent_name,
            user_id=request.user_id
        )
        
        return SessionStartResponse(
            session_id=session_id,
            authority=request.authority.value,
            status="active",
            ingestion_service_id=ingest_service.service_id if request.authority.value == "server" else None
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{session_id}/events", response_model=EventBatchResponse)
async def append_events(session_id: str, batch: EventBatch):
    """
    Append a batch of events to an ingestion session.
    
    Parameters:
        session_id (str): Identifier of the session to append events to.
        batch (EventBatch): Payload containing the events to append.
    
    Returns:
        EventBatchResponse: Response containing `status`, `accepted_count`, and `final_hash` when present.
    
    Raises:
        HTTPException: 409 if a sequence violation occurs.
        HTTPException: 400 if the request is invalid.
        HTTPException: 500 for unexpected internal errors.
    """
    try:
        result = ingest_service.append_events(
            session_id=session_id,
            events=batch.events
        )
        
        return EventBatchResponse(
            status=result["status"],
            accepted_count=result["accepted_count"],
            final_hash=result.get("final_hash")
        )
    except SequenceViolation as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Sequence violation: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Log exception server-side for debugging
        import logging
        logging.getLogger(__name__).exception("Append events error for session %s", session_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/sessions/{session_id}/seal", response_model=SealResponse)
async def seal_session(session_id: str):
    """
    Seal the ingestion session identified by `session_id`, enforcing the CHAIN_SEAL authority gate.
    
    Parameters:
        session_id (str): Identifier of the session to seal (expected UUID string).
    
    Returns:
        SealResponse: Object containing `status`, `seal_timestamp`, `session_digest`, and `event_count`.
    
    Raises:
        HTTPException: 403 if the caller lacks CHAIN_SEAL authority.
        HTTPException: 400 if `session_id` is invalid or sealing cannot proceed due to bad input.
    """
    try:
        result = ingest_service.seal_session(session_id)
        return SealResponse(
            status=result["status"],
            seal_timestamp=result["seal_timestamp"],
            session_digest=result["session_digest"],
            event_count=result["event_count"]
        )
    except AuthorityViolation as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions/{session_id}", response_model=SessionMetadata)
async def get_session(session_id: str, db: DBSession = Depends(get_db)):
    """
    Return metadata for the ingestion session identified by session_id.
    
    @returns SessionMetadata: Contains session_id, authority, status, evidence_class, started_at, sealed_at, total_drops, and event_count.
    @raises HTTPException: 400 if session_id is not a valid UUID string.
    @raises HTTPException: 404 if no session exists for the given session_id.
    """
    try:
        session = db.query(Session).filter(
            Session.session_id_str == uuid.UUID(session_id)
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        event_count = db.query(EventChain).filter(EventChain.session_id == session.id).count()
        
        return SessionMetadata(
            session_id=str(session.session_id_str),
            authority=session.chain_authority.value,
            status=session.status.value,
            evidence_class=session.evidence_class,
            started_at=session.started_at,
            sealed_at=session.sealed_at,
            total_drops=session.total_drops,
            event_count=event_count
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")