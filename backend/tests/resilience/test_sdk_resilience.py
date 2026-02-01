import pytest
from unittest.mock import MagicMock, patch
import httpx
from agentops_sdk.remote_client import RemoteAgentOpsClient
from agentops_sdk.events import EventType

class MockResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self.json_data = json_data or {}
        self.headers = {}

    def raise_for_status(self):
        if 400 <= self.status_code < 600:
            raise httpx.HTTPStatusError("Error", request=None, response=self)

    def json(self):
        return self.json_data

class TestSDKResilience:
    
    @pytest.fixture
    def mock_client(self):
        # Create client with fast retry config
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
        assert payload_dict["reason"] == "persistent_server_failure"
        assert payload_dict["dropped_events"] == 1
        
        # Failure count incremented
        assert mock_client.consecutive_failures == 1

    def test_kill_switch_activation(self, mock_client):
        """Test that kill switch activates after max consecutive failures."""
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

