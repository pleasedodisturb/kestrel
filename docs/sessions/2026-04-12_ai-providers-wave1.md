# Session: AI Providers & Privacy — Research + Wave 1 Implementation
**Date:** 2026-04-12 to 2026-04-13
**Branch:** feat/ai-providers-wave1
**Tickets:** G-224, G-225, G-226, G-228, G-234, G-236 (Done) + G-254–G-261 (created)

## What was done
- Deep research via 7 parallel agents: local AI options, OpenRouter alternatives, goodailist.com tools, referral/onboarding, Gemini privacy deep dive, full provider privacy audit
- Created 23 Linear tickets in "AI Providers & Privacy" milestone
- PR #120 merged: factory registry refactor (dict-based, from Ultraplan)
- PR #132 opened: Wave 1 implementation (6 modules, 91 tests)
  - G-234: Privacy framework (PrivacyTier enum, metadata registry, API endpoints)
  - G-226: Direct Anthropic provider with prompt caching
  - G-228: SQLite response caching (CachedProvider wrapper)
  - G-236: PII masking (regex email/phone/URL, MaskedProvider wrapper)
  - G-225: Ollama provider (local AI, JSON retry, 120s timeout)
  - G-224: OpenRouter OAuth PKCE (backend endpoints)
- Wrote 4 user-facing docs: ai-providers-explained.md, how-job-search-actually-works.md, LLM research, updated AI-PROVIDERS.md
- Updated README.md with organized doc navigation and multi-provider AI section
- Added in-app education framework to G-231 (tooltips, empty states, score breakdowns as teaching)
- Fixed CI: added actionlint job, removed code scanning from merge ruleset
- Global CLAUDE.md: added "Research Discipline" section

## Decisions made
- Dict-based provider registry (not self-registration) — simpler, one file to read
- Plain SQLite caching (not GPTCache library) — zero dependencies
- Regex PII masking (not spaCy/Presidio) — zero dependencies, extensible later
- No LiteLLM adoption yet — March 2026 supply chain attack makes it risky
- Gemini free tier gets red privacy warning — trains on data, human review, EU-banned
- OpenRouter prompt logging trap must be warned about in onboarding
- Docs tone: warm/teaching for users, technical for devs, analytical for positioning

## Open items
- PR #132 awaiting CI + merge
- Wave 2: G-255 (OAuth frontend button), G-235 (Mistral), G-237 (prompt caching), G-227 (routing), G-231 (UX overhaul)
- Wave 3-4: 11 more tickets in backlog (OpenAI, Together, Gemini, batch API, prompt compression, GDPR, etc.)

## Commits (on feat/ai-providers-wave1)
- G-234: add privacy framework with per-provider privacy indicators
- G-226: add direct Anthropic provider with prompt caching
- G-228: add SQLite-based response caching for AI providers
- G-236: add client-side PII masking layer for AI prompts
- G-225: add Ollama provider for local AI models
- G-224: add OpenRouter OAuth PKCE backend endpoints
- G-234: add AI provider research and user-facing explainer docs
- G-231: update README with organized docs section and multi-provider AI guide
- G-231: add job search education guide and update README docs navigation
- G-234: update AI-PROVIDERS.md — fix stale info, link new explainer
