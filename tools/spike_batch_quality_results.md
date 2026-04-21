# Batch Scoring Quality A/B Test — Spike Results (G-453)

**Date:** 2026-04-21
**Branch:** G-453/batch-quality-spike
**Method:** MockProvider (no real API calls)

## Setup

- Golden set: `tests/fixtures/scoring_golden_set.json` (20 jobs, 4 categories)
- Individual scoring: `provider.score()` per job
- Batch scoring: `batch_score_jobs()` with batch_size=10

## Findings

### 1. Batch pipeline falls back correctly

MockProvider's `complete()` returns plain text, not a JSON array of ScoreResult
objects. The batch scoring service correctly detects the invalid response and
falls back to individual `provider.score()` calls for every job in the batch.

This is the *designed* behavior — `batch_score_jobs()` has a built-in fallback
path (lines 330-354 of `batch_scoring.py`) that individually re-scores any jobs
whose batch parsing fails.

### 2. Result counts match

| Metric | Individual | Batch |
|--------|-----------|-------|
| Results returned | 20/20 | 20/20 |
| Schema-valid ScoreResult | 20/20 | 20/20 |

### 3. Score identity (via fallback)

Because all batch jobs fall back to individual scoring, the scores are identical:

- Fit score mean delta: 0.00
- Fit score max delta: 0.00
- Dimensional score mean delta: 0.00
- Zero deltas: 20/20

### 4. Implications for real-provider testing

The MockProvider cannot validate *actual* batch quality because it doesn't
produce multi-result JSON arrays from `complete()`. To test real batch quality
degradation, you would need:

1. A mock that returns JSON arrays (extending MockProvider's `_handle_score` for
   `AIFeature.score` via `complete()` with multi-job prompts), OR
2. An integration test against a real provider (OpenRouter) with a small sample
   (e.g., 5 jobs) comparing individual vs batch scores.

### 5. What this spike *does* validate

- `batch_score_jobs()` handles complete batch failures gracefully (fallback works)
- All 20 fallback results are valid ScoreResult objects
- The pipeline returns the same number of results as input jobs
- No exceptions or crashes during the full flow
- `build_batch_prompt()` generates valid prompts without errors
- `parse_batch_response()` correctly rejects non-JSON-array responses

## Recommendation

The batch scoring pipeline is structurally sound. The fallback mechanism works
correctly. For production quality validation, a targeted integration test with
a real provider (even 3-5 jobs) would provide more meaningful A/B data than
expanding the mock. File a follow-up ticket if real-provider A/B testing is
desired.

## Script

Run with: `.venv/bin/python tools/spike_batch_quality.py`
