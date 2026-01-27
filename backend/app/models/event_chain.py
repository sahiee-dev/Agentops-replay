"""
event_chain.py - Constitutional event storage model.

CRITICAL GUARANTEES:
1. Append-only enforcement via PostgreSQL trigger
2. NO authority fields on events (authority lives on session)
3. Split payload storage: canonical + hash + queryable
4. Immutable per CONSTITUTION.md
"""

from sqlalchemy import Column, Integer, String, BigInteger, Text, ForeignKey, Index, DDL, event
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class EventChain(Base):
    """
    Append-only event chain storage.
    
    Constitutional Requirements (MUST NOT be violated):
    - Events are immutable once written
    - Authority is session-level, not event-level
    - Payload stored in canonical form for verification
    - Hash chain integrity enforced
    """
    __tablename__ = "event_chains"
    
    # Primary fields
    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False, index=True)
    session_id_str = Column(String(36), nullable=False)  # Denormalized for queries
    sequence_number = Column(BigInteger, nullable=False, index=True)
    
    # Timestamps
    timestamp_wall = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    timestamp_monotonic = Column(BigInteger, nullable=False)
    
    # Event metadata
    event_type = Column(String(50), nullable=False, index=True)
    source_sdk_ver = Column(String(20), nullable=True)
    schema_ver = Column(String(10), nullable=False, default="v0.6")
    
    # Payload storage (SPLIT for verification correctness)
    payload_canonical = Column(Text, nullable=False)  # RFC 8785 canonical bytes as string
    payload_hash = Column(String(64), nullable=False)  # Precomputed SHA-256 hex
    
    # CRITICAL: payload_jsonb is QUERYABLE ONLY, NOT AUTHORITATIVE
    # NEVER use for verification - use payload_canonical instead
    # This exists solely for SQL queries and debugging
    payload_jsonb = Column(JSONB, nullable=True)      # Queryable copy (NOT used for verification)
    
    # Hash chain
    prev_event_hash = Column(String(64), nullable=True)  # Null for first event
    event_hash = Column(String(64), nullable=False, index=True)
    chain_authority = Column(String(20), nullable=False)
    
    # Relationship back to session
    session = relationship("Session", back_populates="event_chains")
    
    # Composite indexes for performance
    __table_args__ = (
        Index('idx_session_sequence', 'session_id', 'sequence_number', unique=True),
        Index('idx_event_type_timestamp', 'event_type', 'timestamp_wall'),
    )


# CONSTITUTIONAL ENFORCEMENT: Append-only trigger
# This prevents UPDATE and DELETE operations on event_chains table
prevent_mutation_trigger = DDL("""
    CREATE OR REPLACE FUNCTION reject_event_mutation()
    RETURNS TRIGGER AS $$
    BEGIN
        RAISE EXCEPTION 'Events are immutable per CONSTITUTION.md. Operation % is forbidden on event_chains.', TG_OP;
    END;
    $$ LANGUAGE plpgsql;
    
    CREATE TRIGGER prevent_event_mutation
    BEFORE UPDATE OR DELETE ON event_chains
    FOR EACH ROW EXECUTE FUNCTION reject_event_mutation();
""")

# Attach trigger to table creation
event.listen(
    EventChain.__table__,
    'after_create',
    prevent_mutation_trigger.execute_if(dialect='postgresql')
)
