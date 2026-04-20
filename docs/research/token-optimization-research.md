# Token Optimization: Strategy & Implementation

> Dev synthesis — opinionated recommendations with trade-off analysis.
> For raw research, see [awesome-llm-token-optimization](https://github.com/pleasedodisturb/awesome-llm-token-optimization).

## Decision Framework

We evaluated 10 strategies from the research corpus. At Kestrel's scale (<500 AI calls/day), the cost-benefit calculation favors **zero-dependency, zero-latency** approaches over heavyweight solutions.

### Implemented (Shipped April 2026)

| Strategy | Ticket | Savings | Effort | Key Insight |
|----------|--------|---------|--------|-------------|
| Compact JSON serialization | G-428 | ~30% profile tokens | S (10 min) | `indent=2` adds whitespace tokens with zero value to the LLM |
| System prompt deduplication | G-429 | ~90% cache hit rate | S (1 hr) | Profile in cached system block exceeds 1024-token minimum for Anthropic cache activation |
| Compressed prompts | G-261 | 67% system prompt tokens | S (30 min) | Telegraphic notation works as well as verbose for structured schema instructions |
| Token-efficient tool use | G-349 | 70% output reduction | S (5 min) | Single header: `anthropic-beta: token-efficient-tool-use-2025-04-14` |
| Model routing (ComplexityTier) | G-352 | 60-95% on simple tasks | M (2 hr) | Classification doesn't need Opus; routing by AIFeature → tier mapping |
| Batch API | G-351 | 50% flat discount | M (2 hr) | Non-real-time scoring is the majority of volume |
| Response caching | (existing) | 100% on repeats | — | SHA-256 key, Fernet-encrypted SQLite, 7-day TTL |
| Cost visibility | G-397 | n/a (observability) | M (1 hr) | Per-call token logging to ai_usage_log table; `X-Title: kestrel` on OpenRouter |
| Cache break detection | G-427 | n/a (protection) | S (30 min) | Sliding window hit ratio tracking, WARNING at <80% |

### Evaluated and Rejected

| Strategy | Why Not |
|----------|---------|
| **LLMLingua-2** (Microsoft) | 1.2GB model download, 2-5s CPU latency per compression. Only worthwhile at 2000+ calls/day. Our prompts are already <300 tokens — LLMLingua targets 5000+ token contexts. |
| **Semantic pre-compression** (cheap model summarizes before expensive model scores) | Adds latency, doubles error surface, information loss risk. Response caching already handles the "same job scored twice" case. Saves ~$0.50/day — not worth the complexity. |
| **KV cache compression** (vLLM/SGLang) | Only relevant for self-hosted inference. We use API providers. |
| **Context window stuffing** | Kestrel's prompts are already well within context limits. No RAG tradeoff needed. |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    CachedProvider                        │
│  (response cache: SHA-256 key → encrypted SQLite)       │
│  → log_usage() on cache miss                           │
├─────────────────────────────────────────────────────────┤
│                   MaskedProvider                         │
│  (PII masking: regex-based, bidirectional)              │
├─────────────────────────────────────────────────────────┤
│               AnthropicProvider                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │ System block: [compressed prompt + profile]      │   │
│  │ cache_control: {"type": "ephemeral"}             │   │
│  │ → cache hit: 90% off input tokens               │   │
│  │ → record_cache_event() for break detection       │   │
│  ├─────────────────────────────────────────────────┤   │
│  │ User message: [job description only]             │   │
│  │ Profile NOT here (moved to cached system block)  │   │
│  ├─────────────────────────────────────────────────┤   │
│  │ Model: resolved by ComplexityTier                │   │
│  │ SIMPLE→Haiku, STANDARD→Sonnet, COMPLEX→Opus    │   │
│  └─────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│              Token-Efficient Tool Use                    │
│  Header: anthropic-beta: token-efficient-tool-use-*     │
│  → 70% reduction on tool use output tokens             │
└─────────────────────────────────────────────────────────┘
```

## Cost Model

Pricing as of April 2026 (per million tokens):

| Model | Input | Output | Cache Read | Cache Write |
|-------|-------|--------|-----------|-------------|
| Claude Opus 4 | $15.00 | $75.00 | $1.50 | $18.75 |
| Claude Sonnet 4 | $3.00 | $15.00 | $0.30 | $3.75 |
| Claude Haiku 4.5 | $0.80 | $4.00 | $0.08 | $1.00 |
| Llama 3.3 70B (Together.ai) | $0.88 | $0.88 | n/a | n/a |

**Typical scoring call (Sonnet, with optimizations):**
- System prompt (compressed): ~39 tokens → $0.000117 input (or $0.0000117 cached)
- Profile (compact, cached): ~400 tokens → $0.00012 cached
- Job description (user message): ~800 tokens → $0.0024 input
- Output: ~1000 tokens → $0.015 output

**Per-job cost: ~$0.018 (first call) / ~$0.017 (cached)**
**Batch cost: ~$0.009/job (50% discount)**

## Compound Effect Calculation

For a batch of 50 jobs, same user:

| Layer | Tokens Saved | Cost Impact |
|-------|-------------|-------------|
| Compact JSON | 120 tokens/call × 50 = 6,000 | -$0.018 |
| Prompt caching (profile) | 400 × 49 × 0.9 = 17,640 | -$0.053 |
| Compressed prompts | 74 × 50 = 3,700 | -$0.011 |
| Model routing (10 Haiku pre-filters) | ~8,000 tokens at Opus price avoided | -$0.12 |
| Batch API | 50% off remaining | -$0.44 |
| **Total saved** | | **~$0.64 per 50-job batch** |

Without optimizations: ~$0.90/batch. With: ~$0.26/batch. **71% reduction.**

## Monitoring

### Token usage logging (G-397)

Every non-cached AI call writes to `ai_usage_log`:
- timestamp, provider, model, feature
- input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens
- estimated_cost_usd (computed from model pricing table)

Query via: `SELECT feature, SUM(estimated_cost_usd) FROM ai_usage_log WHERE timestamp > date('now', '-7 days') GROUP BY feature`

### Cache break detection (G-427)

`cache_monitor.py` tracks per-feature sliding window (100 events):
- `record_cache_event(feature, usage)` — called after every Anthropic response
- Hit = `cache_read_input_tokens > 0`
- Miss = `cache_creation_input_tokens > 0` and read == 0
- WARNING logged when hit ratio drops below 80%
- Auto-resets when ratio recovers

## Files

| File | Purpose |
|------|---------|
| `src/career_os/ai/cache.py` | Response caching (CachedProvider) + log_usage hook |
| `src/career_os/ai/cache_monitor.py` | Cache break detection |
| `src/career_os/ai/anthropic_provider.py` | Prompt caching, profile in system block, model routing |
| `src/career_os/ai/observability.py` | log_usage(), cost estimation, Langfuse integration |
| `src/career_os/ai/base.py` | ComplexityTier enum, AIProvider interface |
| `src/career_os/models/ai_usage.py` | AIUsageLog ORM model |
| `src/career_os/schemas/ai.py` | TokenUsage, AIFeature, feature→tier mapping |
