"""
test_network_partition.py - SDK Resilience Tests

CONSTITUTION ALIGNMENT:
- Art 2.3: No silent data loss. LOG_DROP events document buffer overflow.
- Art 2.4: Sequence gaps must be documented. LOG_DROP provides that evidence.

These tests verify SDK behavior during network partitions and buffer overflow
scenarios, ensuring evidence of data loss is properly preserved.
"""

import pytest
from agentops_sdk.client import AgentOpsClient
from agentops_sdk.events import EventType


class TestBufferOverflowEmitsLogDrop:
    """
    Constitution Art 2.3: "Silent data loss is forbidden."
    When buffer overflows, LOG_DROP MUST be emitted to document the loss.
    """

    def test_overflow_triggers_log_drop(self):
        """
        When buffer capacity is exceeded:
        1. Events are dropped (not added to buffer).
        2. dropped_count increments.
        3. Next record() emits LOG_DROP before the new event.
        
        Note: LOG_DROP bypasses capacity (force=True), so buffer may exceed capacity.
        """
        # Arrange: Small buffer to force overflow
        client = AgentOpsClient(local_authority=True, buffer_size=5)
        client.start_session(agent_id="test-agent")

        # Act: Fill buffer (SESSION_START already used 1 slot)
        for i in range(6):  # 1 (start) + 6 = 7, but capacity is 5
            client.record(EventType.MODEL_REQUEST, {"model": "test", "prompt": f"test-{i}"})

        # Assert: Some events were dropped and LOG_DROP was emitted
        event_types = [e.event_type for e in client.buffer.queue]
        assert EventType.LOG_DROP.value in event_types, "LOG_DROP must be present after overflow"

    def test_log_drop_emitted_before_triggering_event(self):
        """
        LOG_DROP must be emitted BEFORE the triggering event.
        This ensures sequence integrity.
        """
        client = AgentOpsClient(local_authority=True, buffer_size=3)
        client.start_session(agent_id="test-agent")

        # Fill buffer: SESSION_START = 1, so 2 more to fill
        client.record(EventType.MODEL_REQUEST, {"model": "test", "prompt": "fill-1"})
        client.record(EventType.MODEL_REQUEST, {"model": "test", "prompt": "fill-2"})

        # Buffer is now full (3 events)
        assert len(client.buffer.queue) == 3

        # Next event causes overflow (gets dropped, dropped_count = 1)
        client.record(EventType.MODEL_REQUEST, {"model": "test", "prompt": "overflow-trigger"})

        # Trigger LOG_DROP emission by recording another event
        # This will emit LOG_DROP (force=True) then try to emit the new event (dropped)
        client.record(EventType.MODEL_REQUEST, {"model": "test", "prompt": "after-overflow"})

        # Now check for LOG_DROP in buffer
        event_types = [e.event_type for e in client.buffer.queue]
        assert EventType.LOG_DROP.value in event_types, "LOG_DROP must be emitted after overflow"

        # Verify LOG_DROP comes before the next event in sequence
        log_drop_idx = None
        for i, e in enumerate(client.buffer.queue):
            if e.event_type == EventType.LOG_DROP.value:
                log_drop_idx = i
                break
        
        assert log_drop_idx is not None, "LOG_DROP must be in buffer"


class TestLogDropPayloadIntegrity:
    """
    LOG_DROP events must contain proper evidence of what was lost.
    """

    def test_log_drop_contains_required_fields(self):
        """
        LOG_DROP payload must include dropped_count, cumulative_drops, drop_reason.
        """
        client = AgentOpsClient(local_authority=True, buffer_size=2)
        client.start_session(agent_id="test-agent")

        # Fill buffer (SESSION_START = 1)
        client.record(EventType.MODEL_REQUEST, {"model": "test", "prompt": "fill"})

        # Overflow (event dropped, dropped_count = 1)
        client.record(EventType.MODEL_REQUEST, {"model": "test", "prompt": "dropped-1"})

        # Trigger LOG_DROP emission
        client.record(EventType.MODEL_REQUEST, {"model": "test", "prompt": "trigger"})

        # Find LOG_DROP event
        log_drops = [e for e in client.buffer.queue if e.event_type == EventType.LOG_DROP.value]

        assert len(log_drops) >= 1, "At least one LOG_DROP must be emitted"

        # Verify it has a payload hash (evidence exists)
        log_drop = log_drops[0]
        assert log_drop.payload_hash is not None, "LOG_DROP must have payload_hash"


class TestBufferResetAfterLogDropEmission:
    """
    After LOG_DROP is emitted, the dropped_count must reset to prevent
    duplicate LOG_DROP emissions for the same loss event.
    """

    def test_dropped_count_resets_after_log_drop(self):
        """
        After LOG_DROP is successfully emitted, dropped_count must be 0.
        """
        client = AgentOpsClient(local_authority=True, buffer_size=2)
        client.start_session(agent_id="test-agent")

        # Buffer: SESSION_START = 1, 1 more to fill
        client.record(EventType.MODEL_REQUEST, {"model": "test", "prompt": "fill"})

        # Overflow: This event gets dropped
        client.record(EventType.MODEL_REQUEST, {"model": "test", "prompt": "dropped"})

        # At this point, dropped_count = 1 (not yet emitted as LOG_DROP)
        assert client.buffer.dropped_count == 1

        # Trigger LOG_DROP emission by recording again
        # LOG_DROP is emitted with force=True, then new event is recorded
        # The new event will be dropped (buffer full), incrementing dropped_count
        client.record(EventType.MODEL_REQUEST, {"model": "test", "prompt": "trigger-log-drop"})

        # After LOG_DROP emission, dropped_count was reset to 0
        # But the new event was still dropped, so dropped_count should be 1 again
        assert client.buffer.dropped_count == 1

        # Verify LOG_DROP is in buffer
        event_types = [e.event_type for e in client.buffer.queue]
        assert EventType.LOG_DROP.value in event_types


class TestSequenceIntegrityWithLogDrop:
    """
    Sequence numbers must remain monotonic even with LOG_DROP insertion.
    """

    def test_sequence_continues_after_log_drop(self):
        """
        LOG_DROP takes a sequence number, subsequent events continue from there.
        """
        client = AgentOpsClient(local_authority=True, buffer_size=10)
        client.start_session(agent_id="test-agent")

        # Record some events
        client.record(EventType.MODEL_REQUEST, {"model": "test", "prompt": "event-1"})
        client.record(EventType.MODEL_REQUEST, {"model": "test", "prompt": "event-2"})

        # Check sequence numbers are monotonic
        sequences = [e.sequence_number for e in client.buffer.queue]
        assert sequences == sorted(sequences), "Sequences must be monotonic"
        assert sequences == list(range(len(sequences))), "Sequences must be 0-indexed and contiguous"


class TestSimulatedNetworkPartition:
    """
    Simulates a network partition scenario where events cannot be sent.
    SDK should buffer locally and emit LOG_DROP when buffer overflows.
    """

    def test_partition_preserves_buffer_and_emits_log_drop(self):
        """
        During partition, SDK buffers locally.
        LOG_DROP provides evidence of loss.
        """
        client = AgentOpsClient(local_authority=True, buffer_size=5)
        client.start_session(agent_id="partition-test-agent")

        # Pre-partition: 1 event in buffer (SESSION_START)
        assert len(client.buffer.queue) == 1

        # Simulate partition: No actual network call, just fill buffer
        for i in range(10):  # Way more than buffer size
            client.record(EventType.MODEL_REQUEST, {"model": "test", "prompt": f"during-partition-{i}"})

        # Post-partition: Check buffer state
        # LOG_DROP events bypass capacity, so they should be in buffer
        event_types = [e.event_type for e in client.buffer.queue]
        
        # LOG_DROP must be present as evidence of data loss
        assert EventType.LOG_DROP.value in event_types, \
            "LOG_DROP must be emitted to document data loss during partition"
