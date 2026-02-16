"""
gdpr_policy.py - GDPR compliance policy adapter.

Wraps the existing gdpr.py module's check_pii_exposure() and validate_redactions()
functions, mapping their Finding output to ViolationRecord.

STRUCTURAL PURITY:
- No database imports
- No network access
- No environment access for logic
- Receives CanonicalEvent, not raw dicts

CONSTRAINT: This is HEURISTIC detection, NOT compliance certification.
Violation descriptions must state this explicitly.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from app.compliance.gdpr import Severity as GdprSeverity
from app.compliance.gdpr import check_pii_exposure, validate_redactions
from app.services.policy.engine import CanonicalEvent, Policy, ViolationRecord


class GDPRPolicy(Policy):
    """
    GDPR privacy compliance policy.

    Runs two checks:
    1. Redaction integrity: [REDACTED] fields must have corresponding hashes
    2. PII exposure: Heuristic scan for common PII patterns

    Output severity mapping:
    - gdpr.Severity.ERROR → ViolationSeverity.ERROR (structural)
    - gdpr.Severity.WARNING → ViolationSeverity.WARNING (heuristic)
    """

    name = "gdpr"
    version = "1.0.0"

    def evaluate(
        self,
        events: list[CanonicalEvent],
        policy_version: str,
        policy_hash: str,
    ) -> list[ViolationRecord]:
        """
        Evaluate GDPR compliance over canonical events.

        Converts CanonicalEvent → event dict format expected by gdpr.py,
        then maps Finding → ViolationRecord.
        """
        # Convert CanonicalEvent to the dict format gdpr.py expects
        event_dicts = _to_gdpr_event_dicts(events)

        # Run both checks
        redaction_findings = validate_redactions(event_dicts)
        pii_findings = check_pii_exposure(event_dicts)

        violations: list[ViolationRecord] = []

        # Map redaction findings
        for finding in redaction_findings:
            canonical_event = _find_event_by_index(events, finding.event_index)
            if canonical_event is None:
                continue

            violations.append(
                ViolationRecord(
                    id=str(uuid.uuid4()),
                    session_id=canonical_event.session_id,
                    event_id=canonical_event.event_id,
                    event_sequence_number=canonical_event.sequence_number,
                    policy_name="GDPR_REDACTION_INTEGRITY",
                    policy_version=policy_version,
                    policy_hash=policy_hash,
                    severity=_map_severity(finding.severity),
                    description=finding.message,
                    metadata={
                        "field_path": finding.field_path,
                        "check_type": "redaction_integrity",
                        "note": "Structural check. Missing hash for redacted field.",
                    },
                )
            )

        # Map PII findings
        for finding in pii_findings:
            canonical_event = _find_event_by_index(events, finding.event_index)
            if canonical_event is None:
                continue

            violations.append(
                ViolationRecord(
                    id=str(uuid.uuid4()),
                    session_id=canonical_event.session_id,
                    event_id=canonical_event.event_id,
                    event_sequence_number=canonical_event.sequence_number,
                    policy_name="GDPR_PII_DETECTED",
                    policy_version=policy_version,
                    policy_hash=policy_hash,
                    severity=_map_severity(finding.severity),
                    description=finding.message,
                    metadata={
                        "field_path": finding.field_path,
                        "check_type": "pii_heuristic",
                        "note": "Heuristic detection. May be false positive. "
                        "This is NOT a compliance certification.",
                    },
                )
            )

        return violations


def _to_gdpr_event_dicts(events: list[CanonicalEvent]) -> list[dict[str, Any]]:
    """Convert CanonicalEvent list to the dict format expected by gdpr.py."""
    result = []
    for event in events:
        try:
            payload = json.loads(event.payload_canonical)
        except json.JSONDecodeError:
            payload = event.payload_canonical

        result.append(
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "payload": payload,
            }
        )
    return result


def _find_event_by_index(
    events: list[CanonicalEvent], index: int
) -> CanonicalEvent | None:
    """Safely get event by index."""
    if 0 <= index < len(events):
        return events[index]
    return None


def _map_severity(gdpr_severity: GdprSeverity) -> str:
    """Map gdpr.Severity to ViolationSeverity string."""
    if gdpr_severity == GdprSeverity.ERROR:
        return "ERROR"
    return "WARNING"
