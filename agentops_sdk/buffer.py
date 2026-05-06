"""
agentops_sdk/buffer.py - Thread-safe ring buffer with LOG_DROP support.
"""

import threading
from dataclasses import dataclass
from typing import Optional


@dataclass
class DropRecord:
    seq_start: int
    seq_end: int
    count: int
    reason: str


class RingBuffer:
    """
    Thread-safe ring buffer for event storage.

    When capacity is exceeded:
    - Drop info is accumulated (seq_start, seq_end, count)
    - A LOG_DROP event is emitted when space is available
    - No events are silently lost

    Implementation notes:
    - Uses threading.Lock for all operations
    - deque with maxlen is NOT used (would silently drop — forbidden)
    - Buffer uses a plain list with explicit capacity management
    """

    def __init__(self, capacity: int = 1000) -> None:
        if capacity < 1:
            raise ValueError("buffer_size must be at least 1")
        self._capacity = capacity
        self._events: list[dict] = []
        self._lock = threading.Lock()
        self._drop_record: Optional[DropRecord] = None

    def push(self, event: dict) -> bool:
        """
        Add an event to the buffer.

        Returns True if event was added.
        Returns False if buffer is full (caller must handle LOG_DROP emission).
        Never raises.
        """
        with self._lock:
            if len(self._events) >= self._capacity:
                seq = event.get("seq", 0)
                if self._drop_record is None:
                    self._drop_record = DropRecord(
                        seq_start=seq,
                        seq_end=seq,
                        count=1,
                        reason="buffer_overflow",
                    )
                else:
                    self._drop_record.seq_end = seq
                    self._drop_record.count += 1
                return False

            self._events.append(event)
            return True

    def has_pending_drops(self) -> bool:
        """Returns True if events have been dropped since last flush."""
        with self._lock:
            return self._drop_record is not None

    def get_and_clear_drop_record(self) -> Optional[DropRecord]:
        """
        Returns the current drop record and clears it.
        Called by the SDK before building a LOG_DROP event.
        """
        with self._lock:
            record = self._drop_record
            self._drop_record = None
            return record

    def drain(self) -> list[dict]:
        """
        Returns all events sorted by seq ascending, then clears the buffer.
        Thread-safe. Used by flush_to_jsonl and send_to_server.
        """
        with self._lock:
            events = sorted(self._events, key=lambda e: e.get("seq", 0))
            self._events = []
            return events

    def size(self) -> int:
        """Current number of events in the buffer."""
        with self._lock:
            return len(self._events)

    @property
    def next_seq(self) -> int:
        """Next sequence number to assign."""
        with self._lock:
            if not self._events:
                return 1
            return max(e.get("seq", 0) for e in self._events) + 1
