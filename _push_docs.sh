#!/usr/bin/env bash
set -e
cd /Users/lulu/Desktop/agentops-replay-pro

git checkout -b add-agentops-docs

git add AgentOps_docs/AGENT_CONTEXT.md


git add AgentOps_docs/AGENT_PROMPT.md
git commit -m "docs: add AGENT_PROMPT.md"

git add AgentOps_docs/BUILD_SEQUENCE.md
git commit -m "docs: add BUILD_SEQUENCE.md"

git add AgentOps_docs/MARKET_ENTERPRISE_SECURITY.md
git commit -m "docs: add MARKET_ENTERPRISE_SECURITY.md"

git add AgentOps_docs/MARKET_OPENSOURCE_COMMUNITY.md
git commit -m "docs: add MARKET_OPENSOURCE_COMMUNITY.md"

git add AgentOps_docs/PRD_v5.md
git commit -m "docs: add PRD_v5.md"

git add AgentOps_docs/RESEARCH_PAPER_ROADMAP.md
git commit -m "docs: add RESEARCH_PAPER_ROADMAP.md"

git push -u origin add-agentops-docs

echo "Done! Open a PR at: https://github.com/$(git remote get-url origin | sed 's/.*github.com[:/]\(.*\)\.git/\1/')/compare/add-agentops-docs"
