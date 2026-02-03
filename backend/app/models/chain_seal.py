from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from app.database import Base

class ChainSeal(Base):
    __tablename__ = "chain_seals"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False, unique=True)
    ingestion_service_id = Column(String, nullable=False)
    seal_timestamp = Column(DateTime, nullable=False)
    session_digest = Column(String, nullable=False)
    final_event_hash = Column(String, nullable=False)
    event_count = Column(Integer, nullable=False)
