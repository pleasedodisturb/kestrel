#!/usr/bin/env python3
"""Build a stratified, blind label set from your own discovered jobs.

Why this exists
---------------
A filter's precision and recall are only meaningful against ground truth, and
ground truth is *yours*. Someone else's labels measure agreement with someone
else's taste on someone else's search. So Kestrel ships the *method* for
building a label set, not a label set.

What this produces
------------------
``label_set.json``: a sample of postings drawn from your own ``discovered_jobs``,
stratified roughly 50/50 into what the geo filter would KEEP and what it would
DROP, with three properties that cannot be added afterwards:

1. **Per-stratum sampling probabilities**, recorded in ``_meta``. The sample is
   deliberately balanced; the population is not. Without the draw probability
   for each stratum, precision and recall computed on this sample describe the
   *sample*, not the population, and there is no way to reweight them back. This
   number is unrecoverable once the draw is over, which is why it is written
   here and not left to the scorer.

2. **Repeat items**, tagged at draw time. The same posting appears twice, drawn
   from the decision boundary where judgement is hardest. Your agreement with
   *yourself* across those pairs is the ceiling on how well any judge can score
   against you: a filter cannot be more consistent with you than you are.
   Whether an item is a repeat is a property of the draw, so it cannot be
   reconstructed later either.

3. **Every filter-derived field under ``_hidden``**. Scores, geo classes and
   filter verdicts anchor a human rater. A label produced while looking at the
   model's answer measures agreement, not truth, and the resulting metrics look
   *better* the more thoroughly they are corrupted. ``tools/annotate.py``
   refuses to render anything under ``_hidden``; there is a test that fails if
   it can.

The label schema itself (what verdicts you record) is deliberately NOT decided
here. This step chooses *which* postings you look at. See ``tools/annotate.py``.

Usage
-----
    python tools/build_label_set.py --profile frankfurt
    python tools/build_label_set.py --profile us_remote --n-per-stratum 150

``--profile`` is required and has no default, on purpose: a geo profile encodes
one person's location, work authorisation and willingness to move. Defaulting it
would silently label your postings against a stranger's circumstances.
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
sys.path.insert(0, str(_REPO / "src"))

from career_os.services.geo.classifier import (  # noqa: E402
    ELIGIBLE_CLASSES,
    MAYBE_CLASSES,
    geo_eligibility,
)
from career_os.services.geo.profile import GeoProfile  # noqa: E402

DEFAULT_DB = _REPO / "data" / "career_os.db"
DEFAULT_OUT = _REPO / "data" / "label_set.json"

# A posting the annotator cannot read is not a usable item: they would be
# guessing from the title, which is a different task than the one being measured.
DEFAULT_MIN_DESC = 500

# Classes that sit on the decision boundary. Repeats are drawn from here first
# because self-consistency measured on obvious items overstates the ceiling.
BOUNDARY_CLASSES = frozenset(MAYBE_CLASSES)

KEEP_CLASSES = frozenset(ELIGIBLE_CLASSES) | frozenset(MAYBE_CLASSES)


def load_profile(name: str) -> GeoProfile:
    """Resolve a named geo profile, or fail loudly.

    Never falls back to a default. A wrong profile produces a label set that
    looks fine and measures the wrong person.
    """
    from career_os.services.geo import presets

    key = f"{name.upper()}_PROFILE"
    profile = getattr(presets, key, None)
    if profile is None:
        available = sorted(
            n[: -len("_PROFILE")].lower()
            for n in dir(presets)
            if n.endswith("_PROFILE")
        )
        raise SystemExit(
            f"unknown profile {name!r}. available: {', '.join(available) or '(none)'}\n"
            f"profiles are built with career_os.services.geo.profile.build_profile()"
        )
    return profile


def load_population(
    db_path: Path, profile: GeoProfile, min_desc: int
) -> tuple[list[dict], list[dict]]:
    """Split every readable discovered job into the KEEP and DROP strata.

    Returns (keep, drop). Each record carries its geo class so the sampler does
    not have to classify twice.
    """
    if not db_path.exists():
        raise SystemExit(
            f"no database at {db_path}\n"
            f"run a discovery scan first, or pass --db"
        )

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, title, company, location, url, description, remote, fit_score
            FROM discovered_jobs
            WHERE description IS NOT NULL
            """
        ).fetchall()
    except sqlite3.OperationalError as exc:
        raise SystemExit(f"cannot read discovered_jobs from {db_path}: {exc}") from exc
    finally:
        conn.close()

    keep: list[dict] = []
    drop: list[dict] = []
    skipped_short = 0

    for row in rows:
        desc = row["description"] or ""
        if len(desc) < min_desc:
            skipped_short += 1
            continue

        geo_class = geo_eligibility(
            row["location"],
            offices=None,
            remote=bool(row["remote"]),
            title=row["title"] or "",
            description=desc,
            profile=profile,
        )
        rec = {
            "job_id": row["id"],
            "title": row["title"],
            "company": row["company"],
            "location": row["location"],
            "url": row["url"],
            "description": desc,
            "remote": bool(row["remote"]),
            "geo_class": geo_class,
            "fit_score": row["fit_score"],
        }
        (keep if geo_class in KEEP_CLASSES else drop).append(rec)

    if skipped_short:
        print(
            f"  skipped {skipped_short} postings shorter than {min_desc} chars "
            f"(unreadable is not labellable)",
            file=sys.stderr,
        )
    return keep, drop


def pick_repeats(sample: list[tuple[dict, str]], n: int, rng: random.Random) -> list[dict]:
    """Choose items to present a second time, preferring the decision boundary.

    Drawn from the already-drawn sample so a first-time user can measure their
    own consistency in a single session, with no prior labelling round.
    """
    if n <= 0:
        return []
    boundary = [rec for rec, _ in sample if rec["geo_class"] in BOUNDARY_CLASSES]
    rest = [rec for rec, _ in sample if rec["geo_class"] not in BOUNDARY_CLASSES]
    rng.shuffle(boundary)
    rng.shuffle(rest)
    chosen = (boundary + rest)[:n]
    if len(chosen) < n:
        print(
            f"  only {len(chosen)} repeat candidates available (wanted {n}); "
            f"self-consistency will be measured on a smaller base",
            file=sys.stderr,
        )
    return chosen


def build_item(rec: dict, index: int, stratum: str, *, repeat_of: int | None) -> dict:
    """Assemble one annotator-facing item.

    Everything the filter produced lives under ``_hidden`` and must never be
    rendered. Everything above it is what a human would see on the posting.
    """
    return {
        "index": index,
        "title": rec["title"],
        "company": rec["company"],
        "location": rec["location"],
        "description": rec["description"],
        "_hidden": {
            "job_id": rec["job_id"],
            "url": rec["url"],
            "stratum": stratum,
            "geo_class": rec["geo_class"],
            "fit_score": rec["fit_score"],
            "remote": rec["remote"],
            "repeat": repeat_of is not None,
            "repeat_of": repeat_of,
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--profile", required=True, help="geo profile name (no default, by design)")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--n-per-stratum", type=int, default=100)
    ap.add_argument("--n-repeats", type=int, default=15)
    ap.add_argument("--min-desc", type=int, default=DEFAULT_MIN_DESC)
    ap.add_argument("--seed", type=int, default=1507, help="deterministic shuffle seed")
    args = ap.parse_args(argv)

    profile = load_profile(args.profile)
    rng = random.Random(args.seed)

    keep_pop, drop_pop = load_population(args.db, profile, args.min_desc)
    if not keep_pop and not drop_pop:
        raise SystemExit("no labellable postings found")

    n_keep = min(args.n_per_stratum, len(keep_pop))
    n_drop = min(args.n_per_stratum, len(drop_pop))
    if n_keep < args.n_per_stratum or n_drop < args.n_per_stratum:
        print(
            f"  stratum smaller than requested: KEEP {n_keep}/{args.n_per_stratum}, "
            f"DROP {n_drop}/{args.n_per_stratum}",
            file=sys.stderr,
        )

    sample: list[tuple[dict, str]] = [
        (rec, "KEEP") for rec in rng.sample(keep_pop, n_keep)
    ] + [(rec, "DROP") for rec in rng.sample(drop_pop, n_drop)]

    repeats = pick_repeats(sample, args.n_repeats, rng)

    items: list[dict] = [
        build_item(rec, 0, stratum, repeat_of=None) for rec, stratum in sample
    ]
    items += [
        build_item(rec, 0, "REPEAT", repeat_of=rec["job_id"]) for rec in repeats
    ]

    # Shuffle before numbering so repeats are not adjacent to their originals
    # and the strata are interleaved. Order must not leak the stratum.
    rng.shuffle(items)
    for i, item in enumerate(items, 1):
        item["index"] = i

    payload = {
        "_meta": {
            "created_at": datetime.now(UTC).isoformat(),
            "profile": profile.name,
            "seed": args.seed,
            "min_desc": args.min_desc,
            "n_items": len(items),
            "n_repeats": len(repeats),
            # The load-bearing numbers. Without these, metrics computed on this
            # sample cannot be reweighted to the population base rate.
            "strata": {
                "KEEP": {
                    "population": len(keep_pop),
                    "sampled": n_keep,
                    "p_draw": (n_keep / len(keep_pop)) if keep_pop else 0.0,
                },
                "DROP": {
                    "population": len(drop_pop),
                    "sampled": n_drop,
                    "p_draw": (n_drop / len(drop_pop)) if drop_pop else 0.0,
                },
            },
            "population_base_rate_keep": (
                len(keep_pop) / (len(keep_pop) + len(drop_pop))
                if (keep_pop or drop_pop)
                else 0.0
            ),
        },
        "items": items,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    meta = payload["_meta"]
    print(f"wrote {args.out}")
    print(f"  {meta['n_items']} items ({n_keep} KEEP + {n_drop} DROP + {len(repeats)} repeats)")
    print(f"  profile: {meta['profile']}  seed: {meta['seed']}")
    print(
        f"  p_draw  KEEP {meta['strata']['KEEP']['p_draw']:.4f}"
        f"  DROP {meta['strata']['DROP']['p_draw']:.4f}"
    )
    print(f"  population base rate (KEEP): {meta['population_base_rate_keep']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
