# How Kestrel Uses AI (and Why You Don't Need a PhD to Set It Up)

You know how you use ChatGPT or Claude to ask questions? Kestrel does the same thing — but automatically, behind the scenes, to score jobs, prep you for interviews, and analyze your career gaps.

The difference: ChatGPT is like a TV set — you watch what's on. Kestrel needs a **power source** — an AI service that it can call programmatically, hundreds of times, without you typing anything.

---

## The Electricity Analogy

Think of AI providers like electricity providers:

- **You don't generate your own electricity** — you pick a provider, they send power through the wire, you pay for what you use
- **The light switch works the same** no matter which company provides the power
- **Some providers are cheaper**, some are greener, some are local (solar panels on your roof)

Kestrel works the same way. Pick a provider, connect it, and every feature — scoring, coaching, interview prep — works identically regardless of which AI is behind it.

---

## Your Options (from simplest to most private)

### 1. Demo Mode — Free, Works Offline

**Cost:** Free forever | **Privacy:** Perfect — nothing leaves your device

This is the default. Kestrel works completely offline with pre-generated responses. AI features return realistic but not personalized data — good enough to explore and understand how everything works.

*Best for:* Trying Kestrel before committing to an AI provider.

### 2. OpenRouter — One Account, 300+ Models

**Cost:** ~$3-10/month for typical use | **Privacy:** Good (your data is not used for training)

OpenRouter is like a phone plan for AI. You load credits, Kestrel uses them when scoring jobs or preparing interviews. One account gives you access to Claude, GPT, Gemini, and hundreds of other models.

**Setup:** Click "Connect to OpenRouter" in Settings → log in → done. No copying API keys.

*Best for:* Most users who want quality AI without complexity.

### 3. Direct Anthropic (Claude) — Best for Power Users

**Cost:** ~$4-10/month | **Privacy:** Excellent (7-day data retention, shortest in industry)

Connect directly to Claude's API for the best privacy and lowest cost. Kestrel uses **prompt caching** — your profile is sent once and remembered, so scoring 50 jobs costs 88% less than sending your profile each time.

*Best for:* Users who want the best privacy-cost balance.

### 4. Ollama — Run AI on Your Own Computer

**Cost:** Free (after hardware) | **Privacy:** Perfect — nothing leaves your machine

Install [Ollama](https://ollama.com), download a model, and Kestrel talks to it on your computer. No internet needed, no data sent anywhere, no monthly bill.

**The trade-off:** You need a decent computer (16GB+ RAM recommended), and local models aren't quite as smart as Claude or GPT. Scoring is good, deep analysis is weaker.

*Best for:* Privacy maximalists, offline users, developers.

---

## What About My ChatGPT / Claude Subscription?

Short answer: you can't use it directly.

Your $20/month ChatGPT Plus or Claude Pro subscription gives you access through their chat interface — like a gym membership that only works at one location. The API is a separate service with separate billing, like getting a personal trainer.

**The good news:** You don't need those subscriptions. OpenRouter gives you access to both Claude and GPT (plus dozens more) through a single account, often cheaper than a subscription.

---

## Privacy: Where Does My Data Go?

Kestrel sends job descriptions and your profile summary to whichever AI provider you choose. Here's what happens to that data:

| Provider | Trains on your data? | How long kept? | Human review? |
|----------|---------------------|----------------|---------------|
| **Ollama (local)** | No — stays on your computer | Forever (your disk) | No |
| **Anthropic (Claude)** | Never | 7 days | No |
| **OpenRouter** | No (unless you enable logging) | Not stored | No |
| **Gemini (paid)** | No | 55 days | No |
| **Gemini (free)** | **Yes** | **Indefinite** | **Yes** |

**The rule of thumb:** If you're on a paid tier, your data is not used for training. Free tiers are riskier — especially Google's, which explicitly uses free-tier data to improve their models.

Kestrel shows a privacy indicator (green/yellow/red shield) next to each provider so you always know the trade-off.

### PII Protection

Kestrel can automatically strip personal information (phone numbers, email addresses, profile URLs) from prompts before sending them to any AI provider. The AI never sees your real contact details — it works with placeholders like `[EMAIL_1]` and `[PHONE_1]`, and Kestrel puts the real values back in the response.

---

## How Much Does It Cost?

AI pricing is measured in "tokens" (roughly 4 characters = 1 token), but you don't need to think about that. Here's what matters:

| Action | Approximate cost |
|--------|-----------------|
| Score one job | $0.005 - $0.02 |
| Interview prep session | $0.02 - $0.05 |
| Company research | $0.02 - $0.05 |
| Gap analysis | $0.01 - $0.03 |
| Monthly budget (active job search) | **$3 - $10** |

For context: a single coffee costs more than a month of AI-powered job searching.

With prompt caching enabled, discovery sweeps (scoring 50+ jobs at once) cost 88% less because Kestrel reuses your cached profile instead of re-sending it each time.

---

## EU Users: Special Considerations

If you're in the EU, data privacy laws (GDPR) add extra considerations:

- **Recommended:** Anthropic, Ollama (local), or Mistral (French company, EU data centers)
- **Fine with caution:** OpenRouter, Gemini (paid tier only)
- **Avoid:** Gemini free tier (banned in EU by Google's own terms), DeepSeek (data stored in China)

Kestrel will eventually support [Mistral](https://mistral.ai) as a dedicated EU-sovereign provider — French-hosted, GDPR-native, with self-serve data processing agreements.

---

## Quick Start

1. **Try Demo Mode** — explore Kestrel with pre-generated AI responses
2. **When ready:** Click "Connect to OpenRouter" in Settings
3. **Load $5 in credits** — that's roughly 500 job scores
4. **Start discovering** — Kestrel handles the rest

No PhD required.
