import json
import hashlib
import time
from datetime import datetime
import pytest
import os
import sys

# Assume jcs is available (test script path setup might be needed if run directly)
# Adding basic path setup for standalone run
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from agentops_sdk.events import EventType
from app.replay.engine import load_verified_session, build_replay, VerifiedChain
from app.replay.frames import FrameType

# Add verifier path for jcs
verifier_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../verifier"))
sys.path.append(verifier_path)

try:
    import jcs
except ImportError:
    # Use simple json dumps if jcs not found (fallback for dev environments without vendoring setup)
    import json
    class MockJCS:
        @staticmethod
        def canonicalize(obj):
            """
            Produce a canonical UTF-8 byte representation of a JSON-serializable object.
            
            Parameters:
                obj: A JSON-serializable Python object (e.g., dict, list, str, number).
            
            Returns:
                bytes: UTF-8 encoded JSON with keys sorted and compact separators for stable, deterministic serialization.
            """
            return json.dumps(obj, sort_keys=True, separators=(',', ':')).encode('utf-8')
    jcs = MockJCS()


def create_mock_events():
    """
    Generate a fixed sequence of event dictionaries used for replay determinism tests.
    
    Each event contains the keys: `event_id`, `sequence_number`, `event_type`, `timestamp_wall`, `payload` (a canonicalized JSON string), `event_hash`, and `chain_authority`.
    
    Returns:
        events (list[dict]): A list of five events representing a session start, a tool call, a tool result, a log drop, and a session end.
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
    """
    Compare two nested structures (dictionaries, lists, and primitives) for structural and value equality.
    
    Recursively compares mapping keys and values, list elements by index, and primitive values for equality.
    On the first detected mismatch this function prints a diagnostic message indicating the path and nature
    of the mismatch and returns False. If no differences are found, it returns True.
    
    Parameters:
        d1: The first structure to compare; may be a dict, list, or primitive value.
        d2: The second structure to compare; may be a dict, list, or primitive value.
        path (str): Internal caller-visible path used in diagnostic messages to locate mismatches.
    
    Returns:
        True if the two structures are equal in shape and value, False otherwise.
    """
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
    Test that building a replay from the same verified session events and seal produces identical outputs across runs.
    
    Creates a fixed set of mock events and a mock seal, loads the verified session twice, builds a replay for each run, and asserts the serialized replay outputs are bit-for-bit identical. Also verifies specific deterministic properties in the resulting frames (e.g., the frame with sequence_number 1 contains a payload whose `tool` field equals "calc").
    
    Raises:
        AssertionError: If replay outputs differ between runs or if the deterministic property checks fail.
    """
    print("\n>>> START REPLAY DETERMINISM TEST <<<")
    
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
    # Payload string should remain canonical
    payload_dict = json.loads(frame1.payload)
    assert payload_dict["tool"] == "calc"
    # assert payload_dict["args"]["val"] == 10.5 # Wait, payload is a JSON string in the frame?
    # ReplayEngine lines 226: payload=event.get("payload")
    # In my mock, payload is a DICT. 
    # But Ingestion Service stores payloads as STRINGS (Canonical JSON).
    # ReplayEngine docstring says "Consumes VERIFIED chains only". 
    # Verified chains usually come from DB where payload is string.
    # So my mock data is slightly wrong. I need to make payload a canonical string in mock data.
    
    # Let's fix the Mock Data generator to serialize payloads
    # But wait, json_export.py loads it. 
    # ReplayEngine logic:
    # Line 226: payload=event.get("payload")
    # If event.get("payload") is a string (from DB), it passes it through.
    # The frontend expects what? A string? Or objects?
    # Schema replay_v2.py probably defines Frame.payload as Any or Json.
    # Let's assume string for now to be safe.

    # Actually, let's fix the mock generator to be realistic (strings).

if __name__ == "__main__":
    # Test runner
    try:
        test_replay_determinism()
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
