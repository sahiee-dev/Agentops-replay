"""
AgentOps Replay - LangChain Callback Handler

Captures all LangChain events (LLM calls, tool invocations, chain execution)
and emits them as verifiable AgentOps events.

Design Philosophy:
- This handler is an UNTRUSTED PRODUCER (per PRD)
- It captures events and sends to SDK buffer
- Server will re-verify all hashes
- Fail open for agent (don't crash), fail closed for integrity (record losses)
"""

import hashlib
import json
import logging
import time
from datetime import datetime
from typing import Any
from uuid import UUID

# Module logger for debug output
logger = logging.getLogger(__name__)

from .version import (
    INTEGRATION_VERSION,
    check_compatibility,
    get_langchain_version_string,
    warn_if_incompatible,
)

# Import agentops SDK
try:
    from agentops_sdk.client import AgentOpsClient
    from agentops_sdk.events import EventType
except ImportError:
    # Fallback for direct imports
    AgentOpsClient = None  # type: ignore
    EventType = None  # type: ignore

# Try to import LangChain
try:
    from langchain_core.agents import AgentAction, AgentFinish
    from langchain_core.callbacks.base import BaseCallbackHandler
    from langchain_core.messages import BaseMessage
    from langchain_core.outputs import LLMResult
    LANGCHAIN_AVAILABLE = True
except ImportError:
    # Stub for when LangChain is not installed
    BaseCallbackHandler = object  # type: ignore
    LLMResult = None  # type: ignore
    AgentAction = None  # type: ignore
    AgentFinish = None  # type: ignore
    BaseMessage = None  # type: ignore
    LANGCHAIN_AVAILABLE = False


def _safe_serialize(obj: Any, max_depth: int = 5) -> Any:
    """
    Safely convert arbitrary Python objects to JSON-compatible primitives for telemetry.
    
    Recursively serializes common primitive types, lists (up to 100 items), dicts (up to 50 entries),
    UUIDs (to string), and datetimes (to ISO 8601). If an object exposes `dict()`, `to_dict()`,
    or `__dict__`, those are used recursively. Stops recursion when `max_depth` is reached and
    returns the sentinel "<max_depth_exceeded>". On other failures falls back to the object's
    string representation truncated to 1000 characters, or "<unserializable>" if that fails.
    
    Parameters:
        obj (Any): The object to serialize.
        max_depth (int): Maximum recursion depth; when reached returns "<max_depth_exceeded>".
    
    Returns:
        Any: A JSON-compatible representation of `obj`, or a sentinel/string fallback on failure.
    """
    if max_depth <= 0:
        return "<max_depth_exceeded>"

    if obj is None:
        return None

    if isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(item, max_depth - 1) for item in obj[:100]]  # Limit list size

    if isinstance(obj, dict):
        return {
            str(k): _safe_serialize(v, max_depth - 1)
            for k, v in list(obj.items())[:50]  # Limit dict size
        }

    if isinstance(obj, UUID):
        return str(obj)

    if isinstance(obj, datetime):
        return obj.isoformat()

    if hasattr(obj, 'dict'):
        try:
            return _safe_serialize(obj.dict(), max_depth - 1)
        except Exception as e:
            logger.debug(
                "Serialization via .dict() failed for %s: %s",
                type(obj).__name__, e, exc_info=True
            )

    if hasattr(obj, 'to_dict'):
        try:
            return _safe_serialize(obj.to_dict(), max_depth - 1)
        except Exception as e:
            logger.debug(
                "Serialization via .to_dict() failed for %s: %s",
                type(obj).__name__, e, exc_info=True
            )

    if hasattr(obj, '__dict__'):
        try:
            return _safe_serialize(obj.__dict__, max_depth - 1)
        except Exception as e:
            logger.debug(
                "Serialization via __dict__ failed for %s: %s",
                type(obj).__name__, e, exc_info=True
            )

    # Fallback: string representation
    try:
        return str(obj)[:1000]
    except Exception:
        return "<unserializable>"


def _compute_content_hash(content: Any) -> str:
    """
    Compute a deterministic SHA-256 hex digest for the given content.
    
    Parameters:
        content (Any): Value to be serialized and hashed; may be any JSON-serializable or complex object.
    
    Returns:
        str: The SHA-256 hex digest of the safely serialized content, or the literal string "hash_error" if hashing fails.
    """
    try:
        serialized = json.dumps(_safe_serialize(content), sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()
    except Exception:
        return "hash_error"


class AgentOpsCallbackHandler(BaseCallbackHandler):
    """
    LangChain callback handler that captures events for AgentOps Replay.
    
    This handler implements the untrusted producer pattern:
    - Captures events from LangChain callbacks
    - Buffers them locally with ring buffer (prevents OOM)
    - Emits LOG_DROP events when buffer overflows
    - Marks all events with framework version metadata
    
    Args:
        agent_id: Unique identifier for the agent
        local_authority: If True, SDK seals chains locally (testing only).
                        If False, events are sent to server for sealing (production).
        buffer_size: Maximum events in ring buffer before dropping
        redact_pii: If True, hash sensitive fields instead of storing raw values
        tags: Optional list of tags for session metadata
    
    Example:
        handler = AgentOpsCallbackHandler(
            agent_id="customer-support-v2",
            local_authority=True,
            tags=["production", "tier-1"]
        )
        
        llm = ChatOpenAI(callbacks=[handler])
        agent.run("query", callbacks=[handler])
        
        # Export for verification
        handler.end_session()
        handler.export_to_jsonl("session.jsonl")
    """

    def __init__(
        self,
        agent_id: str,
        local_authority: bool = False,
        buffer_size: int = 10000,
        redact_pii: bool = False,
        tags: list[str] | None = None
    ):
        """
        Create a LangChain callback handler that records LangChain events to the AgentOps replay system.
        
        Initializes the handler and its internal AgentOps SDK client, session state, run correlation map, and framework metadata. Validates that LangChain and the AgentOps SDK are available and checks framework compatibility.
        
        Parameters:
            agent_id (str): Identifier for the agent whose events will be recorded.
            local_authority (bool): If True, seal chains locally (useful for testing); if False, rely on server-side sealing.
            buffer_size (int): Size of the internal event buffer used by the AgentOps client.
            redact_pii (bool): If True, redact sensitive fields in recorded payloads with placeholders.
            tags (Optional[List[str]]): Optional list of tags to attach to the session metadata.
        """
        super().__init__()

        if not LANGCHAIN_AVAILABLE:
            raise ImportError(
                "LangChain is not installed. Install with: "
                "pip install langchain langchain-core"
            )

        # Check compatibility and warn if needed
        warn_if_incompatible()

        self.agent_id = agent_id
        self.local_authority = local_authority
        self.redact_pii = redact_pii
        self.tags = tags or []

        # Initialize SDK client
        if AgentOpsClient is None:
            raise ImportError("AgentOps SDK not found. Check installation.")

        self.client = AgentOpsClient(
            local_authority=local_authority,
            buffer_size=buffer_size
        )

        # Session state
        self._session_active = False
        self._session_start_time: float | None = None

        # Track run IDs for correlation
        self._run_id_map: dict[str, dict[str, Any]] = {}

        # Framework metadata
        self._framework_metadata = {
            "framework": "langchain",
            "framework_version": get_langchain_version_string(),
            "integration_version": INTEGRATION_VERSION,
            "compatibility": check_compatibility()
        }

    # =========================================================================
    # Session Management
    # =========================================================================
    
    def start_session(self, additional_tags: Optional[List[str]] = None):
        """
        Start a new AgentOps recording session and register session tags.
        
        Parameters:
            additional_tags (Optional[List[str]]): Extra tags to attach to the session; these are combined with the handler's configured tags and a LangChain version tag.
        
        Raises:
            RuntimeError: If a session is already active.
        """
        if self._session_active:
            raise RuntimeError("Session already active. Call end_session() first.")

        all_tags = self.tags + (additional_tags or [])
        all_tags.append(f"langchain:{get_langchain_version_string()}")

        if self.client:
            self.client.start_session(
                agent_id=self.agent_id,
                tags=all_tags
            )

        self._session_active = True
        self._session_start_time = time.time()
        self._run_id_map = {}
    
    def end_session(self, status: str = "success"):
        """
        End the currently active session and record its final status.
        
        If no session is active this is a no-op. The handler reports the session duration and the provided status to the AgentOps client and marks the session inactive.
        
        Parameters:
            status (str): Final status label for the session (e.g., "success", "failure").
        """
        if not self._session_active:
            return

        start_time = self._session_start_time or time.time()
        duration_ms = int((time.time() - start_time) * 1000)
        
        if self.client:
            self.client.end_session(status=status, duration_ms=duration_ms)
        self._session_active = False
    
    def export_to_jsonl(self, filename: str):
        """
        Export the current session's recorded events to a JSONL file.
        
        Parameters:
            filename (str): Path to the output JSONL file where recorded session events will be written.
        """
        self.client.flush_to_jsonl(filename)
    
    def _ensure_session(self):
        """Auto-start session if not active."""
        if not self._session_active:
            self.start_session()

    # =========================================================================
    # LLM Callbacks
    # =========================================================================

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Record the start of an LLM run and emit a MODEL_REQUEST event to the AgentOps client.
        
        Parameters:
            serialized (Dict[str, Any]): The LLM's serialized configuration/metadata (used to derive model, model_class, and provider).
            prompts (List[str]): The prompts sent to the LLM; may be redacted in the emitted payload depending on handler settings.
            run_id (UUID): Unique identifier for this LLM run.
            parent_run_id (Optional[UUID]): Optional parent run identifier for correlation.
            tags (Optional[List[str]]): Optional tags to attach to the emitted event.
            metadata (Optional[Dict[str, Any]]): Optional additional metadata to include in the event.
        """
        self._ensure_session()

        # Store run info for correlation
        self._run_id_map[str(run_id)] = {
            "type": "llm",
            "start_time": time.time(),
            "model": serialized.get("name", "unknown")
        }

        payload = {
            "run_id": str(run_id),
            "parent_run_id": str(parent_run_id) if parent_run_id else None,
            "model": serialized.get("name", "unknown"),
            "model_class": serialized.get("id", ["unknown"])[-1] if serialized.get("id") else "unknown",
            "provider": self._extract_provider(serialized),
            "prompts": self._maybe_redact(prompts, "prompts"),
            "prompts_hash": _compute_content_hash(prompts) if self.redact_pii else None,
            "tags": tags,
            "metadata": _safe_serialize(metadata),
            **self._framework_metadata
        }

        self.client.record(EventType.MODEL_REQUEST, payload)

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Emit a MODEL_RESPONSE event summarizing an LLM run's output.
        
        Ensures a session is active, computes the run duration, and records a payload that includes run identifiers, the inferred model, a list of generations (each containing the text or a redacted placeholder, an optional content hash when PII redaction is enabled, and any generation metadata), and a safely serialized `llm_output` if present. The payload is sent to the AgentOps client as EventType.MODEL_RESPONSE.
        
        Parameters:
            response (LLMResult): The LLM result object containing one or more generations and optional `llm_output`.
            run_id (UUID): Identifier for the LLM run being finished.
            parent_run_id (Optional[UUID]): Optional parent run identifier for correlation.
        """
        self._ensure_session()

        run_info = self._run_id_map.get(str(run_id), {})
        duration_ms = int((time.time() - run_info.get("start_time", time.time())) * 1000)

        # Extract response content
        generations = []
        if response and response.generations:
            for gen_list in response.generations:
                for gen in gen_list:
                    generations.append({
                        "text": self._maybe_redact(gen.text, "response"),
                        "text_hash": _compute_content_hash(gen.text) if self.redact_pii else None,
                        "generation_info": _safe_serialize(gen.generation_info) if hasattr(gen, 'generation_info') else None
                    })

        payload = {
            "run_id": str(run_id),
            "parent_run_id": str(parent_run_id) if parent_run_id else None,
            "model": run_info.get("model", "unknown"),
            "generations": generations,
            "duration_ms": duration_ms,
            "llm_output": _safe_serialize(response.llm_output) if response and response.llm_output else None
        }

        self.client.record(EventType.MODEL_RESPONSE, payload)
        
        # Clean up run_id_map to prevent memory leak
        self._run_id_map.pop(str(run_id), None)
    
    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Handle an LLM error by recording a standardized error event for the current session.
        
        Documents the error by emitting an error event containing the run correlation IDs, the error type, a trimmed error message (up to 500 characters), and no traceback.
        
        Parameters:
            error (BaseException): The exception raised by the LLM.
            run_id (UUID): The identifier of the LLM run associated with this error.
            parent_run_id (Optional[UUID]): The parent run identifier, if any.
        """
        self._ensure_session()

        payload = {
            "run_id": str(run_id),
            "parent_run_id": str(parent_run_id) if parent_run_id else None,
            "error_type": type(error).__name__,
            "error_message": str(error)[:500],  # Limit error message length
            "error_traceback": None  # Don't log full tracebacks (security)
        }

        self.client.record(EventType.ERROR, payload)
        
        # Clean up run_id_map
        self._run_id_map.pop(str(run_id), None)
    
    # =========================================================================
    # Tool Callbacks
    # =========================================================================

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Record the start of a tool invocation and emit a TOOL_CALL event to the AgentOps client.
        
        Ensures a session is active, registers run metadata for correlation, attempts to parse the tool input (falling back to a raw payload on JSON parse failure), and sends a payload containing tool identity, (possibly redacted) arguments, optional content hash, tags, and metadata to the client.
        
        Parameters:
            serialized (Dict[str, Any]): Tool descriptor from LangChain (expected keys include "name" and "description").
            input_str (str | Any): Raw tool input as provided by LangChain; if a JSON string, it will be parsed into an object, otherwise passed through or wrapped as {"raw_input": input_str}.
            run_id (UUID): Unique identifier for this tool run.
            parent_run_id (Optional[UUID]): Optional identifier of the parent run for correlation.
            tags (Optional[List[str]]): Optional tags associated with this run.
            metadata (Optional[Dict[str, Any]]): Additional arbitrary metadata for the run.
            inputs (Optional[Dict[str, Any]]): (Not used by this handler) preserved for compatibility with LangChain callback signature.
        
        Side effects:
            - Starts a session if none is active.
            - Updates internal run mapping for the given run_id.
            - Emits an EventType.TOOL_CALL event via the AgentOps client with the constructed payload.
        """
        self._ensure_session()

        self._run_id_map[str(run_id)] = {
            "type": "tool",
            "start_time": time.time(),
            "tool_name": serialized.get("name", "unknown")
        }

        # Parse input_str as JSON if possible
        try:
            parsed_inputs = json.loads(input_str) if isinstance(input_str, str) else input_str
        except json.JSONDecodeError:
            parsed_inputs = {"raw_input": input_str}

        payload = {
            "run_id": str(run_id),
            "parent_run_id": str(parent_run_id) if parent_run_id else None,
            "tool_name": serialized.get("name", "unknown"),
            "tool_description": serialized.get("description", ""),
            "args": self._maybe_redact(parsed_inputs, "tool_args"),
            "args_hash": _compute_content_hash(parsed_inputs) if self.redact_pii else None,
            "tags": tags,
            "metadata": _safe_serialize(metadata)
        }

        self.client.record(EventType.TOOL_CALL, payload)

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Record a tool invocation result and emit a TOOL_RESULT event to the AgentOps client.
        
        Parses the tool `output` (attempting JSON), computes the run duration, and builds a payload containing `run_id`, optional `parent_run_id`, the tool name, the (possibly redacted) result, an integrity hash when redaction is enabled, and `duration_ms`; the payload is sent via the client.
        
        Parameters:
            output (str | Any): The raw output produced by the tool; if a string containing JSON, it will be parsed into a structured object, otherwise recorded as `{"raw_output": "..."}`
            run_id (UUID): Identifier for the tool run being recorded.
            parent_run_id (Optional[UUID]): Optional identifier of the parent run, if any.
        """
        self._ensure_session()

        run_info = self._run_id_map.get(str(run_id), {})
        duration_ms = int((time.time() - run_info.get("start_time", time.time())) * 1000)

        # Parse output as JSON if possible
        try:
            parsed_output = json.loads(output) if isinstance(output, str) else output
        except (json.JSONDecodeError, TypeError):
            parsed_output = {"raw_output": str(output)}

        payload = {
            "run_id": str(run_id),
            "parent_run_id": str(parent_run_id) if parent_run_id else None,
            "tool_name": run_info.get("tool_name", "unknown"),
            "result": self._maybe_redact(parsed_output, "tool_result"),
            "result_hash": _compute_content_hash(parsed_output) if self.redact_pii else None,
            "duration_ms": duration_ms
        }

        self.client.record(EventType.TOOL_RESULT, payload)
        
        # Clean up run_id_map
        self._run_id_map.pop(str(run_id), None)
    
    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Handle a tool execution error by recording a structured ERROR event for the current session.
        
        Parameters:
            error (BaseException): The exception raised by the tool.
            run_id (UUID): The identifier for the tool run that errored.
            parent_run_id (Optional[UUID]): The parent run identifier, if any.
        
        Notes:
            Emits an event containing `run_id`, `parent_run_id`, `tool_name` (if known), `error_type`, and a trimmed `error_message`.
        """
        self._ensure_session()

        run_info = self._run_id_map.get(str(run_id), {})

        payload = {
            "run_id": str(run_id),
            "parent_run_id": str(parent_run_id) if parent_run_id else None,
            "tool_name": run_info.get("tool_name", "unknown"),
            "error_type": type(error).__name__,
            "error_message": str(error)[:500]
        }

        self.client.record(EventType.ERROR, payload)
        
        # Clean up run_id_map
        self._run_id_map.pop(str(run_id), None)
    
    # =========================================================================
    # Agent Callbacks
    # =========================================================================

    def on_agent_action(
        self,
        action: AgentAction,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Record an agent decision as a DECISION_TRACE event for the current session.
        
        Builds a payload describing the agent action (including the tool name, tool input —redacted if configured— and the agent log), associates it with the provided run and parent run IDs, and emits a DECISION_TRACE event to the AgentOps client.
        
        Parameters:
            action (AgentAction): The LangChain agent action containing `tool`, `tool_input`, and `log` attributes.
            run_id (UUID): Identifier for the current run.
            parent_run_id (Optional[UUID]): Identifier for the parent run, if any.
        """
        self._ensure_session()

        payload = {
            "run_id": str(run_id),
            "parent_run_id": str(parent_run_id) if parent_run_id else None,
            "action_type": "agent_action",
            "tool": action.tool if hasattr(action, 'tool') else "unknown",
            "tool_input": self._maybe_redact(
                _safe_serialize(action.tool_input) if hasattr(action, 'tool_input') else {},
                "tool_input"
            ),
            "log": action.log if hasattr(action, 'log') else ""
        }

        self.client.record(EventType.DECISION_TRACE, payload)

    def on_agent_finish(
        self,
        finish: AgentFinish,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Record an agent finish decision trace and send it to the AgentOps client.
        
        Builds a payload containing the run identifiers, action_type "agent_finish", safely serialized (and optionally redacted) return values, and the agent log, then records it as a DECISION_TRACE event.
        
        Parameters:
            finish (AgentFinish): Agent finish object; expected to provide `return_values` and `log`.
            run_id (UUID): Identifier for the finished run.
            parent_run_id (Optional[UUID]): Optional parent run identifier for correlation.
        """
        self._ensure_session()

        payload = {
            "run_id": str(run_id),
            "parent_run_id": str(parent_run_id) if parent_run_id else None,
            "action_type": "agent_finish",
            "return_values": self._maybe_redact(
                _safe_serialize(finish.return_values) if hasattr(finish, 'return_values') else {},
                "return_values"
            ),
            "log": finish.log if hasattr(finish, 'log') else ""
        }

        self.client.record(EventType.DECISION_TRACE, payload)

    # =========================================================================
    # Chain Callbacks (optional, for completeness)
    # =========================================================================

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Record the start of a chain run and initialize internal run tracking.
        
        Ensures a session is active, then registers this run in the handler's run map with its type ("chain"), start time, and the chain name extracted from `serialized`.
        
        Parameters:
            serialized (Dict[str, Any]): Chain metadata; may contain a "name" key used as the chain name.
            inputs (Dict[str, Any]): Inputs provided to the chain run; retained for context and potential serialization.
            run_id (UUID): Unique identifier for the chain run being started.
            parent_run_id (Optional[UUID]): Optional identifier of the parent run, if any.
            tags (Optional[List[str]]): Optional tags associated with the chain run.
            metadata (Optional[Dict[str, Any]]): Optional additional metadata for the chain run.
        """
        self._ensure_session()

        self._run_id_map[str(run_id)] = {
            "type": "chain",
            "start_time": time.time(),
            "chain_name": serialized.get("name", "unknown")
        }

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Handle the completion of a chain run.
        
        This callback intentionally performs no actions because detailed outputs and results are captured by LLM and tool callbacks; the method exists to satisfy the LangChain callback interface and preserve run correlation.
        """
        pass  # We rely on tool/llm callbacks for detailed tracking

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Record a chain-level error event to the AgentOps replay client.
        
        Ensures a session is active and emits an ERROR event containing the error type and a message (trimmed to 500 characters) correlated to the given run identifiers.
        
        Parameters:
            error (BaseException): The exception raised by the chain to record.
            run_id (UUID): Identifier of the chain run where the error occurred.
            parent_run_id (Optional[UUID]): Optional identifier of the parent run for correlation.
        """
        self._ensure_session()

        payload = {
            "run_id": str(run_id),
            "parent_run_id": str(parent_run_id) if parent_run_id else None,
            "error_type": type(error).__name__,
            "error_message": str(error)[:500],
            "chain_type": "chain"
        }

        self.client.record(EventType.ERROR, payload)
        
        # Clean up run_id_map to prevent memory leak
        self._run_id_map.pop(str(run_id), None)
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _extract_provider(self, serialized: Dict[str, Any]) -> str:
        """
        Infer a provider identifier from a serialized LLM configuration.
        
        Parameters:
            serialized (Dict[str, Any]): Serialized LLM config expected to contain an "id" key with a list of identifier fragments.
        
        Returns:
            str: A provider name such as "openai", "anthropic", "google", "azure", or "aws_bedrock"; if none match, returns the first element of the `id` list or "unknown" when no `id` is present.
        """
        id_list = serialized.get("id", [])
        if not id_list:
            return "unknown"

        # Look for known providers
        id_str = ".".join(str(x) for x in id_list).lower()

        if "openai" in id_str:
            return "openai"
        if "anthropic" in id_str:
            return "anthropic"
        if "google" in id_str or "gemini" in id_str:
            return "google"
        if "azure" in id_str:
            return "azure"
        if "bedrock" in id_str:
            return "aws_bedrock"

        return id_list[0] if id_list else "unknown"

    def _maybe_redact(self, content: Any, field_name: str) -> Any:
        """
        Return a safe-serializable representation of content or a redaction placeholder.
        
        If PII redaction is disabled, returns a JSON-compatible serialization of `content` produced by _safe_serialize. If PII redaction is enabled, returns the placeholder string "[REDACTED:<field_name>]" where `<field_name>` identifies the redacted field.
        
        Parameters:
            content (Any): The value to serialize or redact.
            field_name (str): Identifier inserted into the redaction placeholder.
        
        Returns:
            Any: The safe-serialized value when not redacted, or a redaction placeholder string when redaction is enabled.
        """
        if not self.redact_pii:
            return _safe_serialize(content)

        # When redacting, replace content with placeholder but preserve hash
        return f"[REDACTED:{field_name}]"