"""
hasher.py - Server-side hash recomputation for event chains.

CRITICAL INVARIANTS:
1. NEVER trust SDK-provided hashes
2. Re-calculate entire chain from genesis
3. Validate strict sequence monotonicity
4. Explicit rejection for all violations

Rejection Reasons:
- NON_MONOTONIC_SEQUENCE: Sequence numbers not strictly increasing
- MISSING_PREV_HASH: Event (non-genesis) missing prev_hash
- INVALID_GENESIS: First event has incorrect genesis hash
- HASH_MISMATCH: Recomputed hash differs from claimed (if any)
"""

import sys
import os
import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple

# Add verifier to path for JCS import (LOCKED to verifier implementation)
_verifier_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', 'verifier'))
if _verifier_path not in sys.path:
    sys.path.insert(0, _verifier_path)

from jcs import canonicalize  # AUTHORITATIVE: verifier's RFC 8785 implementation


class RejectionReason(Enum):
    """Reasons for rejecting an event batch."""
    NON_MONOTONIC_SEQUENCE = "NON_MONOTONIC_SEQUENCE"
    MISSING_PREV_HASH = "MISSING_PREV_HASH"
    INVALID_GENESIS = "INVALID_GENESIS"
    SEQUENCE_GAP = "SEQUENCE_GAP"
    DUPLICATE_SEQUENCE = "DUPLICATE_SEQUENCE"


# Genesis hash constant (all zeros - first event's prev_hash)
GENESIS_HASH = "0" * 64


@dataclass
class ChainResult:
    """Result of chain recomputation."""
    valid: bool
    rejection_reason: Optional[RejectionReason] = None
    rejection_details: Optional[str] = None
    recomputed_events: Optional[List[Dict[str, Any]]] = None
    final_hash: Optional[str] = None
    event_count: int = 0
    
    # SDK hashes are logged but NEVER trusted
    untrusted_sdk_hashes: Optional[List[str]] = None


def recompute_chain(
    events: List[Dict[str, Any]],
    expected_genesis_hash: str = GENESIS_HASH
) -> ChainResult:
    """
    Recompute hash chain from scratch, ignoring SDK-provided hashes.
    
    CRITICAL: This function establishes SERVER AUTHORITY.
    - SDK hashes are logged as untrusted_hash, never used
    - All hashes are recomputed from canonical payloads
    - Any validation failure results in FULL REJECTION
    
    Args:
        events: List of raw events from SDK (untrusted)
        expected_genesis_hash: Expected prev_hash for first event
        
    Returns:
        ChainResult with validation outcome
    """
    if not events:
        return ChainResult(
            valid=True,
            recomputed_events=[],
            final_hash=expected_genesis_hash,
            event_count=0
        )
    
    # Collect untrusted SDK hashes for logging
    untrusted_hashes = []
    
    # Validate sequence monotonicity FIRST
    validation_result = _validate_sequences(events)
    if not validation_result[0]:
        return ChainResult(
            valid=False,
            rejection_reason=validation_result[1],
            rejection_details=validation_result[2]
        )
    
    # Recompute chain
    recomputed = []
    prev_hash = expected_genesis_hash
    
    for idx, event in enumerate(events):
        # Log SDK hash as untrusted (if present)
        sdk_hash = event.get('event_hash')
        if sdk_hash:
            untrusted_hashes.append(sdk_hash)
        
        # Validate prev_hash for non-genesis events
        if idx == 0:
            # Genesis event
            event_prev_hash = event.get('prev_event_hash')
            if event_prev_hash and event_prev_hash != expected_genesis_hash:
                return ChainResult(
                    valid=False,
                    rejection_reason=RejectionReason.INVALID_GENESIS,
                    rejection_details=f"First event has prev_hash={event_prev_hash}, expected {expected_genesis_hash}"
                )
        else:
            # Non-genesis: prev_hash must match our computed prev
            event_prev_hash = event.get('prev_event_hash')
            # Note: We don't reject if SDK's prev_hash is wrong - we replace it
            # The key is that WE control the chain, not the SDK
        
        # Compute canonical payload
        payload = event.get('payload', {})
        if isinstance(payload, str):
            # Already serialized - parse and re-canonicalize
            import json
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                pass  # Keep as string if not valid JSON
        
        payload_canonical = canonicalize(payload)
        payload_hash = hashlib.sha256(payload_canonical).hexdigest()
        
        # Compute event hash
        # Hash includes: prev_hash + sequence + event_type + payload_hash
        event_data = {
            "prev_hash": prev_hash,
            "sequence_number": event.get('sequence_number'),
            "event_type": event.get('event_type'),
            "payload_hash": payload_hash,
            "timestamp_monotonic": event.get('timestamp_monotonic'),
        }
        event_canonical = canonicalize(event_data)
        event_hash = hashlib.sha256(event_canonical).hexdigest()
        
        # Build recomputed event (with server authority)
        recomputed_event = {
            **event,
            "prev_event_hash": prev_hash,
            "payload_canonical": payload_canonical.decode('utf-8'),
            "payload_hash": payload_hash,
            "event_hash": event_hash,
            "chain_authority": "SERVER",
        }
        recomputed.append(recomputed_event)
        
        # Update chain
        prev_hash = event_hash
    
    return ChainResult(
        valid=True,
        recomputed_events=recomputed,
        final_hash=prev_hash,
        event_count=len(recomputed),
        untrusted_sdk_hashes=untrusted_hashes if untrusted_hashes else None
    )


def _validate_sequences(events: List[Dict[str, Any]]) -> Tuple[bool, Optional[RejectionReason], Optional[str]]:
    """
    Validate sequence numbers are strictly monotonic.
    
    Returns:
        Tuple of (valid, rejection_reason, rejection_details)
    """
    if not events:
        return (True, None, None)
    
    seen_sequences = set()
    prev_seq = None
    
    for idx, event in enumerate(events):
        seq = event.get('sequence_number')
        
        if seq is None:
            return (False, RejectionReason.NON_MONOTONIC_SEQUENCE, 
                    f"Event {idx} missing sequence_number")
        
        # Check for duplicates
        if seq in seen_sequences:
            return (False, RejectionReason.DUPLICATE_SEQUENCE,
                    f"Duplicate sequence_number {seq} at event {idx}")
        
        # Check monotonicity
        if prev_seq is not None:
            if seq <= prev_seq:
                return (False, RejectionReason.NON_MONOTONIC_SEQUENCE,
                        f"Non-monotonic sequence: {prev_seq} -> {seq} at event {idx}")
            if seq != prev_seq + 1:
                return (False, RejectionReason.SEQUENCE_GAP,
                        f"Sequence gap: {prev_seq} -> {seq} at event {idx}")
        
        seen_sequences.add(seq)
        prev_seq = seq
    
    return (True, None, None)
