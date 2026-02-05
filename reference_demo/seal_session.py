import json
import hashlib
import sys
import os

# Add repo root to path to import agentops_sdk (if needed for JCS)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from agentops_sdk import jcs

def seal_session(input_path, output_path):
    """
    Seal a session of events by validating each event's payload hash, computing chained event hashes, and writing the sealed events to output_path.
    
    Parameters:
        input_path (str): Filesystem path to a JSON file containing an array of unsealed events.
        output_path (str): Filesystem path where the sealed session (JSON array) will be written.
    
    Raises:
        ValueError: If a recomputed payload hash does not match an event's declared `payload_hash`.
    """
    print(f"Reading unsealed events from {input_path}...")
    with open(input_path, 'r') as f:
        events = json.load(f)
    
    sealed_events = []
    prev_event_hash = None
    
    print("Applying Authoritative Chain Seal...")
    
    for i, event in enumerate(events):
        # 1. Validate payload hash (Simulation of Ingestion Check)
        # Note: In a real system, we'd recompute and check payload_hash
        # Here we trust the SDK's deterministic output for the demo, 
        # but let's recompute it to be sure.
        canonical_payload = jcs.canonicalize(event['payload'])
        expected_payload_hash = hashlib.sha256(canonical_payload).hexdigest()
        
        if expected_payload_hash != event['payload_hash']:
            raise ValueError(f"Payload hash mismatch at seq {i}! SDK may be buggy.")
            
        # 2. Populate Ingestion Fields
        event['prev_event_hash'] = prev_event_hash
        event['chain_authority'] = "agentops-ingest-v1"
        
        # 3. Compute Event Hash (The Seal)
        # Fields to sign: event_id, session_id, sequence_number, timestamp_wall, event_type, payload_hash, prev_event_hash
        # (This matches the SDK's signature spec but done by Server)
        signed_obj = {
            "event_id": event['event_id'],
            "session_id": event['session_id'],
            "sequence_number": event['sequence_number'],
            "timestamp_wall": event['timestamp_wall'],
            "event_type": event['event_type'],
            "payload_hash": event['payload_hash'],
            "prev_event_hash": event['prev_event_hash']
        }
        
        canonical_env = jcs.canonicalize(signed_obj)
        event_hash = hashlib.sha256(canonical_env).hexdigest()
        event['event_hash'] = event_hash
        
        # Update Chain
        prev_event_hash = event_hash
        sealed_events.append(event)
        
    print(f"Sealed {len(sealed_events)} events.")
    print(f"Final Hash: {prev_event_hash}")
    
    with open(output_path, 'w') as f:
        json.dump(sealed_events, f, indent=2)
    print(f"Written sealed session to {output_path}")

if __name__ == "__main__":
    seal_session(
        "reference_demo/expected_output/agent_output.json",
        "reference_demo/expected_output/session_golden.json"
    )