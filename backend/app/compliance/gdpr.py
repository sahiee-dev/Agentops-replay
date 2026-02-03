"""
gdpr.py - Privacy compliance checks with severity levels.

CRITICAL CONSTRAINTS:
1. This is HEURISTIC detection, NOT compliance certification
2. Never claims completeness
3. Records evidence, does not enforce policy retroactively
4. Flags violations, does not erase history

Severity Levels:
- ERROR: Structural violation (missing hash for redacted field) - HARD FAILURE
- WARNING: Potential PII exposure (heuristic detection) - ADVISORY ONLY
"""

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class Severity(Enum):
    """Finding severity levels."""

    ERROR = "ERROR"  # Structural violation - hard failure
    WARNING = "WARNING"  # Potential issue - advisory


@dataclass
class Finding:
    """A GDPR/privacy compliance finding."""

    severity: Severity
    event_index: int
    event_id: str
    field_path: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity.value,
            "event_index": self.event_index,
            "event_id": self.event_id,
            "field_path": self.field_path,
            "message": self.message,
        }


# Heuristic PII patterns (NOT exhaustive - never claim completeness)
PII_PATTERNS = {
    "email": re.compile(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", re.IGNORECASE
    ),
    "phone": re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
    "ip_address": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
}

# Redaction marker
REDACTION_MARKER = "[REDACTED]"


def validate_redactions(events: list[dict[str, Any]]) -> list[Finding]:
    """
    Validate that all redacted fields have corresponding hashes.

    This is a STRUCTURAL check - ERROR severity.
    A [REDACTED] field without a corresponding hash is a hard failure.

    Args:
        events: List of event dictionaries from export

    Returns:
        List of Finding objects (ERROR severity only)
    """
    findings = []

    for idx, event in enumerate(events):
        event_id = event.get("event_id", f"event_{idx}")
        payload = event.get("payload", {})

        if isinstance(payload, str):
            # Parse canonical JSON string and inspect
            try:
                parsed_payload = json.loads(payload)
            except json.JSONDecodeError as e:
                findings.append(
                    Finding(
                        severity=Severity.ERROR,
                        event_index=idx,
                        event_id=event_id,
                        field_path="payload",
                        message=f"Payload is invalid JSON: {e}",
                    )
                )
                continue

            if isinstance(parsed_payload, dict):
                _check_redactions_recursive(
                    data=parsed_payload,
                    path="payload",
                    event_index=idx,
                    event_id=event_id,
                    findings=findings,
                )
            elif isinstance(parsed_payload, list):
                for i, item in enumerate(parsed_payload):
                    _check_redactions_recursive(
                        data=item,
                        path=f"payload[{i}]",
                        event_index=idx,
                        event_id=event_id,
                        findings=findings,
                    )
            continue
        elif isinstance(payload, dict):
            _check_redactions_recursive(
                data=payload,
                path="payload",
                event_index=idx,
                event_id=event_id,
                findings=findings,
            )
        elif isinstance(payload, list):
            for i, item in enumerate(payload):
                _check_redactions_recursive(
                    data=item,
                    path=f"payload[{i}]",
                    event_index=idx,
                    event_id=event_id,
                    findings=findings,
                )
        else:
            # Unexpected payload type - report as ERROR
            findings.append(
                Finding(
                    severity=Severity.ERROR,
                    event_index=idx,
                    event_id=event_id,
                    field_path="payload",
                    message=f"Unexpected payload type: {type(payload).__name__}. Expected str, dict, or list.",
                )
            )

    return findings


def _check_redactions_recursive(
    data: Any, path: str, event_index: int, event_id: str, findings: list[Finding]
) -> None:
    """Recursively check for [REDACTED] without corresponding hash."""

    if isinstance(data, dict):
        for key, value in data.items():
            field_path = f"{path}.{key}"

            if value == REDACTION_MARKER:
                # Check for corresponding hash field
                hash_key = f"{key}_hash"
                if hash_key not in data or not data[hash_key]:
                    findings.append(
                        Finding(
                            severity=Severity.ERROR,
                            event_index=event_index,
                            event_id=event_id,
                            field_path=field_path,
                            message=f"[REDACTED] field '{key}' missing corresponding '{hash_key}'",
                        )
                    )
            elif isinstance(value, (dict, list)):
                _check_redactions_recursive(
                    value, field_path, event_index, event_id, findings
                )

    elif isinstance(data, list):
        for i, item in enumerate(data):
            _check_redactions_recursive(
                item, f"{path}[{i}]", event_index, event_id, findings
            )


def check_pii_exposure(events: list[dict[str, Any]]) -> list[Finding]:
    """
    Heuristic check for potential PII exposure in unredacted fields.

    This is a HEURISTIC check - WARNING severity only.
    Does NOT claim completeness. Does NOT enforce policy.

    Args:
        events: List of event dictionaries from export

    Returns:
        List of Finding objects (WARNING severity only, ERROR for unexpected types)
    """
    findings = []

    for idx, event in enumerate(events):
        event_id = event.get("event_id", f"event_{idx}")
        payload = event.get("payload", {})

        if isinstance(payload, str):
            # Attempt to parse JSON string into structured data
            try:
                parsed = json.loads(payload)
                if isinstance(parsed, dict):
                    _check_pii_recursive(parsed, "payload", idx, event_id, findings)
                elif isinstance(parsed, list):
                    _check_pii_in_list(parsed, "payload", idx, event_id, findings)
                else:
                    # Parsed to a primitive - check as string
                    _check_string_for_pii(
                        str(parsed), "payload", idx, event_id, findings
                    )
            except json.JSONDecodeError:
                # Not valid JSON - check as raw text
                _check_string_for_pii(payload, "payload", idx, event_id, findings)
        elif isinstance(payload, dict):
            _check_pii_recursive(payload, "payload", idx, event_id, findings)
        elif isinstance(payload, list):
            _check_pii_in_list(payload, "payload", idx, event_id, findings)
        else:
            # Unexpected payload type - report as ERROR and coerce to string for PII scan
            findings.append(
                Finding(
                    severity=Severity.ERROR,
                    event_index=idx,
                    event_id=event_id,
                    field_path="payload",
                    message=f"Unexpected payload type: {type(payload).__name__}. Expected str, dict, or list.",
                )
            )
            # Still scan the coerced string for PII
            _check_string_for_pii(str(payload), "payload", idx, event_id, findings)

    return findings


def _check_pii_in_list(
    data: list, path: str, event_index: int, event_id: str, findings: list[Finding]
) -> None:
    """Check list items for potential PII."""
    for i, item in enumerate(data):
        item_path = f"{path}[{i}]"
        if isinstance(item, dict):
            _check_pii_recursive(item, item_path, event_index, event_id, findings)
        elif isinstance(item, list):
            _check_pii_in_list(item, item_path, event_index, event_id, findings)
        elif isinstance(item, str):
            _check_string_for_pii(item, item_path, event_index, event_id, findings)


def _check_pii_recursive(
    data: Any, path: str, event_index: int, event_id: str, findings: list[Finding]
) -> None:
    """Recursively check for potential PII in data."""

    if isinstance(data, str):
        _check_string_for_pii(data, path, event_index, event_id, findings)
    elif isinstance(data, dict):
        for key, value in data.items():
            field_path = f"{path}.{key}"
            _check_pii_recursive(value, field_path, event_index, event_id, findings)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            _check_pii_recursive(item, f"{path}[{i}]", event_index, event_id, findings)


def _check_string_for_pii(
    value: str, path: str, event_index: int, event_id: str, findings: list[Finding]
) -> None:
    """Check a string value for PII patterns."""

    # Skip ONLY if the entire value is exactly the redaction marker
    if value.strip() == REDACTION_MARKER:
        return

    for pii_type, pattern in PII_PATTERNS.items():
        if pattern.search(value):
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    event_index=event_index,
                    event_id=event_id,
                    field_path=path,
                    message=f"Potential {pii_type} detected (heuristic, may be false positive)",
                )
            )
            # Only report first match per field to avoid spam
            break


def check_compliance(events: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Run all compliance checks and return summary.

    Returns:
        Dict with 'errors', 'warnings', and 'summary' keys
    """
    redaction_findings = validate_redactions(events)
    pii_findings = check_pii_exposure(events)

    errors = [f for f in redaction_findings if f.severity == Severity.ERROR]
    # Add PII errors to errors list
    pii_errors = [f for f in pii_findings if f.severity == Severity.ERROR]
    errors.extend(pii_errors)

    # Warnings are only non-error PII findings
    warnings = [f for f in pii_findings if f.severity != Severity.ERROR]

    return {
        "errors": [f.to_dict() for f in errors],
        "warnings": [f.to_dict() for f in warnings],
        "summary": {
            "total_errors": len(errors),
            "total_warnings": len(warnings),
            "passed": len(errors) == 0,
            "note": "PII detection is heuristic only. This is NOT a compliance certification.",
        },
    }
