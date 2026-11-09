"""Honesty test for the script ledger (MAP-01, decision D-06).

``tests/ports/PORT_LEDGER.yaml`` holds one row per file under ``tools/`` and per
scheduler-glue file. Retire deletes ``tools/`` on this ledger's word, so a stale
ledger is a deletion hazard (threat T-11-10). The swept file set is derived from
the filesystem, never from a hand-written list:

* every file under ``tools/`` (``__pycache__``, ``.pyc`` and ``.DS_Store`` excluded),
* every file under ``automation/``,
* every ``.github/workflows`` file other than ``ci.yml`` whose text contains ``tools/``.

Files that git ignores are dropped (``.venv/``, ``.claude/worktrees/`` and other
local noise never sit under these roots, but an ignored scratch file must not make
the answer differ between a worktree, the main checkout and CI). Tracked files are
never dropped, because ``git check-ignore`` does not report tracked paths.

Every file must match exactly one row, every row must match at least one file, and
the enumerations, the sort order and the listed tests are validated by
``ledger_problems``, a pure function proven by the guard cases below. The module
only reads files: running it twice leaves the working tree unchanged and no shared
state exists, so a parallel or interrupted run cannot leave a partial state.
"""

import copy
import fnmatch
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
LEDGER_PATH = Path(__file__).with_name("PORT_LEDGER.yaml")

RUN_STATUSES = frozenset({"scheduled", "by_hand", "dead"})
DISPOSITIONS = frozenset({"port", "keep_until_retire", "delete"})
MIN_SWEPT_FILES = 60
MIN_LEDGER_ROWS = 45

ANCHORS = (
    "tools/daily_pipeline.py",
    "tools/normalize.py",
    "tools/check_review_trailers.py",
    ".github/workflows/daily-scan.yml",
)

# Rows where REQUIREMENTS.md overrides ARCHITECTURE.md section 10 and must say so.
REQUIREMENTS_OVERRIDES = (
    "tools/auto_apply.py",
    "tools/batch_apply_browser.py",
    "tools/captcha_solver.py",
    "tools/generate_batch_covers.py",
    "tools/generate_batch_submit_yaml.py",
    "tools/germany_jobs.py",
    "tools/kit_builder.py",
    "tools/md_to_pdf_cover_letter.py",
    "tools/open_question_probe.py",
    "tools/render_cover_letter_html.py",
    "tools/render_tailored_cvs.py",
    "tools/scrape_form_questions.py",
    "tools/scrape_new_sources.py",
    "tools/scrape_resilient.py",
    "tools/scraper.py",
    "tools/source_registry.py",
    "tools/t3_lane.py",
    "tools/tier0_ats_poller.py",
)

_NOISE_PARTS = frozenset({"__pycache__"})
_NOISE_SUFFIXES = frozenset({".pyc"})
_NOISE_NAMES = frozenset({".DS_Store"})


# ---------------------------------------------------------------------------
# Sweep
# ---------------------------------------------------------------------------


def _is_noise(path: Path) -> bool:
    """True for build and OS noise that is never ledger material."""
    return (
        bool(_NOISE_PARTS & set(path.parts))
        or path.suffix in _NOISE_SUFFIXES
        or path.name in _NOISE_NAMES
    )


def _git_ignored(repo_root: Path, rels: list[str]) -> set[str]:
    """Return the subset of ``rels`` that git ignores (read-only; empty if git cannot say)."""
    if not rels:
        return set()
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-z", "--stdin"],
            input="\0".join(rels) + "\0",
            capture_output=True,
            text=True,
            cwd=repo_root,
            check=False,
        )
    except OSError:
        return set()
    if result.returncode not in (0, 1):
        return set()
    return {p for p in result.stdout.split("\0") if p}


def sweep_files(repo_root: Path) -> list[str]:
    """Return sorted repo-relative POSIX paths of every file the ledger must cover."""
    found: set[str] = set()
    for root_name in ("tools", "automation"):
        root = repo_root / root_name
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.is_file() and not _is_noise(path.relative_to(repo_root)):
                found.add(path.relative_to(repo_root).as_posix())
    workflows = repo_root / ".github" / "workflows"
    if workflows.is_dir():
        for path in workflows.iterdir():
            if path.suffix not in {".yml", ".yaml"} or path.name == "ci.yml":
                continue
            if "tools/" in path.read_text(encoding="utf-8", errors="replace"):
                found.add(path.relative_to(repo_root).as_posix())
    ignored = _git_ignored(repo_root, sorted(found))
    return sorted(found - ignored)


# ---------------------------------------------------------------------------
# Detector (pure)
# ---------------------------------------------------------------------------


def _row_key(row: object) -> str:
    """Sort key of a row: its path, else its glob, else the empty string."""
    if isinstance(row, dict):
        key = row.get("path") or row.get("glob")
        if isinstance(key, str):
            return key
    return ""


def _row_matches(row: dict, rel: str) -> bool:
    """True when ``rel`` falls under the row's path, directory or glob."""
    path = row.get("path")
    if isinstance(path, str):
        return rel == path or (path.endswith("/") and rel.startswith(path))
    glob = row.get("glob")
    return isinstance(glob, str) and fnmatch.fnmatchcase(rel, glob)


def _row_stem(row: dict) -> str:
    """The script stem a listed test must mention; empty for glob rows."""
    path = row.get("path")
    if not isinstance(path, str):
        return ""
    if path.endswith("/"):
        return Path(path.rstrip("/")).name
    return Path(path).stem


def _nonempty(value: object) -> bool:
    """True for a non-blank string."""
    return isinstance(value, str) and bool(value.strip())


def _row_field_problems(label: str, row: dict, repo_root: Path) -> list[str]:
    """Validate one row's own fields (enums, conditionals, listed tests)."""
    problems: list[str] = []
    has_path, has_glob = "path" in row, "glob" in row
    if has_path == has_glob:
        problems.append(f"{label}: needs exactly one of path or glob")
    if row.get("run_status") not in RUN_STATUSES:
        problems.append(f"{label}: invalid run_status {row.get('run_status')!r}")
    if row.get("disposition") not in DISPOSITIONS:
        problems.append(f"{label}: invalid disposition {row.get('disposition')!r}")
    if row.get("run_status") == "scheduled" and not _nonempty(row.get("trigger")):
        problems.append(f"{label}: scheduled row has no trigger")
    if row.get("disposition") == "port" and not _nonempty(row.get("target")):
        problems.append(f"{label}: port row has no target")
    needs_reason = row.get("run_status") == "dead" or row.get("disposition") == "delete"
    if needs_reason and not _nonempty(row.get("reason")):
        problems.append(f"{label}: dead or delete row has no reason")
    tests = row.get("tests", [])
    if not isinstance(tests, list):
        return [*problems, f"{label}: tests must be a list"]
    stem = _row_stem(row)
    for test_rel in tests:
        test_path = repo_root / str(test_rel)
        if not test_path.is_file():
            problems.append(f"{label}: listed test {test_rel} does not exist")
        elif stem and stem not in test_path.read_text(encoding="utf-8", errors="replace"):
            problems.append(f"{label}: listed test {test_rel} does not mention {stem!r}")
    return problems


def ledger_problems(rows: list, files: list[str], repo_root: Path = REPO_ROOT) -> list[str]:
    """Return every problem found between ``rows`` and the swept ``files`` (empty means honest)."""
    problems: list[str] = []
    if not rows:
        problems.append("ledger has no rows")
    if not files:
        problems.append("sweep is empty")
    dict_rows: list[dict] = []
    for index, row in enumerate(rows):
        label = f"row {index} ({_row_key(row) or '?'})"
        if not isinstance(row, dict):
            problems.append(f"{label}: not a mapping")
            continue
        dict_rows.append(row)
        problems.extend(_row_field_problems(label, row, repo_root))
    keys = [_row_key(row) for row in rows]
    for left, right in zip(keys, keys[1:], strict=False):
        if left > right:
            problems.append(f"rows not sorted: {left!r} comes before {right!r}")
    for rel in files:
        owners = [_row_key(row) for row in dict_rows if _row_matches(row, rel)]
        if not owners:
            problems.append(f"missing: {rel} matches no ledger row")
        elif len(owners) > 1:
            problems.append(f"collision: {rel} matched by rows {owners[0]!r} and {owners[1]!r}")
    for row in dict_rows:
        if not any(_row_matches(row, rel) for rel in files):
            problems.append(f"phantom: row {_row_key(row)!r} matches no file")
    return problems


def sweep_problems(files: list[str], anchors: tuple[str, ...] = ANCHORS) -> list[str]:
    """Problems with the sweep itself: empty, or missing a known anchor."""
    problems = ["sweep is empty"] if not files else []
    problems.extend(f"sweep misses anchor {anchor}" for anchor in anchors if anchor not in files)
    return problems


def load_ledger() -> dict:
    """Read the committed ledger (YAML safe-load only)."""
    return yaml.safe_load(LEDGER_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Tests on the real ledger
# ---------------------------------------------------------------------------


def test_ledger_has_no_problems():
    """The real ledger over the real sweep is honest, and the sweep is big enough to matter."""
    files = sweep_files(REPO_ROOT)
    data = load_ledger()
    problems = ledger_problems(data["rows"], files) + sweep_problems(files)
    assert len(files) >= MIN_SWEPT_FILES, f"sweep found only {len(files)} files"
    assert problems == [], (
        "script ledger is out of step with the filesystem:\n  "
        + "\n  ".join(problems)
        + "\nRemedy: add, fix or remove the row in tests/ports/PORT_LEDGER.yaml."
    )


def test_ledger_schema_and_size():
    """The ledger declares schema 1 and holds at least the seeded number of rows."""
    data = load_ledger()
    assert data["schema"] == 1
    assert len(data["rows"]) >= MIN_LEDGER_ROWS


def test_sweep_contains_the_anchors():
    """The scheduled entry point, shared normaliser, CI gate and workflow are each covered once."""
    files = sweep_files(REPO_ROOT)
    rows = load_ledger()["rows"]
    for anchor in ANCHORS:
        assert anchor in files, f"sweep lost the anchor {anchor}"
        owners = [r for r in rows if _row_matches(r, anchor)]
        assert len(owners) == 1, f"{anchor} must match exactly one row, got {len(owners)}"


def test_conflict_rows_cite_requirements():
    """Rows where REQUIREMENTS.md overrides ARCHITECTURE.md section 10 name the winner."""
    rows = {_row_key(r): r for r in load_ledger()["rows"]}
    assert len(REQUIREMENTS_OVERRIDES) == len(set(REQUIREMENTS_OVERRIDES))
    for path in REQUIREMENTS_OVERRIDES:
        assert path in rows, f"no ledger row for {path}"
        assert "REQUIREMENTS.md" in rows[path].get("reason", ""), (
            f"{path}: reason must say REQUIREMENTS.md wins over ARCHITECTURE.md section 10"
        )


def test_sweep_is_stable_between_runs():
    """Sweeping twice gives the same list, so the test reads files and holds no state."""
    first = sweep_files(REPO_ROOT)
    second = sweep_files(REPO_ROOT)
    assert first == second
    assert first == sorted(first)


# ---------------------------------------------------------------------------
# Guard the guard: the sweep
# ---------------------------------------------------------------------------


def test_sweep_excludes_noise_and_filters_workflows(tmp_path):
    """Noise files drop out; workflows count only when they mention tools/ and are not ci.yml."""
    for rel, text in {
        "tools/a.py": "x",
        "tools/sub/b.md": "x",
        "tools/__pycache__/a.cpython-311.pyc": "x",
        "tools/stale.pyc": "x",
        "tools/.DS_Store": "x",
        "automation/run.sh": "x",
        ".github/workflows/ci.yml": "run: python tools/x.py",
        ".github/workflows/daily.yml": "run: python tools/y.py",
        ".github/workflows/other.yml": "run: echo hi",
    }.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    assert sweep_files(tmp_path) == [
        ".github/workflows/daily.yml",
        "automation/run.sh",
        "tools/a.py",
        "tools/sub/b.md",
    ]
    assert sweep_files(tmp_path / "nothing-here") == []


def test_sweep_drops_git_ignored_files_but_keeps_tracked_ones(tmp_path):
    """An ignored scratch file is not swept; a tracked file that matches the ignore rule stays."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text("scratch.txt\n", encoding="utf-8")
    (tmp_path / "tools").mkdir()
    for name in ("keep.py", "scratch.txt", "tracked-but-matches.txt"):
        (tmp_path / "tools" / name).write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "-f", "tools/tracked-but-matches.txt"], cwd=tmp_path, check=True)
    swept = sweep_files(tmp_path)
    assert "tools/scratch.txt" not in swept
    assert swept == ["tools/keep.py", "tools/tracked-but-matches.txt"]


# ---------------------------------------------------------------------------
# Guard the guard: the detector, over in-memory fixtures
# ---------------------------------------------------------------------------

_BASE_FILES = [
    "automation/run.sh",
    "tools/sub/c.md",
    "tools/zzscript.py",
    "tools/zzdead.py",
]
_BASE_ROWS: list[dict] = [
    {
        "path": "automation/run.sh",
        "run_status": "by_hand",
        "disposition": "keep_until_retire",
    },
    {"path": "tools/sub/", "run_status": "by_hand", "disposition": "keep_until_retire"},
    {
        "path": "tools/zzdead.py",
        "run_status": "dead",
        "disposition": "delete",
        "reason": "spike",
    },
    {
        "path": "tools/zzscript.py",
        "run_status": "scheduled",
        "trigger": "ci",
        "disposition": "port",
        "target": "TBD:Phase 1",
        "tests": ["tests/ports/test_script_ledger.py"],
    },
]


def _drop_row(rows: list[dict], files: list[str]) -> tuple[list[dict], list[str]]:
    return [r for r in rows if r["path"] != "tools/zzscript.py"], files


def _phantom_row(rows: list[dict], files: list[str]) -> tuple[list[dict], list[str]]:
    extra = {
        "path": "tools/zzghost.py",
        "run_status": "by_hand",
        "disposition": "keep_until_retire",
    }
    return sorted([*rows, extra], key=_row_key), files


def _collision(rows: list[dict], files: list[str]) -> tuple[list[dict], list[str]]:
    extra = {"path": "tools/sub/c.md", "run_status": "by_hand", "disposition": "keep_until_retire"}
    return sorted([*rows, extra], key=_row_key), files


def _bad_enum(rows: list[dict], files: list[str]) -> tuple[list[dict], list[str]]:
    rows[0]["run_status"] = "sometimes"
    rows[1]["disposition"] = "archive"
    return rows, files


def _unsorted(rows: list[dict], files: list[str]) -> tuple[list[dict], list[str]]:
    return list(reversed(rows)), files


def _empty_ledger(rows: list[dict], files: list[str]) -> tuple[list[dict], list[str]]:
    return [], files


def _empty_sweep(rows: list[dict], files: list[str]) -> tuple[list[dict], list[str]]:
    return rows, []


def _scheduled_no_trigger(rows: list[dict], files: list[str]) -> tuple[list[dict], list[str]]:
    del rows[3]["trigger"]
    return rows, files


def _port_no_target(rows: list[dict], files: list[str]) -> tuple[list[dict], list[str]]:
    del rows[3]["target"]
    return rows, files


def _delete_no_reason(rows: list[dict], files: list[str]) -> tuple[list[dict], list[str]]:
    del rows[2]["reason"]
    return rows, files


def _missing_test(rows: list[dict], files: list[str]) -> tuple[list[dict], list[str]]:
    rows[3]["tests"] = ["tests/ports/does_not_exist.py"]
    return rows, files


def _test_without_stem(rows: list[dict], files: list[str]) -> tuple[list[dict], list[str]]:
    rows[3]["tests"] = ["tests/ports/__init__.py"]
    return rows, files


def _both_path_and_glob(rows: list[dict], files: list[str]) -> tuple[list[dict], list[str]]:
    rows[0]["glob"] = "automation/*"
    return rows, files


def _glob_row(rows: list[dict], files: list[str]) -> tuple[list[dict], list[str]]:
    rows[1] = {
        "glob": "tools/sub/*.md",
        "run_status": "by_hand",
        "disposition": "delete",
        "reason": "x",
    }
    return sorted(rows, key=_row_key), files


_Mutation = Callable[[list[dict], list[str]], tuple[list[dict], list[str]]]
_GUARD_CASES: list[tuple[str, _Mutation, str]] = [
    ("one-row-removed", _drop_row, "missing: tools/zzscript.py"),
    ("phantom-row", _phantom_row, "phantom: row 'tools/zzghost.py'"),
    ("file-covered-twice", _collision, "collision: tools/sub/c.md"),
    ("invalid-run-status", _bad_enum, "invalid run_status 'sometimes'"),
    ("invalid-disposition", _bad_enum, "invalid disposition 'archive'"),
    ("unsorted-pair", _unsorted, "rows not sorted"),
    ("empty-ledger", _empty_ledger, "ledger has no rows"),
    ("empty-sweep", _empty_sweep, "sweep is empty"),
    ("scheduled-without-trigger", _scheduled_no_trigger, "scheduled row has no trigger"),
    ("port-without-target", _port_no_target, "port row has no target"),
    ("delete-without-reason", _delete_no_reason, "dead or delete row has no reason"),
    ("listed-test-missing", _missing_test, "does not exist"),
    ("listed-test-lacks-stem", _test_without_stem, "does not mention 'zzscript'"),
    ("path-and-glob", _both_path_and_glob, "needs exactly one of path or glob"),
]


def test_unmutated_fixture_is_honest():
    """The in-memory baseline yields no problems, so every guard case below is a real signal."""
    assert ledger_problems(copy.deepcopy(_BASE_ROWS), list(_BASE_FILES)) == []
    assert ledger_problems(*_glob_row(copy.deepcopy(_BASE_ROWS), list(_BASE_FILES))) == []


@pytest.mark.parametrize(
    ("case", "mutate", "expected"), _GUARD_CASES, ids=[c[0] for c in _GUARD_CASES]
)
def test_guard_cases_are_detected(case, mutate, expected):
    """Each single mutation of an honest ledger yields its specific problem text."""
    rows, files = mutate(copy.deepcopy(_BASE_ROWS), list(_BASE_FILES))
    problems = ledger_problems(rows, files)
    assert any(expected in problem for problem in problems), f"{case}: got {problems}"
    assert problems != []


def test_sweep_problems_flag_missing_anchors_and_empty_sweeps():
    """A sweep that lost an anchor or found nothing fails, however well the rows match."""
    full = list(ANCHORS)
    assert sweep_problems(full) == []
    assert sweep_problems(full[1:]) == [f"sweep misses anchor {ANCHORS[0]}"]
    assert "sweep is empty" in sweep_problems([])
