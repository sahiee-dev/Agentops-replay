import threading
import pytest
from agentops_sdk.buffer import RingBuffer


def test_buffer_accepts_events_up_to_capacity():
    buf = RingBuffer(capacity=5)
    for i in range(1, 6):
        result = buf.push({"seq": i, "event_type": "LLM_CALL"})
        assert result == True, f"Event {i} should be accepted"
    assert buf.size() == 5


def test_buffer_overflow_triggers_log_drop_not_silent_drop():
    buf = RingBuffer(capacity=3)
    buf.push({"seq": 1})
    buf.push({"seq": 2})
    buf.push({"seq": 3})
    # Buffer full — next push must return False and record the drop
    result = buf.push({"seq": 4})
    assert result == False, "Full buffer must return False"
    assert buf.has_pending_drops() == True, "Must have pending drops recorded"


def test_log_drop_record_has_correct_fields():
    buf = RingBuffer(capacity=2)
    buf.push({"seq": 1})
    buf.push({"seq": 2})
    buf.push({"seq": 3})  # overflow
    buf.push({"seq": 4})  # overflow
    record = buf.get_and_clear_drop_record()
    assert record is not None
    assert hasattr(record, "count"), "Missing field: count"
    assert hasattr(record, "seq_start"), "Missing field: seq_start"
    assert hasattr(record, "seq_end"), "Missing field: seq_end"
    assert hasattr(record, "reason"), "Missing field: reason"
    assert record.count >= 1
    assert record.reason == "buffer_overflow"


def test_buffer_thread_safety():
    buf = RingBuffer(capacity=2000)
    errors = []

    def worker(thread_id):
        try:
            for i in range(100):
                buf.push({"seq": thread_id * 1000 + i, "thread": thread_id})
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Thread errors: {errors}"
    # Total attempted: 1000. All should be in buffer (capacity 2000)
    assert buf.size() == 1000


def test_drain_returns_events_in_seq_order():
    buf = RingBuffer(capacity=10)
    buf.push({"seq": 3, "event_type": "LLM_CALL"})
    buf.push({"seq": 1, "event_type": "SESSION_START"})
    buf.push({"seq": 2, "event_type": "LLM_RESPONSE"})
    events = buf.drain()
    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs), f"Events not in order: {seqs}"
    assert buf.size() == 0, "Buffer must be empty after drain"
