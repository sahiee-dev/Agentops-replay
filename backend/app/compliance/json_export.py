"""
json_export.py - RFC 8785 canonical JSON export for compliance.

CONSTITUTIONAL REQUIREMENT: Exports MUST be in canonical form for verification.
CRITICAL: Uses verifier's JCS implementation to prevent drift.
"""

import sys
import os
import uuid
from typing import Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session as DBSession

# Add verifier to path for JCS import (LOCKED to verifier implementation)
_verifier_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'verifier'))
if _verifier_path not in sys.path:
    sys.path.insert(0, _verifier_path)

from jcs import canonicalize  # AUTHORITATIVE: verifier's RFC 8785 implementation

from app.models import Session, EventChain, ChainSeal


def _format_iso8601(dt: datetime) -> str:
    """
    Format datetime to strict ISO 8601: YYYY-MM-DDTHH:MM:SS.sssZ
    
    No local offsets. No truncated seconds. Always UTC with Z suffix.
    """
    if dt is None:
        return None
    # Ensure UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    elif dt.tzinfo != timezone.utc:
        dt = dt.astimezone(timezone.utc)
    # Format with milliseconds and Z suffix
    return dt.strftime('%Y-%m-%dT%H:%M:%S.') + f'{dt.microsecond // 1000:03d}Z'


def generate_json_export(session_id: str, db: DBSession) -> Dict[str, Any]:
    """
    Generate RFC 8785 canonical JSON export.
    
    Includes:
    - Full event chain
    - Verification metadata
    - Evidence class (AUTHORITATIVE/PARTIAL_AUTHORITATIVE/NON_AUTHORITATIVE)
    - Chain-of-custody statement
    
    Args:
        session_id: Session UUID string
        db: Database session
        
    Returns:
        Canonical export dictionary
        
    Raises:
        ValueError: If session not found
    """
    # Validate session_id format
    try:
        uuid.UUID(session_id)
    except ValueError:
        raise ValueError(f"Invalid session ID format: {session_id}")

    # Get session
    session = db.query(Session).filter(
        Session.session_id_str == session_id
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
    
    # Determine evidence class
    evidence_class = _determine_evidence_class(session, chain_seal)
    
    # Build canonical events (MUST use payload_canonical)
    canonical_events = []
    for event in events:
        canonical_event = {
            "event_id": str(event.event_id),
            "session_id": str(session.session_id_str),
            "sequence_number": event.sequence_number,
            "timestamp_wall": _format_iso8601(event.timestamp_wall),
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
    export_timestamp = _format_iso8601(datetime.now(timezone.utc))
    
    export = {
        "export_version": "1.0",
        "export_timestamp": export_timestamp,
        "session_id": session_id,
        "evidence_class": evidence_class,  # EXPLICIT: per user requirement
        "chain_authority": session.chain_authority.value,
        "session_metadata": {
            "started_at": _format_iso8601(session.started_at),
            "sealed_at": _format_iso8601(session.sealed_at) if session.sealed_at else None,
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
            "seal_timestamp": _format_iso8601(chain_seal.seal_timestamp),
            "session_digest": chain_seal.session_digest,
            "final_event_hash": chain_seal.final_event_hash,
            "event_count": chain_seal.event_count
        }
    else:
        export["seal"] = {"present": False}
    
    return export


def _determine_evidence_class(session: Session, chain_seal: ChainSeal) -> str:
    """
    Determine evidence class per CHAIN_AUTHORITY_INVARIANTS.md.
    
    Returns one of:
    - AUTHORITATIVE_EVIDENCE: Server-sealed, complete chain
    - PARTIAL_AUTHORITATIVE_EVIDENCE: Server-sealed, incomplete chain
    - NON_AUTHORITATIVE_EVIDENCE: SDK-only, no seal
    """
    if chain_seal is None:
        return "NON_AUTHORITATIVE_EVIDENCE"
    
    # Check for completeness (no drops, sealed)
    if session.total_drops == 0 and session.sealed_at is not None:
        return "AUTHORITATIVE_EVIDENCE"
    
    return "PARTIAL_AUTHORITATIVE_EVIDENCE"


def serialize_canonical(export: Dict[str, Any]) -> bytes:
    """
    Serialize export to RFC 8785 canonical bytes.
    
    Uses verifier's JCS implementation (LOCKED).
    """
    return canonicalize(export)
