# Scoring eval harness (G-1336)

Golden-set agreement eval for the job-fit scorer. Implements finding **H** of
`docs/research/2026-07_scoring-technique-audit.md`.

## The one rule

The eval exercises the **real production scorer** —
`career_os.services.scoring.score_job` (and `batch_score_discovery`) — never a
reimplementation. That was the whole lesson: the earlier 18-job MAE benchmark
misled us because it scored a *proxy path*, not production.

It runs with the deterministic **MockProvider** (`AI_PROVIDER=mock`) so there are
**zero paid LLM calls** and CI is reproducible. "Production path, mock provider."

## What it measures

Fit scoring is a **ranking** problem, so we evaluate rank/quadrant agreement,
not MAE-to-a-reference:

- **Weighted Cohen's κ** on the ordinal tier (`reject < mediocre < strong < dream`).
- **NDCG@5** on the ranking.

Both come from the pure-Python primitives in
`career_os.services.scoring_eval` (cross-checked against scikit-learn in
`tests/test_scoring_eval.py`). The eval gates on **deltas vs a frozen baseline**
(`baseline_metrics.json`) with tolerance bands, so it tracks pipeline behavior
without flapping.

## Running

```bash
pytest tests/eval/ -m eval          # nightly gate (excluded from the fast CI run)
python -m tests.eval.generate_baseline   # regenerate baseline (review the diff!)
python -m tests.eval.generate_labels     # reseed interim labels after fixture edits
```

## ⚠️ The remaining step: human labels

The labels in `labels/*.labels.json` are **INTERIM, model-derived** — seeded
from the golden set's LLM-authored `category` field. With the mock provider κ
sits near 0 (hash scores are uncorrelated), so today the harness proves the
**infra + metric math + regression gate**, not real quality.

To make the κ/NDCG gate a real quality signal, a human must label the
**rank/quadrant** of the ~120 jobs across the 6 families (`tier` + `relevance`
in each label file). Each label is bound to its job text by an `input_hash`, so
editing a fixture invalidates its label (the harness flags it) rather than
silently mislabeling. Once human labels land, run a real reference model once and
raise the gate toward **weighted κ ≥ 0.60** (per the research).
