# AgentOps Replay — Technical Requirements Document (TRD v2.0)

> **Status:** Active  
> **Replaces:** TRD v1.0  
> **Audience:** AI coding agents, developers  
> **Rule:** Read AGENT_CONTEXT.md before this. Never build something already built.  
> **Last Updated:** May 2026

---

## 1. Repository Structure (Canonical Target)

This is the authoritative directory layout. Do not create files or directories outside this structure without updating this document.

```
agentops-replay/
│
├── agentops_sdk/                    # Component 1: SDK
│   ├── __init__.py                  # Public API exports
│   ├── client.py                    # AgentOpsClient — main entry point
│   ├── events.py                    # EventType enum + event type constants
│   ├── envelope.py                  # Event envelope construction + hash computation
│   ├── buffer.py                    # Thread-safe ring buffer + LOG_DROP logic
│   └── sender.py                    # HTTP batch sender to Ingestion Service
│
├── verifier/                        # Component 2: Verifier (zero dependencies)
│   ├── agentops_verify.py           # CLI entrypoint
│   ├── jcs.py                       # RFC 8785 JCS canonicalization (THE ONLY COPY)
│   └── test_vectors/
│       ├── generator.py             # Generates all test vectors programmatically
│       ├── valid_session.jsonl      # Expected: PASS, NON_AUTHORITATIVE_EVIDENCE
│       ├── tampered_hash.jsonl      # Expected: FAIL, hash mismatch at seq=N
│       └── sequence_gap.jsonl      # Expected: FAIL, sequence gap at seq=N
│
├── backend/                         # Component 3: Ingestion Service
│   ├── app/
│   │   ├── main.py                  # FastAPI app factory + lifespan management
│   │   ├── config.py                # Settings via pydantic-settings + env vars
│   │   ├── dependencies.py          # FastAPI dependency injection
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── router.py        # Route registration
│   │   │       └── endpoints/
│   │   │           ├── ingestion.py # POST /v1/ingest
│   │   │           ├── sessions.py  # GET /v1/sessions/{id}/export
│   │   │           └── health.py    # GET /health
│   │   ├── services/
│   │   │   └── ingestion/
│   │   │       ├── service.py       # Ingestion orchestrator
│   │   │       ├── chain.py         # Server-side hash chain recomputation
│   │   │       ├── sealer.py        # CHAIN_SEAL construction + emission
│   │   │       └── validator.py     # Event structure validation
│   │   ├── models/
│   │   │   ├── session.py           # SQLAlchemy ORM: sessions table
│   │   │   └── event.py             # SQLAlchemy ORM: events table
│   │   └── db/
│   │       ├── base.py              # SQLAlchemy declarative base
│   │       └── session.py           # Async session factory
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       ├── 001_initial_schema.py
│   │       └── 002_append_only_permissions.py
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── requirements.txt
│
├── sdk/python/agentops_replay/      # Component 4: Integrations
│   ├── __init__.py
│   └── integrations/
│       └── langchain/
│           ├── __init__.py
│           └── handler.py           # AgentOpsCallbackHandler
│
├── examples/
│   ├── sdk_demo.py                  # Minimal working example (no frameworks)
│   └── langchain_demo/
│       ├── agent.py                 # Customer support agent with tools
│       └── README.md
│
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   ├── test_buffer.py           # Buffer overflow → LOG_DROP
│   │   ├── test_envelope.py         # Hash computation correctness
│   │   ├── test_events.py           # EventType enum
│   │   └── test_verifier.py         # Verifier logic (all checks)
│   ├── integration/
│   │   └── test_ingestion_api.py    # POST /v1/ingest + GET export
│   └── e2e/
│       └── test_full_flow.py        # SDK → Ingest → Export → Verify (both modes)
│
├── docs/
│   ├── EVENT_LOG_SPEC.md            # The formal ELS specification
│   ├── CHAIN_AUTHORITY_INVARIANTS.md
│   └── FAILURE_MODES.md
│
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── CONSTITUTION.md                  # Frozen. Never edit.
├── PRD_v5.md
├── TRD_v2.md                        # This document
├── AGENT_CONTEXT.md
├── BUILD_SEQUENCE.md
├── AGENT_PROMPT.md
├── pyproject.toml
├── README.md
└── LICENSE
```

---

## 2. Component 1: SDK — Full Technical Specification

### 2.1 Public API (`agentops_sdk/client.py`)

```python
from agentops_sdk.events import EventType

class AgentOpsClient:
    """
    Main entry point for the AgentOps Replay SDK.
    
    Two modes:
    - local_authority=True (default): Flush to JSONL file. No server required.
      Evidence class: NON_AUTHORITATIVE_EVIDENCE.
    - local_authority=False: POST to Ingestion Service.
      Evidence class: AUTHORITATIVE_EVIDENCE (if no LOG_DROP).
    
    CRITICAL: Never raises exceptions that propagate to caller.
    All errors are handled internally and recorded as LOG_DROP.
    """

    def __init__(
        self,
        local_authority: bool = True,
        server_url: str | None = None,
        buffer_size: int = 1000,
        agent_id: str | None = None,
    ) -> None:
        """
        Parameters
        ----------
        local_authority : bool
            True = flush to JSONL. False = POST to server_url.
        server_url : str | None
            Required when local_authority=False.
            Example: "http://localhost:8000"
        buffer_size : int
            Maximum events in ring buffer before LOG_DROP triggers.
            Default 1000. Minimum 10.
        agent_id : str | None
            Identifier for the agent. Auto-generated UUID v4 if None.
        """

    def start_session(
        self,
        agent_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """
        Start a new recording session.
        
        Emits SESSION_START as seq=1.
        Returns the session_id (UUID v4) for reference.
        
        If called when a session is already active:
        - Ends the previous session with status='error'
        - Starts a new session
        - Does NOT raise an exception
        
        Parameters
        ----------
        agent_id : str | None
            Overrides the client-level agent_id for this session.
        metadata : dict | None
            Additional fields merged into SESSION_START payload.
            Allowed fields are defined in PRD §4.3.
        """

    def record(
        self,
        event_type: EventType,
        payload: dict,
    ) -> None:
        """
        Record an event in the current session.
        
        NEVER raises. On any internal error:
        - Emits LOG_DROP instead
        - Continues normally
        
        Parameters
        ----------
        event_type : EventType
            Must be one of the SDK-authority event types.
            Attempting to record server-authority types (CHAIN_SEAL, etc.)
            is silently ignored and counted as a LOG_DROP.
        payload : dict
            Event-specific data. See PRD §4.3 for schemas.
            Unknown fields are allowed (forward compatibility).
            Missing required fields emit a LOG_DROP.
        
        Raises
        ------
        Never. All errors handled internally.
        """

    def end_session(
        self,
        status: str = "success",
        duration_ms: int | None = None,
        exit_reason: str | None = None,
    ) -> None:
        """
        End the current session.
        
        Emits SESSION_END as the last SDK event.
        After this, record() calls emit LOG_DROP until start_session() is called.
        
        Parameters
        ----------
        status : str
            "success" | "failure" | "error" | "timeout"
        """

    def flush_to_jsonl(self, path: str) -> None:
        """
        Write all buffered events to a JSONL file.
        
        Each line is one JSON event.
        Events are ordered by seq ascending.
        Overwrites existing file if it exists.
        
        Must be called AFTER end_session().
        Calling before end_session() writes a partial session
        (NON_AUTHORITATIVE_EVIDENCE regardless).
        
        Raises
        ------
        IOError: If the file cannot be written.
        (This is the ONE exception that may propagate — file write is
        outside the agent's execution path.)
        """

    def send_to_server(self) -> dict:
        """
        POST all buffered events to the Ingestion Service.
        
        Sends in a single batch. Retries 3 times on connection failure.
        After 3 failures, raises ConnectionError.
        
        Must be called AFTER end_session().
        
        Returns
        -------
        dict: {"status": "accepted", "session_id": str, "events_accepted": int,
               "chain_seal": dict | None}
        
        Raises
        ------
        ConnectionError: After 3 failed retries.
        ValueError: If local_authority=True (can't send to server in local mode).
        """
```

### 2.2 EventType Enum (`agentops_sdk/events.py`)

```python
from enum import Enum

class EventType(str, Enum):
    # SDK-authority events
    SESSION_START = "SESSION_START"
    SESSION_END = "SESSION_END"
    LLM_CALL = "LLM_CALL"
    LLM_RESPONSE = "LLM_RESPONSE"
    TOOL_CALL = "TOOL_CALL"
    TOOL_RESULT = "TOOL_RESULT"
    TOOL_ERROR = "TOOL_ERROR"
    LOG_DROP = "LOG_DROP"
    
    # Server-authority events (SDK must never produce these)
    CHAIN_SEAL = "CHAIN_SEAL"
    CHAIN_BROKEN = "CHAIN_BROKEN"
    REDACTION = "REDACTION"
    FORENSIC_FREEZE = "FORENSIC_FREEZE"
    
    @property
    def is_sdk_authority(self) -> bool:
        return self in {
            EventType.SESSION_START, EventType.SESSION_END,
            EventType.LLM_CALL, EventType.LLM_RESPONSE,
            EventType.TOOL_CALL, EventType.TOOL_RESULT,
            EventType.TOOL_ERROR, EventType.LOG_DROP,
        }
    
    @property
    def is_server_authority(self) -> bool:
        return not self.is_sdk_authority
```

### 2.3 Event Envelope (`agentops_sdk/envelope.py`)

```python
import hashlib
import datetime
import uuid
from typing import Any

# CRITICAL: Import JCS from verifier. Never duplicate this logic.
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'verifier'))
from jcs import canonicalize as jcs_canonicalize


def build_event(
    seq: int,
    event_type: str,
    session_id: str,
    payload: dict,
    prev_hash: str,
) -> dict:
    """
    Build a complete event envelope with computed hashes.
    
    This function is the single source of truth for event construction.
    The SDK must not construct events by any other means.
    
    Hash computation:
    1. Build the event dict WITHOUT the event_hash field
    2. JCS canonicalize it (RFC 8785)
    3. SHA-256 the UTF-8 bytes
    4. Set event_hash to the hex digest
    """
    timestamp = _utc_timestamp()
    
    event = {
        "seq": seq,
        "event_type": event_type,
        "session_id": session_id,
        "timestamp": timestamp,
        "payload": payload,
        "prev_hash": prev_hash,
    }
    
    # Compute hash AFTER all other fields are set
    event["event_hash"] = _compute_event_hash(event)
    return event


def _compute_event_hash(event: dict) -> str:
    """
    Compute the SHA-256 hash of the event's JCS canonical form.
    The event_hash field is excluded from the hash input.
    """
    event_for_hash = {k: v for k, v in event.items() if k != "event_hash"}
    canonical_bytes = jcs_canonicalize(event_for_hash)
    return hashlib.sha256(canonical_bytes).hexdigest()


def _utc_timestamp() -> str:
    """
    Returns current UTC time as ISO 8601 string with microsecond precision.
    Format: "2026-05-05T10:30:00.123456Z"
    
    Uses datetime.datetime.utcnow() — Python 3.11+ required for determinism.
    """
    now = datetime.datetime.utcnow()
    return now.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


GENESIS_HASH = "0" * 64  # prev_hash for the first event (seq=1)
```

### 2.4 Ring Buffer (`agentops_sdk/buffer.py`)

```python
import threading
from collections import deque
from dataclasses import dataclass, field
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
    - Pending drop info is accumulated (start seq, end seq, count)
    - A LOG_DROP event is added to the buffer when space becomes available
    - No events are silently lost
    
    Implementation notes:
    - Uses threading.Lock for all operations
    - deque with maxlen is NOT used (would silently drop — forbidden)
    - Buffer uses a plain list with explicit capacity management
    """
    
    def __init__(self, capacity: int = 1000) -> None:
        if capacity < 10:
            raise ValueError("buffer_size must be at least 10")
        self._capacity = capacity
        self._events: list[dict] = []
        self._lock = threading.Lock()
        self._drop_record: Optional[DropRecord] = None
        self._next_seq: int = 1
    
    def push(self, event: dict) -> bool:
        """
        Add an event to the buffer.
        
        Returns True if event was added.
        Returns False if buffer is full (caller must handle LOG_DROP emission).
        Never raises.
        """
    
    def has_pending_drops(self) -> bool:
        """Returns True if events have been dropped since last flush."""
    
    def get_and_clear_drop_record(self) -> Optional[DropRecord]:
        """
        Returns the current drop record and clears it.
        Called by the SDK before building a LOG_DROP event.
        """
    
    def drain(self) -> list[dict]:
        """
        Returns all events in order, then clears the buffer.
        Thread-safe. Used by flush_to_jsonl and send_to_server.
        """
    
    def size(self) -> int:
        """Current number of events in the buffer."""
    
    @property
    def next_seq(self) -> int:
        """Next sequence number to assign."""
```

### 2.5 HTTP Sender (`agentops_sdk/sender.py`)

```python
import json
import urllib.request
import urllib.error
from typing import Any


class EventSender:
    """
    HTTP batch sender for the Ingestion Service.
    
    Uses only urllib (stdlib) — no requests, no httpx.
    This keeps the core SDK dependency-free for the verifier constraint,
    even though the sender itself is only used in server mode.
    
    Retry policy: 3 attempts with 1s, 2s, 4s exponential backoff.
    On final failure: raises ConnectionError.
    Never modifies the events list.
    """
    
    def __init__(
        self,
        server_url: str,
        timeout_seconds: int = 10,
        max_retries: int = 3,
    ) -> None:
        self._base_url = server_url.rstrip("/")
        self._timeout = timeout_seconds
        self._max_retries = max_retries
    
    def send_batch(
        self,
        session_id: str,
        events: list[dict],
    ) -> dict:
        """
        POST events to /v1/ingest.
        
        Request body:
        {
            "session_id": str,
            "events": [list of event dicts]
        }
        
        Returns the parsed response on success.
        
        Raises
        ------
        ConnectionError: After max_retries failed attempts.
        ValueError: If server returns 4xx (client error — do not retry).
        """
    
    def _post(self, path: str, body: dict) -> dict:
        """Internal: single POST attempt. Raises urllib.error.URLError on failure."""
```

---

## 3. Component 2: Verifier — Full Technical Specification

### 3.1 CLI Interface

```
Usage: agentops_verify.py [-h] [--format {text,json}] session_file

Positional arguments:
  session_file          Path to JSONL session file to verify

Optional arguments:
  --format {text,json}  Output format (default: text)
  -h, --help            Show this help message and exit

Exit codes:
  0    PASS — chain is valid
  1    FAIL — chain has integrity violations
  2    ERROR — file not found, permission error, or malformed JSONL
```

### 3.2 Text Output Specification

**On PASS:**
```
AgentOps Replay Verifier v1.0
==============================
File        : session.jsonl
Session ID  : 550e8400-e29b-41d4-a716-446655440000
Events      : 12
Evidence    : NON_AUTHORITATIVE_EVIDENCE

[1/4] Structural validity ........... PASS
[2/4] Sequence integrity ............. PASS
[3/4] Hash chain integrity ........... PASS
[4/4] Session completeness ........... PASS

Result: PASS ✅
```

**On FAIL:**
```
AgentOps Replay Verifier v1.0
==============================
File        : tampered_session.jsonl
Session ID  : 550e8400-e29b-41d4-a716-446655440000
Events      : 12
Evidence    : (cannot determine — chain invalid)

[1/4] Structural validity ........... PASS
[2/4] Sequence integrity ............. PASS
[3/4] Hash chain integrity ........... FAIL
      Event seq=5 (LLM_RESPONSE):
        expected event_hash : a3f1b2c3d4e5...
        found event_hash    : 9b2c4d5e6f7a...
[4/4] Session completeness .......... (skipped — earlier check failed)

Result: FAIL ❌
```

### 3.3 JSON Output Specification

```json
{
  "verifier_version": "1.0",
  "file": "session.jsonl",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_count": 12,
  "evidence_class": "NON_AUTHORITATIVE_EVIDENCE",
  "result": "PASS",
  "checks": {
    "structural_validity": {
      "status": "PASS",
      "events_checked": 12,
      "errors": []
    },
    "sequence_integrity": {
      "status": "PASS",
      "first_seq": 1,
      "last_seq": 12,
      "gaps": [],
      "duplicates": []
    },
    "hash_chain_integrity": {
      "status": "PASS",
      "errors": []
    },
    "session_completeness": {
      "status": "PASS",
      "has_session_start": true,
      "has_session_end": true,
      "has_chain_seal": false,
      "log_drop_count": 0,
      "chain_broken_count": 0
    }
  },
  "errors": [],
  "timestamp_verified": "2026-05-05T10:30:00.000000Z"
}
```

**On FAIL, the JSON result field is `"FAIL"` and errors are populated:**
```json
{
  "result": "FAIL",
  "evidence_class": null,
  "checks": {
    "hash_chain_integrity": {
      "status": "FAIL",
      "errors": [
        {
          "seq": 5,
          "event_type": "LLM_RESPONSE",
          "error": "hash_mismatch",
          "expected": "a3f1b2c3d4e5...",
          "found": "9b2c4d5e6f7a..."
        }
      ]
    }
  },
  "errors": ["Hash chain integrity check failed at seq=5"]
}
```

### 3.4 Validation Checks (All Four Must Pass for PASS)

**Check 1: Structural Validity**
For every line in the JSONL:
- Line is valid JSON (no parse errors)
- Contains required fields: `seq`, `event_type`, `session_id`, `timestamp`, `payload`, `prev_hash`, `event_hash`
- `seq` is a positive integer
- `event_type` is a string in the allowed EventType set
- `session_id` is a string (format UUID v4, but don't fail on format — only on absence)
- `timestamp` is a string matching `YYYY-MM-DDTHH:MM:SS.ffffffZ`
- `payload` is a JSON object (dict)
- `prev_hash` is a 64-character lowercase hex string
- `event_hash` is a 64-character lowercase hex string

**Check 2: Sequence Integrity**
- Sort events by `seq`
- First `seq` value must be 1
- Each subsequent `seq` must be exactly `previous_seq + 1`
  - Exception: A LOG_DROP event's seq is assigned normally
  - Exception: A CHAIN_SEAL event may be seq = last_seq + 1
- All events must share the same `session_id`
- No duplicate `seq` values
- Gaps detected and reported with: which seq was expected, which was found

**Check 3: Hash Chain Integrity**
For each event, in sequence order:
- Recompute `event_hash` from scratch using JCS + SHA-256 (exclude `event_hash` field)
- Compare recomputed hash to stored `event_hash`
- If they differ: FAIL with seq, expected, found
- Verify `prev_hash` of event N equals `event_hash` of event N-1
- Verify `prev_hash` of seq=1 equals `"0" * 64`

**Check 4: Session Completeness**
- Exactly one `SESSION_START` event must exist
- `SESSION_START` must have the lowest seq
- At least one `SESSION_END` or `CHAIN_SEAL` must exist
- `SESSION_END` (if present) must have the highest SDK-authority seq
- `CHAIN_SEAL` (if present) must be the absolute last event

### 3.5 Evidence Class Determination

After all four checks pass, determine evidence class:

```python
def determine_evidence_class(events: list[dict]) -> str:
    has_chain_seal = any(e["event_type"] == "CHAIN_SEAL" for e in events)
    has_log_drop = any(e["event_type"] == "LOG_DROP" for e in events)
    
    if has_chain_seal and not has_log_drop:
        return "AUTHORITATIVE_EVIDENCE"
    elif has_chain_seal and has_log_drop:
        return "PARTIAL_AUTHORITATIVE_EVIDENCE"
    else:
        return "NON_AUTHORITATIVE_EVIDENCE"
```

If any check fails, `evidence_class` is `null` in JSON output and `(cannot determine)` in text.

### 3.6 JCS Canonicalization (`verifier/jcs.py`)

**THE SINGLE SOURCE OF TRUTH FOR JCS IN THIS PROJECT.**

The `jcs.py` file implements RFC 8785 (JSON Canonicalization Scheme).
The SDK imports this file. The Verifier uses it directly.
No other file in the project may contain JCS logic.

Key implementation requirements:
- Output must be deterministic for the same input on any platform
- Sort object keys lexicographically
- No extra whitespace
- Numbers: use same representation as JSON specification
- Strings: escaped according to RFC 8785
- Returns `bytes` (UTF-8 encoded)

**Function signature:**
```python
def canonicalize(data: Any) -> bytes:
    """
    RFC 8785 JCS canonicalization.
    
    Parameters
    ----------
    data : Any
        Python object to canonicalize (dict, list, str, int, float, bool, None)
    
    Returns
    -------
    bytes
        UTF-8 encoded canonical JSON bytes
    
    Raises
    ------
    ValueError: If data contains non-serializable types
    """
```

### 3.7 Test Vector Generator (`verifier/generator.py`)

This script generates all three test vectors deterministically. Running it always produces the same files (given the same Python version and JCS implementation).

```python
# Usage:
# python3 verifier/generator.py
# → Creates verifier/test_vectors/valid_session.jsonl
# → Creates verifier/test_vectors/tampered_hash.jsonl
# → Creates verifier/test_vectors/sequence_gap.jsonl
# All files are overwritten.
```

**valid_session.jsonl:** A complete 8-event session:
- seq=1: SESSION_START (agent_id="test-agent", model_id="test-model")
- seq=2: LLM_CALL
- seq=3: LLM_RESPONSE
- seq=4: TOOL_CALL (tool_name="calculator")
- seq=5: TOOL_RESULT
- seq=6: LLM_CALL
- seq=7: LLM_RESPONSE
- seq=8: SESSION_END (status="success")

**tampered_hash.jsonl:** Same as valid_session.jsonl but with seq=5 (TOOL_RESULT) having a corrupted `event_hash` (last character changed).

**sequence_gap.jsonl:** Same as valid_session.jsonl but with seq=4 (TOOL_CALL) removed, creating a gap from seq=3 to seq=5.

---

## 4. Component 3: Ingestion Service — Full Technical Specification

### 4.1 Technology Stack

| Layer | Technology | Version |
|---|---|---|
| Framework | FastAPI | ≥ 0.110 |
| ASGI Server | Uvicorn | ≥ 0.27 |
| ORM | SQLAlchemy (async) | ≥ 2.0 |
| DB Driver | asyncpg | ≥ 0.29 |
| Migrations | Alembic | ≥ 1.13 |
| Settings | pydantic-settings | ≥ 2.0 |
| DB | PostgreSQL | ≥ 15 |
| Python | 3.11+ | Pinned |

### 4.2 Configuration (`backend/app/config.py`)

All configuration via environment variables. No hardcoded values.

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://agentops_app:password@localhost:5432/agentops"
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Logging
    log_level: str = "WARNING"
    
    # Security (v1.1+)
    api_key_required: bool = False  # Set True in enterprise deployment
    
    class Config:
        env_prefix = "AGENTOPS_"
        env_file = ".env"
```

### 4.3 API Endpoints — Complete Specification

#### GET /health

Health check endpoint.

**Response 200:**
```json
{"status": "ok", "version": "1.0.0"}
```

#### POST /v1/ingest

Accept a batch of events from the SDK.

**Request Headers:**
- `Content-Type: application/json`
- `X-API-Key: <key>` (when `api_key_required=True`)

**Request Body:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "events": [
    {
      "seq": 1,
      "event_type": "SESSION_START",
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "timestamp": "2026-05-05T10:30:00.000000Z",
      "payload": { "agent_id": "my-agent", "model_id": "claude-sonnet-4-6" },
      "prev_hash": "0000000000000000000000000000000000000000000000000000000000000000",
      "event_hash": "a3f1b2c3..."
    }
  ]
}
```

**Server Processing Steps (in order):**
1. Parse and validate request JSON structure
2. Verify `session_id` in body matches `session_id` in each event
3. For each event, validate all required fields are present
4. Sort events by `seq`
5. Retrieve current chain state for this session from DB (last seq + last event_hash)
6. For each event (in seq order):
   a. Check seq is expected_next_seq (gap → emit CHAIN_BROKEN)
   b. Recompute `event_hash` server-side using JCS + SHA-256
   c. Compare to SDK-provided `event_hash` (mismatch → return 400 with details)
   d. Verify `prev_hash` == previous event's hash (mismatch → return 400)
7. Begin DB transaction
8. Insert all events
9. If SESSION_END is present, construct and insert CHAIN_SEAL
10. Update session record (status, event_count, final_hash if sealed)
11. Commit transaction
12. Return response

**Response 200:**
```json
{
  "status": "accepted",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "events_accepted": 8,
  "chain_seal": {
    "seq": 9,
    "event_type": "CHAIN_SEAL",
    "session_id": "...",
    "timestamp": "2026-05-05T10:30:05.000000Z",
    "payload": {
      "final_hash": "a3f1...",
      "event_count": 9,
      "server_timestamp": "...",
      "authority": "ingestion_service",
      "server_version": "1.0.0"
    },
    "prev_hash": "...",
    "event_hash": "..."
  }
}
```

**Response 400 (Hash Mismatch):**
```json
{
  "error": "hash_mismatch",
  "seq": 5,
  "expected_hash": "a3f1b2c3...",
  "provided_hash": "9b2c4d5e...",
  "message": "Server-recomputed hash does not match SDK-provided hash at seq=5"
}
```

**Response 409 (Duplicate Sequence):**
```json
{
  "error": "duplicate_sequence",
  "seq": 3,
  "session_id": "...",
  "message": "Event with seq=3 already exists for this session"
}
```

**Response 422 (Validation Error):**
Standard FastAPI validation error format.

#### GET /v1/sessions/{session_id}/export

Export a complete session as JSONL for Verifier consumption.

**Path Parameters:**
- `session_id`: UUID v4 string

**Response 200:**
- `Content-Type: application/x-ndjson`
- Body: one JSON event object per line, ordered by `seq` ascending
- Includes server-emitted events (CHAIN_SEAL, CHAIN_BROKEN if present)

**Response 404:**
```json
{"error": "session_not_found", "session_id": "..."}
```

**Note:** The exported JSONL must produce PASS when run through the Verifier. This is a correctness requirement, not a nice-to-have. There is an E2E test for this.

### 4.4 Database Schema — Complete DDL

```sql
-- Migration: 001_initial_schema.py

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id        VARCHAR(255) NOT NULL,
    started_at      TIMESTAMPTZ,
    ended_at        TIMESTAMPTZ,
    status          VARCHAR(50) NOT NULL DEFAULT 'active',
    -- Values: 'active' | 'sealed' | 'broken' | 'frozen'
    event_count     INTEGER NOT NULL DEFAULT 0,
    final_hash      VARCHAR(64),        -- Set when CHAIN_SEAL is emitted
    evidence_class  VARCHAR(50),        -- Set when CHAIN_SEAL is emitted
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_sessions_created_at ON sessions(created_at);

CREATE TABLE events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES sessions(id) ON DELETE RESTRICT,
    seq             INTEGER NOT NULL,
    event_type      VARCHAR(50) NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}',
    prev_hash       VARCHAR(64) NOT NULL,
    event_hash      VARCHAR(64) NOT NULL,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    authority       VARCHAR(20) NOT NULL DEFAULT 'sdk',
    -- Values: 'sdk' | 'server'

    CONSTRAINT events_session_seq_unique UNIQUE (session_id, seq)
    -- This constraint enforces append-only at the data level
);

CREATE INDEX idx_events_session_seq ON events(session_id, seq);
CREATE INDEX idx_events_event_type ON events(event_type);
```

```sql
-- Migration: 002_append_only_permissions.py
-- Creates the restricted application user

-- Create app user (run as superuser during setup)
CREATE USER agentops_app WITH PASSWORD 'CHANGE_ME_IN_PRODUCTION';

-- Grant schema access
GRANT USAGE ON SCHEMA public TO agentops_app;

-- Events: INSERT and SELECT only. No UPDATE. No DELETE. EVER.
GRANT SELECT, INSERT ON events TO agentops_app;

-- Sessions: INSERT, SELECT, UPDATE allowed (status field changes).
-- UPDATE is needed to set status='sealed' when CHAIN_SEAL is emitted.
-- DELETE is NOT granted.
GRANT SELECT, INSERT, UPDATE ON sessions TO agentops_app;

-- Sequence for gen_random_uuid (needed for inserts)
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO agentops_app;
```

**Why UPDATE is denied for events but allowed for sessions:**
- Events, once written, must never change. This is the core tamper-evidence guarantee.
- Sessions need their `status`, `event_count`, and `final_hash` updated as events arrive.
- Session records are metadata about the chain, not part of the chain itself.

### 4.5 Server-Side Hash Chain Computation (`backend/app/services/ingestion/chain.py`)

```python
import sys
import os
# CRITICAL: Use the same JCS from verifier — do not duplicate
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'verifier'))
from jcs import canonicalize as jcs_canonicalize
import hashlib


class ChainVerifier:
    """
    Server-side hash chain verification.
    
    The server NEVER trusts SDK-computed hashes.
    It recomputes every hash independently and compares.
    
    If SDK hash matches server-computed hash: event is accepted.
    If they differ: batch is rejected with 400.
    
    This is what upgrades NON_AUTHORITATIVE to AUTHORITATIVE:
    an independent party has verified the computation.
    """
    
    def verify_event_hash(self, event: dict) -> tuple[bool, str, str]:
        """
        Verify the event_hash of a single event.
        
        Returns (is_valid, expected_hash, provided_hash).
        """
        event_for_hash = {k: v for k, v in event.items() if k != "event_hash"}
        canonical = jcs_canonicalize(event_for_hash)
        expected = hashlib.sha256(canonical).hexdigest()
        provided = event.get("event_hash", "")
        return (expected == provided, expected, provided)
    
    def verify_prev_hash(
        self,
        event: dict,
        previous_event_hash: str,
    ) -> tuple[bool, str, str]:
        """
        Verify that event.prev_hash equals the previous event's event_hash.
        
        Returns (is_valid, expected_prev_hash, provided_prev_hash).
        """
        expected = previous_event_hash
        provided = event.get("prev_hash", "")
        return (expected == provided, expected, provided)
```

### 4.6 CHAIN_SEAL Construction (`backend/app/services/ingestion/sealer.py`)

```python
class ChainSealer:
    """
    Emits the CHAIN_SEAL event when SESSION_END is received.
    
    The CHAIN_SEAL is the server's cryptographic endorsement:
    "I have verified this session's hash chain, and it is complete."
    
    The CHAIN_SEAL is itself a proper event with seq, prev_hash, event_hash.
    It can be verified by the standalone Verifier.
    """
    
    def build_chain_seal(
        self,
        session_id: str,
        last_seq: int,
        last_event_hash: str,
        total_event_count: int,  # including the CHAIN_SEAL itself
        server_version: str = "1.0.0",
    ) -> dict:
        """
        Build the CHAIN_SEAL event.
        
        Parameters
        ----------
        last_seq : int
            The seq of the SESSION_END event
        last_event_hash : str
            The event_hash of the SESSION_END event (= our prev_hash)
        total_event_count : int
            Total events in the session AFTER adding CHAIN_SEAL
        """
        import datetime
        server_ts = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
        
        seal_seq = last_seq + 1
        
        seal_event = {
            "seq": seal_seq,
            "event_type": "CHAIN_SEAL",
            "session_id": session_id,
            "timestamp": server_ts,
            "payload": {
                "final_hash": last_event_hash,
                "event_count": total_event_count,
                "server_timestamp": server_ts,
                "authority": "ingestion_service",
                "server_version": server_version,
            },
            "prev_hash": last_event_hash,
        }
        
        # Compute hash for the CHAIN_SEAL itself
        from verifier.jcs import canonicalize
        import hashlib
        canonical = canonicalize({k: v for k, v in seal_event.items() if k != "event_hash"})
        seal_event["event_hash"] = hashlib.sha256(canonical).hexdigest()
        
        return seal_event
```

---

## 5. Component 4: LangChain Integration — Full Technical Specification

### 5.1 AgentOpsCallbackHandler (`sdk/python/agentops_replay/integrations/langchain/handler.py`)

```python
from langchain.callbacks.base import BaseCallbackHandler
from agentops_sdk.client import AgentOpsClient
from agentops_sdk.events import EventType
import hashlib


class AgentOpsCallbackHandler(BaseCallbackHandler):
    """
    LangChain callback handler for AgentOps Replay.
    
    Automatically captures all LLM calls, tool invocations,
    and errors from any LangChain component.
    
    Usage:
        handler = AgentOpsCallbackHandler(agent_id="my-agent")
        handler.start_session()
        chain.invoke(input, config={"callbacks": [handler]})
        handler.end_session()
        handler.export_to_jsonl("session.jsonl")
    
    Privacy guarantee:
    - Prompt content is hashed, never stored verbatim
    - Response content is hashed, never stored verbatim
    - Tool arguments are hashed, never stored verbatim
    """
    
    def __init__(
        self,
        agent_id: str,
        local_authority: bool = True,
        server_url: str | None = None,
        redact_pii: bool = False,
        buffer_size: int = 1000,
    ) -> None: ...
    
    def start_session(self) -> str:
        """Start recording. Returns session_id."""
    
    def end_session(self, status: str = "success") -> None:
        """End recording."""
    
    def export_to_jsonl(self, path: str) -> None:
        """Flush to JSONL file (local authority mode)."""
    
    def send_to_server(self) -> dict:
        """Send to ingestion service (server authority mode)."""
    
    # LangChain BaseCallbackHandler methods to implement:
    
    def on_llm_start(
        self,
        serialized: dict,
        prompts: list[str],
        **kwargs,
    ) -> None:
        """Fires before LLM call. Records LLM_CALL event."""
        payload = {
            "model_id": serialized.get("id", ["unknown"])[-1],
            "prompt_hash": hashlib.sha256(
                "\n".join(prompts).encode()
            ).hexdigest(),
            "prompt_token_count": sum(len(p.split()) for p in prompts),  # approx
        }
        self._client.record(EventType.LLM_CALL, payload)
    
    def on_llm_end(self, response, **kwargs) -> None:
        """Fires after LLM response. Records LLM_RESPONSE event."""
    
    def on_llm_error(self, error: Exception, **kwargs) -> None:
        """Fires on LLM error. Records TOOL_ERROR or LOG_DROP."""
    
    def on_tool_start(
        self,
        serialized: dict,
        input_str: str,
        **kwargs,
    ) -> None:
        """Fires before tool invocation. Records TOOL_CALL event."""
    
    def on_tool_end(self, output: str, **kwargs) -> None:
        """Fires after tool completion. Records TOOL_RESULT event."""
    
    def on_tool_error(self, error: Exception, **kwargs) -> None:
        """Fires on tool failure. Records TOOL_ERROR event."""
```

### 5.2 Event Mapping: LangChain → AgentOps

| LangChain Callback | AgentOps EventType | Key Payload Fields |
|---|---|---|
| `on_llm_start` | `LLM_CALL` | `prompt_hash`, `model_id`, `prompt_token_count` |
| `on_llm_end` | `LLM_RESPONSE` | `content_hash`, `completion_token_count`, `finish_reason` |
| `on_llm_error` | `TOOL_ERROR` | `error_type`, `error_message` |
| `on_tool_start` | `TOOL_CALL` | `tool_name`, `args_hash`, `call_id` |
| `on_tool_end` | `TOOL_RESULT` | `tool_name`, `result_hash`, `call_id` |
| `on_tool_error` | `TOOL_ERROR` | `tool_name`, `error_type`, `error_message` |

---

## 6. Packaging and Distribution

### 6.1 `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "agentops-replay"
version = "1.0.0"
description = "Cryptographically verifiable, immutable event logging for AI agents"
requires-python = ">=3.11"
license = {text = "Apache-2.0"}
readme = "README.md"
keywords = ["ai", "agents", "audit", "accountability", "observability"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: Apache Software License",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: System :: Logging",
    "Topic :: Security",
]

# Core SDK + Verifier: ZERO DEPENDENCIES
dependencies = []

[project.optional-dependencies]
langchain = [
    "langchain>=0.1.0",
]
server = [
    "fastapi>=0.110",
    "uvicorn>=0.27",
    "sqlalchemy>=2.0",
    "asyncpg>=0.29",
    "alembic>=1.13",
    "pydantic-settings>=2.0",
]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",         # for TestClient
    "pytest-cov>=4.0",
]

[project.scripts]
agentops-verify = "verifier.agentops_verify:main"

[tool.setuptools.packages.find]
where = ["."]
include = ["agentops_sdk*", "verifier*", "sdk*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### 6.2 Install Scenarios

```bash
# Minimal: SDK + Verifier only (zero dependencies)
pip install agentops-replay

# With LangChain integration
pip install "agentops-replay[langchain]"

# With Ingestion Service
pip install "agentops-replay[server]"

# Full development install
pip install -e ".[langchain,server,dev]"

# Verifier CLI after install
agentops-verify session.jsonl
agentops-verify session.jsonl --format json
```

---

## 7. Testing Requirements

### 7.1 Unit Tests — Required Coverage

**`tests/unit/test_buffer.py`**
- Buffer accepts events up to capacity
- Buffer overflow triggers LOG_DROP, not silent drop
- LOG_DROP contains correct seq_range_start, seq_range_end, count
- Thread-safe: 10 concurrent threads recording 100 events each → all events either recorded or in LOG_DROP
- Buffer drain returns events in seq order

**`tests/unit/test_envelope.py`**
- Compute hash for a known event → compare to pre-computed expected hash
- Hash changes when any field changes (seq, type, payload, timestamp)
- `prev_hash = "0" * 64` for seq=1
- `prev_hash` for seq=N equals `event_hash` of seq=N-1
- JCS import works (imports from verifier/jcs.py, not a copy)

**`tests/unit/test_verifier.py`**
- valid_session.jsonl → result=PASS, evidence_class=NON_AUTHORITATIVE_EVIDENCE
- tampered_hash.jsonl → result=FAIL, check=hash_chain_integrity
- sequence_gap.jsonl → result=FAIL, check=sequence_integrity
- A session with CHAIN_SEAL and no LOG_DROP → AUTHORITATIVE_EVIDENCE
- A session with CHAIN_SEAL and LOG_DROP → PARTIAL_AUTHORITATIVE_EVIDENCE
- A session without SESSION_START → FAIL (session completeness)
- A session without SESSION_END → FAIL (session completeness)
- Exit code 0 on PASS, 1 on FAIL, 2 on FileNotFoundError

### 7.2 Integration Tests — Required Coverage

**`tests/integration/test_ingestion_api.py`**
- POST /v1/ingest with valid batch → 200
- POST /v1/ingest with hash mismatch → 400 with seq and hash details
- POST /v1/ingest with duplicate seq → 409
- POST /v1/ingest with SESSION_END → 200 with chain_seal in response
- GET /v1/sessions/{id}/export → JSONL with all events in seq order
- GET /v1/sessions/nonexistent/export → 404
- GET /health → 200

### 7.3 E2E Tests — Required Coverage

**`tests/e2e/test_full_flow.py`**

Test 1: Local Authority Mode
1. Create AgentOpsClient(local_authority=True)
2. start_session(agent_id="e2e-test-agent", model_id="test-model")
3. record(LLM_CALL, {...})
4. record(LLM_RESPONSE, {...})
5. record(TOOL_CALL, {...})
6. record(TOOL_RESULT, {...})
7. end_session(status="success")
8. flush_to_jsonl("/tmp/test_session.jsonl")
9. Run Verifier programmatically on the file
10. Assert result == "PASS"
11. Assert evidence_class == "NON_AUTHORITATIVE_EVIDENCE"

Test 2: Server Authority Mode (requires running Ingestion Service)
1. Same steps 1–7 but with local_authority=False, server_url="http://localhost:8000"
2. send_to_server() → assert chain_seal is returned
3. GET /v1/sessions/{id}/export → save to /tmp/server_export.jsonl
4. Run Verifier on /tmp/server_export.jsonl
5. Assert result == "PASS"
6. Assert evidence_class == "AUTHORITATIVE_EVIDENCE"

Test 3: Buffer Overflow Flow
1. Create AgentOpsClient with buffer_size=5
2. Record 10 events
3. flush_to_jsonl()
4. Run Verifier → Assert PASS (chain must be valid with LOG_DROP)
5. Assert exactly one LOG_DROP event in the JSONL
6. Assert evidence_class == "NON_AUTHORITATIVE_EVIDENCE"

---

## 8. CI/CD Specification

### 8.1 GitHub Actions Workflow (`.github/workflows/ci.yml`)

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: agentops_test
          POSTGRES_USER: agentops_app
          POSTGRES_PASSWORD: testpassword
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      
      - name: Install dependencies
        run: pip install -e ".[langchain,server,dev]"
      
      - name: Run unit tests
        run: pytest tests/unit/ -v
      
      - name: Verify test vectors
        run: |
          python3 verifier/generator.py
          python3 verifier/agentops_verify.py verifier/test_vectors/valid_session.jsonl
          python3 verifier/agentops_verify.py verifier/test_vectors/tampered_hash.jsonl && exit 1 || true
          python3 verifier/agentops_verify.py verifier/test_vectors/sequence_gap.jsonl && exit 1 || true
          echo "All test vector checks passed"
      
      - name: Run integration tests
        env:
          AGENTOPS_DATABASE_URL: postgresql+asyncpg://agentops_app:testpassword@localhost:5432/agentops_test
        run: pytest tests/integration/ -v
      
      - name: Run E2E tests
        env:
          AGENTOPS_DATABASE_URL: postgresql+asyncpg://agentops_app:testpassword@localhost:5432/agentops_test
        run: pytest tests/e2e/ -v
```

---

## 9. Docker Configuration

### 9.1 `backend/docker-compose.yml`

```yaml
version: "3.9"

services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: agentops
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres_superuser_password
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 10

  app_user_setup:
    image: postgres:15-alpine
    depends_on:
      db:
        condition: service_healthy
    environment:
      PGPASSWORD: postgres_superuser_password
    command: >
      psql -h db -U postgres -c
      "CREATE USER agentops_app WITH PASSWORD 'apppassword';
       CREATE DATABASE agentops OWNER postgres;
       GRANT USAGE ON SCHEMA public TO agentops_app;"
    restart: "no"

  server:
    build: .
    depends_on:
      db:
        condition: service_healthy
    environment:
      AGENTOPS_DATABASE_URL: postgresql+asyncpg://agentops_app:apppassword@db:5432/agentops
      AGENTOPS_LOG_LEVEL: INFO
    ports:
      - "8000:8000"
    command: >
      sh -c "
        alembic upgrade head &&
        uvicorn app.main:app --host 0.0.0.0 --port 8000
      "

volumes:
  pgdata:
```

### 9.2 `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the verifier (needed for JCS import by the server)
COPY verifier/ /app/verifier/

# Copy backend code
COPY backend/ /app/backend/
COPY agentops_sdk/ /app/agentops_sdk/

WORKDIR /app/backend

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 10. Environment Variables Reference

| Variable | Component | Default | Required | Description |
|---|---|---|---|---|
| `AGENTOPS_SERVER_URL` | SDK | None | If `local_authority=False` | Ingestion service base URL |
| `AGENTOPS_BUFFER_SIZE` | SDK | 1000 | No | Ring buffer capacity |
| `AGENTOPS_LOG_LEVEL` | All | WARNING | No | Python logging level |
| `AGENTOPS_DATABASE_URL` | Backend | None | Yes (in Docker) | PostgreSQL connection string |
| `AGENTOPS_HOST` | Backend | 0.0.0.0 | No | Bind host |
| `AGENTOPS_PORT` | Backend | 8000 | No | Bind port |
| `AGENTOPS_API_KEY_REQUIRED` | Backend | false | No | Enable API key auth (enterprise) |

---

*TRD v2.0 — Last Updated May 2026*  
*This document is authoritative for all technical decisions.*  
*When PRD and TRD conflict: PRD wins on scope; TRD wins on implementation details.*  
*When both conflict with CONSTITUTION.md: CONSTITUTION.md wins.*
