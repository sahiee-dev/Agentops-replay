# backend/app/api/v1/endpoints/compliance.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.event import Event
from app.models.session import Session as SessionModel

router = APIRouter()

@router.get("/")
def compliance_overview():
    return {"message": "Compliance service available"}


@router.get("/{session_id}")
def compliance_report(session_id: int, db: Session = Depends(get_db)):
    # Check if session exists
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get all events for this session
    events = db.query(Event).filter(Event.session_id == session_id).all()
    
    # Basic compliance checks
    flagged_events = [e for e in events if e.flags and len(e.flags) > 0]
    total_events = len(events)
    flagged_count = len(flagged_events)
    
    # Calculate compliance score
    compliance_score = (total_events - flagged_count) / total_events * 100 if total_events > 0 else 100
    
    return {
        "session_id": session_id,
        "total_events": total_events,
        "flagged_events": flagged_count,
        "compliance_score": round(compliance_score, 2),
        "status": "passed" if flagged_count == 0 else "failed",
        "flagged_event_details": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "flags": e.flags,
                "timestamp": e.timestamp
            } for e in flagged_events
        ]
    }


@router.get("/sessions/flagged")
def list_flagged_sessions(db: Session = Depends(get_db)):
    # Find sessions with flagged events
    flagged_sessions = db.query(SessionModel).join(Event).filter(
        Event.flags.isnot(None)
    ).distinct().all()
    
    return {
        "flagged_sessions": [
            {
                "id": s.id,
                "user_id": s.user_id,
                "agent_name": s.agent_name,
                "status": s.status,
                "started_at": s.started_at
            } for s in flagged_sessions
        ]
    }
