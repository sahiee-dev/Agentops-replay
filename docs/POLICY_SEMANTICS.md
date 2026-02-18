# POLICY_SEMANTICS.md (v1.0)

> **Classification: AUTHORITATIVE. Policy evaluation behavior is governed by this document.**
> **Aligned with CONSTITUTION.md v1.0 and EVENT_LOG_SPEC.md v0.6.**

---

## 1. Purpose

This document defines the **evaluation contract** for the Policy Engine. It specifies what a policy is, how it is invoked, what it produces, and how its output relates to the immutable event chain.

---

## 2. Core Principle: Violations Are Derived Artifacts

**Violations are NOT primary evidence. They are derived artifacts computed over committed events.**

| Artifact Type | Mutable?         | Authority         | Trust Level   |
| ------------- | ---------------- | ----------------- | ------------- |
| Events        | No (append-only) | Ingestion Service | AUTHORITATIVE |
| Violations    | No (append-only) | Policy Engine     | DERIVED       |
| Policy Rules  | Yes (versioned)  | Configuration     | OPERATIONAL   |

A violation never modifies, annotates, or reinterprets the events it references. It is a separate record that points to events by `event_id`.

---

## 3. Evaluation Contract

### 3.1 Input

Policy evaluation receives a **committed, hash-chained event batch**. It MUST NOT run on uncommitted events.

```
Input: List[Event]  (already persisted, hashes verified)
```

### 3.2 Output

```python
@dataclass(frozen=True)
class ViolationRecord:
    id: UUID                        # Unique violation ID
    session_id: UUID                # Session that triggered the violation
    event_id: UUID                  # Specific event that triggered the violation
    event_sequence_number: int      # Immutable ordering anchor (NOT timestamp)
    policy_name: str                # e.g., "GDPR_PII_DETECTED"
    policy_version: str             # e.g., "1.0.0" — policy set semver
    policy_hash: str                # SHA-256(policy source + canonical config subset)
    severity: ViolationSeverity     # WARNING | ERROR | CRITICAL
    description: str                # Human-readable finding (factual, not inferential)
    metadata: dict                  # Policy-specific context (field_path, pattern_matched, etc.)
```

**Note:** The `created_at` field is set by the Worker at transaction commit time. It is NOT part of the policy output — it is a persistence-layer timestamp.

### 3.3 Determinism Requirement

**Given the same event batch and the same policy version, evaluation MUST produce identical violations.**

- No randomness.
- No external API calls.
- No dependency on wall clock (the `created_at` timestamp is persistence metadata, not evaluation logic).
- No dependency on other sessions or historical violations.
- Violations are anchored to `event_sequence_number` (immutable ordering), NOT timestamps.

### 3.4 Pure Function

```
evaluate(events: List[CanonicalEvent], policy_set: PolicySet) -> List[ViolationRecord]
```

This function:

- Has no side effects.
- Does not modify events.
- Does not access the database.
- Does not access the network.
- Returns a deterministic list.

Persistence is the caller's responsibility.

---

## 4. Transaction Semantics

### 4.1 Ordering

The Worker MUST follow this exact sequence:

```
1. Validate batch (schema, structure)
2. Persist events via IngestService (append-only, hash-chain extended)
3. Compute violations: PolicyEngine.evaluate(committed_events, active_policy_set)
4. Persist violations in the SAME database transaction as step 2
5. Single atomic COMMIT (events + violations)
6. XACK the Redis message (confirms processing complete)
```

### 4.2 Atomicity

**Events and their violations are committed atomically.**

- If event persistence succeeds but violation persistence fails → **ROLLBACK the entire batch**.
- If event persistence fails → violations are never computed.
- If policy evaluation raises an exception → **ROLLBACK the entire batch** (events included).
- Partial writes are forbidden (CONSTITUTION §4.2).

### 4.3 Failure Modes

| Failure                            | Behavior                         | Evidence                            |
| ---------------------------------- | -------------------------------- | ----------------------------------- |
| Event persist fails                | Batch rejected, NACK, retry      | Worker logs                         |
| Policy evaluation raises exception | **ROLLBACK events**, NACK, retry | Worker logs + DLQ after max retries |
| Violation persist fails            | **ROLLBACK events**, NACK, retry | Worker logs                         |
| Policy config missing/corrupt      | Worker refuses to start          | Startup log                         |

**No event may exist in the store without its corresponding policy evaluation having completed.** If re-evaluation is needed (policy bug discovered), it follows the Re-Evaluation Protocol in §6.

---

## 5. Policy Versioning

### 5.1 Policy Set Identity

Every policy evaluation records the active policy set:

```python
@dataclass(frozen=True)
class PolicySet:
    version: str        # Semantic version of policy.yaml
    config_hash: str    # SHA-256 of the canonicalized policy.yaml content
    policies: tuple[PolicyDescriptor, ...]

@dataclass(frozen=True)
class PolicyDescriptor:
    name: str           # "GDPR_PII_DETECTED"
    version: str        # "1.0.0"
    source_hash: str    # SHA-256 of the policy's evaluate() source code
    enabled: bool
```

### 5.2 policy_hash Construction

```
policy_hash = SHA-256(
    inspect.getsource(policy.evaluate)
    + "\n---\n"
    + json.dumps(policy_config_subset, sort_keys=True, separators=(",", ":"))
)
```

**This captures the full evaluation semantics:**

- Source code changes → hash changes.
- Configuration changes (e.g., `allowed_tools` list) → hash changes.
- The hash is deterministic given the same source + config.

### 5.3 Traceability

Every `Violation` record contains `policy_version` and `policy_hash` so that:

1. Any violation can be traced to the exact rule + config that generated it.
2. If a policy is updated, old violations remain attributable to the old version.
3. Compliance exports include the policy version active at evaluation time.

### 5.4 Policy Change Protocol

- Changing a policy rule or its configuration increments the policy set version.
- The new PolicySet identity is logged at Worker startup.
- Old violations are never re-evaluated or modified (append-only).
- If re-evaluation is desired, see §6.

---

## 6. Policy Upgrade Semantics

> **HARD INVARIANTS — These are non-negotiable.**

### 6.1 Historical Invariance

Violations are computed **at ingestion time** under a specific PolicySet identity. The following invariants MUST hold:

| #   | Invariant                                             | Rationale                                                        |
| --- | ----------------------------------------------------- | ---------------------------------------------------------------- |
| 1   | Old violations are NEVER mutated                      | Append-only. CONSTITUTION §2.                                    |
| 2   | Old violations are NEVER deleted                      | Derived artifacts are evidence of governance activity.           |
| 3   | Old violations are NEVER overwritten by re-evaluation | Historical record must reflect what was known at ingestion time. |
| 4   | Automatic retroactive recomputation is FORBIDDEN      | Policy upgrades apply to NEW events only.                        |
| 5   | No inference about what "would have been" detected    | The system records facts, not counterfactuals.                   |

### 6.2 Upgrade Scenario

```
Timeline:
  T1: Events A ingested under PolicySet v1.0.0 → Violations V1 created
  T2: Policy upgraded to v1.1.0 (adds new rule)
  T3: Events B ingested under PolicySet v1.1.0 → Violations V2 created
```

**At T3:**

- Events B are evaluated under v1.1.0. Correct.
- Events A retain their original violations V1. Correct.
- Events A are NOT re-evaluated under v1.1.0. Correct.
- V1 records `policy_version=1.0.0` and `policy_hash=<hash_at_T1>`. Correct.

### 6.3 Re-Evaluation Protocol

If re-evaluation is ever implemented (e.g., policy bug discovered, compliance audit), it MUST:

1. **Create new violation records** with a distinct `policy_version` and `policy_hash`.
2. **Never overwrite or modify** the original violations.
3. **Store a `re_evaluation_id`** linking the new violations to the re-evaluation batch.
4. **Log the re-evaluation event** including the reason, who triggered it, and the old/new PolicySet identities.
5. **Clearly mark** re-evaluated violations as `re-evaluation` in metadata to distinguish from ingestion-time violations.

```
# Re-evaluation violations are separate records:
Violation(
    policy_name="GDPR_PII_DETECTED",
    policy_version="1.1.0",           # New version
    policy_hash="<new_hash>",          # New hash
    metadata={"re_evaluation_id": "...", "original_policy_version": "1.0.0"},
)
```

### 6.4 Prohibited Patterns

| Pattern                                          | Why It's Prohibited                                     |
| ------------------------------------------------ | ------------------------------------------------------- |
| `UPDATE violations SET policy_version = '1.1.0'` | Retroactive mutation destroys audit trail               |
| Automatic nightly re-evaluation cron             | Creates historical drift without explicit authorization |
| "Backfill" that replaces old violations          | Same as mutation — forbidden                            |
| Skipping policy evaluation to improve throughput | Evidence without governance is incomplete               |

---

## 7. What Policies MUST NOT Do

Per CONSTITUTION.md:

1. **Must not modify events.** Policies are read-only observers.
2. **Must not infer intent.** A policy detects patterns, it does not judge decisions.
3. **Must not block ingestion.** Violations are records, not gates. Events are always persisted.
4. **Must not claim compliance.** A GDPR check is a heuristic scan, not a compliance certification.
5. **Must not introduce non-determinism.** Same input → same output.

---

## 8. Export Requirements

Compliance exports (JSON/PDF) MUST include:

- Active `policy_set_version` at time of evaluation.
- Number of violations per severity level.
- Full violation details with `policy_hash` for each.
- Disclaimer: "Policy findings are heuristic. They do not constitute compliance certification."

---

_POLICY_SEMANTICS.md v1.1 — Aligned with CONSTITUTION.md v1.0. Added §6 Policy Upgrade Semantics._
