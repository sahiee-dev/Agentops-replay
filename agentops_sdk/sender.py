import json
import time
import urllib.request
import urllib.error
from typing import Any


class EventSender:
    """
    HTTP batch sender for the Ingestion Service.

    Uses only urllib (stdlib). No requests. No httpx.
    Retry policy: 3 attempts with 1s, 2s, 4s exponential backoff.
    On final failure: raises ConnectionError.
    Never modifies the events list.
    """

    def __init__(
        self,
        server_url: str,
        timeout_seconds: int = 10,
        max_retries: int = 3,
    ) -> None:
        self._base_url = server_url.rstrip("/")
        self._timeout = timeout_seconds
        self._max_retries = max_retries

    def send_batch(
        self,
        session_id: str,
        events: list[dict],
    ) -> dict:
        """
        POST events to /v1/ingest.

        Translates SDK envelope fields to server-expected fields:
          SDK field  →  Server field
          seq        →  sequence_number
          timestamp  →  timestamp_monotonic (epoch-converted)
          prev_hash  →  prev_event_hash
          payload    →  payload

        Request body: {"session_id": str, "events": [...], "seal": bool}
        Returns parsed response dict on success.

        Raises
        ------
        ConnectionError: After max_retries failed attempts.
        ValueError: If server returns 4xx (client error — do not retry).
        """
        # Translate SDK events to server schema
        translated = []
        for event in events:
            server_event = {
                "event_type": event["event_type"],
                "sequence_number": event["seq"],
                "timestamp_monotonic": _timestamp_to_monotonic(event.get("timestamp", "")),
                "timestamp": event.get("timestamp", ""),
                "payload": event.get("payload", {}),
                # SDK hashes are logged but never trusted by the server
                "event_hash": event.get("event_hash"),
                "prev_event_hash": event.get("prev_hash"),
            }
            translated.append(server_event)

        # Determine if we should request sealing
        # Seal if the last event is SESSION_END
        seal = False
        if translated and translated[-1]["event_type"] == "SESSION_END":
            seal = True

        body = {
            "session_id": session_id,
            "events": translated,
            "seal": seal,
        }
        return self._post("/v1/ingest", body)

    def _post(self, path: str, body: dict) -> dict:
        """Single POST attempt with retry logic."""
        url = self._base_url + path
        data = json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        last_error: Exception | None = None
        delays = [1, 2, 4]

        for attempt in range(self._max_retries):
            try:
                req = urllib.request.Request(
                    url, data=data, headers=headers, method="POST"
                )
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    response_body = resp.read().decode("utf-8")
                    return json.loads(response_body)

            except urllib.error.HTTPError as e:
                if 400 <= e.code < 500:
                    # Client error — do not retry
                    error_body = e.read().decode("utf-8")
                    raise ValueError(
                        f"Server returned {e.code}: {error_body}"
                    ) from e
                last_error = e

            except urllib.error.URLError as e:
                last_error = e

            if attempt < self._max_retries - 1:
                time.sleep(delays[attempt])

        raise ConnectionError(
            f"Failed to POST to {url} after {self._max_retries} attempts. "
            f"Last error: {last_error}"
        )


def _timestamp_to_monotonic(ts: str) -> int:
    """Convert ISO 8601 timestamp string to epoch microseconds for timestamp_monotonic."""
    if not ts:
        return 0
    try:
        from datetime import datetime
        # Strip trailing Z and parse
        clean = ts.rstrip("Z")
        dt = datetime.fromisoformat(clean)
        return int(dt.timestamp() * 1_000_000)
    except (ValueError, TypeError):
        return 0
