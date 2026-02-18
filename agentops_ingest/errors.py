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
        """
        Serialize the IngestError into a plain dictionary suitable for external consumption.
        
        Returns:
            dict: Dictionary with keys:
                - error_code (str): string value of the error code.
                - classification (str): string value of the error classification.
                - message (str): human-readable error message.
                - details (dict): additional context; empty dict if no details were set.
        """
        return {
            "error_code": self.error_code.value,
            "classification": self.classification.value,
            "message": self.message,
            "details": self.details or {}
        }


class IngestException(Exception):
    """Exception raised for hard rejections."""
    def __init__(self, error: IngestError):
        """
        Create an IngestException that carries an IngestError payload.
        
        Parameters:
            error (IngestError): The immutable error object to attach to this exception. The exception's message is set to `error.message`.
        """
        self.error = error
        super().__init__(error.message)


# Pre-defined error factories for consistency
def schema_invalid(details: Dict[str, Any]) -> IngestError:
    """
    Create an IngestError representing a JSON schema violation.
    
    Parameters:
        details (Dict[str, Any]): Additional context to include in the error's `details` field.
    
    Returns:
        IngestError: An error with code `SCHEMA_INVALID`, classification `HARD_REJECT`, message "JSON schema violation", and the provided details.
    """
    return IngestError(
        error_code=IngestErrorCode.SCHEMA_INVALID,
        classification=ErrorClassification.HARD_REJECT,
        message="JSON schema violation",
        details=details
    )


def jcs_invalid(details: Dict[str, Any]) -> IngestError:
    """
    Create an IngestError for a payload canonicalization failure (JCS / RFC 8785).
    
    Parameters:
        details (Dict[str, Any]): Additional context to include in the error's details field.
    
    Returns:
        ingest_error (IngestError): Error with code `JCS_INVALID`, classification `HARD_REJECT`, message "Cannot canonicalize payload (RFC 8785)", and the provided details.
    """
    return IngestError(
        error_code=IngestErrorCode.JCS_INVALID,
        classification=ErrorClassification.HARD_REJECT,
        message="Cannot canonicalize payload (RFC 8785)",
        details=details
    )


def timestamp_invalid(details: Dict[str, Any]) -> IngestError:
    """
    Create an IngestError representing a malformed or missing timestamp.
    
    Parameters:
        details (Dict[str, Any]): Optional context for the error (e.g., offending field name, provided value, parsing error messages).
    
    Returns:
        IngestError: Error with code `TIMESTAMP_INVALID`, classification `HARD_REJECT`, message "Malformed or missing timestamp", and the provided `details`.
    """
    return IngestError(
        error_code=IngestErrorCode.TIMESTAMP_INVALID,
        classification=ErrorClassification.HARD_REJECT,
        message="Malformed or missing timestamp",
        details=details
    )


def authority_leak() -> IngestError:
    """
    Create an IngestError for a client assertion of authority.
    
    Returns:
        IngestError: error_code `AUTHORITY_LEAK`, classification `HARD_REJECT`, message "Client attempted to assert authority (event_hash or chain_authority present)", and an empty `details` dictionary.
    """
    return IngestError(
        error_code=IngestErrorCode.AUTHORITY_LEAK,
        classification=ErrorClassification.HARD_REJECT,
        message="Client attempted to assert authority (event_hash or chain_authority present)",
        details={}
    )


def payload_hash_mismatch(expected: str, received: str) -> IngestError:
    """
    Create an IngestError for a payload-hash mismatch between client and server.
    
    Parameters:
        expected (str): The recomputed payload hash (hex-encoded) expected by the server.
        received (str): The payload_hash provided by the client (hex-encoded).
    
    Returns:
        IngestError: Error with code `PAYLOAD_HASH_MISMATCH`, classification `HARD_REJECT`,
        message "Client-provided payload_hash does not match recomputed hash", and
        details containing the `expected` and `received` hash values.
    """
    return IngestError(
        error_code=IngestErrorCode.PAYLOAD_HASH_MISMATCH,
        classification=ErrorClassification.HARD_REJECT,
        message="Client-provided payload_hash does not match recomputed hash",
        details={"expected": expected, "received": received}
    )


def sequence_rewind(last_seq: int, received_seq: int) -> IngestError:
    """
    Create an IngestError for a sequence rewind where the received sequence is not greater than the last accepted sequence.
    
    Parameters:
        last_seq (int): The last accepted sequence number.
        received_seq (int): The sequence number received from the client.
    
    Returns:
        IngestError: An error with code `SEQUENCE_REWIND`, classification `HARD_REJECT`, message "Sequence number <= last accepted sequence", and `details` containing `last_sequence` and `received_sequence`.
    """
    return IngestError(
        error_code=IngestErrorCode.SEQUENCE_REWIND,
        classification=ErrorClassification.HARD_REJECT,
        message="Sequence number <= last accepted sequence",
        details={"last_sequence": last_seq, "received_sequence": received_seq}
    )


def invalid_first_sequence(received: int) -> IngestError:
    """
    Constructs an IngestError for a violation where the first event's sequence number is not zero.
    
    Parameters:
        received (int): The sequence number provided by the client for the first event.
    
    Returns:
        ingest_error (IngestError): An error with code `INVALID_FIRST_SEQUENCE`, classification `HARD_REJECT`, a message stating the first event must have `sequence_number=0`, and `details` containing the provided `received` value.
    """
    return IngestError(
        error_code=IngestErrorCode.INVALID_FIRST_SEQUENCE,
        classification=ErrorClassification.HARD_REJECT,
        message="First event must have sequence_number=0",
        details={"received": received}
    )


def session_closed(session_id: str) -> IngestError:
    """
    Create an IngestError indicating the ingestion session is closed and backfill is not allowed.
    
    Parameters:
        session_id (str): Identifier of the session that is closed.
    
    Returns:
        IngestError: Error with code `SESSION_CLOSED`, classification `HARD_REJECT`, a message explaining backfill is disallowed, and `details` containing the provided `session_id`.
    """
    return IngestError(
        error_code=IngestErrorCode.SESSION_CLOSED,
        classification=ErrorClassification.HARD_REJECT,
        message="Session is closed; no backfill allowed",
        details={"session_id": session_id}
    )


def log_gap(expected_seq: int, received_seq: int) -> IngestError:
    """
    Create an IngestError representing a detected sequence gap during ingestion.
    
    Parameters:
        expected_seq (int): The sequence number that was expected (next in-order).
        received_seq (int): The sequence number actually received.
    
    Returns:
        IngestError: Error with code `LOG_GAP`, classification `PARTIAL_ACCEPT`, message
        "Sequence gap detected", and details containing `expected_sequence` and
        `received_sequence`.
    """
    return IngestError(
        error_code=IngestErrorCode.LOG_GAP,
        classification=ErrorClassification.PARTIAL_ACCEPT,
        message="Sequence gap detected",
        details={"expected_sequence": expected_seq, "received_sequence": received_seq}
    )


def accepted(event_id: str, event_hash: str) -> IngestError:
    """
    Create an IngestError representing a successfully accepted event.
    
    Parameters:
        event_id (str): The event's unique identifier.
        event_hash (str): The event's canonical payload hash.
    
    Returns:
        IngestError: An error object with code `ACCEPTED`, classification `ACCEPT`, message "Event sealed", and `details` containing `event_id` and `event_hash`.
    """
    return IngestError(
        error_code=IngestErrorCode.ACCEPTED,
        classification=ErrorClassification.ACCEPT,
        message="Event sealed",
        details={"event_id": event_id, "event_hash": event_hash}
    )