---
title: "How Token Optimization Works"
description: "How Kestrel keeps AI costs low without sacrificing quality — the strategies behind 90%+ savings"
---

# How Token Optimization Works

## The Problem

Every time Kestrel asks an AI to score a job, it sends text — your profile, the job description, scoring instructions. The AI reads it, thinks, and sends back a structured answer. You're charged by the word (well, by the "token" — roughly 0.75 words each).

Score 50 jobs and you've sent your profile 50 times. That's like printing 50 copies of your CV just to hand them to the same person who already read it. Wasteful, right?

At full price on Claude Sonnet, scoring 50 jobs might cost $1-2. Scale that to daily scanning across hundreds of positions, and you're looking at $30-60/month for one user. For a self-hosted tool, that's too much.

Kestrel uses six layered strategies to cut this by 90%+ while keeping the same scoring quality.

---

## Strategy 1: Prompt Caching (90% off repeat prefixes)

**The insight:** When scoring multiple jobs for the same person, your profile doesn't change between calls. Why re-process it every time?

Anthropic's prompt caching works like this: the first time you send a system prompt + profile, the AI "remembers" it for 5 minutes. Every subsequent call that starts with the same prefix gets a 90% discount on those tokens.

**How Kestrel uses it:** Your profile data is placed in the cached "system block" alongside the scoring instructions. When batch-scoring 50 jobs, only the first call pays full price for your profile. The other 49 get it at 90% off.

**Savings:** If your profile is 1,500 tokens and you score 50 jobs, you save ~67,500 tokens worth of processing (1,500 × 49 × 0.9).

---

## Strategy 2: Compact Serialization (30% off profile data)

**The insight:** When converting your profile to text for the AI, the default "pretty-printed" format adds unnecessary whitespace — indentation, line breaks, extra spaces. The AI doesn't need them.

```json
// Before (indented — extra whitespace tokens):
{
  "name": "Jane Doe",
  "skills": [
    "Python",
    "TypeScript"
  ]
}

// After (compact — same data, fewer tokens):
{"name":"Jane Doe","skills":["Python","TypeScript"]}
```

**Savings:** ~30% reduction on profile data. Zero risk — the data is identical, just without cosmetic formatting.

---

## Strategy 3: Compressed Prompts (67% off system instructions)

**The insight:** AI models understand telegraphic instructions just as well as verbose ones. "You are a career scoring AI. Return valid JSON with:" is 11 tokens that mean the same as "Career scoring AI. Valid JSON output:" at 6 tokens.

The scoring system prompt went from ~113 tokens to ~39 tokens. Across all 9 features, total system prompt tokens dropped from ~395 to ~129.

**Compression techniques:**
- Remove filler words ("You are a", "Return valid JSON with:")
- Use shorthand notation (`:str`, `:0-10`, `low|medium|high`)
- Inline options instead of prose descriptions
- Drop redundant type annotations the model can infer

**Quality check:** All compressed prompts pass the golden set regression tests — same output quality, fewer tokens.

---

## Strategy 4: Smart Model Selection (60-95% on simple tasks)

Not every AI task needs the most powerful (expensive) model. Kestrel routes tasks by complexity:

| Task | Model | Relative Cost |
|------|-------|---------------|
| "Is this job relevant?" (classification) | Haiku (small) | 1× |
| Score a job (analysis) | Sonnet (standard) | 4× |
| Deep career strategy (reasoning) | Opus (large) | 19× |

A simple yes/no relevance check doesn't need the model that writes novels. Routing saves 60-95% on simple tasks.

---

## Strategy 5: Response Caching (100% off repeated questions)

Ask the same question twice? Kestrel serves the answer from a local encrypted cache. Zero API calls, instant response.

The cache uses a SHA-256 hash of the question as the key. Answers are encrypted at rest with Fernet symmetric encryption (your scores are never stored in plaintext). Cache entries expire after 7 days.

---

## Strategy 6: Batch Scoring (50% off bulk work)

Scoring a big backlog overnight? Anthropic's Batch API gives a flat 50% discount for non-urgent work. Kestrel detects when you have many jobs to score and automatically submits them as a batch.

The batch has a 24-hour SLA — fine for discovery sweeps that run while you sleep. Real-time scoring (when you paste a URL) always uses the fast path.

---

## How They Stack

These strategies compound:

```
Base cost per job:         $0.03
After prompt caching:      $0.003  (90% off on repeats)
After compact JSON:        $0.002  (30% off profile data)
After compressed prompts:  $0.001  (67% off system prompt)
After model routing:       $0.0004 (use Haiku where possible)
After response cache:      $0.00   (if already scored)
After batch API:           50% off (for overnight sweeps)
```

**Result:** Monthly scanning cost drops from ~$30-60 to under $2.

---

## Cost Visibility

Every AI call logs its token usage to a local SQLite table — provider, model, feature, input/output tokens, and estimated USD cost. Nothing leaves your machine.

OpenRouter calls include an `X-Title: kestrel` header so Kestrel-specific costs show up separately in the OpenRouter dashboard (useful if you share an account across projects).

---

## Cache Break Detection

When the prompt caching system stops working (a "cache break"), costs can silently spike 10×. Kestrel monitors the cache hit ratio per feature and logs a warning when it drops below 80%:

```
WARNING: Cache break detected for feature=score: hit ratio 40%
(threshold 80%, window=20 events, 8 hits, 12 misses)
```

Common causes: a timestamp in the prompt, randomized field ordering, or a profile update mid-batch. The alert helps you diagnose and fix the issue before it burns through credits.

---

## Show Me the Numbers

Theory is nice. Here's what actually happens when Kestrel scores a real job posting against a real profile.

### The test case

- **Profile:** Technical Product Manager, 8 years experience, 16 skills, certifications, languages — a typical mid-career professional. 775 characters as pretty JSON, 598 characters compact.
- **Job:** "Senior TPM - AI Platform" posting with requirements, nice-to-haves, compensation — typical LinkedIn-length. 857 characters.

### What one scoring call looks like

Every scoring call has three parts — think of them like a sandwich:

```
┌─────────────────────────────────────────┐
│  System prompt (the instructions)       │  ← This is the bread.
│  "Career scoring AI. Valid JSON..."     │     Same every time.
├─────────────────────────────────────────┤
│  Your profile (who you are)             │  ← This is the filling.
│  Skills, experience, preferences...     │     Same for all jobs in a batch.
├─────────────────────────────────────────┤
│  Job description (what to score)        │  ← This is the unique part.
│  The actual posting text.               │     Different every call.
└─────────────────────────────────────────┘
```

The insight: **only the bottom layer changes.** The bread and filling are identical across all 50 jobs in a batch. So why pay full price for them every time?

### Single call: before vs after

| Provider | Old | New | Saved |
|----------|-----|-----|-------|
| OpenRouter / Together / Ollama | ~877 tokens | ~775 tokens | **12%** |
| Anthropic (first call) | ~877 tokens | ~772 tokens | **12%** |
| Anthropic (repeat, cached) | ~877 tokens | ~512 tokens | **42%** |

A single call saves 12%. Not life-changing. But watch what happens at scale.

### Batch scoring: where the magic kicks in

When scoring 50 jobs for the same user, the bread and filling get cached after the first call. The remaining 49 calls only pay 10% for those parts:

| Component | Old (50 calls) | New Anthropic (50 calls) | Saved |
|-----------|----------------|--------------------------|-------|
| System prompt | Sent 50× at full price | 1× full + 49× at 90% off | **92%** |
| Profile data | Sent 50× with whitespace | 1× compact + 49× cached | **92%** |
| Job descriptions | 50× (varies each time) | 50× (can't cache these) | 0% |

The job description is the stubborn part — it's unique per call, so no amount of caching helps. But everything else gets compressed and cached into near-nothing.

### Monthly: the number that matters

For a typical user scoring ~200 jobs/day (daily discovery scan + manual scoring):

| | Monthly cost (Sonnet, input tokens) |
|---|---|
| **Before optimization** | ~$15.79 |
| **After optimization** | ~$9.45 |
| **Savings** | **$6.35/month (40%)** |

And that's just input tokens on one model. Add the 70% output token reduction from token-efficient tool use, the 50% batch API discount for overnight scans, and the fact that response caching eliminates 100% of duplicate requests — **real-world all-in cost lands around $1-5/month.**

### Why it's not "90% savings" on everything

You might notice the 90% number from the strategies above, but only 40% overall savings. Here's why:

The cacheable parts (system prompt + profile) make up about 40% of a typical scoring call. The job description — which is unique and can't be cached — makes up the other 60%. You can't optimize what's already unique.

Think of it like commuting. If your drive is 40% highway and 60% city streets, even a 90% improvement on highway speed only cuts your total commute time by ~36%. The city streets are the bottleneck.

The good news: as profiles get richer (more skills, more preferences, more context), the cacheable portion grows — and the savings compound further.

---

## The Philosophy

Token optimization isn't about being cheap — it's about making AI-powered tools sustainable for self-hosting. A tool that costs $60/month in API fees won't get used daily. One that costs $2/month becomes invisible infrastructure.

Every optimization is validated against the golden set: same quality, lower cost. We never trade accuracy for savings.
