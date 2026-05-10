# AgentOps Replay — Formal Trust Model
# Version: 1.0
# Status: Stable
# Last Updated: May 2026
# This document is the authoritative specification of what AgentOps Replay
# guarantees, under what assumptions, and where its boundaries lie.
# Every claim in the arXiv preprint must be traceable to a section here.

---

## OVERVIEW

AgentOps Replay provides **behavioral event sequence integrity** for AI agent
sessions. This document defines precisely what that means: the trust assumptions
required, the guarantees provided, the attacks defended against, the attacks
not defended against, and the epistemic boundaries of each evidence class.

This document answers the following questions formally:
1. What does AUTHORITATIVE_EVIDENCE actually guarantee?
2. What trust assumptions does each evidence class require?
3. What attacks remain unsolved in v1.0?
4. What are the liveness assumptions?
5. What if the Ingestion Service is Byzantine?
6. What if event suppression occurs pre-capture?
7. What if clock manipulation occurs?
8. What are the replay attack assumptions?

---

## SECTION 1: PRINCIPALS AND TRUST LEVELS

AgentOps Replay defines three principals. Each operates in a distinct trust
domain with a distinct level of privilege.

### 1.1 The SDK (Untrusted)

**Definition:** The AgentOps SDK runs inside the agent process. It shares
memory space, file handles, and execution context with the agent being observed.

**Trust level:** Untrusted.

**Rationale:** Any component running in the agent process must be considered
potentially compromised. The agent process may be adversarially controlled
(adversary A1). The SDK's outputs — the events it produces — are self-reported
by the process under observation.

**What the SDK can do:** Produce SDK-authority events (SESSION_START,
SESSION_END, LLM_CALL, LLM_RESPONSE, TOOL_CALL, TOOL_RESULT, TOOL_ERROR,
LOG_DROP). Hash event payloads. Build the hash chain. Output JSONL locally
or send to the Ingestion Service.

**What the SDK cannot do:** Produce server-authority events (CHAIN_SEAL,
CHAIN_BROKEN, REDACTION, FORENSIC_FREEZE). Verify its own output — the SDK
is not the Verifier.

**Invariant SDK-1:** The SDK must never produce a server-authority event.
Any attempt to record EventType.CHAIN_SEAL results in a LOG_DROP event
instead. This invariant is enforced at the type level in EventType.is_sdk_authority.

### 1.2 The Ingestion Service (Trusted-Verify)

**Definition:** The Ingestion Service is a separate process, separate memory
space, and separate executable from the agent process. It receives events from
the SDK over HTTP, independently recomputes the hash chain, and stores events
in an append-only PostgreSQL database.

**Trust level:** Trusted-Verify.

**Rationale:** The Ingestion Service is assumed to be honest and correctly
implemented. It is not assumed to be Byzantine-fault-tolerant (see Section 4.4).
Its independence from the agent process is the source of the AUTHORITATIVE
upgrade over NON_AUTHORITATIVE.

**What the Ingestion Service can do:** Receive event batches. Independently
recompute event hashes using the same JCS+SHA-256 algorithm. Accept or reject
batches based on hash validity. Produce server-authority events (CHAIN_SEAL on
SESSION_END, CHAIN_BROKEN on sequence gap detection). Store events in an
append-only database. Sign CHAIN_SEAL with HMAC-SHA256.

**What the Ingestion Service cannot do:** Modify SDK-produced events after
acceptance. Delete events (database permission enforcement: agentops_app has
SELECT+INSERT only; no UPDATE, no DELETE). Produce SDK-authority events.

**Invariant IS-1:** The Ingestion Service must independently recompute every
event hash. It must not trust the event_hash field sent by the SDK. The SDK-
provided hash is silently ignored; the server computes its own.

**Invariant IS-2:** Batch persistence is atomic. Either all events in a batch
are persisted or none are. Partial writes are rejected.

### 1.3 The Verifier (Independent)

**Definition:** The Verifier is a standalone command-line tool with zero
external dependencies beyond Python 3.11 stdlib. It can run on any machine,
including air-gapped machines, without network access, without database access,
and without any connection to either the SDK or the Ingestion Service.

**Trust level:** Independent.

**Rationale:** The Verifier's independence is its core property. It trusts
nothing. It reads a JSONL file, recomputes every hash from scratch using JCS
+SHA-256, and reports a result. Its output is deterministic: the same input
always produces the same output on any Python 3.11+ machine.

**What the Verifier can do:** Recompute the full hash chain independently.
Determine evidence class from the event types present. Verify CHAIN_SEAL HMAC
when a key is provided. Report PASS/FAIL with structured JSON output including
trust_assumptions. Exit with POSIX codes 0 (PASS), 1 (FAIL), 2 (ERROR).

**What the Verifier cannot do:** Access the Ingestion Service database to
cross-check stored events. Verify that all events were captured (it only sees
what is in the file). Verify the freshness of a session (it does not check
whether the session is recent or has been replayed).

---

## SECTION 2: EVIDENCE CLASSES — FORMAL DEFINITIONS

### 2.1 NON_AUTHORITATIVE_EVIDENCE

**Formal definition:** A session has NON_AUTHORITATIVE_EVIDENCE if and only if:
- The JSONL passes all four Verifier checks (structural validity, sequence
  integrity, hash chain integrity, session completeness), AND
- No CHAIN_SEAL event is present in the session

**What this guarantees:**
- The event sequence is complete with no gaps (or gaps are explicitly
  recorded as LOG_DROP events)
- No event was inserted, deleted, or reordered after the session was written
  (modulo the A5 boundary condition — see Section 4.5)
- The hash chain is internally consistent
- The evidence was produced by the same process that contains the agent

**What this does NOT guarantee:**
- Independent verification of any kind
- That the producing process was not compromised
- That events were not suppressed before capture (pre-capture suppression)
- That the content of events reflects what the agent actually did vs. what
  it wanted the logger to record

**Trust assumptions required:**
- trust_assumptions.ingestion_service_honest: NOT APPLICABLE (no server used)
- trust_assumptions.hmac_key_uncompromised: NOT APPLICABLE
- trust_assumptions.sdk_process_uncompromised: REQUIRED (self-reported)

**Analogy:** A witness statement. The witness reports what they observed.
The statement may be accurate. No independent party has corroborated it.

### 2.2 AUTHORITATIVE_EVIDENCE

**Formal definition:** A session has AUTHORITATIVE_EVIDENCE if and only if:
- The JSONL passes all four Verifier checks, AND
- A CHAIN_SEAL event is present, AND
- No LOG_DROP events are present, AND
- (If --hmac-key is provided) the CHAIN_SEAL HMAC is valid

**What this guarantees:**
- Everything guaranteed by NON_AUTHORITATIVE_EVIDENCE, PLUS:
- An independent process (the Ingestion Service) received the events,
  independently recomputed the hash chain, found it valid, and sealed it
- The seal's origin can be verified with HMAC-SHA256 (with key)
- The database storing the events enforces append-only constraints at the
  permission level (no UPDATE or DELETE possible for agentops_app)

**What this does NOT guarantee:**
- That the Ingestion Service itself is honest (Byzantine server — Section 4.4)
- That the HMAC key is uncompromised (Section 4.6)
- That all events were captured (if no LOG_DROP, capture was complete
  per the SDK's observation — not per external ground truth)
- That the session is fresh (replay attacks — Section 4.7)
- That pre-capture suppression did not occur (Section 4.3)

**Trust assumptions required:**
- trust_assumptions.ingestion_service_honest: REQUIRED
- trust_assumptions.hmac_key_uncompromised: REQUIRED (when HMAC used)
- trust_assumptions.append_only_db_enforced: REQUIRED

**Analogy:** A notarized statement. An independent notary received the
witness statement, verified its internal consistency, and sealed it.
The notary is trusted to be honest. If the notary is corrupt, the seal
means nothing.

### 2.3 SIGNED_AUTHORITATIVE_EVIDENCE

**Formal definition:** All conditions for AUTHORITATIVE_EVIDENCE, AND:
- The CHAIN_SEAL HMAC is present and verified against the provided key

**Additional guarantee beyond AUTHORITATIVE_EVIDENCE:**
- The CHAIN_SEAL was produced by an entity that holds the HMAC key —
  i.e., the seal's origin is cryptographically attested, not just claimed
- A forged CHAIN_SEAL (added by an adversary with write access to the JSONL)
  will be detected if the adversary does not know the HMAC key

**What SIGNED_AUTHORITATIVE_EVIDENCE does NOT provide:**
- Non-repudiation (HMAC is symmetric — both the server and any key holder
  can produce a valid HMAC; only asymmetric signing provides non-repudiation)
- Public verifiability without the key
- Defense against a compromised key

**Path to stronger guarantee (v1.1):**
ECDSA signing with a published public key in a transparency log would upgrade
SIGNED_AUTHORITATIVE_EVIDENCE to NON_REPUDIABLE_EVIDENCE. The server signs
with a private key; anyone with the public key (published, auditable) can
verify. This removes the symmetric key sharing requirement.

### 2.4 PARTIAL_AUTHORITATIVE_EVIDENCE

**Formal definition:** A session has PARTIAL_AUTHORITATIVE_EVIDENCE if and
only if:
- A CHAIN_SEAL event is present, AND
- One or more LOG_DROP events are present

**What this guarantees:**
- The events that were captured are verified (same as AUTHORITATIVE for the
  captured portion)
- The gaps in capture are explicitly recorded (LOG_DROP with seq_range_start,
  seq_range_end, count, reason)
- The gap metadata itself is part of the hash chain — the gap record is
  tamper-evident

**What this does NOT guarantee:**
- Completeness — by definition, some events were not captured
- The content of the dropped events — only that a gap of N events at seq M
  through N occurred for a stated reason

---

## SECTION 3: WHAT IS PROVEN (AND WHAT IS NOT)

### 3.1 What AgentOps Replay proves

AgentOps Replay proves **behavioral sequence integrity**: the structure and
ordering of agent behavior events, not their content.

Specifically, a PASS result proves:

1. **Completeness (structural):** The event sequence has no unexplained gaps.
   Every seq number from 1 to N is present. If gaps exist, they are explicitly
   recorded as LOG_DROP events with their range and reason.

2. **Ordering (cryptographic):** The hash chain proves that event at seq=N
   was recorded after event at seq=N-1. Reordering any two events breaks the
   chain. This is cryptographic ordering, not timestamp-based ordering.
   Timestamp manipulation does not affect this guarantee (see Section 4.8).

3. **Integrity (hash chain):** No event payload, event type, session ID,
   sequence number, or timestamp was modified after the session was recorded.
   Any modification changes the JCS canonical form, changes the SHA-256 hash,
   and breaks the chain at the modification point.

4. **Attribution (structural):** The agent_id field in SESSION_START was set
   at session creation time and is covered by the hash chain. It cannot be
   changed post-hoc without breaking the chain.

### 3.2 What AgentOps Replay does NOT prove

1. **Content:** Prompt content, response content, tool arguments, and tool
   results are stored as SHA-256 hashes only. A PASS result proves these hashes
   are unmodified; it does not reconstruct what was said or what the tool did.

2. **Completeness (ground truth):** A PASS result with no LOG_DROP proves that
   everything the SDK captured is intact. It does not prove that everything the
   agent did was captured. Events that were never instrumented are invisible.

3. **Correctness:** AgentOps Replay does not evaluate whether the agent's
   actions were correct, appropriate, or safe — only that they were recorded
   with integrity.

4. **Causality:** The hash chain proves temporal ordering within a session.
   It does not prove that event A caused event B, or that an LLM response at
   seq=5 was produced by the specific LLM call at seq=4.

5. **External effects:** TOOL_CALL events record that a tool was called with
   certain arguments (hashed). They do not record what the tool actually did
   in the external system. The external effect is outside the chain.

6. **Cross-session lineage (v1.0):** The parent_session_id field in
   SESSION_START records which session spawned this one. The Verifier does not
   cross-check parent sessions — each session is verified independently.

---

## SECTION 4: THREAT MODEL AND ATTACK BOUNDARIES

### 4.1 Adversary A1 — Compromised SDK / Agent Process

**Attack:** The agent process is adversarially controlled. The SDK is modified
to inject false events into the session.

**Detected by:** Yes, in server-authority mode. The Ingestion Service
independently recomputes every event hash using the same JCS+SHA-256 algorithm.
A false event injected by a compromised SDK will have a hash computed by the
attacker that does not match the server's independent computation. The server
rejects the batch.

**In local-authority mode:** Partial detection. A compromised SDK that modifies
events after hashing (but before writing to JSONL) can produce internally
consistent fake events. The Verifier cannot distinguish these from genuine
events because it trusts the JSONL's hash chain, not an independent source.

**Empirical result:** test_a1_injected_event_detected — PASS (detected in
server-authority equivalent test where hash is not recomputed by attacker).

**Residual risk:** A sophisticated compromised SDK that knows JCS and
recomputes hashes correctly can produce a valid fake chain in local-authority
mode. This is adversary A5 (see Section 4.5).

### 4.2 Adversary A2 — MITM Between SDK and Ingestion Service

**Attack:** An attacker intercepts HTTP traffic between SDK and Ingestion
Service and modifies event payloads in transit.

**Detected by:** Yes. The Ingestion Service ignores the SDK-provided event_hash
and recomputes independently. A MITM that modifies a payload cannot also produce
a valid hash without knowing JCS. The server's independent computation will not
match the modified payload, and the batch is rejected.

**Note:** TLS (HTTPS) for the Ingestion Service endpoint makes this attack
require active certificate compromise. The hash chain provides defense-in-depth
even without TLS.

**Empirical result:** test_a2_payload_tampered_in_transit — PASS (detected).

### 4.3 Adversary A3 — Compromised Storage / Event Deletion

**Attack:** An attacker with access to the JSONL file or the database deletes
events to hide agent behavior (e.g., removes a TOOL_CALL that violated policy).

**Detected by:** Yes. Deleting any event creates a sequence gap (seq numbers
are not contiguous). The Verifier reports FAIL at the sequence_integrity check.
In the database, append-only constraints (agentops_app has no DELETE privilege)
prevent deletion at the permission level.

**Empirical result:** test_a3_events_deleted_from_storage — PASS (detected).

### 4.4 Adversary A4 — Insider Threat / Event Reordering

**Attack:** A legitimate administrator with file or database access reorders
events to change the apparent sequence of agent actions.

**Detected by:** Yes. Reordering breaks the hash chain because prev_hash[N]
= event_hash[N-1]. Swapping events N and N+1 makes event N's prev_hash point
to the wrong predecessor. The Verifier reports FAIL at hash_chain_integrity.

**Empirical result:** test_a4_event_reordering_detected — PASS (detected).

### 4.5 Adversary A5 — Full Chain Rewrite (Known Limitation)

**Attack:** A sophisticated adversary who knows the JCS+SHA-256 algorithm
has write access to the JSONL file and rewrites the entire hash chain with
modified events, producing a valid chain that the Verifier cannot distinguish
from the original.

**Detected by:**
- **In local-authority mode (NON_AUTHORITATIVE_EVIDENCE):** NOT DETECTED.
  This is a known architectural boundary. If the attacker knows JCS and can
  rewrite the full chain, the Verifier cannot detect the attack because the
  chain is internally consistent. The evidence class NON_AUTHORITATIVE_EVIDENCE
  explicitly acknowledges this limit.
- **In server-authority mode with CHAIN_SEAL HMAC:** DETECTED. The attacker
  must also forge the CHAIN_SEAL HMAC, which requires knowing the HMAC key.
  Without the key, they cannot produce a valid HMAC for the rewritten chain's
  final_hash.

**Empirical result:** test_a5_full_chain_rewrite — documents this boundary.
Original chain PASS (chain is valid). Rewritten chain without HMAC check:
PASS (known limitation). Rewritten chain with HMAC check: FAIL (detected).

**Mitigation path:**
- v1.0: CHAIN_SEAL HMAC-SHA256 (symmetric key) — detects A5 in server-authority
  mode when key is not compromised
- v1.1: CHAIN_SEAL ECDSA signing with published public key — detects A5 without
  requiring key sharing, with non-repudiation

**Honest statement:** No locally-produced (local_authority=True) session can
be defended against A5 without an independent verifier that saw the events at
capture time. This is an architectural property of the system, not a bug.

### 4.6 Byzantine Ingestion Service

**Attack:** The Ingestion Service is compromised. It accepts events, computes
correct hashes, emits a valid CHAIN_SEAL with valid HMAC, but also maintains
a shadow database where it stores modified events that it can serve to other
clients.

**Detected by:** NOT DETECTED in v1.0. The current system assumes the
Ingestion Service is honest (Trusted-Verify). A Byzantine server can produce
a valid CHAIN_SEAL for a modified event set.

**Why this is an architectural boundary, not a bug:**
Defending against a Byzantine Ingestion Service requires either:
(a) Multiple independent Ingestion Services with Byzantine agreement (e.g.,
    PBFT or similar BFT protocol), or
(b) A transparency log (e.g., Certificate Transparency style) where the
    server's commitments are publicly auditable and equivocation is detectable

Both are out of scope for v1.0. The system document (CONSTITUTION.md) scopes
the system to defend against external adversaries, not a compromised server.

**Trust assumption:** trust_assumptions.ingestion_service_honest = true is
a precondition for AUTHORITATIVE_EVIDENCE meaning anything stronger than
NON_AUTHORITATIVE_EVIDENCE.

**Mitigation path (v2.0):** Append-only transparency log. The Ingestion
Service publishes a commitment (hash of the session's final_hash) to a
public append-only log. Third parties can verify that the CHAIN_SEAL the
server produced matches the publicly committed value.

### 4.7 Pre-Capture Event Suppression

**Attack:** The agent takes an action (e.g., calls a sensitive tool) that is
never instrumented and therefore never appears in the hash chain. The audit
record is complete for what was captured but incomplete relative to what the
agent actually did.

**Detected by:** NOT DETECTED. The Verifier cannot see what it was not shown.
If an event was never passed to the SDK, no LOG_DROP is emitted (LOG_DROP
covers capture failures, not instrumentation gaps). The chain will PASS while
missing the suppressed event entirely.

**Honest framing:** This is the instrumentation completeness problem. It is
shared by every observability system including Terrarium, LangSmith, and all
distributed tracing tools. There is no cryptographic solution to the problem
of events that were never captured. The only mitigations are:
(a) Comprehensive instrumentation (instrument every agent action)
(b) Independent side-channel verification (verify tool invocations at the
    infrastructure level, e.g., API gateway logs)
(c) Formal instrumentation completeness proofs (out of scope for v1.0)

**Trust assumption:** trust_assumptions.instrumentation_complete = "unknown"
in all evidence classes. This field is always "unknown" because the Verifier
cannot determine whether all agent actions were instrumented.

### 4.8 Clock Manipulation

**Attack:** The agent process or a network adversary manipulates timestamps
on events to create false impressions of timing or ordering.

**Detected by:** NOT RELEVANT to ordering guarantees. AgentOps Replay's
ordering guarantee is cryptographic, not timestamp-based. The hash chain
prev_hash[N] = event_hash[N-1] proves ordering regardless of timestamps.
Manipulated timestamps produce wrong timestamps but do not affect chain
integrity or verifiability.

**What timestamp manipulation CAN affect:**
- Human interpretation of "when" events occurred
- Time-based compliance rules (e.g., "response within 500ms") that use
  the recorded timestamp rather than independent measurement

**Design decision:** Timestamps are informational metadata, not security
inputs. The hash chain is the ordering proof. This is a deliberate design
choice — it eliminates the need for trusted time sources and NTP security
as preconditions for chain integrity.

### 4.9 Replay Attacks

**Attack:** A valid historical JSONL is submitted to the Verifier, which
reports PASS. The attacker presents a valid-but-stale session as evidence
of a recent event that never occurred.

**Detected by:** NOT DETECTED in v1.0. The Verifier checks integrity and
completeness, not freshness. A session from six months ago with a valid chain
will report PASS with the same evidence class as a session from today.

**Mitigation:**
- For forensic use: include a FORENSIC_FREEZE server event at investigation
  time, which timestamps the freeze in the chain and prevents the "this
  session is current" claim
- For real-time verification: require the SESSION_START timestamp to be within
  a defined window (application-level check, not Verifier-level)
- v1.1: nonce-based session binding (a challenge nonce in SESSION_START
  prevents replay of a session with a different nonce)

**Trust assumption:** trust_assumptions.session_is_fresh = "not_checked" in
all evidence classes. Freshness verification requires application-level context
that the Verifier does not have.

---

## SECTION 5: LIVENESS ASSUMPTIONS

The system makes the following liveness assumptions. If these do not hold, the
system degrades gracefully rather than failing catastrophically.

### 5.1 SDK Liveness

**Assumption:** The SDK can write to a local buffer (memory) at event capture
time.

**What happens if violated:** If the buffer is full, LOG_DROP is emitted.
If the buffer itself cannot be written (out of memory), the SDK must not crash
the agent process. The SDK is designed fail-open: it records what it can and
emits LOG_DROP for what it cannot.

**Degradation:** Evidence class degrades from AUTHORITATIVE or NON_AUTHORITATIVE
to PARTIAL_AUTHORITATIVE.

### 5.2 Ingestion Service Liveness

**Assumption:** The Ingestion Service is reachable over HTTP when the SDK calls
send_to_server().

**What happens if violated:** The SDK retries 3 times with exponential backoff
(1s, 2s, 4s). After 3 failures, it raises ConnectionError. The session remains
in the local buffer and can be flushed to JSONL for local-authority verification.

**Degradation:** Evidence class degrades from AUTHORITATIVE_EVIDENCE to
NON_AUTHORITATIVE_EVIDENCE. The session is not lost — it is verifiable locally.

### 5.3 Database Liveness

**Assumption:** PostgreSQL is writable when the Ingestion Service processes
a batch.

**What happens if violated:** The Ingestion Service rejects the batch atomically.
No partial writes. The SDK receives a 503 and retries. If retries exhaust, the
session falls back to local-authority mode.

**Degradation:** Same as Ingestion Service liveness violation.

### 5.4 Verifier Liveness

**Assumption:** Python 3.11+ is available.

**What happens if violated:** The Verifier cannot run. There is no degraded
mode — verification requires the Verifier. The JSONL can be retained and
verified when Python 3.11+ becomes available.

---

## SECTION 6: TRUST ASSUMPTIONS SUMMARY TABLE

| Assumption | NON_AUTH | AUTH | SIGNED_AUTH | PARTIAL_AUTH |
|---|---|---|---|---|
| SDK process uncompromised | REQUIRED | PARTIAL† | PARTIAL† | PARTIAL† |
| Ingestion Service honest | N/A | REQUIRED | REQUIRED | REQUIRED |
| HMAC key uncompromised | N/A | N/A | REQUIRED | N/A |
| Append-only DB enforced | N/A | REQUIRED | REQUIRED | REQUIRED |
| Instrumentation complete | UNKNOWN | UNKNOWN | UNKNOWN | KNOWN INCOMPLETE |
| Session is fresh | NOT CHECKED | NOT CHECKED | NOT CHECKED | NOT CHECKED |
| Clock is accurate | NOT REQUIRED | NOT REQUIRED | NOT REQUIRED | NOT REQUIRED |
| Byzantine server defense | NONE | NONE | NONE | NONE |

† PARTIAL: Server-authority mode provides independent verification that detects
  A1-A4 attacks. A5 (full chain rewrite by attacker who knows JCS) is detected
  only with HMAC key in SIGNED_AUTHORITATIVE mode.

---

## SECTION 7: COMPARISON TO RELATED WORK

### 7.1 vs. Terrarium (arXiv:2510.14312)

Terrarium provides no trust model. Its logging infrastructure (src/logger.py)
has zero cryptographic integrity mechanisms — confirmed by grep -rn "hashlib|
sha256" src/ returning no cryptographic results. Terrarium makes no claims
about the integrity of its released logs. AgentOps Replay provides the formal
trust layer that Terrarium's reproducibility commitment implicitly requires.

### 7.2 vs. Colosseum (arXiv:2602.15198)

Colosseum claims to produce "evidence of collusion." Evidence in a security
context requires chain of custody. Colosseum's interaction traces inherit
Terrarium's mutable log infrastructure — the evidence has no chain of custody.
AgentOps Replay provides AUTHORITATIVE_EVIDENCE for Colosseum's interaction
traces, making the audit framework's own evidence defensible.

### 7.3 vs. Blockchain / Distributed Ledger

Blockchain provides Byzantine-fault-tolerant append-only storage through
distributed consensus. AgentOps Replay's Ingestion Service + append-only
PostgreSQL is NOT Byzantine-fault-tolerant — it assumes an honest server.
The tradeoff is intentional: blockchain infrastructure is complex, high-latency,
and costly; AgentOps Replay targets the common case (honest infrastructure,
external adversaries) with low overhead (<3% runtime, <8.3ms median latency).

### 7.4 vs. Certificate Transparency

Certificate Transparency (RFC 6962) provides a transparency log where
certificate issuance is publicly auditable and equivocation (issuing two
different certificates for the same key) is detectable. AgentOps Replay v2.0
plans a similar mechanism: publishing CHAIN_SEAL commitments to a public
append-only log. This would address the Byzantine server attack (Section 4.6).

---

## SECTION 8: VERSION HISTORY OF FORMAL GUARANTEES

| Version | Evidence Classes | Signing | Byzantine Defense | Pre-Capture |
|---|---|---|---|---|
| v1.0 (current) | NON / PARTIAL / AUTH / SIGNED_AUTH | HMAC-SHA256 | None | None |
| v1.1 (planned) | + NON_REPUDIABLE | ECDSA + public key | None | None |
| v2.0 (research) | All v1.1 | ECDSA | Transparency log | Formal coverage proofs |

---

## SECTION 9: HOW TO CITE THIS DOCUMENT

When making claims about AgentOps Replay's guarantees in a paper or report,
cite the specific section of this document:

- "AgentOps Replay provides behavioral sequence integrity under the trust
  assumptions in docs/TRUST_MODEL.md §6"
- "The system defends against adversaries A1-A4 (docs/TRUST_MODEL.md §4.1-4.4)
  and documents A5 as a known boundary (§4.5)"
- "AUTHORITATIVE_EVIDENCE requires an honest Ingestion Service (§4.6) and does
  not provide freshness guarantees (§4.9)"

---

*This document was written in response to the following reviewer questions:*
*"Authoritative relative to what trust assumptions? What attacks remain unsolved?*
*What are the epistemic boundaries? What does CHAIN_SEAL actually guarantee?*
*What are the liveness assumptions? What if the Ingestion Service is Byzantine?*
*What if event suppression occurs pre-capture? What if clock manipulation happens?*
*What are the replay attack assumptions?"*
*Every question is answered in a numbered section above.*
