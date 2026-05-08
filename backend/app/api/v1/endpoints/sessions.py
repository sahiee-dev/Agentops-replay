import json
import hashlib

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

try:
    from backend.app.db.session import get_db
except ImportError:
    try:
        from app.db.session import get_db
    except ImportError:
        get_db = None

try:
    from jcs import canonicalize as jcs_canonicalize
except ImportError:
    jcs_canonicalize = None

router = APIRouter()

@router.get("/v1/sessions/{session_id}/export")
async def export_session(
    session_id: str,
    db = Depends(get_db if get_db else lambda: None),
):
    """
    Export all events for a session as JSONL (application/x-ndjson).

    Events are ordered by sequence_number ascending.
    Each line is a JSON object with the 7-field envelope:
      seq, event_type, session_id, timestamp, payload, prev_hash, event_hash

    If the session is sealed, a CHAIN_SEAL event is appended as the final line.

    Returns 404 if the session does not exist.
    """
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        from app.models import EventChain, Session as SessionModel, ChainSeal
    except ImportError:
        from backend.app.models import EventChain, Session as SessionModel, ChainSeal  # type: ignore[no-redef]

    # Verify session exists
    db_session = db.query(SessionModel).filter(
        SessionModel.session_id_str == session_id
    ).first()
    if db_session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    # Query event_chains ordered by sequence_number
    events = (
        db.query(EventChain)
        .filter(EventChain.session_id == db_session.session_id_str)
        .order_by(EventChain.sequence_number)
        .all()
    )

    # Check for seal
    seal = db.query(ChainSeal).filter(
        ChainSeal.session_id == db_session.id
    ).first()

    lines: list[str] = []
    
    total_drops = db_session.total_drops or 0
    evidence_class = (
        "AUTHORITATIVE_EVIDENCE" if total_drops == 0
        else "PARTIAL_AUTHORITATIVE_EVIDENCE"
    )

    for event in events:
        payload = {}
        if event.payload_canonical:
            try:
                payload = json.loads(event.payload_canonical)
            except (json.JSONDecodeError, TypeError):
                payload = {}

        row = {
            "seq": event.sequence_number,
            "event_type": event.event_type,
            "session_id": session_id,
            "timestamp": event.timestamp_wall.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z" if event.timestamp_wall else "",
            "payload": payload,
            "prev_hash": event.prev_event_hash or ("0" * 64),
            "event_hash": event.event_hash,
        }
        lines.append(json.dumps(row))

    if seal is not None:
        seal_row = {
            "seq": (events[-1].sequence_number + 1) if events else 1,
            "event_type": "CHAIN_SEAL",
            "session_id": session_id,
            "timestamp": seal.seal_timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z" if seal.seal_timestamp else "",
            "payload": {
                "session_digest": seal.session_digest,
                "final_event_hash": seal.final_event_hash,
                "event_count": seal.event_count,
                "ingestion_service_id": seal.ingestion_service_id,
                "evidence_class": evidence_class,
            },
            "prev_hash": events[-1].event_hash if events else ("0" * 64),
        }
        if jcs_canonicalize is not None:
            canonical_bytes = jcs_canonicalize(seal_row)
            seal_row["event_hash"] = hashlib.sha256(canonical_bytes).hexdigest()
        else:
            seal_row["event_hash"] = seal.session_digest
            
        lines.append(json.dumps(seal_row))

    body = "\n".join(lines) + "\n" if lines else ""

    return Response(
        content=body,
        media_type="application/x-ndjson",
    )
