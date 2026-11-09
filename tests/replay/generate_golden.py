#!/usr/bin/env python3
"""One-shot developer script: freeze, check and register the MAP-02 goldens.

NOT run by CI. CI consumes only the committed goldens and MANIFEST.json and
replays them in ``tests/replay/test_golden.py``.

Modes::

    python tests/replay/generate_golden.py --class dedup_verdicts   # regenerate
    python tests/replay/generate_golden.py --all                    # every class with a harness
    python tests/replay/generate_golden.py --check --all            # recompute, write nothing
    python tests/replay/generate_golden.py --register-awaiting      # add the six awaiting entries
    python tests/replay/generate_golden.py --register-private gate_verdicts --file PATH \
        --private-commit SHA [--gates fact,voice] [--dry-run]
    python tests/replay/generate_golden.py --register-private private_scoring --file PATH \
        --private-commit SHA --producer-row P-NN [--ledger PATH] [--dry-run]

Family B classes (the five private_* classes) have no harness: they are never
recomputed, only validated by ``private_golden_problems`` and their sha256.

``--register-private`` (with or without ``--dry-run``) and ``--check`` read files
that came from the private pipeline. What they print about such a file names a
line number and a rule and never repeats a value read from it: the findings are
those of ``private_golden_problems`` and ``gate_verdict_problems``, and a ledger
that cannot be parsed is reported by its error class only.

Contract (modelled on ``tests/eval/geo/fixtures/generate_reference.py``): on any
PII hit, schema error or duplicate the script writes NOTHING and exits non-zero.
Regeneration keeps each case's ``id`` and ``input`` and recomputes only the
``output`` by calling the producing ``tools/`` function inside ``pinned()``;
nothing here makes a network call, reads a database or calls an LLM.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.replay import _support as S  # noqa: E402

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_PRODUCER_ROW = re.compile(r"^P-\d{2,3}$")
GATE_CLASS = "gate_verdicts"
GATE_DRAFTS = "gate_drafts.jsonl"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _read_cases(path: Path) -> list[dict[str, Any]]:
    """Read a golden or a hand-authored ``{id, input}`` file and validate its shape."""
    rows = S.load_jsonl(path)
    seen_ids: set[str] = set()
    seen_inputs: set[str] = set()
    for number, row in enumerate(rows, start=1):
        if not isinstance(row, dict) or "id" not in row or "input" not in row:
            raise ValueError(f"{path.name} line {number}: needs id and input")
        if not set(row) <= {"id", "input", "output"}:
            raise ValueError(f"{path.name} line {number}: unknown key besides id, input, output")
        if row["id"] in seen_ids:
            raise ValueError(f"{path.name} line {number}: duplicate id {row['id']!r}")
        seen_ids.add(row["id"])
        key = _canonical(row["input"])
        if key in seen_inputs:
            raise ValueError(f"{path.name} line {number}: duplicate input (id {row['id']!r})")
        seen_inputs.add(key)
    return rows


def _compute(cls: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Recompute every output through the harness, inside ``pinned()``."""
    import copy

    harness = S.HARNESS[cls]
    out: list[dict[str, Any]] = []
    with S.pinned():
        for row in rows:
            out.append(
                {
                    "id": row["id"],
                    "input": row["input"],
                    "output": harness(copy.deepcopy(row["input"])),
                }
            )
    return out


def regenerate(classes: list[str], golden_dir: Path = S.GOLDEN) -> int:
    """Recompute the goldens of *classes* and update the manifest, or write nothing."""
    manifest_path = golden_dir / "MANIFEST.json"
    manifest = (
        S.load_manifest(manifest_path) if manifest_path.is_file() else {"schema": 1, "classes": {}}
    )
    pending: dict[str, tuple[str, list[dict[str, Any]]]] = {}
    for cls in classes:
        path = golden_dir / f"{cls}.jsonl"
        try:
            rows = _read_cases(path)
        except (OSError, ValueError) as exc:
            print(f"FAIL {cls}: {exc}", file=sys.stderr)
            return 1
        if not rows:
            print(f"FAIL {cls}: no cases", file=sys.stderr)
            return 1
        computed = _compute(cls, rows)
        text = S.dump_jsonl(computed)
        labels = sorted(S.pii_hits(text))
        if labels:
            print(f"FAIL {cls}: PII scan hit {labels}; writing nothing", file=sys.stderr)
            return 1
        pending[cls] = (text, computed)

    for cls, (text, _computed) in pending.items():
        manifest["classes"][cls] = {
            "golden": f"{cls}.jsonl",
            "sha256": S.sha256_bytes(text.encode("utf-8")),
            "status": S.STATUS_FROZEN,
            "producers": {p: S.git_blob(p) for p in S.CLASS_PRODUCERS[cls]},
            "producer_commit": S.git_head(),
            "python": S.python_version(),
            "generated": S.current_month(),
            "inputs": "synthetic",
            "pins": list(S.CLASS_PINS[cls]),
            **_keep_input_files(manifest["classes"].get(cls)),
        }
    for cls, (text, computed) in pending.items():
        (golden_dir / f"{cls}.jsonl").write_text(text, encoding="utf-8", newline="")
        print(f"wrote {cls}: {len(computed)} cases")
    manifest_path.write_text(S.dump_manifest(manifest), encoding="utf-8", newline="")
    return 0


def _keep_input_files(previous: Any) -> dict[str, Any]:
    if isinstance(previous, dict) and isinstance(previous.get("input_files"), dict):
        return {"input_files": previous["input_files"]}
    return {}


def check(golden_dir: Path = S.GOLDEN) -> int:
    """Recompute every class with a harness and compare; write nothing."""
    drift = 0
    manifest_path = golden_dir / "MANIFEST.json"
    if not manifest_path.is_file():
        print("PROBLEM MANIFEST.json is missing")
        return 1
    manifest = S.load_manifest(manifest_path)
    for cls in sorted(S.HARNESS):
        entry = manifest["classes"].get(cls)
        if entry is None or entry.get("status") != S.STATUS_FROZEN:
            print(f"DRIFT {cls} <not frozen in the manifest>")
            drift += 1
            continue
        path = golden_dir / entry["golden"]
        try:
            committed = path.read_bytes()
            rows = _read_cases(path)
        except (OSError, ValueError) as exc:
            print(f"DRIFT {cls} <unreadable: {exc}>")
            drift += 1
            continue
        computed = _compute(cls, rows)
        stored = {row["id"]: row.get("output") for row in rows}
        drifted = [row["id"] for row in computed if stored[row["id"]] != row["output"]]
        for row_id in drifted:
            print(f"DRIFT {cls} {row_id}")
        drift += len(drifted)
        if not drifted and S.dump_jsonl(computed).encode("utf-8") != committed:
            print(f"DRIFT {cls} <file bytes are not the canonical encoding>")
            drift += 1
    problems = S.manifest_problems(golden_dir)
    for problem in problems:
        print(f"PROBLEM {problem}")
    gate = manifest["classes"].get(GATE_CLASS)
    if isinstance(gate, dict) and gate.get("status") == S.STATUS_FROZEN:
        gate_problems = S.gate_verdict_problems(
            golden_dir / gate["golden"],
            golden_dir / GATE_DRAFTS,
            gates=gate.get("gates", "fact,voice"),
        )
        for problem in gate_problems:
            print(f"PROBLEM {GATE_CLASS}: {problem}")
        problems = problems + gate_problems
    return 1 if drift or problems else 0


def register_private(
    cls: str,
    file: Path,
    private_commit: str,
    *,
    golden_dir: Path = S.GOLDEN,
    gates: str | None = None,
    producer_row: str | None = None,
    ledger: Path | None = None,
    dry_run: bool = False,
) -> int:
    """Validate a private-pipeline file and, unless *dry_run*, freeze its class.

    ``gate_verdicts`` takes ``gates`` and never ``producer_row`` or ``ledger``;
    the five Family B classes take ``producer_row`` (required) and ``ledger`` and
    never ``gates``. Exit codes: 2 for a usage error, 1 for a failed validation.
    """
    manifest_path = golden_dir / "MANIFEST.json"
    manifest = S.load_manifest(manifest_path)
    entry = manifest["classes"].get(cls)
    family_b = cls in S.FAMILY_B_CLASSES
    if (cls != GATE_CLASS and not family_b) or entry is None:
        print(f"FAIL {cls}: no private registration path for this class", file=sys.stderr)
        return 2
    if family_b:
        if gates is not None:
            print(f"FAIL {cls}: --gates applies to {GATE_CLASS} only", file=sys.stderr)
            return 2
        if not (producer_row and _PRODUCER_ROW.fullmatch(producer_row)):
            print(f"FAIL {cls}: --producer-row P-NN is required", file=sys.stderr)
            return 2
    elif producer_row is not None or ledger is not None:
        print(
            f"FAIL {cls}: --producer-row and --ledger apply to Family B classes only",
            file=sys.stderr,
        )
        return 2
    if not _SHA40.fullmatch(private_commit):
        print("FAIL --private-commit must be 40 lowercase hex", file=sys.stderr)
        return 2
    if entry.get("status") != S.STATUS_AWAITING:
        print(
            f"FAIL {cls}: status is {entry.get('status')!r}, not awaiting_private_run",
            file=sys.stderr,
        )
        return 1

    gate_set = gates or "fact,voice"
    if family_b:
        assert producer_row is not None
        ledger_path = ledger if ledger is not None else S.PRIVATE_LEDGER_PATH
        if ledger_path.is_file():
            try:
                known_rows = S.ledger_row_ids(ledger_path)
            except S.LedgerUnreadable as exc:
                # Class name only: the ledger is private until it has crossed, and
                # a YAML parser error quotes the offending line.
                print(f"FAIL {cls}: cannot read {ledger_path.name}: {exc}", file=sys.stderr)
                return 1
            if producer_row not in known_rows:
                print(
                    f"FAIL {cls}: producer_row {producer_row} is not in {ledger_path.name}",
                    file=sys.stderr,
                )
                return 1
        else:
            print(f"PENDING producer_row {producer_row}: ledger not present")
        problems = S.private_golden_problems(file, cls)
    else:
        problems = S.gate_verdict_problems(file, golden_dir / GATE_DRAFTS, gates=gate_set)
    if problems:
        for problem in problems:
            print(f"FAIL {cls}: {problem}", file=sys.stderr)
        return 1
    if dry_run:
        print(f"OK {cls}: validated {file.name} (dry run, nothing written)")
        return 0
    target = golden_dir / f"{cls}.jsonl"
    if not file.exists() or file.resolve() != target.resolve():
        print(
            f"FAIL {cls}: the file must already sit at {target} (use --dry-run elsewhere)",
            file=sys.stderr,
        )
        return 2
    update: dict[str, Any] = {
        "golden": target.name,
        "sha256": S.sha256_file(target),
        "status": S.STATUS_FROZEN,
        "producers": {S.PRIVATE_KEY: private_commit},
        "producer_commit": private_commit,
        "generated": S.current_month(),
    }
    if family_b:
        update |= {
            "producer_row": producer_row,
            "inputs": "scrubbed",
            "profile_scope": "maintainer",
        }
    else:
        update["gates"] = gate_set
    entry.update(update)
    manifest_path.write_text(S.dump_manifest(manifest), encoding="utf-8", newline="")
    print(f"froze {cls}" + ("" if family_b else f" (gates={gate_set})"))
    return 0


def register_awaiting(golden_dir: Path = S.GOLDEN) -> int:
    """Add the awaiting entries (gate_verdicts and the Family B classes) that are missing.

    Existing entries are left alone, so a frozen class is never reset. The gate
    entry records the sha256 of its two Kestrel-authored input files.
    """
    manifest_path = golden_dir / "MANIFEST.json"
    manifest = S.load_manifest(manifest_path)
    added = []
    for cls in (GATE_CLASS, *S.FAMILY_B_CLASSES):
        if cls not in manifest["classes"]:
            manifest["classes"][cls] = S.awaiting_entry(cls, golden_dir)
            added.append(cls)
    manifest_path.write_text(S.dump_manifest(manifest), encoding="utf-8", newline="")
    print(f"registered awaiting: {added or 'nothing to add'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--class", dest="classes", action="append", default=[], metavar="NAME")
    parser.add_argument("--all", action="store_true", help="every class that has a harness")
    parser.add_argument("--check", action="store_true", help="recompute and compare; write nothing")
    parser.add_argument("--register-awaiting", action="store_true")
    parser.add_argument("--register-private", metavar="CLASS")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--private-commit")
    parser.add_argument("--gates", help="gate_verdicts only: fact,voice | fact | voice")
    parser.add_argument("--producer-row", help="Family B only: the P-NN row of the private ledger")
    parser.add_argument("--ledger", type=Path, help="Family B only: ledger the row must appear in")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--golden-dir", type=Path, default=S.GOLDEN, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    # One operation per run, decided before anything runs: --check promises to write
    # nothing, so it must never share a command line with a registration, and a
    # registration never rides along with a regeneration. --check may still name
    # classes (--check --all is the documented spelling).
    operations = [
        flag
        for flag, chosen in (
            ("--check", args.check),
            ("--register-awaiting", args.register_awaiting),
            ("--register-private", args.register_private is not None),
        )
        if chosen
    ]
    regenerating = bool(args.classes or args.all) and not args.check
    if len(operations) > 1 or (regenerating and operations):
        parser.error(
            "--check, --register-awaiting, --register-private and regeneration "
            "(--class, --all) are separate operations; run one at a time"
        )
    # Same rule for options: the ones below belong to --register-private, and are refused
    # here, before any operation runs. Checked after the dispatch, a --dry-run given to
    # --register-awaiting was ignored and the MANIFEST was written anyway.
    private_only = (
        args.gates
        or args.dry_run
        or args.file
        or args.private_commit
        or args.producer_row
        or args.ledger
    )
    if private_only and args.register_private is None:
        parser.error(
            "--gates, --dry-run, --file, --private-commit, --producer-row and --ledger "
            "belong to --register-private"
        )

    if args.register_awaiting:
        return register_awaiting(args.golden_dir)
    if args.register_private:
        if not args.file or not args.private_commit:
            parser.error("--register-private needs --file and --private-commit")
        return register_private(
            args.register_private,
            args.file,
            args.private_commit,
            golden_dir=args.golden_dir,
            gates=args.gates,
            producer_row=args.producer_row,
            ledger=args.ledger,
            dry_run=args.dry_run,
        )
    unknown = [c for c in args.classes if c not in S.HARNESS]
    if unknown:
        parser.error(f"no harness for class(es) {unknown}; known: {sorted(S.HARNESS)}")
    classes = sorted(S.HARNESS) if args.all else args.classes
    if args.check:
        return check(args.golden_dir)
    if not classes:
        parser.error("name a class with --class, or use --all, --check or --register-private")
    return regenerate(classes, args.golden_dir)


if __name__ == "__main__":
    raise SystemExit(main())
