"""
agentops_ingest/validator.py - The Constitutional Gate

Most critical module. Responsibilities:
- JSON Schema validation (strict, no additional properties)
- RFC 8785 JCS canonicalization
- Timestamp validation (ISO-8601, timezone required)
- Authority-leak detection
- Payload hash recomputation

Output: ValidatedClaim object OR hard failure.
No partial success.
"""
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from .errors import (
    IngestException,
    schema_invalid,
    jcs_invalid,
    timestamp_invalid,
    authority_leak,
    payload_hash_mismatch,
)

# Import JCS from SDK (shared canonical implementation)
from agentops_sdk import jcs


# --- SCHEMA DEFINITION (v1.0) ---
# Strict: No additional properties allowed

REQUIRED_ENVELOPE_FIELDS = [
    "event_id",
    "session_id",
    "sequence_number",
    "timestamp_wall",
    "event_type",
    "payload",
]

OPTIONAL_ENVELOPE_FIELDS = [
    "payload_hash",
    "prev_event_hash",
    "timestamp_monotonic",
    "source_sdk_ver",
    "schema_ver",
]

# Fields that clients MUST NOT provide (authority leak)
FORBIDDEN_CLIENT_FIELDS = [
    "event_hash",
    "chain_authority",
]

VALID_EVENT_TYPES = [
    "SESSION_START",
    "SESSION_END",
    "MODEL_REQUEST",
    "MODEL_RESPONSE",
    "TOOL_CALL",
    "TOOL_RESULT",
    "AGENT_STATE_SNAPSHOT",
    "AGENT_DECISION",
    "DECISION_TRACE",
    "ERROR",
    "ANNOTATION",
    "CHAIN_SEAL",
    "LOG_DROP",
]

# ISO-8601 with timezone (Z or +HH:MM)
ISO8601_REGEX = re.compile(
    r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$'
)


@dataclass(frozen=True)
class ValidatedClaim:
    """Immutable validated claim ready for sealing."""
    event_id: str
    session_id: str
    sequence_number: int
    timestamp_wall: str
    timestamp_parsed: datetime
    event_type: str
    payload_jcs: bytes
    payload_hash: str
    # Monotonic timestamp if provided by client (optional hint)
    timestamp_monotonic: Optional[float] = None
    # SDK version hint
    source_sdk_ver: Optional[str] = None
    schema_ver: Optional[str] = None


def validate_claim(raw_event: Dict[str, Any]) -> ValidatedClaim:
    """
    Validate an incoming event claim.
    
    Raises IngestException on any failure.
    Returns ValidatedClaim on success.
    """
    # 1. Authority Leak Detection (FIRST - fail fast)
    _check_authority_leak(raw_event)
    
    # 2. Schema Validation
    _validate_schema(raw_event)
    
    # 3. Timestamp Validation
    timestamp_parsed = _validate_timestamp(raw_event["timestamp_wall"])
    
    # 4. JCS Canonicalization
    payload_jcs = _canonicalize_payload(raw_event["payload"])
    
    # 5. Recompute Payload Hash
    computed_hash = hashlib.sha256(payload_jcs).hexdigest()
    
    # 6. Verify client-provided hash (if present)
    if "payload_hash" in raw_event:
        client_hash = raw_event["payload_hash"]
        # Normalize comparison to be case-insensitive
        if client_hash.lower() != computed_hash.lower():
            raise IngestException(payload_hash_mismatch(computed_hash, client_hash))
    
    # Build ValidatedClaim
    return ValidatedClaim(
        event_id=raw_event["event_id"],
        session_id=raw_event["session_id"],
        sequence_number=raw_event["sequence_number"],
        timestamp_wall=raw_event["timestamp_wall"],
        timestamp_parsed=timestamp_parsed,
        event_type=raw_event["event_type"],
        payload_jcs=payload_jcs,
        payload_hash=computed_hash,
        timestamp_monotonic=raw_event.get("timestamp_monotonic"),
        source_sdk_ver=raw_event.get("source_sdk_ver"),
        schema_ver=raw_event.get("schema_ver"),
    )


def _check_authority_leak(raw_event: Dict[str, Any]) -> None:
    """Reject if client tries to assert authority."""
    for field in FORBIDDEN_CLIENT_FIELDS:
        if field in raw_event and raw_event[field] is not None:
            raise IngestException(authority_leak())


def _validate_schema(raw_event: Dict[str, Any]) -> None:
    """Validate required fields, strict schema (no extra fields), and types."""
    # 1. Required Fields
    missing = [f for f in REQUIRED_ENVELOPE_FIELDS if f not in raw_event]
    if missing:
        raise IngestException(schema_invalid({"missing_fields": missing}))
    
    # 2. Strict Schema (No Additional Properties)
    known_fields = set(REQUIRED_ENVELOPE_FIELDS) | set(OPTIONAL_ENVELOPE_FIELDS)
    unexpected = set(raw_event.keys()) - known_fields
    if unexpected:
        raise IngestException(schema_invalid({"unexpected_fields": list(unexpected)}))
    
    # 3. Type Checks (Required)
    if not isinstance(raw_event["event_id"], str):
        raise IngestException(schema_invalid({"field": "event_id", "error": "must be string"}))
    
    if not isinstance(raw_event["session_id"], str):
        raise IngestException(schema_invalid({"field": "session_id", "error": "must be string"}))
    
    # Reject booleans for sequence_number
    if not isinstance(raw_event["sequence_number"], int) or isinstance(raw_event["sequence_number"], bool):
        raise IngestException(schema_invalid({"field": "sequence_number", "error": "must be integer, not boolean"}))
    
    if raw_event["sequence_number"] < 0:
        raise IngestException(schema_invalid({"field": "sequence_number", "error": "must be >= 0"}))
    
    if not isinstance(raw_event["timestamp_wall"], str):
        raise IngestException(schema_invalid({"field": "timestamp_wall", "error": "must be string"}))
    
    if not isinstance(raw_event["event_type"], str):
        raise IngestException(schema_invalid({"field": "event_type", "error": "must be string"}))
    
    if raw_event["event_type"] not in VALID_EVENT_TYPES:
        raise IngestException(schema_invalid({
            "field": "event_type",
            "error": "invalid event type",
            "received": raw_event["event_type"],
            "valid": VALID_EVENT_TYPES
        }))
    
    if not isinstance(raw_event["payload"], dict):
        raise IngestException(schema_invalid({"field": "payload", "error": "must be object"}))

    # 4. Type Checks (Optional)
    if "payload_hash" in raw_event and not isinstance(raw_event["payload_hash"], str):
         raise IngestException(schema_invalid({"field": "payload_hash", "error": "must be string"}))

    if "timestamp_monotonic" in raw_event:
        tm = raw_event["timestamp_monotonic"]
        if (not isinstance(tm, (int, float))) or isinstance(tm, bool):
             raise IngestException(schema_invalid({"field": "timestamp_monotonic", "error": "must be number (int/float)"}))

    if "source_sdk_ver" in raw_event and not isinstance(raw_event["source_sdk_ver"], str):
         raise IngestException(schema_invalid({"field": "source_sdk_ver", "error": "must be string"}))

    if "schema_ver" in raw_event:
        sv = raw_event["schema_ver"]
        if (not isinstance(sv, (str, int))) or isinstance(sv, bool):
             raise IngestException(schema_invalid({"field": "schema_ver", "error": "must be string or int"}))


def _validate_timestamp(ts_str: str) -> datetime:
    """Validate ISO-8601 timestamp with timezone."""
    if not ISO8601_REGEX.match(ts_str):
        raise IngestException(timestamp_invalid({
            "received": ts_str,
            "error": "must be ISO-8601 with timezone (e.g., 2023-10-01T12:00:00Z)"
        }))
    
    try:
        # Parse the timestamp
        if ts_str.endswith('Z'):
            dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        else:
            dt = datetime.fromisoformat(ts_str)
        
        # Ensure timezone aware
        if dt.tzinfo is None:
            raise IngestException(timestamp_invalid({
                "received": ts_str,
                "error": "timestamp must be timezone-aware"
            }))
        
        return dt
    except ValueError as e:
        raise IngestException(timestamp_invalid({
            "received": ts_str,
            "error": str(e)
        }))


def _canonicalize_payload(payload: Dict[str, Any]) -> bytes:
    """Canonicalize payload using JCS (RFC 8785)."""
    try:
        return jcs.canonicalize(payload)
    except Exception as e:
        raise IngestException(jcs_invalid({"error": str(e)}))
