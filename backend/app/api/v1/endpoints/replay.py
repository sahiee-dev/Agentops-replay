# backend/app/api/v1/endpoints/replay.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.session import Session as SessionModel
from app.models.event import Event

router = APIRouter()

@router.get("/")
def replay_overview():
    return {"message": "Replay service available"}


@router.get("/{session_id}")
def replay_session(session_id: int, db: Session = Depends(get_db)):
    # Check if session exists
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get all events for this session, ordered by sequence and timestamp
    events = db.query(Event).filter(
        Event.session_id == session_id
    ).order_by(
        Event.sequence_number.asc(),
        Event.timestamp.asc()
    ).all()

    return {
        "session": {
            "id": session.id,
            "user_id": session.user_id,
            "agent_name": session.agent_name,
            "status": session.status,
            "started_at": session.started_at
        },
        "events": events,
        "event_count": len(events)
    }
