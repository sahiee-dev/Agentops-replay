"""
conftest.py - Fixtures for Worker atomicity tests.

Test strategy:
- Real PostgreSQL test database for transaction semantics
- Mocked Redis client (no real Redis needed)
- Mocked/injectable PolicyEngine for failure injection
- Each test gets its own session + isolated transaction
"""

import json
import os
import sys
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

# Ensure paths
_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)

_verifier_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "verifier")
)
if _verifier_path not in sys.path:
    sys.path.insert(0, _verifier_path)

from app.database import SessionLocal, engine
from app.ingestion import IngestService
from app.models import (
    ChainAuthority,
    EventChain,
    Session,
    SessionStatus,
    Violation,
)
from app.models.user import User


@pytest.fixture
def ingest_service():
    """Real IngestService for actual event persistence."""
    return IngestService(service_id="test-worker-ingest-01")


@pytest.fixture
def test_user():
    """Create a test user in the database. Cleaned up by conftest truncation."""
    db = SessionLocal()
    try:
        user = User(username=f"test-user-{uuid.uuid4().hex[:8]}")
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


@pytest.fixture
def test_session(ingest_service, test_user):
    """
    Create a real active session in the database.

    Returns session_id_str.
    Cleaned up by conftest.py's db fixture truncation.
    """
    session_id = str(uuid.uuid4())
    ingest_service.start_session(
        session_id_str=session_id,
        authority="server",
        agent_name="atomicity-test-agent",
        user_id=test_user,
    )
    return session_id


@pytest.fixture
def mock_redis():
    """Mock Redis client with call tracking."""
    redis_mock = MagicMock()
    redis_mock.xack = MagicMock(return_value=1)
    redis_mock.xadd = MagicMock(return_value="mock-msg-id")
    return redis_mock


def make_batch_fields(
    session_id: str,
    events: list[dict],
    batch_id: str | None = None,
    seal: bool = False,
) -> dict:
    """
    Build a Redis-like message field dict for Worker._process_message.

    Events must include: event_type, sequence_number, timestamp_monotonic, payload.
    Also requires timestamp_wall for IngestService.
    """
    batch_id = batch_id or str(uuid.uuid4())
    return {
        "batch_id": batch_id,
        "session_id": session_id,
        "seal": str(seal),
        "events": json.dumps(events),
    }


def make_event(
    seq: int,
    event_type: str = "LLM_CALL",
    payload: dict | None = None,
) -> dict:
    """Build a single event dict compatible with Worker's processing."""
    return {
        "event_type": event_type,
        "sequence_number": seq,
        "timestamp_wall": datetime.now(UTC).isoformat(),
        "timestamp_monotonic": 1000 + seq,
        "payload": payload or {"action": f"test-{seq}"},
    }


def count_events(session_id: str) -> int:
    """Count events in DB for a session (fresh connection)."""
    db = SessionLocal()
    try:
        return (
            db.query(EventChain)
            .filter(EventChain.session_id == session_id)
            .count()
        )
    finally:
        db.close()


def count_violations(session_id: str) -> int:
    """Count violations in DB for a session (fresh connection)."""
    db = SessionLocal()
    try:
        return (
            db.query(Violation)
            .filter(Violation.session_id == session_id)
            .count()
        )
    finally:
        db.close()


def get_max_sequence(session_id: str) -> int | None:
    """Get the max sequence number for a session (fresh connection)."""
    db = SessionLocal()
    try:
        from sqlalchemy import func

        result = (
            db.query(func.max(EventChain.sequence_number))
            .filter(EventChain.session_id == session_id)
            .scalar()
        )
        return result
    finally:
        db.close()
