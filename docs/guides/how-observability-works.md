---
title: "How Observability Works"
description: "A guide to how Kestrel watches its own AI — and why you'd want that"
---

# How Observability Works

## The Problem

Imagine you're a chef running a busy restaurant. You send dishes to every table, but you can't see the kitchen. You don't know how long each dish takes to prepare, which ingredients cost the most, or whether the sous chef has been quietly burning the garlic all night. Customers complain, and all you can say is: "I'll look into it."

That's what running an AI system without observability feels like. Kestrel makes dozens of AI calls — scoring jobs, analyzing gaps, coaching you on interview prep, researching companies. Each call goes to a language model, and each model response is slightly different every time. Sometimes the scoring is spot-on. Sometimes it's oddly generous. Sometimes it takes 8 seconds instead of 2. Without observability, you're flying blind.

Observability is the kitchen camera. It shows you every AI call — what went in, what came out, how long it took, how much it cost — so you can understand what's happening and fix what's broken.


## What Kestrel Tracks

When observability is enabled, every AI call gets a **trace** — a detailed record of what happened:

### The Generation

At the core, every AI provider call (OpenRouter, Anthropic, Together, Ollama) records:

- **Model**: Which AI model handled this request (Claude Sonnet, Llama 3, etc.)
- **Input**: The first 500 characters of what was sent (truncated for privacy)
- **Output**: The first 500 characters of what came back
- **Token usage**: How many tokens went in and came out — this is how AI bills you
- **Latency**: How long the model took to respond

Think of this like a receipt for every AI interaction.

### The Layers

But a generation doesn't happen in isolation. Before your prompt reaches the AI model, it passes through layers:

**PII Masking** strips sensitive information. If your resume mentions your email address, it gets replaced with `[EMAIL_1]` before the AI ever sees it. The trace records *how many* PII items were detected (say, 3 emails and a phone number), but never the actual values. That's the whole point of masking.

**Caching** checks whether we've asked this exact question before. If you score the same job twice, the second time is instant — served from an encrypted local cache. The trace records whether it was a **hit** (served from cache, free) or **miss** (sent to the AI, costs tokens).

**Route context** adds metadata about *who* asked and *why*. Your profile ID, the scoring session, what kind of AI feature was used (scoring? coaching? gap analysis?). This lets you filter traces later — "show me all scoring calls for engineering roles last week."

### The Full Picture

```
You click "Score this job"
  └── Route adds your profile ID and session info
        └── PII masking strips your email (records: 1 detection)
              └── Cache checks (records: miss)
                    └── Claude Sonnet generates a score
                          (records: model, tokens, latency, input/output)
```

All of this shows up as a single trace in the Langfuse dashboard, with each layer as a nested span. You can see exactly where time was spent and what decisions were made.


## Why This Matters

### Cost Visibility

AI models charge by the token. Without tracking, your monthly bill is a mystery. With observability, you can see:

- Which features consume the most tokens (scoring is expensive — it involves long prompts)
- Whether caching is actually saving you money (a 60% cache hit rate means 60% of repeat calls are free)
- Whether complexity routing is working (simple tasks like classification should use cheaper models)

### Debugging

When a score looks wrong, you need to see what the AI actually received and returned. Observability gives you the conversation history — truncated for privacy, but enough to spot issues like "the job description was garbled" or "the model returned a score of 15 on a 0-10 scale."

### Privacy Verification

Kestrel promises that PII is masked before it reaches external AI providers. Observability lets you verify this claim. If the PII detection count is consistently 0 on prompts that should contain emails and phone numbers, something is broken. If it's catching 5-10 items per scoring call, the masking is working.

### Provider Comparison

Running multiple AI providers? Observability shows you side-by-side how they compare on latency, token efficiency, and output quality. Maybe Anthropic is 40% faster but costs 2x more. Maybe Together.ai is great for simple tasks but struggles with complex scoring. The data tells the story.


## How to Turn It On

Observability is completely optional. Kestrel works exactly the same with or without it.

**To enable it:**

1. Start the Langfuse stack (a one-time Docker setup — see [Observability Setup](../reference/observability.md))
2. Set three environment variables in your `.env` file
3. Install the Python SDK: `pip install kestrel-app[observability]`
4. Restart Kestrel

That's it. The `Langfuse observability enabled` message in the logs confirms it's working. Open `http://localhost:3100` to see your traces.

**To disable it:** Remove the environment variables and restart. All observability code becomes a no-op — zero overhead, zero network calls, zero anything.


## What We Don't Track

Some things are deliberately excluded:

- **Full prompts and responses** — only the first 500 characters are logged. Your complete job descriptions, profile data, and AI responses stay local.
- **Actual PII values** — we track that 3 emails were masked, not what those emails were.
- **Database contents** — observability covers the AI layer only, not your applications, contacts, or profile data.
- **Frontend activity** — no page views, click tracking, or usage analytics.

This is a developer tool for understanding AI behavior, not a user analytics platform.


## The Stack

The observability stack runs alongside Kestrel as a separate set of Docker containers:

| What | Why |
|------|-----|
| **Langfuse Web** | The dashboard where you view traces |
| **Langfuse Worker** | Processes incoming trace events asynchronously |
| **PostgreSQL** | Stores trace metadata and project configuration |
| **ClickHouse** | Stores the actual trace data (optimized for analytics queries) |
| **Redis** | Manages job queues between web and worker |
| **MinIO** | S3-compatible storage for large trace payloads |

It sounds like a lot, but it's all managed by a single `docker compose` command and runs quietly in the background. The dashboard at `http://localhost:3100` is where you spend your time — the rest is infrastructure you never need to think about.
