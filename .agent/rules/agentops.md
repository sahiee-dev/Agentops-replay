---
trigger: always_on
---

# AgentOps Replay Workspace Rules

These rules apply to all Agent behavior in this workspace.
They are strict and override default agent behavior.

## Product Identity and Direction

1. This repository implements AgentOps Replay.
2. AgentOps Replay is critical evidence infrastructure, not an observability tool.
3. The system is a system of record, not an analytics or UX product.
4. Evidence integrity, determinism, and verifiability are higher priority than performance or ergonomics.
5. Any change that weakens evidentiary guarantees is invalid by definition.

## Constitution First Development

6. Assume a constitution exists even if not fully implemented yet.
7. Any behavior that enables mutation, repair, inference, or silent loss of evidence is forbidden.
8. If a proposed change violates append-only semantics, reject it.
9. If a proposed change introduces non-determinism, reject it.
10. If a proposed change hides gaps, failures, or uncertainty, reject it.
11. When in doubt, fail loudly and preserve evidence of failure.

## Evidence Model Rules

12. Treat all SDK input as untrusted.
13. Never trust client-side hashes, ordering, timestamps, or authority claims.
14. All authoritative facts must be recomputed server-side.
15. Mixed authority event chains must be rejected.
16. SDK code must never emit server authority artifacts such as CHAIN_SEAL.
17. Redaction must preserve cryptographic integrity.
18. Chain-of-thought must never be stored by default.

## Bug Fixing in This Repo

19. Every bug is an evidence risk until proven otherwise.
20. Root cause analysis is mandatory.
21. Do not apply patches that merely suppress errors.
22. Never mask integrity violations to improve availability.
23. If the correct behavior is unclear, stop and state the ambiguity.
24. Prefer rejecting bad data over accepting questionable data.

## Architecture and Scope Control

25. Respect the trust boundaries defined in the PRD.
26. Do not blur SDK, ingestion, storage, verifier, or replay responsibilities.
27. Avoid introducing cross-layer coupling.
28. Do not add features that interpret intent or judge correctness.
29. Replay must remain read-only and non-inferential.

## Verifier Supremacy

30. Verifier correctness is the top priority in this workspace.
31. Any change that complicates verification must be justified explicitly.
32. The verifier must be deterministic, standalone, and paranoid.
33. Never add auto-repair or best-effort fixes to the verifier.
34. Invalid chains must remain invalid.

## Failure Semantics

35. Silent data loss is never acceptable.
36. All degradation must be visible post-hoc.
37. LOG_DROP and equivalent artifacts are mandatory for loss.
38. Failing closed for integrity is preferred over succeeding incorrectly.
39. Availability is secondary to evidence correctness.

## Open Source and PR Expectations

40. Changes must align with the project’s long-term direction as defined in the PRD.
41. Large refactors require architectural justification tied to evidence guarantees.
42. Minimal, high-confidence changes are preferred.
43. Avoid speculative features.
44. Avoid roadmap expansion unless explicitly requested.

## Documentation and Communication

45. Explanations must be precise and technical.
46. Avoid marketing language.
47. Avoid narrative interpretations of agent behavior.
48. Document what the system does, not what it intends.

## Token and Output Discipline

49. Prefer concise reasoning.
50. Do not restate the PRD unnecessarily.
51. Avoid verbose analysis unless correctness requires it.
52. Output only what is necessary to support the change.

## Absolute Prohibitions

53. Do not add dashboards as a primary feature.
54. Do not infer missing events.
55. Do not reorder events for UX.
56. Do not downgrade integrity for performance.
57. Do not weaken cryptographic guarantees for convenience.

End of workspace rules.
