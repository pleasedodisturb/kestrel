# Scoring Engine

*Part of the [Kestrel roadmap](../../ROADMAP.md).*

## Goal

Make sense of thousands of job postings by scoring each one against what you actually want.

## What This Delivers

Every job that enters your pipeline gets two scores: a fit score (how well you match the role's requirements) and a desire score (how much the role matches what you want). Together, they tell you whether a job is worth your time, even before you read the posting.

Scoring is not one-size-fits-all. Kestrel includes 288 job family presets across 18 sectors, from software engineering to healthcare to finance. When you set your target role, the scoring rubric adjusts automatically. A data scientist and a product manager are evaluated on different dimensions because the jobs demand different things. You can also customize the rubric directly if the presets do not match your situation.

Red flags get surfaced alongside scores. Ghost postings, vague descriptions, suspiciously broad requirements, and other warning signs are flagged so you can skip them quickly. For jobs that land in the borderline range (close calls where a small difference in weight could change the outcome), Kestrel runs a second scoring pass with adjusted emphasis to give you a more confident result. If you disagree with a score, you can give feedback that calibrates future scoring, teaching the system what matters to you over time.

For high-volume scoring, jobs are batched into groups and evaluated together, cutting costs by roughly 80% without meaningful loss in accuracy. Nightly scoring can use async Batch APIs from providers like Anthropic and OpenAI, which process results within 24 hours at half the normal price.

## How It Works

When a job arrives for scoring, Kestrel builds a prompt that includes your profile (skills, preferences, experience level), the job description, and the scoring rubric for your target role. That prompt goes to whichever AI provider you have configured. The provider returns structured scores, which Kestrel parses, validates, and stores. If batch scoring is active, multiple jobs go into a single prompt and the results are split apart afterward.

The scoring rubric itself is a set of weighted dimensions: technical fit, experience level, role alignment, company signals, location match, and others. Job family presets adjust these weights. A "Software Engineer" preset emphasizes technical stack and seniority. A "Marketing Manager" preset cares more about industry experience and campaign metrics. The fuzzy matching system identifies your target role even if you phrase it differently than the preset name.

## Current Status

*Shipped in [v0.4.0](../../CHANGELOG.md#040-2026-04-16)*

Core scoring is fully functional with dual fit/desire scores, 288 presets, red flag detection, borderline re-scoring, feedback calibration, and batch scoring. The scoring service is a 4,262-line module that works reliably but would benefit from decomposition into smaller sub-modules as complexity grows.

## Related Milestones

- **[Discovery Engine](discovery-engine.md)** -- Discovery feeds jobs into the scoring queue
- **[Cost Control](cost-control.md)** -- Cost presets configure how scoring uses AI providers
- **[AI Provider System](ai-provider-system.md)** -- Providers execute the scoring prompts

---

*For Contributors*

## Architecture

The scoring engine lives in `src/career_os/services/scoring.py`, a 4,262-line service module that handles prompt construction, LLM response parsing, rubric logic, borderline two-pass scoring, feedback calibration, batch orchestration, statistics, and letter-grade mapping. This is the single largest file in the codebase and a known decomposition target.

Supporting modules:

- `src/career_os/services/batch_scoring.py` -- Batch scoring orchestration (10 jobs per prompt, randomized order to prevent position bias)
- `src/career_os/services/presets.py` -- 288 job family presets with fuzzy matching via `rapidfuzz`
- `src/career_os/schemas/scoring.py` -- Pydantic schemas for score results, rubric configuration
- `src/career_os/models/scoring.py` -- `ScoredJob`, `ScoringFeedback`, `ScoringWeights` ORM models
- `src/career_os/api/scoring.py` -- REST endpoints (`POST /api/scoring/score`, batch endpoints)

The AI provider layer (`src/career_os/ai/`) handles the actual LLM calls. The scoring service calls `get_ai_provider()` from the factory, which returns whichever provider is configured. Complexity tier routing sends simple scoring tasks to smaller models and reserves larger models for nuanced operations.

## Research & Decisions

Annotated links to research and reference documents:

- [Scoring Research](../research/scoring-research.md) -- Core scoring philosophy: human-first rubric design, multi-factor evaluation, and why "recommended" means balanced, not optimal
- [Scoring Raw Research](../research/scoring-raw-research.md) -- Raw research data behind scoring decisions, benchmark methodology, and model comparison results
- [Batch Scoring Feasibility](../research/batch-scoring-feasibility.md) -- Evidence that 10-25 jobs per prompt maintains quality while cutting costs by 80% or more
- [Preset Tier Validation](../research/preset-tier-validation.md) -- Benchmark validation that five quality tiers (Free/Budget/Quality/Privacy/Custom) reflect real model performance clusters
- [Scoring Validation Report](../reference/scoring-validation-report.md) -- Before/after validation data: variance dropped 15.7%, reject accuracy 100%, mediocre accuracy improved from 63.6% to 75.0%

## BMAD Integration

**PRD Status:** Not started

A PRD would formalize the scoring rubric dimensions, define quality metrics for scoring accuracy, establish the golden set regression testing approach, and specify how job family presets map to scoring weights.

To start a PRD: `/bmad-create-prd` in Claude Code.
See the [planning hierarchy](inventory.md#how-planning-works) for how PRDs connect to implementation.
