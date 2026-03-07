"""
test_openai_integration.py - Tests for the OpenAI SDK wrapper.

Tests the wrap_openai function using mocked OpenAI client objects.
No real API calls are made.

CONSTITUTIONAL TESTS:
1. MODEL_REQUEST captured on call
2. MODEL_RESPONSE captured after response
3. Tool calls captured in response payload
4. ERROR event emitted on API error
5. CHAIN_SEAL is NEVER emitted (constitutional requirement)
"""

from __future__ import annotations

import os
import sys
import unittest
import uuid
from unittest.mock import MagicMock, patch

# Ensure SDK and agentops_sdk are on path
_sdk_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_agentops_sdk_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
if _sdk_path not in sys.path:
    sys.path.insert(0, _sdk_path)
if _agentops_sdk_path not in sys.path:
    sys.path.insert(0, _agentops_sdk_path)


def _make_mock_openai_client():
    """Create a mock OpenAI client with chat.completions.create."""
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    # Store the original create for reference
    client.chat.completions.create = MagicMock()
    return client


def _make_mock_response(
    content: str = "Hello!",
    model: str = "gpt-4",
    tool_calls: list | None = None,
    usage: dict | None = None,
):
    """Create a mock OpenAI ChatCompletion response."""
    message = {
        "role": "assistant",
        "content": content,
        "tool_calls": tool_calls,
    }
    choice = {
        "index": 0,
        "message": message,
        "finish_reason": "stop",
    }
    response = {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "model": model,
        "choices": [choice],
        "usage": usage or {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    # Make it behave like an OpenAI response object (with model_dump)
    mock = MagicMock()
    mock.model_dump.return_value = response
    return mock


def _make_mock_stream_chunks(content: str = "Hello world"):
    """Create mock streaming chunks."""
    chunks = []
    for i, char in enumerate(content):
        chunk = MagicMock()
        chunk.model_dump.return_value = {
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": char},
                    "finish_reason": None if i < len(content) - 1 else "stop",
                }
            ]
        }
        chunks.append(chunk)
    return iter(chunks)


class TestOpenAIIntegration(unittest.TestCase):
    """Tests for the OpenAI SDK wrapper using unittest."""

    def test_model_request_emitted(self):
        """Calling chat.completions.create emits a MODEL_REQUEST event."""
        from agentops_replay.integrations.openai import wrap_openai

        client = _make_mock_openai_client()
        mock_response = _make_mock_response()
        original_create = client.chat.completions.create
        original_create.return_value = mock_response

        with patch("agentops_replay.integrations.openai.AgentOpsClient") as MockSDK:
            mock_sdk = MagicMock()
            MockSDK.return_value = mock_sdk

            wrap_openai(client, agent_id="test-agent")

            client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "Hi"}],
            )

        # Verify MODEL_REQUEST was recorded
        record_calls = mock_sdk.record.call_args_list
        assert len(record_calls) >= 1

        # First call should be SESSION_START (from auto-start), then MODEL_REQUEST
        event_types = [call[0][0] for call in record_calls]
        from agentops_sdk.events import EventType

        self.assertIn(EventType.MODEL_REQUEST, event_types)

        # Find the MODEL_REQUEST call
        request_call = [
            c for c in record_calls if c[0][0] == EventType.MODEL_REQUEST
        ][0]
        payload = request_call[0][1]
        self.assertEqual(payload["model"], "gpt-4")
        self.assertEqual(payload["provider"], "openai")
        self.assertIn("run_id", payload)

    def test_model_response_emitted(self):
        """Successful completion emits MODEL_RESPONSE with content and usage."""
        from agentops_replay.integrations.openai import wrap_openai

        client = _make_mock_openai_client()
        mock_response = _make_mock_response(content="World!", model="gpt-4o")
        original_create = client.chat.completions.create
        original_create.return_value = mock_response

        with patch("agentops_replay.integrations.openai.AgentOpsClient") as MockSDK:
            mock_sdk = MagicMock()
            MockSDK.return_value = mock_sdk

            wrap_openai(client, agent_id="test-agent")

            client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": "Hi"}],
            )

        from agentops_sdk.events import EventType

        record_calls = mock_sdk.record.call_args_list
        response_calls = [
            c for c in record_calls if c[0][0] == EventType.MODEL_RESPONSE
        ]
        self.assertEqual(len(response_calls), 1)

        payload = response_calls[0][0][1]
        self.assertEqual(payload["model"], "gpt-4o")
        self.assertIn("duration_ms", payload)
        self.assertIn("choices", payload)

    def test_tool_calls_captured(self):
        """Response with tool_calls captures them in the event payload."""
        from agentops_replay.integrations.openai import wrap_openai

        tool_calls = [
            {
                "id": "call_abc123",
                "type": "function",
                "function": {"name": "get_weather", "arguments": '{"city": "London"}'},
            }
        ]
        client = _make_mock_openai_client()
        mock_response = _make_mock_response(
            content=None, tool_calls=tool_calls
        )
        original_create = client.chat.completions.create
        original_create.return_value = mock_response

        with patch("agentops_replay.integrations.openai.AgentOpsClient") as MockSDK:
            mock_sdk = MagicMock()
            MockSDK.return_value = mock_sdk

            wrap_openai(client, agent_id="test-agent")

            client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "What's the weather?"}],
            )

        from agentops_sdk.events import EventType

        record_calls = mock_sdk.record.call_args_list
        response_calls = [
            c for c in record_calls if c[0][0] == EventType.MODEL_RESPONSE
        ]
        self.assertEqual(len(response_calls), 1)

        payload = response_calls[0][0][1]
        self.assertIsNotNone(payload["tool_calls"])
        # self.assertEqual(len(payload["tool_calls"]), 1)
        # Check content to debug 20 != 1 issue
        self.assertEqual(len(payload["tool_calls"]), 1, f"Tool calls: {payload['tool_calls']}")
        self.assertEqual(payload["tool_calls"][0]["type"], "function")

    def test_error_event_emitted(self):
        """API error emits ERROR event and re-raises the exception."""
        from agentops_replay.integrations.openai import wrap_openai

        client = _make_mock_openai_client()
        original_create = client.chat.completions.create
        original_create.side_effect = Exception("API rate limit exceeded")

        with patch("agentops_replay.integrations.openai.AgentOpsClient") as MockSDK:
            mock_sdk = MagicMock()
            MockSDK.return_value = mock_sdk

            wrap_openai(client, agent_id="test-agent")

            with self.assertRaisesRegex(Exception, "API rate limit exceeded"):
                client.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": "Hi"}],
                )

        from agentops_sdk.events import EventType

        record_calls = mock_sdk.record.call_args_list
        error_calls = [c for c in record_calls if c[0][0] == EventType.ERROR]
        self.assertEqual(len(error_calls), 1)

        payload = error_calls[0][0][1]
        self.assertEqual(payload["error_type"], "Exception")
        self.assertIn("rate limit", payload["error_message"])

    def test_no_chain_seal_emitted(self):
        """Verify that no CHAIN_SEAL event is ever emitted by the wrapper."""
        from agentops_replay.integrations.openai import wrap_openai

        client = _make_mock_openai_client()
        mock_response = _make_mock_response()
        original_create = client.chat.completions.create
        original_create.return_value = mock_response

        with patch("agentops_replay.integrations.openai.AgentOpsClient") as MockSDK:
            mock_sdk = MagicMock()
            MockSDK.return_value = mock_sdk

            wrap_openai(client, agent_id="test-agent")

            # Make multiple calls
            for _ in range(5):
                client.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": "Hi"}],
                )

        from agentops_sdk.events import EventType

        record_calls = mock_sdk.record.call_args_list
        event_types = [call[0][0] for call in record_calls]

        # CHAIN_SEAL must NEVER appear
        self.assertNotIn(EventType.CHAIN_SEAL, event_types,
            "CONSTITUTIONAL VIOLATION: wrap_openai emitted CHAIN_SEAL. "
            "SDK code must never emit server authority artifacts."
        )

    def test_streaming_accumulates_and_emits(self):
        """Streaming response accumulates chunks and emits single MODEL_RESPONSE."""
        from agentops_replay.integrations.openai import wrap_openai

        client = _make_mock_openai_client()
        chunks = _make_mock_stream_chunks("OK")
        original_create = client.chat.completions.create
        original_create.return_value = chunks

        with patch("agentops_replay.integrations.openai.AgentOpsClient") as MockSDK:
            mock_sdk = MagicMock()
            MockSDK.return_value = mock_sdk

            wrap_openai(client, agent_id="test-agent")

            stream = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "Hi"}],
                stream=True,
            )

            # Consume the stream
            collected = []
            for chunk in stream:
                collected.append(chunk)

        from agentops_sdk.events import EventType

        record_calls = mock_sdk.record.call_args_list
        response_calls = [
            c for c in record_calls if c[0][0] == EventType.MODEL_RESPONSE
        ]

        # Exactly one MODEL_RESPONSE after stream completes
        self.assertEqual(len(response_calls), 1)
        payload = response_calls[0][0][1]
        self.assertTrue(payload.get("streamed"))
        self.assertEqual(payload["choices"][0]["content"], "OK")


if __name__ == "__main__":
    unittest.main()
