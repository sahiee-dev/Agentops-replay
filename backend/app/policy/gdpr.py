"""
gdpr.py - Non-destructive PII detection for GDPR compliance.

CONSTITUTIONAL REQUIREMENT: Detection does NOT mutate stored payloads.
Detection runs at EXPORT time only. Original hashes remain verifiable.
"""

import re
from typing import List, Dict, Any
from pydantic import BaseModel


class PIIMatch(BaseModel):
    """PII detection match result"""
    pattern_type: str  # "email", "phone", "ssn", "credit_card"
    matched_text: str
    location: str  # JSON path to the field
    confidence: str  # "high", "medium", "low"


# PII Detection Patterns
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
PHONE_US_PATTERN = re.compile(r'\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')
PHONE_INTL_PATTERN = re.compile(r'\+\d{1,3}[-.\s]?\d{1,14}')
SSN_PATTERN = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
CREDIT_CARD_PATTERN = re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b')


def detect_pii(payload: Dict[str, Any], path: str = "$") -> List[PIIMatch]:
    """
    Recursively scan a payload for personal identifiable information (PII) and return structured match entries.
    
    Parameters:
        payload (dict | list | str): The event payload to inspect; may be a nested dict, list, or string.
        path (str): JSON-path-like location of `payload` within the original document (used in returned matches).
    
    Returns:
        List[PIIMatch]: A list of PIIMatch instances describing each detected PII occurrence (pattern_type, matched_text, location, confidence).
    
    Notes:
        This function does not mutate the input `payload`; it only inspects values and returns detection metadata.
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
                matches.append(PIIMatch(
                    pattern_type="email",
                    matched_text=match.group(),
                    location=path,
                    confidence="high"
                ))
        
        # Check for US phone
        if PHONE_US_PATTERN.search(payload):
            for match in PHONE_US_PATTERN.finditer(payload):
                matches.append(PIIMatch(
                    pattern_type="phone_us",
                    matched_text=match.group(),
                    location=path,
                    confidence="high"
                ))
        
        # Check for international phone
        if PHONE_INTL_PATTERN.search(payload):
            for match in PHONE_INTL_PATTERN.finditer(payload):
                matches.append(PIIMatch(
                    pattern_type="phone_intl",
                    matched_text=match.group(),
                    location=path,
                    confidence="medium"
                ))
        
        # Check for SSN
        if SSN_PATTERN.search(payload):
            for match in SSN_PATTERN.finditer(payload):
                matches.append(PIIMatch(
                    pattern_type="ssn",
                    matched_text=match.group(),
                    location=path,
                    confidence="high"
                ))
        
        # Check for credit card
        if CREDIT_CARD_PATTERN.search(payload):
            for match in CREDIT_CARD_PATTERN.finditer(payload):
                # Luhn algorithm check for credit cards
                if _luhn_check(match.group().replace('-', '').replace(' ', '')):
                    matches.append(PIIMatch(
                        pattern_type="credit_card",
                        matched_text=match.group(),
                        location=path,
                        confidence="high"
                    ))
    
    return matches


def _luhn_check(card_number: str) -> bool:
    """
    Determine whether a numeric string is a valid credit card number using the Luhn algorithm.
    
    Parameters:
        card_number (str): String containing digits only to validate.
    
    Returns:
        `true` if the card number passes the Luhn check, `false` otherwise.
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


def scan_session_for_pii(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Scan a list of event dictionaries for PII and produce a summary of detected matches.
    
    Parameters:
        events (List[Dict[str, Any]]): Events to scan; each event is a dict that may contain a 'payload' key.
    
    Returns:
        Dict[str, Any]: Summary with the following keys:
            - has_pii (bool): `true` if any PII matches were found, `false` otherwise.
            - total_matches (int): Total number of PII matches across all events.
            - matches_by_type (Dict[str, int]): Mapping from PII type (e.g., "email", "ssn") to count of matches.
            - flagged_events (List[Dict[str, Any]]): Per-event summaries for events that contained matches. Each summary includes:
                - event_index (int): Index of the event in the input list.
                - event_id: The event's 'event_id' value, if present.
                - event_type: The event's 'event_type' value, if present.
                - match_count (int): Number of matches in the event's payload.
                - matches (List[Dict]): List of detected matches represented as dicts (PIIMatch.dict()).
    """
    all_matches = []
    flagged_events = []
    
    for i, event in enumerate(events):
        payload = event.get('payload', {})
        matches = detect_pii(payload)
        
        if matches:
            flagged_events.append({
                'event_index': i,
                'event_id': event.get('event_id'),
                'event_type': event.get('event_type'),
                'match_count': len(matches),
                'matches': [m.dict() for m in matches]
            })
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
        "flagged_events": flagged_events
    }