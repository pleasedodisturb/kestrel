---
title: "Model Scoring Benchmark — Cost vs Quality"
description: "Which AI model gives the best job-scoring quality per dollar — measured, not assumed"
---

# Model Scoring Benchmark — Cost vs Quality (2026-07)

**TL;DR:** For bulk job scoring, **Mistral Small is the best cost/quality model** — it agrees with premium Claude Opus more closely than any other model tested, at a fraction of the cost. Counterintuitively, the mid-size **Llama 3.3 70B was the worst**: it inflated scores by ~2 points and was noisy. Job scoring is a filtering task; it does not need a frontier model, and a *bigger* model is not automatically a better scorer.

## Why measure this

It's tempting to reach for the biggest model you can afford, or to assume a cheap model must be worse. Both assumptions are wrong for scoring. Scoring a job is a rating/classification task — "how well does this role fit, 0-10?" — not open-ended reasoning or writing. So we measured which model actually judges jobs best per dollar, rather than guessing.

## Method

- **Sample:** 18 real scraped jobs.
- **Harness:** every model scored the same 18 jobs through one OpenAI-compatible endpoint (OpenRouter), using an identical scoring prompt and parser, `temperature=0.3`. Only the model varied — apples-to-apples.
- **Quality metric:** mean absolute score difference (MAE) from **Claude Opus 4.1** as the reference judge — lower means closer to premium judgment. (Opus isn't ground truth, but it's the strongest available judge; several independent models converging near it while one sits far off is strong signal.)
- **Cost:** live per-token prices × measured token usage, extrapolated to 1,000 jobs.

## Results

| Model | Mean score | Consistency (std) | Agreement w/ Opus (MAE) | Cost / 1,000 jobs | Latency |
|---|---|---|---|---|---|
| **Mistral Small** | 2.7 | 0.8 | **0.50 (best)** | **$0.20** | 1.1s |
| Llama 3.1 8B | 2.6 | 0.8 | 0.72 | $0.05 | 1.7s |
| Claude Haiku 4.5 | 2.2 | 0.9 | 0.67 | $3.64 | 2.9s |
| Claude Sonnet 4.6 | 3.4 | 1.2 | 0.78 | $9.63 | 3.9s |
| Claude Opus 4.1 (reference) | 2.9 | 0.7 | 0.00 | $46.87 | 4.7s |
| **Llama 3.3 70B** | **5.0** | **1.9** | **2.11 (worst)** | $0.27 | 2.0s |

## Findings

1. **Bigger ≠ better for scoring.** The mid-size Llama 3.3 70B scored ~2 points higher than every other model (5.0 vs the 2.2–2.9 cluster) and was the noisiest. Over-generous scoring inflates your top tier with false positives — jobs that look like strong matches but aren't.
2. **Mistral Small wins on cost *and* quality.** Best agreement with premium Opus (closer than Haiku or Sonnet), at a bottom-tier price — ~230× cheaper than Opus for equivalent-or-better filtering judgment.
3. **Premium models buy almost nothing for filtering.** Haiku/Sonnet/Opus cost 18–230× more without judging these jobs meaningfully better. Reserve them for deep work (cover letters, analyzing your shortlist), not the 1,000-job funnel.

## What Kestrel does with this

Kestrel defaults its Mistral provider to **Mistral Small** for scoring. Set `MISTRAL_MODEL=mistral-large-latest` to opt into the flagship for deeper analysis. See [AI Costs and Privacy → Smart Model Routing](../guides/cost-optimization.md#smart-model-routing-saves-60-95) and [Fallback Chain Ordering](../guides/cost-optimization.md#fallback-chain-ordering-avoids-surprise-bills).

## Caveats

Directional, not definitive: 18 jobs, one scrape (skewed toward low-fit roles, which is why most means sit ~2–3). "Quality = agreement with Opus" is a proxy for ground truth. Re-run larger for higher confidence, and re-measure when model versions change — but the effect here is large and consistent, not noise.
