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

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from annotate import item_hash  # noqa: E402
from calibrate import (  # noqa: E402
    bootstrap_ci,
    build_report,
    filter_agreement,
    load_inputs,
    nearest_rank_percentile,
    precision_recall,
    repeat_accounting,
    repeat_pairs,
    response_rates,
    self_consistency,
    stratified_resample,
    suggest_threshold,
    usable_labels,
    validate_label_set,
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
    # A REAL input_hash. It previously used a placeholder, which meant every
    # label was silently discarded as stale once the hash gate landed -- and the
    # report tests kept passing, because they assert static text. Third instance
    # in this work of a test passing for the wrong reason.
    # input_hash covers title|company|description, all of which depend only on
    # the index in _it(), so this matches any _it(index, ...) variant.
    return {
        "index": index,
        "item_hash": item_hash(_it(index, "KEEP")),
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

    # NON-VACUITY GUARD. Every assertion below looks for static text, so they all
    # pass on an empty report. Prove the fixture's labels actually survive the
    # hash gate before trusting anything the report says.
    kept, stale = usable_labels(items, labels)
    assert stale == 0, f"{stale} fixture labels discarded as stale; the report is vacuous"
    assert len(kept) == len(labels), "fixture labels did not bind to items"

    text = build_report({"items": items, "_meta": _meta()}, labels, n_boot=60)
    assert "0 labelled" not in text, "report has no labels; its text assertions prove nothing"
    return text


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


# ===================================================================
# Regressions from the 2026-08-17 adversarial cross-review (codex).
# ===================================================================


def test_stale_labels_are_dropped_and_counted():
    """DEFECT 1: labels joined to items by index alone, ignoring input_hash."""
    items = [_it(1, "KEEP"), _it(2, "KEEP")]
    labels = {1: _lab(1, True, True), 2: {**_lab(2, True, True), "item_hash": "sha256:wrong"}}
    kept, stale = usable_labels(items, labels)
    assert set(kept) == {1}
    assert stale == 1


def test_stale_labels_never_reach_the_statistics():
    items = [_it(1, "KEEP"), _it(2, "DROP")]
    labels = {1: _lab(1, True, True), 2: {**_lab(2, True, True), "item_hash": "sha256:wrong"}}
    kept, _ = usable_labels(items, labels)
    conf = weighted_confusion(items, kept, _meta(), "can_win_cold")
    assert conf["fn"] == 0.0, "a stale label was counted as a false negative"


def test_nearest_rank_percentile_known_vectors():
    """DEFECT 5, tested against arithmetic rather than against itself.

    The first version of this test asserted `lo <= hi` and then restated the
    formula, so reverting the fix to the old mixed int() convention left it
    green. Mutation N8 caught that. These are hand-computed expectations.

    vals = 1..100, so vals[i] == i + 1 and the index is readable in the value.
      p=0.025 -> ceil(2.5) - 1 = 2      -> 3
      p=0.975 -> ceil(97.5) - 1 = 97    -> 98
    The old code gave int(2.5)-1 = 1 -> 2, and int(97.5) = 97 -> 98: wrong at
    the low end only, for this n.

    vals = 1..200 makes p*n integral at the top, where the old code was wrong:
      p=0.975 -> ceil(195) - 1 = 194    -> 195
    The old code gave int(195) = 195 -> 196.
    """
    hundred = list(range(1, 101))
    assert nearest_rank_percentile(hundred, 0.025) == 3
    assert nearest_rank_percentile(hundred, 0.975) == 98

    two_hundred = list(range(1, 201))
    assert nearest_rank_percentile(two_hundred, 0.975) == 195, (
        "integral p*n at the upper endpoint: the old int() convention returned 196"
    )
    assert nearest_rank_percentile(two_hundred, 0.025) == 5

    # Endpoints and degenerate sizes must stay in range.
    assert nearest_rank_percentile([7.0], 0.025) == 7.0
    assert nearest_rank_percentile([7.0], 0.975) == 7.0
    assert nearest_rank_percentile([2, 1], 0.0) == 1
    assert nearest_rank_percentile([2, 1], 1.0) == 2


def test_nearest_rank_percentile_sorts_its_input():
    assert nearest_rank_percentile([9, 1, 5], 0.0) == 1


def test_nearest_rank_percentile_rejects_empty():
    with pytest.raises(ValueError):
        nearest_rank_percentile([], 0.5)


def test_stratified_resample_preserves_every_stratum_count():
    """DEFECT 3: the bootstrap pooled the strata.

    The design draws a FIXED count from each stratum, so each replicate must
    too. Pooled resampling can produce a replicate with no DROP items at all,
    which widens the interval with variance the design never had.
    """
    import random as _random

    by_stratum = {
        "KEEP": [_it(i, "KEEP") for i in range(1, 6)],
        "DROP": [_it(i, "DROP") for i in range(6, 21)],
    }
    for seed in range(20):
        draw = stratified_resample(by_stratum, _random.Random(seed))
        counts: dict[str, int] = {}
        for it in draw:
            st = it["_hidden"]["stratum"]
            counts[st] = counts.get(st, 0) + 1
        assert counts == {"KEEP": 5, "DROP": 15}, (
            f"seed {seed} produced {counts}; a replicate must keep the design's counts"
        )


def test_stratified_resample_actually_resamples():
    """It must vary within a stratum, or the interval would be degenerate."""
    import random as _random

    by_stratum = {"KEEP": [_it(i, "KEEP") for i in range(1, 11)]}
    seen = set()
    for seed in range(10):
        draw = stratified_resample(by_stratum, _random.Random(seed))
        seen.add(tuple(it["index"] for it in draw))
    assert len(seen) > 1, "every replicate identical; nothing is being resampled"


def test_response_rates_expose_partial_labelling():
    """DEFECT 4: p_draw alone assumes every drawn item got labelled."""
    items = [_it(i, "KEEP") for i in range(1, 4)] + [_it(i, "DROP") for i in range(4, 7)]
    labels = {1: _lab(1, True, True), 4: _lab(4, False, False)}
    rates = response_rates(items, labels, _meta())
    assert rates["KEEP"] == {"drawn": 3, "labelled": 1, "rate": pytest.approx(1 / 3)}
    assert rates["DROP"]["rate"] == pytest.approx(1 / 3)


def test_nonresponse_adjustment_changes_the_weight():
    items = [_it(1, "KEEP"), _it(2, "KEEP")]
    labels = {1: _lab(1, True, True)}  # half the stratum labelled
    meta = _meta()
    plain = weighted_confusion(items, labels, meta, "can_win_cold")
    adj = weighted_confusion(items, labels, meta, "can_win_cold",
                             rates=response_rates(items, labels, meta))
    assert adj["tp"] == pytest.approx(plain["tp"] * 2), "response rate not applied"


def test_report_warns_when_a_stratum_is_incomplete():
    items = [_it(i, "KEEP", fit=float(i)) for i in range(1, 5)]
    items += [_it(i, "DROP", fit=float(i)) for i in range(5, 9)]
    labels = {i: _lab(i, i <= 4, i <= 4) for i in (1, 2, 5, 6)}  # half of each
    text = build_report({"items": items, "_meta": _meta()}, labels, n_boot=40)
    assert "RESPONSE" in text
    assert "not fully labelled" in text
    assert "ASSUMES what you skipped is unrelated" in text


def test_duplicate_non_repeat_job_id_is_rejected():
    """DEFECT 6: whichever duplicate came last silently became the original."""
    items = [
        _it(1, "KEEP", job_id=100),
        _it(7, "KEEP", job_id=100),
        _it(9, "KEEP", job_id=100, repeat=True, repeat_of=100),
    ]
    labels = {i: _lab(i, True, True) for i in (1, 7, 9)}
    with pytest.raises(SystemExit) as exc:
        repeat_pairs(items, labels)
    assert "two non-repeat items" in str(exc.value)


def test_repeat_accounting_surfaces_orphans_and_unlabelled():
    items = [
        _it(1, "KEEP", job_id=100),                               # original A
        _it(5, "KEEP", job_id=101),                               # original B
        _it(2, "KEEP", job_id=100, repeat=True, repeat_of=100),   # pairs with A
        _it(3, "KEEP", job_id=999, repeat=True, repeat_of=555),   # orphan: no original
        _it(4, "KEEP", job_id=101, repeat=True, repeat_of=101),   # has B, but unlabelled
    ]
    labels = {1: _lab(1, True, True), 2: _lab(2, True, True),
              3: _lab(3, True, True), 5: _lab(5, True, True)}
    acc = repeat_accounting(items, labels)
    assert acc["drawn"] == 3
    assert acc["labelled"] == 2
    assert acc["orphaned_no_original"] == 1
    assert acc["complete_pairs"] == 1


def test_threshold_refuses_when_all_scores_are_equal():
    """DEFECT 7: returned a cutoff with Youden J = 0 and called it suggested."""
    items = [_it(i, "KEEP", fit=5.0) for i in range(1, 5)]
    labels = {1: _lab(1, True, True), 2: _lab(2, True, True),
              3: _lab(3, False, False), 4: _lab(4, False, False)}
    th = suggest_threshold(items, labels, "can_win_cold")
    assert th["threshold"] is None
    assert "same fit_score" in th["note"]


def test_threshold_refuses_when_youden_j_is_non_positive():
    # Scores vary but are anti-correlated in a way that gives no positive J.
    items = [_it(1, "KEEP", fit=1.0), _it(2, "KEEP", fit=2.0),
             _it(3, "KEEP", fit=3.0), _it(4, "KEEP", fit=4.0)]
    labels = {1: _lab(1, True, True), 2: _lab(2, False, False),
              3: _lab(3, True, True), 4: _lab(4, False, False)}
    th = suggest_threshold(items, labels, "can_win_cold")
    if th["threshold"] is None:
        assert "worse than useless" in th["note"] or "same fit_score" in th["note"]
    else:
        assert th["youden_j"] > 0, "returned a cutoff with no discriminatory value"


def test_threshold_reports_score_coverage():
    items = [_it(i, "KEEP", fit=float(i)) for i in range(1, 4)]
    items.append(_it(4, "KEEP", fit=None))
    labels = {i: _lab(i, i >= 2, i >= 2) for i in range(1, 5)}
    th = suggest_threshold(items, labels, "can_win_cold")
    assert th["n_labelled"] == 4
    assert th["n_scored"] == 3


def test_calibrate_and_annotate_agree_on_corruption(tmp_path):
    """DEFECT 8: two loaders, same file, different verdicts."""
    import annotate as ann
    ls = tmp_path / "ls.json"
    ls.write_text(json.dumps({"_meta": _meta(), "items": [_it(1, "KEEP")]}))
    lab = tmp_path / "lab.jsonl"
    lab.write_text('{"index":1,"can_win_cold":true,"wants":true}\n{"index":2,"corrupt\n')

    with pytest.raises(SystemExit):
        ann.load_labels(lab)
    with pytest.raises(SystemExit):
        load_inputs(ls, lab)



# ===================================================================
# Regressions from the 2026-08-18 adversarial security review (codex).
# ===================================================================


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0, 0.0, 1.5, "0.5", True, None])
def test_invalid_p_draw_is_rejected(bad):
    """`if not p:` waved NaN and Infinity through, because both are truthy.

    1/NaN is nan, which then propagates into every statistic and prints as
    "nan%" beside real numbers -- a corrupted report that looks like a report.
    Python's json accepts NaN and Infinity by default, so a label set can carry
    them without being malformed.
    """
    items = [_it(1, "KEEP")]
    labels = {1: _lab(1, True, True)}
    meta = {"strata": {"KEEP": {"p_draw": bad}}}
    with pytest.raises(SystemExit) as exc:
        weighted_confusion(items, labels, meta, "can_win_cold")
    assert "p_draw" in str(exc.value)


def test_valid_p_draw_still_accepted():
    items = [_it(1, "KEEP")]
    labels = {1: _lab(1, True, True)}
    conf = weighted_confusion(items, labels, {"strata": {"KEEP": {"p_draw": 0.25}}}, "can_win_cold")
    assert conf["tp"] == pytest.approx(4.0)


@pytest.mark.parametrize("payload,expect", [
    ([], "top level"),
    ({"_meta": [], "items": []}, "_meta"),
    ({"_meta": {}, "items": {}}, "items must be a list"),
    ({"_meta": {}, "items": [[]]}, "must be an object"),
    ({"_meta": {}, "items": [{"index": "1", "_hidden": {}}]}, "index must be an int"),
    ({"_meta": {}, "items": [{"index": 1, "_hidden": []}]}, "_hidden must be an object"),
    ({"_meta": {}, "items": [{"index": 1, "_hidden": {}},
                              {"index": 1, "_hidden": {}}]}, "duplicate"),
])
def test_malformed_label_set_is_rejected(payload, expect, tmp_path):
    """Without this, a bad file surfaces as an AttributeError inside a statistic."""
    with pytest.raises(SystemExit) as exc:
        validate_label_set(payload, tmp_path / "ls.json")
    assert expect in str(exc.value)


def test_wellformed_label_set_passes(tmp_path):
    validate_label_set({"_meta": _meta(), "items": [_it(1, "KEEP"), _it(2, "DROP")]},
                       tmp_path / "ls.json")


def test_load_inputs_actually_validates(tmp_path):
    """The validator must be WIRED IN, not merely present.

    The earlier tests called validate_label_set() directly, so deleting its call
    site in load_inputs() left them all green. Same shape as the blindness test
    that passed with the projection removed: a guard tested in isolation proves
    the guard works, never that anything invokes it.
    """
    ls = tmp_path / "ls.json"
    ls.write_text(json.dumps({"_meta": _meta(), "items": [{"index": "not-an-int", "_hidden": {}}]}))
    lab = tmp_path / "lab.jsonl"
    lab.write_text(json.dumps(_lab(1, True, True)) + "\n")

    with pytest.raises(SystemExit) as exc:
        load_inputs(ls, lab)
    assert "index must be an int" in str(exc.value), (
        "load_inputs accepted a malformed label set; the validator is not wired in"
    )
