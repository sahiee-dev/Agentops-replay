# Goals: Operational Readiness & Resilience

**Date:** February 7, 2026
**Theme:** "If It Breaks, We Can Prove It"

Today's objective is to complete Phase 8: Operational Readiness & Resilience. We transition from "It works in theory" to "It survives failure in practice".

---

## 🎯 Goal 1: Operational Proof (Reference Deployment)

**Objective:** A single command brings up the entire evidence infrastructure in a production-like topology.

### 1.1 Docker Compose Environment

- **File:** `docker-compose.yml`
- **Services:**
  - `postgres:16-alpine` (Immutable Event Store)
  - `ingestion-service` (FastAPI + SQLAlchemy)
  - `verifier` (CLI container for on-demand checks)
- **Success Criteria:** `docker-compose up` results in a healthy, ingestion-ready system < 30s.

### 1.2 Deployment Documentation

- **File:** `DEPLOYMENT.md`
- **Content:** Exact environment variables, port mappings, and health check endpoints.

---

## 🚀 Goal 2: Resilience Verification (Network Partitions)

**Objective:** Prove that when the network dies, evidence integrity survives (or fails loudly/safely).

### 2.1 Partition Simulation Test

- **Test:** `tests/resilience/test_network_partition.py`
- **Scenario:**
  1. SDK sends events (success).
  2. Network cut (simulated).
  3. SDK fills buffer -> Emits `LOG_DROP`.
  4. Network restored.
  5. Ingestion accepts remaining events.
  6. **Verifier confirms:** Chain is VALID but marks data loss (if any).

### 2.2 Ingestion Recovery

- **Requirement:** Ingestion service-specific handling of `LOG_DROP` sequencing.
- **Success Criteria:** System classifies session as `PARTIAL_AUTHORITATIVE_EVIDENCE` if drops occurred, never `AUTHORITATIVE`.

---

## 🛡️ Goal 3: Incident Response Playbooks

**Objective:** When the pager rings, the operator knows exactly how to prove what happened.

### 3.1 Playbook Creation

- **File:** `INCIDENT_RESPONSE.md`
- **Scenarios to Document:**
  - **"The Gap"**: Handling Sequence Gaps (Investigate vs Reject).
  - **"The Lie"**: Handling Hash Mismatches (Tampering detected).
  - **"The Leak"**: Handling PII spill (Redaction verification).

---

## 📊 Success Criteria for Today

1. `docker-compose up` works and ingestion endpoint accepts events.
2. `test_network_partition.py` passes and correctly identifies `LOG_DROP` behavior.
3. `INCIDENT_RESPONSE.md` exists and covers the 3 critical failure modes.
