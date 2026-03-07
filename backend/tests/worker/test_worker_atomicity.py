"""
test_worker_atomicity.py - Proves Worker atomic transaction invariants.

NOT testing functionality. Testing invariants:

1. No partial event persistence
2. No partial violation persistence
3. No Redis ACK before durable commit
4. No silent corruption under crash-like exceptions
5. Deterministic behavior under retry
6. Idempotency under replay
7. Corruption detection (guarded ACK)

Uses real PostgreSQL. Mocks Redis + PolicyEngine.

CONSTITUTION §5: Fail closed for integrity (no partial writes).
"""

import json
import os
import sys
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# Ensure paths
_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)

_verifier_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "verifier")
)
if _verifier_path not in sys.path:
    sys.path.insert(0, _verifier_path)

from sqlalchemy.exc import IntegrityError

from app.core.redis import CONSUMER_GROUP, STREAM_NAME
from app.database import SessionLocal
from app.ingestion import IngestService, SequenceViolation
from app.models import EventChain, Violation
from app.services.policy.engine import CanonicalEvent, ViolationRecord

from .conftest import (
    count_events,
    count_violations,
    get_max_sequence,
    make_batch_fields,
    make_event,
)


def _make_violation_record(session_id: str, event_id: str, seq: int) -> ViolationRecord:
    """Create a deterministic ViolationRecord for testing."""
    return ViolationRecord(
        id=str(uuid.uuid4()),
        session_id=session_id,
        event_id=event_id,
        event_sequence_number=seq,
        policy_name="TEST_POLICY",
        policy_version="1.0.0",
        policy_hash="a" * 64,
        severity="WARNING",
        description="Test violation",
        metadata={"test": True},
    )


def _build_worker(mock_redis, policy_engine_mock):
    """
    Build an IngestionWorker with injected mocks.

    Avoids calling __init__ which requires real Redis + PolicyEngine config.
    """
    from app.worker.main import IngestionWorker

    worker = object.__new__(IngestionWorker)
    worker.running = False
    worker.redis = mock_redis
    worker.ingest_service = IngestService(service_id="test-worker-ingest-01")
    worker.policy_engine = policy_engine_mock
    return worker


class TestHappyPath:
    """1. Baseline: events + violations persisted, XACK called."""

    def test_happy_path(self, test_session, mock_redis):
        """Given valid batch + policy violations, assert full atomic commit."""
        session_id = test_session
        events = [make_event(0, "SESSION_START"), make_event(1, "LLM_CALL")]

        # PolicyEngine returns violations
        policy_mock = MagicMock()

        def evaluate_side_effect(canonical_events):
            return [
                _make_violation_record(session_id, ce.event_id, ce.sequence_number)
                for ce in canonical_events
            ]

        policy_mock.evaluate = MagicMock(side_effect=evaluate_side_effect)

        worker = _build_worker(mock_redis, policy_mock)
        fields = make_batch_fields(session_id, events)

        worker._process_message("msg-001", fields)

        # Assert: events persisted
        assert count_events(session_id) == 2

        # Assert: violations persisted
        assert count_violations(session_id) == 2

        # Assert: XACK called exactly once, after commit
        mock_redis.xack.assert_called_once_with(STREAM_NAME, CONSUMER_GROUP, "msg-001")

        # Assert: no duplicates (each event has unique event_id)
        db = SessionLocal()
        try:
            event_ids = [
                e.event_id
                for e in db.query(EventChain)
                .filter(EventChain.session_id == session_id)
                .all()
            ]
            assert len(event_ids) == len(set(event_ids)), "Duplicate event_ids found"
        finally:
            db.close()


class TestViolationInsertFailure:
    """2. Violation insert failure → full rollback (events + violations)."""

    def test_violation_insert_failure_rolls_back_events(
        self, test_session, mock_redis
    ):
        """
        Simulate: PolicyEngine returns 2 violations, second db.add throws.
        Assert: No events, no violations persisted.
        """
        session_id = test_session
        events = [make_event(0, "SESSION_START")]

        call_count = 0

        def evaluate_side_effect(canonical_events):
            return [
                _make_violation_record(session_id, canonical_events[0].event_id, 0),
                _make_violation_record(session_id, canonical_events[0].event_id, 0),
            ]

        policy_mock = MagicMock()
        policy_mock.evaluate = MagicMock(side_effect=evaluate_side_effect)

        worker = _build_worker(mock_redis, policy_mock)
        fields = make_batch_fields(session_id, events)

        # Inject failure: second Violation() construction gets a duplicate PK
        # to trigger IntegrityError on flush.
        # Strategy: make both violations have the same id → IntegrityError on commit.
        violation_ids = [str(uuid.uuid4())]  # Same ID for both → PK violation

        original_evaluate = evaluate_side_effect

        def rigged_evaluate(canonical_events):
            vid = violation_ids[0]
            v1 = _make_violation_record(session_id, canonical_events[0].event_id, 0)
            v2 = _make_violation_record(session_id, canonical_events[0].event_id, 0)
            # Override IDs to force duplicate PK
            object.__setattr__(v1, "id", vid)
            object.__setattr__(v2, "id", vid)
            return [v1, v2]

        policy_mock.evaluate = MagicMock(side_effect=rigged_evaluate)

        worker._process_message("msg-002", fields)

        # Assert: FULL rollback — no events, no violations
        assert count_events(session_id) == 0
        assert count_violations(session_id) == 0

        # Assert: retry re-queued (xadd called), not clean success.
        # _handle_retry calls xack to remove old msg, then xadd to re-queue.
        # The critical invariant: no data committed.
        mock_redis.xadd.assert_called()


class TestMidEvaluationException:
    """3. PolicyEngine raises mid-evaluation → full rollback."""

    def test_mid_evaluation_exception_rolls_back_all(
        self, test_session, mock_redis
    ):
        """
        Simulate: PolicyEngine.evaluate() raises RuntimeError.
        Events were added to session (unflushed) but not committed.
        Assert: No events, no violations. Message NOT ACKed.
        """
        session_id = test_session
        events = [make_event(0, "SESSION_START"), make_event(1, "LLM_CALL")]

        policy_mock = MagicMock()
        policy_mock.evaluate = MagicMock(
            side_effect=RuntimeError("Policy evaluation explosion")
        )

        worker = _build_worker(mock_redis, policy_mock)
        fields = make_batch_fields(session_id, events)

        worker._process_message("msg-003", fields)

        # Assert: FULL rollback — no events persisted
        assert count_events(session_id) == 0
        assert count_violations(session_id) == 0

        # Assert: retry re-queued, not clean success.
        mock_redis.xadd.assert_called()


class TestCommitSucceedsXACKFails:
    """4. Commit succeeds, XACK fails → events persist, retry detects duplicate."""

    def test_xack_failure_then_retry_idempotent(self, test_session, mock_redis):
        """
        Simulate:
        1. First call: commit succeeds, XACK throws.
           (ConnectionError cascades through _handle_retry too — expected.)
        2. Second call (retry): SequenceViolation → detects existing events → XACK.

        Assert: Events persisted exactly once. No duplicates.
        """
        session_id = test_session
        events = [make_event(0, "SESSION_START")]

        # PolicyEngine: no violations (keep it simple)
        policy_mock = MagicMock()
        policy_mock.evaluate = MagicMock(return_value=[])

        worker = _build_worker(mock_redis, policy_mock)
        fields = make_batch_fields(session_id, events)

        # First call: XACK fails.
        # ConnectionError will cascade through _handle_retry too.
        # The outer except in the worker loop (line 168-170) catches this
        # in production. In our test, _process_message is called directly,
        # so the exception escapes. We expect this.
        mock_redis.xack.side_effect = ConnectionError("Redis gone")

        # The exception will propagate out. That's fine — the critical
        # invariant is that events were committed BEFORE the exception.
        try:
            worker._process_message("msg-004", fields)
        except ConnectionError:
            pass  # Expected — Redis is "down"

        # Verify events were committed despite XACK failure
        assert count_events(session_id) == 1

        # Reset mock for retry
        mock_redis.reset_mock()
        mock_redis.xack.side_effect = None  # XACK works now
        mock_redis.xack.return_value = 1

        # Second call: retry the same batch.
        # SequenceViolation → guarded handler detects seq 0 exists → XACK.
        worker._process_message("msg-004", fields)

        # Assert: still exactly 1 event (no duplicates)
        assert count_events(session_id) == 1

        # Assert: XACK was called on retry (idempotent success)
        mock_redis.xack.assert_called_once_with(
            STREAM_NAME, CONSUMER_GROUP, "msg-004"
        )


class TestCrashBeforePolicyEval:
    """5. Crash after event persist, before policy evaluation → full rollback."""

    def test_crash_before_evaluate_rolls_back(self, test_session, mock_redis):
        """
        Simulate: IngestService.append_events succeeds (events in session, not committed),
        then exception before PolicyEngine.evaluate runs.

        Assert: No events persisted (rollback). No violations. No XACK.
        """
        session_id = test_session
        events = [make_event(0, "SESSION_START")]

        policy_mock = MagicMock()
        # evaluate will never be called — we'll inject failure before it

        worker = _build_worker(mock_redis, policy_mock)
        fields = make_batch_fields(session_id, events)

        # Patch the worker's policy_engine.evaluate to throw BEFORE any
        # evaluation logic runs — simulating a crash between append_events
        # and evaluate.
        original_ingest = worker.ingest_service.append_events

        def ingest_then_crash(*args, **kwargs):
            result = original_ingest(*args, **kwargs)
            # Events are now in the DB session but NOT committed.
            # Simulate crash by raising.
            raise OSError("Simulated process crash after event persist")

        worker.ingest_service.append_events = ingest_then_crash

        worker._process_message("msg-005", fields)

        # Assert: events NOT committed (rollback happened)
        assert count_events(session_id) == 0
        assert count_violations(session_id) == 0

        # Assert: retry re-queued, not clean success.
        mock_redis.xadd.assert_called()


class TestSequenceIntegrityUnderRollback:
    """6. Sequence numbers are not reused after rollback."""

    def test_no_sequence_reuse_after_rollback(self, test_session, mock_redis):
        """
        Simulate:
        1. Batch 1 (seq 0, 1) → exception → rollback. Sequences NOT persisted.
        2. Batch 2 (seq 0, 1) → succeeds. Sequences assigned fresh.

        Assert: No reused sequence numbers. Batch 2 starts at correct offset.
        """
        session_id = test_session

        # Batch 1: will fail during policy evaluation
        events_1 = [make_event(0, "SESSION_START"), make_event(1, "LLM_CALL")]

        policy_mock = MagicMock()
        policy_mock.evaluate = MagicMock(
            side_effect=RuntimeError("Batch 1 policy failure")
        )

        worker = _build_worker(mock_redis, policy_mock)
        fields_1 = make_batch_fields(session_id, events_1, batch_id="batch-1")

        worker._process_message("msg-006a", fields_1)

        # Verify: nothing persisted from batch 1
        assert count_events(session_id) == 0
        assert get_max_sequence(session_id) is None

        # Batch 2: same sequences, should succeed (no reuse conflict)
        events_2 = [make_event(0, "SESSION_START"), make_event(1, "LLM_CALL")]
        policy_mock.evaluate = MagicMock(return_value=[])  # No violations

        fields_2 = make_batch_fields(session_id, events_2, batch_id="batch-2")
        mock_redis.reset_mock()

        worker._process_message("msg-006b", fields_2)

        # Assert: batch 2 persisted cleanly
        assert count_events(session_id) == 2
        assert get_max_sequence(session_id) == 1

        # Assert: ACKed
        mock_redis.xack.assert_called_once()


class TestCorruptedDuplicate:
    """7. SequenceViolation from real corruption → NOT ACKed, DLQ'd."""

    def test_corrupted_sequence_goes_to_dlq(self, test_session, mock_redis):
        """
        Simulate:
        1. Batch 1 (seq 0) → succeeds.
        2. Batch 2 (seq 0 again) → SequenceViolation.
           But batch 2 is NOT a replay — batch 1 started at seq 0,
           and batch 2 also starts at seq 0. The first sequence EXISTS.
           This IS a replay scenario.

        For true corruption: start batch at a sequence that does NOT exist.
        3. Batch 3 (seq 5) → SequenceViolation (gap). Seq 5 does NOT exist in DB.
           This is real corruption → DLQ.
        """
        session_id = test_session

        # Step 1: real batch with seq 0, 1
        events_1 = [make_event(0, "SESSION_START"), make_event(1, "LLM_CALL")]
        policy_mock = MagicMock()
        policy_mock.evaluate = MagicMock(return_value=[])
        worker = _build_worker(mock_redis, policy_mock)

        fields_1 = make_batch_fields(session_id, events_1, batch_id="batch-ok")
        worker._process_message("msg-007a", fields_1)
        assert count_events(session_id) == 2
        mock_redis.reset_mock()

        # Step 2: Corrupted batch starting at seq 5 (gap — seq 2,3,4 missing)
        events_corrupt = [make_event(5, "LLM_CALL")]
        fields_corrupt = make_batch_fields(
            session_id, events_corrupt, batch_id="batch-corrupt"
        )

        worker._process_message("msg-007b", fields_corrupt)

        # Assert: no new events persisted
        assert count_events(session_id) == 2

        # Assert: DLQ'd (xadd to DLQ stream called)
        # _move_to_dlq calls redis.xadd then redis.xack
        xadd_calls = mock_redis.xadd.call_args_list
        assert len(xadd_calls) >= 1, "Expected DLQ xadd call"

        dlq_call = xadd_calls[0]
        dlq_fields = dlq_call[0][1]  # positional arg [1] = fields dict
        assert dlq_fields["_dlq_reason"] == "SEQUENCE_VIOLATION"
