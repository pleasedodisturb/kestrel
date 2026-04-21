# OpenRouter Rate Limit Tiers

*Research date: 2026-04-21 | Related ticket: G-454*

## Problem Statement

Kestrel uses OpenRouter as its default API gateway. Understanding exactly what changes at each credit threshold is critical for recommending the right minimum deposit to users running 18,000 scores/month (~600/day).

## Balance Tier Summary

| Dimension | $0 (No Credits) | $10+ (Purchased Once) | $50+ Balance |
|-----------|-----------------|----------------------|--------------|
| **Free model RPD** | 50/day | 1,000/day | 1,000/day |
| **Free model RPM** | 20/min | 20/min | 20/min |
| **Paid model RPS** | N/A (no balance) | 10 RPS ($1 = 1 RPS) | 50 RPS ($1 = 1 RPS) |
| **Paid model RPS cap** | N/A | 500 RPS max | 500 RPS max |
| **Paid model RPM/RPD** | N/A | No platform-level cap | No platform-level cap |
| **Free model count** | 28 models | 28 models | 28 models |
| **Paid model access** | None | 400+ models | 400+ models |
| **Negative balance** | 402 errors (even on free models) | 402 errors if negative | 402 errors if negative |

### Key Threshold: $10 Lifetime Purchase

The $10 threshold is a **one-time purchase gate**, not a balance floor. Once you have purchased $10 or more in credits at any point, the higher free model limits (1,000 RPD) are permanently unlocked -- even if your balance later drops below $10 or to $0.

### Paid Model Dynamic RPS

For paid models, OpenRouter uses a dynamic rate limit tied to your current credit balance:

- **Formula:** $1 balance = 1 RPS (request per second)
- **Cap:** 500 RPS maximum regardless of balance
- **No platform RPM/RPD cap:** Paid models are not limited by OpenRouter's platform -- only by upstream provider limits

This means:
- $10 balance = 10 RPS = 600 requests/min theoretical max
- $50 balance = 50 RPS = 3,000 requests/min theoretical max
- As balance is consumed, RPS decreases proportionally

### Free Model Limits (All Tiers)

All `:free` model variants share the same RPM cap of 20 requests/minute regardless of credit tier. The only difference credits make is the daily cap (50 vs 1,000 RPD).

Important caveats:
- Failed requests still count toward daily quota
- Free models are rate-limited by upstream providers during peak times
- Free models require enabling training/logging permissions in OpenRouter privacy settings
- Free models are "usually not suitable for production use" per OpenRouter's own FAQ
- Multiple API keys or accounts do NOT bypass limits -- rate limits are per-account globally

## Free Models Available (April 2026)

28 free models on OpenRouter, notable ones for Kestrel's scoring use case:

| Model | Provider | Model ID | Context | JSON Quality |
|-------|----------|----------|---------|-------------|
| Llama 3.3 70B | Meta | `meta-llama/llama-3.3-70b-instruct:free` | 66K | MEDIUM-HIGH |
| Qwen3 Coder 480B | Qwen | `qwen/qwen3-coder:free` | 262K | Untested |
| Qwen3 Next 80B | Qwen | `qwen/qwen3-next-80b-a3b-instruct:free` | 262K | Untested |
| Nemotron 3 Super 120B | NVIDIA | `nvidia/nemotron-3-super-120b-a12b:free` | 262K | Untested |
| Gemma 4 31B | Google | `google/gemma-4-31b-it:free` | 262K | Untested |
| gpt-oss-120b | OpenAI | `openai/gpt-oss-120b:free` | 131K | Untested |
| Hermes 3 405B | Nous | `nousresearch/hermes-3-llama-3.1-405b:free` | 131K | Untested |
| Free Models Router | OpenRouter | `openrouter/free` | 200K | Varies |

The Free Models Router (`openrouter/free`) automatically routes to the best available free model, providing built-in failover.

## Kestrel Use Case Analysis

### Scoring Volume: 18,000/month (600/day)

#### Scenario 1: Free Models Only ($0 balance)
- 50 RPD limit makes this impossible (need 600/day)
- Even with $10 purchase unlock (1,000 RPD), scoring 600 jobs leaves only 400 RPD headroom
- 20 RPM cap means scoring takes minimum 30 minutes/day (600 / 20 = 30 min)
- **Verdict:** Barely viable at 1,000 RPD, not viable at 50 RPD

#### Scenario 2: Free Models + $10 Lifetime Purchase
- 1,000 RPD unlocked -- 600 scores/day fits with 40% headroom
- 20 RPM cap means ~30 minutes minimum for daily scoring batch
- Risk: upstream provider throttling during peak hours can extend this
- Risk: any failed requests eat into the 1,000 RPD budget
- **Verdict:** Viable for scoring only, tight with no margin for other operations

#### Scenario 3: Paid Models + $10 Balance (Recommended Minimum)
- No platform RPD cap for paid models
- 10 RPS = 600 RPM theoretical, scoring completes in ~1 minute
- GPT-4o-mini at $0.15/$0.60 per M tokens = ~$0.81/month for 18,000 scores
- Balance consumed slowly -- $10 lasts ~12 months at this rate
- **Verdict:** Best value. $10 one-time covers scoring for a year

#### Scenario 4: $50 Balance
- 50 RPS = 3,000 RPM theoretical
- Overkill for scoring volume, but useful if user also runs generation tasks
- Enables concurrent scoring + research + generation without RPS contention
- **Verdict:** Only needed for power users running multiple concurrent operations

### With Batch Optimization (10 jobs/prompt)

Pre-filter (60% reduction) + batching reduces 600 scores to ~24 API calls/day:

| Tier | 24 calls/day | Fits RPD? | Time to Complete |
|------|-------------|-----------|-----------------|
| $0 free | 24 of 50 | Yes (48%) | ~2 min (20 RPM) |
| $10 free | 24 of 1,000 | Yes (2.4%) | ~2 min (20 RPM) |
| $10 paid | 24 of unlimited | Yes | <1 sec (10 RPS) |

With batch optimization, even the $0 free tier becomes viable for scoring alone. However, the user still needs headroom for non-scoring API calls (company research, interview prep, etc.).

## Recommendation for Kestrel

### Minimum Deposit: $10 (one-time)

**Rationale:**
1. Unlocks 1,000 RPD for free models permanently (vs 50 RPD at $0)
2. Enables paid model access at 10 RPS (no daily cap)
3. At GPT-4o-mini rates, $10 covers ~12 months of scoring
4. Even if the user only uses free models, the 20x RPD increase alone justifies the deposit
5. Balance never expires within a year (credits expire after 365 days)

### Default Preset Configuration

| User Type | Recommended Deposit | Strategy |
|-----------|-------------------|----------|
| Free tier | $0 | Groq/Cerebras/SambaNova fallback chain (bypass OpenRouter entirely) |
| Budget user | $10 | OpenRouter paid models (GPT-4o-mini), ~$0.81/month |
| Quality user | $10-25 | OpenRouter paid models (Sonnet for generation, mini for scoring) |
| Power user | $50+ | Higher RPS for concurrent operations |

### Implementation Notes for Kestrel

1. **Onboarding flow** should explain the $10 threshold clearly -- it is a one-time unlock, not a recurring cost
2. **Free preset** should route through Groq/Cerebras/SambaNova directly (not OpenRouter free models) to avoid the 50 RPD wall
3. **Budget preset** should default to OpenRouter + GPT-4o-mini, which requires any positive balance
4. **Monitor balance** via `/api/v1/auth/key` endpoint to warn users before balance hits $0 (402 errors affect even free models when balance is negative)
5. **Batch optimization is critical** -- with batching, even free tier works; without it, only paid tier is practical

## Discrepancies in Sources

Two different free RPD numbers appear across sources:
- **50 RPD** (no credits): Confirmed by OpenRouter FAQ, Novelcrafter docs, multiple community sources
- **200 RPD** (per model): Reported by CostGoat and MindStudio blog, may refer to per-model limits vs global limit

The most likely explanation: 200 RPD may be the per-model limit for users who have purchased credits but are using free model variants, while 50 RPD is the hard global limit for users with zero purchase history. The OpenRouter docs use template variables (`{FREE_MODEL_NO_CREDITS_RPD}`) making exact values hard to confirm from source code alone.

**Conservative assumption for Kestrel:** Use 50 RPD as the $0 tier limit and 1,000 RPD as the $10+ tier limit, as these are the most consistently reported across official and community sources.

## Sources

- [OpenRouter Rate Limits Documentation](https://openrouter.ai/docs/api/reference/limits)
- [OpenRouter FAQ](https://openrouter.ai/docs/faq)
- [OpenRouter Pricing](https://openrouter.ai/pricing)
- [OpenRouter Free Models Collection](https://openrouter.ai/collections/free-models)
- [OpenRouter Free Models Router](https://openrouter.ai/openrouter/free)
- [OpenRouter Principles](https://openrouter.ai/docs/guides/overview/principles)
- [CostGoat: OpenRouter Free Models (April 2026)](https://costgoat.com/pricing/openrouter-free-models)
- [CostGoat: OpenRouter Pricing Calculator (April 2026)](https://costgoat.com/pricing/openrouter)
- [ZenMux: OpenRouter API Pricing 2026](https://zenmux.ai/blog/openrouter-api-pricing-2026-full-breakdown-of-rates-tiers-and-usage-costs)
- [Novelcrafter: OpenRouter Free Models Help](https://www.novelcrafter.com/help/faq/ai-connections/open-router-free)
- [MindStudio: OpenRouter Free Models with Claude Code](https://www.mindstudio.ai/blog/open-router-free-models-claude-code-cost-reduction)
- [LiteLLM Issue #9035: Free model 429 errors](https://github.com/BerriAI/litellm/issues/9035)
