"""
agentops_sdk/envelope.py - ProposedEvent and Envelope Logic
"""
import datetime
import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from typing import Any

from .events import SCHEMA_VER, EventType

# We need JCS for local authority signatures.
# Vendoring JCS into SDK for standalone distribution
try:
    from . import jcs
except ImportError:
    import jcs  # Fallback if installed as package

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
    prev_event_hash: str | None # Hint
    event_hash: str | None   # None unless finalized
    payload: bytes              # Canonicalized JSON bytes
    chain_authority: str | None = None

    def to_dict(self) -> dict[str, Any]:
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
    payload: dict[str, Any],
    prev_hash: str | None,
    local_authority: bool = False
) -> ProposedEvent:

    # 1. Canonicalize Payload
    canonical_payload = jcs.canonicalize(payload)
    p_hash = hashlib.sha256(canonical_payload).hexdigest()

    # 2. Envelope
    ts_wall = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    import time
    ts_mono = int(time.monotonic() * 1000)  # Convert to milliseconds

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
