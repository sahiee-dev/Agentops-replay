"""
violation.py - Violation model for policy evaluation records.

Violations are DERIVED ARTIFACTS computed over committed events.
They are NOT primary evidence. They are immutable once persisted.

CONSTITUTIONAL CONSTRAINTS:
1. Violations never modify or annotate events
2. Violations are append-only (no update, no delete)
3. Every violation is anchored to an immutable event via event_id + event_sequence_number
4. Every violation records the policy_version and policy_hash that produced it
5. policy_hash = SHA-256(policy source + canonical policy config subset)
"""

from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database import Base


class ViolationSeverity(str, Enum):
    """Severity levels for policy violations."""

    WARNING = "WARNING"    # Heuristic finding (e.g., potential PII detected)
    ERROR = "ERROR"        # Structural violation (e.g., missing redaction hash)
    CRITICAL = "CRITICAL"  # High-risk violation (e.g., unauthorized tool usage)


class Violation(Base):
    """
    Immutable record of a policy violation.

    Each violation is:
    - Linked to the specific event that triggered it (event_id + event_sequence_number)
    - Tagged with the exact policy version and source hash that produced it
    - Never modified or deleted after creation
    """

    __tablename__ = "violations"

    id = Column(String, primary_key=True)  # UUID string
    session_id = Column(
        String(36),
        ForeignKey("sessions.session_id_str"),
        nullable=False,
        index=True,
    )
    event_id = Column(String, nullable=False)  # References event_chains.event_id
    event_sequence_number = Column(Integer, nullable=False)  # Immutable ordering anchor
    policy_name = Column(String, nullable=False, index=True)  # e.g., "GDPR_PII_DETECTED"
    policy_version = Column(String, nullable=False)  # Semantic version of policy set
    policy_hash = Column(String, nullable=False)  # SHA-256(source + config)
    severity = Column(String, nullable=False, index=True)  # ViolationSeverity value
    description = Column(Text, nullable=False)
    metadata_json = Column(Text, nullable=True)  # JSON-serialized policy-specific context
    created_at = Column(DateTime, nullable=False)  # Transaction commit timestamp
