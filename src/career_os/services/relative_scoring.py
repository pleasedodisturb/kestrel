"""Relative / percentile batch scoring (G-1338, finding N).

Absolute pointwise calibration is the root cause of scoring drift; *relative*
ranking sidesteps it — a job's rank within a batch is far more stable across
model swaps than its absolute 0–10 number. This module normalizes a discovery
batch's raw fit scores to **within-batch percentiles and relative tiers**,
reusing the exact percentile math from ``compute_score_context`` (G-271).

Design guarantees:

* **Opt-in, off by default.** Gated on ``settings.relative_batch_scoring_enabled``
  at the call site. When off, ``batch_score_discovery`` returns byte-for-byte
  what it always did (strict identity — no ``relative`` key).
* **Non-destructive.** Raw ``fit_score`` values are NEVER mutated. The relative
  view is an *additional* structure computed from the raw scores; both are kept.
* **Deterministic, no LLM.** Pure arithmetic over the batch's raw scores — no
  extra provider calls, so it is free and testable on fixtures.
"""

from __future__ import annotations

# Relative-tier bucket edges over the within-batch percentile (0–100). A job in
# the top quartile of its batch is "top", and so on. Ordinal, batch-relative —
# independent of the absolute fit_score tiers in ``scoring_eval``.
_RELATIVE_TIER_EDGES: tuple[tuple[int, str], ...] = (
    (75, "top"),
    (50, "upper"),
    (25, "lower"),
    (0, "bottom"),
)


def relative_tier_from_percentile(percentile: int) -> str:
    """Bucket a within-batch percentile (0–100) into an ordinal relative tier."""
    for edge, name in _RELATIVE_TIER_EDGES:
        if percentile >= edge:
            return name
    return "bottom"


def relativize_scores(scores: list[float]) -> list[dict]:
    """Normalize a batch of raw fit scores to within-batch percentiles + tiers.

    Pure. For each score (in input order) returns::

        {
            "raw_fit_score": float,     # unchanged input
            "batch_percentile": int,    # % of the batch strictly below this score
            "relative_rank": int,       # 1 = highest raw score in the batch (ties share)
            "relative_tier": str,       # top / upper / lower / bottom
        }

    Percentile uses the same ``below_count / total * 100`` definition as
    ``compute_score_context`` (G-271) so the two stay consistent. Empty input
    returns ``[]``. A single-element batch is degenerate (percentile 0, rank 1,
    tier "bottom") — relative tiering is only meaningful across several jobs.
    """
    n = len(scores)
    if n == 0:
        return []

    out: list[dict] = []
    for s in scores:
        below = sum(1 for other in scores if other < s)
        above = sum(1 for other in scores if other > s)
        percentile = int(below / n * 100)
        rank = above + 1
        out.append(
            {
                "raw_fit_score": s,
                "batch_percentile": percentile,
                "relative_rank": rank,
                "relative_tier": relative_tier_from_percentile(percentile),
            }
        )
    return out


def build_relative_view(scored_jobs: list) -> dict[int, dict]:
    """Build a ``{scored_job_id: relative_entry}`` view over a batch of ScoredJobs.

    Reads ``fit_score`` off each :class:`~career_os.models.scoring.ScoredJob` and
    returns the relative normalization keyed by the scored job's ``id`` — a
    join-free lens the caller can attach without touching the persisted rows. Raw
    scores are read only, never written.
    """
    raw = [float(sj.fit_score) for sj in scored_jobs]
    relatives = relativize_scores(raw)
    return {sj.id: rel for sj, rel in zip(scored_jobs, relatives, strict=True)}
