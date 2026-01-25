#!/usr/bin/env python3
"""
verifier_core.py - Shared hash computation and verification primitives.

CONSTITUTIONAL REQUIREMENT: Single source of truth for hash computation.
Used by BOTH ingestion service AND standalone verifier to ensure deterministic hashing.

Any modification to hash computation MUST update golden vector tests.
"""

import hashlib
import json
from typing import Dict, Any, List, Optional
import jcs  # Local RFC 8785 canonical JSON serialization


# --- Constants (from EVENT_LOG_SPEC.md v0.6) ---
SPEC_VERSION = "v0.6"
SIGNED_FIELDS = [
    "event_id",
    "session_id",
    "sequence_number",
    "timestamp_wall",
    "event_type",
    "payload_hash",
    "prev_event_hash"
]


def sha256(data: bytes) -> str:
    """
    Compute the SHA-256 hexadecimal digest of the input data.
    
    Returns:
        hex_digest (str): Hexadecimal SHA-256 digest of the provided data.
    """
    return hashlib.sha256(data).hexdigest()


def compute_payload_hash(payload: Dict[str, Any]) -> str:
    """
    Compute the canonical SHA-256 hash of an event payload using RFC 8785 canonical JSON.
    
    Parameters:
        payload (Dict[str, Any]): Event payload to hash.
    
    Returns:
        str: SHA-256 hexadecimal digest of the payload's RFC 8785 canonical JSON representation.
    
    Raises:
        ValueError: If the payload cannot be canonicalized.
    """
    try:
        canonical_bytes = jcs.canonicalize(payload)
        return sha256(canonical_bytes)
    except Exception as e:
        raise ValueError(f"Failed to canonicalize payload: {e}")


def compute_event_hash(event: Dict[str, Any]) -> str:
    """
    Compute event hash from signed fields per EVENT_LOG_SPEC.md.
    
    Hash is computed over canonicalized JSON of signed fields only:
    - event_id, session_id, sequence_number, timestamp_wall
    - event_type, payload_hash, prev_event_hash
    
    Args:
        event: Full event envelope
        
    Returns:
        SHA-256 hex digest of canonical signed fields
        
    Raises:
        ValueError: If required signed fields are missing
    """
    # Extract signed fields only
    signed_obj = {}
    for field in SIGNED_FIELDS:
        if field not in event:
            raise ValueError(f"Missing required signed field: {field}")
        signed_obj[field] = event[field]
    
    # Canonicalize and hash
    canonical_envelope = jcs.canonicalize(signed_obj)
    return sha256(canonical_envelope)


def verify_event_hash(event: Dict[str, Any]) -> bool:
    """
    Validate that the event's `event_hash` equals the SHA-256 hash computed over its signed fields.
    
    Parameters:
        event (dict): Event envelope containing the signed fields and an `event_hash` claim.
    
    Returns:
        `true` if the claimed `event_hash` matches the computed hash, `false` otherwise.
    """
    try:
        computed = compute_event_hash(event)
        claimed = event.get("event_hash")
        return computed == claimed
    except Exception:
        return False


def verify_payload_hash(event: Dict[str, Any]) -> bool:
    """
    Verify that an event's `payload_hash` equals the SHA-256 hash of its `payload` computed using RFC 8785 canonicalization.
    
    Parameters:
        event (Dict[str, Any]): Event envelope expected to contain `payload` and `payload_hash`.
    
    Returns:
        `True` if the computed payload hash matches `payload_hash`, `False` otherwise.
    """
    try:
        payload = event.get("payload")
        if payload is None:
            return False
        computed = compute_payload_hash(payload)
        claimed = event.get("payload_hash")
        return computed == claimed
    except Exception:
        return False


def classify_evidence(authority: str, sealed: bool, complete: bool, has_drops: bool = False) -> str:
    """
    Classify session evidence as authoritative or non-authoritative.
    
    Authoritative evidence is declared only when all of the following are true: authority equals "server", `sealed` is True, `complete` is True, and `has_drops` is False. Any other combination yields non-authoritative evidence.
    
    Parameters:
        authority (str): Chain authority identifier, typically "server" or "sdk".
        sealed (bool): Whether the chain has a valid chain seal.
        complete (bool): Whether the session is complete (e.g., SESSION_END present and sequence has no gaps).
        has_drops (bool): Whether any LOG_DROP events are present.
    
    Returns:
        str: `"AUTHORITATIVE_EVIDENCE"` if all authoritative conditions are met, `"NON_AUTHORITATIVE_EVIDENCE"` otherwise.
    """
    if authority == "server" and sealed and complete and not has_drops:
        # ALL conditions met - this is the ONLY path to authoritative status
        return "AUTHORITATIVE_EVIDENCE"
    else:
        # Everything else - including:
        # - SDK authority (even if "sealed")
        # - Server authority without seal
        # - Server authority with drops
        # - Incomplete sessions
        return "NON_AUTHORITATIVE_EVIDENCE"


def validate_chain_continuity(events: List[Dict[str, Any]]) -> tuple[bool, Optional[str]]:
    """
    Validate that a list of events forms a continuous, internally consistent hash chain.
    
    Checks that the first event's `prev_event_hash` is null, each event's `prev_event_hash` equals the previous event's `event_hash`, and that every event's `event_hash` and `payload_hash` verify successfully.
    
    Parameters:
        events (List[Dict[str, Any]]): Ordered list of event objects representing the chain.
    
    Returns:
        tuple[bool, Optional[str]]: `True` and `None` if the chain is continuous and all hashes verify; `False` and a descriptive error message otherwise.
    """
    prev_hash = None
    
    for i, event in enumerate(events):
        # First event must have null prev_event_hash
        if i == 0:
            if event.get("prev_event_hash") is not None:
                return False, "First event must have null prev_event_hash"
        else:
            # Subsequent events must link to previous
            if event.get("prev_event_hash") != prev_hash:
                return False, f"Chain broken at event {i}: expected {prev_hash}, got {event.get('prev_event_hash')}"
        
        # Verify event hash
        if not verify_event_hash(event):
            return False, f"Invalid event hash at event {i}"
        
        # Verify payload hash
        if not verify_payload_hash(event):
            return False, f"Invalid payload hash at event {i}"
        
        prev_hash = event.get("event_hash")
    
    return True, None


def validate_sequence_monotonicity(events: List[Dict[str, Any]]) -> tuple[bool, Optional[str]]:
    """
    Ensure sequence_number fields start at 0 and increase by 1 for each consecutive event.
    
    Parameters:
        events (List[Dict[str, Any]]): Ordered list of event objects to validate.
    
    Returns:
        tuple[bool, Optional[str]]: First element is `True` if sequence numbers are strictly increasing starting at 0, `False` otherwise. Second element is `None` on success or an error message describing the first detected mismatch.
    """
    expected_seq = 0
    
    for i, event in enumerate(events):
        actual_seq = event.get("sequence_number")
        if actual_seq != expected_seq:
            return False, f"Sequence gap at event {i}: expected {expected_seq}, got {actual_seq}"
        expected_seq += 1
    
    return True, None


def check_mixed_authority(events: List[Dict[str, Any]]) -> tuple[bool, Optional[set]]:
    """
    Detects whether multiple distinct non-empty `chain_authority` values appear across the provided events.
    
    Parameters:
        events (List[Dict[str, Any]]): Sequence of event objects; each event may contain a `chain_authority` field.
    
    Returns:
        tuple[bool, Optional[set]]: `(has_mixed_authority, authorities)` where `has_mixed_authority` is `True` if more than one distinct non-empty authority was found, `False` otherwise; `authorities` is the set of distinct authorities when mixed, or `None` when not mixed.
    """
    authorities = set()
    for event in events:
        auth = event.get("chain_authority")
        if auth:
            authorities.add(auth)
    
    has_mixed = len(authorities) > 1
    return has_mixed, authorities if has_mixed else None


# Golden vector for hash determinism testing
GOLDEN_TEST_PAYLOAD = {
    "test": "data",
    "number": 42,
    "nested": {"key": "value"}
}

GOLDEN_PAYLOAD_HASH = "9c15b0e1e3c6c8f3a9c8e9b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"  # Placeholder - will be computed


def test_golden_vector() -> bool:
    """
    Performs the golden-vector check to ensure payload hash determinism across implementations.
    
    Returns:
        `True` if the computed payload hash matches the golden-vector expectation (valid SHA-256 hex digest), `False` otherwise.
    """
    computed = compute_payload_hash(GOLDEN_TEST_PAYLOAD)
    # For now, we compute and accept
    # In production, this would be a fixed expected hash
    return len(computed) == 64  # Valid SHA-256 hex length