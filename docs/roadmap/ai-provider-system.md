# AI Provider System

*Part of the [Kestrel roadmap](../../ROADMAP.md).*

## Goal

Choose which AI service processes your data, and switch anytime without losing anything.

## What This Delivers

Kestrel supports eleven AI providers: OpenRouter, Anthropic, OpenAI, Together, Groq, xAI, Gemini, Ollama, Mistral, Hugging Face, and a mock provider for testing. You bring your own API key to whichever provider you trust. If you change your mind, switch providers in settings and everything keeps working. Your scores, pipeline, and data stay exactly where they are.

Each provider has a privacy tier that tells you upfront what happens to your data. Some providers offer zero-data-retention guarantees. Others use free-tier data for training. Kestrel shows you this information before you choose, so you make an informed decision rather than discovering the policy after the fact.

Not every task needs the same model. Kestrel uses complexity-tier routing to match the AI model to the job. Simple classification tasks (is this job relevant?) go to small, fast models. Nuanced tasks (write a cover letter that sounds like you) go to larger, more capable models. This happens automatically based on the operation type, and you can override it if you prefer a specific model for everything.

If your primary provider is unavailable or returns an error, a fallback chain tries the next provider on your list. You configure the chain once and Kestrel handles the rest. The response cache stores encrypted results locally so repeated identical requests do not cost extra tokens. Cache entries expire after seven days.

For providers that support it, Kestrel uses prompt caching to reduce costs on repeated prompts. Your profile and scoring instructions are identical across every call, so the cached prefix gets a 90% discount on subsequent requests.

## How It Works

All providers implement the same interface: `complete()` for text generation, `score()` for job evaluation, and optional methods for batch scoring and embeddings. A factory pattern registers each provider by name. When Kestrel needs to call an AI, it asks the factory for the configured provider and gets back an object that speaks the same language regardless of which service is behind it.

The provider selection flows from the `AI_PROVIDER` setting or from credentials stored in the database. Complexity tiers (Simple, Standard, Complex) map to different models within each provider. The `CachedAIProvider` wrapper sits in front of any provider and transparently caches responses using Fernet encryption in a local SQLite database.

## Current Status

*Shipped in [v0.5.0](../../CHANGELOG.md#050-2026-04-16)*

All eleven providers are functional with bring-your-own-key support, privacy tier metadata, complexity routing, encrypted caching, and fallback chains. The mock provider enables full testing and demo mode without any API key. OpenRouter OAuth PKCE flow allows browser-based key provisioning.

## Related Milestones

- **[Scoring Engine](scoring-engine.md)** -- Providers execute the scoring prompts
- **[Cost Control](cost-control.md)** -- Presets select which provider tier to use
- **[PII Safety Boundary](pii-safety-boundary.md)** -- Privacy layer controls what data reaches providers

---

*For Contributors*

## Architecture

The AI provider system lives in `src/career_os/ai/` with the following structure:

- `src/career_os/ai/base.py` -- `AIProvider` abstract base class defining the interface: `complete()`, `score()`, optional `batch_score()`, `embed()`. Also defines `ComplexityTier` enum (SIMPLE, STANDARD, COMPLEX) and `ProviderQuotaError`.
- `src/career_os/ai/factory.py` -- `_PROVIDER_REGISTRY` dict maps provider names to constructors. `get_ai_provider()` resolves credentials from env vars or database and returns an instance.
- `src/career_os/ai/cache.py` -- `CachedAIProvider` wrapper. Fernet-encrypted SQLite cache, SHA-256 keyed, 7-day TTL.
- `src/career_os/ai/pii_masking.py` -- Regex-based masking of emails, phone numbers, LinkedIn URLs, and GitHub URLs before external calls.
- `src/career_os/ai/privacy.py` -- Privacy registry with per-provider metadata (tier, training policy, GDPR status, retention).
- Provider implementations: `mock_provider.py` (1,844 lines of hardcoded fixtures), `openrouter_provider.py`, `anthropic_provider.py`, `ollama_provider.py`, `together_provider.py`, plus additional providers for OpenAI, Groq, xAI, Gemini, Mistral, and Hugging Face.

Adding a new provider requires creating a module that subclasses `AIProvider` and adding one entry to `_PROVIDER_REGISTRY` in the factory.

## Research & Decisions

Annotated links to research and reference documents:

- [LLMs, Tokens, and Privacy](../research/llms-tokens-privacy.md) -- 2026 LLM API landscape: pricing drops, BYOK strategy, EU sovereignty, and prompt caching economics
- [Provider Privacy Audit](../research/provider-privacy-audit.md) -- Per-provider privacy trust matrix: training policies, retention periods, ZDR status, GDPR compliance
- [Free Model Landscape 2026](../research/free-model-landscape-2026.md) -- Free tier comparison across seven providers: rate limits, quality, and which ones work for structured scoring
- [OpenRouter Rate Limits](../research/openrouter-rate-limits.md) -- Rate limit tiers at $0/$10/$50 balance thresholds and what changes at each level
- [AI Providers Reference](../reference/AI-PROVIDERS.md) -- User-facing provider guide with setup instructions and recommendations per provider

## BMAD Integration

**PRD Status:** Not started

A PRD would specify the provider onboarding checklist, privacy tier classification criteria, cache eviction policies, and the complexity routing decision matrix.

To start a PRD: `/bmad-create-prd` in Claude Code.
See the [planning hierarchy](inventory.md#how-planning-works) for how PRDs connect to implementation.
