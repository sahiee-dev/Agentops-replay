"""
session.py - Session model with authority boundary enforcement.

CRITICAL: chain_authority is SESSION-LEVEL ONLY.
Authority set at creation, immutable thereafter.
"""

from sqlalchemy import Column, Integer, String, Enum as SQLEnum, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid
import enum


class ChainAuthority(str, enum.Enum):
    """Authority types per EVENT_LOG_SPEC.md v0.6"""
    SERVER = "server"
    SDK = "sdk"


class SessionStatus(str, enum.Enum):
    """Session lifecycle states"""
    ACTIVE = "active"
    SEALED = "sealed"
    FAILED = "failed"


class Session(Base):
    """
    Session model with constitutional authority boundary.
    
    CRITICAL REQUIREMENTS:
    - chain_authority set at creation, immutable
    - Authority is session-level, NOT event-level
    - Evidence class computed via verification gate
    """
    __tablename__ = "sessions"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Session identity (from SDK)
    session_id_str = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True, default=uuid.uuid4)
    
    # AUTHORITY BOUNDARY (Constitutional requirement)
    chain_authority = Column(
        SQLEnum(ChainAuthority, name="chain_authority_enum"),
        nullable=False,
        index=True
    )
    
    # Session state
    status = Column(
        SQLEnum(SessionStatus, name="session_status_enum"),
        nullable=False,
        default=SessionStatus.ACTIVE,
        index=True
    )
    
    # Evidence classification (computed via verification gate)
    evidence_class = Column(String(50), nullable=True, index=True)
    
    # Timestamps
    started_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), index=True)
    sealed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    
    # Failure tracking
    total_drops = Column(Integer, nullable=False, default=0)
    
    # Ingestion service identity (for server authority)
    ingestion_service_id = Column(String(100), nullable=True)
    
    # Legacy fields (for backward compatibility with existing app)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    agent_name = Column(String(100), nullable=True, index=True)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    event_chains = relationship("EventChain", back_populates="session", cascade="all, delete-orphan")
    chain_seal = relationship("ChainSeal", back_populates="session", uselist=False, cascade="all, delete-orphan")
    
    # Legacy relationship (keeping for existing app compatibility)
    events = relationship("Event", back_populates="session", cascade="all, delete-orphan")
    
    __table_args__ = (
        CheckConstraint(
            "chain_authority IN ('server', 'sdk')",
            name="valid_chain_authority"
        ),
        CheckConstraint(
            "total_drops >= 0",
            name="non_negative_drops"
        ),
    )

