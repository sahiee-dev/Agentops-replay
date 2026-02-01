"""
Test API endpoints for ingestion and verification.
"""

import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import UTC, datetime

from app.main import app

client = TestClient(app)


class TestIngestionAPI:
    """Test ingestion API endpoints."""

    def test_start_session_server_authority(self):
        """Test session creation with server authority."""
        response = client.post(
            "/api/v1/ingest/sessions",
            json={"authority": "server", "agent_name": "test-agent", "user_id": None},
        )

        assert response.status_code == 201
        data = response.json()
        assert "session_id" in data
        assert data["authority"] == "server"
        assert data["status"] == "active"
        assert data["ingestion_service_id"] is not None

    def test_start_session_sdk_authority(self):
        """Test session creation with SDK authority."""
        response = client.post(
            "/api/v1/ingest/sessions",
            json={"authority": "sdk", "agent_name": "test-agent"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["authority"] == "sdk"
        assert (
            data["ingestion_service_id"] is None
        )  # SDK sessions don't have service ID

    def test_append_events(self):
        """Test event appending."""
        # Create session
        session_resp = client.post(
            "/api/v1/ingest/sessions", json={"authority": "server"}
        )
        session_id = session_resp.json()["session_id"]

        # Append events
        response = client.post(
            f"/api/v1/ingest/sessions/{session_id}/events",
            json={
                "session_id": session_id,
                "events": [
                    {
                        "sequence_number": 0,
                        "timestamp_wall": datetime.now(UTC).isoformat(),
                        "event_type": "TEST",
                        "payload": {"data": "test"},
                    }
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["accepted_count"] == 1
        assert "final_hash" in data

    def test_sequence_violation_returns_409(self):
        """Test that sequence gaps return HTTP 409."""
        # Create session and add event
        session_resp = client.post(
            "/api/v1/ingest/sessions", json={"authority": "server"}
        )
        session_id = session_resp.json()["session_id"]

        client.post(
            f"/api/v1/ingest/sessions/{session_id}/events",
            json={
                "session_id": session_id,
                "events": [
                    {
                        "sequence_number": 0,
                        "timestamp_wall": datetime.now(UTC).isoformat(),
                        "event_type": "TEST",
                        "payload": {},
                    }
                ],
            },
        )

        # Gap: jump to seq 5
        response = client.post(
            f"/api/v1/ingest/sessions/{session_id}/events",
            json={
                "session_id": session_id,
                "events": [
                    {
                        "sequence_number": 5,
                        "timestamp_wall": datetime.now(UTC).isoformat(),
                        "event_type": "TEST",
                        "payload": {},
                    }
                ],
            },
        )

        assert response.status_code == 409  # Conflict
        assert "Sequence violation" in response.json()["detail"]

    def test_seal_session(self):
        """Test session sealing."""
        # Create session with SESSION_END
        session_resp = client.post(
            "/api/v1/ingest/sessions", json={"authority": "server"}
        )
        session_id = session_resp.json()["session_id"]

        # Add SESSION_END
        client.post(
            f"/api/v1/ingest/sessions/{session_id}/events",
            json={
                "session_id": session_id,
                "events": [
                    {
                        "sequence_number": 0,
                        "timestamp_wall": datetime.now(UTC).isoformat(),
                        "event_type": "SESSION_END",
                        "payload": {},
                    }
                ],
            },
        )

        # Seal
        response = client.post(f"/api/v1/ingest/sessions/{session_id}/seal")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "sealed"
        assert "session_digest" in data
        assert "seal_timestamp" in data
        assert data["event_count"] > 0

    def test_seal_without_session_end_fails(self):
        """Test that seal fails without SESSION_END."""
        session_resp = client.post(
            "/api/v1/ingest/sessions", json={"authority": "server"}
        )
        session_id = session_resp.json()["session_id"]

        # Try to seal without SESSION_END
        response = client.post(f"/api/v1/ingest/sessions/{session_id}/seal")

        assert response.status_code == 400
        assert "SESSION_END" in response.json()["detail"]

    def test_seal_sdk_session_fails(self):
        """Test that SDK sessions cannot be sealed."""
        session_resp = client.post("/api/v1/ingest/sessions", json={"authority": "sdk"})
        session_id = session_resp.json()["session_id"]

        # Add SESSION_END
        client.post(
            f"/api/v1/ingest/sessions/{session_id}/events",
            json={
                "session_id": session_id,
                "events": [
                    {
                        "sequence_number": 0,
                        "timestamp_wall": datetime.now(UTC).isoformat(),
                        "event_type": "SESSION_END",
                        "payload": {},
                    }
                ],
            },
        )

        # Try to seal
        response = client.post(f"/api/v1/ingest/sessions/{session_id}/seal")

        assert response.status_code == 403  # Forbidden
        assert "authority" in response.json()["detail"].lower()


class TestExportAPI:
    """Test export endpoints."""

    def test_json_export(self):
        """Test JSON export generation."""
        # Create and populate session
        session_resp = client.post(
            "/api/v1/ingest/sessions",
            json={"authority": "server", "agent_name": "test"},
        )
        session_id = session_resp.json()["session_id"]

        client.post(
            f"/api/v1/ingest/sessions/{session_id}/events",
            json={
                "session_id": session_id,
                "events": [
                    {
                        "sequence_number": 0,
                        "timestamp_wall": datetime.now(UTC).isoformat(),
                        "event_type": "TEST",
                        "payload": {"data": "test"},
                    }
                ],
            },
        )

        # Export JSON
        response = client.get(
            f"/api/v1/export/sessions/{session_id}/export?format=json"
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

        # Validate structure
        data = response.json()
        assert "export_version" in data
        assert "session_id" in data
        assert "events" in data
        assert "chain_of_custody" in data
        assert data["chain_of_custody"]["canonical_format"] == "RFC 8785 (JCS)"

    def test_pdf_export(self):
        """Test PDF export generation."""
        # Create session
        session_resp = client.post(
            "/api/v1/ingest/sessions", json={"authority": "server"}
        )
        session_id = session_resp.json()["session_id"]

        client.post(
            f"/api/v1/ingest/sessions/{session_id}/events",
            json={
                "session_id": session_id,
                "events": [
                    {
                        "sequence_number": 0,
                        "timestamp_wall": datetime.now(UTC).isoformat(),
                        "event_type": "TEST",
                        "payload": {},
                    }
                ],
            },
        )

        # Export PDF
        response = client.get(f"/api/v1/export/sessions/{session_id}/export?format=pdf")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert len(response.content) > 1000  # PDF should have substantial content
