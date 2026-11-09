"""Shared harness for the MAP-02 golden replay (Phase 11, plan 01).

Three things live here so the generator, the tests and later plans share one
implementation (a second copy of any of them is how a golden silently drifts):

* the **replay harness**: ``HARNESS`` maps a golden class to the function that
  produces its output from a case input, ``CLASS_PRODUCERS`` lists the
  ``tools/`` files that produce it, and :func:`pinned` fixes every
  machine-dependent input (geo config, clock, environment) while a producer
  runs;
* the **JSONL / hash helpers** (:func:`load_jsonl`, :func:`dump_jsonl`,
  :func:`git_blob`) that fix the byte encoding of every golden;
* the **manifest checker** (:func:`manifest_problems`) and the PII scan
  (:func:`pii_hits`, delegating to ``scrub_patterns()`` so there is exactly one
  pattern list).

Nothing here makes a network call, reads a database or calls an LLM.
"""

from __future__ import annotations

import contextlib
import functools
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN = Path(__file__).resolve().parent / "golden"
MANIFEST_PATH = GOLDEN / "MANIFEST.json"
FROZEN_NOW = "2000-01-01T00:00:00+00:00"

# conftest.py puts tools/ on sys.path for pytest; the standalone generator needs
# the same, plus the repo root for ``tests.eval.geo.replay``.
for _entry in (REPO_ROOT, REPO_ROOT / "tools"):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))

import batch_probe  # noqa: E402
import normalize  # noqa: E402
import scrape_resilient  # noqa: E402

from tests.eval.geo.replay import scrub_patterns  # noqa: E402

PRIVATE_KEY = "the private pipeline"
STATUS_FROZEN = "frozen"
STATUS_AWAITING = "awaiting_private_run"
INPUTS_VALUES = ("synthetic", "scrubbed")
GATES = ("fact", "voice")

REQUIRED_PATTERN_LABELS = (
    "personal:name-stem",
    "personal:surname",
    "personal:home-city-country",
    "personal:mail-domain",
    "generic:email",
    "tracking:url-query",
)

_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_MONTH = re.compile(r"^\d{4}-\d{2}$")
_REASON_CODE = re.compile(r"^[a-z][a-z0-9_]{2,40}$")
_NON_GOLDEN_FILES = frozenset({"MANIFEST.json", "README.md"})


# ---------------------------------------------------------------------------
# Encoding and hashing
# ---------------------------------------------------------------------------


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL file: UTF-8, one JSON object per non-empty line."""
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def dump_jsonl(rows: list[dict[str, Any]]) -> str:
    """Encode rows as the one canonical golden text.

    Sorted keys, compact separators, UTF-8 (no ASCII escaping), LF endings and
    one trailing newline with no trailing spaces, so the repo's rewriting
    pre-commit hooks (end-of-file-fixer, trailing-whitespace, mixed-line-ending)
    never change a golden's bytes. Goldens are never stored as Markdown.
    """
    return "".join(
        json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in rows
    )


def sha256_bytes(data: bytes) -> str:
    """Hex sha256 of *data*."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    """Hex sha256 of a file's bytes."""
    return sha256_bytes(path.read_bytes())


def git_blob(rel_path: str) -> str:
    """``git hash-object`` of a repo-relative file (works in a shallow CI checkout)."""
    proc = subprocess.run(
        ["git", "hash-object", rel_path],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git hash-object {rel_path} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def git_head() -> str:
    """The current commit (recorded as ``producer_commit``, never checked in CI)."""
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git rev-parse HEAD failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    """Read ``MANIFEST.json``."""
    return json.loads(path.read_text(encoding="utf-8"))


def dump_manifest(manifest: dict[str, Any]) -> str:
    """Encode the manifest: sorted keys, 2-space indent, trailing newline."""
    return json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def current_month() -> str:
    """``YYYY-MM`` of now: the only granularity the manifest records."""
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m")


# ---------------------------------------------------------------------------
# PII scan (one pattern list: tests/eval/geo/replay.py::scrub_patterns)
# ---------------------------------------------------------------------------


def pii_hits(text: str) -> dict[str, list[Any]]:
    """Every scrub pattern that matches *text*, as ``{label: matches}``.

    Raises when a required built-in label is missing, so the gate can never
    shrink silently. Callers print labels only, never the matches.
    """
    patterns = scrub_patterns(REPO_ROOT)
    missing = sorted(set(REQUIRED_PATTERN_LABELS) - set(patterns))
    if missing:
        raise RuntimeError(f"scrub gate degraded: built-in patterns missing: {missing}")
    hits: dict[str, list[Any]] = {}
    for label, pattern in patterns.items():
        found = pattern.findall(text)
        if found:
            hits[label] = found
    return hits


# ---------------------------------------------------------------------------
# Pins: every machine-dependent input fixed while a producer runs
# ---------------------------------------------------------------------------

# Illustrative home region, modelled on tools/tests/test_geo_gate.py and
# config/geo.example.yaml. Never read from any config file: importing tools
# modules loads the maintainer's gitignored config, and a golden that depended
# on it would be red in CI, which holds only the example config.
PINNED_GEO_CONFIG = batch_probe.GeoConfig(
    home_tokens=("ireland", "dublin", "cork", "galway", "limerick"),
    allow_pan_region_remote=True,
    extra_foreign_tokens=(),
)


def _is_pinned_env_key(key: str) -> bool:
    return key == "GITHUB_STEP_SUMMARY" or key.startswith("PIPELINE_")


@contextlib.contextmanager
def pinned() -> Iterator[None]:
    """Fix every machine-dependent input, then restore it exactly.

    Pins: ``batch_probe._CONFIG`` (``normalize_title`` classifies parenthesised
    locations through it) and the environment (``GITHUB_STEP_SUMMARY`` and every
    ``PIPELINE_*`` variable are removed on entry; anything set inside is cleared
    and the saved values are put back on exit).
    """
    saved_env = {k: v for k, v in os.environ.items() if _is_pinned_env_key(k)}
    for key in saved_env:
        del os.environ[key]
    saved_config = batch_probe._CONFIG
    batch_probe._CONFIG = PINNED_GEO_CONFIG
    try:
        yield
    finally:
        batch_probe._CONFIG = saved_config
        for key in [k for k in os.environ if _is_pinned_env_key(k)]:
            del os.environ[key]
        os.environ.update(saved_env)


# ---------------------------------------------------------------------------
# Harness registry
# ---------------------------------------------------------------------------

HARNESS: dict[str, Callable[[dict[str, Any]], Any]] = {}
CLASS_PRODUCERS: dict[str, tuple[str, ...]] = {}
CLASS_PINS: dict[str, tuple[str, ...]] = {}

_PIN_CONFIG = "batch_probe._CONFIG pinned to PINNED_GEO_CONFIG"
_PIN_ENV = "env: GITHUB_STEP_SUMMARY and PIPELINE_* unset"


def _register(
    name: str, producers: tuple[str, ...], pins: tuple[str, ...]
) -> Callable[[Callable[[dict[str, Any]], Any]], Callable[[dict[str, Any]], Any]]:
    """Register a harness function; its result is normalised to JSON-native values."""

    def decorator(fn: Callable[[dict[str, Any]], Any]) -> Callable[[dict[str, Any]], Any]:
        @functools.wraps(fn)
        def wrapper(case_input: dict[str, Any]) -> Any:
            # Round trip so tuples become lists and the output equals what a
            # golden line decodes to.
            return json.loads(json.dumps(fn(case_input), ensure_ascii=False))

        HARNESS[name] = wrapper
        CLASS_PRODUCERS[name] = producers
        CLASS_PINS[name] = pins
        return wrapper

    return decorator


@_register(
    "dedup_verdicts",
    ("tools/normalize.py", "tools/scrape_resilient.py"),
    (_PIN_CONFIG, _PIN_ENV),
)
def _dedup_verdicts(case: dict[str, Any]) -> Any:
    """Dedup and normalisation verdicts, dispatched on ``case['op']``."""
    import dataclasses

    op = case["op"]
    if op == "normalize_company":
        return normalize.normalize_company(case["value"])
    if op == "normalize_title":
        return normalize.normalize_title(case["value"])
    if op == "job_key":
        return list(normalize.job_key(case["company"], case["title"]))
    if op == "fuzzy_ratio":
        return normalize.fuzzy_ratio(case["a"], case["b"])
    if op == "deduplicate":
        jobs = [scrape_resilient.ScrapedJob(**job) for job in case["jobs"]]
        return [dataclasses.asdict(job) for job in scrape_resilient.deduplicate(jobs)]
    raise ValueError(f"dedup_verdicts: unknown op {op!r}")


# ---------------------------------------------------------------------------
# Gate verdict records (A2: produced by the private gates, validated here)
# ---------------------------------------------------------------------------


def _expected_gates(gates: str) -> tuple[list[str], list[str]]:
    """Split a ``gates`` value into (expected gates, problems)."""
    parts = [g.strip() for g in gates.split(",") if g.strip()]
    problems: list[str] = []
    if not parts or any(g not in GATES for g in parts) or len(set(parts)) != len(parts):
        problems.append(f"gates must be a non-empty subset of {list(GATES)}, got {gates!r}")
    return parts, problems


def gate_verdict_problems(path: Path, drafts_path: Path, gates: str = "fact,voice") -> list[str]:
    """Validate a gate-verdict file; independent of the registration lifecycle.

    Every line has exactly ``draft_id``, ``gate`` (fact or voice), ``verdict``
    (pass or fail) and ``reason_code``; every ``draft_id`` exists in the drafts
    file; each ``(draft_id, gate)`` pair appears once and lines are sorted by it;
    the file is non-empty and carries no PII; and the observed pairs equal every
    draft id crossed with the expected gate set (*gates*, default both).
    """
    expected, problems = _expected_gates(gates)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [*problems, f"cannot read {path.name}: {exc.__class__.__name__}"]
    try:
        draft_ids = {row["id"] for row in load_jsonl(drafts_path)}
    except (OSError, ValueError, KeyError, UnicodeDecodeError) as exc:
        return [*problems, f"cannot read drafts {drafts_path.name}: {exc.__class__.__name__}"]

    records: list[tuple[int, dict[str, Any]]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError:
            problems.append(f"line {number}: not valid JSON")
            continue
        if not isinstance(record, dict):
            problems.append(f"line {number}: not a JSON object")
            continue
        records.append((number, record))
    if not records:
        problems.append("file is empty")

    observed: list[tuple[str, str]] = []
    for number, record in records:
        if set(record) != {"draft_id", "gate", "verdict", "reason_code"}:
            problems.append(
                f"line {number}: keys must be exactly draft_id, gate, verdict, reason_code"
            )
            continue
        draft_id, gate = record["draft_id"], record["gate"]
        if draft_id not in draft_ids:
            problems.append(f"line {number}: unknown draft_id")
        if gate not in GATES:
            problems.append(f"line {number}: gate must be fact or voice")
        elif expected and gate not in expected:
            problems.append(f"line {number}: gate {gate} was not run (gates={','.join(expected)})")
        if record["verdict"] not in ("pass", "fail"):
            problems.append(f"line {number}: verdict must be pass or fail")
        code = record["reason_code"]
        if not isinstance(code, str) or not _REASON_CODE.fullmatch(code):
            problems.append(f"line {number}: reason_code does not match the generic code shape")
        if isinstance(draft_id, str) and isinstance(gate, str):
            observed.append((draft_id, gate))

    if len(set(observed)) != len(observed):
        problems.append("a (draft_id, gate) pair appears more than once")
    if observed != sorted(observed):
        problems.append("lines are not sorted by (draft_id, gate)")
    if expected and not any("keys must be" in p for p in problems):
        wanted = {(draft, gate) for draft in draft_ids for gate in expected}
        if set(observed) != wanted:
            missing = len(wanted - set(observed))
            extra = len(set(observed) - wanted)
            problems.append(
                f"observed (draft_id, gate) pairs differ from drafts x gates: "
                f"{missing} missing, {extra} unexpected"
            )
    labels = sorted(pii_hits(text))
    if labels:
        problems.append(f"PII scan hit: {labels}")
    return problems


# ---------------------------------------------------------------------------
# Manifest checker
# ---------------------------------------------------------------------------


def _file_problems(
    name: str, label: str, file_name: Any, sha: Any, golden_dir: Path, *, must_exist: bool = True
) -> list[str]:
    """Existence and sha256 problems for one referenced file."""
    if not isinstance(file_name, str) or not file_name or "/" in file_name:
        return [f"{name}: {label} must be a bare file name, got {file_name!r}"]
    path = golden_dir / file_name
    if not path.is_file():
        return [f"{name}: {label} {file_name} does not exist"] if must_exist else []
    if sha256_file(path) != sha:
        return [f"{name}: sha256 mismatch for {file_name}: the committed bytes changed"]
    return []


def _class_problems(name: str, entry: Any, golden_dir: Path) -> list[str]:
    """Every manifest problem for one class entry."""
    if not isinstance(entry, dict):
        return [f"{name}: entry is not an object"]
    problems: list[str] = []
    status = entry.get("status")
    producers = entry.get("producers")
    private = isinstance(producers, dict) and PRIVATE_KEY in producers
    frozen = status == STATUS_FROZEN

    if status not in (STATUS_FROZEN, STATUS_AWAITING):
        problems.append(f"{name}: status must be frozen or awaiting_private_run, got {status!r}")
    if status == STATUS_AWAITING and not private:
        problems.append(
            f"{name}: only a class whose producer is {PRIVATE_KEY!r} may be awaiting_private_run"
        )
    inputs = entry.get("inputs")
    if inputs not in INPUTS_VALUES:
        problems.append(f"{name}: inputs must be synthetic or scrubbed, got {inputs!r}")
    elif inputs == "scrubbed" and not private:
        problems.append(f"{name}: inputs scrubbed is only for a class produced by {PRIVATE_KEY!r}")
    if not isinstance(producers, dict) or not producers:
        problems.append(f"{name}: producers must be a non-empty object")
        producers = {}

    golden = entry.get("golden")
    if status == STATUS_AWAITING:
        if golden is not None:
            problems.append(f"{name}: golden must be null while awaiting_private_run")
    elif frozen:
        problems += _file_problems(name, "golden", golden, entry.get("sha256"), golden_dir)

    input_files = entry.get("input_files", {})
    if not isinstance(input_files, dict):
        problems.append(f"{name}: input_files must be an object")
        input_files = {}
    for file_name, sha in sorted(input_files.items()):
        problems += _file_problems(name, "input file", file_name, sha, golden_dir)

    for path, blob in sorted(producers.items()):
        if path == PRIVATE_KEY:
            continue
        try:
            actual = git_blob(path)
        except RuntimeError as exc:
            problems.append(f"{name}: producer {path}: {exc}")
            continue
        if actual != blob:
            problems.append(
                f"{name}: producer changed: {path} is {actual}, manifest has {blob}; "
                f"regenerate with python tests/replay/generate_golden.py --class {name} "
                "and explain the change in the PR"
            )

    if frozen:
        commit = entry.get("producer_commit")
        if not isinstance(commit, str) or not _HEX40.fullmatch(commit):
            problems.append(f"{name}: producer_commit must be 40 lowercase hex")
        for path, blob in sorted(producers.items()):
            if not isinstance(blob, str) or not _HEX40.fullmatch(blob):
                problems.append(f"{name}: producer {path} must be 40 lowercase hex")
        generated = entry.get("generated")
        if not isinstance(generated, str) or not _MONTH.fullmatch(generated):
            problems.append(f"{name}: generated must be YYYY-MM")
        if private and producers.get(PRIVATE_KEY) != commit:
            problems.append(f"{name}: the private producer value must equal producer_commit")
    return problems


def manifest_problems(golden_dir: Path = GOLDEN) -> list[str]:
    """Human-readable problems with the golden directory and its manifest.

    Empty means: every golden file is listed by exactly one class, exists and
    matches its sha256; every Kestrel producer file still hashes to the recorded
    git blob; and the lifecycle rules (frozen vs awaiting) hold.
    """
    manifest_path = golden_dir / "MANIFEST.json"
    if not manifest_path.is_file():
        return ["MANIFEST.json is missing"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        return ["MANIFEST.json is not valid JSON"]
    problems: list[str] = []
    if not isinstance(manifest, dict) or manifest.get("schema") != 1:
        return ["MANIFEST.json schema must be 1"]
    classes = manifest.get("classes")
    if not isinstance(classes, dict) or not classes:
        return ["MANIFEST.json lists no classes"]

    references: Counter[str] = Counter()
    for name, entry in sorted(classes.items()):
        problems += _class_problems(name, entry, golden_dir)
        if isinstance(entry, dict):
            if isinstance(entry.get("golden"), str):
                references[entry["golden"]] += 1
            if isinstance(entry.get("input_files"), dict):
                references.update(entry["input_files"])
    for path in sorted(golden_dir.iterdir()):
        if path.name in _NON_GOLDEN_FILES:
            continue
        if not path.is_file():
            problems.append(f"unlisted entry {path.name}: not a file")
        elif references[path.name] == 0:
            problems.append(f"unlisted file {path.name}: no class references it")
    for file_name, count in sorted(references.items()):
        if count > 1:
            problems.append(f"{file_name} is referenced by more than one class")
    return problems


def python_version() -> str:
    """The interpreter version recorded in the manifest."""
    return platform.python_version()
