---
title: Create Cost Control epic in Linear
date: 2026-04-21
priority: high
---

# Create Cost Control Epic in Linear

Create an epic with these tickets:

1. **Pre-filter integration** — wire the G-437 spike findings into the discovery pipeline (regex+keyword pre-filter before AI scoring)
2. **Batch scoring** — implement 10-jobs-per-prompt batch scoring with randomized order (position bias mitigation)
3. **Prompt caching** — add cache_control headers to Anthropic system prompts, implement cache-friendly call ordering
4. **Preset system** — Free/Budget/Quality/Private/Custom presets with simple matrix UI
5. **Groq provider** — OpenAI-compatible, follow Together.ai pattern
6. **xAI/Grok provider** — OpenAI-compatible, include privacy warning
7. **OpenAI direct provider** — OpenAI-native API
8. **Gemini provider** — separate SDK, own task (not OpenAI-compatible)
9. **Edutainment cost docs** — user-facing guide: start free, understand tiers, privacy disclosures with sources
10. **Provider privacy disclosures** — factual warnings with source links for Google, xAI, OpenAI in provider selection UI
