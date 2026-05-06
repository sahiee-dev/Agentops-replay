"""
tests/integration/test_ingestion_api.py — TRD §7.2

Integration tests for the AgentOps Replay ingestion and export API.

DB-dependent tests are marked requires_docker and auto-skipped when
Postgres is not reachable on localhost:5432.
Run: cd backend && docker-compose up -d
"""

import pytest
import json
import sys
import os
import anyio
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'verifier'))

from backend.app.main import app
from agentops_sdk.envelope import build_event, GENESIS_HASH

pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_valid_batch(session_id: str = "integration-test-session"):
    events = []
    prev = GENESIS_HASH
    specs = [
        (1, "SESSION_START", {"agent_id": "test-agent", "model_id": "test-model"}),
        (2, "LLM_CALL", {"model_id": "test-model", "prompt_hash": "abc123"}),
        (3, "SESSION_END", {"status": "success"}),
    ]
    for seq, etype, payload in specs:
        e = build_event(seq, etype, session_id, payload, prev)
        events.append(e)
        prev = e["event_hash"]
    return {"session_id": session_id, "events": events}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_health(client):
    """Health endpoint must return 200 — no DB required."""
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.requires_docker
async def test_valid_batch_returns_200(client):
    body = make_valid_batch()
    r = await client.post("/v1/ingest", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "accepted"
    assert data["events_accepted"] == 3


@pytest.mark.requires_docker
async def test_session_end_triggers_chain_seal(client):
    body = make_valid_batch("seal-test-session")
    r = await client.post("/v1/ingest", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data.get("chain_seal") is not None
    assert data["chain_seal"]["event_type"] == "CHAIN_SEAL"


@pytest.mark.requires_docker
async def test_hash_mismatch_returns_400(client):
    body = make_valid_batch("hash-mismatch-session")
    # Corrupt the hash of the first event
    body["events"][0]["event_hash"] = "a" * 64
    r = await client.post("/v1/ingest", json=body)
    assert r.status_code == 400
    data = r.json()
    assert "hash_mismatch" in data.get("error", "")
    assert "seq" in data


@pytest.mark.requires_docker
async def test_duplicate_sequence_returns_409(client):
    body = make_valid_batch("dup-seq-session")
    r1 = await client.post("/v1/ingest", json=body)
    assert r1.status_code == 200
    # Send same batch again
    r2 = await client.post("/v1/ingest", json=body)
    assert r2.status_code == 409


@pytest.mark.requires_docker
async def test_export_returns_jsonl_in_order(client):
    session_id = "export-test-session"
    body = make_valid_batch(session_id)
    await client.post("/v1/ingest", json=body)
    r = await client.get(f"/v1/sessions/{session_id}/export")
    assert r.status_code == 200
    lines = [line for line in r.text.strip().split("\n") if line]
    events = [json.loads(line) for line in lines]
    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs), f"Events not in order: {seqs}"
    for e in events:
        assert "event_hash" in e
        assert "prev_hash" in e


@pytest.mark.requires_docker
async def test_nonexistent_session_export_returns_404(client):
    r = await client.get("/v1/sessions/nonexistent-session-id-xyz/export")
    assert r.status_code == 404
