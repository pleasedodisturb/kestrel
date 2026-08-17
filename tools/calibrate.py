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
import random
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
sys.path.insert(0, str(_REPO / "src"))

from career_os.services.scoring_eval import weighted_cohen_kappa  # noqa: E402

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
    labels: dict[int, dict] = {}
    for line in labels_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue  # torn final line; annotate.py owns reporting that
        labels[rec["index"]] = rec
    if not labels:
        raise SystemExit(f"{labels_path} holds no usable labels")
    return data, labels


# ------------------------------------------------------- self-consistency


def repeat_pairs(items: list[dict], labels: dict[int, dict]) -> list[tuple[dict, dict]]:
    """Pair each labelled repeat with the labelled original of the same posting."""
    by_job: dict[int, int] = {}
    for it in items:
        h = it.get("_hidden") or {}
        if not h.get("repeat") and h.get("job_id") is not None:
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


def weighted_confusion(
    items: list[dict], labels: dict[int, dict], meta: dict, axis: str
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
    pool = [
        it
        for it in items
        if not (it.get("_hidden") or {}).get("repeat") and it["index"] in labels
    ]
    if len(pool) < 2:
        return {"precision": None, "recall": None, "n_boot": 0}

    rng = random.Random(seed)
    ps: list[float] = []
    rs: list[float] = []
    for _ in range(n_boot):
        draw = [pool[rng.randrange(len(pool))] for _ in range(len(pool))]
        p, r = precision_recall(weighted_confusion(draw, labels, meta, axis))
        if p is not None:
            ps.append(p)
        if r is not None:
            rs.append(r)

    def pct(vals: list[float]) -> list[float] | None:
        if not vals:
            return None
        vals = sorted(vals)
        lo = vals[max(0, int(0.025 * len(vals)) - 1)]
        hi = vals[min(len(vals) - 1, int(0.975 * len(vals)))]
        return [lo, hi]

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

    if len(rows) < 2 or len({g for _, g in rows}) < 2:
        return {
            "threshold": None,
            "n": len(rows),
            "note": "need labelled items on both sides of the axis to place a cutoff",
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
    return {**best, "n": len(rows)}


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

    labelled = sum(1 for it in items if it["index"] in labels)
    add("CALIBRATION REPORT")
    add(f"  label set : {len(items)} items, {labelled} labelled")
    add(f"  profile   : {meta.get('profile')}   seed: {meta.get('seed')}")
    add(f"  base rate : {_fmt(meta.get('population_base_rate_keep'))} of the population is KEEP")
    add("")
    add("  This is calibration, not training. These labels are one person's")
    add("  taste and must not enter a shared scoring path.")
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
        conf = weighted_confusion(items, labels, meta, axis)
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
            add(f"  n/a -- {th.get('note')}")
        else:
            add(f"  fit_score >= {th['threshold']:.2f}   (n={th['n']})")
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
        payload = {
            "self_consistency": self_consistency(repeat_pairs(items, labels)),
            "filter_agreement": {a: filter_agreement(items, labels, a) for a in AXES},
            "reweighted": {
                a: {
                    "confusion": weighted_confusion(items, labels, meta, a),
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
