from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from app.database import Base

class EventChain(Base):
    __tablename__ = "event_chains"

    event_id = Column(String, primary_key=True) # UUID string
    session_id = Column(String(36), ForeignKey("sessions.session_id_str"), nullable=False, index=True)
    sequence_number = Column(Integer, nullable=False)
    timestamp_wall = Column(DateTime, nullable=False)
    timestamp_monotonic = Column(Float, nullable=True)
    event_type = Column(String, nullable=False)
    source_sdk_ver = Column(String, nullable=True)
    schema_ver = Column(String, nullable=True)
    payload_canonical = Column(Text, nullable=False)
    payload_hash = Column(String, nullable=False)
    prev_event_hash = Column(String, nullable=True)
    event_hash = Column(String, nullable=False)
    chain_authority = Column(String, nullable=False)
