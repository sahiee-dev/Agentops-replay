"""
remote_client.py - Remote mode wrapper for AgentOps SDK.

Extends existing SDK with SERVER authority mode via HTTP transport.
"""

import os
from typing import Any

import httpx

from .client import AgentOpsClient
from .events import EventType
from .transport import RetryExhausted, send_batch_with_retry


class RemoteAgentOpsClient(AgentOpsClient):
    """
    AgentOps SDK with remote server mode.

    CONSTITUTIONAL GUARANTEES:
    - Server authority (hash recomputation on server)
    - Exponential backoff retry (5 attempts)
    - Deterministic LOG_DROP on persistent failure
    - Fail-open semantics (SDK continues even if server unreachable)
    """

    def __init__(
        self,
        server_url: str | None = None,
        api_key: str | None = None,
        max_retries: int = 5,
        retry_min_wait: float = 1.0,
        retry_max_wait: float = 10.0,
        batch_size: int = 10,
        local_authority: bool = False,  # Ignored in remote mode
        buffer_size: int = 1000,
    ):
        """
        Create a RemoteAgentOpsClient configured to send batched events to a remote ingestion server and to preserve a local buffer as a fallback.
        
        Parameters:
            server_url (str | None): Base URL for the ingestion service. If None, reads AGENTOPS_SERVER_URL or uses "http://localhost:8000".
            api_key (str | None): Optional API key; if provided (or present in AGENTOPS_API_KEY) it is attached as a Bearer token to HTTP requests.
            max_retries (int): Maximum number of retry attempts for sending a batch.
            retry_min_wait (float): Minimum backoff (seconds) between retry attempts.
            retry_max_wait (float): Maximum backoff (seconds) between retry attempts.
            batch_size (int): Number of events to accumulate locally before sending a batch to the server.
            local_authority (bool): Ignored in remote mode; retained for API compatibility.
            buffer_size (int): Size of the local in-memory event buffer (delegated to the base client).
        
        Behavior:
            - Stores retry, batching, and server configuration on the instance.
            - Initializes an HTTP client configured with JSON content type and optional Authorization header.
            - Prepares local buffering and batching state (pending_events, remote_session_id, server_offline flag, and failure counters).
        """
        super().__init__(local_authority=False, buffer_size=buffer_size)

        self.server_url = server_url or os.getenv(
            "AGENTOPS_SERVER_URL", "http://localhost:8000"
        )
        self.api_key = api_key or os.getenv("AGENTOPS_API_KEY")
        self.max_retries = max_retries
        self.retry_min_wait = retry_min_wait
        self.retry_max_wait = retry_max_wait
        self.batch_size = batch_size

        # HTTP client
        self.http_client = httpx.Client(
            base_url=self.server_url,
            timeout=30.0,
            headers={"Content-Type": "application/json"},
        )
        if self.api_key:
            self.http_client.headers["Authorization"] = f"Bearer {self.api_key}"

        # Remote session ID (from server)
        self.remote_session_id: str | None = None

        # Pending events to send
        self.pending_events: list[dict[str, Any]] = []

        # Track consecutive failures for kill-switch
        self.consecutive_failures = 0
        self.max_consecutive_failures = 3
        self.consecutive_failures = 0
        self.max_consecutive_failures = 3
        self.server_offline = False
        self.total_dropped_events = 0

    def start_session(self, agent_id: str, tags: list[str] = None):
        """
        Start a remote session on the server and fall back to local buffering if the server is unreachable.
        
        On success stores the server-assigned session id in `self.remote_session_id`, clears the offline state and consecutive-failure counter. On failure marks the client as server-offline so the SDK continues in local-buffer-only mode. Always delegates to the parent `start_session` to preserve local buffering and session state.
        
        Parameters:
            agent_id (str): Identifier for the agent to start the session for.
            tags (list[str] | None): Optional list of tags to attach to the session.
        """
        try:
            response = self.http_client.post(
                "/api/v1/ingest/sessions",
                json={"authority": "server", "agent_name": agent_id, "user_id": None},
            )
            response.raise_for_status()
            data = response.json()
            self.remote_session_id = data["session_id"]

            print(
                f"✅ Remote session started: {self.remote_session_id} (SERVER authority)"
            )
            self.server_offline = False
            self.consecutive_failures = 0

        except Exception as e:
            print(f"❌ Failed to start remote session: {e}")
            print("   SDK will continue in local-buffer-only mode...")
            self.server_offline = True

        # Always call parent to maintain local chain
        super().start_session(agent_id, tags)

    def record(self, event_type: EventType, payload: dict[str, Any]):
        """
        Record an event locally and queue it for remote batching and transmission.
        
        This delegates to the base implementation to preserve the local buffer, converts the most recently buffered event into the server-compatible event shape, and appends it to the local batch queue. If the client is marked offline the event is only recorded locally. When the queued batch reaches the configured batch size this method triggers a flush to the remote server.
        
        Parameters:
            event_type (EventType): Category of the event being recorded; used for the local buffer entry and included in the queued server event.
            payload (dict[str, Any]): Event payload to record and include in the queued server event.
        """
        # Always call parent to maintain local buffer
        super().record(event_type, payload)

        # Skip remote send if server is offline
        if self.server_offline:
            return

        # Convert last buffered event to server format
        last_proposal = self.buffer.events[-1] if self.buffer.events else None
        if last_proposal:
            server_event = {
                "event_id": last_proposal.event_id,
                "sequence_number": last_proposal.sequence_number,
                "timestamp_wall": last_proposal.timestamp_wall,
                "timestamp_monotonic": 0,  # Not tracked in current SDK
                "event_type": last_proposal.event_type,
                "payload": last_proposal.payload,
                "source_sdk_ver": "0.2.0",
                "schema_ver": last_proposal.schema_ver,
            }
            self.pending_events.append(server_event)

        # Send batch if threshold reached
        if len(self.pending_events) >= self.batch_size:
            self._flush_batch()

    def _flush_batch(self):
        """
        Flush pending batched events to the remote server and handle persistent failures.
        
        Attempts to send buffered events for the active remote session. On success, clears the pending queue and resets the consecutive failure counter. If sending fails persistently, emits a local `LOG_DROP` event recording the dropped count and error, clears the pending queue, increments the consecutive failure counter, and when the failure count reaches the configured threshold activates a kill-switch by setting `server_offline` to True so the client continues in local-buffer-only mode.
        """
        if not self.pending_events or not self.remote_session_id:
            return

        try:
            result = send_batch_with_retry(
                self.http_client,
                self.remote_session_id,
                self.pending_events,
                self.max_retries,
                self.retry_min_wait,
                self.retry_max_wait,
            )

            print(f"✅ Batch sent: {result['accepted_count']} events")
            self.pending_events = []
            self.consecutive_failures = 0

        except RetryExhausted as e:
            # ALL retries failed - this is persistent failure
            print(f"❌ PERSISTENT FAILURE: {e}")

            # Emit LOG_DROP deterministically
            dropped_count = len(self.pending_events)
            self.total_dropped_events += dropped_count
            print(
                f"📝 Emitting LOG_DROP for {dropped_count} events (5 retries exhausted)"
            )

            # Local LOG_DROP for audit trail
            super().record(
                EventType.LOG_DROP,
                {
                    "dropped_count": dropped_count,
                    "cumulative_drops": self.total_dropped_events,
                    "drop_reason": "persistent_server_failure",
                    "retry_count": self.max_retries,
                    "error": str(e),
                },
            )

            # Clear failed batch
            self.pending_events = []

            # Increment failure counter
            self.consecutive_failures += 1

            # Kill-switch: After multiple consecutive failures, stop trying
            if self.consecutive_failures >= self.max_consecutive_failures:
                print(
                    f"⛔ Kill-switch activated: Server offline for {self.consecutive_failures} batches"
                )
                print("   SDK will continue in local-buffer-only mode...")
                self.server_offline = True

    def end_session(self, status: str, duration_ms: int):
        """
        End the current session, flush any queued events, and attempt to seal the remote session.
        
        Records a local session end, flushes any pending batched events to the server when the server is reachable, and, if a remote session exists, attempts to seal it on the server. If sealing fails or the server is offline, the function leaves the server session open and logs a warning but does not raise.
        
        Parameters:
            status (str): Final session status string.
            duration_ms (int): Session duration in milliseconds.
        """
        # Record SESSION_END
        super().end_session(status, duration_ms)

        # Flush any remaining events
        if self.pending_events and not self.server_offline:
            self._flush_batch()

        # Attempt to seal session on server
        if self.remote_session_id and not self.server_offline:
            try:
                response = self.http_client.post(
                    f"/api/v1/ingest/sessions/{self.remote_session_id}/seal"
                )
                response.raise_for_status()
                data = response.json()
                print(
                    f"🔒 Session sealed: {data['session_digest'][:16]}... ({data['event_count']} events)"
                )

            except Exception as e:
                print(f"⚠️  Failed to seal session: {e}")
                print("   Session remains open on server")

    def __del__(self):
        """
        Close the HTTP client if it was initialized.
        
        Releases underlying network resources held by the client's HTTP connection when the object is destroyed.
        """
        if hasattr(self, "http_client"):
            self.http_client.close()