# Regulatory Alignment — Informational Note

## What This Document Is

This note describes how AgentOps Replay's features relate to common AI
regulatory frameworks. It is informational only. It is not a compliance
certification, legal opinion, or assurance that using AgentOps Replay
satisfies any regulatory requirement in any jurisdiction.

---

## EU AI Act

Article 12 (Transparency and record-keeping for high-risk AI systems)
requires that high-risk AI systems be designed to ensure logging of
operations throughout their lifetime.

AgentOps Replay's AUTHORITATIVE_EVIDENCE chains provide tamper-evident
session logs that address the spirit of this requirement. Whether they
satisfy the specific technical annexes of the EU AI Act in a given
deployment context requires legal analysis.

---

## NIST AI RMF

The NIST AI Risk Management Framework is a voluntary framework. Mapping
to it does not constitute compliance with any law or regulation. AgentOps
Replay's evidence classification (AUTHORITATIVE / PARTIAL / NON_AUTHORITATIVE)
maps conceptually to the MEASURE function's risk quantification intent.

---

## ISO/IEC 42001

ISO/IEC 42001 certification requires third-party audit. No tool can
self-certify ISO/IEC 42001 compliance. AgentOps Replay's non-repudiation
properties (CHAIN_SEAL, append-only storage) are relevant to Clause 9.1
requirements, but formal certification requires an accredited auditor.

---

## What We Recommend

If you need compliance with a specific regulation, consult a qualified
legal or compliance professional. AgentOps Replay provides the technical
infrastructure; compliance determination is a separate assessment.
