# Goals: Compliance & Ingestion Foundation

**Date:** January 29, 2026
**Theme:** "From Evidence to Authority"

Today's objective is to complete the Compliance layer (Phase 5) and lay the authoritative foundation for the Ingestion Service (Phase 6). This transitions the system from a passive recorder (SDK) to an active arbiter of truth.

---

## 🎯 Goal 1: Complete Phase 5 (Compliance Artifacts)

**Objective:** Deliver audit-grade export capabilities that legal/compliance teams can use immediately.

### 1.1 Finalize Canonical JSON Export

- **File:** `backend/app/compliance/json_export.py`
- **Requirements:**
  - [ ] RFC 8785 JCS Compliance (re-verify)
  - [ ] Strict ISO 8601 formatting (Z-suffix)
  - [ ] Full chain-of-custody metadata
  - [ ] Evidence class assertion

### 1.2 Implement PDF Evidence Export

- **New File:** `backend/app/compliance/pdf_export.py`
- **Requirements:**
  - Executive Summary (Status, Verification Result)
  - Timeline View (Readable event chain)
  - Technical Verification Annex (Hashes, Seals)
  - Legal Disclaimer Injection

### 1.3 GDPR & Privacy Controls

- **New File:** `backend/app/compliance/gdpr.py`
- **Requirements:**
  - PII Detection logic (heuristic)
  - `[REDACTED]` pattern validation
  - Hash preservation check

---

## 🚀 Goal 2: Kickstart Phase 6 (Ingestion Service)

**Objective:** Build the server-side authority that seals the evidence.

### 2.1 Ingestion Service Scaffolding

- **Directory:** `backend/app/services/ingestion/`
- **Components:**
  - Service entry point related to FastAPI/Queue worker
  - Dependency injection for Storage/Auth

### 2.2 Server-Side Hash Recomputation

- **File:** `backend/app/services/ingestion/hasher.py`
- **Critical Requirement:**
  - NEVER trust SDK hashes
  - Re-calculate `prev_hash` -> `curr_hash` chain
  - Validate sequence monotonicity

### 2.3 Chain Sealing Logic

- **File:** `backend/app/services/ingestion/sealer.py`
- **Logic:**
  - Finalize batch
  - Compute Session Digest
  - Emit `CHAIN_SEAL` event

---

## 📊 Success Criteria for Today

1. `json_export.py` produces verifiable outputs against the `verifier` CLI.
2. `pdf_export.py` generates a readable PDF with correct legal disclaimers.
3. Ingestion service can take a raw list of events and reject a tampered chain.
