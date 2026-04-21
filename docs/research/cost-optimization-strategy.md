# Cost Optimization Strategy

*Research date: 2026-04-21 | Related tickets: G-437 (pre-filter spike), cost control epic (pending)*

## Problem Statement

Kestrel scrapes ~1,500 jobs/day and scores them with AI models. The goal: a user should be able to run Kestrel for months on $10 or less, without sacrificing scoring quality.

## The Scoring Funnel

| Stage | Volume | Method | Cost |
|-------|--------|--------|------|
| 1. Scrape | 1,500/day | python-jobspy | $0 |
| 2. Pre-filter | → ~600 survivors | Regex/keyword (title, skills, industry blacklist) | $0 |
| 3. AI score | 600/day | LLM via API (batch 10/prompt) | $0-14/mo |
| 4. Personalize | 5-10/day | Cover letters, interview prep (PII, needs privacy) | $0-5/mo |

### Pre-filter (Stage 2) — Confirmed by G-437 Spike (PR #254)

Combined filter strategy: **(title match OR 2+ skill keywords) AND NOT blacklisted industry**

| Metric | Value |
|--------|-------|
| Jobs eliminated | ~60% |
| Recall (relevant jobs kept) | 99.5%+ |
| False negatives | 0-12 out of ~2,500 relevant jobs |
| Monthly savings at $0.003/call | ~$81/mo |

Title-only filtering is a trap (70%+ elimination but only 69-86% recall). Skill density alone is the best single filter (62% elimination, 97% recall).

### Batch Scoring (Stage 3)

arXiv:2604.03684 (April 2026): "Researchers waste 80% of LLM annotation costs by classifying one text at a time."

- Sweet spot: 10-25 jobs per prompt
- Quality loss: <2 percentage points for classification tasks
- Position bias exists — mitigate by randomizing job order within batches
- At 10 jobs/prompt: 600 calls → 60 calls

### Prompt Caching

System prompt + user profile (~2,500 tokens) is identical across all scoring calls.

- Anthropic: cache reads at 0.1x standard input (90% savings), 5-min TTL
- Cache write: 1.25x first call, then 0.1x for all subsequent
- OpenAI: similar caching available

### Batch API (Anthropic + OpenAI)

- 50% off input and output tokens
- Results within 24 hours (perfect for nightly discovery scoring)
- Can stack with prompt caching for up to 95% total reduction
- No quality difference vs real-time

## Cost Math: Stacking All Optimizations

**Baseline:** 600 individual Haiku 4.5 calls/day, no optimization

| Component | Calculation | Daily | Monthly |
|-----------|-------------|-------|---------|
| Input | 600 x 3K tokens x $1.00/M | $1.80 | $54 |
| Output | 600 x 500 tokens x $5.00/M | $1.50 | $45 |
| **Total** | | **$3.30** | **$99** |

**Optimized:** Pre-filter + batch 10/prompt + caching + Batch API

| Component | Calculation | Daily | Monthly |
|-----------|-------------|-------|---------|
| After pre-filter | 240 jobs to score | | |
| Batched | 24 API calls (10 jobs each) | | |
| Input (cached) | 2,500 tokens x 0.1x x 24 = ~6K effective | ~$0.003 | $0.09 |
| Input (fresh) | 5,000 tokens x 0.5x x 24 = ~60K effective | ~$0.03 | $0.90 |
| Output | 48K tokens x $5.00/M x 0.5 | $0.12 | $3.60 |
| **Total** | | **~$0.18** | **~$5.40** |

**94.5% reduction: $99/mo → $5.40/mo**

Without Batch API (real-time needed): ~$12/mo. On free tier (Groq/Cerebras): $0/mo.

## Preset Strategy

Based on the cost data, natural tiers emerge:

| Preset | Provider Strategy | Monthly Cost | Quality |
|--------|------------------|-------------|---------|
| **Free** | OpenRouter free models / Groq→Cerebras→SambaNova rotation | $0 | Good |
| **Budget** | GPT-4o-mini via OpenRouter ($10 deposit unlocks limits) | $1-5 | Good+ |
| **Quality** | Sonnet for scoring + Opus for generation (hybrid routing) | $5-25 | Excellent |
| **Private** | Ollama locally or ZDR providers (Anthropic API) | $0 + hardware | Varies |
| **Custom** | User tunes everything | Varies | Varies |

If A/B testing shows tiers don't hold, simplify to: **Free / Paid / Custom**.

### OpenRouter as Default On-Ramp

- With $0 balance: 50 RPD (not viable for daily scoring)
- With $10 balance: unlocked rate limits + free model access at higher RPM
- Single key accesses 400+ models including free-tier models from Groq, Meta, Mistral
- Simplest setup: one account, one key, done

## Hybrid Routing (by operation type)

The fallback chain (G-405) enables routing by operation type, not just failover:

| Operation | Recommended Tier | Monthly Cost | Why |
|-----------|-----------------|-------------|-----|
| Job scoring (18,000/mo) | Budget (GPT-4o-mini) | ~$14 | 97% of cost, quality sufficient for pass/fail |
| Company research (300/mo) | Standard (Sonnet) | ~$5 | Needs reasoning quality |
| Interview prep (90/mo) | Standard (Sonnet) | ~$3 | Needs reasoning quality |
| Cover letters (90/mo) | Quality (Opus) | ~$3 | User-facing text, PII → privacy provider |
| **Hybrid total** | | **~$25/mo** | vs $307+ for uniform Sonnet |

## Key Decision: Public vs Private Data

| Data Type | Examples | Privacy Need | Provider Freedom |
|-----------|----------|-------------|-----------------|
| Public | Job descriptions, company info, skill keywords | None | Any free/cheap model |
| Private | Resumes, cover letters, interview prep, user profile | High | ZDR providers, Ollama |

Scoring (the expensive operation) is 100% public data. Privacy-sensitive operations (cover letters, interview prep) are low-volume. This means cost optimization and privacy are not in conflict.

## Sources

- [Anthropic API Pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [Anthropic Prompt Caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [OpenAI API Pricing](https://developers.openai.com/api/docs/pricing)
- [Together AI Pricing](https://www.together.ai/pricing)
- [Groq Free Tier Limits](https://tokenmix.ai/blog/groq-free-tier-limits-2026)
- [OpenRouter Pricing](https://openrouter.ai/pricing)
- [arXiv: Batch Prompting Cost Savings](https://arxiv.org/abs/2604.03684v1)
- [Batch Scoring Quality (ICLR 2024)](https://arxiv.org/pdf/2309.00384)
- [Cerebras Free Tier](https://aicreditmart.com/ai-credits-providers/cerebras-free-tier-1-million-tokens-day-guide-2026/)
- [Free AI APIs 2026](https://awesomeagents.ai/tools/free-ai-inference-providers-2026/)
