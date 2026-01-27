"""
chain_seal.py - CHAIN_SEAL metadata model with authority enforcement.

CRITICAL: Seal can ONLY be created for server authority sessions.
Seal MUST be idempotent (second seal returns original).
"""

from sqlalchemy import Column, String, BigInteger, Integer, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import relationship
from app.database import Base


class ChainSeal(Base):
    """
    CHAIN_SEAL metadata for server-sealed sessions.
    
    Authority Gate: Only server authority sessions can have a seal.
    Idempotency: Unique constraint on session_id prevents duplicate seals.
    """
    __tablename__ = "chain_seals"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False, unique=True, index=True)
    
    # Required metadata per EVENT_LOG_SPEC.md v0.6
    ingestion_service_id = Column(String(100), nullable=False)  # e.g., "prod-ingest-01"
    seal_timestamp = Column(TIMESTAMP(timezone=True), nullable=False)
    session_digest = Column(String(64), nullable=False)  # Final hash chain digest
    
    # Seal statistics
    final_event_hash = Column(String(64), nullable=False)
    event_count = Column(Integer, nullable=False)
    
    # Relationship
    session = relationship("Session", back_populates="chain_seal", uselist=False)
    
    __table_args__ = (
        CheckConstraint('event_count > 0', name='seal_event_count_positive'),
    )
