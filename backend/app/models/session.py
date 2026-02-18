from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

from sqlalchemy.sql import expression

class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    agent_name = Column(String(100), nullable=True, index=True)
    status = Column(String(50), nullable=True, index=True)
    started_at = Column(DateTime, nullable=False, index=True, server_default=func.now())
    sealed_at = Column(DateTime, nullable=True)
    session_id_str = Column(String(36), unique=True, index=True, nullable=False)
    chain_authority = Column(String(50), nullable=True)
    total_drops = Column(Integer, default=0)
    ingestion_service_id = Column(String(100), nullable=True)

    # Relationships
    user = relationship("User", back_populates="sessions")
    events = relationship("Event", back_populates="session", cascade="all, delete-orphan")
    is_replay = Column(Boolean, default=False, nullable=False, server_default=expression.false())
