"""Replay and integrity tests for the MAP-02 goldens (Phase 11, plan 01).

Every golden class that has a harness entry is replayed over its stored inputs
and must reproduce its stored output exactly; the manifest checker proves the
bytes and the producer files are the ones that were recorded. Each guard is
paired with a test that makes it fail on purpose (guard-the-guard).
"""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from tests.eval.geo.replay import scrub_patterns
from tests.replay import generate_golden
from tests.replay._support import (
    GOLDEN,
    HARNESS,
    REQUIRED_PATTERN_LABELS,
    dump_jsonl,
    gate_verdict_problems,
    git_blob,
    load_jsonl,
    load_manifest,
    manifest_problems,
    pii_hits,
    pinned,
    sha256_file,
)

_EMAIL_PARTS = ("some.one", "@", "example", ".org")


def _frozen_replay_cases() -> list[Any]:
    """One pytest param per (class, case) of every frozen class that has a harness."""
    manifest = load_manifest()
    params = []
    for cls, entry in sorted(manifest["classes"].items()):
        if cls in HARNESS and entry.get("status") == "frozen":
            for row in load_jsonl(GOLDEN / entry["golden"]):
                params.append(pytest.param(cls, row, id=f"{cls}::{row['id']}"))
    return params


def _harness_classes() -> list[str]:
    return sorted(HARNESS)


def _copy_golden(tmp_path: Path) -> Path:
    target = tmp_path / "golden"
    shutil.copytree(GOLDEN, target)
    return target


def _contains(value: Any, predicate: Any) -> bool:
    """True when *predicate* holds for the value or anything nested inside it."""
    if predicate(value):
        return True
    if isinstance(value, dict):
        return any(_contains(v, predicate) for v in value.values())
    if isinstance(value, list):
        return any(_contains(v, predicate) for v in value)
    return False


# ---------------------------------------------------------------------------
# Manifest integrity
# ---------------------------------------------------------------------------


def test_manifest_has_no_problems():
    manifest = load_manifest()
    assert manifest_problems(GOLDEN) == []
    assert len(manifest["classes"]) >= 1


def test_manifest_checker_detects_a_flipped_byte(tmp_path):
    copy_dir = _copy_golden(tmp_path)
    entry = load_manifest(copy_dir / "MANIFEST.json")["classes"]["dedup_verdicts"]
    original_sha = sha256_file(GOLDEN / entry["golden"])
    target = copy_dir / entry["golden"]
    data = bytearray(target.read_bytes())
    data[0] ^= 0x01
    target.write_bytes(bytes(data))

    problems = manifest_problems(copy_dir)

    assert any("sha256 mismatch" in p and entry["golden"] in p for p in problems)
    assert sha256_file(GOLDEN / entry["golden"]) == original_sha
    assert manifest_problems(GOLDEN) == []


def test_manifest_checker_detects_an_unlisted_file(tmp_path):
    copy_dir = _copy_golden(tmp_path)
    (copy_dir / "stray.jsonl").write_text("{}\n", encoding="utf-8")

    problems = manifest_problems(copy_dir)

    assert any("unlisted file stray.jsonl" in p for p in problems)
    assert not (GOLDEN / "stray.jsonl").exists()


def test_manifest_checker_detects_a_changed_producer_blob(tmp_path):
    copy_dir = _copy_golden(tmp_path)
    manifest_path = copy_dir / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    producers = manifest["classes"]["dedup_verdicts"]["producers"]
    recorded = producers["tools/normalize.py"]
    producers["tools/normalize.py"] = "0" * 40
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    problems = manifest_problems(copy_dir)

    assert any("producer changed: tools/normalize.py" in p for p in problems)
    assert git_blob("tools/normalize.py") == recorded


def test_golden_files_carry_no_pii_or_tracking_urls():
    files = sorted(p for p in GOLDEN.rglob("*") if p.is_file())
    assert any(p.suffix == ".jsonl" for p in files)
    assert set(REQUIRED_PATTERN_LABELS) <= set(scrub_patterns())
    for path in files:
        hits = pii_hits(path.read_text(encoding="utf-8"))
        assert not hits, f"{path.name} matches scrub patterns: {sorted(hits)}"


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("cls", "case"), _frozen_replay_cases())
def test_replay_reproduces_golden(cls, case):
    assert "output" in case
    with pinned():
        actual = HARNESS[cls](copy.deepcopy(case["input"]))
    assert actual == case["output"]


def test_every_harness_class_is_frozen_and_replayed():
    manifest = load_manifest()
    replayed = {param.values[0] for param in _frozen_replay_cases()}
    assert set(HARNESS) == replayed
    for cls in HARNESS:
        assert manifest["classes"][cls]["status"] == "frozen"


@pytest.mark.parametrize("cls", _harness_classes())
def test_golden_lines_are_canonical_and_complete(cls):
    path = GOLDEN / load_manifest()["classes"][cls]["golden"]
    raw = path.read_bytes()
    rows = load_jsonl(path)
    assert raw == dump_jsonl(rows).encode("utf-8")
    assert b"\r" not in raw
    assert len({row["id"] for row in rows}) == len(rows)
    assert all(set(row) == {"id", "input", "output"} for row in rows)


@pytest.mark.parametrize("cls", _harness_classes())
def test_every_class_covers_empty_list_and_none_inputs(cls):
    rows = load_jsonl(GOLDEN / load_manifest()["classes"][cls]["golden"])
    inputs = [row["input"] for row in rows]
    assert any(_contains(i, lambda v: v == []) for i in inputs), f"{cls}: no empty-list input"
    assert any(_contains(i, lambda v: v is None) for i in inputs), f"{cls}: no None input"


def test_dedup_adjacency_pairs_merge_and_stay_apart():
    rows = {r["id"]: r for r in load_jsonl(GOLDEN / "dedup_verdicts.jsonl")}
    exact = rows["dedup-exact-equal"]
    one_char = rows["dedup-one-char-apart"]
    assert len(exact["input"]["jobs"]) == 2
    assert len(exact["output"]) == 1
    assert len(one_char["input"]["jobs"]) == 2
    assert len(one_char["output"]) == 2
    assert rows["dedup-empty-list"]["output"] == []
    assert rows["norm-company-none"]["output"] == ""


# ---------------------------------------------------------------------------
# Generator behaviour
# ---------------------------------------------------------------------------


def _snapshot(directory: Path) -> dict[str, tuple[bytes, int]]:
    return {
        p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in directory.iterdir() if p.is_file()
    }


def test_generator_check_mode_is_clean(capsys):
    before = _snapshot(GOLDEN)
    code = generate_golden.check(GOLDEN)
    printed = capsys.readouterr().out
    assert code == 0
    assert "DRIFT" not in printed
    assert _snapshot(GOLDEN) == before


def test_generator_check_mode_reports_drift(tmp_path, capsys):
    copy_dir = _copy_golden(tmp_path)
    path = copy_dir / "dedup_verdicts.jsonl"
    rows = load_jsonl(path)
    rows[0]["output"] = "tampered"
    path.write_text(dump_jsonl(rows), encoding="utf-8", newline="")

    code = generate_golden.check(copy_dir)
    printed = capsys.readouterr().out

    assert code == 1
    assert f"DRIFT dedup_verdicts {rows[0]['id']}" in printed


def test_generator_refuses_pii_and_writes_nothing(tmp_path, capsys):
    copy_dir = _copy_golden(tmp_path)
    path = copy_dir / "dedup_verdicts.jsonl"
    rows = load_jsonl(path)
    rows[0]["input"]["value"] = "".join(_EMAIL_PARTS)
    path.write_text(dump_jsonl(rows), encoding="utf-8", newline="")
    snapshot = {p.name: p.read_bytes() for p in copy_dir.iterdir() if p.is_file()}

    code = generate_golden.regenerate(["dedup_verdicts"], copy_dir)

    assert code == 1
    assert "PII scan hit" in capsys.readouterr().err
    assert {p.name: p.read_bytes() for p in copy_dir.iterdir() if p.is_file()} == snapshot


def test_generator_rejects_duplicate_inputs_and_writes_nothing(tmp_path, capsys):
    copy_dir = _copy_golden(tmp_path)
    path = copy_dir / "dedup_verdicts.jsonl"
    rows = load_jsonl(path)
    rows.append({"id": "copy-of-first", "input": rows[0]["input"], "output": rows[0]["output"]})
    path.write_text(dump_jsonl(rows), encoding="utf-8", newline="")
    snapshot = {p.name: p.read_bytes() for p in copy_dir.iterdir() if p.is_file()}

    code = generate_golden.regenerate(["dedup_verdicts"], copy_dir)

    assert code == 1
    assert "duplicate input" in capsys.readouterr().err
    assert {p.name: p.read_bytes() for p in copy_dir.iterdir() if p.is_file()} == snapshot


def test_regeneration_reproduces_the_committed_golden_bytes(tmp_path):
    copy_dir = _copy_golden(tmp_path)
    committed = (GOLDEN / "dedup_verdicts.jsonl").read_bytes()

    code = generate_golden.regenerate(["dedup_verdicts"], copy_dir)

    assert code == 0
    assert (copy_dir / "dedup_verdicts.jsonl").read_bytes() == committed
    assert manifest_problems(copy_dir) == []


def test_generator_rejects_a_class_without_a_harness(capsys):
    with pytest.raises(SystemExit) as excinfo:
        generate_golden.main(["--class", "gate_verdicts"])
    assert excinfo.value.code == 2
    assert "no harness" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Gate verdict records (A2)
# ---------------------------------------------------------------------------


def _gate_files(tmp_path: Path, verdict_lines: list[dict[str, Any]]) -> tuple[Path, Path]:
    drafts = tmp_path / "gate_drafts.jsonl"
    drafts.write_text(
        dump_jsonl([{"id": "draft-a", "kind": "form_answer", "text": "x", "planted": []}]),
        encoding="utf-8",
    )
    verdicts = tmp_path / "gate_verdicts.jsonl"
    verdicts.write_text(dump_jsonl(verdict_lines), encoding="utf-8")
    return verdicts, drafts


def _gate_line(gate: str, verdict: str = "pass", code: str = "no_issue") -> dict[str, Any]:
    return {"draft_id": "draft-a", "gate": gate, "verdict": verdict, "reason_code": code}


def test_gate_verdict_problems_accepts_a_clean_file(tmp_path):
    verdicts, drafts = _gate_files(tmp_path, [_gate_line("fact"), _gate_line("voice", "fail")])
    assert gate_verdict_problems(verdicts, drafts) == []
    narrowed = gate_verdict_problems(verdicts, drafts, gates="fact")
    assert any("was not run" in p for p in narrowed)


@pytest.mark.parametrize(
    ("lines", "needle"),
    [
        ([{**_gate_line("fact"), "draft_id": "nope"}, _gate_line("voice")], "unknown draft_id"),
        ([_gate_line("fact", "maybe"), _gate_line("voice")], "verdict must be"),
        ([_gate_line("fact"), _gate_line("fact"), _gate_line("voice")], "more than once"),
        ([_gate_line("fact")], "differ from drafts x gates"),
        ([_gate_line("fact", code="Bad Code"), _gate_line("voice")], "reason_code"),
        ([], "file is empty"),
    ],
    ids=["unknown-draft", "bad-verdict", "duplicate-pair", "missing-pair", "bad-code", "empty"],
)
def test_gate_verdict_problems_reports_each_defect(tmp_path, lines, needle):
    verdicts, drafts = _gate_files(tmp_path, lines)
    problems = gate_verdict_problems(verdicts, drafts)
    assert any(needle in p for p in problems), problems
    assert problems != []


def test_gate_verdicts_golden_matches_manifest():
    manifest = load_manifest()
    entry = manifest["classes"].get("gate_verdicts")
    assert len(manifest["classes"]) >= 1
    if entry is None:
        assert not (GOLDEN / "gate_verdicts.jsonl").exists()
    elif entry["status"] == "frozen":
        golden = GOLDEN / entry["golden"]
        gates = entry["gates"]
        assert golden.is_file()
        assert sha256_file(golden) == entry["sha256"]
        assert {"fact", "voice"} >= set(gates.split(","))
        assert gate_verdict_problems(golden, GOLDEN / "gate_drafts.jsonl", gates=gates) == []
    else:
        assert entry["status"] == "awaiting_private_run"
        assert entry["golden"] is None
        assert not (GOLDEN / "gate_verdicts.jsonl").exists()
