"""Tests for tools/calibrate.py.

The properties here are the ones whose absence is invisible in the output.

REWEIGHTING. A balanced sample drawn from an unbalanced population gives
flattering precision if counted unweighted. The test builds a set where the
weighted and unweighted answers DIFFER and pins the weighted one, so dropping
the weights fails rather than merely shifting a number nobody checks.

MISSING WEIGHTS FAIL LOUDLY. p_draw cannot be recovered after the draw, so a
label set without it must raise, never silently fall back to 1.0.

CEILING SEMANTICS. Self-consistency is computed from repeat pairs matched by
job_id, and repeats are excluded from every other statistic -- counting one
posting twice would inflate n and narrow the intervals.

NAMING. Nothing in the report may present agreement as accuracy, and nothing
may describe the flow as training. Both are asserted against the rendered text
because both errors have actually shipped in this project before.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from calibrate import (  # noqa: E402
    bootstrap_ci,
    build_report,
    filter_agreement,
    load_inputs,
    precision_recall,
    repeat_pairs,
    self_consistency,
    suggest_threshold,
    weighted_confusion,
)


def _it(index, stratum, *, job_id=None, fit=5.0, repeat=False, repeat_of=None):
    return {
        "index": index,
        "title": f"Role {index}",
        "company": "Co",
        "location": "Somewhere",
        "description": "d" * 600,
        "_hidden": {
            "job_id": job_id if job_id is not None else index,
            "url": None,
            "stratum": stratum,
            "geo_class": "home_local" if stratum == "KEEP" else "foreign",
            "fit_score": fit,
            "remote": False,
            "repeat": repeat,
            "repeat_of": repeat_of,
        },
    }


def _lab(index, can_win, wants):
    return {
        "index": index,
        "input_hash": f"sha256:{index}",
        "can_win_cold": can_win,
        "wants": wants,
        "labeled_at": "2026-08-17T00:00:00+00:00",
    }


def _meta(keep_pop=25, keep_n=10, drop_pop=80, drop_n=10):
    return {
        "profile": "test",
        "seed": 7,
        "strata": {
            "KEEP": {"population": keep_pop, "sampled": keep_n, "p_draw": keep_n / keep_pop},
            "DROP": {"population": drop_pop, "sampled": drop_n, "p_draw": drop_n / drop_pop},
        },
        "population_base_rate_keep": keep_pop / (keep_pop + drop_pop),
    }


# ------------------------------------------------------------- reweighting


def test_weighting_changes_the_answer_and_the_weighted_one_is_reported():
    """The whole point: unweighted flatters. Pin the weighted result.

    KEEP p_draw = 10/25 = 0.4 -> weight 2.5
    DROP p_draw = 10/80 = 0.125 -> weight 8.0

    Two KEEP items, one a true positive and one a false positive.
    One DROP item that the human liked -> a false negative.

    unweighted precision = 1/2 = 50.0%, recall = 1/2 = 50.0%
    weighted   precision = 2.5/5.0 = 50.0%, recall = 2.5/(2.5+8.0) = 23.8%

    Recall is where the weights bite, because the missed item comes from the
    stratum that was deliberately under-drawn.
    """
    items = [_it(1, "KEEP"), _it(2, "KEEP"), _it(3, "DROP")]
    labels = {1: _lab(1, True, True), 2: _lab(2, False, False), 3: _lab(3, True, True)}
    conf = weighted_confusion(items, labels, _meta(), "can_win_cold")
    p, r = precision_recall(conf)

    assert conf == {"tp": 2.5, "fp": 2.5, "fn": 8.0, "tn": 0.0}
    assert p == pytest.approx(0.5)
    assert r == pytest.approx(2.5 / 10.5)
    assert r != pytest.approx(0.5), "recall matches the unweighted value; weights are not applied"


def test_missing_p_draw_raises_rather_than_defaulting():
    items = [_it(1, "KEEP")]
    labels = {1: _lab(1, True, True)}
    broken = {"strata": {"KEEP": {"population": 10, "sampled": 5}}}  # no p_draw
    with pytest.raises(SystemExit) as exc:
        weighted_confusion(items, labels, broken, "can_win_cold")
    assert "p_draw" in str(exc.value)
    assert "cannot be recovered" in str(exc.value)


def test_zero_p_draw_also_raises():
    items = [_it(1, "KEEP")]
    labels = {1: _lab(1, True, True)}
    broken = {"strata": {"KEEP": {"p_draw": 0.0}}}
    with pytest.raises(SystemExit):
        weighted_confusion(items, labels, broken, "can_win_cold")


# --------------------------------------------------------- repeats / ceiling


def test_repeat_pairs_match_on_job_id():
    items = [_it(1, "KEEP", job_id=100), _it(2, "KEEP", job_id=100, repeat=True, repeat_of=100)]
    labels = {1: _lab(1, True, True), 2: _lab(2, True, False)}
    pairs = repeat_pairs(items, labels)
    assert len(pairs) == 1
    assert pairs[0][0]["index"] == 1 and pairs[0][1]["index"] == 2


def test_self_consistency_reports_disagreement():
    items = [_it(1, "KEEP", job_id=100), _it(2, "KEEP", job_id=100, repeat=True, repeat_of=100)]
    labels = {1: _lab(1, True, True), 2: _lab(2, True, False)}
    sc = self_consistency(repeat_pairs(items, labels))
    assert sc["n_pairs"] == 1
    assert sc["axes"]["can_win_cold"]["agreement"] == pytest.approx(1.0)
    assert sc["axes"]["wants"]["agreement"] == pytest.approx(0.0)


def test_repeats_are_excluded_from_the_other_statistics():
    """Counting a posting twice inflates n and narrows the intervals."""
    items = [
        _it(1, "KEEP", job_id=100),
        _it(2, "KEEP", job_id=100, repeat=True, repeat_of=100),
        _it(3, "DROP", job_id=101),
    ]
    labels = {i: _lab(i, True, True) for i in (1, 2, 3)}
    assert filter_agreement(items, labels, "can_win_cold")["n"] == 2
    conf = weighted_confusion(items, labels, _meta(), "can_win_cold")
    assert conf["tp"] == pytest.approx(2.5), "the repeat was counted a second time"


def test_no_pairs_is_not_a_crash():
    sc = self_consistency([])
    assert sc["n_pairs"] == 0
    assert sc["axes"]["wants"]["agreement"] is None


# ----------------------------------------------------------------- agreement


def test_filter_agreement_names_both_sides():
    items = [_it(1, "KEEP"), _it(2, "DROP")]
    labels = {1: _lab(1, True, True), 2: _lab(2, False, False)}
    fa = filter_agreement(items, labels, "can_win_cold")
    assert fa["raw_agreement"] == pytest.approx(1.0)
    assert fa["compared"] == "filter KEEP/DROP vs your can_win_cold"


# ---------------------------------------------------------------- thresholds


def test_threshold_separates_a_clean_split():
    items = [_it(i, "KEEP", fit=float(i)) for i in range(1, 11)]
    labels = {i: _lab(i, i >= 6, i >= 6) for i in range(1, 11)}
    th = suggest_threshold(items, labels, "can_win_cold")
    assert th["threshold"] == pytest.approx(6.0)
    assert th["youden_j"] == pytest.approx(1.0)


def test_threshold_declines_when_one_sided():
    items = [_it(i, "KEEP", fit=float(i)) for i in range(1, 5)]
    labels = {i: _lab(i, True, True) for i in range(1, 5)}
    th = suggest_threshold(items, labels, "can_win_cold")
    assert th["threshold"] is None
    assert "both sides" in th["note"]


# ------------------------------------------------------------------ intervals


def test_bootstrap_is_deterministic_and_brackets_the_estimate():
    items = [_it(i, "KEEP" if i % 2 else "DROP", fit=float(i)) for i in range(1, 21)]
    labels = {i: _lab(i, i % 3 != 0, i % 3 != 0) for i in range(1, 21)}
    meta = _meta()
    a = bootstrap_ci(items, labels, meta, "can_win_cold", n_boot=300, seed=7)
    b = bootstrap_ci(items, labels, meta, "can_win_cold", n_boot=300, seed=7)
    assert a == b, "same seed must reproduce the interval"
    p, _ = precision_recall(weighted_confusion(items, labels, meta, "can_win_cold"))
    lo, hi = a["precision"]
    assert lo <= p <= hi
    assert lo < hi, "a degenerate interval hides the uncertainty it exists to show"


def test_bootstrap_declines_on_a_tiny_pool():
    assert bootstrap_ci([_it(1, "KEEP")], {1: _lab(1, True, True)}, _meta(),
                        "can_win_cold", n_boot=10, seed=1)["n_boot"] == 0


# -------------------------------------------------------------------- naming


def _report():
    items = [_it(i, "KEEP" if i % 2 else "DROP", fit=float(i)) for i in range(1, 13)]
    items.append(_it(99, "REPEAT", job_id=1, repeat=True, repeat_of=1))
    labels = {i: _lab(i, i % 2 == 1, i % 3 != 0) for i in range(1, 13)}
    labels[99] = _lab(99, True, True)
    return build_report({"items": items, "_meta": _meta()}, labels, n_boot=60)


def test_report_never_calls_agreement_accuracy():
    text = _report()
    assert "NOT accuracy" in text
    lowered = text.lower()
    for bad in ("filter accuracy", "accuracy of the filter", "judge accuracy"):
        assert bad not in lowered, f"report presents agreement as accuracy: {bad!r}"


def test_report_states_the_calibration_not_training_boundary():
    text = _report().lower()
    assert "not training" in text
    for bad in ("trained on your labels", "learned your preferences", "training set"):
        assert bad not in text, f"report overclaims training: {bad!r}"


def test_report_marks_self_consistency_as_a_ceiling():
    text = _report()
    assert "CEILING" in text
    assert "more than you agree with yourself" in text


def test_report_attaches_an_interval_to_every_rate():
    text = _report()
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(("precision ", "recall ")) and "n/a" not in s:
            assert "[" in s and "]" in s, f"rate quoted without an interval: {s!r}"


def test_report_says_unweighted_would_describe_the_sample():
    assert "not the population" in _report()


# --------------------------------------------------------------------- loading


def test_load_inputs_requires_labels(tmp_path):
    ls = tmp_path / "ls.json"
    ls.write_text(json.dumps({"_meta": _meta(), "items": [_it(1, "KEEP")]}))
    with pytest.raises(SystemExit) as exc:
        load_inputs(ls, tmp_path / "absent.jsonl")
    assert "no labels" in str(exc.value)


def test_load_inputs_skips_a_torn_line(tmp_path):
    ls = tmp_path / "ls.json"
    ls.write_text(json.dumps({"_meta": _meta(), "items": [_it(1, "KEEP")]}))
    lab = tmp_path / "labels.jsonl"
    lab.write_text(json.dumps(_lab(1, True, True)) + '\n{"index": 2, "can_wi')
    _, labels = load_inputs(ls, lab)
    assert set(labels) == {1}
