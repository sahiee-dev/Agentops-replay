"""
agentops_sdk/client.py - Main SDK Entry Point
"""

import hashlib
import os
import sys
from typing import Any

from .buffer import EventBuffer
from .envelope import create_proposal
from .events import EventType, validate_payload

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "verifier"))
)
import uuid

import jcs


class AgentOpsClient:
    def __init__(self, local_authority: bool = False, buffer_size: int = 1000):
        self.local_authority = local_authority
        self.buffer = EventBuffer(capacity=buffer_size)
        self.session_id: str | None = None
        self.sequence_counter: int = 0
        self.prev_hash: str | None = None

    def start_session(self, agent_id: str, tags: list[str] | None = None):
        if self.session_id:
            raise RuntimeError("Session already active")

        self.session_id = str(uuid.uuid4())
        self.buffer.set_session(self.session_id)
        self.sequence_counter = 0
        self.prev_hash = None

        payload = {
            "agent_id": agent_id,
            "tags": tags or [],
            "environment": "dev",  # Default, should be config
            "framework": "python-sdk-raw",
            "framework_version": "0.0.1",
            "sdk_version": "0.1.0",
        }
        self.record(EventType.SESSION_START, payload)

    def record(self, event_type: EventType, payload: dict[str, Any]):
        if not self.session_id:
            raise RuntimeError("No active session")

        # 1. Strict Validation
        validate_payload(event_type, payload)

        # 2. Check for Drop Injection
        dropped = self.buffer.dropped_count  # Read but don't reset yet
        if dropped > 0:
            # LOG_DROP required fields per events.py: dropped_count, cumulative_drops, drop_reason
            drop_payload = {
                "dropped_count": dropped,
                "cumulative_drops": dropped,  # For now, same as dropped_count (no cumulative tracking yet)
                "drop_reason": "buffer_overflow",
            }
            try:
                # force=True: LOG_DROP MUST bypass buffer capacity (Constitution Art 2.3)
                self._emit_proposal(EventType.LOG_DROP, drop_payload, force=True)
                # Only reset after successful emission
                self.buffer.dropped_count = 0
            except Exception:
                # If emission fails, preserve drop count for next attempt
                raise

        # 3. Emit Proposal
        self._emit_proposal(event_type, payload)

    def _emit_proposal(
        self, event_type: EventType, payload: dict[str, Any], force: bool = False
    ):
        """
        Create and buffer an event proposal.
        
        Args:
            event_type: Type of event.
            payload: Event payload.
            force: If True, bypass buffer capacity (for LOG_DROP).
        """
        # Create Proposal
        proposal = create_proposal(
            session_id=self.session_id,
            seq=self.sequence_counter,
            event_type=event_type,
            payload=payload,
            prev_hash=self.prev_hash,
            local_authority=self.local_authority,
        )

        # Update State
        self.sequence_counter += 1
        if self.local_authority:
            # In local mode, we trust our own hash
            self.prev_hash = proposal.event_hash
        else:
            # In server mode, SDK still computes hash as hint for server validation
            # Server may re-stamp, but SDK tracks its own chain for integrity
            signed_obj = {
                "event_id": proposal.event_id,
                "session_id": proposal.session_id,
                "sequence_number": proposal.sequence_number,
                "timestamp_wall": proposal.timestamp_wall,
                "event_type": proposal.event_type,
                "payload_hash": proposal.payload_hash,
                "prev_event_hash": proposal.prev_event_hash,
            }
            canonical_env = jcs.canonicalize(signed_obj)
            self.prev_hash = hashlib.sha256(canonical_env).hexdigest()

        self.buffer.append(proposal, force=force)

    def end_session(self, status: str, duration_ms: int):
        self.record(
            EventType.SESSION_END, {"status": status, "duration_ms": duration_ms}
        )

        if self.local_authority and self.prev_hash is not None:
            # Emit CHAIN_SEAL only if we have a valid prev_hash
            validate_payload(EventType.CHAIN_SEAL, {"final_event_hash": self.prev_hash})
            self._emit_proposal(
                EventType.CHAIN_SEAL, {"final_event_hash": self.prev_hash}
            )

    def flush_to_jsonl(self, filename: str):
        """Helper for local testing"""
        events = self.buffer.flush()
        # In Local Authority mode, these are full events.
        # In Remote mode, these are proposals.

        import json

        with open(filename, "w") as f:
            for e in events:
                f.write(json.dumps(e.to_dict()) + "\n")
