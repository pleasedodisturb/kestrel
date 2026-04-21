# Free Model Landscape (April 2026)

*Research date: 2026-04-21 | Use case: 600 structured JSON scoring calls/day, ~3K input + 500 output tokens each*

## Provider Comparison

| Provider | Free Tier | Daily Limit | RPM | OpenAI-Compatible | Base URL | Best Free Model | JSON Quality |
|----------|-----------|-------------|-----|-------------------|----------|-----------------|-------------|
| **Google Gemini** | Permanent | 1,000 RPD (Flash-Lite) | 10-15 | No (own SDK) | `generativelanguage.googleapis.com` | Gemini 2.5 Flash-Lite | HIGH |
| **Groq** | Permanent | 1,000 RPD per model | 30 | Yes | `api.groq.com/openai/v1` | Llama 3.3 70B | MEDIUM-HIGH |
| **Cerebras** | Permanent | 14,400 RPD (1M tok/day) | 30 | Yes | `api.cerebras.ai/v1` | Llama 3.3 70B | MEDIUM-HIGH |
| **SambaNova** | Permanent | Unlimited (rate-limited) | 10-30 | Yes | `api.sambanova.ai/v1` | Llama 3.3 70B / 405B | MEDIUM-HIGH |
| **OpenRouter** | Permanent | 50 RPD (no balance) | 20 | Yes | `openrouter.ai/api/v1` | Llama 3.3 70B `:free` | MEDIUM-HIGH |
| **xAI (Grok)** | $25 credits + $150/mo (data sharing) | Credit-based | N/A | Yes | `api.x.ai/v1` | Grok 4.1 Mini | HIGH |
| **Together.ai** | $25 credits only | Credit-based | N/A | Yes | `api.together.xyz/v1` | Llama 3.3 70B | MEDIUM-HIGH |
| **OpenAI** | $5 credits only | Credit-based | N/A | Yes (native) | `api.openai.com/v1` | GPT-4o-mini ($0.15/M in) | HIGH |

## Key Findings

### 1. OpenRouter free tier is NOT viable as primary (50 RPD)
With no balance, OpenRouter limits to 50 requests/day. Useless for 600 scores/day. However, with a $10 deposit, rate limits unlock and you get access to free-tier models at higher RPM. OpenRouter is the **convenience play**, not the **free play**.

### 2. Groq + Cerebras + SambaNova = 3,000+ free RPD combined
All three are OpenAI-compatible, all run Llama 3.3 70B, all have permanent free tiers. A fallback chain across these three easily covers 600 calls/day at $0.

### 3. Gemini Flash-Lite has the best quality-per-free-call
1,000 RPD free with HIGH JSON quality. But requires Google's own SDK (not OpenAI-compatible), which means a separate provider implementation.

### 4. GPT-4o-mini is near-free even when paying
At $0.15/M input + $0.60/M output, 600 calls/day costs ~$0.81/month. Below the threshold where "free" matters.

### 5. xAI's $150/mo credits are a privacy trap
The data sharing program is **irrevocable** — once you opt in, you cannot opt out. All API interactions permanently shared with xAI for training. See `provider-privacy-audit.md`.

## Provider-Specific Notes

### Groq
- Fastest inference (300+ tokens/second)
- 6K TPM limit may bottleneck batch scoring windows
- Rate limits tracked per model (can split across models for more headroom)
- No credit card required

### Cerebras
- 1M tokens/day across all models
- 14,400 RPD — most generous request limit
- Unused tokens don't roll over
- No credit card required

### SambaNova
- Unlimited requests (rate-limited at 10-30 RPM depending on model)
- Llama 3.1 405B available free (10 RPM)
- $5 initial credits on top of free tier
- Custom RDU hardware

### Google Gemini
- EU/EEA/UK/Swiss users **cannot use free tier** per Google's Additional Terms
- Free tier data is used to train Google's models and may be reviewed by humans
- Paid tier: no training by default, 55-day retention
- Requires separate SDK implementation

## Recommendation for Kestrel

**Default path:** OpenRouter with $10 deposit (one key, 400+ models, unlocked limits)

**Free fallback chain:** Groq → Cerebras → SambaNova (all OpenAI-compatible, combined 3,000+ RPD)

**Future addition:** Gemini Flash-Lite (separate SDK, high quality, generous free tier — but EU restrictions apply)

## Sources

- [Google Gemini Rate Limits](https://ai.google.dev/gemini-api/docs/rate-limits)
- [Groq Free Tier](https://tokenmix.ai/blog/groq-free-tier-limits-2026)
- [Cerebras Free Tier](https://aicreditmart.com/ai-credits-providers/cerebras-free-tier-1-million-tokens-day-guide-2026/)
- [OpenRouter Free Models](https://openrouter.ai/collections/free-models)
- [xAI API](https://x.ai/api)
- [Together AI Pricing](https://www.together.ai/pricing)
- [OpenAI API Pricing](https://developers.openai.com/api/docs/pricing)
- [Free AI APIs 2026 Guide](https://awesomeagents.ai/tools/free-ai-inference-providers-2026/)
- [Gemini API Terms](https://ai.google.dev/gemini-api/terms) (EU restriction)
