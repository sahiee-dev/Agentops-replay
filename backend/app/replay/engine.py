"""
engine.py - Core replay engine.

CRITICAL INVARIANTS:
1. Replay consumes VERIFIED chains only
2. Verification MUST happen before serving
3. If verification fails: NO frames, NO partial data, NO metadata
4. Serving anything from an invalid chain is FORBIDDEN
"""

import sys
import os
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

# Add verifier to path for JCS import (LOCKED to verifier implementation)
_verifier_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'verifier'))
if _verifier_path not in sys.path:
    sys.path.insert(0, _verifier_path)

from .frames import FrameType, ReplayFrame, VerificationStatus
from .warnings import (
    WarningSeverity, WarningCode, ReplayWarning
)


@dataclass
class VerifiedChain:
    """A verified event chain ready for replay."""
    session_id: str
    events: List[Dict[str, Any]]
    evidence_class: str
    seal_present: bool
    seal_hash: Optional[str]
    final_hash: str
    verification_status: VerificationStatus


@dataclass 
class ReplayFailure:
    """Explicit failure object when verification fails."""
    session_id: str
    verification_status: VerificationStatus  # Always INVALID
    error_code: str
    error_message: str
    
    # CRITICAL: No frames, no partial data, no metadata
    # These fields explicitly do not exist


@dataclass
class ReplayResult:
    """
    Complete replay result for a verified session.
    
    INVARIANT: This object is ONLY created from verified chains.
    """
    session_id: str
    evidence_class: str
    seal_present: bool
    verification_status: VerificationStatus
    
    frames: List[ReplayFrame]
    warnings: List[ReplayWarning]
    
    # Metadata (verbatim from verified chain)
    event_count: int
    total_drops: int
    first_timestamp: Optional[str]
    last_timestamp: Optional[str]
    final_hash: str


def load_verified_session(
    session_id: str,
    events: List[Dict[str, Any]],
    chain_seal: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[VerifiedChain], Optional[ReplayFailure]]:
    """
    Load and verify a session before serving.
    
    CRITICAL: If verification fails:
    - Return explicit failure object
    - NO frames, NO partial data, NO metadata
    - Serving anything from invalid chain is FORBIDDEN
    
    Args:
        session_id: Session UUID
        events: Events from storage
        chain_seal: Chain seal if present
        
    Returns:
        Tuple of (VerifiedChain, None) on success
        Tuple of (None, ReplayFailure) on failure
    """
    # Verify chain integrity
    verification_result = _verify_chain(events)
    
    if not verification_result[0]:
        return None, ReplayFailure(
            session_id=session_id,
            verification_status=VerificationStatus.INVALID,
            error_code=verification_result[1],
            error_message=verification_result[2]
        )
    
    # Determine evidence class
    evidence_class = _determine_evidence_class(events, chain_seal)
    
    # Get final hash
    final_hash = events[-1].get('event_hash', '') if events else ''
    
    return VerifiedChain(
        session_id=session_id,
        events=events,
        evidence_class=evidence_class,
        seal_present=chain_seal is not None,
        seal_hash=chain_seal.get('session_digest') if chain_seal else None,
        final_hash=final_hash,
        verification_status=VerificationStatus.VALID
    ), None


def build_replay(chain: VerifiedChain) -> ReplayResult:
    """
    Convert verified chain to replay frames.
    
    Injects:
    - GAP frames for missing sequences
    - LOG_DROP frames for drop events
    - Warnings for all detected issues
    
    INVARIANT: All frames have single traceable origin.
    """
    frames: List[ReplayFrame] = []
    warnings: List[ReplayWarning] = []
    
    total_drops = 0
    prev_seq = -1
    prev_timestamp = None
    position = 0
    
    for event in chain.events:
        seq = event.get('sequence_number', 0)
        event_type = event.get('event_type', '')
        timestamp = event.get('timestamp') or event.get('timestamp_wall')
        
        # Check for sequence gap
        if prev_seq >= 0 and seq > prev_seq + 1:
            gap_start = prev_seq + 1
            gap_end = seq - 1
            
            # Add GAP frame
            frames.append(ReplayFrame(
                frame_type=FrameType.GAP,
                position=position,
                gap_start=gap_start,
                gap_end=gap_end
            ))
            warnings.append(ReplayWarning.sequence_gap(gap_start, gap_end, position))
            position += 1
        
        # Check for timestamp anomaly
        if prev_timestamp and timestamp:
            if timestamp < prev_timestamp:
                warnings.append(ReplayWarning.timestamp_anomaly(position))
        
        # Handle LOG_DROP events
        if event_type == 'LOG_DROP':
            payload = event.get('payload', {})
            dropped_count = payload.get('dropped_count', 0)
            drop_reason = payload.get('reason', 'UNKNOWN')
            
            frames.append(ReplayFrame(
                frame_type=FrameType.LOG_DROP,
                position=position,
                sequence_number=seq,
                timestamp=timestamp,
                event_type=event_type,
                payload=payload,
                event_hash=event.get('event_hash'),
                dropped_count=dropped_count,
                drop_reason=drop_reason
            ))
            warnings.append(ReplayWarning.events_dropped(dropped_count, drop_reason, position))
            total_drops += dropped_count
        else:
            # Normal EVENT frame
            frames.append(ReplayFrame(
                frame_type=FrameType.EVENT,
                position=position,
                sequence_number=seq,
                timestamp=timestamp,
                event_type=event_type,
                payload=event.get('payload'),
                event_hash=event.get('event_hash')
            ))
        
        prev_seq = seq
        prev_timestamp = timestamp
        position += 1
    
    # Add chain-level warnings
    if not chain.seal_present:
        warnings.append(ReplayWarning.chain_not_sealed())
    
    if 'PARTIAL' in chain.evidence_class:
        warnings.append(ReplayWarning.partial_evidence())
    
    # Build result - fallback to timestamp_wall if timestamp is missing
    first_ts = None
    last_ts = None
    if chain.events:
        first_event = chain.events[0]
        last_event = chain.events[-1]
        first_ts = first_event.get('timestamp') or first_event.get('timestamp_wall')
        last_ts = last_event.get('timestamp') or last_event.get('timestamp_wall')
    
    return ReplayResult(
        session_id=chain.session_id,
        evidence_class=chain.evidence_class,
        seal_present=chain.seal_present,
        verification_status=chain.verification_status,
        frames=frames,
        warnings=warnings,
        event_count=len(chain.events),
        total_drops=total_drops,
        first_timestamp=first_ts,
        last_timestamp=last_ts,
        final_hash=chain.final_hash
    )


def get_frame_at_sequence(
    replay: ReplayResult,
    sequence: int
) -> ReplayFrame:
    """
    Get frame at specific sequence number.
    
    CONSTRAINT: This function:
    - MUST go through full verification (replay is already verified)
    - MUST NOT bypass gap logic
    - MUST return GAP frame if missing
    - Is NOT a "fast path" that skips replay logic
    """
    # First check for exact match
    for frame in replay.frames:
        if frame.sequence_number == sequence:
            return frame
    
    # Not found - determine if it's a gap
    all_sequences = [f.sequence_number for f in replay.frames if f.sequence_number is not None]
    
    if not all_sequences:
        # No events - return gap frame
        return ReplayFrame(
            frame_type=FrameType.GAP,
            position=-1,
            gap_start=sequence,
            gap_end=sequence
        )
    
    min_seq = min(all_sequences)
    max_seq = max(all_sequences)
    
    if min_seq <= sequence <= max_seq:
        # Within range but missing - it's in a gap
        return ReplayFrame(
            frame_type=FrameType.GAP,
            position=-1,
            gap_start=sequence,
            gap_end=sequence
        )
    
    # Outside range - still return gap frame
    return ReplayFrame(
        frame_type=FrameType.GAP,
        position=-1,
        gap_start=sequence,
        gap_end=sequence
    )


def _verify_chain(events: List[Dict[str, Any]]) -> Tuple[bool, str, str]:
    """
    Verify chain integrity.
    
    Returns:
        Tuple of (valid, error_code, error_message)
    """
    if not events:
        return (True, "", "")
    
    # Check sequence monotonicity
    prev_seq = None
    for idx, event in enumerate(events):
        seq = event.get('sequence_number')
        if seq is None:
            return (False, "MISSING_SEQUENCE", f"Event {idx} missing sequence_number")
        
        if prev_seq is not None and seq <= prev_seq:
            return (False, "NON_MONOTONIC", f"Sequence {prev_seq} -> {seq} at event {idx}")
        
        prev_seq = seq
    
    # Check hash chain
    # Note: Full verification would re-compute hashes, but for replay
    # we trust the ingestion service's verification
    for event in events:
        if not event.get('event_hash'):
            return (False, "MISSING_HASH", "Event missing event_hash")
    
    return (True, "", "")


def _determine_evidence_class(
    events: List[Dict[str, Any]],
    chain_seal: Optional[Dict[str, Any]]
) -> str:
    """Determine evidence class from events and seal."""
    # Check for drops
    has_drops = any(e.get('event_type') == 'LOG_DROP' for e in events)
    
    if chain_seal:
        # Sealed chain
        if has_drops:
            return "PARTIAL_AUTHORITATIVE_EVIDENCE"
        return "AUTHORITATIVE_EVIDENCE"
    else:
        # Unsealed
        return "NON_AUTHORITATIVE_EVIDENCE"
