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
        buffer_size: int = 1000
    ):
        """
        Initialize remote client.
        
        Args:
            server_url: Base URL for ingestion service
            api_key: API key for authentication (optional)
            max_retries: Maximum retry attempts
            retry_min_wait: Minimum wait between retries
            retry_max_wait: Maximum wait between retries
            batch_size: Number of events to batch before sending
            buffer_size: Local buffer size
        """
        super().__init__(local_authority=False, buffer_size=buffer_size)

        self.server_url = server_url or os.getenv("AGENTOPS_SERVER_URL", "http://localhost:8000")
        self.api_key = api_key or os.getenv("AGENTOPS_API_KEY")
        self.max_retries = max_retries
        self.retry_min_wait = retry_min_wait
        self.retry_max_wait = retry_max_wait
        self.batch_size = batch_size

        # HTTP client
        self.http_client = httpx.Client(
            base_url=self.server_url,
            timeout=30.0,
            headers={"Content-Type": "application/json"}
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
        self.server_offline = False

    def start_session(self, agent_id: str, tags: list[str] = None):
        """
        Start session on remote server.
        
        SERVER AUTHORITY: Server creates session and assigns authority.
        FAIL-OPEN: If server unreachable, falls back to local buffer only.
        """
        try:
            response = self.http_client.post(
                "/api/v1/ingest/sessions",
                json={
                    "authority": "server",
                    "agent_name": agent_id,
                    "user_id": None
                }
            )
            response.raise_for_status()
            data = response.json()
            self.remote_session_id = data["session_id"]

            print(f"✅ Remote session started: {self.remote_session_id} (SERVER authority)")
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
        Record event and batch to server.
        
        BATCHING: Events buffered locally and sent in batches
        RETRY: Exponential backoff on failures
        LOG_DROP: Deterministic emission on persistent failure
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
                "schema_ver": last_proposal.schema_ver
            }
            self.pending_events.append(server_event)

        # Send batch if threshold reached
        if len(self.pending_events) >= self.batch_size:
            self._flush_batch()

    def _flush_batch(self):
        """
        Flush pending events to server with retry.
        
        CONSTITUTIONAL: Emit LOG_DROP if all retries exhausted.
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
                self.retry_max_wait
            )

            print(f"✅ Batch sent: {result['accepted_count']} events")
            self.pending_events = []
            self.consecutive_failures = 0

        except RetryExhausted as e:
            # ALL retries failed - this is persistent failure
            print(f"❌ PERSISTENT FAILURE: {e}")

            # Emit LOG_DROP deterministically
            dropped_count = len(self.pending_events)
            print(f"📝 Emitting LOG_DROP for {dropped_count} events (5 retries exhausted)")

            # Local LOG_DROP for audit trail
            super().record(EventType.LOG_DROP, {
                "dropped_events": dropped_count,
                "reason": "persistent_server_failure",
                "retry_count": self.max_retries,
                "error": str(e)
            })

            # Clear failed batch
            self.pending_events = []

            # Increment failure counter
            self.consecutive_failures += 1

            # Kill-switch: After multiple consecutive failures, stop trying
            if self.consecutive_failures >= self.max_consecutive_failures:
                print(f"⛔ Kill-switch activated: Server offline for {self.consecutive_failures} batches")
                print("   SDK will continue in local-buffer-only mode...")
                self.server_offline = True

    def end_session(self, status: str, duration_ms: int):
        """
        End session and flush remaining events.
        
        CONSTITUTIONAL: SESSION_END required for CHAIN_SEAL.
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
                print(f"🔒 Session sealed: {data['session_digest'][:16]}... ({data['event_count']} events)")

            except Exception as e:
                print(f"⚠️  Failed to seal session: {e}")
                print("   Session remains open on server")

    def __del__(self):
        """Cleanup HTTP client."""
        if hasattr(self, 'http_client'):
            self.http_client.close()
