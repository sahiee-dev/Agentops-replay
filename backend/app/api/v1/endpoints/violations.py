"""
violations.py - Violation API endpoints.

Read-only. No mutation. No soft delete.
Violations are derived artifacts and immutable once persisted.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models.violation import Violation
from app.schemas.violation import ViolationRead, ViolationSummary

router = APIRouter()


def _to_read(v: Violation) -> ViolationRead:
    """Convert Violation ORM model to ViolationRead schema."""
    return ViolationRead(
        id=str(v.id),
        session_id=str(v.session_id),
        event_id=str(v.event_id),
        event_sequence_number=int(v.event_sequence_number),  # type: ignore[arg-type]
        policy_name=str(v.policy_name),
        policy_version=str(v.policy_version),
        policy_hash=str(v.policy_hash),
        severity=str(v.severity),
        description=str(v.description),
        metadata_json=str(v.metadata_json) if v.metadata_json else None,
        created_at=v.created_at,  # type: ignore[arg-type]
    )


@router.get(
    "/{session_id}",
    response_model=list[ViolationRead],
    summary="Get violations for a session",
)
def get_violations_for_session(
    session_id: str,
    severity: str | None = Query(None, description="Filter by severity"),
    policy_name: str | None = Query(None, description="Filter by policy name"),
    db: DBSession = Depends(get_db),
) -> list[ViolationRead]:
    """
    Retrieve all violations for a session.

    Read-only. No mutation endpoints exist.
    """
    query = db.query(Violation).filter(Violation.session_id == session_id)

    if severity:
        query = query.filter(Violation.severity == severity)
    if policy_name:
        query = query.filter(Violation.policy_name == policy_name)

    violations = query.order_by(Violation.event_sequence_number).all()

    return [_to_read(v) for v in violations]


@router.get(
    "",
    response_model=ViolationSummary,
    summary="Get violation summary with filters",
)
def list_violations(
    severity: str | None = Query(None, description="Filter by severity"),
    policy_name: str | None = Query(None, description="Filter by policy name"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: DBSession = Depends(get_db),
) -> ViolationSummary:
    """
    List violations with pagination and filters.

    Read-only. No mutation endpoints exist.
    """
    query = db.query(Violation)

    if severity:
        query = query.filter(Violation.severity == severity)
    if policy_name:
        query = query.filter(Violation.policy_name == policy_name)

    total = query.count()
    violations = (
        query.order_by(Violation.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return ViolationSummary(
        total=total,
        violations=[_to_read(v) for v in violations],
    )
