# backend/app/api/v1/endpoints/replay.py
"""
Replay API endpoints.

CONSTITUTIONAL CONSTRAINTS:
- Read-only access to verified chains
- No inference or interpolation
- Explicit marking of incomplete evidence
- Deterministic playback

All endpoints go through full verification.
No fast paths that skip replay logic.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Union

from app.database import get_db
from app.models.session import Session as SessionModel
from app.models.event import Event
from app.models.event_chain import EventChain
from app.replay.engine import (
    load_verified_session,
    build_replay,
    get_frame_at_sequence,
    ReplayResult,
    ReplayFailure
)
from app.replay.frames import VerificationStatus
from app.schemas.replay_v2 import (
    ReplayResponseSchema,
    ReplayFailureSchema,
    VerificationResponseSchema,
    FrameResponseSchema,
    ReplayFrameSchema,
    FrameTypeSchema,
    VerificationStatusSchema,
    WarningSeveritySchema,
    ReplayWarningSchema
)

router = APIRouter()


@router.get("/")
def replay_overview():
    """Health check for replay service."""
    return {
        "service": "replay",
        "status": "available",
        "version": "2.0",
        "constraints": [
            "READ_ONLY",
            "VERIFIED_FIRST",
            "NO_INFERENCE",
            "DETERMINISTIC"
        ]
    }


@router.get(
    "/session/{session_id}",
    response_model=Union[ReplayResponseSchema, ReplayFailureSchema]
)
def get_replay(session_id: int, db: Session = Depends(get_db)):
    """
    Get full replay for a session.
    
    Response includes:
    - evidence_class
    - verification_status (VALID/INVALID)
    - frames (in sequence order, with GAPs for missing sequences)
    - warnings (all detected issues)
    
    INVARIANT: If verification fails, returns ReplayFailureSchema
    with NO frames, NO partial data, NO metadata.
    """
    # Check if session exists
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get all events for this session, ordered by sequence
    events = db.query(Event).filter(
        Event.session_id == session_id
    ).order_by(
        Event.sequence_number.asc()
    ).all()
    
    # Convert to dicts for replay engine
    event_dicts = [
        {
            "event_id": str(e.event_id),
            "sequence_number": e.sequence_number,
            "event_type": e.event_type,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "payload": e.payload,
            "event_hash": e.event_hash,
            "prev_event_hash": e.prev_event_hash,
        }
        for e in events
    ]
    
    # Get chain seal if exists
    chain_seal = db.query(EventChain).filter(
        EventChain.session_id == session_id
    ).first()
    
    seal_dict = None
    if chain_seal and chain_seal.sealed:
        seal_dict = {
            "session_digest": chain_seal.session_digest,
            "sealed_at": chain_seal.sealed_at.isoformat() if chain_seal.sealed_at else None
        }
    
    # Load and verify session
    session_id_str = str(session.session_id) if hasattr(session, 'session_id') else str(session.id)
    verified_chain, failure = load_verified_session(session_id_str, event_dicts, seal_dict)
    
    if failure:
        # CRITICAL: Return explicit failure, no partial data
        return ReplayFailureSchema(
            session_id=session_id_str,
            verification_status=VerificationStatusSchema.INVALID,
            error_code=failure.error_code,
            error_message=failure.error_message
        )
    
    # Build replay from verified chain
    replay = build_replay(verified_chain)
    
    # Convert to response schema
    return _replay_to_response(replay)


@router.get("/session/{session_id}/verify", response_model=VerificationResponseSchema)
def verify_session(session_id: int, db: Session = Depends(get_db)):
    """
    Verify a session before replay.
    
    Returns verification result without full replay data.
    Use this to check if replay is available before fetching.
    """
    # Check if session exists
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get events
    events = db.query(Event).filter(
        Event.session_id == session_id
    ).order_by(
        Event.sequence_number.asc()
    ).all()
    
    event_dicts = [
        {
            "event_id": str(e.event_id),
            "sequence_number": e.sequence_number,
            "event_type": e.event_type,
            "event_hash": e.event_hash,
        }
        for e in events
    ]
    
    # Get chain seal
    chain_seal = db.query(EventChain).filter(
        EventChain.session_id == session_id
    ).first()
    
    seal_dict = None
    if chain_seal and chain_seal.sealed:
        seal_dict = {"session_digest": chain_seal.session_digest}
    
    # Verify
    session_id_str = str(session.session_id) if hasattr(session, 'session_id') else str(session.id)
    verified_chain, failure = load_verified_session(session_id_str, event_dicts, seal_dict)
    
    if failure:
        return VerificationResponseSchema(
            session_id=session_id_str,
            verification_status=VerificationStatusSchema.INVALID,
            error_code=failure.error_code,
            error_message=failure.error_message
        )
    
    # Build replay to count warnings
    replay = build_replay(verified_chain)
    
    return VerificationResponseSchema(
        session_id=session_id_str,
        verification_status=VerificationStatusSchema.VALID,
        evidence_class=verified_chain.evidence_class,
        seal_present=verified_chain.seal_present,
        event_count=len(events),
        warning_count=len(replay.warnings)
    )


@router.get("/session/{session_id}/frame/{sequence}", response_model=FrameResponseSchema)
def get_frame(session_id: int, sequence: int, db: Session = Depends(get_db)):
    """
    Get a single frame by sequence number.
    
    CONSTRAINT: This endpoint:
    - MUST go through full verification
    - MUST NOT bypass gap logic
    - MUST return GAP frame if missing
    - Is NOT a "fast path" that skips replay logic
    """
    # Get full replay first (enforces verification)
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    events = db.query(Event).filter(
        Event.session_id == session_id
    ).order_by(
        Event.sequence_number.asc()
    ).all()
    
    event_dicts = [
        {
            "event_id": str(e.event_id),
            "sequence_number": e.sequence_number,
            "event_type": e.event_type,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "payload": e.payload,
            "event_hash": e.event_hash,
            "prev_event_hash": e.prev_event_hash,
        }
        for e in events
    ]
    
    chain_seal = db.query(EventChain).filter(
        EventChain.session_id == session_id
    ).first()
    
    seal_dict = None
    if chain_seal and chain_seal.sealed:
        seal_dict = {"session_digest": chain_seal.session_digest}
    
    session_id_str = str(session.session_id) if hasattr(session, 'session_id') else str(session.id)
    verified_chain, failure = load_verified_session(session_id_str, event_dicts, seal_dict)
    
    if failure:
        raise HTTPException(
            status_code=422,
            detail=f"Verification failed: {failure.error_code} - {failure.error_message}"
        )
    
    # Build replay and get frame
    replay = build_replay(verified_chain)
    frame = get_frame_at_sequence(replay, sequence)
    
    return FrameResponseSchema(
        session_id=session_id_str,
        requested_sequence=sequence,
        frame=_frame_to_schema(frame)
    )


def _replay_to_response(replay: ReplayResult) -> ReplayResponseSchema:
    """Convert internal ReplayResult to API response schema."""
    return ReplayResponseSchema(
        session_id=replay.session_id,
        evidence_class=replay.evidence_class,
        seal_present=replay.seal_present,
        verification_status=VerificationStatusSchema(replay.verification_status.value),
        frames=[_frame_to_schema(f) for f in replay.frames],
        warnings=[
            ReplayWarningSchema(
                severity=WarningSeveritySchema(w.severity.value),
                code=w.code.value,
                message=w.message,
                frame_position=w.frame_position
            )
            for w in replay.warnings
        ],
        event_count=replay.event_count,
        total_drops=replay.total_drops,
        first_timestamp=replay.first_timestamp,
        last_timestamp=replay.last_timestamp,
        final_hash=replay.final_hash
    )


def _frame_to_schema(frame) -> ReplayFrameSchema:
    """Convert internal ReplayFrame to API response schema."""
    from app.replay.frames import FrameType
    
    return ReplayFrameSchema(
        frame_type=FrameTypeSchema(frame.frame_type.value),
        position=frame.position,
        sequence_number=frame.sequence_number,
        timestamp=frame.timestamp,
        event_type=frame.event_type,
        payload=frame.payload,
        event_hash=frame.event_hash,
        gap_start=frame.gap_start,
        gap_end=frame.gap_end,
        dropped_count=frame.dropped_count,
        drop_reason=frame.drop_reason
    )
