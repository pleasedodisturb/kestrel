---
title: Cost Control Research Synthesis
date: 2026-04-21
context: Exploration session — 7 research agents, 1 spike (G-437/PR #254)
---

# Cost Control Research Synthesis

## Strategy: OpenRouter-first, Preset-based

The user's primary goal: a Kestrel user should be able to run the platform for **months on $10 or less**.
The default on-ramp is OpenRouter (one key, 400+ models). With $10 on the account, rate limits
increase and free-tier models become viable at scale.

## The Funnel (confirmed by data)

1. **Scrape** ~1,500 jobs/day (python-jobspy, no AI, $0)
2. **Pre-filter** via regex/keyword — eliminates 60% with 99.5% recall (G-437 spike, PR #254)
3. **AI score** ~600 survivors — batch 10/prompt, cache system prompt → ~$0.18/day on Haiku
4. **Personalize** (cover letters, interview prep) — low volume, PII, needs privacy-conscious provider

## Cost Math (stacking all optimizations)

| Optimization | Reduction |
|-------------|-----------|
| Pre-filter (60% elimination) | -60% |
| Batch scoring (10/prompt) | -90% call count |
| Prompt caching (system+profile) | -90% on cached tokens |
| Batch API (Anthropic/OpenAI) | -50% on remaining |
| **Combined** | **~94.5% total** |

Baseline $99/mo → optimized **$5.40/mo** on Haiku. Or **$0/mo** on free tier rotation.

## Presets (data-driven, not guesswork)

| Preset | Provider | Monthly Cost | Notes |
|--------|----------|-------------|-------|
| Free | OpenRouter free models / Groq→Cerebras→SambaNova | $0 | Good for testing, rate-limited |
| Budget | GPT-4o-mini via OpenRouter ($10 balance) | $1-5 | Sweet spot for most users |
| Quality | Sonnet scoring + Opus generation | $5-25 | Best results, hybrid routing |
| Private | Ollama / ZDR providers | $0 + hardware | For PII-sensitive operations |
| Custom | User tunes everything | Varies | Full control, documented knobs |

If natural tiers don't hold up after real A/B testing, simplify to: Free / Paid / Custom.

## Free Model Landscape (April 2026)

| Provider | Free Limit | OpenAI-Compatible | Best Free Model |
|----------|-----------|-------------------|-----------------|
| Groq | 1,000 RPD | Yes | Llama 3.3 70B |
| Cerebras | 14,400 RPD | Yes | Llama 3.3 70B |
| SambaNova | Unlimited (rate-limited) | Yes | Llama 3.3 70B / 405B |
| OpenRouter | 50 RPD (no balance) | Yes | Llama 3.3 70B :free |
| Google Gemini | 1,000 RPD (Flash-Lite) | No (own SDK) | Gemini 2.5 Flash-Lite |

OpenRouter's free tier (50 RPD) is too low for primary use. With $10 balance, limits unlock.

## Provider Privacy Trust Matrix

| Provider | API Training | Retention | ZDR | Trust Signal |
|----------|-------------|-----------|-----|-------------|
| Anthropic | No | 7 days | Yes | Strongest — no fines, shortest retention |
| OpenAI | No (since 2023) | 30 days | Enterprise only | Moderate — Worldcoin, FTC investigation |
| Google/Gemini | Free: YES / Paid: No | 55 days | Vertex only | Free tier is a trap — EU can't use it |
| xAI/Grok | No (paid) / Yes (data sharing) | 30 days | No | Irrevocable data sharing, active GDPR investigations |
| Together.ai | TBD | TBD | TBD | SOC 2 certified, Frankfurt region |

Privacy disclosure with sources should accompany each provider in the docs.

## New Providers to Add

- **Groq** (`api.groq.com/openai/v1`) — fastest inference, free tier, OpenAI-compatible
- **xAI/Grok** (`api.x.ai/v1`) — OpenAI-compatible, privacy warning needed
- **Gemini** — separate task, needs own SDK (not OpenAI-compatible)
- **OpenAI** — direct API, OpenAI-native

## Decisions Made

- OpenRouter is the default on-ramp (one key, $10 deposit unlocks everything)
- Presets over complexity — simple matrix, not a tuning dashboard
- Custom preset available for power users who want full control
- Privacy warnings (with source links) on Google, xAI, OpenAI providers
- Casual users first, power/privacy users documented but self-serve
