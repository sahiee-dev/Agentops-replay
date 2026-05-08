from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    tool_name = Column(String(50), nullable=True, index=True)
    flags = Column(JSON, nullable=True)  # Was ARRAY(String) — JSON is portable
    sequence_number = Column(Integer, nullable=True)

    # Relationship back to session
    session = relationship("Session", back_populates="events")
