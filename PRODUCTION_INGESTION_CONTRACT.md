# Production Ingestion Contract

**Status**: IMMUTABLE
**Version**: 1.0.0
**Enforcement**: STRICT
**Audience**: Security, Compliance, Legal, Platform Engineering

This document is the **System of Record Definition** for AgentOps Replay. It defines the absolute boundaries of the Ingestion Service.

## 1. Ingestion Authority Definition

- **Sole Authority**: The Ingestion Service is the **ONLY** component permitted to:
  - Assign authoritative `CHAIN_SEAL` events.
  - Compute and assign `event_hash` and `prev_event_hash` for the permanent record.
  - Declare a session as "EVIDENCE".
- **Untrusted Inputs**: All data received from SDKs/Clients is treated as **CLAIMS**, never facts.
  - Client-asserted `event_hash` MUST be ignored or rejected.
  - Client-asserted `chain_authority` MUST be rejected (must be null).
- **Database Trust**: The underlying database is treated as a dumb storage backend. Data integrity is derived **exclusively** from the cryptographic hash chain, not the storage medium.

### Hash Taxonomy

The Ingestion Service computes and validates three distinct hash types:

- **`payload_hash`**: The SHA-256 hash of the canonicalized (JCS) event payload.
  - **Client Behavior**: The client MAY compute and submit `payload_hash`.
  - **Ingestion Behavior**: The Ingestion Service MUST recompute `payload_hash` from the received payload and verify it matches the client-provided value (if present). Client-provided values are never trusted.
  - **Rejection Rule**: If client-provided `payload_hash` does not match the recomputed value, the event MUST be rejected (HARD REJECT).

- **`event_hash`**: The SHA-256 hash of the sealed event envelope, computed over the signed fields (`event_id`, `session_id`, `sequence_number`, `timestamp_wall`, `event_type`, `payload_hash`, `prev_event_hash`).
  - **Client Behavior**: Clients MUST NOT submit `event_hash`. Any client-provided `event_hash` MUST be rejected (Authority Leak).
  - **Ingestion Behavior**: The Ingestion Service MUST compute `event_hash` for every accepted event. This hash forms the cryptographic chain.

- **`prev_event_hash`**: A reference to the previous event's `event_hash`, forming the hash chain linkage.
  - **Client Behavior**: Clients MUST NOT submit `prev_event_hash` in Server Authority Mode. Any client-provided `prev_event_hash` MUST be rejected (Authority Leak).
  - **Ingestion Behavior**: The Ingestion Service MUST compute `prev_event_hash` from its internal chain state for each event.

**Authority Enforcement**: Client-provided `event_hash` and `chain_authority` MUST be rejected. Client-provided `payload_hash` MAY be submitted but is always verified by Ingestion.

## 2. Ingestion API Surface (Minimal)

The Ingestion Service exposes **EXACTLY ONE** write path.

- **Endpoint**: `POST /v1/ingest/events`
- **Method**: Synchronous, Atomic Batch or Single Event.
- **Semantics**: `APPEND_ONLY`.
  - **NO** Updates (PUT/PATCH forbidden).
  - **NO** Deletions (DELETE forbidden).
  - **NO** Out-of-order writes (Sequence must be contiguous).

## 3. Validation & Rejection Rules (Taxonomy)

For every incoming payload, the Ingestion Service MUST make a definitive decision. "Best effort" is forbidden.

### A. HARD REJECT (400 Bad Request)

The payload does not exist. It is discarded.

- **Schema Violation**: Missing required fields, wrong types, extra fields.
- **JCS Violation**: Payload is not valid JSON or cannot be canonicalized (RFC 8785).
- **Timestamp Ambiguity**: `timestamp_wall` is missing or malformed ISO-8601.
- **Authority Leak**: Input contains `event_hash` or `chain_authority` (Client trying to spoof authority).
- **Hash Mismatch**: Client-provided `payload_hash` does not match `SHA256(JCS(payload))`.

### B. PARTIAL ACCEPT (202 Accepted with Warnings)

The payload is stored but explicitly downgraded.

- **Gap Detected**: `sequence_number` > `last_sequence + 1`.
  - **Strict Mode** (see EVENT_LOG_SPEC.md#LOG_DROP): Gaps are REJECTED (HARD REJECT).
  - **Permissive Mode**: Gaps are recorded as `LOG_DROP` events (see EVENT_LOG_SPEC.md#LOG_DROP for `LOG_DROP` definition, fields, and semantics).

### C. ACCEPT (201 Created)

The payload becomes **Authoritative Evidence**.

## 4. Canonicalization & Hashing Rules

- **Standard**: **JCS (RFC 8785)** is the ONLY allowed serialization for hashing.
- **Algorithm**: **SHA-256**.
- **Redaction Timing**: **BEFORE** Ingestion.
  - The SDK must redact PII _before_ transmission.
  - Ingestion computes hashes on the _received_ (redacted) payload.
  - Ingestion **NEVER** sees or hashes raw PII.
- **Rehashing**: Ingestion **MUST RECOMPUTE** the `payload_hash` to verify client integrity. Trusting the client's hash is forbidden.

## 5. Chain Sealing & Authority Versioning

The Ingestion Service applies the **Seal** to every accepted event.

1.  **Prev Hash**: Derived from the previous accepted event's `event_hash`.
2.  **Authority**: Field `chain_authority` is set to the current Ingestion Service Identity (e.g., `agentops-ingest-v1`).
3.  **Event Hash**: Computed as:
    ```
    SHA256( JCS({
        "event_id": ...,
        "session_id": ...,
        "sequence_number": ...,
        "timestamp_wall": ...,
        "event_type": ...,
        "payload_hash": ...,
        "prev_event_hash": ...
    }) )
    ```
    _Note: `chain_authority` field itself is NOT included in the hash preimage to allow for key rotation/migration without breaking the chain, unless strictly specified in `SCHEMA.md`._ (Clarification: If Schema requires it, it must be included. For v1.0, we adhere to the strict list above).
    - **Invariant**: `chain_authority` is metadata, not a fact claim. The cryptographic integrity of the chain is derived exclusively from `(payload_hash, prev_event_hash)` continuity.

## 6. Storage Invariants

- **Immutable Rows**: Once written, a row is **NEVER** modified.
- **No Backfill**: Late-arriving events for a closed or significantly aged session MUST be rejected.
  - **Closed Session**: A session is considered "closed" when:
    - An explicit `CHAIN_SEAL` event for that `session_id` has been ingested, OR
    - A configurable inactivity timeout (e.g., no events received for N minutes, where N is configurable) has elapsed and the Ingestion Service has marked the session as closed.
  - **Significantly Aged**: A session is considered "significantly aged" when:
    - No events have been received for a configurable time threshold (e.g., 24 hours).
  - **Enforcement**: Both the inactivity timeout and the aging threshold MUST be configurable and MUST be surfaced to clients via API or documentation.
  - **Rejection Behavior**: Events arriving for closed or significantly aged sessions MUST be rejected with a clear error indicating the session state.
- **Strict Ordering**: Events are stored by `(session_id, sequence_number)`.

## 7. Outputs & Guarantees

The Ingestion Service guarantees:

1.  **session_golden.json Export**: A stream of events that have been validated and sealed.
    - **Format**: See EVENT_LOG_SPEC.md for the `session_golden.json` schema definition, required fields, and validation rules.
2.  **Evidence Eligibility**: Only sessions that fully pass ingestion checks are eligible for Class A/B classification.
    - **Classification Rules**: See EVIDENCE_CLASSIFICATION_SPEC.md for Class A/B criteria, requirements, and legal implications.

## 8. Explicit Non-Goals

The Ingestion Service strictly **DOES NOT**:

- **Infer Data**: If it's missing, it's missing.
- **Fix Data**: "Auto-correcting" invalid JSON or timestamps is forbidden.
- **Validate Business Logic**: It cares about the _shape_ of the event, not whether the Refund Amount is correct.
- **Execute Code**: It is a passive recorder.
