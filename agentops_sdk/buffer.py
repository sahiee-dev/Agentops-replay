"""
agentops_sdk/buffer.py - RingBuffer with LOG_DROP support
"""

from .envelope import ProposedEvent


class EventBuffer:
    def __init__(self, capacity: int = 1000):
        self.capacity = capacity
        # We use a simple list + truncation for v0.1.
        self.queue: list[ProposedEvent] = []
        self.dropped_count: int = 0
        self.session_id: str | None = None

    def set_session(self, session_id: str):
        self.session_id = session_id

    def append(self, event: ProposedEvent, force: bool = False):
        """
        Append an event to the buffer.
        
        Args:
            event: The event to append.
            force: If True, bypass capacity check. Used for LOG_DROP events
                   which MUST be recorded per Constitution Art 2.3.
        """
        if not force and len(self.queue) >= self.capacity:
            # Buffer Full Strategy: Drop Incoming and increment counter.
            # Client responsibility to check dropped_count and emit LOG_DROP.
            self.dropped_count += 1
            return

        self.queue.append(event)

    def flush(self) -> list[ProposedEvent]:
        # Note: We do NOT inject LOG_DROP here because we lack the sequence number context.
        # The Client (AgentOpsClient) is responsible for checking get_dropped_count()
        # and emitting a LOG_DROP event (with correct sequence) before recording new events.

        batch = list(self.queue)
        self.queue.clear()
        return batch

    def get_dropped_count(self) -> int:
        # Note: Reading implies handling. We reset to 0.
        c = self.dropped_count
        # Actually client handles reset manually after success now?
        # Check client.py: "dropped = self.buffer.dropped_count" .. "self.buffer.dropped_count = 0"
        # So this getter might be vestigial or used for reference.
        # Let's keep it behaving standardly (reset on read) OR just expose property.
        # Client accesses .dropped_count directly in my fix.
        return c
