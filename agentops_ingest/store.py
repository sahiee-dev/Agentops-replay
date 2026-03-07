"""
agentops_ingest/store.py - Dumb Persistence

Responsibilities:
- Insert immutable rows
- Enforce unique (session_id, sequence_number)
- No updates
- No deletes

Must be replaceable without changing integrity semantics.
"""
import json
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import (
    create_engine, Column, String, Integer, Float, Text, DateTime,
    UniqueConstraint, Index
)
from sqlalchemy.orm import sessionmaker, Session as DBSession
from sqlalchemy.ext.declarative import declarative_base

from .sealer import SealedEvent, ChainState


Base = declarative_base()


class EventRow(Base):
    """Immutable event storage row."""
    __tablename__ = "events"
    
    # Primary Key
    event_id = Column(String(36), primary_key=True)
    
    # Session & Ordering
    session_id = Column(String(36), nullable=False, index=True)
    sequence_number = Column(Integer, nullable=False)
    
    # Timestamps
    timestamp_wall = Column(String(64), nullable=False)
    timestamp_monotonic = Column(Float, nullable=True)
    
    # Event Data
    event_type = Column(String(64), nullable=False)
    payload_jcs = Column(Text, nullable=False)
    payload_hash = Column(String(64), nullable=False)
    
    # Chain Integrity
    prev_event_hash = Column(String(64), nullable=True)
    event_hash = Column(String(64), nullable=False)
    chain_authority = Column(String(64), nullable=False)
    
    # Metadata
    source_sdk_ver = Column(String(32), nullable=True)
    schema_ver = Column(String(16), nullable=True)
    ingested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        UniqueConstraint('session_id', 'sequence_number', name='uq_session_sequence'),
        Index('ix_session_sequence', 'session_id', 'sequence_number'),
    )


class EventStore:
    """
    Append-only event storage.
    
    Invariants:
    - Rows are NEVER updated
    - Rows are NEVER deleted
    - (session_id, sequence_number) is unique
    """
    
    def __init__(self, database_url: str):
        """
        Initialize the EventStore by creating a SQLAlchemy engine, ensuring the schema exists, and preparing a session factory.
        
        Parameters:
            database_url (str): SQLAlchemy database connection URL used to create the engine and bind the sessionmaker.
        """
        self.engine = create_engine(database_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
    
    def insert(self, event: SealedEvent) -> None:
        """
        Persist a sealed event as a new immutable row in the events table.
        
        Parameters:
            event (SealedEvent): The sealed event to persist.
        
        Raises:
            sqlalchemy.exc.IntegrityError: If a row with the same (session_id, sequence_number) already exists.
        """
        db = self.Session()
        try:
            row = EventRow(
                event_id=event.event_id,
                session_id=event.session_id,
                sequence_number=event.sequence_number,
                timestamp_wall=event.timestamp_wall,
                timestamp_monotonic=event.timestamp_monotonic,
                event_type=event.event_type,
                payload_jcs=event.payload_jcs.decode('utf-8'),
                payload_hash=event.payload_hash,
                prev_event_hash=event.prev_event_hash,
                event_hash=event.event_hash,
                chain_authority=event.chain_authority,
                source_sdk_ver=event.source_sdk_ver,
                schema_ver=event.schema_ver,
            )
            db.add(row)
            db.commit()
        finally:
            db.close()
    
    def get_chain_state(self, session_id: str) -> Optional[ChainState]:
        """
        Return the current chain state for a session.
        
        Returns:
            ChainState or None: ChainState containing session_id, last_sequence, last_event_hash, and is_closed; `None` if the session has no events.
        """
        db = self.Session()
        try:
            last_event = (
                db.query(EventRow)
                .filter(EventRow.session_id == session_id)
                .order_by(EventRow.sequence_number.desc())
                .first()
            )
            
            if last_event is None:
                return None
            
            # Check if session is closed (SESSION_END or CHAIN_SEAL present)
            is_closed = (
                db.query(EventRow)
                .filter(EventRow.session_id == session_id)
                .filter(EventRow.event_type.in_(["SESSION_END", "CHAIN_SEAL"]))
                .first() is not None
            )
            
            return ChainState(
                session_id=session_id,
                last_sequence=last_event.sequence_number,
                last_event_hash=last_event.event_hash,
                is_closed=is_closed,
            )
        finally:
            db.close()
    
    def get_session_events(self, session_id: str) -> List[EventRow]:
        """
        Return all events for the given session ordered by sequence number ascending.
        
        The returned EventRow objects are detached from the ORM session so they can be used safely after the database session is closed.
        
        Parameters:
            session_id (str): Identifier of the session to retrieve events for.
        
        Returns:
            List[EventRow]: Event rows for the session ordered by increasing sequence_number.
        """
        db = self.Session()
        try:
            events = (
                db.query(EventRow)
                .filter(EventRow.session_id == session_id)
                .order_by(EventRow.sequence_number.asc())
                .all()
            )
            # Detach from session for safe return
            for e in events:
                db.expunge(e)
            return events
        finally:
            db.close()