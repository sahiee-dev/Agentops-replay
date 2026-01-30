from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.session import Session as SessionModel
from app.schemas.session import SessionCreate, SessionRead

router = APIRouter()

@router.get("/", response_model=list[SessionRead])
def list_sessions(db: Session = Depends(get_db)):
    return db.query(SessionModel).all()

@router.post("/", response_model=SessionRead)
def create_session(session: SessionCreate, db: Session = Depends(get_db)):
    # Explicitly set started_at to current timestamp
    db_session = SessionModel(
        user_id=session.user_id,
        agent_name=session.agent_name,
        status=session.status,
        started_at=datetime.utcnow()  # Explicitly set timestamp
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

@router.get("/{session_id}", response_model=SessionRead)
def get_session(session_id: int, db: Session = Depends(get_db)):
    db_session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")
    return db_session
