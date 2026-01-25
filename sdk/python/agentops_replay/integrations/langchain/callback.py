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

import sys
import os
import time
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Union
from uuid import UUID
from datetime import datetime, timezone

# Module logger for debug output
logger = logging.getLogger(__name__)

from .version import (
    INTEGRATION_VERSION, 
    get_langchain_version_string, 
    check_compatibility,
    warn_if_incompatible
)

# Import agentops SDK
try:
    from agentops_sdk.client import AgentOpsClient
    from agentops_sdk.events import EventType
except ImportError:
    # Fallback for direct imports
    AgentOpsClient = None
    EventType = None

# Try to import LangChain
try:
    from langchain_core.callbacks.base import BaseCallbackHandler
    from langchain_core.outputs import LLMResult
    from langchain_core.agents import AgentAction, AgentFinish
    from langchain_core.messages import BaseMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    # Stub for when LangChain is not installed
    BaseCallbackHandler = object
    LLMResult = None
    AgentAction = None
    AgentFinish = None
    BaseMessage = None
    LANGCHAIN_AVAILABLE = False


def _safe_serialize(obj: Any, max_depth: int = 5) -> Any:
    """
    Safely serialize an object to JSON-compatible format.
    Handles complex LangChain objects without crashing.
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
    """Compute SHA-256 hash of content for redaction support."""
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
        tags: Optional[List[str]] = None
    ):
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
        self._session_start_time: Optional[float] = None
        
        # Track run IDs for correlation
        self._run_id_map: Dict[str, Dict[str, Any]] = {}
        
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
        """Start a new recording session."""
        if self._session_active:
            raise RuntimeError("Session already active. Call end_session() first.")
        
        all_tags = self.tags + (additional_tags or [])
        all_tags.append(f"langchain:{get_langchain_version_string()}")
        
        self.client.start_session(
            agent_id=self.agent_id,
            tags=all_tags
        )
        
        self._session_active = True
        self._session_start_time = time.time()
        self._run_id_map = {}
    
    def end_session(self, status: str = "success"):
        """End the current session and seal the chain."""
        if not self._session_active:
            return
        
        duration_ms = int((time.time() - self._session_start_time) * 1000)
        self.client.end_session(status=status, duration_ms=duration_ms)
        self._session_active = False
    
    def export_to_jsonl(self, filename: str):
        """Export session to JSONL file for verification."""
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
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM starts processing."""
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
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM finishes processing."""
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
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM errors."""
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
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        inputs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when tool starts executing."""
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
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when tool finishes."""
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
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when tool errors."""
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
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when agent takes an action."""
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
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when agent finishes."""
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
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when chain starts."""
        self._ensure_session()
        
        self._run_id_map[str(run_id)] = {
            "type": "chain",
            "start_time": time.time(),
            "chain_name": serialized.get("name", "unknown")
        }
    
    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when chain ends."""
        # Clean up run_id_map to prevent memory leak
        self._run_id_map.pop(str(run_id), None)
    
    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when chain errors."""
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
        """Extract provider name from serialized LLM config."""
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
        """Redact content if PII redaction is enabled."""
        if not self.redact_pii:
            return _safe_serialize(content)
        
        # When redacting, replace content with placeholder but preserve hash
        return f"[REDACTED:{field_name}]"
