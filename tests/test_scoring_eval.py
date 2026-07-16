"""Unit tests for the scoring-eval metric primitives (G-1336).

Validates the pure-Python metric math against analytically known values AND, when
available, against scikit-learn as a reference oracle (dev-only; skipped if the
package is absent). Covers weighted Cohen's κ, NDCG@5, PSI, and the tier
projection.
"""

from __future__ import annotations

import math

import pytest

from career_os.services.scoring_eval import (
    DEFAULT_SCORE_BINS,
    SPREAD_MODE_SHARE_CEILING,
    SPREAD_STDDEV_FLOOR,
    bin_counts,
    chosen_rejected_gap,
    kappa_from_tiers,
    mode_share,
    ndcg_at_k,
    population_stability_index,
    psi_from_scores,
    score_entropy,
    score_stddev,
    spread_collapsed,
    spread_metrics,
    tier_from_fit_score,
    weighted_cohen_kappa,
)

# ---------------------------------------------------------------------------
# Weighted Cohen's kappa
# ---------------------------------------------------------------------------


def test_kappa_perfect_agreement_is_one():
    y = [0, 1, 2, 3, 2, 1, 0]
    assert weighted_cohen_kappa(y, y, num_classes=4) == pytest.approx(1.0)


def test_kappa_single_class_degenerate_returns_one():
    # No disagreement weight to normalize against → treated as perfect.
    assert weighted_cohen_kappa([2, 2, 2], [2, 2, 2], num_classes=4) == pytest.approx(1.0)


def test_kappa_known_value():
    # Hand-computable 2x2 case. y_true=[0,0,1,1], y_pred=[0,1,1,1].
    # Confusion: O[0][0]=1,O[0][1]=1,O[1][1]=2. k=2 → linear weights = |i-j|.
    # Observed disagreement = w-weighted O = O[0][1]*1 = 1.
    # Row totals=[2,2], col totals=[1,3]. Expected disagree = (2*3 + 2*1)/4 *? compute:
    #   E[0][1]=2*3/4=1.5 (w=1), E[1][0]=2*1/4=0.5 (w=1) → weighted E = 2.0
    # kappa = 1 - 1/2 = 0.5
    kappa = weighted_cohen_kappa([0, 0, 1, 1], [0, 1, 1, 1], num_classes=2)
    assert kappa == pytest.approx(0.5)


def test_kappa_matches_sklearn_oracle():
    sk = pytest.importorskip("sklearn.metrics")
    y_true = [0, 1, 2, 3, 1, 2, 0, 3, 2, 1]
    y_pred = [0, 2, 2, 3, 1, 1, 0, 2, 3, 1]
    ours = weighted_cohen_kappa(y_true, y_pred, num_classes=4)
    theirs = sk.cohen_kappa_score(y_true, y_pred, weights="linear")
    assert ours == pytest.approx(theirs, abs=1e-9)


def test_kappa_from_tiers():
    true = ["reject", "mediocre", "strong", "dream"]
    pred = ["reject", "mediocre", "strong", "dream"]
    assert kappa_from_tiers(true, pred) == pytest.approx(1.0)


def test_kappa_length_mismatch_raises():
    with pytest.raises(ValueError):
        weighted_cohen_kappa([0, 1], [0])


def test_kappa_empty_raises():
    with pytest.raises(ValueError):
        weighted_cohen_kappa([], [])


# ---------------------------------------------------------------------------
# NDCG@k
# ---------------------------------------------------------------------------


def test_ndcg_perfect_ranking_is_one():
    rel = [3, 2, 1, 0]
    scores = [10.0, 8.0, 5.0, 1.0]  # already in ideal order
    assert ndcg_at_k(rel, scores, k=4) == pytest.approx(1.0)


def test_ndcg_known_value_reversed():
    # rel=[0,1], scores rank item1 (rel=1) first → perfect → 1.0
    assert ndcg_at_k([0, 1], [1.0, 2.0], k=2) == pytest.approx(1.0)
    # scores rank item0 (rel=0) first → DCG = 0/log2(2)+1/log2(3); IDCG=1/log2(2)
    dcg = 0 / math.log2(2) + 1 / math.log2(3)
    idcg = 1 / math.log2(2)
    assert ndcg_at_k([0, 1], [2.0, 1.0], k=2) == pytest.approx(dcg / idcg)


def test_ndcg_all_zero_relevance_is_zero():
    assert ndcg_at_k([0, 0, 0], [3.0, 2.0, 1.0], k=3) == 0.0


def test_ndcg_matches_sklearn_oracle():
    sk = pytest.importorskip("sklearn.metrics")
    rel = [0.0, 1.0, 2.0, 3.0, 1.0, 0.0, 2.0]
    scores = [0.5, 3.1, 2.2, 9.0, 1.0, 0.1, 4.0]  # distinct → no ties
    ours = ndcg_at_k(rel, scores, k=5)
    theirs = sk.ndcg_score([rel], [scores], k=5)
    assert ours == pytest.approx(theirs, abs=1e-9)


def test_ndcg_length_mismatch_raises():
    with pytest.raises(ValueError):
        ndcg_at_k([1, 2], [1.0])


# ---------------------------------------------------------------------------
# Tier projection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0.0, "reject"),
        (3.0, "reject"),
        (3.5, "mediocre"),
        (4.9, "mediocre"),
        (5.0, "strong"),
        (7.9, "strong"),
        (8.0, "dream"),
        (10.0, "dream"),
    ],
)
def test_tier_from_fit_score(score, expected):
    assert tier_from_fit_score(score) == expected


# ---------------------------------------------------------------------------
# PSI
# ---------------------------------------------------------------------------


def test_psi_identical_distributions_is_zero():
    counts = [10, 20, 30, 40]
    assert population_stability_index(counts, counts) == pytest.approx(0.0)


def test_psi_known_two_bin_value():
    # expected 50/50, actual 25/75. PSI = (.25-.5)ln(.25/.5)+(.75-.5)ln(.75/.5)
    expected = (0.25 - 0.5) * math.log(0.25 / 0.5) + (0.75 - 0.5) * math.log(0.75 / 0.5)
    assert population_stability_index([50, 50], [25, 75]) == pytest.approx(expected)


def test_psi_shift_exceeds_significant_threshold():
    # Big shift → PSI well above 0.2.
    psi = population_stability_index([90, 10], [10, 90])
    assert psi > 0.2


def test_psi_bin_mismatch_raises():
    with pytest.raises(ValueError):
        population_stability_index([1, 2], [1, 2, 3])


def test_psi_empty_raises():
    with pytest.raises(ValueError):
        population_stability_index([0, 0], [1, 1])


def test_bin_counts_and_psi_from_scores():
    counts = bin_counts([0.5, 1.9, 4.5, 9.9], edges=DEFAULT_SCORE_BINS)
    assert sum(counts) == 4
    # Same population → PSI 0.
    scores = [1.0, 5.0, 9.0, 2.0, 7.0]
    assert psi_from_scores(scores, scores) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Spread metrics (G-1337, finding F)
# ---------------------------------------------------------------------------


def test_stddev_known_values():
    assert score_stddev([5.0, 5.0, 5.0]) == pytest.approx(0.0)
    # Population std of [0, 10]: mean 5, var (25+25)/2 = 25, sqrt = 5.
    assert score_stddev([0.0, 10.0]) == pytest.approx(5.0)
    # Fewer than 2 values → 0.0 by definition.
    assert score_stddev([7.3]) == pytest.approx(0.0)
    assert score_stddev([]) == pytest.approx(0.0)


def test_stddev_matches_statistics_pstdev():
    import statistics

    scores = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
    assert score_stddev(scores) == pytest.approx(statistics.pstdev(scores))


def test_entropy_single_bin_is_zero():
    # All scores land in the first bin [0, 2) → fully collapsed → entropy 0.
    assert score_entropy([0.1, 0.5, 1.9, 1.0]) == pytest.approx(0.0)


def test_entropy_two_equal_bins_is_one_bit():
    # Half in bin [0,2), half in the last bin → 50/50 over two bins → 1.0 bit.
    scores = [1.0, 1.0, 9.0, 9.0]
    assert score_entropy(scores) == pytest.approx(1.0)


def test_entropy_empty_is_zero():
    assert score_entropy([]) == pytest.approx(0.0)


def test_mode_share_known_values():
    # All in one bin → mode share 1.0.
    assert mode_share([1.0, 1.5, 0.2]) == pytest.approx(1.0)
    # 3 of 4 in the same bin → 0.75.
    assert mode_share([1.0, 1.0, 1.0, 9.0]) == pytest.approx(0.75)
    assert mode_share([]) == pytest.approx(0.0)


def test_chosen_rejected_gap_known_value():
    scores = [8.0, 8.0, 2.0, 2.0]
    tiers = ["strong", "dream", "reject", "reject"]
    # chosen mean 8, rejected mean 2 → gap 6.0.
    assert chosen_rejected_gap(scores, tiers) == pytest.approx(6.0)


def test_chosen_rejected_gap_empty_side_is_zero():
    # No rejected jobs → not measurable → 0.0.
    assert chosen_rejected_gap([8.0, 9.0], ["strong", "dream"]) == pytest.approx(0.0)
    # No chosen jobs → 0.0. (mediocre is excluded from both sides.)
    assert chosen_rejected_gap([2.0, 5.0], ["reject", "mediocre"]) == pytest.approx(0.0)


def test_chosen_rejected_gap_length_mismatch_raises():
    with pytest.raises(ValueError):
        chosen_rejected_gap([1.0, 2.0], ["reject"])


def test_spread_metrics_bundle_and_negative_gap():
    # A clearly-spread, well-ordered set.
    scores = [1.0, 2.0, 5.0, 8.0, 9.0]
    tiers = ["reject", "reject", "mediocre", "strong", "dream"]
    m = spread_metrics(scores, tiers=tiers)
    assert set(m) == {"stddev", "entropy", "mode_share", "chosen_rejected_gap"}
    assert m["stddev"] > 0.0
    assert m["chosen_rejected_gap"] > 0.0  # good jobs outscore bad
    # Without tiers, the gap is omitted.
    assert "chosen_rejected_gap" not in spread_metrics(scores)


def test_spread_collapsed_gate():
    # A single repeated value → std-dev 0, mode-share 1.0 → collapsed.
    collapsed = spread_metrics([5.0] * 10)
    assert collapsed["stddev"] < SPREAD_STDDEV_FLOOR
    assert collapsed["mode_share"] > SPREAD_MODE_SHARE_CEILING
    assert spread_collapsed(collapsed) is True
    # A healthily-spread set → not collapsed.
    healthy = spread_metrics([0.5, 3.0, 5.5, 7.0, 9.5, 2.0, 6.5, 8.5])
    assert spread_collapsed(healthy) is False
