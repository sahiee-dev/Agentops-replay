"""
agentops_sdk/envelope.py - ProposedEvent and Envelope Logic
"""
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List
from .events import EventType, SCHEMA_VER
import hashlib
import json
import uuid
import datetime

# We need JCS for local authority signatures. 
# In a real package we'd vendor it properly or depend on it.
# For now, we import from verifier directory if available (dev mode) or minimal reimplementation.
try:
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'verifier')))
    import jcs
except ImportError:
    # Minimal fallback or fail? 
    # For this exercise, we assume the verifier/jcs.py is in path or we duplicate.
    # Duplicating minimal for standalone safety.
    raise ImportError("Verifier JCS module not found. In dev, ensure verifier/ is in path.")

@dataclass
class ProposedEvent:
    event_id: str
    session_id: str
    sequence_number: int        # Hint (unless local authority)
    timestamp_wall: str
    timestamp_monotonic: int
    event_type: EventType
    source_sdk_ver: str
    schema_ver: str
    payload_hash: str           # Calculated locally
    prev_event_hash: Optional[str] # Hint
    event_hash: Optional[str]   # None unless finalized
    payload: bytes              # Canonicalized JSON bytes
    chain_authority: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        # Return dict matching Spec v0.4
        d = asdict(self)
        # Check None -> null conversion
        d['payload'] = json.loads(self.payload) # Decode for JSON serialization (python dict)
        # But wait, to_dict usually goes to JSON. 
        # The payload field in envelope is bytes? No, spec says bytes but JSON mapping is nested object.
        # Spec: "bytes payload = 12; // Canonicalized JSON"
        # In JSON: "payload": {...}
        return d

def create_proposal(
    session_id: str, 
    seq: int, 
    event_type: EventType, 
    payload: Dict[str, Any],
    prev_hash: Optional[str],
    local_authority: bool = False
) -> ProposedEvent:
    
    # 1. Canonicalize Payload
    canonical_payload = jcs.canonicalize(payload)
    p_hash = hashlib.sha256(canonical_payload).hexdigest()
    
    # 2. Envelope
    ts_wall = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    ts_mono = 0 # Todo: monotonic clock
    
    proposal = ProposedEvent(
        event_id=str(uuid.uuid4()), # UUID7 preferred
        session_id=session_id,
        sequence_number=seq,
        timestamp_wall=ts_wall,
        timestamp_monotonic=ts_mono,
        event_type=event_type,
        source_sdk_ver="python-sdk-0.1",
        schema_ver=SCHEMA_VER,
        payload_hash=p_hash,
        prev_event_hash=prev_hash,
        event_hash=None,
        payload=canonical_payload,
        chain_authority="sdk" if local_authority else None
    )
    
    # 3. Finalize if Local Authority
    if local_authority:
        signed_fields = [
            "event_id", "session_id", "sequence_number", 
            "timestamp_wall", "event_type", "payload_hash", "prev_event_hash"
        ]
        # Construct signed object
        d = proposal.to_dict()
        # Ensure only signed fields
        signed_obj = {k: d[k] for k in signed_fields if k in d}
        
        # JCS
        canonical_env = jcs.canonicalize(signed_obj)
        proposal.event_hash = hashlib.sha256(canonical_env).hexdigest()
        proposal.chain_authority = "sdk"
        
    return proposal
