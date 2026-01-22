"""
agentops_sdk/buffer.py - RingBuffer with LOG_DROP support
"""
from typing import List, Optional
from .events import EventType, SCHEMA_VER
from .envelope import ProposedEvent, create_proposal
import uuid
import datetime

class EventBuffer:
    def __init__(self, capacity: int = 1000):
        self.capacity = capacity
        # We use a simple list + truncation for v0.1. 
        # Real impl: collections.deque with maxlen? 
        # Issue with deque: need to inject LOG_DROP when full.
        self.queue: List[ProposedEvent] = []
        self.dropped_count: int = 0
        self.session_id: Optional[str] = None
        
    def set_session(self, session_id: str):
        self.session_id = session_id

    def append(self, event: ProposedEvent):
        if len(self.queue) >= self.capacity:
            # Buffer Full Strategy: Drop oldest? Or drop incoming?
            # Spec says: "events buffered locally. If buffer fills, DROP events and log DROP_COUNT meta-event."
            # Dropping incoming preserves history. Dropping oldest preserves recent.
            # Usually incidents require recent context.
            # Strategy: Drop NEWEST (reject incoming) until flush?
            # Actually, "Drop events... log meta-event". 
            # If we drop incoming, we lose the "cause" of the drop potentially.
            # Let's Drop Incoming and increment a counter. 
            self.dropped_count += 1
            return
            
        self.queue.append(event)
        
    def flush(self) -> List[ProposedEvent]:
        # If we have dropped events, we MUST inject a LOG_DROP event at the end (or start of next batch?)
        # Spec: "Log DROP_COUNT meta-event."
        if self.dropped_count > 0:
            if not self.session_id:
                # Can't log if no session. Just return what we have.
                pass 
            else:
                # Create LOG_DROP
                # Note: Sequence number assignment happens here? 
                # Ideally Buffer shouldn't assign Sequence. Client does. 
                # But LOG_DROP is meta.
                # Let's return the queue, and let Client handle LOG_DROP insertion if dropped > 0?
                # No, Buffer should own the "state" of drops.
                pass 
        
        # Simple flush
        batch = list(self.queue)
        self.queue.clear()
        
        # We do NOT reset dropped_count here because we haven't successfully emitted LOG_DROP yet?
        # Actually Client.flush() calls Buffer.flush(). 
        # Client needs to know about drops.
        return batch

    def get_dropped_count(self) -> int:
        c = self.dropped_count
        self.dropped_count = 0
        return c
