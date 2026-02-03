"""
agentops_ingest/sealer.py - Authority Origin

The ONLY place hashes are born.

Responsibilities:
- Fetch last authoritative event for (session_id)
- Enforce contiguous sequence numbers
- Compute prev_event_hash and event_hash
- Assign chain_authority
"""
import hashlib
from dataclasses import dataclass
from typing import Optional

from .validator import ValidatedClaim
from .errors import (
    IngestException,
    sequence_rewind,
    log_gap,
    IngestError,
    IngestErrorCode,
    ErrorClassification,
    session_closed,
    invalid_first_sequence,
)

# Import JCS from SDK (should be installed as dependency)
from agentops_sdk import jcs


# Authority version - this is the identity of this ingestion service
CHAIN_AUTHORITY = "agentops-ingest-v1"


@dataclass(frozen=True)
class SealedEvent:
    """Immutable sealed event ready for storage."""
    event_id: str
    session_id: str
    sequence_number: int
    timestamp_wall: str
    event_type: str
    payload_jcs: bytes
    payload_hash: str
    prev_event_hash: Optional[str]
    event_hash: str
    chain_authority: str
    # Optional metadata
    timestamp_monotonic: Optional[float] = None
    source_sdk_ver: Optional[str] = None
    schema_ver: Optional[str] = None


@dataclass(frozen=True)
class ChainState:
    """Current state of a session's chain."""
    session_id: str
    last_sequence: int
    last_event_hash: str
    is_closed: bool


def seal_event(
    claim: ValidatedClaim,
    chain_state: Optional[ChainState],
    strict_mode: bool = True
) -> SealedEvent:
    """
    Seal a validated claim with authoritative hash chain.
    
    Args:
        claim: Validated claim from validator
        chain_state: Current chain state for this session (None if first event)
        strict_mode: If True, reject sequence gaps; if False, allow with warning
    
    Returns:
        SealedEvent ready for storage
    
    Raises:
        IngestException on sequence violations
    """
    # 0. Check Session Alignment
    if chain_state is not None and chain_state.session_id != claim.session_id:
         raise IngestException(IngestError(
             error_code=IngestErrorCode.SCHEMA_INVALID, 
             classification=ErrorClassification.HARD_REJECT,
             message=f"Session ID mismatch: chain_state={chain_state.session_id} vs claim={claim.session_id}",
             details={"chain_session": chain_state.session_id, "claim_session": claim.session_id}
         ))

    # 1. Sequence Continuity
    expected_seq = 0
    if chain_state is not None:
        # Check if session is closed
        if chain_state.is_closed:
            raise IngestException(session_closed(claim.session_id))
        
        expected_seq = chain_state.last_sequence + 1
        
        # Sequence rewind (always fatal)
        if claim.sequence_number <= chain_state.last_sequence:
            raise IngestException(sequence_rewind(
                chain_state.last_sequence,
                claim.sequence_number
            ))
        
        # Sequence gap
        if claim.sequence_number > expected_seq:
            if strict_mode:
                # In strict mode, gaps are fatal
                raise IngestException(log_gap(expected_seq, claim.sequence_number))
            # In non-strict mode, we'd log a warning but continue
            # For now, we always enforce strict
        
        prev_event_hash = chain_state.last_event_hash
    else:
        # First event in session
        if claim.sequence_number != 0:
            # First event must be sequence 0
            raise IngestException(invalid_first_sequence(claim.sequence_number))
        prev_event_hash = None
    
    # 2. Compute Event Hash (The Seal)
    # Fields included in hash preimage (as per PRODUCTION_INGESTION_CONTRACT.md)
    signed_obj = {
        "event_id": claim.event_id,
        "session_id": claim.session_id,
        "sequence_number": claim.sequence_number,
        "timestamp_wall": claim.timestamp_wall,
        "event_type": claim.event_type,
        "payload_hash": claim.payload_hash,
        "prev_event_hash": prev_event_hash,
    }
    
    canonical_envelope = jcs.canonicalize(signed_obj)
    event_hash = hashlib.sha256(canonical_envelope).hexdigest()
    
    # 3. Build Sealed Event
    return SealedEvent(
        event_id=claim.event_id,
        session_id=claim.session_id,
        sequence_number=claim.sequence_number,
        timestamp_wall=claim.timestamp_wall,
        event_type=claim.event_type,
        payload_jcs=claim.payload_jcs,
        payload_hash=claim.payload_hash,
        prev_event_hash=prev_event_hash,
        event_hash=event_hash,
        chain_authority=CHAIN_AUTHORITY,
        timestamp_monotonic=claim.timestamp_monotonic,
        source_sdk_ver=claim.source_sdk_ver,
        schema_ver=claim.schema_ver,
    )
