import json
import hashlib
import time
from datetime import datetime
import pytest
import os
import sys
import platform

# Assume jcs is available (test script path setup might be needed if run directly)
# Adding basic path setup for standalone run
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from agentops_sdk.events import EventType
try:
    from app.replay.engine import load_verified_session, build_replay, VerifiedChain
    from app.replay.frames import FrameType
except ImportError:
    load_verified_session = None
    build_replay = None
    VerifiedChain = None
    FrameType = None
    pytestmark = pytest.mark.skip(reason="app.replay.engine module not found")

# Add verifier path for jcs
verifier_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../verifier"))
sys.path.append(verifier_path)

try:
    import jcs
except ImportError:
    # Skip tests requiring JCS if not available
    jcs = None

pytestmark = pytest.mark.skipif(jcs is None, reason="jcs module not found")



def create_mock_events():
    """
    Return a deterministic list of five mock replay event dictionaries for testing.
    
    Each event's `payload` is a JCS-canonicalized UTF-8 string representing the JSON payload. The sequence includes:
    SESSION_START, TOOL_CALL (with a floating-point argument), TOOL_RESULT (nested object with specific key order), LOG_DROP, and SESSION_END, each with fixed timestamps and sequence numbers.
    
    Returns:
        list: Five event dictionaries suitable for ingestion and replay testing.
    """
    # Payloads must be strings in DB/Engine
    
    events = [
        # 0: Session Start
        {
            "event_id": "evt-0",
            "sequence_number": 0,
            "event_type": "SESSION_START",
            "timestamp_wall": "2024-01-01T12:00:00.000Z",
            "payload": jcs.canonicalize({"agent_id": "test-agent"}).decode('utf-8'),
            "event_hash": "hash_0",
            "chain_authority": "server"
        },
        # 1. Tool Call (Floating point arg)
        {
            "event_id": "evt-1",
            "sequence_number": 1,
            "event_type": "TOOL_CALL",
            "timestamp_wall": "2024-01-01T12:00:01.000Z",
            "payload": jcs.canonicalize({"tool": "calc", "args": {"val": 10.5}}).decode('utf-8'),
            "event_hash": "hash_1",
            "chain_authority": "server"
        },
        # 2. Tool Result (Complex Nested JSON key order)
        {
            "event_id": "evt-2",
            "sequence_number": 2,
            "event_type": "TOOL_RESULT",
            "timestamp_wall": "2024-01-01T12:00:02.000Z",
            "payload": jcs.canonicalize({
                "z": 1,
                "a": 2,
                "nested": {"y": "foo", "x": "bar"}
            }).decode('utf-8'),
            "event_hash": "hash_2",
            "chain_authority": "server" 
        },
        # 3. Log Drop (Gap)
        {
            "event_id": "evt-3",
            "sequence_number": 3,
            "event_type": "LOG_DROP",
            "timestamp_wall": "2024-01-01T12:00:03.000Z",
            "payload": jcs.canonicalize({"dropped_count": 5, "reason": "BUFFER_FULL"}).decode('utf-8'),
            "event_hash": "hash_3",
            "chain_authority": "server"
        },
        # 4. End
        {
            "event_id": "evt-4",
            "sequence_number": 4,
            "event_type": "SESSION_END",
            "timestamp_wall": "2024-01-01T12:00:04.000Z",
            "payload": jcs.canonicalize({"status": "success"}).decode('utf-8'),
            "event_hash": "hash_4",
            "chain_authority": "server"
        }
    ]
    return events

def diff_dicts(d1, d2, path=""):
    """Recursively finds differences between two dictionaries"""
    if isinstance(d1, dict) and isinstance(d2, dict):
        for k in d1.keys():
            if k not in d2:
                print(f"Key {path}.{k} missing in d2")
                return False
            if not diff_dicts(d1[k], d2[k], path=f"{path}.{k}"):
                return False
        for k in d2.keys():
            if k not in d1:
                print(f"Key {path}.{k} missing in d1")
                return False
        return True
    elif isinstance(d1, list) and isinstance(d2, list):
        if len(d1) != len(d2):
            print(f"List length mismatch at {path}: {len(d1)} vs {len(d2)}")
            return False
        for i, (i1, i2) in enumerate(zip(d1, d2)):
            if not diff_dicts(i1, i2, path=f"{path}[{i}]"):
                return False
        return True
    else:
        if d1 != d2:
            print(f"Value mismatch at {path}: {d1} vs {d2}")
            return False
        return True





def test_replay_determinism():
    """
    Test that building a replay from the same verified session data yields bit-for-bit identical outputs and preserves canonicalized payload strings.
    
    Loads a verified session twice with identical mock events and a fixed seal, builds replays for each load, and asserts the serialized replay outputs are identical. Additionally, verifies that the frame corresponding to the tool call event:
    - exposes its payload as a string,
    - parses to the expected tool name and floating-point argument value (10.5),
    - matches the canonical JCS string produced for the same payload content.
    
    The test will skip if the replay engine dependency is unavailable.
    """
    print("\n>>> START REPLAY DETERMINISM TEST <<<")
    if load_verified_session is None:
        pytest.skip("app.replay.engine module not found")
    
    events_data = create_mock_events()
    
    # Run 1
    # Mock Chain Seal
    seal = {
        "session_digest": "digest_123",
        "seal_timestamp": "2024-01-01T12:00:05.000Z"
    }
    
    chain1, fail1 = load_verified_session("session-1", events_data, seal)
    assert fail1 is None
    assert chain1 is not None
    
    result1 = build_replay(chain1)
    
    # Serialize to JSON to check bit-for-bit determinism
    # We use default=str to handle enums/objects
    json1 = json.dumps(result1, default=lambda o: o.__dict__ if hasattr(o, "__dict__") else str(o), sort_keys=True)
    
    # Run 2
    chain2, fail2 = load_verified_session("session-1", events_data, seal)
    assert fail2 is None
    result2 = build_replay(chain2)
    json2 = json.dumps(result2, default=lambda o: o.__dict__ if hasattr(o, "__dict__") else str(o), sort_keys=True)
    
    # Compare
    if json1 != json2:
        print("Determinism FAILED!")
        print("Run 1:", json1)
        print("Run 2:", json2)
        assert False, "Replay outputs are not identical"
        
    print("Determinism PASSED.")
    
    # Verify Specific deterministic properties
    # 1. Floating point in Frames
    # Find frame for event 1
    frame1 = next(f for f in result1.frames if f.sequence_number == 1)
    
    # Payload in the frame should be the raw string from the DB (canonical JSON)
    # The Ingestion Service stores payloads as TEXT columns containing JCS strings.
    # The Replay Engine passes these through.
    assert isinstance(frame1.payload, str)
    
    # Parse to verify content
    payload_obj = json.loads(frame1.payload)
    assert payload_obj["tool"] == "calc"
    assert payload_obj["args"]["val"] == 10.5
    
    # Verify bitwise identity of the string payload (JCS guarantee)
    expected_payload = jcs.canonicalize({"tool": "calc", "args": {"val": 10.5}}).decode('utf-8')
    assert frame1.payload == expected_payload


if __name__ == "__main__":
    # Test runner
    try:
        test_replay_determinism()
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
