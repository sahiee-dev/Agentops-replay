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
    timestamp_monotonic: Optional[int] = None
    # SDK version hint
    source_sdk_ver: Optional[str] = None
    schema_ver: Optional[str] = None


def validate_claim(raw_event: Dict[str, Any]) -> ValidatedClaim:
    """
    Validate and normalize an incoming ingest event claim into a ValidatedClaim.
    
    Performs authority-leak checks, strict schema validation, ISO-8601-with-timezone timestamp parsing, RFC 8785 JCS canonicalization of the payload, and SHA-256 payload-hash recomputation and optional verification. On success returns a ValidatedClaim populated with the parsed timestamp, canonical payload bytes, and computed payload hash.
    
    Parameters:
        raw_event (Dict[str, Any]): Incoming event envelope. Required keys: `event_id`, `session_id`, `sequence_number`, `timestamp_wall`, `event_type`, and `payload`. Optional keys: `payload_hash`, `timestamp_monotonic`, `source_sdk_ver`, `schema_ver`.
    
    Returns:
        ValidatedClaim: An immutable, validated claim containing identifiers, parsed timestamp (`timestamp_parsed`), canonical payload bytes (`payload_jcs`), computed `payload_hash`, and any provided optional hints.
    
    Raises:
        IngestException: If validation fails, with specific error constructors for:
            - authority_leak (forbidden client-provided fields),
            - schema_invalid (missing/invalid fields or types),
            - timestamp_invalid (malformed or timezone-naive timestamps),
            - jcs_invalid (payload canonicalization errors),
            - payload_hash_mismatch (client-provided hash does not match computed hash).
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
    """
    Reject events that include forbidden client-provided authority fields.
    
    Raises IngestException with an authority_leak error if any field from FORBIDDEN_CLIENT_FIELDS
    is present in the incoming event and its value is not None.
    
    Parameters:
        raw_event (dict): Incoming event envelope to validate.
    
    Raises:
        IngestException: with authority_leak() when a forbidden client field is provided.
    """
    for field in FORBIDDEN_CLIENT_FIELDS:
        if field in raw_event and raw_event[field] is not None:
            raise IngestException(authority_leak())


def _validate_schema(raw_event: Dict[str, Any]) -> None:
    """
    Validate that an incoming event envelope contains all required top-level fields and that those fields have the expected types and allowed values.
    
    Checks performed:
    - All fields in REQUIRED_ENVELOPE_FIELDS are present.
    - `event_id` and `session_id` are strings.
    - `sequence_number` is an integer (booleans are rejected) and is >= 0.
    - `timestamp_wall` is a string.
    - `event_type` is a string and one of VALID_EVENT_TYPES.
    - `payload` is a JSON object (dict).
    
    Raises:
        IngestException: with `schema_invalid` payload when any required field is missing or a field has an invalid type or value (details include the offending field and error information).
    """
    missing = [f for f in REQUIRED_ENVELOPE_FIELDS if f not in raw_event]
    if missing:
        raise IngestException(schema_invalid({"missing_fields": missing}))
    
    # Type checks
    if not isinstance(raw_event["event_id"], str):
        raise IngestException(schema_invalid({"field": "event_id", "error": "must be string"}))
    
    if not isinstance(raw_event["session_id"], str):
        raise IngestException(schema_invalid({"field": "session_id", "error": "must be string"}))
    
    # Reject booleans (isinstance(True, int) is True in Python)
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
            "error": f"invalid event type",
            "received": raw_event["event_type"],
            "valid": VALID_EVENT_TYPES
        }))
    
    if not isinstance(raw_event["payload"], dict):
        raise IngestException(schema_invalid({"field": "payload", "error": "must be object"}))


def _validate_timestamp(ts_str: str) -> datetime:
    """
    Validate and parse an ISO-8601 timestamp string that includes an explicit timezone.
    
    Parses the input string into a timezone-aware datetime.
    
    Returns:
        datetime: A timezone-aware datetime parsed from the input string.
    
    Raises:
        IngestException: Raised via `timestamp_invalid` when the input does not match the expected ISO-8601-with-timezone format, when the parsed value is missing timezone information, or when parsing fails.
    """
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
    """
    Produce RFC 8785 JCS canonicalized bytes for the given JSON-like payload.
    
    Parameters:
        payload (Dict[str, Any]): JSON object (mapping) to canonicalize.
    
    Returns:
        bytes: Canonical JCS-encoded bytes of the payload.
    
    Raises:
        IngestException: with `jcs_invalid` when canonicalization fails.
    """
    try:
        return jcs.canonicalize(payload)
    except Exception as e:
        raise IngestException(jcs_invalid({"error": str(e)}))