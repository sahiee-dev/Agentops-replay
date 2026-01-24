# Day 4: Backend & Compliance Artifacts

**Date:** January 25, 2026  
**Focus:** Production Backend + Compliance Exports (Maximum Execution Day)

---

## 🎯 Today's Objective

Ship the production-grade backend and compliance export system. By end of day:

1. Ingestion service with server-side hash verification
2. CHAIN_SEAL emission (true AUTHORITATIVE_EVIDENCE)
3. JSON + PDF compliance exports
4. Full end-to-end test: Agent → Server → Verified Export

---

## 📋 Execution Plan

### Block 1: Ingestion Service Core (1.5 hours)

The critical piece: server-side authority that makes evidence admissible.

- [ ] **1.1** Create `/backend/app/ingestion/` package
- [ ] **1.2** Implement `IngestService` class:
  - [ ] Receive event batches from SDK
  - [ ] Recompute hash chain server-side (MUST ignore SDK hashes)
  - [ ] Validate sequence continuity
  - [ ] Emit CHAIN_SEAL with metadata (ingestion_service_id, seal_timestamp, session_digest)
- [ ] **1.3** Add session management:
  - [ ] Start session endpoint
  - [ ] Append events endpoint
  - [ ] End session + seal endpoint
- [ ] **1.4** PostgreSQL integration:
  - [ ] Append-only event table
  - [ ] Session metadata table
  - [ ] CHAIN_SEAL storage

**Exit Criteria:** Server can receive events and emit AUTHORITATIVE_EVIDENCE

---

### Block 2: API Endpoints (1 hour)

REST API for SDK and UI communication.

- [ ] **2.1** `/api/v1/sessions` endpoints:
  - [ ] POST `/sessions` - Start new session
  - [ ] POST `/sessions/{id}/events` - Append events
  - [ ] POST `/sessions/{id}/seal` - End and seal session
  - [ ] GET `/sessions/{id}` - Retrieve session
- [ ] **2.2** `/api/v1/verify` endpoint:
  - [ ] POST `/verify` - Verify a session
  - [ ] Returns evidence classification
- [ ] **2.3** Authentication (basic API key for now)

**Exit Criteria:** SDK can send events to server, server returns sealed sessions

---

### Block 3: Compliance Exports (1.5 hours)

The money-maker: audit-grade exports.

- [ ] **3.1** JSON Export:
  - [ ] RFC 8785 canonical serialization
  - [ ] Embedded verification metadata
  - [ ] Evidence class prominently displayed
  - [ ] Chain-of-custody statement
- [ ] **3.2** PDF Export:
  - [ ] Human-readable timeline
  - [ ] Executive summary section
  - [ ] Technical verification details
  - [ ] Non-certifying disclaimer (REQUIRED)
  - [ ] Use ReportLab or WeasyPrint
- [ ] **3.3** Export API:
  - [ ] GET `/sessions/{id}/export?format=json`
  - [ ] GET `/sessions/{id}/export?format=pdf`

**Exit Criteria:** Can download JSON and PDF compliance artifacts

---

### Block 4: Server Authority Integration (1 hour)

Connect LangChain demo to real server.

- [ ] **4.1** Update SDK client for remote mode:
  - [ ] HTTP transport
  - [ ] Async batching
  - [ ] Retry with exponential backoff
- [ ] **4.2** Test flow:
  - [ ] LangChain agent → SDK → Ingestion Service → DB
  - [ ] Export session → Verify → AUTHORITATIVE_EVIDENCE
- [ ] **4.3** Update demo:
  - [ ] Add `--server` flag to run_demo.py
  - [ ] Document server setup

**Exit Criteria:** Full flow verified with AUTHORITATIVE_EVIDENCE

---

### Block 5: GDPR & Policy Engine (1 hour)

Basic policy enforcement.

- [ ] **5.1** GDPR exposure detection:
  - [ ] Scan payloads for PII patterns (email, phone, SSN)
  - [ ] Flag sessions with PII exposure
  - [ ] Add to export reports
- [ ] **5.2** Tool access audit:
  - [ ] List all tools called in session
  - [ ] Timestamp and args summary
- [ ] **5.3** Policy configuration:
  - [ ] YAML policy files
  - [ ] Max event count per session
  - [ ] Required tool call logging

**Exit Criteria:** Exports show PII warnings and tool audit

---

### Block 6: Integration Tests (45 min)

Comprehensive test suite.

- [ ] **6.1** Backend API tests
- [ ] **6.2** Ingestion service tests
- [ ] **6.3** Export format validation
- [ ] **6.4** End-to-end flow test

**Exit Criteria:** All tests passing

---

### Block 7: Documentation (30 min)

- [ ] **7.1** Update progress.md
- [ ] **7.2** Add backend setup guide to README
- [ ] **7.3** API documentation

---

## 🚫 Explicitly NOT Doing Today

- Frontend dashboard improvements
- Multi-framework integrations (CrewAI, AutoGen)
- Real-time alerting
- Multi-region deployment
- Hardware security module integration

---

## 📁 Files to Create

| Action | Path                                                  |
| ------ | ----------------------------------------------------- |
| CREATE | `backend/app/ingestion/__init__.py`                   |
| CREATE | `backend/app/ingestion/service.py`                    |
| CREATE | `backend/app/ingestion/models.py`                     |
| CREATE | `backend/app/api/v1/sessions.py`                      |
| CREATE | `backend/app/api/v1/verify.py`                        |
| CREATE | `backend/app/api/v1/export.py`                        |
| CREATE | `backend/app/compliance/json_export.py`               |
| CREATE | `backend/app/compliance/pdf_export.py`                |
| CREATE | `backend/app/policy/gdpr.py`                          |
| CREATE | `backend/app/policy/tool_audit.py`                    |
| MODIFY | `agentops_sdk/client.py` (remote mode)                |
| MODIFY | `examples/langchain_demo/run_demo.py` (--server flag) |
| MODIFY | `progress.md`                                         |
| MODIFY | `README.md`                                           |

---

## ✅ Success Criteria

By end of Day 4:

1. ✅ Ingestion service receives and seals events
2. ✅ Sessions classified as AUTHORITATIVE_EVIDENCE
3. ✅ JSON export with verification metadata
4. ✅ PDF export with disclaimer
5. ✅ GDPR exposure warnings in exports
6. ✅ Full flow: Agent → Server → Export → Verify
7. ✅ Integration tests passing
8. ✅ progress.md updated

---

## 🔥 The One Thing That Matters

> **If we can produce a PDF compliance artifact that says "AUTHORITATIVE_EVIDENCE - VERIFIED", we have enterprise-ready proof.**

This is what Legal and Compliance teams need. Everything else is optimization.

---

## Dependencies

- Python 3.11+
- PostgreSQL (Docker recommended)
- FastAPI
- ReportLab or WeasyPrint (PDF generation)
- Existing SDK and verifier from Days 1-3

---

## How to Proceed

Start with Block 1 (Ingestion Service) - this is the foundation.

**Target completion:** ~7 hours of focused work.

---

_Execute with audit-grade precision._
