---
title: "AI Costs and Privacy"
description: "What Kestrel costs to run, which tiers exist, and what happens to your data — explained like a friend would"
---

# AI Costs and Privacy

Running AI-powered job scoring sounds expensive. It doesn't have to be. Kestrel is designed so you can start for free, stay free as long as you want, and spend under $10/month if you decide to pay. This guide explains how the pricing works, what "free" actually means, and what happens to your data with each provider — because "free" doesn't always mean "no cost."

## The Short Version

- **Demo Mode** lets you explore everything with zero setup — no API key, no account, no credit card
- **Free tier** uses three AI providers that offer permanent free access — enough for daily job scanning
- **$10 on OpenRouter** unlocks premium models and removes rate limits — most users never spend more
- **Privacy varies by provider** — some train on your data, some don't. Kestrel tells you which is which before you choose
- **Batch scoring, caching, and smart routing** keep costs low even for heavy users

## Start Free: Demo Mode

When you first install Kestrel, it runs in Demo Mode. No API key needed. The AI provider is set to `mock`, which means scoring returns realistic-looking results generated locally — no network calls, no tokens burned, no data leaving your machine.

Demo Mode is not a crippled trial. You can:

- Add your profile, skills, and job preferences
- Browse and filter discovered jobs
- See how the scoring pipeline works end to end
- Set up the mobile app and web dashboard

Think of it like test-driving a car with the engine off — you can sit in every seat, check the dashboard, adjust the mirrors. You just can't drive yet.

When you're ready for real AI scoring, you add an API key and Kestrel switches to live mode. Nothing else changes.

## Understanding the Tiers

Kestrel has five cost presets. You pick one during setup and can change it anytime.

### Free — $0/month

Uses a rotation of three AI providers that offer permanent free tiers: Groq, Cerebras, and SambaNova. All three run Meta's Llama 3.3 70B, a capable open-source model. Combined, they give you over 3,000 free API calls per day — more than enough for Kestrel's daily scanning.

**What you get:** Real AI scoring on every discovered job. Solid quality for pass/fail decisions ("is this job worth a closer look?").

**What you give up:** Rate limits mean scoring happens in waves rather than all at once. If one provider is busy, Kestrel falls back to the next. You might notice a slight delay during peak hours. The models are good but not the best — think Honda Civic, not BMW.

**Data privacy:** All three providers are OpenAI-compatible inference hosts running open-source models. They process your job descriptions (public data) but not your resume or cover letters.

### Budget — $1-5/month

Adds a $10 deposit on OpenRouter, which unlocks access to 400+ models including GPT-4o-mini at $0.15 per million input tokens. At that price, scoring 600 jobs per day costs about $0.81/month. The $10 deposit lasts months.

**What you get:** Better model quality, faster responses, higher rate limits. GPT-4o-mini produces noticeably better structured JSON than Llama 3.3.

**What you give up:** You need an OpenRouter account and a one-time $10 deposit. That's it.

**Why OpenRouter?** One account, one API key, access to hundreds of models. Kestrel uses it as the default on-ramp because it's the simplest path from free to paid. You're not locked in — you can switch to any provider anytime.

### Quality — $5-25/month

Uses different models for different tasks. Job scoring (high volume, lower stakes) uses a budget model. Cover letters, interview prep, and company research (low volume, higher stakes) use a stronger model like Claude Sonnet or Opus.

This is called **hybrid routing** — matching the model to the task, like using a sedan for commuting and a truck for moving day.

| Task | Volume | Model Tier | Monthly Cost |
|------|--------|-----------|-------------|
| Job scoring | ~600/day | Budget (GPT-4o-mini) | ~$1-5 |
| Company research | ~10/week | Standard (Sonnet) | ~$5 |
| Interview prep | ~3/week | Standard (Sonnet) | ~$3 |
| Cover letters | ~3/week | Quality (Opus) | ~$3 |
| **Total** | | **Hybrid** | **~$12-25** |

Compare this to using the strongest model for everything: $300+/month. Hybrid routing saves 90%+ by being thoughtful about where quality matters most.

### Private — $0 + your hardware

Runs models locally on your own machine using Ollama, or uses providers with contractual zero-data-retention (ZDR) guarantees like Anthropic's API.

**Who this is for:** People who don't want any data — not even job descriptions — leaving their machine. Journalists, people in sensitive industries, or anyone who simply values privacy as a principle.

**The tradeoff:** Local models need a decent GPU (or a patient attitude — CPU inference is slow). Cloud ZDR providers cost more than OpenRouter but guarantee your data isn't stored or trained on.

### Custom — you decide

Full control over which provider handles which operation. Want Groq for scoring, Anthropic for cover letters, and Ollama for everything that touches your resume? You can wire that up.

Most people never need this. It exists because Kestrel is self-hosted software — your instance, your rules.

## What "Free" Really Means

Free AI providers aren't charities. They have business models, and understanding them helps you make informed choices.

**Groq, Cerebras, SambaNova** offer free tiers to attract developers. They make money from paid enterprise customers. Your free API calls help them benchmark load and demonstrate their hardware. They run open-source models (Llama), so there's no proprietary training angle — they're selling speed, not data.

**OpenRouter with no balance** gives you 50 requests per day. That's enough to test with, not enough to run daily scoring. With a $10 deposit, limits unlock. OpenRouter is a router, not a model provider — it passes your request to the underlying provider (Groq, Anthropic, OpenAI, etc.) and takes a small margin.

**Google Gemini's free tier** is the most generous in raw quality — but it comes with a catch. Free-tier data is used to train Google's models and may be reviewed by human annotators. Paid tier doesn't train on your data. Also, EU/EEA/UK/Swiss users cannot use the free tier at all per Google's terms. Kestrel doesn't use Gemini by default for these reasons.

**xAI's $150/month credits** are a privacy trap. Their "data sharing program" is **irrevocable** — once you opt in, you cannot opt out, ever. All your API interactions are permanently shared with xAI for training. Kestrel will warn you before enabling any xAI integration.

## When to Pay

Here's the honest answer: you probably don't need to.

The free tier handles Kestrel's core job — scanning and scoring hundreds of positions daily. If that's all you need, stay free. Permanently.

Consider paying ($10 one-time deposit) when:

- **You want faster, more reliable scoring** — paid models have higher rate limits and better uptime
- **You're generating cover letters or interview prep** — these benefit noticeably from stronger models
- **You want a single provider** — OpenRouter with a balance is simpler than rotating three free providers
- **You're applying to competitive roles** — the quality difference between Llama 3.3 and GPT-4o-mini shows up most in nuanced scoring dimensions like career trajectory and company culture fit

The $10 deposit is not a subscription. It's credit that depletes as you use it. At Budget tier rates, $10 lasts 2-10 months depending on usage.

## Privacy: Who Sees Your Data?

This matters. When Kestrel sends a job description to an AI for scoring, that text leaves your machine. Here's what happens to it, by provider.

### The Trust Matrix

| Provider | Trains on API data? | How long kept? | Zero-data-retention option? |
|----------|-------------------|----------------|---------------------------|
| **Anthropic** | No | 7 days | Yes (via addendum) |
| **OpenAI** | No (since 2023) | 30 days | Enterprise only |
| **Google (paid)** | No | 55 days | Vertex AI only |
| **Google (free)** | **Yes** | Indefinite | No |
| **Groq/Cerebras/SambaNova** | Running open-source models | Varies | N/A (inference only) |
| **xAI (paid)** | No | 30 days | No |
| **xAI (data sharing)** | **Yes, irrevocably** | Permanent | No |

### The Good News About Job Scoring

Here's something that makes the privacy picture much simpler: job scoring only uses **public data**. Job descriptions are marketing copy that companies posted publicly on job boards. Your profile data goes into the system prompt, but it's metadata (skills, experience level, preferences) — not your resume, not your name, not your contact info.

The privacy-sensitive operations — cover letters, interview prep, resume tailoring — are low volume (a few per week, not hundreds per day). That means you can use the cheapest provider for the expensive operation (scoring) and reserve the privacy-conscious provider for the sensitive operations (generation). Cost optimization and privacy are not in conflict.

### What Kestrel Does

- Kestrel shows you which provider is handling each operation before it runs
- Private data (resume text, cover letters) is never sent to free-tier providers by default
- You can override any routing decision in settings
- All provider choices are logged locally so you can audit what went where

## Realistic Monthly Costs

Here's what real usage looks like across different profiles.

### Casual Job Seeker

Checks in a few times a week, reviews top matches, applies to 2-3 jobs.

| | Free Tier | Budget Tier |
|---|---|---|
| Job scoring | $0 | $0.30 |
| Cover letters (2/week) | $0 (not available) | $0.10 |
| **Monthly total** | **$0** | **~$0.40** |

### Active Job Seeker

Daily scanning, 5-10 applications per week, interview prep.

| | Free Tier | Budget Tier | Quality Tier |
|---|---|---|---|
| Job scoring (600/day) | $0 | $0.81 | $0.81 |
| Cover letters (8/week) | $0 | $0.40 | $1.20 |
| Interview prep (4/week) | $0 | $0.30 | $1.00 |
| Company research (5/week) | $0 | $0.20 | $1.50 |
| **Monthly total** | **$0** | **~$1.70** | **~$4.50** |

### Power User

Maximum scanning, multiple profiles, aggressive application volume.

| | Budget Tier | Quality Tier |
|---|---|---|
| Job scoring (1,500/day) | $2.00 | $2.00 |
| Cover letters (20/week) | $1.00 | $3.00 |
| Interview prep (10/week) | $0.75 | $2.50 |
| Company research (15/week) | $0.50 | $3.75 |
| **Monthly total** | **~$4.25** | **~$11.25** |

These estimates assume all optimizations are active (batch scoring, prompt caching, pre-filtering). Without optimizations, multiply by roughly 10x.

## Tips: How Kestrel Keeps Costs Low

You don't need to configure any of this — it all happens automatically. But understanding it helps you appreciate why costs stay low even with heavy usage.

### Pre-filtering (Saves ~60%)

Before any AI call, Kestrel filters jobs using simple keyword and title matching. A machine learning engineer posting won't get scored if you're looking for product management roles. This eliminates about 60% of jobs before AI touches them — no tokens spent, no time wasted.

### Batch Scoring (Saves ~80%)

Instead of sending one job per API call, Kestrel bundles 10 jobs into a single prompt. The AI scores all ten at once. Research from April 2026 shows this approach loses less than 2 percentage points of accuracy for classification tasks — a trade most users would happily make for an 80% cost reduction.

To prevent position bias (jobs listed first scoring differently than jobs in the middle), Kestrel randomizes the order within each batch.

### Prompt Caching (Saves ~90% on repeats)

Your profile and scoring instructions are identical across every call. Anthropic's prompt caching "remembers" this prefix for 5 minutes. The first call pays full price; subsequent calls get a 90% discount on the cached portion. When you're scoring 60 batches in a row, that adds up fast.

### Batch API (Saves 50% more)

For nightly discovery scoring (not time-sensitive), Kestrel can use Anthropic's and OpenAI's Batch APIs. Results arrive within 24 hours at half the cost. Since discovery runs overnight anyway, the delay is invisible.

### Smart Model Routing (Saves 60-95%)

Not every question needs the smartest model. "Is this job relevant?" is a simple yes/no — a small, fast model handles it perfectly. "Write a compelling cover letter for this specific role" benefits from a larger model that understands nuance. Kestrel matches the model to the task automatically.

### Fallback Chain Ordering (Avoids Surprise Bills)

Kestrel can chain providers so that if one is down or out of quota, scoring automatically falls through to the next. You set this with `AI_PROVIDER_FALLBACK`, a comma-separated list:

```
AI_PROVIDER_FALLBACK=groq,cerebras,sambanova,openrouter,anthropic
```

The order is the whole game, and there's one rule worth burning into memory: **whatever sits at the end of your chain is what you pay when everything before it runs out.** A chain tries each provider in turn and stops at the first one that answers. So on a normal day the cheapest provider at the front does all the work. But the day your free providers hit their daily limit, every request marches down the chain to the last entry — and if that last entry is a premium model, you can wake up to a bill for a full day of scoring at premium rates instead of the ~$0 you expected.

The fix is simply to order the chain **cheapest-capable first, premium last** — and to make the premium tail-end a deliberate choice, not an accident:

- **Front of the chain:** the free providers (Groq, Cerebras, SambaNova) or a cheap paid model. This does the everyday work.
- **Middle:** a cheap paid catch (for example, OpenRouter pointed at an inexpensive open model like Llama 3.3 70B via `OPENROUTER_MODEL`) so an exhausted free tier lands somewhere cheap, not somewhere expensive.
- **End:** a premium provider (Anthropic direct, or OpenRouter with a premium model) as a genuine last resort. It should fire rarely — only when everything cheaper has failed.

> A worked example of getting this wrong: if your chain is `mistral,together,anthropic` and Mistral and Together both run dry, **100% of that day's scoring bills on premium Claude** — often 20-50× what a cheap model would have cost. Adding one cheap provider before the premium tail (`mistral,together,openrouter,anthropic`, with `OPENROUTER_MODEL` set to a cheap Llama) turns that same failure day from dollars into cents.

Two settings make the tail-end intentional rather than accidental:

- `OPENROUTER_MODEL` — OpenRouter is an aggregator that can serve both cheap open models and premium ones. Set this explicitly. If you want OpenRouter as a *cheap* catch, point it at something like `meta-llama/llama-3.3-70b-instruct`; if you want it as your *premium* unlock, point it at a premium model and put it at the end of the chain.
- Provider position — the position in `AI_PROVIDER_FALLBACK` decides when each provider is reached, so a premium provider belongs last.

### All Together

These optimizations stack. Applied together, they reduce the baseline cost of scoring 600 jobs/day from ~$99/month to ~$5.40/month — a 94.5% reduction. On the free tier, the cost is $0.

```
Baseline:     $99/mo  (600 individual calls, no optimization)
Pre-filter:   $40/mo  (240 jobs survive)
+ Batching:   $12/mo  (24 API calls instead of 240)
+ Caching:    $8/mo   (90% off repeated prefix)
+ Batch API:  $5.40/mo (50% off async processing)
Free tier:    $0/mo   (Groq + Cerebras + SambaNova rotation)
```

## Summary

Kestrel is built on the principle that AI-powered job searching shouldn't require a subscription or a leap of faith about your data. Start in Demo Mode, move to free when you're ready for real scoring, and pay $10 when — if — you want better quality. The optimizations that make this possible aren't experimental tricks; they're engineering decisions baked into every API call.

Your data, your providers, your rules. That's the point of self-hosting.
