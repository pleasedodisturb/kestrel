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
import blocklist  # noqa: E402
import daily_pipeline  # noqa: E402
import germany_jobs  # noqa: E402
import httpx  # noqa: E402
import job_scorer  # noqa: E402
import local_scorer  # noqa: E402
import normalize  # noqa: E402
import scrape_resilient  # noqa: E402
import tier0_ats_poller  # noqa: E402

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
    # split on "\n" only: str.splitlines() would also split inside a string that
    # holds U+2028, which json.dumps(ensure_ascii=False) leaves unescaped.
    for line in path.read_text(encoding="utf-8").split("\n"):
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


# Fictional replacements for company lists that hold real target names in the
# producer files. A synthetic input must not name a real company (D-03), and a
# case can only reach the block, dream and strong branches by naming a list
# member, so the lists are pinned to fictional members for the replay. The list
# values in the producer files are covered by the producer blob in MANIFEST.
PINNED_JOB_SCORER_BLOCKED = ("blockedco", "nogo industries")
PINNED_DREAM_COMPANIES = frozenset({"zephyrx", "aspirational labs"})
PINNED_STRONG_COMPANIES = frozenset({"synthstrong", "plausible works"})


def _is_pinned_env_key(key: str) -> bool:
    return key == "GITHUB_STEP_SUMMARY" or key.startswith("PIPELINE_")


@contextlib.contextmanager
def _patched(target: Any, **attrs: Any) -> Iterator[None]:
    """Set module attributes and put the originals back, whatever happens."""
    saved = {name: getattr(target, name) for name in attrs}
    for name, value in attrs.items():
        setattr(target, name, value)
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(target, name, value)


def _frozen_clock() -> str:
    return FROZEN_NOW


@contextlib.contextmanager
def pinned() -> Iterator[None]:
    """Fix every machine-dependent input, then restore it exactly.

    Pins (each recorded per class in the MANIFEST ``pins`` list):

    * ``batch_probe._CONFIG``: the geo config; ``normalize_title`` and the geo
      gate read it, and it is loaded from the maintainer's gitignored
      ``config/geo.yaml`` at import;
    * ``job_scorer._GEO_PROFILE``: reset to ``None`` so the default profile is
      rebuilt from the pinned config;
    * the blocklist floor: ``blocklist.BLOCKED_COMPANIES``,
      ``SOFT_FLAG_COMPANIES``, ``_BLOCKED_RE`` and ``_SOFT_FLAG_RE`` rebuilt from
      ``FLOOR_BLOCKED`` and ``FLOOR_SOFT_FLAG`` (the embedded fictional floor,
      which is what CI loads because ``config/blocklist.yaml`` is absent there);
    * ``job_scorer.BLOCKED_COMPANIES`` and ``local_scorer.DREAM_COMPANIES`` /
      ``STRONG_COMPANIES``: fictional members (see ``PINNED_*`` above);
    * ``tier0_ats_poller._utcnow_iso``: the clock, fixed at ``FROZEN_NOW``;
    * the environment: ``GITHUB_STEP_SUMMARY`` and every ``PIPELINE_*`` variable
      are removed on entry; anything set inside is cleared and the saved values
      are put back on exit.
    """
    saved_env = {k: v for k, v in os.environ.items() if _is_pinned_env_key(k)}
    for key in saved_env:
        del os.environ[key]
    try:
        with contextlib.ExitStack() as stack:
            stack.enter_context(_patched(batch_probe, _CONFIG=PINNED_GEO_CONFIG))
            stack.enter_context(
                _patched(
                    job_scorer,
                    _GEO_PROFILE=None,
                    BLOCKED_COMPANIES=list(PINNED_JOB_SCORER_BLOCKED),
                )
            )
            stack.enter_context(
                _patched(
                    blocklist,
                    BLOCKED_COMPANIES=list(blocklist.FLOOR_BLOCKED),
                    SOFT_FLAG_COMPANIES=dict(blocklist.FLOOR_SOFT_FLAG),
                    _BLOCKED_RE=blocklist._compile(blocklist.FLOOR_BLOCKED),
                    _SOFT_FLAG_RE=blocklist._compile(list(blocklist.FLOOR_SOFT_FLAG)),
                )
            )
            stack.enter_context(
                _patched(
                    local_scorer,
                    DREAM_COMPANIES=set(PINNED_DREAM_COMPANIES),
                    STRONG_COMPANIES=set(PINNED_STRONG_COMPANIES),
                )
            )
            stack.enter_context(_patched(tier0_ats_poller, _utcnow_iso=_frozen_clock))
            yield
    finally:
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


_PIN_PROFILE = "job_scorer._GEO_PROFILE reset to None (rebuilt from the pinned config)"
_PIN_BLOCKLIST = (
    "blocklist floor: BLOCKED_COMPANIES, SOFT_FLAG_COMPANIES, _BLOCKED_RE, _SOFT_FLAG_RE"
)
_PIN_BLOCKED = "job_scorer.BLOCKED_COMPANIES replaced with fictional members"
_PIN_LOCAL = "local_scorer.DREAM_COMPANIES and STRONG_COMPANIES replaced with fictional members"
_PIN_CLOCK = "tier0_ats_poller._utcnow_iso fixed at FROZEN_NOW"


@_register(
    "eligibility_verdicts",
    ("tools/batch_probe.py", "tools/job_scorer.py", "tools/blocklist.py"),
    (_PIN_CONFIG, _PIN_PROFILE, _PIN_BLOCKLIST, _PIN_BLOCKED, _PIN_ENV),
)
def _eligibility_verdicts(case: dict[str, Any]) -> Any:
    """Geo, pre-filter and blocklist verdicts, dispatched on ``case['op']``."""
    op = case["op"]
    if op == "geo_classify":
        return batch_probe.geo_classify(case["location_text"], case["offices"], case["is_remote"])
    if op == "geo_eligibility":
        return job_scorer.geo_eligibility(
            case["location"],
            case["offices"],
            case["remote"],
            case["title"],
            case["description"],
        )
    if op == "pre_filter_job":
        return list(
            job_scorer.pre_filter_job(
                case["title"], case["company"], case["location"], case["remote"]
            )
        )
    if op == "is_blocked":
        return blocklist.is_blocked(case["company"])
    if op == "soft_flag_reason":
        return blocklist.soft_flag_reason(case["company"])
    raise ValueError(f"eligibility_verdicts: unknown op {op!r}")


@contextlib.contextmanager
def _scratch_scored_path() -> Iterator[None]:
    """Point ``PipelineConfig().scored_path`` at a temp dir for the duration.

    ``daily_pipeline._fallback_score`` writes its result to
    ``tracking/scraped_scored_<date>.json``; a replay must never write into the
    repository's tracking folder, so the config class is swapped for a subclass
    whose scored path lives in a temporary directory.
    """
    import tempfile

    original = daily_pipeline.PipelineConfig
    with tempfile.TemporaryDirectory() as tmp:

        class _ScratchConfig(original):  # type: ignore[valid-type, misc]
            def __init__(self) -> None:
                super().__init__()
                self.scored_path = Path(tmp) / "scraped_scored.json"

        daily_pipeline.PipelineConfig = _ScratchConfig
        try:
            yield
        finally:
            daily_pipeline.PipelineConfig = original


@contextlib.contextmanager
def _case_env(env: dict[str, Any]) -> Iterator[None]:
    """Set the PIPELINE_* variables a case names (``None`` means unset); clear after."""
    for key, value in env.items():
        if not _is_pinned_env_key(key):
            raise ValueError(f"scoring: env key {key!r} is not a pinned PIPELINE_* variable")
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = str(value)
    try:
        yield
    finally:
        for key in env:
            os.environ.pop(key, None)


@_register(
    "scoring",
    ("tools/daily_pipeline.py", "tools/job_scorer.py", "tools/local_scorer.py"),
    (_PIN_ENV, _PIN_BLOCKED, _PIN_LOCAL, _PIN_CONFIG),
)
def _scoring(case: dict[str, Any]) -> Any:
    """Deterministic scoring helpers only; no op reaches an AI provider call."""
    import copy

    op = case["op"]
    if op == "fallback_score":
        with _scratch_scored_path():
            return daily_pipeline._fallback_score(copy.deepcopy(case["jobs"]))
    if op == "effective_scoring_cap":
        with _case_env(case["env"]):
            return daily_pipeline.effective_scoring_cap()
    if op == "source_priority":
        return daily_pipeline._source_priority(case["job"])
    if op == "apply_floors":
        return job_scorer.apply_floors(copy.deepcopy(case["jobs"]))
    if op == "classify_tier":
        return job_scorer.classify_tier(case["job"])
    if op == "is_dream_tier":
        return job_scorer.is_dream_tier(case["company"])
    if op == "is_api_submittable":
        return job_scorer.is_api_submittable(case["job"])
    if op == "score_job_local":
        return local_scorer.score_job_local(copy.deepcopy(case["job"]))
    raise ValueError(f"scoring: unknown op {op!r}")


_SCAN_URLS = {
    "fetch_greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    "fetch_lever": "https://api.lever.co/v0/postings/{slug}?mode=json",
    "fetch_ashby": "https://api.ashbyhq.com/posting-api/job-board/{slug}",
}


def _scan_client(registered_url: str, payload: Any, slug: str) -> httpx.Client:
    """An ``httpx.Client`` that serves *payload* at one URL and refuses every other.

    No request can leave the process: the transport is a ``MockTransport``.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) != registered_url:
            raise AssertionError(
                f"scan_arrivals: unexpected request to {request.url} for case slug {slug!r}; "
                f"only {registered_url} is registered"
            )
        # content= (not json=): json=None would send no body at all, and a null
        # payload is a case worth freezing.
        return httpx.Response(
            200, content=json.dumps(payload), headers={"content-type": "application/json"}
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


@_register(
    "scan_arrivals",
    ("tools/tier0_ats_poller.py", "tools/germany_jobs.py"),
    (_PIN_CLOCK, "transport: httpx.MockTransport refuses every unregistered URL", _PIN_ENV),
)
def _scan_arrivals(case: dict[str, Any]) -> Any:
    """Scan-arrival normalisation over synthetic payloads; no request leaves the process."""
    import dataclasses

    op = case["op"]
    if op in _SCAN_URLS:
        slug = case["slug"]
        registered = case.get("payload_url") or _SCAN_URLS[op].format(slug=slug)
        fetcher = getattr(tier0_ats_poller, op)
        with _scan_client(registered, case["payload"], slug) as client:
            jobs = fetcher(slug, company_key=case["company_key"], client=client)
        return [dataclasses.asdict(job) for job in jobs]
    if op == "parse_arbeitsagentur_rows":
        return germany_jobs._parse_arbeitsagentur_rows(case["rows"])
    if op == "parse_arbeitsagentur_page":
        # The row handling of fetch_arbeitsagentur on one served page: raw rows,
        # then the rows that are objects, then the parse.
        rows = germany_jobs._dict_rows(germany_jobs._raw_rows(case["data"]))
        return germany_jobs._parse_arbeitsagentur_rows(rows)
    raise ValueError(f"scan_arrivals: unknown op {op!r}")


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
