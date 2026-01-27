"""
json_export.py - RFC 8785 canonical JSON export for compliance.

CONSTITUTIONAL REQUIREMENT: Exports MUST be in canonical form for verification.
"""

import sys
import os
import uuid
from typing import Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session as DBSession

from app.models import Session, EventChain, ChainSeal


def generate_json_export(session_id: str, db: DBSession) -> Dict[str, Any]:
    """
    Generate RFC 8785 canonical JSON export.
    
    Includes:
    - Full event chain
    - Verification metadata
    - Evidence class
    - Chain-of-custody statement
    
    Args:
        session_id: Session UUID string
        db: Database session
        
    Returns:
        Canonical export dictionary
        
    Raises:
        ValueError: If session not found
    """
    # Get session
    session = db.query(Session).filter(
        Session.session_id_str == uuid.UUID(session_id)
    ).first()
    
    if not session:
        raise ValueError(f"Session {session_id} not found")
    
    # Get events
    events = db.query(EventChain).filter(
        EventChain.session_id == session.id
    ).order_by(EventChain.sequence_number).all()
    
    # Get seal if exists
    chain_seal = db.query(ChainSeal).filter(
        ChainSeal.session_id == session.id
    ).first()
    
    # Build canonical events (MUST use payload_canonical)
    canonical_events = []
    for event in events:
        canonical_event = {
            "event_id": str(event.event_id),
            "session_id": str(session.session_id_str),
            "sequence_number": event.sequence_number,
            "timestamp_wall": event.timestamp_wall.isoformat(),
            "timestamp_monotonic": event.timestamp_monotonic,
            "event_type": event.event_type,
            "source_sdk_ver": event.source_sdk_ver,
            "schema_ver": event.schema_ver,
            "payload": event.payload_canonical,  # AUTHORITATIVE: canonical text for verification
            "payload_hash": event.payload_hash,
            "prev_event_hash": event.prev_event_hash,
            "event_hash": event.event_hash,
            "chain_authority": event.chain_authority,
        }
        canonical_events.append(canonical_event)
    
    # Build export metadata (use single timestamp for determinism)
    export_timestamp = datetime.utcnow().isoformat() + "Z"
    
    export = {
        "export_version": "1.0",
        "export_timestamp": export_timestamp,
        "session_id": session_id,
        "evidence_class": session.evidence_class or "PENDING_VERIFICATION",
        "chain_authority": session.chain_authority.value,
        "session_metadata": {
            "started_at": session.started_at.isoformat().replace('+00:00', 'Z'),
            "sealed_at": session.sealed_at.isoformat().replace('+00:00', 'Z') if session.sealed_at else None,
            "status": session.status.value,
            "total_drops": session.total_drops,
            "event_count": len(events),
            "agent_name": session.agent_name
        },
        "seal": None,
        "events": canonical_events,
        "chain_of_custody": {
            "export_authority": session.ingestion_service_id,
            "export_timestamp": export_timestamp,  # Same timestamp for determinism
            "canonical_format": "RFC 8785 (JCS)"
        }
    }
    
    # Add seal metadata if present
    if chain_seal:
        export["seal"] = {
            "present": True,
            "ingestion_service_id": chain_seal.ingestion_service_id,
            "seal_timestamp": chain_seal.seal_timestamp.isoformat().replace('+00:00', 'Z'),
            "session_digest": chain_seal.session_digest,
            "final_event_hash": chain_seal.final_event_hash,
            "event_count": chain_seal.event_count
        }
    else:
        export["seal"] = {"present": False}
    
    return export
