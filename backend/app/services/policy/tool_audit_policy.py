"""
tool_audit_policy.py - Tool usage audit policy.

Checks that tool calls reference only tools in the allowed list
defined in policy.yaml.

STRUCTURAL PURITY:
- No database imports
- No network access
- Input: CanonicalEvent list + config from PolicyEngine

LANGUAGE CONSTRAINT (CONSTITUTION §3):
- Does NOT infer intent or judge behavior
- States factual policy violation only
- Example: "Tool X not in allowed list per policy.yaml v1.0.0"
- NOT: "Unauthorized behavior detected"
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from app.services.policy.engine import CanonicalEvent, Policy, ViolationRecord


class ToolAuditPolicy(Policy):
    """
    Audit tool calls against an allowed list.

    Configuration (from policy.yaml):
        policies:
          tool_audit:
            enabled: true
            allowed_tools:
              - "web_search"
              - "calculator"
    """

    name = "tool_audit"
    version = "1.0.0"

    def __init__(self, allowed_tools: list[str] | None = None) -> None:
        self._allowed_tools: set[str] = set(allowed_tools or [])

    def configure(self, config: dict[str, Any]) -> None:
        """Load allowed_tools from policy config."""
        tools = config.get("allowed_tools", [])
        if isinstance(tools, list):
            self._allowed_tools = set(tools)

    def evaluate(
        self,
        events: list[CanonicalEvent],
        policy_version: str,
        policy_hash: str,
    ) -> list[ViolationRecord]:
        """
        Check that all TOOL_CALL events reference allowed tools.

        Emits CRITICAL severity for tools not in the allowed list.
        If allowed_tools is empty, no violations are generated (permissive).
        """
        if not self._allowed_tools:
            # No allowlist configured — skip audit (permissive mode)
            return []

        violations: list[ViolationRecord] = []

        for event in events:
            if event.event_type != "TOOL_CALL":
                continue

            tool_name = _extract_tool_name(event)
            if tool_name is None:
                violations.append(
                    ViolationRecord(
                        id=str(uuid.uuid4()),
                        session_id=event.session_id,
                        event_id=event.event_id,
                        event_sequence_number=event.sequence_number,
                        policy_name="TOOL_CALL_UNPARSEABLE",
                        policy_version=policy_version,
                        policy_hash=policy_hash,
                        severity="ERROR",
                        description="Unparseable TOOL_CALL payload. Missing or invalid tool_name.",
                        metadata={
                            "raw_payload": event.payload_canonical[:200]  # Truncate for safety
                        },
                    )
                )
                continue

            if tool_name not in self._allowed_tools:
                violations.append(
                    ViolationRecord(
                        id=str(uuid.uuid4()),
                        session_id=event.session_id,
                        event_id=event.event_id,
                        event_sequence_number=event.sequence_number,
                        policy_name="TOOL_NOT_IN_ALLOWED_LIST",
                        policy_version=policy_version,
                        policy_hash=policy_hash,
                        severity="CRITICAL",
                        description=(
                            f"Tool '{tool_name}' not in allowed list "
                            f"per policy.yaml v{policy_version}"
                        ),
                        metadata={
                            "tool_name": tool_name,
                            "allowed_tools": sorted(self._allowed_tools),
                        },
                    )
                )

        return violations


def _extract_tool_name(event: CanonicalEvent) -> str | None:
    """Extract tool_name from a TOOL_CALL event's canonical payload."""
    try:
        payload = json.loads(event.payload_canonical)
        if isinstance(payload, dict):
            return payload.get("tool_name")
    except (json.JSONDecodeError, TypeError):
        pass
    return None
