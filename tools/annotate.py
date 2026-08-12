#!/usr/bin/env python3
"""Blind two-axis annotation for a label set built by build_label_set.py.

Two axes, both binary, asked separately
--------------------------------------
    Could you win this cold?   (eligibility + realistic shot, no referral)
    Do you want it?            (desire)

They are asked separately because collapsing them destroys the one cell that
matters most:

    win + want      -> apply now
    want, NO win    -> the referral lane
    win, NO want    -> fallback
    neither         -> drop

A single GO/SKIP verdict cannot represent "I want this and could not win it
cold". A filter calibrated on that collapsed verdict learns to bury exactly the
roles a warm introduction would unlock. Splitting the axes is the whole point;
do not add a combined shortcut key.

Blindness
---------
The annotator sees title, company, location and description. Nothing else.
Scores, geo classes, filter verdicts and stratum membership live under
``_hidden`` in the label set and are never rendered: ``render_item`` takes the
visible projection only, and a test fails if a filter-derived field can reach
it. A label produced while looking at the model's answer measures agreement
rather than truth, and it corrupts the metrics in the flattering direction.

Resumability
------------
Labels append to a JSONL file, one line per decision, flushed and fsynced.
An abrupt kill loses at most the line being written, and a truncated final line
is discarded on load rather than poisoning the file. Re-labelling an item simply
appends again: replay is last-wins, which is what makes ``b`` (go back) safe.

Each label carries ``input_hash`` over title|company|description, reusing
``tests/eval/label_store.input_hash``. If a posting's text changes, its label is
invalidated rather than silently re-attached to different words.

Usage
-----
    python tools/annotate.py                       # resumes automatically
    python tools/annotate.py --label-set data/label_set.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "src"))

from tests.eval.label_store import input_hash  # noqa: E402

DEFAULT_LABEL_SET = _REPO / "data" / "label_set.json"
DEFAULT_LABELS = _REPO / "data" / "labels.jsonl"

# The only keys an annotator may see. build_label_set.py puts everything
# filter-derived under _hidden; this is the second, independent gate.
VISIBLE_FIELDS = ("index", "title", "company", "location", "description")

QUIT = "__quit__"
BACK = "__back__"
SKIP = "__skip__"


def visible_projection(item: dict) -> dict:
    """Strip an item down to what a human reads off the posting.

    Allow-list, not deny-list. A new field added upstream is invisible here
    until someone adds it deliberately, which is the safe direction: the
    failure mode of a deny-list is silent leakage.
    """
    return {k: item[k] for k in VISIBLE_FIELDS if k in item}


def render_item(item: dict, position: int, total: int) -> str:
    """Format one posting for display. Pure; takes the visible projection only."""
    v = visible_projection(item)
    head = f"[ {position}/{total} ]  {v.get('title', '')}"
    sub = f"            {v.get('company', '')}  ·  {v.get('location', '')}"
    body = (v.get("description") or "").strip()
    return f"{head}\n{sub}\n\n{body}\n"


def load_label_set(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(
            f"no label set at {path}\n"
            f"build one first: python tools/build_label_set.py --profile <name>"
        )
    data = json.loads(path.read_text())
    if "items" not in data or "_meta" not in data:
        raise SystemExit(f"{path} is not a label set (missing items/_meta)")
    return data


def load_labels(path: Path) -> dict[int, dict]:
    """Replay the JSONL log. Last write wins; a torn final line is dropped."""
    if not path.exists():
        return {}
    out: dict[int, dict] = {}
    for line_no, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            # Only the final line can be torn by a kill mid-write. A broken
            # line anywhere else means real corruption, so say so.
            if line_no != len(path.read_text().splitlines()):
                raise SystemExit(
                    f"{path}:{line_no} is corrupt and is not the last line; refusing to guess"
                ) from None
            print(f"  discarded torn final line {line_no} (interrupted write)", file=sys.stderr)
            continue
        out[rec["index"]] = rec
    return out


def append_label(path: Path, record: dict) -> None:
    """Append one decision durably. fsync so a kill cannot lose an acked label."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def make_record(item: dict, *, can_win: bool, wants: bool) -> dict:
    """Build the stored label. Carries the two axes separately, never merged."""
    return {
        "index": item["index"],
        "input_hash": input_hash(item),
        "can_win_cold": can_win,
        "wants": wants,
        "labeled_at": datetime.now(UTC).isoformat(),
    }


def cell(record: dict) -> str:
    """Name the four-cell outcome. Derived for reporting; never stored as the label."""
    if record["can_win_cold"] and record["wants"]:
        return "apply_now"
    if record["wants"]:
        return "referral_lane"
    if record["can_win_cold"]:
        return "fallback"
    return "drop"


def _ask(prompt: str, valid: dict[str, object], reader) -> object:
    while True:
        raw = (reader(prompt) or "").strip().lower()
        if raw in valid:
            return valid[raw]
        print(f"  ? expected one of: {', '.join(sorted(valid))}")


def annotate(
    items: list[dict],
    labels: dict[int, dict],
    labels_path: Path,
    reader=input,
) -> int:
    """Run the labelling loop. Returns the number of new labels written."""
    total = len(items)
    written = 0
    pos = 0

    while pos < len(items):
        item = items[pos]
        if item["index"] in labels:
            pos += 1
            continue

        print("\n" + "=" * 72)
        print(render_item(item, pos + 1, total))

        win = _ask(
            "  Could you win this cold?  [y/n]  (s skip, b back, q quit) > ",
            {"y": True, "n": False, "s": SKIP, "b": BACK, "q": QUIT},
            reader,
        )
        if win is QUIT:
            break
        if win is BACK:
            pos = max(0, pos - 1)
            labels.pop(items[pos]["index"], None)
            continue
        if win is SKIP:
            pos += 1
            continue

        want = _ask(
            "  Do you want it?           [y/n]  (b back, q quit) > ",
            {"y": True, "n": False, "b": BACK, "q": QUIT},
            reader,
        )
        if want is QUIT:
            break
        if want is BACK:
            continue

        rec = make_record(item, can_win=bool(win), wants=bool(want))
        append_label(labels_path, rec)
        labels[rec["index"]] = rec
        written += 1
        print(f"  -> {cell(rec)}")
        pos += 1

    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--label-set", type=Path, default=DEFAULT_LABEL_SET)
    ap.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    args = ap.parse_args(argv)

    data = load_label_set(args.label_set)
    items = data["items"]
    labels = load_labels(args.labels)

    done = sum(1 for i in items if i["index"] in labels)
    print(f"label set: {args.label_set}  ({len(items)} items, {done} already labelled)")
    if done:
        print(f"resuming at item {done + 1}")

    written = annotate(items, labels, args.labels)

    counts: dict[str, int] = {}
    for rec in labels.values():
        counts[cell(rec)] = counts.get(cell(rec), 0) + 1
    print(f"\nwrote {written} new labels to {args.labels}")
    print(f"  {len(labels)}/{len(items)} labelled")
    for name in ("apply_now", "referral_lane", "fallback", "drop"):
        print(f"  {name:14} {counts.get(name, 0)}")
    if len(labels) < len(items):
        print("\n  resume any time; the log is append-only and replays last-wins")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
