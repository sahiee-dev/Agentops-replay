"""
Terrarium → AgentOps Replay Adapter
====================================
Wraps Terrarium's BlackboardLogger to produce a tamper-evident,
hash-chained audit record alongside Terrarium's existing logs.

Usage in a Terrarium simulation:
    from examples.terrarium_adapter.terrarium_adapter import AuditedBlackboardLogger
    # Replace BlackboardLogger with AuditedBlackboardLogger in your simulation

What changes:
    - Every call to log_blackboard_state() also records a hash-chained event
    - On simulation end, call adapter.finalize("session.jsonl")
    - Run: agentops-verify session.jsonl → PASS ✅ AUTHORITATIVE_EVIDENCE

What does NOT change:
    - All existing Terrarium log files are still written normally
    - blackboard_{id}.txt is still written
    - No Terrarium code is modified
    - Simulation behavior is identical
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

# ── AgentOps Replay SDK import ────────────────────────────────────────────────
# Resolve path to AgentOps Replay repo root from this file's location
_ADAPTER_DIR = Path(__file__).parent
_AGENTOPS_ROOT = _ADAPTER_DIR.parent.parent  # examples/terrarium_adapter/../../
sys.path.insert(0, str(_AGENTOPS_ROOT))

try:
    from agentops_sdk.client import AgentOpsClient
    from agentops_sdk.events import EventType
except ImportError as e:
    raise ImportError(
        "AgentOps Replay SDK not found. "
        "Run: pip install -e '.' from the AgentOps Replay repo root."
    ) from e

# ── Terrarium BlackboardLogger import ─────────────────────────────────────────
try:
    from src.logger import BlackboardLogger as _TerrariumBlackboardLogger
    _TERRARIUM_AVAILABLE = True
except ImportError:
    # Terrarium not installed — create a minimal stub for testing
    _TERRARIUM_AVAILABLE = False

    class _TerrariumBlackboardLogger:  # type: ignore[no-redef]
        """Stub when Terrarium is not installed."""
        def __init__(self, log_dir, board_id, *args, **kwargs):
            self.log_dir = Path(log_dir)
            self.board_id = board_id
            self.log_dir.mkdir(parents=True, exist_ok=True)

        def log_blackboard_state(self, board_id, state, iteration, phase, *args, **kwargs):
            pass

        def log_blackboard_creation(self, *args, **kwargs):
            pass

        def log_blackboard_join(self, *args, **kwargs):
            pass

        def log_blackboard_exit(self, *args, **kwargs):
            pass


class AuditedBlackboardLogger(_TerrariumBlackboardLogger):
    """
    Drop-in replacement for Terrarium's BlackboardLogger.

    Every log_blackboard_state() call:
    1. Writes the existing Terrarium log files (unchanged)
    2. Records a hash-chained TOOL_RESULT event in AgentOps Replay
       with board_state_hash = SHA-256 of the full board state JSON

    Call finalize(output_path) when the simulation ends to write the
    AgentOps JSONL and confirm the chain is intact.
    """

    def __init__(
        self,
        log_dir: str | Path,
        board_id: str,
        *args,
        agentops_output: str | None = None,
        agentops_server_url: str | None = None,
        **kwargs,
    ) -> None:
        """
        Parameters
        ----------
        log_dir : str | Path
            Passed to Terrarium's BlackboardLogger unchanged.
        board_id : str
            Passed to Terrarium's BlackboardLogger unchanged.
        agentops_output : str | None
            Path where the AgentOps JSONL will be written.
            Default: log_dir/agentops_audit.jsonl
        agentops_server_url : str | None
            If set, use server-authority mode (AUTHORITATIVE_EVIDENCE).
            If None, use local-authority mode (NON_AUTHORITATIVE_EVIDENCE).
        """
        # Init Terrarium's logger (writes existing log files)
        super().__init__(log_dir, board_id, *args, **kwargs)

        # Set up AgentOps output path
        self._agentops_output = agentops_output or str(
            Path(log_dir) / "agentops_audit.jsonl"
        )
        self._board_id = board_id
        self._event_count = 0

        # Init AgentOps client
        local_authority = agentops_server_url is None
        self._client = AgentOpsClient(
            local_authority=local_authority,
            server_url=agentops_server_url,
        )
        self._session_id = self._client.start_session(
            agent_id=f"terrarium-blackboard-{board_id}",
            metadata={
                "model_id": "terrarium",
                "framework": "terrarium",
                "board_id": board_id,
                "log_dir": str(log_dir),
            },
        )

    def log_blackboard_state(
        self,
        board_id: str,
        state: Any,
        iteration: int,
        phase: str,
        *args,
        **kwargs,
    ) -> None:
        """
        Override: write Terrarium's log AND record AgentOps event.
        """
        # Step 1: Write Terrarium's existing log files (unchanged)
        if _TERRARIUM_AVAILABLE:
            super().log_blackboard_state(board_id, state, iteration, phase, *args, **kwargs)

        # Step 2: Record in AgentOps hash chain
        try:
            # Hash the full board state — never store raw content
            state_bytes = json.dumps(state, sort_keys=True, ensure_ascii=False).encode()
            state_hash = hashlib.sha256(state_bytes).hexdigest()

            self._client.record(
                EventType.TOOL_RESULT,
                {
                    "tool_name": f"blackboard_{board_id}",
                    "result_hash": state_hash,
                    "result_summary": (
                        f"board_state board={board_id} "
                        f"iter={iteration} phase={phase}"
                    ),
                },
            )
            self._event_count += 1
        except Exception as e:
            # Never crash the simulation — AgentOps SDK handles LOG_DROP internally
            # but we add an outer guard here for safety
            print(f"[AgentOps] Warning: failed to record board state: {e}")

    def log_blackboard_creation(self, *args, **kwargs) -> None:
        if _TERRARIUM_AVAILABLE:
            super().log_blackboard_creation(*args, **kwargs)
        self._client.record(
            EventType.TOOL_CALL,
            {
                "tool_name": f"blackboard_create_{self._board_id}",
                "args_hash": "0" * 64,
                "args_summary": f"blackboard created board={self._board_id}",
            },
        )

    def log_blackboard_join(self, agent_name: str, *args, **kwargs) -> None:
        if _TERRARIUM_AVAILABLE:
            super().log_blackboard_join(agent_name, *args, **kwargs)
        self._client.record(
            EventType.TOOL_CALL,
            {
                "tool_name": "blackboard_join",
                "args_hash": hashlib.sha256(agent_name.encode()).hexdigest(),
                "args_summary": f"agent={agent_name} joined board={self._board_id}",
            },
        )

    def log_blackboard_exit(self, agent_name: str, *args, **kwargs) -> None:
        if _TERRARIUM_AVAILABLE:
            super().log_blackboard_exit(agent_name, *args, **kwargs)
        self._client.record(
            EventType.TOOL_RESULT,
            {
                "tool_name": "blackboard_exit",
                "result_hash": hashlib.sha256(agent_name.encode()).hexdigest(),
                "result_summary": f"agent={agent_name} exited board={self._board_id}",
            },
        )

    def finalize(self, output_path: str | None = None) -> str:
        """
        End the AgentOps session and write the audit JSONL.

        Call this when the simulation ends.

        Returns
        -------
        str
            Path to the written JSONL file.
        """
        self._client.end_session(status="success")
        out = output_path or self._agentops_output
        self._client.flush_to_jsonl(out)
        return out
