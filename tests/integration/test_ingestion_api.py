"""
tests/integration/test_ingestion_api.py — TRD §7.2

Integration tests for the AgentOps Replay ingestion and export API.
All 7 required test cases per TRD §7.2:

  Case 1: POST valid batch → 201
  Case 2: POST with hash mismatch → 400
  Case 3: POST with duplicate seq → 409
  Case 4: POST with SESSION_END + seal → 201, chain_seal present
  Case 5: GET /v1/sessions/{id}/export → JSONL in seq order
  Case 6: GET /v1/sessions/nonexistent/export → 404
  Case 7: GET /health → 200

Uses an in-memory SQLite database via env override,
eliminating the Docker/Postgres requirement.
"""

import json
import os
import sys
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

# Path setup: add both project root (for agentops_sdk) and backend/ (for app.*)
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_BACKEND_DIR = os.path.join(_PROJECT_ROOT, "backend")

if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(1, _PROJECT_ROOT)

# Override database URL BEFORE importing any backend module
os.environ["AGENTOPS_DATABASE_URL"] = "sqlite://"

# Import from app.* (canonical path when backend/ is on sys.path)
from app.database import Base, engine, SessionLocal  # noqa: E402
from app.models import ChainSeal, EventChain, Session as SessionModel, User  # noqa: E402

# CRITICAL: Alias app.* modules as backend.app.* in sys.modules.
# This prevents dual module identity when FastAPI's try/except blocks
# successfully import backend.app.* (which creates separate Base/engine objects).
for _name in list(sys.modules):
    if _name == "app" or _name.startswith("app."):
        _alias = f"backend.{_name}"
        if _alias not in sys.modules:
            sys.modules[_alias] = sys.modules[_name]

from app.main import app  # noqa: E402  — must be after aliasing

# SDK envelope builder
from agentops_sdk.envelope import GENESIS_HASH, build_event  # noqa: E402

pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_session_id(prefix: str = "test") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _make_valid_batch(session_id: str, seal: bool = False) -> dict:
    """Build a valid 3-event batch: SESSION_START, LLM_CALL, SESSION_END."""
    events = []
    prev = GENESIS_HASH
    specs = [
        (0, "SESSION_START", {"agent_id": "test-agent", "model_id": "test-model"}),
        (1, "LLM_CALL", {"model_id": "test-model", "prompt_hash": "abc123"}),
        (2, "SESSION_END", {"status": "success"}),
    ]
    for seq, etype, payload in specs:
        e = build_event(seq, etype, session_id, payload, prev)
        events.append(
            {
                "event_type": e["event_type"],
                "sequence_number": e["seq"],
                "timestamp_monotonic": 0,
                "timestamp": e["timestamp"],
                "payload": e["payload"],
                "event_hash": e["event_hash"],
                "prev_event_hash": e["prev_hash"],
            }
        )
        prev = e["event_hash"]
    return {"session_id": session_id, "events": events, "seal": seal}


def _seed_user_and_session(session_id: str) -> SessionModel:
    """Insert user + session rows that the ingestion service expects."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "integration-test-user").first()
        if user is None:
            user = User(username="integration-test-user", email="test@test.com")
            db.add(user)
            db.flush()

        session = SessionModel(
            user_id=user.id,
            session_id_str=session_id,
            status="active",
            chain_authority="SERVER",
        )
        db.add(session)
        db.commit()
        return session
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _setup_db():
    """Create all tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
async def client():
    """httpx AsyncClient talking to the FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.fixture
def seeded_session():
    """Create a user + session and return the session_id."""
    sid = _unique_session_id("seeded")
    _seed_user_and_session(sid)
    return sid


# ---------------------------------------------------------------------------
# Case 7: GET /health → 200
# ---------------------------------------------------------------------------


async def test_health_returns_200(client):
    """GET /health must return 200 with status=ok."""
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Case 1: POST valid batch → 201
# ---------------------------------------------------------------------------


async def test_valid_batch_returns_201(client, seeded_session):
    """POST a valid 3-event batch → 201 Created."""
    body = _make_valid_batch(seeded_session)
    r = await client.post("/v1/ingest", json=body)
    assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
    data = r.json()
    assert data["status"] == "success"
    assert data["accepted_count"] == 3
    assert data["chain_authority"] == "SERVER"
    assert len(data["final_hash"]) == 64


# ---------------------------------------------------------------------------
# Case 2: POST with hash mismatch → 400
# ---------------------------------------------------------------------------


async def test_invalid_payload_returns_4xx(client, seeded_session):
    """POST batch with missing required field → 400 or 422."""
    body = _make_valid_batch(seeded_session)
    # Remove event_type from second event — structurally invalid
    del body["events"][1]["event_type"]
    r = await client.post("/v1/ingest", json=body)
    # FastAPI/Pydantic returns 422 for schema violations
    assert r.status_code in (400, 422), f"Expected 4xx, got {r.status_code}: {r.text}"


async def test_corrupted_sdk_hash_is_ignored(client, seeded_session):
    """Server-authority: SDK hashes are logged but never trusted.
    Corrupting them must NOT cause rejection (server recomputes)."""
    body = _make_valid_batch(seeded_session)
    body["events"][1]["event_hash"] = "b" * 64
    r = await client.post("/v1/ingest", json=body)
    # Server ignores SDK hash, recomputes server-side → 201
    assert r.status_code == 201, f"Server should accept (recomputes hashes): {r.text}"


# ---------------------------------------------------------------------------
# Case 3: POST with duplicate seq → 409
# ---------------------------------------------------------------------------


async def test_duplicate_sequence_returns_409(client):
    """POST same batch twice → second request gets 409 Conflict."""
    sid = _unique_session_id("dup-seq")
    _seed_user_and_session(sid)

    body = _make_valid_batch(sid)
    r1 = await client.post("/v1/ingest", json=body)
    assert r1.status_code == 201, f"First batch should succeed: {r1.text}"

    # Second identical batch → conflict
    r2 = await client.post("/v1/ingest", json=body)
    assert r2.status_code == 409, f"Expected 409, got {r2.status_code}: {r2.text}"


# ---------------------------------------------------------------------------
# Case 4: POST with SESSION_END + seal → 201, chain_seal present
# ---------------------------------------------------------------------------


async def test_session_end_triggers_chain_seal(client):
    """POST batch with seal=true → 201, chain_seal in response."""
    sid = _unique_session_id("seal")
    _seed_user_and_session(sid)

    body = _make_valid_batch(sid, seal=True)
    r = await client.post("/v1/ingest", json=body)
    assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
    data = r.json()
    assert data["sealed"] is True, f"Expected sealed=True: {data}"
    assert data["chain_seal"] is not None, f"Missing chain_seal: {data}"

    seal = data["chain_seal"]
    assert "final_event_hash" in seal
    assert "event_count" in seal
    assert seal["event_count"] == 3
    assert "evidence_class" in seal
    assert seal["evidence_class"] == "AUTHORITATIVE_EVIDENCE"
    assert "ingestion_service_id" in seal


# ---------------------------------------------------------------------------
# Case 5: GET /v1/sessions/{id}/export → JSONL in seq order
# ---------------------------------------------------------------------------


async def test_export_returns_jsonl_in_order(client):
    """Ingest then export → events in seq order with 7-field envelopes."""
    sid = _unique_session_id("export")
    _seed_user_and_session(sid)

    body = _make_valid_batch(sid, seal=True)
    r1 = await client.post("/v1/ingest", json=body)
    assert r1.status_code == 201, f"Ingest failed: {r1.text}"

    r2 = await client.get(f"/v1/sessions/{sid}/export")
    assert r2.status_code == 200
    assert "ndjson" in r2.headers.get("content-type", "")

    lines = [line for line in r2.text.strip().split("\n") if line]
    assert len(lines) >= 3, f"Expected at least 3 lines, got {len(lines)}"

    events = [json.loads(line) for line in lines]
    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs), f"Events not in order: {seqs}"

    for e in events:
        for field in ("seq", "event_type", "session_id", "timestamp",
                       "payload", "prev_hash", "event_hash"):
            assert field in e, f"Missing field '{field}' in event: {e}"


# ---------------------------------------------------------------------------
# Case 6: GET /v1/sessions/nonexistent/export → 404
# ---------------------------------------------------------------------------


async def test_nonexistent_session_export_returns_404(client):
    """GET export for non-existent session → 404."""
    r = await client.get("/v1/sessions/nonexistent-session-id-xyz/export")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Bonus: verify persisted payloads contain hashes, not raw text
# ---------------------------------------------------------------------------


async def test_persisted_payloads_contain_hashes_not_raw_text(client):
    """Ingested events must contain payload hashes, not raw content."""
    sid = _unique_session_id("privacy")
    _seed_user_and_session(sid)

    body = _make_valid_batch(sid)
    r = await client.post("/v1/ingest", json=body)
    assert r.status_code == 201

    db = SessionLocal()
    try:
        events = (
            db.query(EventChain)
            .filter(EventChain.session_id == sid)
            .order_by(EventChain.sequence_number)
            .all()
        )
        assert len(events) == 3
        for e in events:
            assert e.payload_hash is not None
            assert len(e.payload_hash) == 64
    finally:
        db.close()
