# Goals: Ingestion Service Completion & System Unification

**Date:** January 30, 2026
**Theme:** "Closing the Loop"

Today's objective is to complete **Phase 6 (Ingestion Service)** and verify the "Golden Path" (SDK → Ingestion → Storage → Replay). We are moving from "components in isolation" to a "working system".

---

## 🎯 Goal 1: The Ingestion Service (Phase 6 Finalization)

**Objective:** Build the authoritative gatekeeper that validates, sequences, seals, and persists events.

### 1.1 Core Service Logic

- **File:** `backend/app/services/ingestion/service.py` (New)
- **Responsibility:** Orchestrator.
- **Logic:**
  - Accept batch of raw events.
  - Validate Session ID / Sequence continuity (using `EventChain` model).
  - Recompute hashes (using `Hasher`).
  - Seal the chain (using `Sealer`).
  - Atomic persistence (All-or-Nothing).

### 1.2 API Layer

- **File:** `backend/app/api/v1/endpoints/ingestion.py` (New)
- **Endpoint:** `POST /v1/ingest`
- **Requirements:**
  - High-throughput optimized.
  - Strict schema validation.
  - Proper error codes (409 Conflict for sequence mismatch, 400 for bad hash).

### 1.3 Database Integration

- **File:** `backend/app/services/ingestion/transaction.py` or within `service.py`
- **Requirements:**
  - **Atomic Batch Commits:** Use `db.begin_nested()` or transaction scope.
  - **Concurrency Control:** `SELECT FOR UPDATE` on the generic Session or Chain record to prevent race conditions (two diverse batches for same session).

---

## 🚀 Goal 2: End-to-End Verification (The "It Works" Moment)

**Objective:** Prove the system works as a whole.

### 2.1 The Golden Path

- Run the SDK (using `examples/langchain_demo` or similar).
- Send events to the _local_ Ingestion Service.
- Verify events appear in DB with `AUTHORITATIVE` status and `CHAIN_SEAL`.
- Verify Replay API serves these events correctly.

### 2.2 Rejection Testing

- Manually tamper with a payload in the SDK before sending.
- Verify Ingestion Service **rejects** the batch (HTTP 400/409).
- Verify no partial data is written to DB.

---

## 📊 Success Criteria for Today

1.  **Ingestion Service is Live:** `POST /v1/ingest` is accepting events.
2.  **Authority is Enforced:** Server-side `CHAIN_SEAL` events are generated and stored.
3.  **Atomicity is Guaranteed:** Failed batches write ZERO events to DB.
4.  **Replay is Deterministic:** The Replay API serves the exact sequence stored.
