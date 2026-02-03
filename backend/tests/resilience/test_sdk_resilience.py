import pytest
from unittest.mock import MagicMock, patch
import httpx
from agentops_sdk.remote_client import RemoteAgentOpsClient
from agentops_sdk.events import EventType

class MockResponse:
    def __init__(self, status_code, json_data=None):
        """
        Initialize a mock HTTP response with a status code, JSON payload, and empty headers.
        
        Parameters:
            status_code (int): HTTP status code to simulate (e.g., 200, 404, 500).
            json_data (dict | None): JSON-serializable payload returned by json(); defaults to an empty dict.
        """
        self.status_code = status_code
        self.json_data = json_data or {}
        self.headers = {}

    def raise_for_status(self):
        """
        Raise an HTTPStatusError for response status codes in the 400–599 range.
        
        Raises:
            httpx.HTTPStatusError: If `self.status_code` is greater than or equal to 400 and less than 600.
        """
        if 400 <= self.status_code < 600:
            raise httpx.HTTPStatusError("Error", request=None, response=self)

    def json(self):
        """
        Return the stored JSON payload provided when the MockResponse was created.
        
        Returns:
            The JSON-compatible object (e.g., dict, list) originally passed as `json_data`.
        """
        return self.json_data

class TestSDKResilience:
    
    @pytest.fixture
    def mock_client(self):
        # Create client with fast retry config
        """
        Provide a RemoteAgentOpsClient configured for fast retries and with its HTTP client mocked.
        
        Returns:
            RemoteAgentOpsClient: Client set with max_retries=2, retry_min_wait=0.01, retry_max_wait=0.05, batch_size=1, and with `http_client` replaced by a MagicMock.
        """
        client = RemoteAgentOpsClient(
            server_url="http://test-server",
            api_key="test-key",
            max_retries=2,
            retry_min_wait=0.01,
            retry_max_wait=0.05,
            batch_size=1  # Flush every event
        )
        # Mock the internal http_client
        client.http_client = MagicMock()
        return client

    def test_retry_logic_success(self, mock_client):
        """Test that client retries on 500 error and eventually succeeds."""
        # Setup: Fail once with 500, then succeed
        mock_client.http_client.post.side_effect = [
            MockResponse(500),
            MockResponse(200, {"accepted_count": 1, "final_hash": "hash123"})
        ]
        
        # Manually set session ID to skip start_session call
        mock_client.remote_session_id = "sess-123"
        mock_client.session_id = "sess-local-123"
        
        # Act
        mock_client.record(EventType.TOOL_CALL, {"prompt": "test"})
        
        # Assert
        # Should have called post twice
        assert mock_client.http_client.post.call_count == 2
        # Should not have dropped logic
        assert mock_client.consecutive_failures == 0
        assert mock_client.server_offline is False

    def test_persistent_failure_triggers_log_drop(self, mock_client):
        """Test that persistent failure triggers LOG_DROP in local buffer."""
        # Setup: Always fail with NetworkError
        mock_client.http_client.post.side_effect = httpx.NetworkError("Net Down")
        
        mock_client.remote_session_id = "sess-123"
        mock_client.session_id = "sess-local-123"
        
        # Act
        mock_client.record(EventType.TOOL_CALL, {"prompt": "test"})
        
        # Assert
        # Should have retried max_retries (2) -> 2 attempts? 
        # Actually send_batch_with_retry loops 'attempt < max_retries'.
        # If max_retries=2, loop runs for attempt=0, attempt=1. So 2 calls.
        assert mock_client.http_client.post.call_count == 2
        
        
        # Should have emitted LOG_DROP to local buffer (super().record)
        # Check buffer
        import json
        last_event = mock_client.buffer.queue[-1]
        assert last_event.event_type == EventType.LOG_DROP
        payload_dict = json.loads(last_event.payload)
        assert payload_dict["drop_reason"] == "persistent_server_failure"
        assert payload_dict["dropped_count"] == 1
        
        # Failure count incremented
        assert mock_client.consecutive_failures == 1

    def test_kill_switch_activation(self, mock_client):
        """
        Verify that the client's kill switch marks the server offline after reaching max consecutive failures, prevents further network requests, and buffers subsequent events locally.
        
        After the configured `max_consecutive_failures` is reached the client's `server_offline` flag is set to True and `consecutive_failures` equals that threshold. While offline, calls to `record` do not invoke the network client and instead append events to the local buffer (e.g., the last buffered event contains the supplied prompt).
        """
        mock_client.http_client.post.side_effect = httpx.NetworkError("Net Down")
        mock_client.remote_session_id = "sess-123"
        mock_client.session_id = "sess-local-123"
        mock_client.max_consecutive_failures = 3
        
        # Fail 3 times (3 batches)
        for i in range(3):
            mock_client.record(EventType.TOOL_CALL, {"prompt": f"msg {i}"})
        
        assert mock_client.consecutive_failures == 3
        assert mock_client.server_offline is True
        
        # reset mock
        mock_client.http_client.post.reset_mock()
        
        # Next call should NOT attempt network
        mock_client.record(EventType.TOOL_CALL, {"prompt": "msg 4"})
        mock_client.http_client.post.assert_not_called()
        
        # But should be in local buffer
        import json
        last_event = mock_client.buffer.queue[-1]
        payload_dict = json.loads(last_event.payload)
        assert payload_dict["prompt"] == "msg 4"
