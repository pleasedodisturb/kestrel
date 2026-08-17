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
    """Replay the JSONL log. Last write wins; retractions remove; torn tail dropped.

    Reads the file exactly ONCE. An earlier version called ``read_text()`` again
    inside the loop to find the last line number, which made a file with many
    malformed lines quadratic.

    "Torn" means an interrupted write, and the only honest signal for that is a
    final line with **no trailing newline**. A malformed line that IS newline-
    terminated was fully written and is therefore corruption, not a torn tail --
    ``splitlines()`` discards exactly the information needed to tell those apart,
    which is why the raw text is inspected here.
    """
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8")
    if not raw:
        return {}
    ends_with_newline = raw.endswith("\n")
    lines = raw.split("\n")
    if ends_with_newline:
        lines = lines[:-1]

    out: dict[int, dict] = {}
    for line_no, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            rec = json.loads(stripped)
        except json.JSONDecodeError:
            if line_no == len(lines) and not ends_with_newline:
                print(
                    f"  discarded torn final line {line_no} (interrupted write)",
                    file=sys.stderr,
                )
                continue
            raise SystemExit(
                f"{path}:{line_no} is corrupt and was fully written "
                f"(newline-terminated), so it is not a torn tail; refusing to guess"
            ) from None
        if rec.get("retracted"):
            # A durable tombstone from `b` (go back). Without this, a retraction
            # lived only in memory and the label came back on the next run.
            out.pop(rec["index"], None)
        else:
            out[rec["index"]] = rec
    return out


def append_label(path: Path, record: dict) -> None:
    """Append one decision durably. fsync so a kill cannot lose an acked label."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def append_retraction(path: Path, index: int) -> None:
    """Append a durable tombstone for a label the user went back on.

    The log is append-only, so a retraction is a record rather than a deletion.
    ``load_labels`` replays it as a removal. Popping the in-memory dict alone
    left the original line on disk, and it was resurrected on the next run.
    """
    append_label(path, {
        "index": index,
        "retracted": True,
        "retracted_at": datetime.now(UTC).isoformat(),
    })


def label_matches_item(item: dict, rec: dict) -> bool:
    """Is this stored label still bound to THIS posting's text?

    The whole point of storing ``input_hash`` is that an edited posting must
    invalidate its label rather than silently re-attach it to different words.
    Storing the hash without ever comparing it made the binding decorative:
    labels join to items by ``index``, and indices are reused whenever a label
    set is rebuilt.
    """
    return rec.get("input_hash") == input_hash(item)


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
        existing = labels.get(item["index"])
        if existing is not None:
            if label_matches_item(item, existing):
                pos += 1
                continue
            # Same index, different posting text: the label set was rebuilt or
            # edited under this log. Treat as unlabelled rather than crediting
            # the old answer to new words.
            print(
                f"  index {item['index']}: posting text changed since it was "
                f"labelled; re-asking",
                file=sys.stderr,
            )
            labels.pop(item["index"], None)

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
            back_index = items[pos]["index"]
            if labels.pop(back_index, None) is not None:
                append_retraction(labels_path, back_index)
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
