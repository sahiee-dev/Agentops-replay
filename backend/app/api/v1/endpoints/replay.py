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
from typing import Union, List, Dict, Any, Optional

from app.database import get_db
from app.models.session import Session as SessionModel
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


def _get_event_dicts(db: Session, session_id: int) -> List[Dict[str, Any]]:
    """
    Builds ordered event dictionaries from authoritative EventChain rows for a session.
    
    Each returned dictionary represents a single EventChain row and contains canonical, replay-ready fields.
    
    Parameters:
        session_id (int): Primary key of the session whose EventChain rows will be read.
    
    Returns:
        List[dict]: Ordered (ascending by sequence_number) list of event dictionaries. Each dictionary contains:
            - `event_id` (str): UUID string of the event.
            - `sequence_number` (int): Monotonic sequence number within the session.
            - `event_type` (str): Event type name.
            - `timestamp` (str|None): ISO 8601 wall-clock timestamp or `None` if absent.
            - `timestamp_wall` (str|None): ISO 8601 wall-clock timestamp (same as `timestamp`) or `None`.
            - `timestamp_monotonic` (float|int|None): Monotonic timestamp value, if present.
            - `payload` (str): Canonical JSON string of the event payload (authoritative).
            - `payload_canonical` (str): Canonical JSON string of the event payload (same as `payload`).
            - `event_hash` (str): Hex/string representation of the event's hash.
            - `prev_event_hash` (str|None): Hash of the previous event in the chain or `None`.
    """
    event_chains = db.query(EventChain).filter(
        EventChain.session_id == session_id
    ).order_by(
        EventChain.sequence_number.asc()
    ).all()
    
    return [
        {
            "event_id": str(e.event_id),
            "sequence_number": e.sequence_number,
            "event_type": e.event_type,
            "timestamp": e.timestamp_wall.isoformat() if e.timestamp_wall else None,
            "timestamp_wall": e.timestamp_wall.isoformat() if e.timestamp_wall else None,
            "timestamp_monotonic": e.timestamp_monotonic,
            "payload": e.payload_canonical,  # AUTHORITATIVE: canonical JSON string
            "payload_canonical": e.payload_canonical,
            "event_hash": e.event_hash,
            "prev_event_hash": e.prev_event_hash,
        }
        for e in event_chains
    ]


def _get_seal_dict(db: Session, session_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve the chain seal information for a session if a CHAIN_SEAL event exists.
    
    Returns:
        dict: A dictionary with keys:
            - `session_digest` (str | None): Digest value from the seal payload, or `None` if missing.
            - `sealed_at` (str | None): ISO 8601 string of the seal's wall-clock timestamp, or `None` if not available.
        None: If no CHAIN_SEAL event is found for the given session.
    """
    chain_seal = db.query(EventChain).filter(
        EventChain.session_id == session_id,
        EventChain.event_type == "CHAIN_SEAL"
    ).first()
    
    if chain_seal:
        payload = chain_seal.payload_jsonb or {}
        return {
            "session_digest": payload.get("session_digest"),
            "sealed_at": chain_seal.timestamp_wall.isoformat() if chain_seal.timestamp_wall else None
        }
    
    return None


@router.get("/")
def replay_overview():
    """
    Return basic health and constraint information for the replay service.
    
    Returns:
        dict: A mapping containing:
            - service (str): Service name.
            - status (str): Availability status.
            - version (str): Service version string.
            - constraints (List[str]): Replay constraints (e.g., "READ_ONLY", "VERIFIED_FIRST", "NO_INFERENCE", "DETERMINISTIC").
    """
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
    Retrieve the fully verified replay for a session.
    
    Performs full verification of the session's event chain and, if verification succeeds, returns the complete replay (frames, warnings, metadata). If verification fails, returns a ReplayFailureSchema that contains only verification failure information and no frames or partial data.
    
    Parameters:
        session_id (int): Database primary key of the session to retrieve.
    
    Returns:
        ReplayResponseSchema: The assembled replay when verification is successful.
        ReplayFailureSchema: A failure schema with `verification_status` set to INVALID, `error_code`, and `error_message` when verification fails.
    
    Raises:
        HTTPException: 404 if the session does not exist.
    """
    # Check if session exists
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get all events from EventChain (authoritative)
    event_dicts = _get_event_dicts(db, session_id)
    
    # Get chain seal
    seal_dict = _get_seal_dict(db, session_id)
    
    # Use session.session_id_str (UUID string)
    session_id_str = session.session_id_str
    
    # Load and verify session
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
    Verify a recording session and return verification metadata.
    
    Validates the session exists, performs full chain verification using authoritative EventChain data and any chain seal, and reports verification results without returning full replay frames.
    
    Parameters:
        session_id (int): Database primary key of the session to verify.
    
    Returns:
        VerificationResponseSchema: If verification fails, contains `verification_status` set to INVALID and `error_code`/`error_message` with failure details. If verification succeeds, contains `verification_status` set to VALID and fields `evidence_class`, `seal_present`, `event_count`, and `warning_count`.
    """
    # Check if session exists
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Use same full event serialization as get_replay
    event_dicts = _get_event_dicts(db, session_id)
    
    # Get chain seal
    seal_dict = _get_seal_dict(db, session_id)
    
    # Use session.session_id_str (UUID string)
    session_id_str = session.session_id_str
    
    # Verify
    verified_chain, failure = load_verified_session(session_id_str, event_dicts, seal_dict)
    
    if failure:
        return VerificationResponseSchema(
            session_id=session_id_str,
            verification_status=VerificationStatusSchema.INVALID,
            error_code=failure.error_code,
            error_message=failure.error_message
        )
    
    # Build replay to count warnings (uses timestamp for anomaly detection)
    replay = build_replay(verified_chain)
    
    return VerificationResponseSchema(
        session_id=session_id_str,
        verification_status=VerificationStatusSchema.VALID,
        evidence_class=verified_chain.evidence_class,
        seal_present=verified_chain.seal_present,
        event_count=len(event_dicts),
        warning_count=len(replay.warnings)
    )


@router.get("/session/{session_id}/frame/{sequence}", response_model=FrameResponseSchema)
def get_frame(session_id: int, sequence: int, db: Session = Depends(get_db)):
    """
    Retrieve a single replay frame by sequence after verifying the session's event chain.
    
    This endpoint enforces full verification of the session's authoritative EventChain and applies replay gap logic; it will not return partial or unverified data.
    
    Parameters:
    	session_id (int): Database primary key of the session.
    	sequence (int): Sequence number of the requested frame.
    
    Returns:
    	FrameResponseSchema: Object containing `session_id`, `requested_sequence`, and the serialized frame.
    
    Raises:
    	HTTPException(404): If the session does not exist.
    	HTTPException(422): If chain verification fails.
    """
    # Get full replay first (enforces verification)
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Use same full event serialization as get_replay
    event_dicts = _get_event_dicts(db, session_id)
    
    # Get chain seal
    seal_dict = _get_seal_dict(db, session_id)
    
    # Use session.session_id_str (UUID string)
    session_id_str = session.session_id_str
    
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
    """
    Create a ReplayResponseSchema from an internal ReplayResult.
    
    Parameters:
        replay (ReplayResult): Internal replay result containing verified session metadata, frames, warnings, counts, timestamps, and final hash.
    
    Returns:
        replay_response (ReplayResponseSchema): API-ready representation of the replay including session_id, evidence_class, seal_present, verification_status, frames, warnings, event_count, total_drops, first_timestamp, last_timestamp, and final_hash.
    """
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
    """
    Convert an internal ReplayFrame into a ReplayFrameSchema suitable for API responses.
    
    Parameters:
        frame: Internal frame object with attributes used to populate the schema
            (e.g., frame_type, position, sequence_number, timestamp, event_type,
            payload, event_hash, gap_start, gap_end, dropped_count, drop_reason,
            redaction_hash, redacted_fields).
    
    Returns:
        ReplayFrameSchema: API-ready representation of the provided frame.
    
    Raises:
        ValueError: If `frame.payload` is a `dict`; payloads must already be canonical JSON strings.
    """
    from app.replay.frames import FrameType
    import json
    
    # Payload MUST be a canonical JSON string, not a dict
    # Raise explicit error if dict is passed - this indicates a bug upstream
    payload_str = None
    if frame.payload is not None:
        if isinstance(frame.payload, dict):
            raise ValueError(
                f"Frame payload must be a canonical JSON string, not dict. "
                f"Frame position={frame.position}, type={frame.frame_type}. "
                f"This indicates a bug in event processing - payloads should be "
                f"canonicalized before reaching _frame_to_schema."
            )
        elif isinstance(frame.payload, str):
            payload_str = frame.payload
        else:
            # Coerce other types to canonical JSON string
            payload_str = json.dumps(frame.payload, separators=(',', ':'), sort_keys=True, ensure_ascii=False)
    
    return ReplayFrameSchema(
        frame_type=FrameTypeSchema(frame.frame_type.value),
        position=frame.position,
        sequence_number=frame.sequence_number,
        timestamp=frame.timestamp,
        event_type=frame.event_type,
        payload=payload_str,
        event_hash=frame.event_hash,
        gap_start=frame.gap_start,
        gap_end=frame.gap_end,
        dropped_count=frame.dropped_count,
        drop_reason=frame.drop_reason,
        redaction_hash=frame.redaction_hash,
        redacted_fields=frame.redacted_fields
    )