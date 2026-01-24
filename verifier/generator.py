"""
test_generator.py - Generates valid and invalid test vectors for agentops-verify.
"""
import json
import hashlib
import uuid
import sys

try:
    import jcs
except ImportError:
    # Fallback for package-relative import
    from . import jcs

SPEC_VERSION = "v0.6"
SIGNED_FIELDS = [
    "event_id", 
    "session_id", 
    "sequence_number", 
    "timestamp_wall", 
    "event_type", 
    "payload_hash", 
    "prev_event_hash"
]

REQUIRED_SESSION_START = ["agent_id", "environment", "framework", "framework_version", "sdk_version"]

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def create_event(session_id: str, seq: int, prev_hash: str, event_type: str, payload: dict, tamper=None):
    event = {
        "event_id": str(uuid.uuid7()) if sys.version_info >= (3, 14) else str(uuid.uuid4()), # Python 3.14+ has uuid7
        "session_id": session_id,
        "sequence_number": seq,
        "timestamp_wall": "2023-10-27T10:00:00Z",
        "timestamp_monotonic": seq * 100,
        "event_type": event_type,
        "source_sdk_ver": "test-gen-0.1",
        "schema_ver": SPEC_VERSION,
        "prev_event_hash": prev_hash,
        "chain_authority": "server"
    }

    # Canonicalize Payload
    event["payload"] = payload # Store as object for JSON serialization later, but hash the bytes
    canonical_payload = jcs.canonicalize(payload)
    event["payload_hash"] = sha256(canonical_payload)

    # TAMPER PAYLOAD HASH if requested
    if tamper == "payload_hash":
        event["payload_hash"] = "badhash"

    # Calculate Event Hash
    signed_obj = {k: event[k] for k in SIGNED_FIELDS if k in event}
    canonical_envelope = jcs.canonicalize(signed_obj)
    event["event_hash"] = sha256(canonical_envelope)
    
    # TAMPER EVENT HASH
    if tamper == "event_hash":
        event["event_hash"] = "badhash"

    return event

def generate_valid_session():
    session_id = str(uuid.uuid4())
    events = []
    prev_hash = None
    
    # 1. Start
    e1 = create_event(session_id, 0, None, "SESSION_START", {
        "agent_id": "test-agent",
        "environment": "dev",
        "framework": "test-framework",
        "framework_version": "1.0.0",
        "sdk_version": "0.1.0",
        "tags": ["verification-test"]
    })
    events.append(e1)
    prev_hash = e1["event_hash"]

    # 2. Tool Call
    e2 = create_event(session_id, 1, prev_hash, "TOOL_CALL", {"tool_name": "search", "args": {"q": "agentops"}})
    events.append(e2)
    prev_hash = e2["event_hash"]

    # 3. Session End
    e3 = create_event(session_id, 2, prev_hash, "SESSION_END", {
        "status": "success",
        "duration_ms": 200
    })
    events.append(e3)
    prev_hash = e3["event_hash"]

    # 4. Seal with required server authority metadata (Spec v0.6)
    e4 = create_event(session_id, 3, prev_hash, "CHAIN_SEAL", {
        "final_event_hash": prev_hash,
        "ingestion_service_id": "ingestion-svc-prod-001",
        "seal_timestamp": "2023-10-27T10:00:02Z",
        "session_digest": prev_hash[:16]  # Short digest for session summary
    })
    events.append(e4)

    return events

def generate_tampered_payload_session():
    events = generate_valid_session()
    # Tamper payload of event 1 but keep hash -> Verifier should catch payload_hash mismatch
    # Wait, create_event calculates hash from payload. 
    # To tamper, we modify the payload AFTER creation.
    events[1]["payload"]["args"]["q"] = "evil_query" 
    # Now payload_hash (calculated from "agentops") matches the old payload, but payload is "evil_query"
    return events

def generate_tampered_chain_session():
    events = generate_valid_session()
    # Break chain: E2 prev_hash != E1 hash
    events[1]["prev_event_hash"] = "broken_link"
    # Note: This invalidates E2's event_hash too if we don't re-sign.
    # But usually verifier checks previous_hash == prev_event.event_hash FIRST.
    return events

def generate_sequence_gap_session():
    events = generate_valid_session()
    # E2 sequence = 5
    events[1]["sequence_number"] = 5
    # Recalculate hash so it looks "valid" locally
    signed_obj = {k: events[1][k] for k in SIGNED_FIELDS if k in events[1]}
    events[1]["event_hash"] = sha256(jcs.canonicalize(signed_obj))
    return events

def write_jsonl(events, filename):
    with open(filename, 'w') as f:
        for e in events:
            f.write(json.dumps(e) + '\n')

if __name__ == "__main__":
    write_jsonl(generate_valid_session(), "verifier/test_vectors/valid_session.jsonl")
    write_jsonl(generate_tampered_payload_session(), "verifier/test_vectors/invalid_hash.jsonl")
    write_jsonl(generate_tampered_chain_session(), "verifier/test_vectors/invalid_chain.jsonl")
    write_jsonl(generate_sequence_gap_session(), "verifier/test_vectors/invalid_sequence.jsonl")
    print("Generated test vectors.")
