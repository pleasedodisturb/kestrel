"""Scoring evaluation metrics — agreement, ranking, and drift primitives.

Job-fit scoring is a *ranking* problem, not a regression problem (see
``docs/research/2026-07_scoring-technique-audit.md``, finding H). We therefore
evaluate the production scorer on **rank/quadrant agreement** against labeled
reference data — never on MAE-to-a-reference-model.

This module holds the pure-Python metric primitives shared by the golden-set
eval harness (``tests/eval/``), the shadow-mode comparator
(``scoring_shadow.py``), and the drift canary (``drift_canary.py``):

* :func:`weighted_cohen_kappa` — inter-rater agreement on an ordinal tier
  (linear weights), matching ``sklearn.metrics.cohen_kappa_score(weights="linear")``.
* :func:`ndcg_at_k` — ranking quality, matching ``sklearn.metrics.ndcg_score``
  (linear gains, ``log2`` discount).
* :func:`population_stability_index` — distribution drift (PSI), the standard
  ``sum((a - e) * ln(a / e))`` over bins.

They are implemented in the standard library (``math`` only) so nothing in the
production import path depends on numpy/scikit-learn. ``scikit-learn`` is a
dev-only test oracle: ``tests/eval`` cross-checks these implementations against
it on toy data with analytically known values.
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# Ordinal fit tiers — the categorical axis for agreement (κ)
# ---------------------------------------------------------------------------

# The golden sets label each job with one of these four ordinal categories
# (weakest → strongest). We compare the production ``fit_score`` against the
# label by projecting the 0–10 score into the same ordinal tier.
TIER_ORDER: tuple[str, ...] = ("reject", "mediocre", "strong", "dream")
_TIER_INDEX: dict[str, int] = {name: i for i, name in enumerate(TIER_ORDER)}

# fit_score → tier bin edges (upper-exclusive except the last). Chosen so the
# role-fit gate ceiling (3.0) and the quadrant threshold (5.0) fall on natural
# tier boundaries: gated jobs land in "reject", quadrant-positive jobs in
# "strong"/"dream".
_TIER_EDGES: tuple[tuple[float, str], ...] = (
    (3.5, "reject"),
    (5.0, "mediocre"),
    (8.0, "strong"),
    (10.0001, "dream"),
)


def tier_from_fit_score(fit_score: float) -> str:
    """Project a 0–10 ``fit_score`` into an ordinal :data:`TIER_ORDER` tier."""
    for upper, name in _TIER_EDGES:
        if fit_score < upper:
            return name
    return TIER_ORDER[-1]


def tier_index(tier: str) -> int:
    """Return the ordinal index (0–3) of a tier name."""
    return _TIER_INDEX[tier]


# ---------------------------------------------------------------------------
# Weighted Cohen's kappa (linear weights)
# ---------------------------------------------------------------------------


def weighted_cohen_kappa(
    y_true: list[int],
    y_pred: list[int],
    *,
    num_classes: int | None = None,
) -> float:
    """Linearly-weighted Cohen's κ for ordinal labels.

    Matches ``sklearn.metrics.cohen_kappa_score(y_true, y_pred, weights="linear")``.
    Labels are 0-based ordinal class indices. Returns 1.0 for the degenerate
    case where the disagreement weight vanishes (e.g. all raters pick one class),
    consistent with perfect agreement.

    Raises ``ValueError`` on length mismatch or empty input.
    """
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must have equal length")
    n = len(y_true)
    if n == 0:
        raise ValueError("cannot compute kappa on empty input")

    k = num_classes if num_classes is not None else (max(max(y_true), max(y_pred)) + 1)
    if k <= 1:
        return 1.0

    # Observed confusion matrix.
    observed = [[0.0] * k for _ in range(k)]
    for t, p in zip(y_true, y_pred, strict=True):
        observed[t][p] += 1.0

    row_totals = [sum(observed[i]) for i in range(k)]
    col_totals = [sum(observed[i][j] for i in range(k)) for j in range(k)]

    # Linear weight matrix: |i - j| / (k - 1).
    denom_w = k - 1
    num = 0.0
    den = 0.0
    for i in range(k):
        for j in range(k):
            w = abs(i - j) / denom_w
            expected = row_totals[i] * col_totals[j] / n
            num += w * observed[i][j]
            den += w * expected

    if den == 0.0:
        return 1.0
    return 1.0 - num / den


def kappa_from_tiers(true_tiers: list[str], pred_tiers: list[str]) -> float:
    """Weighted κ over :data:`TIER_ORDER` tier names."""
    yt = [tier_index(t) for t in true_tiers]
    yp = [tier_index(t) for t in pred_tiers]
    return weighted_cohen_kappa(yt, yp, num_classes=len(TIER_ORDER))


# ---------------------------------------------------------------------------
# NDCG@k
# ---------------------------------------------------------------------------


def _dcg(relevances: list[float], k: int) -> float:
    """Discounted cumulative gain with linear gains and log2 discount."""
    total = 0.0
    for rank, rel in enumerate(relevances[:k], start=1):
        total += rel / math.log2(rank + 1)
    return total


def ndcg_at_k(
    relevances: list[float],
    scores: list[float],
    *,
    k: int = 5,
) -> float:
    """Normalized DCG@k for a single ranking.

    ``relevances[i]`` is the ground-truth relevance grade of item ``i``;
    ``scores[i]`` is the model score used to *rank* the items. Items are sorted
    by descending score; ties break by original index (deterministic). Uses
    linear gains and a ``log2(rank + 1)`` discount, matching
    ``sklearn.metrics.ndcg_score([relevances], [scores], k=k)`` when scores are
    distinct.

    Returns 0.0 when the ideal DCG is 0 (all relevances zero).
    """
    if len(relevances) != len(scores):
        raise ValueError("relevances and scores must have equal length")
    if not relevances:
        return 0.0

    order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
    ranked_rel = [relevances[i] for i in order]
    ideal_rel = sorted(relevances, reverse=True)

    idcg = _dcg(ideal_rel, k)
    if idcg == 0.0:
        return 0.0
    return _dcg(ranked_rel, k) / idcg


# ---------------------------------------------------------------------------
# Population Stability Index (drift)
# ---------------------------------------------------------------------------

# Default score-distribution bins over the 0–10 fit-score range.
DEFAULT_SCORE_BINS: tuple[float, ...] = (0.0, 2.0, 4.0, 5.0, 6.0, 8.0, 10.0001)

# Standard PSI interpretation thresholds.
PSI_MODERATE_SHIFT = 0.1
PSI_SIGNIFICANT_SHIFT = 0.2


def bin_counts(values: list[float], edges: tuple[float, ...] = DEFAULT_SCORE_BINS) -> list[int]:
    """Bucket ``values`` into ``len(edges) - 1`` bins defined by ``edges``.

    Values below the first edge fall in the first bin; values at/above the last
    edge fall in the last bin.
    """
    counts = [0] * (len(edges) - 1)
    for v in values:
        placed = False
        for b in range(len(edges) - 1):
            if v < edges[b + 1]:
                counts[b] += 1
                placed = True
                break
        if not placed:
            counts[-1] += 1
    return counts


def population_stability_index(
    expected_counts: list[int],
    actual_counts: list[int],
    *,
    epsilon: float = 1e-4,
) -> float:
    """Population Stability Index between two binned distributions.

    ``PSI = Σ (a% - e%) * ln(a% / e%)`` over bins, where ``a%``/``e%`` are the
    proportion of the actual/expected populations in each bin. ``epsilon`` floors
    each proportion so empty bins do not blow up the logarithm. Rule of thumb:
    ``< 0.1`` stable, ``0.1–0.2`` moderate shift, ``> 0.2`` significant shift.

    Raises ``ValueError`` on bin-count mismatch or empty populations.
    """
    if len(expected_counts) != len(actual_counts):
        raise ValueError("expected and actual must have the same number of bins")
    e_total = sum(expected_counts)
    a_total = sum(actual_counts)
    if e_total == 0 or a_total == 0:
        raise ValueError("cannot compute PSI on an empty distribution")

    psi = 0.0
    for e, a in zip(expected_counts, actual_counts, strict=True):
        e_pct = max(e / e_total, epsilon)
        a_pct = max(a / a_total, epsilon)
        psi += (a_pct - e_pct) * math.log(a_pct / e_pct)
    return psi


def psi_from_scores(
    baseline_scores: list[float],
    current_scores: list[float],
    *,
    edges: tuple[float, ...] = DEFAULT_SCORE_BINS,
) -> float:
    """Convenience: PSI between two raw 0–10 score populations."""
    return population_stability_index(
        bin_counts(baseline_scores, edges),
        bin_counts(current_scores, edges),
    )
