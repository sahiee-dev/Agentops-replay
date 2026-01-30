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

import re
import json
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any


class Severity(Enum):
    """Finding severity levels."""
    ERROR = "ERROR"    # Structural violation - hard failure
    WARNING = "WARNING"  # Potential issue - advisory


@dataclass
class Finding:
    """A GDPR/privacy compliance finding."""
    severity: Severity
    event_index: int
    event_id: str
    field_path: str
    message: str
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the Finding into a plain dictionary for consumption by JSON serializers or logging.
        
        Returns:
            dict: Dictionary with keys "severity", "event_index", "event_id", "field_path", and "message".
                  "severity" contains the enum member's value; other keys contain the Finding's corresponding field values.
        """
        return {
            "severity": self.severity.value,
            "event_index": self.event_index,
            "event_id": self.event_id,
            "field_path": self.field_path,
            "message": self.message
        }


# Heuristic PII patterns (NOT exhaustive - never claim completeness)
PII_PATTERNS = {
    "email": re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', re.IGNORECASE),
    "phone": re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),
    "ssn": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
    "credit_card": re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'),
    "ip_address": re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'),
}

# Redaction marker
REDACTION_MARKER = "[REDACTED]"


def validate_redactions(events: List[Dict[str, Any]]) -> List[Finding]:
    """
    Verify that every "[REDACTED]" field in the provided events has a corresponding "<field>_hash" entry.
    
    Performs a structural validation across event payloads and records ERROR-level findings for:
    - Missing or empty "<field>_hash" entries for any field whose value is the REDACTION_MARKER.
    - Invalid JSON payloads when payload is a string.
    - Unexpected payload types (neither str, dict, nor list).
    
    Parameters:
        events (List[Dict[str, Any]]): Sequence of event objects; each event may include 'event_id' and a 'payload'
            (which can be a dict, list, or a JSON-encoded string).
    
    Returns:
        List[Finding]: A list of ERROR-severity Finding objects describing structural redaction violations.
    """
    findings = []
    
    for idx, event in enumerate(events):
        event_id = event.get('event_id', f'event_{idx}')
        payload = event.get('payload', {})
        
        if isinstance(payload, str):
            # Parse canonical JSON string and inspect
            try:
                parsed_payload = json.loads(payload)
            except json.JSONDecodeError as e:
                findings.append(Finding(
                    severity=Severity.ERROR,
                    event_index=idx,
                    event_id=event_id,
                    field_path="payload",
                    message=f"Payload is invalid JSON: {e}"
                ))
                continue
            
            if isinstance(parsed_payload, dict):
                _check_redactions_recursive(
                    data=parsed_payload,
                    path="payload",
                    event_index=idx,
                    event_id=event_id,
                    findings=findings
                )
            elif isinstance(parsed_payload, list):
                for i, item in enumerate(parsed_payload):
                    _check_redactions_recursive(
                        data=item,
                        path=f"payload[{i}]",
                        event_index=idx,
                        event_id=event_id,
                        findings=findings
                    )
            continue
        elif isinstance(payload, dict):
            _check_redactions_recursive(
                data=payload,
                path="payload",
                event_index=idx,
                event_id=event_id,
                findings=findings
            )
        elif isinstance(payload, list):
            for i, item in enumerate(payload):
                _check_redactions_recursive(
                    data=item,
                    path=f"payload[{i}]",
                    event_index=idx,
                    event_id=event_id,
                    findings=findings
                )
        else:
            # Unexpected payload type - report as ERROR
            findings.append(Finding(
                severity=Severity.ERROR,
                event_index=idx,
                event_id=event_id,
                field_path="payload",
                message=f"Unexpected payload type: {type(payload).__name__}. Expected str, dict, or list."
            ))
    
    return findings


def _check_redactions_recursive(
    data: Any,
    path: str,
    event_index: int,
    event_id: str,
    findings: List[Finding]
) -> None:
    """
    Recursively verify that any "[REDACTED]" value has a corresponding "<field>_hash" key present and non-empty.
    
    This function walks dictionaries and lists under `data` and, for each key whose value equals the module-level REDACTION_MARKER, appends a Severity.ERROR Finding to `findings` if the sibling key "<key>_hash" is missing or falsy. The `findings` list is mutated in place to record errors with the provided event context and field path.
    
    Parameters:
        data (Any): The node to inspect (dict, list, or nested combinations).
        path (str): Dotted/indexed path prefix for the current node (e.g., "payload.user" or "payload.items[0]").
        event_index (int): Numeric index of the event being inspected, used in created Findings.
        event_id (str): Identifier of the event being inspected, used in created Findings.
        findings (List[Finding]): Mutable list that will be appended with ERROR Findings for missing redaction hashes.
    """
    
    if isinstance(data, dict):
        for key, value in data.items():
            field_path = f"{path}.{key}"
            
            if value == REDACTION_MARKER:
                # Check for corresponding hash field
                hash_key = f"{key}_hash"
                if hash_key not in data or not data[hash_key]:
                    findings.append(Finding(
                        severity=Severity.ERROR,
                        event_index=event_index,
                        event_id=event_id,
                        field_path=field_path,
                        message=f"[REDACTED] field '{key}' missing corresponding '{hash_key}'"
                    ))
            elif isinstance(value, (dict, list)):
                _check_redactions_recursive(value, field_path, event_index, event_id, findings)
                
    elif isinstance(data, list):
        for i, item in enumerate(data):
            _check_redactions_recursive(item, f"{path}[{i}]", event_index, event_id, findings)


def check_pii_exposure(events: List[Dict[str, Any]]) -> List[Finding]:
    """
    Heuristically detects potential PII in event payloads and records findings for suspected exposures.
    
    Parameters:
        events (List[Dict[str, Any]]): Sequence of event objects; each should include a 'payload' (string, dict, or list) and may include 'event_id'.
    
    Returns:
        List[Finding]: WARNING-level findings for suspected PII matches. ERROR-level findings are produced only for unexpected payload types or invalid JSON payloads.
    """
    findings = []
    
    for idx, event in enumerate(events):
        event_id = event.get('event_id', f'event_{idx}')
        payload = event.get('payload', {})
        
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
                    _check_string_for_pii(str(parsed), "payload", idx, event_id, findings)
            except json.JSONDecodeError:
                # Not valid JSON - check as raw text
                _check_string_for_pii(payload, "payload", idx, event_id, findings)
        elif isinstance(payload, dict):
            _check_pii_recursive(payload, "payload", idx, event_id, findings)
        elif isinstance(payload, list):
            _check_pii_in_list(payload, "payload", idx, event_id, findings)
        else:
            # Unexpected payload type - report as ERROR and coerce to string for PII scan
            findings.append(Finding(
                severity=Severity.ERROR,
                event_index=idx,
                event_id=event_id,
                field_path="payload",
                message=f"Unexpected payload type: {type(payload).__name__}. Expected str, dict, or list."
            ))
            # Still scan the coerced string for PII
            _check_string_for_pii(str(payload), "payload", idx, event_id, findings)
    
    return findings


def _check_pii_in_list(
    data: list,
    path: str,
    event_index: int,
    event_id: str,
    findings: List[Finding]
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
    data: Any,
    path: str,
    event_index: int,
    event_id: str,
    findings: List[Finding]
) -> None:
    """
    Recursively scan a value for potential personally identifiable information (PII) and append any findings.
    
    Scans strings for heuristic PII patterns, traverses dictionaries and lists, and constructs field paths using dot notation for dict keys and `[index]` for list elements (e.g., "root.field[0].subfield").
    
    Parameters:
        data: The value to inspect; may be a str, dict, or list.
        path: Current field path used in findings (use an empty string or a root identifier when starting).
        event_index: Index of the event being inspected, recorded on any Finding.
        event_id: Identifier of the event being inspected, recorded on any Finding.
        findings: Mutable list to which discovered Finding instances will be appended.
    
    """
    
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
    value: str,
    path: str,
    event_index: int,
    event_id: str,
    findings: List[Finding]
) -> None:
    """
    Detect heuristic PII patterns in a string and record a WARNING finding when a pattern is matched.
    
    Skips scanning if the string is exactly the redaction marker. On the first matching PII pattern, appends a Finding with severity WARNING using the provided event context and field path, and stops further matching for that field (mutates the `findings` list).
    
    Parameters:
        value (str): The string to scan for PII.
        path (str): Dotted/indexed field path used in the resulting Finding.
        event_index (int): Index of the event containing the value.
        event_id (str): Identifier of the event containing the value.
        findings (List[Finding]): Mutable list to which any detected Finding will be appended.
    """
    
    # Skip ONLY if the entire value is exactly the redaction marker
    if value.strip() == REDACTION_MARKER:
        return
    
    for pii_type, pattern in PII_PATTERNS.items():
        if pattern.search(value):
            findings.append(Finding(
                severity=Severity.WARNING,
                event_index=event_index,
                event_id=event_id,
                field_path=path,
                message=f"Potential {pii_type} detected (heuristic, may be false positive)"
            ))
            # Only report first match per field to avoid spam
            break


def check_compliance(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Run heuristic compliance checks (redactions and PII exposure) across a sequence of events and return aggregated findings.
    
    Parameters:
        events (List[Dict[str, Any]]): Sequence of event objects to inspect. Each event may include an 'event_id' and a 'payload' (a dict, list, or a JSON-encoded string) that will be validated.
    
    Returns:
        Dict[str, Any]: Aggregated results with keys:
            - "errors": list of redaction findings (serialized dicts) with severity ERROR for structural redaction issues.
            - "warnings": list of PII findings (serialized dicts) with severity WARNING for heuristic potential exposures.
            - "summary": dict containing:
                - "total_errors" (int): number of ERROR findings.
                - "total_warnings" (int): number of WARNING findings.
                - "passed" (bool): true if there are no errors.
                - "note" (str): clarification that PII detection is heuristic and not a compliance certification.
    """
    redaction_findings = validate_redactions(events)
    pii_findings = check_pii_exposure(events)
    
    errors = [f for f in redaction_findings if f.severity == Severity.ERROR]
    warnings = pii_findings  # All PII findings are warnings
    
    return {
        "errors": [f.to_dict() for f in errors],
        "warnings": [f.to_dict() for f in warnings],
        "summary": {
            "total_errors": len(errors),
            "total_warnings": len(warnings),
            "passed": len(errors) == 0,
            "note": "PII detection is heuristic only. This is NOT a compliance certification."
        }
    }