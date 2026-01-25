"""
remote_client.py - Remote mode wrapper for AgentOps SDK.

Extends existing SDK with SERVER authority mode via HTTP transport.
"""

from .client import AgentOpsClient
from .events import EventType
from .transport import send_batch_with_retry, RetryExhausted
from typing import Optional, Dict, Any, List
import httpx
import os


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
        server_url: Optional[str] = None,
        api_key: Optional[str] = None,
        max_retries: int = 5,
        retry_min_wait: float = 1.0,
        retry_max_wait: float = 10.0,
        batch_size: int = 10,
        local_authority: bool = False,  # Ignored in remote mode
        buffer_size: int = 1000
    ):
        """
        Create a RemoteAgentOpsClient configured to send events to a remote ingestion server with batching, retry/backoff, and a local fail-open buffer.
        
        Parameters:
            server_url (Optional[str]): Base URL for the ingestion service; if omitted, taken from AGENTOPS_SERVER_URL or "http://localhost:8000".
            api_key (Optional[str]): API key for authenticating requests to the server; if omitted, taken from AGENTOPS_API_KEY.
            max_retries (int): Maximum number of retry attempts for sending a batch before considering it failed.
            retry_min_wait (float): Minimum backoff wait (seconds) between retry attempts.
            retry_max_wait (float): Maximum backoff wait (seconds) between retry attempts.
            batch_size (int): Number of events to accumulate locally before attempting a remote send.
            local_authority (bool): Present for API compatibility; ignored because remote mode enforces server authority.
            buffer_size (int): Size of the local in-memory event buffer used as a fallback when the server is unavailable.
        
        Notes:
            This initializer configures the HTTP client, stores retry and batching settings, and initializes internal state used for remote session management, pending-event batching, and fail-open behavior.
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
        self.remote_session_id: Optional[str] = None
        
        # Pending events to send
        self.pending_events: List[Dict[str, Any]] = []
        
        # Track consecutive failures for kill-switch
        self.consecutive_failures = 0
        self.max_consecutive_failures = 3
        self.server_offline = False
    
    def start_session(self, agent_id: str, tags: List[str] = None):
        """
        Initiates a session with the remote server and establishes server-assigned authority.
        
        Attempts to create a remote session and, on success, stores the server-provided session ID and resets the client's remote-failure state. On persistent failure to contact the server, switches the client into local-buffer-only (fail-open) mode by setting the server_offline flag; local buffering and sequencing are still maintained. Always delegates to the superclass start_session to preserve local session state.
        
        Parameters:
            agent_id (str): The agent name/identifier for the session.
            tags (List[str], optional): Optional tags to associate with the session.
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
            print(f"   SDK will continue in local-buffer-only mode...")
            self.server_offline = True
        
        # Always call parent to maintain local chain
        super().start_session(agent_id, tags)
    
    def record(self, event_type: EventType, payload: Dict[str, Any]):
        """
        Record an event locally and enqueue it for remote batching.
        
        Calls the superclass to maintain the local buffer. If the client is in remote mode (server not marked offline),
        the most-recently buffered event is converted to the server-facing format and appended to the outgoing batch.
        When the batch size threshold is reached, a flush is triggered. If the server is offline, no remote enqueue or send is performed.
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
        Send queued events to the remote server and handle persistent failures.
        
        If there are no pending events or no active remote session, does nothing. Attempts to transmit the pending batch using the client's configured retry policy; on success it clears the batch and resets the consecutive-failure counter. If all retries are exhausted, emits a deterministic local LOG_DROP event recording the number of dropped events and the error, clears the pending batch, increments the consecutive-failure counter, and—when the consecutive-failure count reaches the configured threshold—marks the server as offline so the SDK continues in local-buffer-only mode.
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
                print(f"   SDK will continue in local-buffer-only mode...")
                self.server_offline = True
    
    def end_session(self, status: str, duration_ms: int):
        """
        End the current session locally and, if connected, flush pending events and request the server to seal the remote session.
        
        Calls the superclass to record the session end (SESSION_END). If the client has pending events and the server is reachable, those events are flushed. If a remote session ID exists and the server is reachable, a seal request is sent; failures to seal are handled internally and do not raise.
        
        Parameters:
        	status (str): Final status of the session (for example, "success" or "failure").
        	duration_ms (int): Duration of the session in milliseconds.
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
                print(f"   Session remains open on server")
    
    def __del__(self):
        """Cleanup HTTP client."""
        if hasattr(self, 'http_client'):
            self.http_client.close()