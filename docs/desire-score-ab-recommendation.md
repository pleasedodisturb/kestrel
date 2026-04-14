# Desire Score A/B Recommendation

## Context

The dual-score architecture (G-275) adds a second dimension to job scoring:
**desire_score** measures "how much would the candidate want this job?" while
**fit_score** measures "how qualified is the candidate?" Two computation
approaches were implemented and evaluated.

## Option A: Derived Score

### How It Works

Computes `desire_score` as a weighted average of three dimensional sub-scores
that the AI already produces during fit scoring:

```
desire_score = (career_trajectory * w1) + (company_fit * w2) + (compensation_fit * w3)
```

**Default weights:** career_trajectory=0.35, company_fit=0.35, compensation_fit=0.30

**Goal-aware adjustment:** If the user has active goals containing specific
keywords, the weights shift to match their priorities:

| Goal keyword      | career_trajectory | company_fit | compensation_fit |
|-------------------|-------------------|-------------|------------------|
| leadership/management | 0.50          | 0.25        | 0.25             |
| compensation/salary   | 0.20          | 0.25        | 0.55             |
| culture/remote        | 0.25          | 0.50        | 0.25             |
| (no match)            | 0.35          | 0.35        | 0.30             |

**Implementation:** `compute_derived_desire_score()` in `src/career_os/services/scoring.py`

### Characteristics

- **Cost:** Zero additional AI cost (reuses existing dimensional scores)
- **Latency:** ~0ms (pure arithmetic)
- **Determinism:** Fully deterministic given the same dimensional inputs
- **Accuracy:** Limited by the quality of the dimensional scores and the
  simplicity of the weighting model. Cannot capture nuances like "this company
  is known for toxic culture" that aren't reflected in dimensions.

## Option B: AI-Generated Score

### How It Works

Adds `desire_score` (0-10) and `desire_reasoning` (text) to the `ScoreResult`
schema. The AI provider prompt is updated to request both fields alongside the
existing scoring output:

```
desire_score (0-10, how much the candidate would WANT this job --
considering company reputation, growth potential, culture signals,
role excitement, compensation attractiveness, work-life balance),
desire_reasoning (string explaining what makes this job desirable
or undesirable from the candidate's perspective)
```

**Implementation:** Updated prompts in `anthropic_provider.py` and
`openrouter_provider.py`. Mock provider returns deterministic values.

### Characteristics

- **Cost:** Zero *additional* cost per call, since the desire_score is
  requested as part of the same prompt. However, adds ~50 tokens to the
  prompt and ~50-100 tokens to the response, which slightly increases
  per-call cost (~$0.0001-$0.0003 additional per scoring).
- **Latency:** Zero additional latency (same API call)
- **Determinism:** Non-deterministic (LLM temperature variation)
- **Accuracy:** Can capture subtle signals: company reputation awareness,
  industry trends, culture red flags, career trajectory nuances that
  dimensional scores miss. The LLM has world knowledge about companies
  and roles that a simple weighted average cannot replicate.

## Trade-off Analysis

| Dimension          | Option A (Derived)         | Option B (AI-Generated)    |
|--------------------|----------------------------|----------------------------|
| Additional cost    | $0                         | ~$0.0002/call (marginal)   |
| Additional latency | 0ms                        | 0ms (same call)            |
| Determinism        | Fully deterministic        | Non-deterministic          |
| Accuracy           | Limited to 3 dimensions    | Full context + world knowledge |
| Personalization    | Goal-keyword matching only | Understands goals semantically |
| Explainability     | Weights are transparent    | Has desire_reasoning text  |
| Offline capability | Works without AI           | Requires AI provider       |
| Failure mode       | Always available if dims exist | Graceful: falls back to A |

## Recommendation: Option B (AI-Generated) as Default, Option A as Fallback

**Use Option B as the primary method** for the following reasons:

1. **Near-zero marginal cost.** Since desire_score is requested in the same
   API call as fit_score, the additional cost is negligible (~50 extra output
   tokens). There is no second API call.

2. **Superior accuracy.** The LLM can reason about company reputation, industry
   trends, role excitement, and growth potential using world knowledge that a
   3-dimension weighted average cannot capture. A job at a company known for
   toxic culture will get a low AI desire_score but might get a high derived
   score if its dimensional scores happen to be favorable.

3. **Built-in explainability.** `desire_reasoning` provides a natural-language
   explanation that users can read. Option A can only say "score based on
   career_trajectory (0.35) + company_fit (0.35) + compensation_fit (0.30)."

4. **Semantic goal understanding.** Option B understands "I want to transition
   into product management" holistically. Option A only matches literal keywords
   like "leadership" or "salary."

**Keep Option A as a fallback** for:
- Legacy rows where the AI didn't return desire_score
- Offline/mock scoring scenarios
- Cases where AI providers fail or are rate-limited
- Quick re-estimation when only weights change (no re-scoring needed)

The current implementation already uses this architecture: Option B is preferred
when the AI returns a desire_score; Option A kicks in as automatic fallback.
The `desire_score_method` column tracks which was used for every scored job.

## 2D Quadrant Classification

Jobs are classified into quadrants based on a threshold of 5.0:

```
                    desire_score
                    high (>=5)     low (<5)
                ┌──────────────┬──────────────┐
fit_score       │              │              │
high (>=5)      │  DREAM JOB   │  SAFE BET    │
                │              │              │
                ├──────────────┼──────────────┤
                │              │              │
low (<5)        │ STRETCH GOAL │    SKIP      │
                │              │              │
                └──────────────┴──────────────┘
```

- **Dream Job** (high fit, high desire): Qualified AND desirable. Apply immediately.
- **Stretch Goal** (low fit, high desire): Desirable but underqualified. Invest in upskilling.
- **Safe Bet** (high fit, low desire): Qualified but uninspiring. Good backup option.
- **Skip** (low fit, low desire): Neither qualified nor interested. Deprioritize.

**Implementation:** `classify_quadrant()` in `src/career_os/schemas/scoring.py`

## Files Changed

| File | Changes |
|------|---------|
| `src/career_os/models/scoring.py` | `desire_score`, `desire_score_method`, `desire_reasoning` columns |
| `src/career_os/schemas/scoring.py` | `DesireScoreResponse`, `classify_quadrant()`, fields on `ScoreResponse` |
| `src/career_os/schemas/ai.py` | `desire_score`, `desire_reasoning` on `ScoreResult` |
| `src/career_os/services/scoring.py` | `compute_derived_desire_score()`, integration in `score_job()` |
| `src/career_os/ai/anthropic_provider.py` | Updated scoring prompt |
| `src/career_os/ai/openrouter_provider.py` | Updated scoring prompt |
| `src/career_os/ai/mock_provider.py` | Mock desire_score generation |
| `alembic/versions/l3m4n5o6p7q8_*.py` | Migration for new columns |
| `frontend/src/api/types.ts` | `DesireScoreResponse`, `ScoreQuadrant`, fields on `ScoreResponseShape` |
| `tests/test_desire_score.py` | 25 tests covering both options |
