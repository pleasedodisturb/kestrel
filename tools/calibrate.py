#!/usr/bin/env python3
"""Report what your own labels say about the filter, and about the labels.

This is calibration and measurement. It is NOT training
------------------------------------------------------
Two to five hundred labels from one person are not a training set, and the
reason is not the count. Fifty to a hundred examples is enough to move a
fine-tune; the reason is *population*. These labels encode one installer's
taste, market and circumstances. Baking them into Kestrel's shared scoring path
would make every other user's results worse in a way none of them could see.

What labels this size legitimately buy:

* **threshold calibration** — where to put your own keep/drop cutoff
* **agreement measurement** — how far the automated judge is from you, which is
  the check that catches a filter drifting away from its user
* **a self-consistency ceiling** — how far *you* are from you, which bounds how
  well any judge could possibly score
* **drift detection** over time, via the population-stability machinery already
  in ``scoring_eval``

Anything in this file that reads like "the model learned your preferences" is a
bug in the wording. Say calibrated.

Three things this report refuses to do
--------------------------------------
1. **It never calls agreement "accuracy".** Every agreement figure is named for
   both things being compared. Reporting judge-agreement as accuracy is the
   specific error that put a false number on a CV, so the metric names here
   carry their own basis.

2. **It never quotes a rate without an interval.** Point estimates from a couple
   of hundred items are wide, and a bare 53% invites a conclusion the sample
   cannot support. Intervals are bootstrapped over the reweighted estimator, so
   they describe the number actually being reported.

3. **It never reports sample rates as population rates.** Precision and recall
   are reweighted by the per-stratum draw probabilities that
   ``build_label_set.py`` recorded, because the sample is deliberately balanced
   and the population is not.

Usage
-----
    python tools/calibrate.py
    python tools/calibrate.py --axis wants --bootstrap 4000
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
sys.path.insert(0, str(_REPO / "src"))

from career_os.services.scoring_eval import weighted_cohen_kappa  # noqa: E402

sys.path.insert(0, str(_HERE))
from annotate import label_matches_item as _label_matches_item  # noqa: E402
from annotate import load_labels as _load_labels  # noqa: E402

DEFAULT_LABEL_SET = _REPO / "data" / "label_set.json"
DEFAULT_LABELS = _REPO / "data" / "labels.jsonl"

AXES = ("can_win_cold", "wants")


# --------------------------------------------------------------------- loading


def load_inputs(label_set_path: Path, labels_path: Path) -> tuple[dict, dict[int, dict]]:
    if not label_set_path.exists():
        raise SystemExit(f"no label set at {label_set_path}")
    if not labels_path.exists():
        raise SystemExit(
            f"no labels at {labels_path}\nlabel some postings first: python tools/annotate.py"
        )
    data = json.loads(label_set_path.read_text())
    # Reuse annotate's loader rather than reimplementing it. A second, more
    # permissive parser here meant a corrupt MID-FILE line raised in annotate.py
    # and vanished silently in calibrate.py -- the same file, two verdicts, and
    # the quieter one feeding the statistics.
    labels = _load_labels(labels_path)
    if not labels:
        raise SystemExit(f"{labels_path} holds no usable labels")
    return data, labels


def usable_labels(items: list[dict], labels: dict[int, dict]) -> tuple[dict[int, dict], int]:
    """Drop labels whose posting text has changed. Returns (kept, n_stale).

    Labels join to items by ``index``, and indices are reused whenever a label
    set is rebuilt, so the stored ``input_hash`` is the only thing that makes the
    join trustworthy. It was previously stored and never compared.
    """
    kept: dict[int, dict] = {}
    stale = 0
    for it in items:
        rec = labels.get(it["index"])
        if rec is None:
            continue
        if _label_matches_item(it, rec):
            kept[it["index"]] = rec
        else:
            stale += 1
    return kept, stale


# ------------------------------------------------------- self-consistency


def repeat_pairs(items: list[dict], labels: dict[int, dict]) -> list[tuple[dict, dict]]:
    """Pair each labelled repeat with the labelled original of the same posting."""
    by_job: dict[int, int] = {}
    for it in items:
        h = it.get("_hidden") or {}
        if h.get("repeat") or h.get("job_id") is None:
            continue
        if h["job_id"] in by_job:
            # Two non-repeat items for one posting: `repeat_of` carries only a
            # job_id, so there is no way to know which one a repeat pairs with.
            # Silently taking the last would make self-consistency depend on
            # list order.
            raise SystemExit(
                f"label set has two non-repeat items for job_id {h['job_id']} "
                f"(indices {by_job[h['job_id']]} and {it['index']}). A repeat "
                f"cannot be paired unambiguously; rebuild the label set."
            )
        by_job[h["job_id"]] = it["index"]

    pairs = []
    for it in items:
        h = it.get("_hidden") or {}
        if not h.get("repeat"):
            continue
        origin_index = by_job.get(h.get("repeat_of"))
        if origin_index is None:
            continue
        a, b = labels.get(origin_index), labels.get(it["index"])
        if a and b:
            pairs.append((a, b))
    return pairs


def repeat_accounting(items: list[dict], labels: dict[int, dict]) -> dict:
    """Where every drawn repeat went.

    Only the final pair count used to be reported, so a repeat that was drawn
    but never labelled, or whose original was never labelled, vanished from the
    report. A shrinking denominator that nothing mentions is how a ceiling
    quietly stops meaning anything.
    """
    originals = {
        (it.get("_hidden") or {}).get("job_id")
        for it in items
        if not (it.get("_hidden") or {}).get("repeat")
    }
    drawn = labelled = orphaned = 0
    for it in items:
        h = it.get("_hidden") or {}
        if not h.get("repeat"):
            continue
        drawn += 1
        if it["index"] in labels:
            labelled += 1
        if h.get("repeat_of") not in originals:
            orphaned += 1
    return {
        "drawn": drawn,
        "labelled": labelled,
        "orphaned_no_original": orphaned,
        "complete_pairs": len(repeat_pairs(items, labels)),
    }


def self_consistency(pairs: list[tuple[dict, dict]]) -> dict:
    """How often you agreed with yourself. This is a CEILING, not a target.

    A judge cannot be more consistent with you than you are with yourself, so
    every agreement figure below is bounded by this. It is explicitly not
    something to chase: the one controlled study of purposively boundary-drawn
    repeats reports ~74% intra-annotator agreement and argues against treating
    that as a goal.
    """
    out: dict = {"n_pairs": len(pairs), "axes": {}}
    for axis in AXES:
        if not pairs:
            out["axes"][axis] = {"agreement": None, "kappa": None}
            continue
        first = [int(bool(a[axis])) for a, _ in pairs]
        second = [int(bool(b[axis])) for _, b in pairs]
        agree = sum(1 for x, y in zip(first, second, strict=True) if x == y) / len(pairs)
        try:
            kappa = weighted_cohen_kappa(first, second, num_classes=2)
        except ValueError:
            kappa = None
        out["axes"][axis] = {"agreement": agree, "kappa": kappa}
    return out


# ------------------------------------------------- agreement with the filter


def filter_agreement(items: list[dict], labels: dict[int, dict], axis: str) -> dict:
    """κ between the filter's KEEP/DROP and one of your axes.

    Named for both sides on purpose. This is NOT the filter's accuracy:

    * against ``can_win_cold`` the filter is judged on a STRICTLY STRONGER
      criterion than it implements. The geo filter decides eligibility; you also
      weighed competitiveness. Disagreement here is a lower bound on the
      filter's geo correctness, not a measure of it.
    * against ``wants`` it is being judged on something it never modelled at
      all. Low agreement is expected and is not a defect.
    """
    y_filter: list[int] = []
    y_human: list[int] = []
    for it in items:
        h = it.get("_hidden") or {}
        if h.get("repeat"):
            continue  # a repeat would double-count one posting
        rec = labels.get(it["index"])
        if rec is None:
            continue
        y_filter.append(1 if h.get("stratum") == "KEEP" else 0)
        y_human.append(int(bool(rec[axis])))
    if not y_filter:
        return {"n": 0, "kappa": None, "raw_agreement": None}
    return {
        "n": len(y_filter),
        "kappa": weighted_cohen_kappa(y_human, y_filter, num_classes=2),
        "raw_agreement": sum(
            1 for a, b in zip(y_filter, y_human, strict=True) if a == b
        ) / len(y_filter),
        "compared": f"filter KEEP/DROP vs your {axis}",
    }


# --------------------------------------------- reweighted precision / recall


def _weight_for(stratum: str, meta: dict) -> float:
    """Horvitz-Thompson weight: one over the probability this item was drawn."""
    strata = meta.get("strata") or {}
    p = (strata.get(stratum) or {}).get("p_draw")
    if not p:
        raise SystemExit(
            f"label set _meta has no usable p_draw for stratum {stratum!r}.\n"
            "Sample rates cannot be reweighted to the population without it, and "
            "it cannot be recovered after the draw. Rebuild the label set."
        )
    return 1.0 / p


def response_rates(items: list[dict], labels: dict[int, dict], meta: dict) -> dict:
    """Per-stratum share of DRAWN items that actually got labelled.

    Reweighting by ``p_draw`` alone assumes every sampled item was labelled. If
    a stratum is half-labelled, dividing by the draw probability credits the
    labelled half with representing the whole stratum. That is only defensible
    if what got skipped was unrelated to the answer, which for a human skipping
    the hard ones is exactly the assumption most likely to be false.
    """
    out: dict[str, dict] = {}
    for it in items:
        h = it.get("_hidden") or {}
        if h.get("repeat"):
            continue
        st = h.get("stratum")
        row = out.setdefault(st, {"drawn": 0, "labelled": 0})
        row["drawn"] += 1
        if it["index"] in labels:
            row["labelled"] += 1
    for row in out.values():
        row["rate"] = (row["labelled"] / row["drawn"]) if row["drawn"] else 0.0
    return out


def weighted_confusion(
    items: list[dict],
    labels: dict[int, dict],
    meta: dict,
    axis: str,
    *,
    rates: dict | None = None,
) -> dict[str, float]:
    """Confusion counts weighted back to the population base rate.

    The sample is ~50/50 by construction; the population is not. Counting
    unweighted answers "how did the filter do on this deliberately balanced
    sample", which is a different and much more flattering question.
    """
    tp = fp = fn = tn = 0.0
    for it in items:
        h = it.get("_hidden") or {}
        if h.get("repeat"):
            continue
        rec = labels.get(it["index"])
        if rec is None:
            continue
        w = _weight_for(h.get("stratum"), meta)
        if rates:
            # Nonresponse adjustment. Assumes what was skipped within a stratum
            # is unrelated to the label (MCAR within stratum) -- stated, not
            # assumed silently, and the report warns whenever it bites.
            rate = (rates.get(h.get("stratum")) or {}).get("rate") or 0.0
            if rate <= 0:
                continue
            w /= rate
        kept = h.get("stratum") == "KEEP"
        good = bool(rec[axis])
        if kept and good:
            tp += w
        elif kept and not good:
            fp += w
        elif not kept and good:
            fn += w
        else:
            tn += w
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def precision_recall(c: dict[str, float]) -> tuple[float | None, float | None]:
    p = c["tp"] / (c["tp"] + c["fp"]) if (c["tp"] + c["fp"]) else None
    r = c["tp"] / (c["tp"] + c["fn"]) if (c["tp"] + c["fn"]) else None
    return p, r


def nearest_rank_percentile(vals: list[float], p: float) -> float:
    """Nearest-rank percentile: idx = ceil(p * n) - 1, clamped.

    ONE convention for both endpoints. The original used ``int(p*n) - 1`` at the
    low end and ``int(p*n)`` at the high end, which is off by one at the low end
    when ``p*n`` is non-integral and off by one at the high end when it is. Two
    conventions inside a single interval is worse than either one alone, and it
    was invisible because the interval still looked plausible.

    Lives at module level so it can be tested against known vectors. As a closure
    it could only be reached through a bootstrap, which is how the first attempt
    at testing it ended up asserting a tautology.
    """
    if not vals:
        raise ValueError("cannot take a percentile of an empty sequence")
    ordered = sorted(vals)
    n = len(ordered)
    return ordered[min(n - 1, max(0, math.ceil(p * n) - 1))]


def stratified_resample(by_stratum: dict[str, list[dict]], rng: random.Random) -> list[dict]:
    """One bootstrap replicate: resample WITH replacement inside each stratum.

    Each stratum contributes exactly as many items as it did in the real sample,
    because that is what the sampling design does. Pooling the strata and drawing
    n from the mixture adds variance from random stratum composition that the
    design never had, and can yield a replicate containing no DROP items at all.
    """
    draw: list[dict] = []
    for members in by_stratum.values():
        k = len(members)
        draw.extend(members[rng.randrange(k)] for _ in range(k))
    return draw


def bootstrap_ci(
    items: list[dict],
    labels: dict[int, dict],
    meta: dict,
    axis: str,
    *,
    n_boot: int,
    seed: int,
) -> dict:
    """Percentile CI for the REWEIGHTED estimates, by resampling items.

    The interval is bootstrapped over the same weighted estimator that produces
    the headline number, so the two describe the same quantity. Quoting a
    Wilson interval on the unweighted proportion beside a reweighted point
    estimate would silently pair a number with an interval for a different
    statistic.
    """
    by_stratum: dict[str, list[dict]] = {}
    for it in items:
        h = it.get("_hidden") or {}
        if h.get("repeat") or it["index"] not in labels:
            continue
        by_stratum.setdefault(h.get("stratum"), []).append(it)

    pool_size = sum(len(v) for v in by_stratum.values())
    if pool_size < 2:
        return {"precision": None, "recall": None, "n_boot": 0}

    rates = response_rates(items, labels, meta)
    rng = random.Random(seed)
    ps: list[float] = []
    rs: list[float] = []
    for _ in range(n_boot):
        # Resample WITHIN each stratum, preserving its observed count. Pooling
        # the strata and drawing n from the mixture injects variance from random
        # stratum composition that the design never had -- the design always
        # draws a fixed number from each -- and it can produce a replicate with
        # no DROP items at all.
        draw = stratified_resample(by_stratum, rng)
        p, r = precision_recall(weighted_confusion(draw, labels, meta, axis, rates=rates))
        if p is not None:
            ps.append(p)
        if r is not None:
            rs.append(r)

    def pct(vals: list[float]) -> list[float] | None:
        if not vals:
            return None
        return [
            nearest_rank_percentile(vals, 0.025),
            nearest_rank_percentile(vals, 0.975),
        ]

    return {"precision": pct(ps), "recall": pct(rs), "n_boot": n_boot}


# ------------------------------------------------------------- thresholds


def suggest_threshold(items: list[dict], labels: dict[int, dict], axis: str) -> dict:
    """Sweep fit_score cutoffs and pick the one maximising Youden's J.

    J = sensitivity + specificity - 1, which weights both errors equally and
    does not depend on the sample's class balance -- the right property here,
    since the balance was chosen by the sampler rather than observed.
    """
    rows = []
    for it in items:
        h = it.get("_hidden") or {}
        if h.get("repeat") or h.get("fit_score") is None:
            continue
        rec = labels.get(it["index"])
        if rec is None:
            continue
        rows.append((float(h["fit_score"]), bool(rec[axis])))

    n_labelled = sum(1 for it in items if it["index"] in labels
                     and not (it.get("_hidden") or {}).get("repeat"))
    coverage = {"n_scored": len(rows), "n_labelled": n_labelled}

    if len(rows) < 2 or len({g for _, g in rows}) < 2:
        return {
            "threshold": None,
            **coverage,
            "note": "need labelled items on both sides of the axis to place a cutoff",
        }
    if len({s for s, _ in rows}) < 2:
        return {
            "threshold": None,
            **coverage,
            "note": "every scored item has the same fit_score; no cutoff can separate them",
        }

    best = None
    for cut in sorted({s for s, _ in rows}):
        tp = sum(1 for s, g in rows if s >= cut and g)
        fn = sum(1 for s, g in rows if s < cut and g)
        fp = sum(1 for s, g in rows if s >= cut and not g)
        tn = sum(1 for s, g in rows if s < cut and not g)
        sens = tp / (tp + fn) if (tp + fn) else 0.0
        spec = tn / (tn + fp) if (tn + fp) else 0.0
        j = sens + spec - 1
        if best is None or j > best["youden_j"]:
            best = {"threshold": cut, "sensitivity": sens, "specificity": spec, "youden_j": j}

    if best is None or best["youden_j"] <= 0:
        return {
            "threshold": None,
            **coverage,
            "note": (
                "best Youden J is "
                f"{(best or {}).get('youden_j', 0):.3f} (<= 0): fit_score carries no "
                "discriminatory information for this axis, so any cutoff would be "
                "worse than useless"
            ),
        }
    return {**best, **coverage}


# ---------------------------------------------------------------- reporting


def _fmt(x: float | None, pct: bool = True) -> str:
    if x is None:
        return "n/a"
    return f"{x * 100:.1f}%" if pct else f"{x:.3f}"


def _fmt_ci(ci: list[float] | None) -> str:
    if not ci:
        return ""
    return f"  [{ci[0] * 100:.1f}%, {ci[1] * 100:.1f}%]"


def build_report(data: dict, labels: dict[int, dict], *, n_boot: int) -> str:
    items, meta = data["items"], data["_meta"]
    lines: list[str] = []
    add = lines.append

    labels, n_stale = usable_labels(items, labels)
    labelled = sum(1 for it in items if it["index"] in labels)
    rates = response_rates(items, labels, meta)

    add("CALIBRATION REPORT")
    add(f"  label set : {len(items)} items, {labelled} labelled")
    if n_stale:
        add(f"  ! {n_stale} label(s) DISCARDED: the posting text changed since they")
        add("    were written, so their input_hash no longer matches. They are not")
        add("    counted anywhere below.")
    add(f"  profile   : {meta.get('profile')}   seed: {meta.get('seed')}")
    add(f"  base rate : {_fmt(meta.get('population_base_rate_keep'))} of the population is KEEP")
    add("")
    add("  RESPONSE (labelled / drawn, per stratum)")
    incomplete = []
    for st, row in sorted(rates.items()):
        add(f"    {st:6} {row['labelled']}/{row['drawn']}  = {_fmt(row['rate'])}")
        if row["rate"] < 1.0:
            incomplete.append(st)
    if incomplete:
        add(f"  ! {', '.join(incomplete)} not fully labelled. Population figures below are")
        add("    adjusted by these rates, which ASSUMES what you skipped is unrelated")
        add("    to the answer. If you skipped the hard ones, that assumption is false")
        add("    and the population numbers are not trustworthy. Label the rest.")
    add("")
    add("  This is calibration, not training. These labels are one person's")
    add("  taste and must not enter a shared scoring path.")
    add("")

    ra = repeat_accounting(items, labels)
    add("REPEATS  drawn {drawn}, labelled {labelled}, complete pairs {complete_pairs}"
        .format(**ra) + (f", orphaned {ra['orphaned_no_original']}"
                         if ra["orphaned_no_original"] else ""))
    if ra["complete_pairs"] < ra["drawn"]:
        add(f"  ! {ra['drawn'] - ra['complete_pairs']} drawn repeat(s) did not become a pair")
        add("    (repeat or original unlabelled). The ceiling below rests on fewer")
        add("    observations than were drawn for it.")
    add("")

    sc = self_consistency(repeat_pairs(items, labels))
    add(f"SELF-CONSISTENCY  (n={sc['n_pairs']} repeat pairs)  -- a CEILING, not a target")
    for axis in AXES:
        a = sc["axes"][axis]
        add(f"  {axis:14} agreement {_fmt(a['agreement'])}   kappa {_fmt(a['kappa'], pct=False)}")
    if sc["n_pairs"] < 10:
        add("  ! too few pairs to read much into; treat as indicative only")
    add("  No judge can agree with you more than you agree with yourself.")
    add("")

    for axis in AXES:
        fa = filter_agreement(items, labels, axis)
        add(f"FILTER vs YOUR {axis.upper()}  (n={fa['n']})   -- agreement, NOT accuracy")
        add(f"  kappa {_fmt(fa['kappa'], pct=False)}   raw agreement {_fmt(fa['raw_agreement'])}")
        if axis == "can_win_cold":
            add("  The filter decides eligibility; you also weighed competitiveness.")
            add("  So this is a LOWER BOUND on its geo correctness, not a measure of it.")
        else:
            add("  The filter never modelled desire. Low agreement here is expected,")
            add("  and is not a defect.")
        add("")

    for axis in AXES:
        conf = weighted_confusion(items, labels, meta, axis, rates=rates)
        p, r = precision_recall(conf)
        ci = bootstrap_ci(items, labels, meta, axis, n_boot=n_boot, seed=meta.get("seed", 0))
        add(f"REWEIGHTED TO POPULATION  (filter KEEP as the prediction, {axis} as truth)")
        add(f"  precision {_fmt(p)}{_fmt_ci(ci['precision'])}")
        add(f"  recall    {_fmt(r)}{_fmt_ci(ci['recall'])}")
        add(f"  intervals: {ci['n_boot']} bootstrap resamples of the weighted estimator")
        add("  Unweighted rates would describe the balanced SAMPLE, not the population.")
        add("")

    for axis in AXES:
        th = suggest_threshold(items, labels, axis)
        add(f"SUGGESTED CUTOFF for {axis}")
        if th.get("threshold") is None:
            add(f"  none -- {th.get('note')}")
            add(f"  (scored {th.get('n_scored')} of {th.get('n_labelled')} labelled items)")
        else:
            add(
                f"  fit_score >= {th['threshold']:.2f}   "
                f"(scored {th['n_scored']} of {th['n_labelled']} labelled items)"
            )
            if th["n_labelled"] and th["n_scored"] / th["n_labelled"] < 0.5:
                add("  ! fewer than half the labelled items carry a fit_score, so this")
                add("    cutoff is derived from a minority and may be selectively scored.")
            add(
                f"  sensitivity {_fmt(th['sensitivity'])}  "
                f"specificity {_fmt(th['specificity'])}  "
                f"Youden J {th['youden_j']:.3f}"
            )
        add("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--label-set", type=Path, default=DEFAULT_LABEL_SET)
    ap.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    ap.add_argument("--bootstrap", type=int, default=2000)
    ap.add_argument("--json", action="store_true", help="emit machine-readable output")
    args = ap.parse_args(argv)

    data, labels = load_inputs(args.label_set, args.labels)

    if args.json:
        items, meta = data["items"], data["_meta"]
        labels, n_stale = usable_labels(items, labels)
        rates = response_rates(items, labels, meta)
        payload = {
            "discarded_stale_labels": n_stale,
            "response_rates": rates,
            "repeats": repeat_accounting(items, labels),
            "self_consistency": self_consistency(repeat_pairs(items, labels)),
            "filter_agreement": {a: filter_agreement(items, labels, a) for a in AXES},
            "reweighted": {
                a: {
                    "confusion": weighted_confusion(items, labels, meta, a, rates=rates),
                    "ci": bootstrap_ci(
                        items, labels, meta, a, n_boot=args.bootstrap, seed=meta.get("seed", 0)
                    ),
                }
                for a in AXES
            },
            "thresholds": {a: suggest_threshold(items, labels, a) for a in AXES},
            "note": "calibration and measurement only; not training data",
        }
        print(json.dumps(payload, indent=2))
    else:
        print(build_report(data, labels, n_boot=args.bootstrap))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
