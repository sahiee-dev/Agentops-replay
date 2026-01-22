"""
agentops_sdk/client.py - Main SDK Entry Point
"""
from typing import Optional, Dict, Any, List
from .events import EventType, SCHEMA_VER, validate_payload
from .envelope import ProposedEvent, create_proposal
from .buffer import EventBuffer
import uuid
import datetime

class AgentOpsClient:
    def __init__(self, local_authority: bool = False, buffer_size: int = 1000):
        self.local_authority = local_authority
        self.buffer = EventBuffer(capacity=buffer_size)
        self.session_id: Optional[str] = None
        self.sequence_counter: int = 0
        self.prev_hash: Optional[str] = None
        
    def start_session(self, agent_id: str, tags: List[str] = None):
        if self.session_id:
            raise RuntimeError("Session already active")
            
        self.session_id = str(uuid.uuid4())
        self.buffer.set_session(self.session_id)
        self.sequence_counter = 0
        self.prev_hash = None
        
        payload = {
            "agent_id": agent_id,
            "tags": tags or [],
            "environment": "dev", # Default, should be config
            "framework": "python-sdk-raw",
            "framework_version": "0.0.1",
            "sdk_version": "0.1.0"
        }
        self.record(EventType.SESSION_START, payload)

    def record(self, event_type: EventType, payload: Dict[str, Any]):
        if not self.session_id:
            raise RuntimeError("No active session")
            
        # 1. Strict Validation
        validate_payload(event_type, payload)
        
        # 2. Check for Drop Injection  
        dropped = self.buffer.dropped_count  # Read but don't reset yet
        if dropped > 0:
            drop_payload = {
                "dropped_events": dropped,
                "reason": "buffer_overflow"
            }
            try:
                self._emit_proposal(EventType.LOG_DROP, drop_payload)
                # Only reset after successful emission
                self.buffer.dropped_count = 0
            except Exception:
                # If emission fails, preserve drop count for next attempt
                raise
            
        # 3. Emit Proposal
        self._emit_proposal(event_type, payload)
        
    def _emit_proposal(self, event_type: EventType, payload: Dict[str, Any]):
        # Create Proposal
        proposal = create_proposal(
            session_id=self.session_id,
            seq=self.sequence_counter,
            event_type=event_type,
            payload=payload,
            prev_hash=self.prev_hash,
            local_authority=self.local_authority
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
                "prev_event_hash": proposal.prev_event_hash
            }
            import hashlib
            canonical_env = jcs.canonicalize(signed_obj)
            self.prev_hash = hashlib.sha256(canonical_env).hexdigest()
            
        self.buffer.append(proposal)

    def end_session(self, status: str, duration_ms: int):
        self.record(EventType.SESSION_END, {"status": status, "duration_ms": duration_ms})
        
        if self.local_authority:
            # Emit CHAIN_SEAL
            validate_payload(EventType.CHAIN_SEAL, {"final_event_hash": self.prev_hash})
            self._emit_proposal(EventType.CHAIN_SEAL, {"final_event_hash": self.prev_hash})

    def flush_to_jsonl(self, filename: str):
        """Helper for local testing"""
        events = self.buffer.flush()
        # In Local Authority mode, these are full events.
        # In Remote mode, these are proposals.
        
        import json
        with open(filename, 'w') as f:
            for e in events:
                f.write(json.dumps(e.to_dict()) + '\n')
