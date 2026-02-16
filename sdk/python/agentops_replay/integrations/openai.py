from __future__ import annotations

"""
openai.py - OpenAI SDK integration for AgentOps Replay.

Wraps the OpenAI Python client to capture LLM calls as verifiable events.

Design Philosophy:
- This wrapper is an UNTRUSTED PRODUCER (per Constitution)
- It captures events and sends to SDK buffer
- Server will re-verify all hashes
- Fail open for agent (don't crash), fail closed for integrity (record losses)
- MUST NEVER emit CHAIN_SEAL or server authority artifacts

Usage:
    from openai import OpenAI
    from agentops_replay.integrations.openai import wrap_openai

    client = OpenAI()
    wrap_openai(client, agent_id="my-agent")

    # All calls are now automatically captured
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello"}]
    )
"""

import hashlib
import json
import logging
import time
from datetime import datetime
from functools import wraps
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

# Integration metadata
INTEGRATION_VERSION = "0.1.0"
FRAMEWORK_NAME = "openai"

# Import agentops SDK
try:
    from agentops_sdk.client import AgentOpsClient
    from agentops_sdk.events import EventType
except ImportError:
    AgentOpsClient = None  # type: ignore
    EventType = None  # type: ignore


def _safe_serialize(obj: Any, max_depth: int = 10) -> Any:
    """
    Safely convert arbitrary Python objects to JSON-compatible primitives.

    Handles OpenAI response objects which have model_dump() methods.
    Stops recursion at max_depth to prevent stack overflow.
    """
    if max_depth <= 0:
        return "<max_depth_exceeded>"

    if obj is None:
        return None

    if isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(item, max_depth - 1) for item in obj[:100]]

    if isinstance(obj, dict):
        return {
            str(k): _safe_serialize(v, max_depth - 1)
            for k, v in list(obj.items())[:50]
        }

    if isinstance(obj, UUID):
        return str(obj)

    if isinstance(obj, datetime):
        return obj.isoformat()

    # OpenAI Pydantic models
    if hasattr(obj, "model_dump"):
        try:
            return _safe_serialize(obj.model_dump(), max_depth - 1)
        except Exception:
            pass

    if hasattr(obj, "dict"):
        try:
            return _safe_serialize(obj.dict(), max_depth - 1)
        except Exception:
            pass

    if hasattr(obj, "__dict__"):
        try:
            return _safe_serialize(obj.__dict__, max_depth - 1)
        except Exception:
            pass

    try:
        return str(obj)[:1000]
    except Exception:
        return "<unserializable>"


def _compute_content_hash(content: Any) -> str:
    """Compute a deterministic SHA-256 hex digest for content."""
    try:
        serialized = json.dumps(_safe_serialize(content), sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()
    except Exception:
        return "hash_error"


def wrap_openai(
    client: Any,
    agent_id: str,
    *,
    local_authority: bool = False,
    buffer_size: int = 10000,
    redact_pii: bool = False,
    tags: list[str] | None = None,
    auto_start_session: bool = True,
) -> Any:
    """
    Wrap an OpenAI client to capture LLM calls as AgentOps events.

    Monkey-patches client.chat.completions.create to intercept calls.
    The original client is returned (same object, patched in-place).

    CONSTITUTIONAL CONSTRAINT: This wrapper is an UNTRUSTED PRODUCER.
    It NEVER emits CHAIN_SEAL or assigns server authority.

    Args:
        client: An openai.OpenAI client instance.
        agent_id: Unique identifier for the agent.
        local_authority: If True, SDK seals chains locally (testing only).
        buffer_size: Maximum events in ring buffer before dropping.
        redact_pii: If True, hash sensitive fields instead of storing raw values.
        tags: Optional list of tags for session metadata.
        auto_start_session: If True, auto-start a session on first call.

    Returns:
        The same client, with chat.completions.create patched.

    Raises:
        ImportError: If agentops_sdk is not installed.
    """
    if AgentOpsClient is None:
        raise ImportError(
            "AgentOps SDK not found. Install with: pip install agentops-sdk"
        )

    # Initialize SDK client
    sdk_client = AgentOpsClient(
        local_authority=local_authority,
        buffer_size=buffer_size,
    )

    # Session state
    session_started = False

    all_tags = (tags or []) + [f"openai-integration:{INTEGRATION_VERSION}"]

    def _ensure_session() -> None:
        nonlocal session_started
        if not session_started:
            sdk_client.start_session(agent_id=agent_id, tags=all_tags)
            session_started = True

    def _maybe_redact(content: Any, field_name: str) -> Any:
        if not redact_pii:
            return _safe_serialize(content)
        return f"[REDACTED:{field_name}]"

    def _get_openai_version() -> str:
        try:
            import openai

            return openai.__version__
        except Exception:
            return "unknown"

    # Store references for external access (testing, end_session)
    client._agentops_sdk_client = sdk_client
    client._agentops_session_started = lambda: session_started
    client._agentops_integration_version = INTEGRATION_VERSION

    def _end_session(status: str = "success") -> None:
        nonlocal session_started
        if session_started:
            sdk_client.end_session(status=status, duration_ms=0)
            session_started = False

    def _export_to_jsonl(filename: str) -> None:
        sdk_client.flush_to_jsonl(filename)

    client.end_agentops_session = _end_session
    client.export_agentops_jsonl = _export_to_jsonl

    # Patch chat.completions.create
    if hasattr(client, "chat") and hasattr(client.chat, "completions"):
        original_create = client.chat.completions.create

        @wraps(original_create)
        def patched_create(*args: Any, **kwargs: Any) -> Any:
            if auto_start_session:
                _ensure_session()

            run_id = str(uuid4())
            start_time = time.time()

            # Capture request
            model = kwargs.get("model", args[0] if args else "unknown")
            messages = kwargs.get("messages", args[1] if len(args) > 1 else [])
            stream = kwargs.get("stream", False)

            # Emit MODEL_REQUEST
            request_payload = {
                "run_id": run_id,
                "model": str(model),
                "provider": "openai",
                "messages": _maybe_redact(messages, "messages"),
                "messages_hash": _compute_content_hash(messages)
                if redact_pii
                else None,
                "stream": stream,
                "framework": FRAMEWORK_NAME,
                "framework_version": _get_openai_version(),
                "integration_version": INTEGRATION_VERSION,
            }

            try:
                sdk_client.record(EventType.MODEL_REQUEST, request_payload)
            except Exception:
                logger.debug("Failed to record MODEL_REQUEST", exc_info=True)

            # Execute the actual call
            try:
                if stream:
                    return _handle_streaming(
                        original_create,
                        args,
                        kwargs,
                        run_id,
                        model,
                        start_time,
                    )
                else:
                    return _handle_sync(
                        original_create,
                        args,
                        kwargs,
                        run_id,
                        model,
                        start_time,
                    )
            except Exception as e:
                # Record error event
                duration_ms = int((time.time() - start_time) * 1000)
                error_payload = {
                    "run_id": run_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e)[:500],
                    "model": str(model),
                    "duration_ms": duration_ms,
                }
                try:
                    sdk_client.record(EventType.ERROR, error_payload)
                except Exception:
                    logger.debug("Failed to record ERROR event", exc_info=True)
                raise  # Re-raise the original exception

        def _handle_sync(
            original_fn: Any,
            args: tuple,
            kwargs: dict,
            run_id: str,
            model: Any,
            start_time: float,
        ) -> Any:
            """Handle synchronous (non-streaming) completion call."""
            response = original_fn(*args, **kwargs)
            duration_ms = int((time.time() - start_time) * 1000)

            # Extract response data
            response_payload = _extract_response_payload(
                response, run_id, model, duration_ms
            )

            try:
                sdk_client.record(EventType.MODEL_RESPONSE, response_payload)
            except Exception:
                logger.debug("Failed to record MODEL_RESPONSE", exc_info=True)

            return response

        def _handle_streaming(
            original_fn: Any,
            args: tuple,
            kwargs: dict,
            run_id: str,
            model: Any,
            start_time: float,
        ) -> Any:
            """
            Handle streaming completion call.

            Wraps the stream iterator to accumulate chunks. Emits a single
            MODEL_RESPONSE event after the stream completes.
            """
            stream_response = original_fn(*args, **kwargs)

            return _StreamWrapper(
                stream_response,
                sdk_client=sdk_client,
                run_id=run_id,
                model=model,
                start_time=start_time,
                redact_pii=redact_pii,
            )

        def _extract_response_payload(
            response: Any, run_id: str, model: Any, duration_ms: int
        ) -> dict[str, Any]:
            """Extract a MODEL_RESPONSE payload from an OpenAI response object."""
            response_data = _safe_serialize(response)

            # Extract key fields
            choices = []
            tool_calls = []

            if isinstance(response_data, dict):
                for choice in response_data.get("choices", []):
                    if isinstance(choice, dict):
                        message = choice.get("message", {})
                        choices.append(
                            {
                                "index": choice.get("index", 0),
                                "content": _maybe_redact(
                                    message.get("content"), "response_content"
                                ),
                                "role": message.get("role", "assistant"),
                                "finish_reason": choice.get("finish_reason"),
                            }
                        )
                        # Extract tool calls if present
                        if message.get("tool_calls"):
                            for tc in message["tool_calls"]:
                                tool_calls.append(_safe_serialize(tc))

            usage = {}
            if isinstance(response_data, dict) and response_data.get("usage"):
                usage = _safe_serialize(response_data["usage"])

            return {
                "run_id": run_id,
                "model": str(model),
                "choices": choices,
                "tool_calls": tool_calls if tool_calls else None,
                "usage": usage,
                "duration_ms": duration_ms,
                "response_id": response_data.get("id") if isinstance(response_data, dict) else None,
            }

        client.chat.completions.create = patched_create

    return client


class _StreamWrapper:
    """
    Wraps an OpenAI streaming response to accumulate chunks.

    Emits a single MODEL_RESPONSE event after the stream completes.
    Behaves as a transparent iterator — the caller sees the same chunks.
    """

    def __init__(
        self,
        stream: Any,
        *,
        sdk_client: Any,
        run_id: str,
        model: Any,
        start_time: float,
        redact_pii: bool,
    ) -> None:
        self._stream = stream
        self._sdk_client = sdk_client
        self._run_id = run_id
        self._model = model
        self._start_time = start_time
        self._redact_pii = redact_pii
        self._accumulated_content: list[str] = []
        self._accumulated_tool_calls: list[Any] = []
        self._finish_reason: str | None = None

    def __iter__(self) -> "_StreamWrapper":
        return self

    def __next__(self) -> Any:
        try:
            chunk = next(self._stream)
            self._process_chunk(chunk)
            return chunk
        except StopIteration:
            self._emit_response()
            raise

    def _process_chunk(self, chunk: Any) -> None:
        """Accumulate content and tool calls from a stream chunk."""
        chunk_data = _safe_serialize(chunk)
        if not isinstance(chunk_data, dict):
            return

        for choice in chunk_data.get("choices", []):
            if not isinstance(choice, dict):
                continue

            delta = choice.get("delta", {})
            if isinstance(delta, dict):
                content = delta.get("content")
                if content:
                    self._accumulated_content.append(content)

                tool_calls = delta.get("tool_calls")
                if tool_calls:
                    self._accumulated_tool_calls.extend(
                        _safe_serialize(tc) for tc in tool_calls
                    )

            finish_reason = choice.get("finish_reason")
            if finish_reason:
                self._finish_reason = finish_reason

    def _emit_response(self) -> None:
        """Emit MODEL_RESPONSE with accumulated stream data."""
        duration_ms = int((time.time() - self._start_time) * 1000)
        full_content = "".join(self._accumulated_content)

        content_value = full_content
        if self._redact_pii:
            content_value = "[REDACTED:response_content]"

        payload = {
            "run_id": self._run_id,
            "model": str(self._model),
            "choices": [
                {
                    "index": 0,
                    "content": content_value,
                    "role": "assistant",
                    "finish_reason": self._finish_reason,
                }
            ],
            "tool_calls": self._accumulated_tool_calls
            if self._accumulated_tool_calls
            else None,
            "usage": {},  # Streaming responses don't include usage in chunks
            "duration_ms": duration_ms,
            "streamed": True,
        }

        try:
            self._sdk_client.record(EventType.MODEL_RESPONSE, payload)
        except Exception:
            logger.debug("Failed to record streamed MODEL_RESPONSE", exc_info=True)
