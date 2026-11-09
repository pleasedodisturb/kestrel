"""Replay and integrity tests for the MAP-02 goldens (Phase 11, plan 01).

Every golden class that has a harness entry is replayed over its stored inputs
and must reproduce its stored output exactly; the manifest checker proves the
bytes and the producer files are the ones that were recorded. Each guard is
paired with a test that makes it fail on purpose (guard-the-guard).
"""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

import batch_probe
import blocklist
import job_scorer
import pytest
import tier0_ats_poller

from tests.eval.geo.replay import scrub_patterns
from tests.replay import generate_golden
from tests.replay._support import (
    FAMILY_B_CLASSES,
    FAMILY_B_REPLAY,
    FROZEN_NOW,
    GATE_CLASS,
    GOLDEN,
    HARNESS,
    PINNED_GEO_CONFIG,
    REPO_ROOT,
    REQUIRED_PATTERN_LABELS,
    awaiting_entry,
    dump_jsonl,
    dump_manifest,
    gate_verdict_problems,
    git_blob,
    load_jsonl,
    load_manifest,
    manifest_pending,
    manifest_problems,
    pii_hits,
    pinned,
    private_golden_problems,
    sha256_file,
)

_EMAIL_PARTS = ("some.one", "@", "example", ".org")
_PLANTED_LABELS = {
    "unsupported_number",
    "unsupported_employer",
    "unsupported_title",
    "tenure_mismatch",
    "unsupported_tool",
    "ownership_inflation",
    "generic_ai_phrasing",
    "banned_phrase",
}


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
# Pins and transport (T-11-02, T-11-04)
# ---------------------------------------------------------------------------


def test_scan_transport_refuses_unknown_urls():
    case = {
        "op": "fetch_greenhouse",
        "slug": "synth-board-z",
        "company_key": "synth-greenhouse-co",
        "payload": {"jobs": []},
        "payload_url": "https://example.invalid/registered-for-another-url",
    }
    with pytest.raises(AssertionError) as excinfo, pinned():
        HARNESS["scan_arrivals"](case)
    message = str(excinfo.value)
    assert "https://boards-api.greenhouse.io/v1/boards/synth-board-z/jobs" in message
    assert "synth-board-z" in message


def test_pins_are_restored_after_use(monkeypatch):
    sentinel_config = batch_probe.GeoConfig(home_tokens=("sentinel-only",))
    sentinel_regex = re.compile("sentinel-only-blocked")
    sentinel_profile = object()

    def sentinel_clock() -> str:
        return "sentinel-clock"

    monkeypatch.setattr(batch_probe, "_CONFIG", sentinel_config)
    monkeypatch.setattr(blocklist, "_BLOCKED_RE", sentinel_regex)
    monkeypatch.setattr(job_scorer, "_GEO_PROFILE", sentinel_profile)
    monkeypatch.setattr(tier0_ats_poller, "_utcnow_iso", sentinel_clock)
    monkeypatch.setenv("PIPELINE_MODE", "sentinel-mode")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", "sentinel-summary")

    with pinned():
        assert batch_probe._CONFIG is PINNED_GEO_CONFIG
        assert blocklist._BLOCKED_RE.pattern == blocklist._compile(blocklist.FLOOR_BLOCKED).pattern
        assert job_scorer._GEO_PROFILE is None
        assert tier0_ats_poller._utcnow_iso() == FROZEN_NOW
        assert "PIPELINE_MODE" not in os.environ
        assert "GITHUB_STEP_SUMMARY" not in os.environ

    assert batch_probe._CONFIG is sentinel_config
    assert blocklist._BLOCKED_RE is sentinel_regex
    assert job_scorer._GEO_PROFILE is sentinel_profile
    assert tier0_ats_poller._utcnow_iso is sentinel_clock
    assert os.environ["PIPELINE_MODE"] == "sentinel-mode"
    assert os.environ["GITHUB_STEP_SUMMARY"] == "sentinel-summary"


def test_pins_are_restored_when_a_producer_raises():
    original_config = batch_probe._CONFIG
    original_clock = tier0_ats_poller._utcnow_iso
    with pytest.raises(RuntimeError, match="boom"), pinned():
        raise RuntimeError("boom")
    assert batch_probe._CONFIG is original_config
    assert tier0_ats_poller._utcnow_iso is original_clock


def test_case_env_values_do_not_leak_out_of_a_replay(monkeypatch):
    monkeypatch.delenv("PIPELINE_MAX_SCORE", raising=False)
    case = {"op": "effective_scoring_cap", "env": {"PIPELINE_MAX_SCORE": "77"}}
    with pinned():
        assert HARNESS["scoring"](case) == 77
        assert "PIPELINE_MAX_SCORE" not in os.environ
    assert "PIPELINE_MAX_SCORE" not in os.environ


def test_scoring_replay_never_writes_into_the_tracking_folder():
    tracking = REPO_ROOT / "tracking"
    before = sorted((p.name, p.stat().st_mtime_ns) for p in tracking.iterdir())
    case = {
        "op": "fallback_score",
        "jobs": [
            {
                "title": "Product Manager",
                "company": "Synthco Robotics GmbH",
                "location": "Remote, Europe",
                "remote": True,
                "description": "",
            }
        ],
    }
    with pinned():
        scored = HARNESS["scoring"](case)
    after = sorted((p.name, p.stat().st_mtime_ns) for p in tracking.iterdir())
    assert scored[0]["fit_score"] >= 1
    assert after == before


def test_manifest_records_the_pins_each_class_needs():
    classes = load_manifest()["classes"]
    joined = {cls: " ".join(classes[cls]["pins"]) for cls in HARNESS}
    assert "batch_probe._CONFIG" in joined["eligibility_verdicts"]
    assert "job_scorer._GEO_PROFILE" in joined["eligibility_verdicts"]
    assert "blocklist floor" in joined["eligibility_verdicts"]
    assert "tier0_ats_poller._utcnow_iso" in joined["scan_arrivals"]
    assert "MockTransport" in joined["scan_arrivals"]
    assert "PIPELINE_*" in joined["scoring"]


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


# ---------------------------------------------------------------------------
# Digest, gate inputs and the awaiting registrations
# ---------------------------------------------------------------------------


def test_digest_golden_stores_markdown_as_json_and_matches_the_written_file():
    rows = load_jsonl(GOLDEN / "digest.jsonl")
    assert len(rows) >= 4
    assert all(row["output"]["file_matches_return"] is True for row in rows)
    assert all(row["output"]["markdown"].startswith("# Daily Job Scan") for row in rows)
    assert sorted(p.name for p in GOLDEN.glob("*.md")) == ["README.md"]


def test_gate_inputs_are_registered():
    manifest = load_manifest()
    entry = manifest["classes"]["gate_verdicts"]
    drafts = load_jsonl(GOLDEN / "gate_drafts.jsonl")
    assert entry["status"] in {"awaiting_private_run", "frozen"}
    if entry["status"] == "awaiting_private_run":
        assert entry["golden"] is None
    else:
        assert (GOLDEN / entry["golden"]).is_file()
        assert sha256_file(GOLDEN / entry["golden"]) == entry["sha256"]
    for file_name, sha in entry["input_files"].items():
        assert sha256_file(GOLDEN / file_name) == sha
    assert set(entry["input_files"]) == {"gate_drafts.jsonl", "gate_fact_sheet.json"}
    assert len({d["id"] for d in drafts}) == len(drafts) >= 12
    assert sum(1 for d in drafts if d["planted"] == []) >= 3
    assert {label for d in drafts for label in d["planted"]} == _PLANTED_LABELS
    assert {d["kind"] for d in drafts} == {
        "cover_letter_paragraph",
        "outreach_message",
        "form_answer",
    }
    assert all(len(d["planted"]) <= 1 for d in drafts)


def test_gate_fact_sheet_is_fictional_and_unnamed():
    text = (GOLDEN / "gate_fact_sheet.json").read_text(encoding="utf-8")
    sheet = json.loads(text)
    assert sheet["candidate"] == "Candidate A"
    assert len(sheet["employers"]) >= 2
    required = {"name", "title", "start_year", "end_year", "tools"}
    assert all(required <= set(employer) for employer in sheet["employers"])
    assert pii_hits(text) == {}


def test_fresh_gate_registration_is_awaiting(tmp_path):
    copy_dir = _copy_golden(tmp_path)
    manifest_path = copy_dir / "MANIFEST.json"
    manifest = load_manifest(manifest_path)
    del manifest["classes"]["gate_verdicts"]
    manifest_path.write_text(dump_manifest(manifest), encoding="utf-8", newline="")

    assert generate_golden.register_awaiting(copy_dir) == 0
    entry = load_manifest(manifest_path)["classes"]["gate_verdicts"]

    assert entry["status"] == "awaiting_private_run"
    assert entry["golden"] is None
    assert entry["producers"] == {"the private pipeline": None}
    assert not (copy_dir / "gate_verdicts.jsonl").exists()
    assert entry["input_files"]["gate_drafts.jsonl"] == sha256_file(copy_dir / "gate_drafts.jsonl")
    assert manifest_problems(copy_dir) == []


def test_register_awaiting_never_resets_a_frozen_class(tmp_path):
    copy_dir = _copy_golden(tmp_path)
    manifest_path = copy_dir / "MANIFEST.json"
    manifest = load_manifest(manifest_path)
    manifest["classes"]["dedup_verdicts"]["generated"] = "2001-02"
    manifest_path.write_text(dump_manifest(manifest), encoding="utf-8", newline="")
    before = manifest_path.read_bytes()

    assert generate_golden.register_awaiting(copy_dir) == 0

    assert manifest_path.read_bytes() == before
    assert load_manifest(manifest_path)["classes"]["dedup_verdicts"]["generated"] == "2001-02"


def _reset_private_classes(golden_dir: Path) -> None:
    """Put gate_verdicts and the Family B classes back to their awaiting entries."""
    path = golden_dir / "MANIFEST.json"
    manifest = load_manifest(path)
    for cls in (GATE_CLASS, *FAMILY_B_CLASSES):
        (golden_dir / f"{cls}.jsonl").unlink(missing_ok=True)
        manifest["classes"][cls] = awaiting_entry(cls, golden_dir)
    path.write_text(dump_manifest(manifest), encoding="utf-8", newline="")


def _run(argv: list[str]) -> int:
    try:
        return generate_golden.main(argv)
    except SystemExit as exc:
        return int(exc.code)


def _gate_verdict_file(path: Path, gates: tuple[str, ...] = ("fact", "voice")) -> Path:
    drafts = load_jsonl(GOLDEN / "gate_drafts.jsonl")
    lines = [
        {"draft_id": d["id"], "gate": gate, "verdict": "pass", "reason_code": "no_issue_found"}
        for d in sorted(drafts, key=lambda d: d["id"])
        for gate in gates
    ]
    path.write_text(dump_jsonl(lines), encoding="utf-8", newline="")
    return path


def _register_gate(copy_dir: Path, file: Path, *extra: str) -> int:
    return _run(
        [
            "--register-private",
            "gate_verdicts",
            "--file",
            str(file),
            "--private-commit",
            "a" * 40,
            "--golden-dir",
            str(copy_dir),
            *extra,
        ]
    )


def test_register_private_refuses_bad_files(tmp_path):
    copy_dir = _copy_golden(tmp_path)
    _reset_private_classes(copy_dir)
    manifest_path = copy_dir / "MANIFEST.json"
    before = manifest_path.read_bytes()
    good = _gate_verdict_file(tmp_path / "good.jsonl")
    lines = load_jsonl(good)

    def write(name: str, content: list[dict[str, Any]]) -> Path:
        path = tmp_path / name
        path.write_text(dump_jsonl(content), encoding="utf-8", newline="")
        return path

    bad_files = {
        "unknown-draft": (
            write("a.jsonl", [{**lines[0], "draft_id": "no-such"}, *lines[1:]]),
            "fact,voice",
        ),
        "bad-verdict": (
            write("b.jsonl", [{**lines[0], "verdict": "maybe"}, *lines[1:]]),
            "fact,voice",
        ),
        "duplicate-pair": (write("c.jsonl", [lines[0], *lines]), "fact,voice"),
        "empty": (write("d.jsonl", []), "fact,voice"),
        "missing-pair": (write("e.jsonl", lines[:-1]), "fact,voice"),
        "voice-while-fact-only": (good, "fact"),
    }
    for label, (path, gates) in bad_files.items():
        assert _register_gate(copy_dir, path, "--gates", gates) == 1, label
        assert manifest_path.read_bytes() == before, label

    pii_file = tmp_path / "f.jsonl"
    pii_file.write_text(
        good.read_text(encoding="utf-8") + "".join(_EMAIL_PARTS) + "\n", encoding="utf-8"
    )
    assert any(
        "PII scan hit" in p for p in gate_verdict_problems(pii_file, copy_dir / "gate_drafts.jsonl")
    )
    assert _register_gate(copy_dir, pii_file) == 1
    assert manifest_path.read_bytes() == before

    assert _register_gate(copy_dir, good, "--dry-run") == 0
    assert manifest_path.read_bytes() == before


def test_register_private_freezes_gate_verdicts_with_the_narrowed_gates(tmp_path):
    copy_dir = _copy_golden(tmp_path)
    _reset_private_classes(copy_dir)
    target = _gate_verdict_file(copy_dir / "gate_verdicts.jsonl", gates=("fact",))

    code = _register_gate(copy_dir, target, "--gates", "fact")
    entry = load_manifest(copy_dir / "MANIFEST.json")["classes"]["gate_verdicts"]

    assert code == 0
    assert (entry["status"], entry["gates"], entry["producers"]) == (
        "frozen",
        "fact",
        {"the private pipeline": "a" * 40},
    )
    assert manifest_problems(copy_dir) == []
    assert generate_golden.check(copy_dir) == 0


# ---------------------------------------------------------------------------
# Family B: validator, lifecycle and replay modes
# ---------------------------------------------------------------------------


def _posting(n: int, **overrides: Any) -> dict[str, Any]:
    titles = ["Product Manager", "Platform Engineer", "Data Analyst", "Support Lead", "Ops Lead"]
    company = (n % 40) + 10
    posting = {
        "title": f"{titles[n % 5]} {n}",
        "company": f"Company-{company:02d}",
        "location": "Remote, Europe" if n % 2 else "Cork, Ireland",
        "url": f"https://example.invalid/row-{n:03d}",
        "source": f"tier0:greenhouse:company-{company:02d}",
        "remote": bool(n % 2),
    }
    return posting | overrides


def _clean_io(cls: str, n: int) -> dict[str, Any]:
    """The input and output of the n-th clean record of a class."""
    if cls == "private_scan_arrivals":
        posting = _posting(n)
        return {
            "input": {"source": posting["source"], "search_keyword": "product manager"},
            "output": posting,
        }
    if cls == "private_dedup_verdicts":
        duplicate = n % 2 == 1
        return {
            "input": {"a": _posting(n), "b": _posting(n + 100)},
            "output": {
                "duplicate": duplicate,
                "fuzzy_ratio": 100.0 if duplicate else 41.5 + n / 100,
                "kept": "a" if duplicate else "b",
                "reason_code": "same_job_key" if duplicate else "distinct_jobs",
            },
        }
    if cls == "private_eligibility_verdicts":
        home = n % 2 == 0
        return {
            "input": _posting(n, location="Home-01" if home else "Somewhere, Elsewhere"),
            "output": {
                "geo_class": "home" if home else "foreign",
                "prefilter_skip": False,
                "reason_code": "geo_rule",
                "score_cap": None,
            },
        }
    if cls == "private_scoring":
        return {
            "input": _posting(n, geo_class="foreign"),
            "output": {
                "effort_flag": "sweet-spot",
                "fit_score": 5.0 + (n % 5) / 2,
                "prep_level": 0,
                "review_flag": False,
                "scorer": "model-a",
                "tier": "T2" if n % 2 == 0 else None,
            },
        }
    return {
        "input": {
            "config": {"hours_old": 24, "min_score": 5, "mode": "api-only"},
            "counts": {"arrived": 100 + n, "scored": 50 + n, "shortlisted": 5},
        },
        "output": {
            "footer": None,
            "rows": [
                {
                    "company": f"Company-{n + 10:02d}",
                    "effort_flag": None,
                    "fit_score": 7.5,
                    "location": "Remote, Europe",
                    "source": "tier0:greenhouse:company-11",
                    "tier": "T2",
                    "title": f"Product Manager {n}",
                }
            ],
        },
    }


def _clean_private_rows(cls: str) -> list[dict[str, Any]]:
    """A synthetic sample that satisfies the Family B contract and every coverage invariant.

    Months alternate and every class's coverage values alternate too, so keeping
    only the first rows (19 for private_scoring, 2 for private_digest) still meets
    every coverage invariant and breaks only the row minimum.
    """
    count = 4 if cls == "private_digest" else 20
    return [
        {
            "id": f"row-{n:03d}",
            "month": "2000-01" if n % 2 else "2000-02",
            "profile_scope": "maintainer",
            "scrubbed": True,
            **_clean_io(cls, n),
        }
        for n in range(1, count + 1)
    ]


def _write_private(directory: Path, cls: str, rows: list[dict[str, Any]]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{cls}.jsonl"
    path.write_text(dump_jsonl(rows), encoding="utf-8", newline="")
    return path


@pytest.mark.parametrize("cls", FAMILY_B_CLASSES)
def test_private_golden_validator_accepts_a_clean_sample(tmp_path, cls):
    path = _write_private(tmp_path, cls, _clean_private_rows(cls))
    expected = 4 if cls == "private_digest" else 20
    assert private_golden_problems(path, cls) == []
    assert len(path.read_text(encoding="utf-8").splitlines()) == expected


def _many_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for i in range(201):
        row = copy.deepcopy(rows[i % len(rows)])
        row["id"] = f"row-{i + 1:03d}"
        row["input"]["title"] = f"Product Manager {i + 1}"
        out.append(row)
    return out


def _set_all(rows: list[dict[str, Any]], path: tuple[str, ...], value: Any) -> list[dict[str, Any]]:
    for row in rows:
        target = row
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
    return rows


def _first(rows: list[dict[str, Any]], key: str, sub: str, value: Any) -> list[dict[str, Any]]:
    rows[0][key][sub] = value
    return rows


# Assembled from fragments so no day-level date, @ string or query URL is committed.
_DAY = "-".join(["2000", "01", "15"])
_AT = "".join(["a", "@", "b"])
_QUERY_URL = "https://example.invalid/row-001" + "?" + "utm=1"


def _drop_scrubbed(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    del rows[0]["scrubbed"]
    return rows


def _copy_first_pair(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows[1]["input"] = copy.deepcopy(rows[0]["input"])
    rows[1]["output"] = copy.deepcopy(rows[0]["output"])
    return rows


def _day_month(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows[0]["month"] = _DAY
    return rows


def _other_scope(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows[0]["profile_scope"] = "generic"
    return rows


def _home_verbatim(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    home = next(r for r in rows if r["output"]["geo_class"] == "home")
    home["input"]["location"] = "Cork"
    return rows


_SCORING, _DIGEST = "private_scoring", "private_digest"
_DEDUP, _ELIG = "private_dedup_verdicts", "private_eligibility_verdicts"

# (defect, class, mutation of the clean rows, the rule the validator must name)
_DEFECTS: list[tuple[str, str, Any, str]] = [
    ("day_date", _SCORING, _day_month, "day-level date"),
    ("at_sign", _SCORING, lambda r: _first(r, "input", "title", _AT), "@ sign"),
    (
        "url_query",
        _SCORING,
        lambda r: _first(r, "input", "url", _QUERY_URL),
        "url query or non-synthetic url",
    ),
    (
        "raw_company",
        _SCORING,
        lambda r: _first(r, "input", "company", "Synthco Robotics GmbH"),
        "company is not a synthetic token",
    ),
    ("too_many_rows", _SCORING, _many_rows, "more than 200 rows"),
    ("too_few_rows", _SCORING, lambda r: r[:19], "fewer rows than the class minimum"),
    (
        "single_month",
        _SCORING,
        lambda r: _set_all(r, ("month",), "2000-01"),
        "fewer than two months",
    ),
    ("duplicate_input_output", _SCORING, _copy_first_pair, "duplicate input and output"),
    ("single_tier", _SCORING, lambda r: _set_all(r, ("output", "tier"), "T2"), "coverage: tier"),
    (
        "dream_tier_true",
        _SCORING,
        lambda r: _first(r, "input", "dream_tier", True),
        "config-derived flag",
    ),
    (
        "floored_true",
        _SCORING,
        lambda r: _first(r, "output", "floored", True),
        "config-derived flag",
    ),
    ("missing_scrubbed", _SCORING, _drop_scrubbed, "scrubbed is not true"),
    ("wrong_profile_scope", _SCORING, _other_scope, "profile_scope is not maintainer"),
    ("unknown_key", _SCORING, lambda r: _first(r, "output", "note", "free text"), "unknown key"),
    ("too_few_digest_runs", _DIGEST, lambda r: r[:2], "fewer rows than the class minimum"),
    (
        "digest_markdown_key",
        _DIGEST,
        lambda r: _first(r, "output", "markdown", "# Digest"),
        "unknown key",
    ),
    (
        "digest_footer_text",
        _DIGEST,
        lambda r: _first(r, "output", "footer", "Generated by a script"),
        "footer is not null",
    ),
    (
        "one_sided_dedup",
        _DEDUP,
        lambda r: _set_all(r, ("output", "duplicate"), True),
        "coverage: duplicate true and false",
    ),
    (
        "single_geo_class",
        _ELIG,
        lambda r: _set_all(r, ("output", "geo_class"), "foreign"),
        "coverage: geo_class",
    ),
    ("home_location_verbatim", _ELIG, _home_verbatim, "home location not tokenised"),
    ("blocked_true", _ELIG, lambda r: _first(r, "output", "blocked", True), "config-derived flag"),
    (
        "soft_flag_true",
        _ELIG,
        lambda r: _first(r, "output", "soft_flag", True),
        "config-derived flag",
    ),
    (
        "config_reason_code",
        _ELIG,
        lambda r: _first(r, "output", "reason_code", "blocked_company"),
        "config-derived reason code",
    ),
]


def test_defect_table_covers_the_23_documented_mutations():
    assert len(_DEFECTS) == 23
    assert len({name for name, _cls, _fn, _rule in _DEFECTS}) == 23
    assert {cls for _name, cls, _fn, _rule in _DEFECTS} == {_SCORING, _DIGEST, _DEDUP, _ELIG}


@pytest.mark.parametrize(
    ("defect", "cls", "mutate", "rule"), _DEFECTS, ids=[d[0] for d in _DEFECTS]
)
def test_private_golden_validator_rejects_each_defect(tmp_path, defect, cls, mutate, rule):
    clean = _clean_private_rows(cls)
    clean_path = _write_private(tmp_path / "clean", cls, clean)
    assert private_golden_problems(clean_path, cls) == []

    mutated = mutate(copy.deepcopy(clean))
    mutated_path = _write_private(tmp_path / "mutated", cls, mutated)
    problems = private_golden_problems(mutated_path, cls)

    assert mutated != clean
    assert any(rule in problem for problem in problems), (defect, problems)


def test_private_golden_validator_never_raises_on_unreadable_input(tmp_path):
    missing = tmp_path / "private_scoring.jsonl"
    bad_utf8 = tmp_path / "bad.jsonl"
    bad_utf8.write_bytes(b"\xff\xfe\x00")
    not_object = tmp_path / "list.jsonl"
    not_object.write_text("[1,2]\n", encoding="utf-8")

    assert any("cannot read" in p for p in private_golden_problems(missing, _SCORING))
    assert any("UTF-8" in p for p in private_golden_problems(bad_utf8, _SCORING))
    assert any("not a JSON object" in p for p in private_golden_problems(not_object, _SCORING))
    assert any("unknown Family B class" in p for p in private_golden_problems(missing, "nope"))


@pytest.mark.parametrize("cls", FAMILY_B_CLASSES)
def test_private_golden_matches_manifest(cls):
    entry = load_manifest()["classes"][cls]
    assert entry["replay"] == FAMILY_B_REPLAY[cls]
    if entry["status"] == "awaiting_private_run":
        assert entry["golden"] is None
        assert not (GOLDEN / f"{cls}.jsonl").exists()
    else:
        golden = GOLDEN / entry["golden"]
        assert golden.is_file()
        assert sha256_file(golden) == entry["sha256"]
        assert re.fullmatch(r"P-\d{2,3}", entry["producer_row"])
        assert entry["profile_scope"] == "maintainer"
        assert private_golden_problems(golden, cls) == []


def test_every_family_b_class_is_registered_without_a_harness():
    classes = load_manifest()["classes"]
    for cls in FAMILY_B_CLASSES:
        assert cls in classes
        assert cls not in HARNESS
        assert classes[cls]["inputs"] == "scrubbed"
        assert classes[cls]["profile_scope"] == "maintainer"
        assert classes[cls]["producers"].keys() == {"the private pipeline"}


@pytest.mark.parametrize("cls", [_SCORING, _DIGEST, GATE_CLASS])
def test_generator_never_recomputes_private_classes(cls, capsys):
    with pytest.raises(SystemExit) as excinfo:
        generate_golden.main(["--class", cls])
    assert excinfo.value.code == 2
    assert "no harness" in capsys.readouterr().err


def _family_b_args(copy_dir: Path, sha: str) -> list[str]:
    return [
        "--register-private",
        _SCORING,
        "--private-commit",
        sha,
        "--golden-dir",
        str(copy_dir),
    ]


def test_register_private_family_b_refuses_bad_input(tmp_path):
    copy_dir = _copy_golden(tmp_path)
    _reset_private_classes(copy_dir)
    manifest_path = copy_dir / "MANIFEST.json"
    before = manifest_path.read_bytes()
    ledger = tmp_path / "ledger.yaml"
    ledger.write_text("schema: 1\nrows:\n  - id: P-01\n    private: true\n", encoding="utf-8")
    sha = "b" * 40
    clean = _write_private(tmp_path / "ok", _SCORING, _clean_private_rows(_SCORING))
    broken_rows = _clean_private_rows(_SCORING)
    broken_rows[0]["month"] = _DAY
    broken = _write_private(tmp_path / "broken", _SCORING, broken_rows)
    base = _family_b_args(copy_dir, sha)
    led = ["--ledger", str(ledger)]

    refused = {
        "gates-given": (["--file", str(clean), "--producer-row", "P-01", "--gates", "fact"], 2),
        "no-producer-row": (["--file", str(clean)], 2),
        "malformed-producer-row": (["--file", str(clean), "--producer-row", "row-1"], 2),
        "row-not-in-ledger": (["--file", str(clean), "--producer-row", "P-02", *led], 1),
        "validator-failure": (["--file", str(broken), "--producer-row", "P-01", *led], 1),
        "file-not-in-golden-dir": (["--file", str(clean), "--producer-row", "P-01", *led], 2),
    }
    for label, (extra, expected) in refused.items():
        assert _run([*base, *extra]) == expected, label
        assert manifest_path.read_bytes() == before, label

    assert _run([*base, "--file", str(clean), "--producer-row", "P-01", *led, "--dry-run"]) == 0
    assert manifest_path.read_bytes() == before
    gate_with_row = ["--producer-row", "P-01"]
    assert _register_gate(copy_dir, clean, *gate_with_row) == 2

    placed = copy_dir / f"{_SCORING}.jsonl"
    shutil.copyfile(clean, placed)
    assert _run([*base, "--file", str(placed), "--producer-row", "P-01", *led]) == 0
    entry = load_manifest(manifest_path)["classes"][_SCORING]
    assert (entry["status"], entry["inputs"], entry["profile_scope"]) == (
        "frozen",
        "scrubbed",
        "maintainer",
    )
    assert (entry["replay"], entry["producer_row"], entry["producer_commit"]) == (
        "reference",
        "P-01",
        sha,
    )
    assert entry["sha256"] == sha256_file(placed)

    missing_ledger = tmp_path / "no-such-ledger.yaml"
    assert manifest_problems(copy_dir, private_ledger=ledger) == []
    assert manifest_problems(copy_dir, private_ledger=missing_ledger) == []
    pending = manifest_pending(copy_dir, private_ledger=missing_ledger)
    assert any(_SCORING in line and "not crossed yet" in line for line in pending)
    assert manifest_pending(copy_dir, private_ledger=ledger) == []

    other_ledger = tmp_path / "other.yaml"
    other_ledger.write_text("schema: 1\nrows:\n  - id: P-09\n", encoding="utf-8")
    assert any(
        "not a row id" in p for p in manifest_problems(copy_dir, private_ledger=other_ledger)
    )


def test_register_private_family_b_reports_a_pending_ledger(tmp_path, capsys):
    copy_dir = _copy_golden(tmp_path)
    _reset_private_classes(copy_dir)
    clean = _write_private(tmp_path / "ok", _SCORING, _clean_private_rows(_SCORING))
    argv = [
        *_family_b_args(copy_dir, "d" * 40),
        "--file",
        str(clean),
        "--producer-row",
        "P-04",
        "--ledger",
        str(tmp_path / "absent.yaml"),
        "--dry-run",
    ]
    assert _run(argv) == 0
    assert "PENDING producer_row P-04: ledger not present" in capsys.readouterr().out


def test_private_golden_replay_modes():
    assert set(FAMILY_B_REPLAY) == set(FAMILY_B_CLASSES)
    assert set(FAMILY_B_REPLAY.values()) <= {"exact", "shape", "reference"}
    assert FAMILY_B_REPLAY[_SCORING] == "reference"
    assert FAMILY_B_REPLAY[_DIGEST] == "reference"
    assert manifest_problems(GOLDEN) == []


def test_manifest_checker_rejects_a_wrong_replay_mode(tmp_path):
    copy_dir = _copy_golden(tmp_path)
    manifest_path = copy_dir / "MANIFEST.json"
    manifest = load_manifest(manifest_path)
    assert manifest_problems(copy_dir) == []
    manifest["classes"][_SCORING]["replay"] = "exact"
    manifest_path.write_text(dump_manifest(manifest), encoding="utf-8", newline="")

    problems = manifest_problems(copy_dir)

    assert any("replay mode" in p and _SCORING in p for p in problems)
    assert load_manifest()["classes"][_SCORING]["replay"] == "reference"


def test_manifest_checker_rejects_awaiting_for_a_synthetic_class_and_an_unlisted_family_b(tmp_path):
    copy_dir = _copy_golden(tmp_path)
    manifest_path = copy_dir / "MANIFEST.json"
    manifest = load_manifest(manifest_path)
    manifest["classes"]["dedup_verdicts"]["status"] = "awaiting_private_run"
    del manifest["classes"][_DIGEST]
    manifest_path.write_text(dump_manifest(manifest), encoding="utf-8", newline="")

    problems = manifest_problems(copy_dir)

    assert any("only a class whose producer is" in p and "dedup_verdicts" in p for p in problems)
    assert any(_DIGEST in p and "not listed" in p for p in problems)


def test_readme_states_the_two_family_contract():
    text = (GOLDEN / "README.md").read_text(encoding="utf-8")
    flat = text.replace("\n", " ")
    assert "Two golden families" in text
    assert 'profile_scope: "maintainer"' in text
    assert "output-only" in text
    assert "only inside the private pipeline's" in flat
    for mode in ("exact", "shape", "reference"):
        assert f"`{mode}`" in text
    assert "`private_scoring`, `private_digest` | a model call made" in text
    assert len(text.splitlines()) >= 30
