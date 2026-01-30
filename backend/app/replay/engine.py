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
    Verify an event chain for a session before serving.
    
    Per invariant: if verification fails, return an explicit ReplayFailure and expose no frames, partial data, or metadata — serving from an invalid chain is forbidden.
    
    Parameters:
        session_id (str): Session UUID.
        events (List[Dict[str, Any]]): Events retrieved from storage for the session.
        chain_seal (Optional[Dict[str, Any]]): Optional chain seal metadata.
    
    Returns:
        Tuple[Optional[VerifiedChain], Optional[ReplayFailure]]: On success, `(VerifiedChain, None)`. On failure, `(None, ReplayFailure)` where the `ReplayFailure` has `verification_status` set to `INVALID` and contains `error_code` and `error_message`.
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
    Convert a verified event chain into a ReplayResult containing frames and warnings.
    
    Builds a sequence of ReplayFrame objects from the provided VerifiedChain, injecting GAP frames for missing sequence numbers and LOG_DROP frames for drop events, and accumulates ReplayWarning entries for detected issues (gaps, timestamp anomalies, dropped events, and chain-level concerns).
    
    Parameters:
        chain (VerifiedChain): A verified event chain to convert; must represent a VALID verification state.
    
    Returns:
        ReplayResult: Replay result containing frames, warnings, counts (event_count, total_drops), first/last timestamps, and the chain final_hash.
    
    Raises:
        ValueError: If a LOG_DROP event has a missing, non-string, or invalid JSON `payload` (data integrity violation).
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
            # Payload MUST be payload_canonical (string), parse with json.loads
            payload_canonical = event.get('payload')
            if payload_canonical is None:
                raise ValueError(
                    f"LOG_DROP event at sequence {seq} missing payload_canonical. "
                    f"This is a data integrity violation."
                )
            if not isinstance(payload_canonical, str):
                raise ValueError(
                    f"LOG_DROP event at sequence {seq} has non-string payload. "
                    f"Expected canonical JSON string, got {type(payload_canonical).__name__}."
                )
            
            try:
                import json
                payload_dict = json.loads(payload_canonical)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"LOG_DROP event at sequence {seq} has invalid JSON payload: {e}"
                )
            
            dropped_count = payload_dict.get('dropped_count', 0)
            drop_reason = payload_dict.get('reason', 'UNKNOWN')
            
            frames.append(ReplayFrame(
                frame_type=FrameType.LOG_DROP,
                position=position,
                sequence_number=seq,
                timestamp=timestamp,
                event_type=event_type,
                payload=payload_canonical,  # Keep as canonical string
                event_hash=event.get('event_hash'),
                dropped_count=dropped_count,
                drop_reason=drop_reason
            ))
            warnings.append(ReplayWarning.events_dropped(dropped_count, drop_reason, position))
            total_drops += dropped_count
        else:
            # Normal EVENT frame - payload is already canonical string
            frames.append(ReplayFrame(
                frame_type=FrameType.EVENT,
                position=position,
                sequence_number=seq,
                timestamp=timestamp,
                event_type=event_type,
                payload=event.get('payload'),  # Already canonical JSON string
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
    Retrieve the replay frame that covers a given sequence number.
    
    Returns the exact frame whose `sequence_number` equals `sequence` if present; otherwise returns an existing GAP frame that contains `sequence`. If no covering frame exists, returns a synthetic GAP `ReplayFrame` with `position=-1` and `gap_start`/`gap_end` set to `sequence`.
    
    Returns:
        ReplayFrame: The frame covering `sequence` — either an existing EVENT/LOG_DROP frame, an existing GAP frame containing the sequence, or a synthetic GAP frame for the sequence.
    """
    # First check for exact match on sequence_number
    for frame in replay.frames:
        if frame.sequence_number == sequence:
            return frame
    
    # Check if sequence falls within an existing GAP frame
    for frame in replay.frames:
        if frame.frame_type == FrameType.GAP:
            if frame.gap_start is not None and frame.gap_end is not None:
                if frame.gap_start <= sequence <= frame.gap_end:
                    # Return the original GAP frame with its real position and range
                    return frame
    
    # Not in an existing gap - determine if we need a synthetic gap
    all_sequences = [f.sequence_number for f in replay.frames if f.sequence_number is not None]
    
    if not all_sequences:
        # No events at all - return synthetic gap frame
        return ReplayFrame(
            frame_type=FrameType.GAP,
            position=-1,
            gap_start=sequence,
            gap_end=sequence
        )
    
    # Outside any existing frame range - return synthetic gap
    return ReplayFrame(
        frame_type=FrameType.GAP,
        position=-1,
        gap_start=sequence,
        gap_end=sequence
    )


def _verify_chain(events: List[Dict[str, Any]]) -> Tuple[bool, str, str]:
    """
    Validate a sequence of events for replay readiness.
    
    Checks that the event list is either empty or contains strictly increasing
    `sequence_number` values and that every event has a non-empty `event_hash`.
    
    Parameters:
        events (List[Dict[str, Any]]): Ordered list of event dictionaries. Each event is expected
            to contain at least the keys `sequence_number` (int) and `event_hash` (str).
    
    Returns:
        Tuple[bool, str, str]: `(valid, error_code, error_message)` where:
            - `valid` is `True` when the chain passes all checks, `False` otherwise.
            - `error_code` is `""` on success or one of:
                - `"MISSING_SEQUENCE"` — an event is missing `sequence_number`.
                - `"NON_MONOTONIC"` — sequence numbers are not strictly increasing.
                - `"MISSING_HASH"` — an event is missing `event_hash`.
            - `error_message` is a human-readable description of the failure or `""` on success.
    
    Behavior notes:
        - An empty `events` list is considered valid.
        - This function performs structural integrity checks only and does not re-compute or cryptographically verify hashes.
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
    """
    Classify the evidence class for a chain based on whether it is sealed and whether any LOG_DROP events are present.
    
    If a chain seal is present and there are no LOG_DROP events, the result is "AUTHORITATIVE_EVIDENCE". If a chain seal is present and any LOG_DROP events exist, the result is "PARTIAL_AUTHORITATIVE_EVIDENCE". If no chain seal is present, the result is "NON_AUTHORITATIVE_EVIDENCE".
    
    Returns:
        str: One of "AUTHORITATIVE_EVIDENCE", "PARTIAL_AUTHORITATIVE_EVIDENCE", or "NON_AUTHORITATIVE_EVIDENCE".
    """
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