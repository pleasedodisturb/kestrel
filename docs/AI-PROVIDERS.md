---
layout: default
permalink: /docs/AI-PROVIDERS
title: AI Provider Guide
---

<p align="center"><img src="../assets/illustrations/hero-tropical.webp" alt="Kestrel" width="300"></p>

# AI Provider Guide

Kestrel uses AI for job scoring, skills analysis, interview prep, company research, and coaching. This guide explains your options.

---

## TL;DR

- **Free, works now:** Demo Mode (built in, no signup needed)
- **Best value:** OpenRouter with Claude Sonnet or GPT-4o ($1-3/month for typical job search use)
- **Free with caveats:** OpenRouter free models (some Chinese models have data collection concerns)
- **Maximum privacy:** Run a local model with Ollama (coming soon)

---

## "I already pay for ChatGPT / Claude. Can I use that?"

Short answer: not directly. Here's why.

**ChatGPT Plus ($20/month)** gives you access to GPT-4o through the ChatGPT interface (web, desktop app, mobile). But it doesn't give you an API key. The API is a separate product with separate billing. You'd need to sign up at platform.openai.com and add a payment method to get an API key.

**Claude Pro/Max ($20-100/month)** gives you access to Claude through claude.ai and Claude Code. Same story - the subscription doesn't include API access. The API is at console.anthropic.com with separate billing.

**The good news:** You don't need either of those. OpenRouter is cheaper and gives you access to both Claude and GPT (plus dozens of other models) through a single key.

---

## Option 1: Demo Mode (free, offline)

This is the default. Kestrel works completely offline with pre-generated responses. AI features return realistic but not personalized data - good enough to explore the dashboard and understand how everything works.

**What you get:** All features work. Scores, gap analysis, coaching, interview prep, company research - all functional with simulated data.

**What you don't get:** Personalized results. The scores aren't actually analyzing YOUR profile against the job. They're demo data.

**How to use:** It's the default. You don't need to do anything.

---

## Option 2: OpenRouter (recommended)

OpenRouter is a service that gives you one API key to access 200+ AI models from different providers (Anthropic, OpenAI, Google, Meta, Mistral, and more). Think of it as a universal adapter.

### Setup (5 minutes)

1. Go to [openrouter.ai](https://openrouter.ai)
2. Sign up (email or Google/GitHub login)
3. Add credits ($5 is plenty to start - lasts 1-2 months of job searching)
4. Go to Keys, create a new key
5. Copy the key (starts with `sk-or-`)
6. Open your Kestrel settings file:
   - On Mac: `open .env` in Terminal (from the Kestrel folder)
   - On Windows: `notepad .env`
7. Change these two lines:
   ```
   AI_PROVIDER=openrouter
   OPENROUTER_API_KEY=sk-or-your-key-here
   ```
8. Restart Kestrel: `docker compose down && docker compose up -d`

### Cost

Typical job search usage: **$1-3 per month.**

A single job scoring call costs about $0.002-0.01 depending on the model. If you score 20 jobs a day, that's roughly $0.10/day or $3/month.

You can set a spending limit on OpenRouter so you never get surprised.

### Choosing a model

Set this in your settings file:

```
OPENROUTER_MODEL=anthropic/claude-sonnet-4
```

**Recommended models (good quality, reasonable cost):**

| Model | Cost (per 1M tokens) | Quality | Speed | Notes |
|-------|---------------------|---------|-------|-------|
| `anthropic/claude-sonnet-4` | $3 in / $15 out | Excellent | Fast | Default. Best balance of quality and cost. |
| `openai/gpt-5` | $1.25 in / $10 out | Excellent | Fast | Cheaper than Claude, 400K context. |
| `google/gemini-2.5-flash-lite` | $0.10 in / $0.40 out | Very good | Very fast | Absurdly cheap. Best budget option. |
| `mistral/mistral-large` | $2 in / $6 out | Very good | Fast | EU-based provider (data stays in France). |

**Budget models (under $1/month for typical use):**

| Model | Cost (in/out per 1M) | Quality | Notes |
|-------|---------------------|---------|-------|
| `google/gemini-2.5-flash-lite` | $0.10 / $0.40 | Good | Best budget pick. Google's fast model. |
| `deepseek/deepseek-chat` | $0.32 / $0.89 | Very good | Frontier-class cheap. See privacy note below. |
| `meta-llama/llama-3.3-70b` | Varies by host | Good | Open source. GPT-4 level performance. |

### Free models on OpenRouter

OpenRouter offers ~30 free models. Rate-limited to 20 requests/minute and 200/day, but that's enough for personal job searching.

**Genuinely capable free models (not toy 7B models):**

| Model | Why it's good |
|-------|---------------|
| `qwen/qwen3.6-plus` | 1M context window, flagship quality. Alibaba model (see privacy notes). |
| `openai/gpt-oss-120b` | OpenAI's open-weight model. Apache 2.0 license. 120B MoE. |
| `nvidia/nemotron-3-super` | 120B hybrid architecture. Strong general reasoning. |
| `meta-llama/llama-3.3-70b` | 70B dense model. GPT-4 level. No data concerns (Meta, open weights). |
| `google/gemma-3-27b` | Google's open model. 27B. Solid for scoring tasks. |

You can also use `openrouter/free` as the model name - OpenRouter will auto-pick the best available free model per request.

**Caveats with free models:**
- They go offline sometimes. Don't rely on them for daily automated scans.
- Some are Chinese models (Qwen, DeepSeek) - see the privacy section below.
- Rate limits mean you can score about 200 jobs/day maximum.

---

## Option 3: Direct Anthropic API

If you want Claude specifically and don't want to go through OpenRouter:

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Add a payment method
3. Create an API key
4. In your settings file:
   ```
   AI_PROVIDER=anthropic
   ANTHROPIC_API_KEY=sk-ant-your-key-here
   ```

Cost is similar to OpenRouter. Slightly cheaper (no middleware markup) but you only get Claude models.

---

## Option 4: Direct OpenAI API

1. Go to [platform.openai.com](https://platform.openai.com)
2. Add a payment method
3. Create an API key
4. In your settings file:
   ```
   AI_PROVIDER=openai
   OPENAI_API_KEY=sk-your-key-here
   ```

---

## Option 5: Local models with Ollama (coming soon)

Run AI entirely on your machine. Zero cost, total privacy. Requires a Mac with 16GB+ RAM or a decent GPU.

This feature is on the roadmap. When available, you'll install [Ollama](https://ollama.com), download a model, and point Kestrel at it.

---

## Privacy and data concerns

### What Kestrel sends to AI providers

When you use real AI scoring, Kestrel sends:
- The job description text
- A summary of your profile (target roles, skills, location preferences)
- Your scoring criteria

It does NOT send: your full name, email, phone number, application history, or personal documents.

### Provider data policies

| Provider | Data retention | Trains on your data? | Where data is processed |
|----------|---------------|---------------------|------------------------|
| Anthropic (Claude) | 30 days for safety, then deleted | No | US |
| OpenAI (GPT) | 30 days for safety, then deleted | No (API usage) | US |
| Google (Gemini) | Varies by plan | No (API usage) | US/EU |
| Mistral | EU-hosted, GDPR compliant | No | EU (France) |
| OpenRouter | Routes to provider, minimal caching | No | Depends on provider |

### Chinese model providers (DeepSeek, Qwen, Yi)

Some of the best and cheapest models on OpenRouter are from Chinese companies. They're genuinely capable, but there are real privacy concerns you should understand.

**The facts:**
- DeepSeek's direct API sends data to servers in China. The CCP has legal authority to compel access to data stored in China. South Korea removed DeepSeek from app stores for transferring user data without consent. Italy banned it within 72 hours. 13 European jurisdictions opened investigations.
- Qwen (Alibaba) and Yi (01.AI) have similar regulatory obligations under Chinese law.
- Neither DeepSeek nor Qwen has a GDPR-required EU representative.

**The mitigation:** When you use DeepSeek or Qwen through OpenRouter, the data doesn't necessarily go to China. OpenRouter routes requests through hosting providers like Azure, Fireworks, or Together.ai (US/EU companies). With ZDR (Zero Data Retention) enabled, your data stays with these Western providers.

**How to use Chinese models safely:**
1. Enable ZDR in your OpenRouter account settings
2. Disable prompt logging (the 1% discount isn't worth the irrevocable license it grants)
3. Use Chinese models only through OpenRouter (never their direct APIs)
4. OpenRouter's ZDR mode will only route to providers with zero data retention

**Our recommendation:** For job search data (which includes your career history, skills, and target roles), use Anthropic, OpenAI, Google, or Mistral through OpenRouter. The cost difference is $1-3/month and your data stays with providers that have clear, enforceable privacy policies.

If you want Chinese model quality at zero risk, wait for local model support (Ollama) - you can run DeepSeek and Qwen locally with zero data leaving your machine.

### OpenRouter's own data policy

| Setting | What's stored | Risk level |
|---------|--------------|------------|
| Default (no logging) | Metadata only (timestamps, model, token counts) | Low |
| Prompt logging ON | Your prompts + responses stored on OpenRouter | Medium |
| "May use for training" ON | Irrevocable commercial license to your data | **High - never enable this** |
| ZDR enabled | Nothing at provider level | Lowest |

**Recommended settings:** Keep prompt logging OFF. Enable ZDR for anything sensitive. Never enable "OpenRouter may use my data."

---

## Quick decision guide

| Your situation | Recommended provider |
|----------------|---------------------|
| Just exploring Kestrel | Demo Mode (default, free) |
| Ready for real scoring, want best quality | OpenRouter + Claude Sonnet |
| On a tight budget | OpenRouter + Gemini Flash |
| Maximum privacy, EU data residency | OpenRouter + Mistral Large |
| Zero data exposure | Demo Mode or local Ollama (coming soon) |
| Already have OpenAI API access | Direct OpenAI |
| Already have Anthropic API access | Direct Anthropic |
