"""
agentops_ingest/errors.py - Error Taxonomy (Machine-Enforced)

Errors are contracts, not strings.
"""
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any


class ErrorClassification(str, Enum):
    HARD_REJECT = "HARD_REJECT"
    PARTIAL_ACCEPT = "PARTIAL_ACCEPT"
    ACCEPT = "ACCEPT"


class IngestErrorCode(str, Enum):
    # HARD_REJECT (400)
    SCHEMA_INVALID = "INGEST_SCHEMA_INVALID"
    JCS_INVALID = "INGEST_JCS_INVALID"
    TIMESTAMP_INVALID = "INGEST_TIMESTAMP_INVALID"
    AUTHORITY_LEAK = "INGEST_AUTHORITY_LEAK"
    PAYLOAD_HASH_MISMATCH = "INGEST_PAYLOAD_HASH_MISMATCH"
    SEQUENCE_REWIND = "INGEST_SEQUENCE_REWIND"
    INVALID_FIRST_SEQUENCE = "INGEST_INVALID_FIRST_SEQUENCE"
    SESSION_CLOSED = "INGEST_SESSION_CLOSED"
    
    # PARTIAL_ACCEPT (202) - Strict mode rejects these
    LOG_GAP = "INGEST_LOG_GAP"
    
    # ACCEPT (201)
    ACCEPTED = "INGEST_ACCEPTED"


@dataclass(frozen=True)
class IngestError:
    """Immutable error response object."""
    error_code: IngestErrorCode
    classification: ErrorClassification
    message: str
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code.value,
            "classification": self.classification.value,
            "message": self.message,
            "details": self.details or {}
        }


class IngestException(Exception):
    """Exception raised for hard rejections."""
    def __init__(self, error: IngestError):
        self.error = error
        super().__init__(error.message)


# Pre-defined error factories for consistency
def schema_invalid(details: Dict[str, Any]) -> IngestError:
    return IngestError(
        error_code=IngestErrorCode.SCHEMA_INVALID,
        classification=ErrorClassification.HARD_REJECT,
        message="JSON schema violation",
        details=details
    )


def jcs_invalid(details: Dict[str, Any]) -> IngestError:
    return IngestError(
        error_code=IngestErrorCode.JCS_INVALID,
        classification=ErrorClassification.HARD_REJECT,
        message="Cannot canonicalize payload (RFC 8785)",
        details=details
    )


def timestamp_invalid(details: Dict[str, Any]) -> IngestError:
    return IngestError(
        error_code=IngestErrorCode.TIMESTAMP_INVALID,
        classification=ErrorClassification.HARD_REJECT,
        message="Malformed or missing timestamp",
        details=details
    )


def authority_leak() -> IngestError:
    return IngestError(
        error_code=IngestErrorCode.AUTHORITY_LEAK,
        classification=ErrorClassification.HARD_REJECT,
        message="Client attempted to assert authority (event_hash or chain_authority present)",
        details={}
    )


def payload_hash_mismatch(expected: str, received: str) -> IngestError:
    return IngestError(
        error_code=IngestErrorCode.PAYLOAD_HASH_MISMATCH,
        classification=ErrorClassification.HARD_REJECT,
        message="Client-provided payload_hash does not match recomputed hash",
        details={"expected": expected, "received": received}
    )


def sequence_rewind(last_seq: int, received_seq: int) -> IngestError:
    return IngestError(
        error_code=IngestErrorCode.SEQUENCE_REWIND,
        classification=ErrorClassification.HARD_REJECT,
        message="Sequence number <= last accepted sequence",
        details={"last_sequence": last_seq, "received_sequence": received_seq}
    )


def invalid_first_sequence(received: int) -> IngestError:
    return IngestError(
        error_code=IngestErrorCode.INVALID_FIRST_SEQUENCE,
        classification=ErrorClassification.HARD_REJECT,
        message="First event must have sequence_number=0",
        details={"received": received}
    )


def session_closed(session_id: str) -> IngestError:
    return IngestError(
        error_code=IngestErrorCode.SESSION_CLOSED,
        classification=ErrorClassification.HARD_REJECT,
        message="Session is closed; no backfill allowed",
        details={"session_id": session_id}
    )


def log_gap(expected_seq: int, received_seq: int) -> IngestError:
    return IngestError(
        error_code=IngestErrorCode.LOG_GAP,
        classification=ErrorClassification.PARTIAL_ACCEPT,
        message="Sequence gap detected",
        details={"expected_sequence": expected_seq, "received_sequence": received_seq}
    )


def accepted(event_id: str, event_hash: str) -> IngestError:
    return IngestError(
        error_code=IngestErrorCode.ACCEPTED,
        classification=ErrorClassification.ACCEPT,
        message="Event sealed",
        details={"event_id": event_id, "event_hash": event_hash}
    )
