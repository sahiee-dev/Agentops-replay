"""
verify.py - Session verification API endpoint.

CONSTITUTIONAL REQUIREMENT: Verification operates on RFC 8785 canonical exports only.
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session as DBSession
import sys
import os
import uuid
import json
import tempfile

# Add verifier to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../verifier'))
import verifier_core

from app.database import get_db
from app.models import Session, EventChain, ChainSeal

router = APIRouter()


@router.post("/verify")
async def verify_session_api(session_id: str, db: DBSession = Depends(get_db)):
    """
    Verify a session's integrity by exporting its events to RFC 8785 canonical form and running the verifier.
    
    Parameters:
        session_id (str): UUID string of the session to verify.
    
    Returns:
        dict: Verification summary containing:
            - session_id (str): The verified session UUID string.
            - status (str|None): Verification status reported by the verifier.
            - evidence_class (str|None): Evidence classification assigned by the verifier.
            - sealed (bool|None): Whether the session was sealed.
            - complete (bool|None): Whether the event chain is complete.
            - authority (str|None): Authority identifier used for verification.
            - total_drops (int): Number of dropped events (defaults to 0).
            - violations (list): List of verifier-reported violations (defaults to []).
            - replay_fingerprint (str|None): Replay fingerprint if produced.
            - event_count (int|None): Number of events processed by the verifier.
    
    Raises:
        HTTPException: 404 if the session_id does not exist.
        HTTPException: 400 if the session has no events or if input is invalid (ValueError).
        HTTPException: 500 for unexpected verification errors.
    """
    try:
        # 1. Get session
        session = db.query(Session).filter(
            Session.session_id_str == uuid.UUID(session_id)
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        # 2. Export to canonical form
        events = db.query(EventChain).filter(
            EventChain.session_id == session.id
        ).order_by(EventChain.sequence_number).all()
        
        if not events:
            raise HTTPException(status_code=400, detail="Cannot verify empty session")
        
        # 3. Convert to canonical event list
        canonical_events = []
        for event in events:
            canonical_event = {
                "event_id": str(event.event_id),
                "session_id": session_id,
                "sequence_number": int(event.sequence_number),
                "timestamp_wall": event.timestamp_wall.isoformat().replace('+00:00', 'Z'),
                "timestamp_monotonic": int(event.timestamp_monotonic),
                "event_type": event.event_type,
                "source_sdk_ver": event.source_sdk_ver,
                "schema_ver": event.schema_ver,
                "payload_hash": event.payload_hash,
                "prev_event_hash": event.prev_event_hash,
                "event_hash": event.event_hash,
                "payload": event.payload_jsonb,
                "chain_authority": session.chain_authority.value
            }
            canonical_events.append(canonical_event)
        
        # 4. Run verifier on canonical form
        policy = {"reject_local_authority": False}
        
        # Import verify_session from agentops_verify
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../verifier'))
        from agentops_verify import verify_session
        
        result = verify_session(canonical_events, policy)
        
        #  5. Update session evidence class
        session.evidence_class = result.get("evidence_class")
        db.commit()
        
        # 6. Return verification result
        return {
            "session_id": session_id,
            "status": result.get("status"),
            "evidence_class": result.get("evidence_class"),
            "sealed": result.get("sealed"),
            "complete": result.get("complete"),
            "authority": result.get("authority"),
            "total_drops": result.get("total_drops", 0),
            "violations": result.get("violations", []),
            "replay_fingerprint": result.get("replay_fingerprint"),
            "event_count": result.get("event_count")
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification error: {str(e)}")