# Cost Control

*Part of the [Kestrel roadmap](../../ROADMAP.md).*

## Goal

Run a full AI-powered job search without worrying about the bill.

## What This Delivers

Kestrel ships with five cost presets: Free, Budget, Quality, Private, and Custom. You pick one during setup and can change it anytime. Each preset configures the AI provider, model selection, pre-filter aggressiveness, and batch size in a single choice. The Budget preset targets about $0.81 per month for daily job scanning. The Free preset costs nothing at all.

The Free preset rotates between three providers (Groq, Cerebras, SambaNova) that offer permanent free tiers running Meta's Llama 3.3 70B model. Combined, they provide over 3,000 free API calls per day. Budget adds OpenRouter with GPT-4o-mini at $0.15 per million input tokens. Quality uses different models for different tasks, matching model strength to task complexity. Private routes everything through local Ollama or providers with zero-data-retention guarantees. Custom gives you full control over every routing decision.

Several optimization layers stack to keep costs low. Batch scoring bundles 10 jobs into a single prompt, cutting API calls by roughly 80%. Prompt caching stores your profile and scoring instructions across calls so providers charge only for the new content. Async Batch APIs from Anthropic and OpenAI process nightly discovery results at 50% off since the delay does not matter for overnight runs. Pre-filtering eliminates about 60% of jobs before any AI call happens. Applied together, these optimizations reduce the baseline cost of scoring 600 jobs per day from roughly $99 to about $5.40 per month.

## How It Works

When you select a preset, Kestrel configures the provider, model, and optimization settings behind a single API call. The presets service stores your active preset and exposes it through `GET/PUT /api/presets/active`. Each preset maps to a specific provider configuration, model selection, and batch scoring parameters.

Token tracking captures input tokens, output tokens, and cache tokens from every provider response. This data feeds into the cost monitoring that shows you what you are actually spending versus what the preset predicted.

## Current Status

*Shipped in [v0.11.0](../../CHANGELOG.md#0110-2026-04-21)*

All five presets are active. Batch scoring, prompt caching, async Batch APIs, and pre-filtering are all shipped and enabled by default. The $0.81/month target has been validated against real usage data. Token tracking captures usage from every provider response.

## Related Milestones

- **[Scoring Engine](scoring-engine.md)** -- Presets configure scoring cost behavior
- **[AI Provider System](ai-provider-system.md)** -- Presets select provider and model

---

*For Contributors*

## Architecture

Cost control spans several modules:

- `src/career_os/services/presets.py` -- Preset definitions and active-preset management. Five named presets mapping to provider, model, batch size, and pre-filter strategy.
- `src/career_os/services/batch_scoring.py` -- Batch orchestration: groups jobs into batches of `BATCH_SCORING_SIZE` (default 10), sends as a single prompt, parses individual results. Falls back to individual scoring on parse failure.
- `src/career_os/services/async_batch.py` -- Anthropic and OpenAI Batch API integration for nightly scoring at 50% discount. Endpoints: `POST /api/score/batch/submit`.
- `src/career_os/ai/cache.py` -- AI response caching with Fernet encryption, 7-day TTL, SHA-256 keyed. Prevents duplicate API calls for identical requests.
- `src/career_os/discovery/prefilter.py` -- Pre-filter strategy (strict/moderate/off) configured via `PREFILTER_STRATEGY` env var.
- `src/career_os/schemas/ai.py` -- `TokenUsage` schema capturing input/output/cache tokens from every provider response.

The optimization layers are independent of each other. You can disable batch scoring, skip the cache, or turn off pre-filtering without affecting the others.

## Research & Decisions

Annotated links to research and reference documents:

- [Cost Optimization Strategy](../research/cost-optimization-strategy.md) -- The complete cost optimization strategy: funnel math, $0.81/month budget target, and tier analysis
- [Batch Scoring Feasibility](../research/batch-scoring-feasibility.md) -- Academic evidence supporting batch scoring at 10-25 jobs per prompt with less than 2% accuracy loss
- [Preset Tier Validation](../research/preset-tier-validation.md) -- Data-driven validation of five preset tiers against real benchmark results
- [Token Optimization Research](../research/token-optimization-research.md) -- Ten strategies evaluated. Shipped: compact JSON (30% savings), system prompt deduplication (90% cache hit rate)
- [Token Optimization Raw Research](../research/token-optimization-raw-research.md) -- Raw research data behind token optimization decisions and benchmark measurements
- [AI Costs and Privacy Guide](../guides/cost-optimization.md) -- User-facing guide explaining tiers, realistic monthly costs, and what "free" really means

## BMAD Integration

**PRD Status:** Not started

A PRD would define preset boundaries and upgrade triggers, cost monitoring dashboard UX, budget alert threshold configuration, and the token accounting methodology.

To start a PRD: `/bmad-create-prd` in Claude Code.
See the [planning hierarchy](inventory.md#how-planning-works) for how PRDs connect to implementation.
