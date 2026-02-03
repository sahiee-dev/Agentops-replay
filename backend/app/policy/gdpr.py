"""
gdpr.py - Non-destructive PII detection for GDPR compliance.

CONSTITUTIONAL REQUIREMENT: Detection does NOT mutate stored payloads.
Detection runs at EXPORT time only. Original hashes remain verifiable.
"""

import re
from typing import Any

from pydantic import BaseModel


class PIIMatch(BaseModel):
    """PII detection match result"""

    pattern_type: str  # "email", "phone", "ssn", "credit_card"
    matched_text: str
    location: str  # JSON path to the field
    confidence: str  # "high", "medium", "low"


# PII Detection Patterns
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE_US_PATTERN = re.compile(r"\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
PHONE_INTL_PATTERN = re.compile(r"\+\d{1,3}[-.\s]?\d{1,14}")
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CREDIT_CARD_PATTERN = re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b")


def detect_pii(payload: dict[str, Any], path: str = "$") -> list[PIIMatch]:
    """
    Detect PII in event payload.

    CRITICAL: This function does NOT mutate the payload.
    It only returns detected PII locations for flagging.

    Args:
        payload: Event payload dictionary
        path: JSON path (for recursive traversal)

    Returns:
        List of PII matches
    """
    matches = []

    if isinstance(payload, dict):
        for key, value in payload.items():
            new_path = f"{path}.{key}"
            matches.extend(detect_pii(value, new_path))

    elif isinstance(payload, list):
        for i, item in enumerate(payload):
            new_path = f"{path}[{i}]"
            matches.extend(detect_pii(item, new_path))

    elif isinstance(payload, str):
        # Check for email
        if EMAIL_PATTERN.search(payload):
            for match in EMAIL_PATTERN.finditer(payload):
                matches.append(
                    PIIMatch(
                        pattern_type="email",
                        matched_text=match.group(),
                        location=path,
                        confidence="high",
                    )
                )

        # Check for US phone
        if PHONE_US_PATTERN.search(payload):
            for match in PHONE_US_PATTERN.finditer(payload):
                matches.append(
                    PIIMatch(
                        pattern_type="phone_us",
                        matched_text=match.group(),
                        location=path,
                        confidence="high",
                    )
                )

        # Check for international phone
        if PHONE_INTL_PATTERN.search(payload):
            for match in PHONE_INTL_PATTERN.finditer(payload):
                matches.append(
                    PIIMatch(
                        pattern_type="phone_intl",
                        matched_text=match.group(),
                        location=path,
                        confidence="medium",
                    )
                )

        # Check for SSN
        if SSN_PATTERN.search(payload):
            for match in SSN_PATTERN.finditer(payload):
                matches.append(
                    PIIMatch(
                        pattern_type="ssn",
                        matched_text=match.group(),
                        location=path,
                        confidence="high",
                    )
                )

        # Check for credit card
        if CREDIT_CARD_PATTERN.search(payload):
            for match in CREDIT_CARD_PATTERN.finditer(payload):
                # Luhn algorithm check for credit cards
                if _luhn_check(match.group().replace("-", "").replace(" ", "")):
                    matches.append(
                        PIIMatch(
                            pattern_type="credit_card",
                            matched_text=match.group(),
                            location=path,
                            confidence="high",
                        )
                    )

    elif isinstance(payload, (int, float)) and not isinstance(payload, bool):
        # CRITICAL: Numeric PII detection (SSNs, phones, credit cards stored as numbers)
        payload_str = str(payload)
        # Strip all non-digits for reliable matching
        digits = re.sub(r"\D", "", payload_str)

        # Check for SSN pattern (exactly 9 digits)
        if re.fullmatch(r"\d{9}", digits):
            matches.append(
                PIIMatch(
                    pattern_type="ssn",
                    matched_text=payload_str,
                    location=path,
                    confidence="high",
                )
            )

        # Check for phone patterns (10-11 digits)
        if re.fullmatch(r"\d{10,11}", digits):
            matches.append(
                PIIMatch(
                    pattern_type="phone_us",
                    matched_text=payload_str,
                    location=path,
                    confidence="medium",
                )
            )

        # Check for credit card (13-19 digits with Luhn validation)
        if re.fullmatch(r"\d{13,19}", digits) and _luhn_check(digits):
            matches.append(
                PIIMatch(
                    pattern_type="credit_card",
                    matched_text=payload_str,
                    location=path,
                    confidence="high",
                )
            )

    return matches


def _luhn_check(card_number: str) -> bool:
    """
    Validate credit card number using Luhn algorithm.

    Args:
        card_number: Card number string (digits only)

    Returns:
        True if valid card number
    """
    if not card_number.isdigit():
        return False

    digits = [int(d) for d in card_number]
    checksum = 0

    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit

    return checksum % 10 == 0


def scan_session_for_pii(events: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Scan entire session for PII.

    Returns summary of PII exposure.

    Args:
        events: List of event dictionaries

    Returns:
        dict with 'has_pii', 'total_matches', 'matches_by_type', 'flagged_events'
    """
    all_matches = []
    flagged_events = []

    for i, event in enumerate(events):
        payload = event.get("payload", {})
        matches = detect_pii(payload)

        if matches:
            flagged_events.append(
                {
                    "event_index": i,
                    "event_id": event.get("event_id"),
                    "event_type": event.get("event_type"),
                    "match_count": len(matches),
                    "matches": [m.dict() for m in matches],
                }
            )
            all_matches.extend(matches)

    # Group by type
    matches_by_type = {}
    for match in all_matches:
        pii_type = match.pattern_type
        if pii_type not in matches_by_type:
            matches_by_type[pii_type] = 0
        matches_by_type[pii_type] += 1

    return {
        "has_pii": len(all_matches) > 0,
        "total_matches": len(all_matches),
        "matches_by_type": matches_by_type,
        "flagged_events": flagged_events,
    }
