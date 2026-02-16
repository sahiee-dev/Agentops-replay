"""
test_async_ingestion.py - Tests for the async ingestion pipeline.

Tests the batch endpoint (API → Redis) and worker (Redis → IngestService → DB).
Does NOT test IngestService internals — those are covered by test_ingestion_service.py.

CONVERTED TO UNITTEST to run in restricted environments.
"""

from __future__ import annotations

import json
import unittest
import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

# Mock app import if environment is tricky
try:
    from app.main import app
    HAS_APP = True
except ImportError:
    HAS_APP = False
    app = MagicMock()


def _make_batch_payload(
    session_id: str | None = None,
    events: list | None = None,
    seal: bool = False,
) -> dict:
    """Build a valid IngestBatchRequest payload."""
    if session_id is None:
        session_id = str(uuid.uuid4())
    if events is None:
        events = [
            {
                "event_type": "SESSION_START",
                "sequence_number": 0,
                "timestamp_monotonic": 1000,
                "payload": {"action": "start"},
            }
        ]
    return {"session_id": session_id, "events": events, "seal": seal}


class TestAsyncIngestion(unittest.TestCase):
    """Tests for async ingestion (API + Worker) using unittest."""

    def setUp(self):
        self.test_client = TestClient(app)
        self.mock_redis = MagicMock()
        self.mock_redis.xadd.return_value = "1234567890-0"
        self.mock_redis.ping.return_value = True

    def test_valid_batch_returns_202(self):
        """POST /api/v1/ingest/batch with valid payload returns 202 + batch_id."""
        if not HAS_APP:
            self.skipTest("App not importable")
            
        payload = _make_batch_payload()

        with patch("app.core.redis.get_redis_client", return_value=self.mock_redis):
            response = self.test_client.post("/api/v1/ingest/batch", json=payload)

        self.assertEqual(response.status_code, 202)
        data = response.json()
        self.assertEqual(data["status"], "accepted")
        self.assertIn("batch_id", data)
        self.assertEqual(data["accepted_count"], 1)

        # Verify Redis was called
        self.mock_redis.xadd.assert_called_once()
        call_args = self.mock_redis.xadd.call_args
        self.assertEqual(call_args[0][0], "agentops:events:ingest")

    def test_multi_event_batch(self):
        """Multiple events in a single batch are accepted."""
        payload = _make_batch_payload(
            events=[
                {
                    "event_type": "SESSION_START",
                    "sequence_number": 0,
                    "timestamp_monotonic": 1000,
                    "payload": {},
                },
                {
                    "event_type": "LLM_CALL",
                    "sequence_number": 1,
                    "timestamp_monotonic": 2000,
                    "payload": {"prompt": "hello"},
                },
            ]
        )

        with patch("app.core.redis.get_redis_client", return_value=self.mock_redis):
            response = self.test_client.post("/api/v1/ingest/batch", json=payload)

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["accepted_count"], 2)

    def test_empty_events_rejected(self):
        """Empty events list must be rejected (422)."""
        payload = {"session_id": str(uuid.uuid4()), "events": []}

        response = self.test_client.post("/api/v1/ingest/batch", json=payload)
        self.assertEqual(response.status_code, 422)

    def test_missing_session_id_rejected(self):
        """Missing session_id must be rejected (422)."""
        payload = {
            "events": [
                {
                    "event_type": "SESSION_START",
                    "sequence_number": 0,
                    "timestamp_monotonic": 1000,
                    "payload": {},
                }
            ]
        }

        response = self.test_client.post("/api/v1/ingest/batch", json=payload)
        self.assertEqual(response.status_code, 422)

    def test_redis_down_returns_503(self):
        """If Redis is unreachable, endpoint returns 503."""
        self.mock_redis.xadd.side_effect = ConnectionError("Redis unreachable")

        payload = _make_batch_payload()

        with patch("app.core.redis.get_redis_client", return_value=self.mock_redis):
            response = self.test_client.post("/api/v1/ingest/batch", json=payload)

        self.assertEqual(response.status_code, 503)

    def test_worker_calls_ingest_service(self):
        """Worker deserializes batch and calls IngestService.append_events."""
        from app.worker.main import IngestionWorker

        # Mock IngestService in worker
        with patch("app.worker.main.IngestService") as MockIngestService:
            mock_service_instance = MagicMock()
            MockIngestService.return_value = mock_service_instance
            mock_service_instance.append_events.return_value = {
                "status": "success",
                "accepted_count": 1,
                "final_hash": "abc123",
            }
            
            with patch("app.worker.main.get_redis_client", return_value=self.mock_redis):
                worker = IngestionWorker()
                worker.redis = self.mock_redis # Ensure uses our mock
                
                session_id = str(uuid.uuid4())
                events = [
                    {
                        "event_type": "SESSION_START",
                        "sequence_number": 0,
                        "timestamp_monotonic": 1000,
                        "payload": {},
                    }
                ]

                fields = {
                    "batch_id": str(uuid.uuid4()),
                    "session_id": session_id,
                    "seal": "False",
                    "events": json.dumps(events),
                }

                worker._process_message("msg-001", fields)

                # Verify IngestService was called with correct args
                mock_service_instance.append_events.assert_called_once()
                call_kwargs = mock_service_instance.append_events.call_args
                self.assertEqual(call_kwargs[1]["session_id"], session_id)

                # Verify XACK was called
                self.mock_redis.xack.assert_called_once()

    def test_invalid_json_goes_to_dlq(self):
        """Invalid JSON in events field → immediate DLQ."""
        from app.worker.main import IngestionWorker

        with patch("app.worker.main.IngestService"), \
             patch("app.worker.main.get_redis_client", return_value=self.mock_redis):
             
            worker = IngestionWorker()
            
            fields = {
                "batch_id": str(uuid.uuid4()),
                "session_id": str(uuid.uuid4()),
                "seal": "False",
                "events": "NOT VALID JSON {{{",
            }

            worker._process_message("msg-002", fields)

            # Should go directly to DLQ
            self.mock_redis.xadd.assert_called_once()
            dlq_call = self.mock_redis.xadd.call_args
            self.assertEqual(dlq_call[0][0], "agentops:events:dlq")

            # Should be acknowledged
            self.mock_redis.xack.assert_called_once()


if __name__ == "__main__":
    unittest.main()
