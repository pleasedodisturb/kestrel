# Session: Test Infrastructure Epic & Research Documentation
**Date:** 2026-04-16
**Branch:** G-305/testing-research-docs, G-305/research-docs-integration
**Tickets:** G-305 (epic), G-329–G-343 (14 children), G-346, G-347

## What was done
- Audited current test landscape: 97 backend files, 23 frontend, 0 mobile, zero tier markers, flat CI
- Ran 5 parallel research agents covering layered testing, AI-agent QA, exploratory testing, CI orchestration, cross-project standards
- Created G-305 epic with full research synthesis, target architecture, and success criteria
- Created 14 child tickets across 5 phases (foundation → agent-aware → advanced → deep → docs)
- Wrote 9 research documents across 3 topics x 3 formats (scoring, testing, CI/CD)
- Fixed MIT → AGPL-3.0 in README badge, pyproject.toml, npm-package/package.json
- Added "How we build" section to README with 4x3 research matrix
- Added "How it works under the hood" docs section to README
- Linked awesome-llm-token-optimization repo as 4th row in research matrix
- Created G-346 (awesome-ai-agent-testing) and G-347 (awesome-agentic-cicd) tickets

## Decisions made
- Test pyramid: 5 tiers (T0 smoke → T4 deep) with explicit trigger conditions per tier
- CI architecture: detect-then-run with dorny/paths-filter, ci-complete as sole required check
- All tooling $0/year: testmon, Schemathesis, Hypothesis, mutmut, Bandit, Playwright, Gremlins.js
- Don't extract shared test infra yet — build in Kestrel first, extract when second project needs it
- awesome-ai-agent-testing is worth a standalone repo; awesome-agentic-cicd needs evaluation first
- 3-format research doc pattern is now a project standard

## Open items
- PR #198 awaiting merge (license fix, scoring docs, README matrix)
- G-305 Phase 1 ready to start (G-329 pytest markers is the first ticket)
- G-346 awesome-ai-agent-testing needs deep research before creation

## Commits
- `740b74e` docs(G-305): add testing strategy research docs in 3 formats (PR #195, merged)
- `70cf8bb` fix(G-305): correct license MIT→AGPL-3.0, integrate research docs into README
- `8ce88e1` docs(G-305): complete 3x3 research doc matrix — scoring + CI/CD docs, full README table
- `2833aa1` docs(G-305): add LLM token optimization research to README matrix
- `66c3abf` docs(G-305): hyperlink LLM Token Costs topic name to awesome repo
- Above 4 commits cherry-picked as PR #198
