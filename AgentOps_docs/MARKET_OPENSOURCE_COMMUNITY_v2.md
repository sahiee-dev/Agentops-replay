# AgentOps Replay — Open-Source Community Market Document (v2)
## Adoption Strategy Targeting OpenClaw / Clawdbot / Moltbot Users

> **Document Type:** Community Adoption Strategy + Integration Requirements
> **Audience:** You (the builder), OSS community contributors
> **Companion:** Enterprise Security Document, Research Document
> **Last Updated:** May 2026

---

## Section 1: The Target User — Who They Are and What They're Running

### 1.1 OpenClaw: The Primary Target

The software your users called "openclaw," "clawdbot," and "moltbot" are all the same product. OpenClaw (formerly Clawdbot, formerly Moltbot, nicknamed "Molty") is a single open-source personal AI agent created by Austrian developer Peter Steinberger. It launched in November 2025 under the name Clawdbot, went viral, and now has 68,000+ GitHub stars — one of the fastest-growing open-source repositories in GitHub history.

This is your primary community target. OpenClaw users are exactly the people AgentOps Replay is built for.

### 1.2 What OpenClaw Does (And Why It's a Perfect Fit)

OpenClaw is a self-hosted gateway that connects LLM models (Claude, Gemini, GPT) to the messaging apps users already use — WhatsApp, Telegram, Slack, Discord, Signal, iMessage — and lets the agent act on their behalf: running shell commands, managing files, browsing the web, reading email, executing calendar operations, and interacting with financial services like Stripe.

It runs locally. It has full system access. It operates on a heartbeat scheduler — it wakes up autonomously, even overnight, and takes actions without being prompted.

The users running this are technically sophisticated. They understand Docker, can write Python, and chose self-hosting deliberately because they want control and privacy.

What they have not built — and what OpenClaw does not provide — is any way to prove what their agent did, in what order, and that the record hasn't been modified.

### 1.3 The Name History (Important for Community Messaging)

When talking to this community, you need to know all the names:

| Name | Period | Notes |
|---|---|---|
| Clawd / Molty | Original prototype | Peter Steinberger's internal name, derived from "Claude" |
| Clawdbot | November 2025 launch | Original public name on GitHub |
| Moltbot | Brief rename | Same software |
| OpenClaw | Current (2026) | Final name, 68K+ stars |

Community members may use any of these names interchangeably. They all refer to the same software. Acknowledging all three in your documentation and README will signal that you know this community.

---

## Section 2: The Accountability Gap in OpenClaw (Documented, Specific, Real)

This section is the core of your value proposition to OpenClaw users. Every claim here is sourced from OpenClaw's own documentation or published security research.

### 2.1 OpenClaw's Own Logging: What It Provides

OpenClaw does have logging. It writes three types of logs by default:
- Session transcripts at `~/.openclaw/agents/<agentId>/sessions/*.jsonl` — every conversation turn, tool invocation, and agent response
- Cron execution logs at `~/.openclaw/agents/<agentId>/cron/runs/` — scheduled task outputs
- A built-in `openclaw security audit` command that checks configuration risks

This sounds reasonable. The problem is structural, not cosmetic.

### 2.2 The Structural Problem: Mutable, Local, Deletable

OpenClaw's own compliance documentation states it explicitly: **"Default OpenClaw logging writes to local files that can be modified or deleted by anyone with shell access."**

This is not a bug — it is a design choice appropriate for a personal tool. But it means:

1. **No tamper evidence.** Any process or user with filesystem access to `~/.openclaw/` can modify or delete session transcripts. There is no way to prove a log hasn't been altered.

2. **SOC 2 disqualifying.** The SFAI Labs compliance analysis found that local-only logging fails three of five SOC 2 Common Criteria related to monitoring (CC7.2 requires centralized monitoring; local logs don't satisfy it).

3. **No evidence class.** A session transcript and an evidence chain are different things. OpenClaw produces the former. There is no mechanism to produce the latter.

### 2.3 The Compliance Analysis Finding

An independent security maturity analysis of OpenClaw's April 2026 security upgrades (covering 3.23 to 4.12 release block) concluded:

> "OpenClaw's patches are engineering-grade vulnerability management. They do not produce compliance evidence. There is no immutable audit log with risk scores, no authorization attribution per action, no policy conformance reporting, and no SIEM integration."

This is the gap AgentOps Replay fills. Not vulnerability management — that's OpenClaw's job. Evidence production — that's AgentOps Replay's job.

### 2.4 The CVE Record: Real Incidents Prove the Need

OpenClaw has had real security incidents that directly illustrate why tamper-evident logs matter:

**CVE-2026-25253 (January 2026):** A 1-click account takeover to full RCE vulnerability. Security firm Ethiack's autonomous AI pentester found it in under 2 hours. An attacker could take control of the OpenClaw Gateway without any human interaction by crafting a URL that the user's browser would open. The vulnerability was patched in the January 28, 2026 commit, but any OpenClaw instance running a version before 2026.1.29 was vulnerable.

**What this means for accountability:** When CVE-2026-25253 was exploited, an attacker with RCE on the host could modify or delete the `~/.openclaw/sessions/*.jsonl` files. The user would have no way to know what the agent did during the compromise period, or whether the logs they were looking at were the original ones.

**Additional advisories (March 2026):** Session transcript files created without forced user-only permissions, Telegram bot tokens exposed in log file URLs, unsanitized attachment paths enabling command injection. Each of these represents a scenario where the user's audit record could be compromised alongside the agent.

A comprehensive taxonomy study from Texas A&M University analyzed 190 security advisories filed against OpenClaw. Their core finding: because the model's output is itself a control signal (a tool call instructs the runtime to execute a shell command), the attack surface includes not just implementation bugs but the model's susceptibility to adversarial influence through any data path that reaches its context window.

**The implication:** In a system where prompt injection can cause the agent to execute shell commands, a tamper-evident log becomes forensic evidence — not just a debug aid.

### 2.5 The Specific Gap AgentOps Replay Fills

| What OpenClaw Provides | What AgentOps Replay Adds |
|---|---|
| Local JSONL session transcripts | Hash-chained JSONL with cryptographic integrity |
| `openclaw security audit` (configuration scan) | Independent verifier (any party can run it) |
| Filesystem-local logs (deletable) | Ingestion service with append-only storage |
| No evidence classification | AUTHORITATIVE / PARTIAL / NON_AUTHORITATIVE evidence classes |
| No tamper detection | Any modification invalidates the chain |
| No SIEM integration (built-in) | CHAIN_SEAL events suitable for SIEM ingestion (v1.1) |

The key phrase from the compliance analysis is worth repeating: OpenClaw does **engineering-grade vulnerability management**. AgentOps Replay does **evidence production**. These are complementary, not competing.

---

## Section 3: How the Integration Works

### 3.1 The OpenClaw AgentSkill Integration Path

OpenClaw supports over 100 preconfigured AgentSkills — portable, community-extensible capabilities the agent can load. This is the natural integration point: an **AgentOps Replay AgentSkill** that automatically instruments every OpenClaw session.

**How it works:**
```
OpenClaw Agent (running locally)
    ↓
AgentOps Replay AgentSkill (interceptor, runs in-process)
    ↓
Option A: flush_to_jsonl → ~/.openclaw/agentops/<session_id>.jsonl
Option B: send_to_server → local AgentOps Ingestion Service (Docker)
    ↓
agentops-verify <session>.jsonl → PASS ✅ + evidence class
```

**What gets captured automatically:**
- Every LLM call (model, prompt hash, token count — never raw prompt content)
- Every tool invocation (tool name, args hash — never raw args)
- Every tool result (result hash — never raw result content)
- Session start/end with agent version, model ID, tool list
- Any LOG_DROP if the session had high event volume

**What users get:**
- A cryptographically verifiable JSONL for every OpenClaw session
- The ability to run `agentops-verify session.jsonl` and see PASS ✅
- In server mode: AUTHORITATIVE_EVIDENCE with CHAIN_SEAL

### 3.2 Why This Requires Zero Code Changes from OpenClaw Users

OpenClaw's AgentSkill format allows skills to hook into the agent's execution lifecycle. An AgentOps Replay skill would:
1. Intercept the session start → emit SESSION_START
2. Intercept each LLM call → emit LLM_CALL
3. Intercept each LLM response → emit LLM_RESPONSE
4. Intercept each tool invocation → emit TOOL_CALL + TOOL_RESULT/TOOL_ERROR
5. Intercept session end → emit SESSION_END

The user installs the skill once. Every subsequent session is automatically recorded.

**Target UX:**
```bash
openclaw skill install agentops-replay
# Done. All sessions now produce cryptographically verifiable logs.
```

### 3.3 Privacy-First by Design (Critical for This Community)

OpenClaw users chose self-hosting precisely because they don't trust cloud providers. The integration must respect this:

- **Local authority mode (default):** Nothing leaves the machine. The JSONL file stays in `~/.openclaw/agentops/`. The AgentOps Ingestion Service is optional.
- **Content never stored verbatim:** LLM prompts, responses, tool arguments, and results are stored as SHA-256 hashes only. The actual content never appears in the AgentOps log.
- **Zero cloud dependency:** The verifier has zero external dependencies. It runs without network access. No account required.
- **User controls everything:** Users choose whether to run the local Ingestion Service, which directory logs go to, and whether to use server mode.

This must be stated clearly in the README and in any community posts: *"AgentOps Replay stores hashes and metadata, not content. Your prompts, responses, and file contents never leave your machine."*

---

## Section 4: The User Who Needs This Most

### 4.1 The "Car Negotiation" Use Case

A known OpenClaw community story: a developer named AJ Stuyvenberg tasked his OpenClaw with buying a 2026 Hyundai Palisade. The agent scraped local dealer inventories, filled out contact forms using his phone number and email, then spent several days playing dealers against each other — forwarding competing PDF quotes and asking each to beat the other's price. He saved $4,200 while sleeping.

This is exactly the use case that needs AgentOps Replay. The agent:
- Sent emails on his behalf (tool calls)
- Accessed dealer websites (browser automation)
- Made decisions without human approval at each step
- Ran for several days with no human supervision

If anything had gone wrong — the wrong email sent, an unintended commitment made, a form filled with incorrect information — he would have had no cryptographic proof of what the agent actually did, in what sequence, and whether anyone had modified the log afterward.

AgentOps Replay gives him that proof.

### 4.2 The Power User Segment

OpenClaw's community includes users running agents that:
- Manage financial workflows (Stripe integrations, invoice processing)
- Access Gmail and calendar (reading, writing, scheduling)
- Execute shell commands and manage filesystems
- Operate on multi-day heartbeat schedules without human oversight
- Automate business workflows across APIs

These are not toy applications. These are autonomous agents with real access to real systems. The users running these are exactly the ones who will eventually ask: "What did my agent actually do last Tuesday? And can I prove it?"

### 4.3 The NVIDIA NemoClaw Signal

NVIDIA has built NemoClaw — an open-source stack that adds privacy and security controls to OpenClaw. It uses NVIDIA OpenShell to enforce policy-based guardrails. The fact that NVIDIA invested engineering resources into hardening OpenClaw tells you something important: there is institutional recognition that OpenClaw's security model needs extension.

NemoClaw adds guardrails (what the agent is *allowed* to do). AgentOps Replay adds evidence (what the agent *actually did*). These are complementary. NemoClaw is not a competitor — it's a validation that enterprise-grade users want accountability infrastructure around OpenClaw.

---

## Section 5: Community Adoption Strategy

### 5.1 The GitHub Strategy

**The hook message for the OpenClaw community:**

> "Your OpenClaw agent has full access to your files, email, shell, and financial accounts. When something goes wrong — and it will, eventually — will you be able to prove exactly what it did? AgentOps Replay adds cryptographic proof to every OpenClaw session. Zero code changes. Nothing leaves your machine. Run `agentops-verify session.jsonl` yourself."

This lands because:
- OpenClaw users know their agent has broad access (they chose it)
- CVE-2026-25253 and the 190 security advisories mean the community is security-aware
- "Nothing leaves your machine" speaks to the self-hosting ethos
- "Run it yourself" speaks to the distrust of black boxes

### 5.2 Where to Post

**OpenClaw GitHub Discussions:** The primary community hub. Post an "Integrations" discussion: "I built a zero-dependency accountability layer for OpenClaw sessions."

**OpenClaw Discord:** The real-time community. Post in `#skills` or `#security` channels.

**Hacker News:** The message that works on HN: "OpenClaw has 190 filed security advisories and its default session logs are mutable and deletable. Here's a zero-dependency tool that adds cryptographic proof to every session. Open source. No account required."

**r/LocalLLaMA:** The self-hosted AI subreddit. This community is privacy-focused and will immediately understand the value of a verifier that runs without network access.

**r/OpenClaw (if it exists) / relevant subreddits:** Community already discussing the platform.

### 5.3 The Timing Window

OpenClaw is at a critical inflection point. It went from 0 to 68,000 GitHub stars in early 2026. The community is growing, security incidents have raised awareness, and NVIDIA's involvement signals enterprise interest. This is the ideal moment to position AgentOps Replay as the accountability layer the community didn't know it needed.

The CVE-2026-25253 incident (January 2026) is particularly useful context: it proved that a compromised OpenClaw instance could have its session logs silently modified. Users who experienced that vulnerability or heard about it are primed to understand why tamper-evident logs matter.

### 5.4 The NemoClaw Opportunity

NVIDIA's NemoClaw project is open source. Contributing AgentOps Replay as an optional component to the NemoClaw stack (alongside OpenShell guardrails) would give immediate access to the NemoClaw user base and NVIDIA's institutional backing.

The pitch to NemoClaw maintainers: "NemoClaw tells the agent what it can do. AgentOps Replay proves what it actually did. Together they're a complete accountability stack."

---

## Section 6: Product Requirements for OpenClaw Integration (v1.2 target)

### 6.1 OpenClaw AgentSkill Package

**Requirements:**
- A standard OpenClaw AgentSkill that users install with one command
- Compatible with OpenClaw's skill format (YAML manifest + Python implementation)
- Configuration: server URL (defaults to disabled/local-only), output directory (defaults to `~/.openclaw/agentops/`)
- Works in fully offline/air-gapped mode using local authority (JSONL only)
- Captures all standard OpenClaw event types: LLM calls, tool invocations, cron executions, errors

**Skill manifest (target):**
```yaml
name: agentops-replay
version: "1.0.0"
description: "Cryptographically verifiable audit trail for OpenClaw sessions"
author: "agentops-replay"
permissions:
  - session.read        # Read session events
  - filesystem.write    # Write JSONL to output directory
hooks:
  - session.start
  - session.end
  - llm.call
  - llm.response
  - tool.invoke
  - tool.result
  - tool.error
config:
  local_authority: true          # Default: no server required
  server_url: null               # Set to enable server mode
  output_dir: "~/.openclaw/agentops/"
  buffer_size: 1000
```

### 6.2 Zero-Configuration Local Mode

For the vast majority of OpenClaw users, the value proposition is local-only:
1. Install the skill
2. Every session automatically produces a JSONL in `~/.openclaw/agentops/`
3. Run `agentops-verify ~/.openclaw/agentops/<session_id>.jsonl` any time
4. See PASS ✅ + NON_AUTHORITATIVE_EVIDENCE

No Docker, no server, no configuration. This must work out of the box.

### 6.3 Optional Local Server Mode

For power users or those with compliance needs:
1. `docker-compose up agentops` in the AgentOps Replay directory
2. Set `server_url: "http://localhost:8000"` in the skill config
3. Sessions now produce AUTHORITATIVE_EVIDENCE with CHAIN_SEAL
4. Export and verify: `agentops-verify` on exported JSONL shows AUTHORITATIVE_EVIDENCE

### 6.4 CronJob / Heartbeat Session Support

OpenClaw's heartbeat scheduler creates sessions that run on a configurable interval, often without a human initiating them. AgentOps Replay must handle these correctly:

- Cron/heartbeat sessions must be recorded with `agent_role: "autonomous"` in SESSION_START
- Sessions that run overnight without human oversight get the same cryptographic treatment as interactive sessions
- Long-running sessions (multi-hour or multi-day heartbeat sequences) must not overflow the buffer — LOG_DROP semantics must handle high-event-count sessions gracefully

---

## Section 7: Differentiation from OpenClaw's Built-In Logging

This section is for messaging, not internal documents. Use it when writing README comparisons, community posts, or documentation.

### The One-Line Difference

OpenClaw's built-in logging tells you **what happened**. AgentOps Replay tells you **what happened and proves no one changed the record**.

### The Longer Version (for documentation)

| Property | OpenClaw Built-In | AgentOps Replay |
|---|---|---|
| Log format | JSONL session transcripts | JSONL hash-chained event envelopes |
| Tamper evidence | None — files are mutable | SHA-256 hash chain — any change detected |
| Verification | No independent tool | `agentops-verify` — zero-dependency, runs anywhere |
| Evidence class | Not defined | AUTHORITATIVE / PARTIAL / NON-AUTHORITATIVE |
| Deletable? | Yes — shell access deletes them | Yes locally; server mode is append-only at DB level |
| Suitable for compliance? | Fails SOC 2 CC7.2 (local only) | AUTHORITATIVE_EVIDENCE suitable for audit |
| Content stored? | Full conversation transcripts | Hashes only — content never stored |
| Requires account? | No | No — verifier runs standalone |

**Important:** This is not a criticism of OpenClaw. Its built-in logging is appropriate for a personal tool. AgentOps Replay is the layer you add when you need the log to be evidence rather than just a transcript.

---

*Open-Source Community Market Document v2 — May 2026*
*This document supersedes MARKET_OPENSOURCE_COMMUNITY.md v1.*
*Primary target: OpenClaw (formerly Clawdbot/Moltbot) users and community.*
