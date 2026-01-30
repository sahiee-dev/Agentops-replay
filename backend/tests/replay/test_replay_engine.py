"""
test_replay_engine.py - Unit tests for replay system.

Tests cover:
1. Gap detection
2. LOG_DROP rendering
3. Determinism
4. Verification failure
5. Anti-inference (no synthetic events)
"""

import sys
import os
import pytest
from typing import List, Dict, Any

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'app'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'verifier'))

from app.replay.engine import load_verified_session, build_replay, get_frame_at_sequence
from app.replay.frames import FrameType, VerificationStatus
from app.replay.warnings import WarningCode


class TestGapDetection:
    """Tests for sequence gap detection."""
    
    def test_gap_detected_in_replay(self):
        """ADVERSARIAL: Gaps must be explicit, not smoothed."""
        events = [
            {"sequence_number": 0, "event_type": "SESSION_START", "event_hash": "abc", "payload": {}},
            {"sequence_number": 1, "event_type": "LLM_CALL", "event_hash": "def", "payload": {}},
            # Gap: 2, 3, 4 missing
            {"sequence_number": 5, "event_type": "LLM_RESPONSE", "event_hash": "ghi", "payload": {}},
            {"sequence_number": 6, "event_type": "SESSION_END", "event_hash": "jkl", "payload": {}},
        ]
        
        chain, failure = load_verified_session("test-session", events, None)
        assert chain is not None, "Chain should be valid"
        
        replay = build_replay(chain)
        
        # Find GAP frame
        gap_frames = [f for f in replay.frames if f.frame_type == FrameType.GAP]
        assert len(gap_frames) == 1, "Should have exactly one GAP frame"
        
        gap = gap_frames[0]
        assert gap.gap_start == 2, "Gap should start at sequence 2"
        assert gap.gap_end == 4, "Gap should end at sequence 4"
        
        # Verify warning exists
        gap_warnings = [w for w in replay.warnings if w.code == WarningCode.SEQUENCE_GAP]
        assert len(gap_warnings) == 1, "Should have gap warning"
    
    def test_no_gap_for_contiguous(self):
        """No GAP frames for contiguous sequences."""
        events = [
            {"sequence_number": 0, "event_type": "SESSION_START", "event_hash": "a", "payload": {}},
            {"sequence_number": 1, "event_type": "LLM_CALL", "event_hash": "b", "payload": {}},
            {"sequence_number": 2, "event_type": "SESSION_END", "event_hash": "c", "payload": {}},
        ]
        
        chain, _ = load_verified_session("test", events, None)
        replay = build_replay(chain)
        
        gap_frames = [f for f in replay.frames if f.frame_type == FrameType.GAP]
        assert len(gap_frames) == 0, "No gaps in contiguous chain"


class TestLogDropRendering:
    """Tests for LOG_DROP event rendering."""
    
    def test_log_drop_creates_frame_and_warning(self):
        """LOG_DROP events become LOG_DROP frames with warnings."""
        events = [
            {"sequence_number": 0, "event_type": "SESSION_START", "event_hash": "a", "payload": {}},
            {"sequence_number": 1, "event_type": "LLM_CALL", "event_hash": "b", "payload": {}},
            {
                "sequence_number": 2, 
                "event_type": "LOG_DROP", 
                "event_hash": "c",
                "payload": {"dropped_count": 5, "reason": "BUFFER_FULL"}
            },
            {"sequence_number": 3, "event_type": "SESSION_END", "event_hash": "d", "payload": {}},
        ]
        
        chain, _ = load_verified_session("test", events, None)
        replay = build_replay(chain)
        
        # Find LOG_DROP frame
        drop_frames = [f for f in replay.frames if f.frame_type == FrameType.LOG_DROP]
        assert len(drop_frames) == 1
        
        drop = drop_frames[0]
        assert drop.dropped_count == 5
        assert drop.drop_reason == "BUFFER_FULL"
        
        # Check warning
        drop_warnings = [w for w in replay.warnings if w.code == WarningCode.EVENTS_DROPPED]
        assert len(drop_warnings) == 1
        assert "5" in drop_warnings[0].message
        
        # Check total drops
        assert replay.total_drops == 5


class TestDeterminism:
    """Tests for deterministic replay."""
    
    def test_same_input_same_output(self):
        """CRITICAL: Same events must produce identical replay."""
        events = [
            {"sequence_number": 0, "event_type": "SESSION_START", "event_hash": "a", "payload": {"x": 1}},
            {"sequence_number": 1, "event_type": "LLM_CALL", "event_hash": "b", "payload": {"prompt": "hello"}},
            {"sequence_number": 2, "event_type": "SESSION_END", "event_hash": "c", "payload": {}},
        ]
        
        # Run twice
        chain1, _ = load_verified_session("test", events, None)
        replay1 = build_replay(chain1)
        
        chain2, _ = load_verified_session("test", events, None)
        replay2 = build_replay(chain2)
        
        # Compare
        assert len(replay1.frames) == len(replay2.frames)
        
        for f1, f2 in zip(replay1.frames, replay2.frames):
            assert f1.frame_type == f2.frame_type
            assert f1.sequence_number == f2.sequence_number
            assert f1.event_hash == f2.event_hash
            assert f1.payload == f2.payload


class TestVerificationFailure:
    """Tests for verification failure handling."""
    
    def test_missing_sequence_fails(self):
        """Events missing sequence_number must fail verification."""
        events = [
            {"event_type": "SESSION_START", "event_hash": "a", "payload": {}},  # No sequence!
        ]
        
        chain, failure = load_verified_session("test", events, None)
        
        assert chain is None, "Chain should be None on failure"
        assert failure is not None, "Should have failure object"
        assert failure.verification_status == VerificationStatus.INVALID
        assert "MISSING_SEQUENCE" in failure.error_code
    
    def test_non_monotonic_fails(self):
        """Non-monotonic sequences must fail verification."""
        events = [
            {"sequence_number": 0, "event_type": "START", "event_hash": "a", "payload": {}},
            {"sequence_number": 3, "event_type": "CALL", "event_hash": "b", "payload": {}},
            {"sequence_number": 2, "event_type": "END", "event_hash": "c", "payload": {}},  # Out of order!
        ]
        
        chain, failure = load_verified_session("test", events, None)
        
        assert chain is None
        assert failure is not None
        assert failure.verification_status == VerificationStatus.INVALID
        assert "NON_MONOTONIC" in failure.error_code


class TestAntiInference:
    """Tests proving no synthetic events are created."""
    
    def test_no_synthetic_events_in_gap(self):
        """ADVERSARIAL: Gaps must NOT be filled with inferred events."""
        events = [
            {"sequence_number": 0, "event_type": "START", "event_hash": "a", "payload": {}},
            {"sequence_number": 10, "event_type": "END", "event_hash": "b", "payload": {}},
        ]
        
        chain, _ = load_verified_session("test", events, None)
        replay = build_replay(chain)
        
        # Count EVENT frames
        event_frames = [f for f in replay.frames if f.frame_type == FrameType.EVENT]
        
        # Should be exactly 2 (the originals), NOT 11 (with inferred events)
        assert len(event_frames) == 2, f"Got {len(event_frames)} event frames, expected 2"
        
        # GAP frame should exist
        gap_frames = [f for f in replay.frames if f.frame_type == FrameType.GAP]
        assert len(gap_frames) == 1
        assert gap_frames[0].gap_start == 1
        assert gap_frames[0].gap_end == 9
    
    def test_no_reordering(self):
        """Events must appear in sequence order, not reordered for UX."""
        # Events with out-of-order timestamps but correct sequences
        events = [
            {"sequence_number": 0, "event_type": "START", "event_hash": "a", "payload": {}, "timestamp": "2026-01-29T12:00:00Z"},
            {"sequence_number": 1, "event_type": "CALL", "event_hash": "b", "payload": {}, "timestamp": "2026-01-29T11:00:00Z"},  # Earlier!
            {"sequence_number": 2, "event_type": "END", "event_hash": "c", "payload": {}, "timestamp": "2026-01-29T13:00:00Z"},
        ]
        
        chain, _ = load_verified_session("test", events, None)
        replay = build_replay(chain)
        
        # Frames should be in SEQUENCE order, not timestamp order
        sequences = [f.sequence_number for f in replay.frames if f.sequence_number is not None]
        assert sequences == [0, 1, 2], "Frames must be in sequence order"
        
        # Should have timestamp anomaly warning
        anomaly_warnings = [w for w in replay.warnings if w.code == WarningCode.TIMESTAMP_ANOMALY]
        assert len(anomaly_warnings) == 1


class TestFrameAtSequence:
    """Tests for get_frame_at_sequence."""
    
    def test_returns_gap_for_missing(self):
        """Missing sequence returns GAP frame."""
        events = [
            {"sequence_number": 0, "event_type": "START", "event_hash": "a", "payload": {}},
            {"sequence_number": 5, "event_type": "END", "event_hash": "b", "payload": {}},
        ]
        
        chain, _ = load_verified_session("test", events, None)
        replay = build_replay(chain)
        
        # Request missing sequence
        frame = get_frame_at_sequence(replay, 3)
        
        assert frame.frame_type == FrameType.GAP
        assert frame.gap_start == 3
        assert frame.gap_end == 3
    
    def test_returns_event_for_existing(self):
        """Existing sequence returns EVENT frame."""
        events = [
            {"sequence_number": 0, "event_type": "START", "event_hash": "a", "payload": {"x": 1}},
            {"sequence_number": 1, "event_type": "END", "event_hash": "b", "payload": {}},
        ]
        
        chain, _ = load_verified_session("test", events, None)
        replay = build_replay(chain)
        
        frame = get_frame_at_sequence(replay, 0)
        
        assert frame.frame_type == FrameType.EVENT
        assert frame.sequence_number == 0
        assert frame.event_type == "START"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
