"""
violation.py - Pydantic schemas for Violation API responses.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ViolationRead(BaseModel):
    """Read-only violation record."""

    id: str = Field(..., description="Violation UUID")
    session_id: str = Field(..., description="Session UUID")
    event_id: str = Field(..., description="Event that triggered the violation")
    event_sequence_number: int = Field(
        ..., description="Immutable ordering anchor"
    )
    policy_name: str = Field(..., description="Policy identifier")
    policy_version: str = Field(..., description="Policy set version")
    policy_hash: str = Field(
        ..., description="SHA-256(policy source + config)"
    )
    severity: str = Field(..., description="WARNING | ERROR | CRITICAL")
    description: str = Field(..., description="Violation description")
    metadata_json: str | None = Field(
        None, description="JSON-serialized policy-specific context"
    )
    created_at: datetime = Field(
        ..., description="Transaction commit timestamp"
    )

    class Config:
        from_attributes = True


class ViolationSummary(BaseModel):
    """Paginated violation list response."""

    total: int = Field(..., description="Total matching violations")
    violations: list[ViolationRead] = Field(
        ..., description="Violation records"
    )
