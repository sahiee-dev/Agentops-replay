import os
import sys
import json
import uuid
import subprocess
from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest
import hashlib

# Add backend to path (and root)
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, "backend"))

from app.compliance.json_export import generate_json_export
from app.compliance.pdf_export import generate_pdf_from_verified_dict
from app.models import Session, EventChain, ChainSeal, SessionStatus, ChainAuthority
from agentops_sdk.events import EventType

# Need to import jcs for test data generation
# Add verifier to path
_verifier_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../verifier"))
if _verifier_path not in sys.path:
    sys.path.append(_verifier_path)
import jcs

class MockDB:
    def __init__(self, session, events, seal):
        self.session_obj = session
        self.events = events
        self.seal = seal

    def query(self, model):
        self.current_model = model
        return self

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args):
        return self

    def all(self):
        if self.current_model == EventChain:
            return self.events
        return []

    def first(self):
        if self.current_model == Session:
            return self.session_obj
        if self.current_model == ChainSeal:
            return self.seal
        return None

def test_compliance_artifacts():
    # 1. Setup Data
    session_id = str(uuid.uuid4())
    session_uuid = uuid.UUID(session_id)
    
    # Session
    session = Session(
        id=1,
        session_id_str=session_id,
        agent_name="Test Agent",
        status=SessionStatus.SEALED,
        started_at=datetime.now(timezone.utc),
        sealed_at=datetime.now(timezone.utc),
        chain_authority=ChainAuthority.SERVER,
        total_drops=0,
        ingestion_service_id="ingest-1"
    )

    # Use check helper
    def hash_event(evt_dict):
        # Calculate event hash
        # Signed fields only
        signed_fields = ["event_id", "session_id", "sequence_number", "timestamp_wall", "event_type", "payload_hash", "prev_event_hash"]
        signed_obj = {k: evt_dict[k] for k in signed_fields}
        canonical = jcs.canonicalize(signed_obj)
        return hashlib.sha256(canonical).hexdigest()

    # Rebuild Events with Valid Hashes
    # Genesis
    evt0_payload = {"agent_id": "agent-007", "environment": "prod", "framework": "langchain", "framework_version": "0.1", "sdk_version": "0.1"} # Session Start required fields
    evt0_payload_bytes = jcs.canonicalize(evt0_payload)
    evt0_phash = hashlib.sha256(evt0_payload_bytes).hexdigest()
    
    evt0_dict = {
        "event_id": str(uuid.uuid4()),
        "session_id": session_id,
        "sequence_number": 0,
        "timestamp_wall": "2024-01-01T12:00:00.000Z",
        "event_type": "SESSION_START",
        "payload_hash": evt0_phash,
        "prev_event_hash": None
    }
    evt0_hash = hash_event(evt0_dict)
    
    e0 = EventChain(
        event_id=uuid.UUID(evt0_dict["event_id"]),
        session_id=1,
        session_id_str=session_id,
        sequence_number=0,
        event_type="SESSION_START",
        timestamp_wall=datetime.fromisoformat("2024-01-01T12:00:00+00:00"),
        timestamp_monotonic=1000,
        source_sdk_ver="0.1",
        schema_ver="v0.6",
        payload_canonical=evt0_payload_bytes.decode('utf-8'), # DB stores as Text
        payload_hash=evt0_phash,
        prev_event_hash=None,
        event_hash=evt0_hash,
        chain_authority="server"
    )
    
    # End
    evt1_payload = {"status": "success", "duration_ms": 100}
    evt1_payload_bytes = jcs.canonicalize(evt1_payload)
    evt1_phash = hashlib.sha256(evt1_payload_bytes).hexdigest()
    
    evt1_dict = {
        "event_id": str(uuid.uuid4()),
        "session_id": session_id,
        "sequence_number": 1,
        "timestamp_wall": "2024-01-01T12:00:01.000Z",
        "event_type": "SESSION_END",
        "payload_hash": evt1_phash,
        "prev_event_hash": evt0_hash
    }
    evt1_hash = hash_event(evt1_dict)
    
    e1 = EventChain(
        event_id=uuid.UUID(evt1_dict["event_id"]),
        session_id=1,
        session_id_str=session_id,
        sequence_number=1,
        event_type="SESSION_END",
        timestamp_wall=datetime.fromisoformat("2024-01-01T12:00:01+00:00"),
        timestamp_monotonic=2000,
        source_sdk_ver="0.1",
        schema_ver="v0.6",
        payload_canonical=evt1_payload_bytes.decode('utf-8'),
        payload_hash=evt1_phash,
        prev_event_hash=evt0_hash,
        event_hash=evt1_hash,
        chain_authority="server"
    )

    # Chain Seal Event
    evt2_payload = {
        "ingestion_service_id": "ingest-1",
        "seal_timestamp": "2024-01-01T12:00:02.000Z",
        "session_digest": "digest_123"
    }
    evt2_payload_bytes = jcs.canonicalize(evt2_payload)
    evt2_phash = hashlib.sha256(evt2_payload_bytes).hexdigest()
    
    evt2_dict = {
        "event_id": str(uuid.uuid4()),
        "session_id": session_id,
        "sequence_number": 2,
        "timestamp_wall": "2024-01-01T12:00:02.000Z",
        "event_type": "CHAIN_SEAL",
        "payload_hash": evt2_phash,
        "prev_event_hash": evt1_hash,
        "chain_authority": "server" # Explicitly server for seal
    }
    evt2_hash = hash_event(evt2_dict)
    
    e2 = EventChain(
        event_id=uuid.UUID(evt2_dict["event_id"]),
        session_id=1,
        session_id_str=session_id,
        sequence_number=2,
        event_type="CHAIN_SEAL",
        timestamp_wall=datetime.fromisoformat("2024-01-01T12:00:02+00:00"),
        timestamp_monotonic=3000,
        source_sdk_ver="0.1",
        schema_ver="v0.6",
        payload_canonical=evt2_payload_bytes.decode('utf-8'),
        payload_hash=evt2_phash,
        prev_event_hash=evt1_hash,
        event_hash=evt2_hash,
        chain_authority="server"
    )
    
    events = [e0, e1, e2]
    
    # Seal with valid hash (pointing to e2 as final event? No, e2 IS the seal)
    # The ChainSeal table stores the hash of the Seal Event usually, or the hash of the last event BEFORE seal?
    # PRD says CHAIN_SEAL event is the last event.
    # The ChainSeal TABLE is likely metadata about that event.
    seal = ChainSeal(
        session_id=1,
        ingestion_service_id="ingest-1",
        seal_timestamp=datetime.now(timezone.utc),
        session_digest="digest_123",
        final_event_hash=evt2_hash,
        event_count=3
    )

    # Mock DB
    db = MockDB(session, events, seal)

    # 2. Generate JSON Export
    json_export = generate_json_export(session_id, db)
    
    # Save to file
    outfile = "test_compliance_export.json"
    with open(outfile, "wb") as f:
        f.write(jcs.canonicalize(json_export))
        
    print(f"JSON Export saved to {outfile}")

    # 3. Verify with Verifier
    verifier_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../verifier/agentops_verify.py"))
    
    result = subprocess.run(
        [sys.executable, verifier_path, outfile, "--format", "json"],
        capture_output=True,
        text=True,
        timeout=30
    )
    
    print("Verifier Output:", result.stdout)
    print("Verifier Error:", result.stderr)
    
    assert result.returncode == 0
    # Parse JSON output for robust assertion
    verifier_data = json.loads(result.stdout)
    assert verifier_data["status"] == "PASS"
    assert verifier_data["evidence_class"] == "AUTHORITATIVE_EVIDENCE"
    
    # 4. Generate PDF
    pdf_bytes = generate_pdf_from_verified_dict(json_export)
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF")
    
    with open("test_compliance.pdf", "wb") as f:
        f.write(pdf_bytes)
    print("PDF Export saved to test_compliance.pdf")

if __name__ == "__main__":
    test_compliance_artifacts()
