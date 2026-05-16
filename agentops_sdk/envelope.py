import hashlib
import datetime
import sys
import os

# CRITICAL: Import JCS from verifier — the single canonical copy
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'verifier'))
from jcs import canonicalize as jcs_canonicalize


# The prev_hash value for the first event in any session (seq=1)
GENESIS_HASH = "0" * 64


def build_event(
    seq: int,
    event_type: str,
    session_id: str,
    payload: dict,
    prev_hash: str,
) -> dict:
    """
    Build a complete event envelope with computed hashes.

    This is the single source of truth for event construction.
    The SDK must not construct events by any other means.

    The 7-field envelope (TRD §2.3):
        seq, event_type, session_id, timestamp, payload, prev_hash, event_hash

    Hash computation:
    1. Build event dict WITHOUT event_hash field
    2. JCS canonicalize (RFC 8785)
    3. SHA-256 the UTF-8 bytes
    4. Set event_hash to hex digest
    """
    timestamp = _utc_timestamp()

    event = {
        "seq": seq,
        "event_type": event_type,
        "session_id": session_id,
        "timestamp": timestamp,
        "payload": payload,
        "prev_hash": prev_hash,
    }

    event["event_hash"] = _compute_event_hash(event)
    return event


def _compute_event_hash(event: dict) -> str:
    """
    SHA-256 of the JCS canonical form, excluding the event_hash field itself.
    """
    event_for_hash = {k: v for k, v in event.items() if k != "event_hash"}
    canonical_bytes = jcs_canonicalize(event_for_hash)
    return hashlib.sha256(canonical_bytes).hexdigest()


def _utc_timestamp() -> str:
    """
    UTC time as ISO 8601 with microsecond precision.
    Format: 2026-05-05T10:30:00.123456Z
    """
    now = datetime.datetime.utcnow()
    return now.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
