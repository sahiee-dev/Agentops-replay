from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models.event import Event
from app.schemas.event import EventCreate, EventRead

router = APIRouter()

@router.get("/", response_model=List[EventRead])
def list_events(
    session_id: Optional[int] = Query(None),
    event_type: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Event)
    
    if session_id:
        query = query.filter(Event.session_id == session_id)
    if event_type:
        query = query.filter(Event.event_type == event_type)
    
    return query.order_by(Event.timestamp.desc()).all()

@router.post("/", response_model=EventRead)
def create_event(event: EventCreate, db: Session = Depends(get_db)):
    # Create event with current timestamp
    db_event = Event(
        session_id=event.session_id,
        event_type=event.event_type,
        tool_name=event.tool_name,
        flags=event.flags,
        sequence_number=event.sequence_number,
        timestamp=datetime.utcnow()  # Set timestamp automatically
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event

@router.get("/{event_id}", response_model=EventRead)
def get_event(event_id: int, db: Session = Depends(get_db)):
    db_event = db.query(Event).filter(Event.id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    return db_event
