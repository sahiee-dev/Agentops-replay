"""
agentops_ingest/export.py - Read-Only Export

Responsibilities:
- Generate session_golden.json
- Cannot write
- Cannot seal
- Cannot infer
"""
import json
from typing import List, Dict, Any

from .store import EventStore, EventRow


def export_session(store: EventStore, session_id: str) -> List[Dict[str, Any]]:
    """
    Export a session as a list of event dictionaries.
    
    This is the format used for session_golden.json and verification.
    """
    rows = store.get_session_events(session_id)
    
    events = []
    for row in rows:
        event = {
            "event_id": row.event_id,
            "session_id": row.session_id,
            "sequence_number": row.sequence_number,
            "timestamp_wall": row.timestamp_wall,
            "event_type": row.event_type,
            "payload_hash": row.payload_hash,
            "prev_event_hash": row.prev_event_hash,
            "event_hash": row.event_hash,
            "chain_authority": row.chain_authority,
            "payload": json.loads(row.payload_jcs),
        }
        
        # Optional fields
        if row.timestamp_monotonic is not None:
            event["timestamp_monotonic"] = row.timestamp_monotonic
        if row.source_sdk_ver is not None:
            event["source_sdk_ver"] = row.source_sdk_ver
        if row.schema_ver is not None:
            event["schema_ver"] = row.schema_ver
        
        events.append(event)
    
    return events


def export_session_json(store: EventStore, session_id: str, indent: int = 2) -> str:
    """
    Export a session as a JSON string.
    """
    events = export_session(store, session_id)
    return json.dumps(events, indent=indent)
