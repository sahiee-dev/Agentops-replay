# LOG_DROP_ABUSE_PREVENTION.md (v1.0)

## Purpose

This document addresses operational attack surfaces related to LOG_DROP events, explicitly defining abuse scenarios and prevention strategies.

**Context:** EVENT_LOG_SPEC v0.6 defines LOG_DROP _semantics_. This document defines LOG_DROP _economics_ and abuse mitigation.

---

## 1. Abuse Scenarios

### Scenario 1: Storage Bloat Attack

**Attack:**

- Malicious or buggy SDK emits excessive LOG_DROP events
- Each LOG_DROP consumes storage, sequence numbers, and indexing resources
- Session becomes unusable due to metadata bloat

**Example:**

```python
# Malicious SDK
for i in range(1_000_000):
    client.emit_log_drop(dropped_count=1, reason="BUFFER_FULL")
```

**Impact:**

- Storage costs increase linearly with LOG_DROP count
- Replay performance degrades
- Forensic value of session diminishes

---

### Scenario 2: Replay Determinism Degradation

**Attack:**

- SDK emits LOG_DROP events at unpredictable intervals
- Replay system must handle gaps, slowing down playback
- Auditors lose confidence in replay fidelity

**Impact:**

- Replay becomes too slow for incident response
- Evidence usability decreases
- System appears unreliable

---

### Scenario 3: False "Incomplete Evidence" Classification

**Attack:**

- SDK emits unnecessary LOG_DROP events
- Session classified as PARTIAL_AUTHORITATIVE_EVIDENCE
- Downgrades compliance value without actual data loss

**Impact:**

- Compliance-grade sessions misclassified
- False signal in audit reports
- Loss of trust in evidence classification

---

## 2. Prevention Strategies

### Strategy 1: Server-Side Rate Limiting (Recommended)

**Ingestion Service Behavior:**

```python
MAX_LOG_DROPS_PER_SESSION = 100  # Configurable per deployment
MAX_LOG_DROP_RATE = 10  # Per minute

drop_count = 0
last_drop_time = None

for event in session_events:
    if event["event_type"] == "LOG_DROP":
        drop_count += 1

        # Per-session limit
        if drop_count > MAX_LOG_DROPS_PER_SESSION:
            reject_event("EXCESSIVE_LOG_DROPS", f"Session exceeded {MAX_LOG_DROPS_PER_SESSION} drops")

        # Rate limit
        if last_drop_time:
            time_delta = event["timestamp_wall"] - last_drop_time
            if time_delta < 60 / MAX_LOG_DROP_RATE:  # Less than 6 seconds
                reject_event("LOG_DROP_RATE_EXCEEDED", "Too many drops per minute")

        last_drop_time = event["timestamp_wall"]
```

**Consequences of Limit Breach:**

- Ingestion rejects event
- SDK receives error response
- Session marked as PARTIAL_AUTHORITATIVE ("EXCESSIVE_LOG_DROPS" in partial_reasons)

---

### Strategy 2: Cumulative Drop Threshold

**Verifier Behavior:**

```python
total_drops = sum(e["payload"]["dropped_count"] for e in events if e["event_type"] == "LOG_DROP")

if total_drops > EXCESSIVE_THRESHOLD:  # e.g., 10,000 events
    report["warnings"].append({
        "type": "EXCESSIVE_CUMULATIVE_DROPS",
        "message": f"Session dropped {total_drops} events (evidence quality suspect)"
    })
```

**Use Case:**

- Flag sessions with unreasonable data loss
- Auditors can filter out low-quality sessions
- Does not block verification, only warns

---

### Strategy 3: SDK-Side Best Practices (Documentation)

**SDK Design Constraints:**

1. **Backpressure Before Dropping:**
   - SDK SHOULD slow down event emission before dropping
   - LOG_DROP is last resort, not first response

2. **Coalesced Drops:**
   - SDK SHOULD emit one LOG_DROP for N consecutive drops
   - NOT one LOG_DROP per dropped event

3. **Drop Reason Accuracy:**
   - SDK MUST use correct `drop_reason`: `BUFFER_FULL`, `NETWORK_LOSS`, `SDK_CRASH`
   - Allows forensic analysis of drop cause

**Example (Good SDK):**

```python
# Buffer at 95% capacity - slow down
if buffer.utilization() > 0.95:
    sleep(backoff_delay)

# Buffer full - emit single LOG_DROP for batch
if buffer.full():
    dropped_batch = buffer.evict_oldest(N)
    client.emit_log_drop(dropped_count=N, reason="BUFFER_FULL")
```

**Example (Bad SDK):**

```python
# Emit LOG_DROP for every dropped event
for event in dropped_events:
    client.emit_log_drop(dropped_count=1, reason="BUFFER_FULL")
```

---

## 3. Explicit Non-Goals

This specification **WILL NOT**:

### Non-Goal 1: Prevent Denial of Service via LOG_DROP

**Rationale:**

- DoS via LOG_DROP is a resource exhaustion attack, not a correctness bug
- Mitigation is _operational_ (rate limiting), not _protocol-level_
- Ingestion service responsible for resource protection

**Alternative Mitigations:**

- Session-level quotas
- Per-client rate limiting
- Network-level DoS protection

### Non-Goal 2: Cryptographic Proof of Drop Legitimacy

**Rationale:**

- SDK drop reasons are _hints_, not _proofs_
- System cannot distinguish intentional drop from fabricated LOG_DROP
- Trust model: SDK is untrusted, drops are forensically visible but not preventable

**Alternative:**

- Server-side drop detection (e.g., sequence gap without corresponding LOG_DROP)
- Audit of SDK behavior patterns

### Non-Goal 3: Enforce "Acceptable Drop Rate"

**Rationale:**

- No universal definition of "too many drops"
- Context-dependent (batch jobs vs. real-time agents)
- Left to policy layer, not protocol

**Alternative:**

- Verifier warnings for excessive drops (Strategy 2)
- Policy-based rejection (future extension)

---

## 4. Recommended Deployment Limits

### Production Ingestion Service

```yaml
log_drop_limits:
  max_drops_per_session: 100
  max_drops_per_minute: 10
  max_cumulative_dropped_events: 10000
```

**Justification:**

- 100 LOG_DROP events = reasonable for long-running sessions with network issues
- 10/minute rate = prevents burst attacks
- 10,000 cumulative drops = session is degraded but not useless

**Breach Behavior:**

- Session continues (fail-open for agent)
- Evidence classification downgraded (fail-closed for integrity)
- Audit trail preserved

---

### Policy Enforcement (Future)

```bash
# Reject sessions with > 50 drops
python3 verifier/agentops_verify.py session.jsonl \
  --reject-excessive-drops \
  --max-drops 50
```

**Use Case:**

- Compliance requirements: "sessions with >X drops are not compliance-grade"
- Automated filtering of low-quality sessions

---

## 5. Verifier Warnings

When excessive drops detected, verifier SHOULD emit warning (not error):

```json
{
  "session_id": "...",
  "status": "PASS",
  "evidence_class": "PARTIAL_AUTHORITATIVE_EVIDENCE",
  "partial_reasons": ["LOG_DROP_PRESENT"],
  "warnings": [
    {
      "type": "EXCESSIVE_CUMULATIVE_DROPS",
      "message": "Session dropped 15,000 events (evidence quality suspect)",
      "total_drops": 15000,
      "log_drop_events": 120
    }
  ]
}
```

**Warning vs. Error:**

- Warning: Evidence exists but quality is degraded
- Error: Evidence is invalid or tampered

---

## 6. Auditor Talking Points

**Question:** "Can an attacker flood your system with LOG_DROP events?"

**Answer:**

- "Ingestion service enforces per-session and per-minute rate limits"
- "Excessive drops downgrade evidence classification, not system stability"
- "DoS protection is operational (quotas), not protocol-level"

**Question:** "How do you know LOG_DROP events are legitimate?"

**Answer:**

- "We don't. SDK is untrusted."
- "LOG_DROP events are _forensically visible_, not _cryptographically proven_"
- "System goal: detect data loss, not prevent SDK misbehavior"

**Question:** "What's an acceptable drop rate?"

**Answer:**

- "Context-dependent. We provide warnings, not rejections."
- "Recommended limit: 100 LOG_DROP events, 10,000 cumulative drops"
- "Auditors can set stricter policies via verifier flags (future)"

---

## 7. Implementation Checklist

When implementing LOG_DROP abuse prevention:

- [ ] Add per-session LOG_DROP counter to ingestion service
- [ ] Implement rate limiting (events per minute)
- [ ] Add cumulative drop threshold to verifier
- [ ] Emit warnings (not errors) for excessive drops
- [ ] Document SDK best practices for drop coalescing
- [ ] Add `--reject-excessive-drops` policy flag (future)
- [ ] Add test vectors for edge cases (100+ LOG_DROPs)

---

**Status:** EXPLICIT NON-GOAL (DoS via LOG_DROP)  
**Mitigation:** Operational (rate limiting), not protocol  
**Effective:** EVENT_LOG_SPEC v0.6+
