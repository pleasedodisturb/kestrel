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


DIGEST_DATE = "2000-01-03"
DIGEST_TIMESTAMP = "2000-01-03T07:00:00"


@_register(
    "digest",
    ("tools/daily_pipeline.py",),
    (
        _PIN_ENV,
        "PipelineConfig date, timestamp, tracking_dir and digest_path fixed; digest written to a temp dir",
    ),
)
def _digest(case: dict[str, Any]) -> Any:
    """``step_generate_digest`` over synthetic jobs; the Markdown is stored as a JSON string."""
    import copy
    import tempfile

    settings = case["config"]
    with tempfile.TemporaryDirectory() as tmp:
        config = daily_pipeline.PipelineConfig()
        config.date = DIGEST_DATE
        config.timestamp = DIGEST_TIMESTAMP
        config.mode = settings["mode"]
        config.min_score = settings["min_score"]
        config.hours_old = settings["hours_old"]
        config.tracking_dir = Path(tmp)
        config.digest_path = Path(tmp) / f"daily-scan-{DIGEST_DATE}.md"
        markdown = daily_pipeline.step_generate_digest(
            config,
            copy.deepcopy(case["all_scraped"]),
            copy.deepcopy(case["scored"]),
            copy.deepcopy(case["filtered"]),
        )
        written = config.digest_path.read_text()
    return {"file_matches_return": written == markdown, "markdown": markdown}


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
    for number, line in enumerate(text.split("\n"), start=1):
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
        if not isinstance(draft_id, str) or draft_id not in draft_ids:
            problems.append(f"line {number}: unknown draft_id")
        if not isinstance(gate, str) or gate not in GATES:
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
# Family B: scrubbed, output-only samples of the private pipeline's recorded runs
# ---------------------------------------------------------------------------
#
# Kestrel never recomputes these (no HARNESS entry). It checks them by schema,
# invariants, sha256 and PII only; any replay of a port against them runs only
# inside the private pipeline's repository, under the class's replay mode. The
# record contract is the "Family B record contract" section of plan 11-01 and is
# restated in golden/README.md.

FAMILY_B_CLASSES = (
    "private_dedup_verdicts",
    "private_digest",
    "private_eligibility_verdicts",
    "private_scan_arrivals",
    "private_scoring",
)
GATE_CLASS = "gate_verdicts"
PRIVATE_LEDGER_PATH = REPO_ROOT / "tests/ports/PORT_LEDGER_PRIVATE.yaml"

# What a later port is held to when replayed against the unscrubbed private copy.
# A model call made fit_score (and tier, digest membership and order follow from
# it), so scoring and digest are reference only, never an equality target.
FAMILY_B_REPLAY = {
    "private_dedup_verdicts": "exact",
    "private_digest": "reference",
    "private_eligibility_verdicts": "exact",
    "private_scan_arrivals": "shape",
    "private_scoring": "reference",
}
FAMILY_B_MIN_ROWS = {cls: 20 for cls in FAMILY_B_CLASSES} | {"private_digest": 3}
FAMILY_B_MAX_ROWS = 200

_RE_ID = re.compile(r"^[a-z0-9-]{3,40}$")
_RE_COMPANY = re.compile(r"^Company-\d{2,3}$")
_RE_HOME = re.compile(r"^Home-\d{2,3}$")
_RE_URL = re.compile(r"^https://example\.invalid/[a-z0-9-]+$")
_RE_URL_ANY = re.compile(r"https?://[^\s)\]\"'<>]+")
_RE_SOURCE = re.compile(r"^(tier0:)?[a-z][a-z0-9._-]*(:company-\d{2,3})?$")
_RE_REQ = re.compile(r"^Req-\d{2,4}$")
_RE_PERSON = re.compile(r"^Person-\d{2,3}$")
_RE_EMAIL_TOKEN = re.compile(r"^Email-\d{2,3}$")
_RE_ATS_FAMILY = re.compile(r"^[a-z][a-z0-9.]*$")
_RE_SCORER = re.compile(r"^[a-z0-9._-]{2,40}$")
_RE_DAY_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}")
_RE_PRODUCER_ROW = re.compile(r"^P-\d{2,3}$")
_TIERS = ("T1", "T2", "T3", None)
_CONFIG_REASON_WORDS = ("blocked", "dream", "soft_flag")
_FLAG_FIELDS = ("dream_tier", "blocked", "soft_flag", "floored")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_str_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def _matches(pattern: re.Pattern[str]) -> Callable[[Any], bool]:
    return lambda value: isinstance(value, str) and pattern.fullmatch(value) is not None


# Field name -> (check, rule text used in the problem). Fields that are decision
# data (title, location, remote policy, salary band, scores, verdicts) are kept
# verbatim and only type-checked.
_POSTING_FIELD_CHECKS: dict[str, tuple[Callable[[Any], bool], str]] = {
    "title": (lambda v: isinstance(v, str) and v != "", "title is not a non-empty string"),
    "company": (_matches(_RE_COMPANY), "company is not a synthetic token"),
    "location": (lambda v: isinstance(v, str), "location is not a string"),
    "url": (_matches(_RE_URL), "url query or non-synthetic url"),
    "source": (_matches(_RE_SOURCE), "source does not match the synthetic source shape"),
    "remote": (lambda v: isinstance(v, bool), "remote is not a bool"),
    "salary": (lambda v: isinstance(v, str), "salary is not a string"),
    "posted": (
        lambda v: isinstance(v, str) and (v == "" or re.fullmatch(r"\d{4}-\d{2}", v) is not None),
        "posted is not month-level",
    ),
    "age_days": (lambda v: _is_int(v) and v >= 0, "age_days is not a non-negative integer"),
    "offices": (_is_str_list, "offices is not a list of strings"),
    "remote_policy": (lambda v: isinstance(v, str), "remote_policy is not a string"),
    "tags": (_is_str_list, "tags is not a list of strings"),
    "search_keyword": (lambda v: isinstance(v, str), "search_keyword is not a string"),
    "job_id": (_matches(_RE_REQ), "job_id is not a synthetic Req token"),
    "recruiter": (_matches(_RE_PERSON), "recruiter is not a synthetic Person token"),
    "contact": (_matches(_RE_PERSON), "contact is not a synthetic Person token"),
    "email": (_matches(_RE_EMAIL_TOKEN), "email is not a synthetic Email token"),
    "description": (lambda v: v == "", "description is not empty"),
    "api_submittable": (lambda v: isinstance(v, bool), "api_submittable is not a bool"),
    "ats_family": (_matches(_RE_ATS_FAMILY), "ats_family does not match its shape"),
    "geo_class": (lambda v: isinstance(v, str) and v != "", "geo_class is not a non-empty string"),
}
_POSTING_REQUIRED = frozenset({"title", "company", "location", "url", "source", "remote"})
_POSTING_OPTIONAL = frozenset(
    {
        "salary",
        "posted",
        "age_days",
        "offices",
        "remote_policy",
        "tags",
        "search_keyword",
        "job_id",
        "recruiter",
        "contact",
        "email",
        "description",
        "dream_tier",
        "blocked",
        "soft_flag",
        "api_submittable",
        "ats_family",
    }
)

_REASON_FIELD = (_matches(_REASON_CODE), "reason_code does not match the generic code shape")
# Output fields of the per-record classes: name -> (check, rule).
_OUTPUT_FIELD_CHECKS: dict[str, tuple[Callable[[Any], bool], str]] = {
    "duplicate": (lambda v: isinstance(v, bool), "duplicate is not a bool"),
    "kept": (lambda v: v in ("a", "b"), "kept is not a or b"),
    "fuzzy_ratio": (_is_number, "fuzzy_ratio is not a number"),
    "reason_code": _REASON_FIELD,
    "geo_class": _POSTING_FIELD_CHECKS["geo_class"],
    "prefilter_skip": (lambda v: isinstance(v, bool), "prefilter_skip is not a bool"),
    "score_cap": (lambda v: v is None or _is_int(v), "score_cap is not an integer or null"),
    "blocked": (lambda v: isinstance(v, bool), "blocked is not a bool"),
    "soft_flag": (lambda v: isinstance(v, bool), "soft_flag is not a bool"),
    "fit_score": (_is_number, "fit_score is not a number"),
    "tier": (lambda v: v in _TIERS, "tier is not T1, T2, T3 or null"),
    "review_flag": (lambda v: isinstance(v, bool), "review_flag is not a bool"),
    "floored": (lambda v: isinstance(v, bool), "floored is not a bool"),
    "estimated_salary": (lambda v: isinstance(v, str), "estimated_salary is not a string"),
    "effort_flag": (lambda v: isinstance(v, str), "effort_flag is not a string"),
    "prep_level": (_is_int, "prep_level is not an integer"),
    "scorer": (_matches(_RE_SCORER), "scorer does not match its shape"),
}
_DIGEST_ROW_KEYS = ("company", "title", "location", "fit_score", "tier", "effort_flag", "source")
_DIGEST_CONFIG_KEYS = ("mode", "min_score", "hours_old")
_DIGEST_COUNT_KEYS = ("arrived", "scored", "shortlisted")
# Keys that hold a date, by name or by ending. A key that only matches an ending
# is file content, so a problem names the ending and never the key.
_DATE_KEYS = ("month", "posted", "date")
_DATE_KEY_ENDINGS = ("_at", "_date")

# Per class: (input required, input optional, output required, output optional).
FAMILY_B_SHAPES: dict[str, dict[str, Any]] = {
    "private_scan_arrivals": {
        "input": ({"source"}, {"search_keyword"}),
        "output": "posting",
    },
    "private_dedup_verdicts": {
        "input": ({"a", "b"}, set()),
        "output": ({"duplicate"}, {"kept", "fuzzy_ratio", "reason_code"}),
    },
    "private_eligibility_verdicts": {
        "input": "posting",
        "output": (
            {"geo_class"},
            {"prefilter_skip", "score_cap", "blocked", "soft_flag", "reason_code"},
        ),
    },
    "private_scoring": {
        "input": "posting+geo_class",
        "output": (
            {"fit_score"},
            {
                "tier",
                "review_flag",
                "floored",
                "estimated_salary",
                "effort_flag",
                "prep_level",
                "scorer",
                "reason_code",
            },
        ),
    },
    "private_digest": {
        "input": ({"config", "counts"}, set()),
        "output": ({"rows", "footer"}, set()),
    },
}


def _key_problems(
    obj: Any, required: set[str] | frozenset[str], optional: set[str] | frozenset[str], where: str
) -> list[str]:
    """Unknown or missing keys of one object (an unknown key is how free text would slip in).

    An unknown key is content of the file, so it is counted and never named; a
    missing key is one of this module's own names and is shown.
    """
    if not isinstance(obj, dict):
        return [f"{where}: not an object"]
    problems: list[str] = []
    unknown = len(set(obj) - required - optional)
    if unknown:
        problems.append(f"{where}: {unknown} unknown key(s)")
    problems += [f"{where}: missing key {key!r}" for key in sorted(required - set(obj))]
    return problems


def _posting_problems(obj: Any, where: str, *, extra: frozenset[str] = frozenset()) -> list[str]:
    """Check one posting object against the shared Kestrel ScrapedJob / Tier0Job field set."""
    problems = _key_problems(obj, _POSTING_REQUIRED, _POSTING_OPTIONAL | extra, where)
    if not isinstance(obj, dict):
        return problems
    for name, value in sorted(obj.items()):
        if name in _FLAG_FIELDS and name in _POSTING_OPTIONAL:
            if value is True:
                problems.append(f"{where}: config-derived flag {name} is true")
            elif value is not False:
                problems.append(f"{where}: {name} is not a bool")
        elif name in _POSTING_FIELD_CHECKS:
            check, rule = _POSTING_FIELD_CHECKS[name]
            if not check(value):
                problems.append(f"{where}: {rule}")
    offices = obj.get("offices")
    if isinstance(offices, list) and any(isinstance(o, str) and "@" in o for o in offices):
        problems.append(f"{where}: @ sign in offices")
    return problems


def _output_field_problems(obj: dict[str, Any], where: str) -> list[str]:
    problems: list[str] = []
    for name, value in sorted(obj.items()):
        if name in _FLAG_FIELDS:
            if value is True:
                problems.append(f"{where}: config-derived flag {name} is true")
            elif value is not False:
                problems.append(f"{where}: {name} is not a bool")
        elif name in _OUTPUT_FIELD_CHECKS:
            check, rule = _OUTPUT_FIELD_CHECKS[name]
            if not check(value):
                problems.append(f"{where}: {rule}")
        if (
            name == "reason_code"
            and isinstance(value, str)
            and any(word in value for word in _CONFIG_REASON_WORDS)
        ):
            problems.append(f"{where}: config-derived reason code")
    return problems


def _is_home_class(geo_class: Any) -> bool:
    """True when *geo_class* names a home-family verdict, in any letter case.

    The producer (``tools/job_scorer.py::geo_eligibility``) returns ``home_local``
    and ``home_relocate``, never the bare word, so the test is the substring and
    there is no list of values to keep in step with it. Anything that is not a
    string counts as home: a verdict that cannot be read must never switch the
    home rule off.
    """
    return not isinstance(geo_class, str) or "home" in geo_class.casefold()


def _location_tokenised(posting: Any) -> bool:
    return (
        isinstance(posting, dict)
        and isinstance(posting.get("location"), str)
        and _RE_HOME.fullmatch(posting["location"]) is not None
    )


def _offices_tokenised(posting: Any) -> bool:
    """True when *posting* lists no offices, or every office is a ``Home-NN`` token."""
    if not isinstance(posting, dict) or "offices" not in posting:
        return True
    offices = posting["offices"]
    return isinstance(offices, list) and all(_matches(_RE_HOME)(office) for office in offices)


def _home_problems(holder: Any, posting: Any, where: str) -> list[str]:
    """The home-region rule of one record; *holder* is the object that carries ``geo_class``.

    A record of a home-family class may name its home region only as ``Home-NN``
    tokens: in ``location`` and in every element of ``offices``, the two
    location fields a posting may carry. A record that carries no ``geo_class``
    key states no verdict and is outside the rule.
    """
    if not isinstance(holder, dict) or "geo_class" not in holder:
        return []
    geo_class = holder["geo_class"]
    if not _is_home_class(geo_class):
        return []
    why = "is a home-family class" if isinstance(geo_class, str) else "is not a string"
    problems: list[str] = []
    if not _location_tokenised(posting):
        problems.append(f"{where}: home location not tokenised (geo_class {why})")
    if not _offices_tokenised(posting):
        problems.append(f"{where}: home offices not tokenised (geo_class {why})")
    return problems


def _record_problems(cls: str, record: dict[str, Any], where: str) -> list[str]:
    """Per-class input and output problems of one record."""
    shape = FAMILY_B_SHAPES[cls]
    problems: list[str] = []
    rec_in, rec_out = record.get("input"), record.get("output")

    if cls == "private_scan_arrivals":
        problems += _key_problems(rec_in, *shape["input"], f"{where} input")
        if isinstance(rec_in, dict):
            for name in ("source", "search_keyword"):
                if name in rec_in:
                    check, rule = _POSTING_FIELD_CHECKS[name]
                    if not check(rec_in[name]):
                        problems.append(f"{where} input: {rule}")
        problems += _posting_problems(rec_out, f"{where} output")
    elif cls == "private_dedup_verdicts":
        problems += _key_problems(rec_in, *shape["input"], f"{where} input")
        if isinstance(rec_in, dict):
            for side in ("a", "b"):
                if side in rec_in:
                    problems += _posting_problems(rec_in[side], f"{where} input {side}")
        problems += _key_problems(rec_out, *shape["output"], f"{where} output")
        if isinstance(rec_out, dict):
            problems += _output_field_problems(rec_out, f"{where} output")
    elif cls == "private_eligibility_verdicts":
        problems += _posting_problems(rec_in, f"{where} input")
        problems += _key_problems(rec_out, *shape["output"], f"{where} output")
        if isinstance(rec_out, dict):
            problems += _output_field_problems(rec_out, f"{where} output")
        problems += _home_problems(rec_out, rec_in, where)
    elif cls == "private_scoring":
        problems += _posting_problems(rec_in, f"{where} input", extra=frozenset({"geo_class"}))
        problems += _key_problems(rec_out, *shape["output"], f"{where} output")
        if isinstance(rec_out, dict):
            problems += _output_field_problems(rec_out, f"{where} output")
        problems += _home_problems(rec_in, rec_in, where)
    else:  # private_digest
        problems += _key_problems(rec_in, *shape["input"], f"{where} input")
        if isinstance(rec_in, dict):
            problems += _digest_input_problems(rec_in, where)
        problems += _key_problems(rec_out, *shape["output"], f"{where} output")
        if isinstance(rec_out, dict):
            problems += _digest_output_problems(rec_out, where)
    return problems


def _digest_input_problems(rec_in: dict[str, Any], where: str) -> list[str]:
    problems: list[str] = []
    config, counts = rec_in.get("config"), rec_in.get("counts")
    problems += _key_problems(config, set(), set(_DIGEST_CONFIG_KEYS), f"{where} config")
    problems += _key_problems(counts, set(), set(_DIGEST_COUNT_KEYS), f"{where} counts")
    if isinstance(config, dict):
        if "mode" in config and not isinstance(config["mode"], str):
            problems.append(f"{where} config: mode is not a string")
        if "min_score" in config and not _is_number(config["min_score"]):
            problems.append(f"{where} config: min_score is not a number")
        if "hours_old" in config and not _is_int(config["hours_old"]):
            problems.append(f"{where} config: hours_old is not an integer")
    if isinstance(counts, dict):
        # Only the contract's own names: any other key is file content and is
        # already reported, by count, as an unknown key.
        for name in _DIGEST_COUNT_KEYS:
            if name in counts and not (_is_int(counts[name]) and counts[name] >= 0):
                problems.append(f"{where} counts: {name} is not a non-negative integer")
    return problems


def _digest_output_problems(rec_out: dict[str, Any], where: str) -> list[str]:
    problems: list[str] = []
    if rec_out.get("footer") is not None:
        problems.append(f"{where}: footer is not null")
    rows = rec_out.get("rows")
    if not isinstance(rows, list):
        return [*problems, f"{where}: rows is not a list"]
    for index, row in enumerate(rows):
        spot = f"{where} row {index}"
        problems += _key_problems(row, set(_DIGEST_ROW_KEYS), set(), spot)
        if not isinstance(row, dict):
            continue
        if not _matches(_RE_COMPANY)(row.get("company")):
            problems.append(f"{spot}: company is not a synthetic token")
        if not isinstance(row.get("title"), str):
            problems.append(f"{spot}: title is not a string")
        if not isinstance(row.get("location"), str):
            problems.append(f"{spot}: location is not a string")
        if not _is_number(row.get("fit_score")):
            problems.append(f"{spot}: fit_score is not a number")
        if row.get("tier") not in _TIERS:
            problems.append(f"{spot}: tier is not T1, T2, T3 or null")
        if row.get("effort_flag") is not None and not isinstance(row.get("effort_flag"), str):
            problems.append(f"{spot}: effort_flag is not a string or null")
        if not _matches(_RE_SOURCE)(row.get("source")):
            problems.append(f"{spot}: source does not match the synthetic source shape")
    return problems


def _walk(value: Any, key: str | None = None) -> Iterator[tuple[str | None, Any]]:
    """Every (key, value) pair of a parsed record, depth first."""
    yield key, value
    if isinstance(value, dict):
        for child_key, child in value.items():
            yield from _walk(child, child_key)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child, key)


def _invariant_problems(record: Any, where: str) -> list[str]:
    """Whole-record invariants: month-level dates, URL shape, no @."""
    problems: list[str] = []
    for key, value in _walk(record):
        if key is not None and isinstance(value, str | int | float | type(None)):
            dated = key in _DATE_KEYS or key.endswith(_DATE_KEY_ENDINGS)
            if dated and not (
                isinstance(value, str)
                and (re.fullmatch(r"\d{4}-\d{2}", value) or (key == "posted" and value == ""))
            ):
                shown = key if key in _DATE_KEYS else "(a key ending _at or _date)"
                problems.append(f"{where}: date field {shown} is not month-level")
        if isinstance(value, str):
            for match in _RE_URL_ANY.finditer(value):
                if not _RE_URL.fullmatch(match.group(0)):
                    problems.append(f"{where}: url query or non-synthetic url")
    return problems


def private_golden_problems(path: Path, cls: str) -> list[str]:
    """Validate a Family B golden against the record contract; never raises.

    Returns human-readable problems, each naming the line number and the rule.
    An unknown class, a missing file, invalid UTF-8 or a line that is not a JSON
    object is a problem string. Empty means the file may be registered.

    The file is private until it has crossed and a problem is printed to
    terminals, transcripts and CI logs, so no problem repeats a value read from
    the file: not a cell, not a key, and not the row id, whose shape
    (``^[a-z0-9-]{3,40}$``) is loose enough to hold a slug or a key. A row is
    named by its line number, an unknown key is counted, and a rule quotes only
    this module's own names.
    """
    if cls not in FAMILY_B_CLASSES:
        return [f"unknown Family B class {cls!r}"]
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return [f"cannot read {path.name}: {exc.__class__.__name__}"]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return [f"{path.name} is not valid UTF-8"]
    if not text.strip():
        return [f"{path.name} is empty"]

    problems: list[str] = []
    if "@" in text:
        problems.append("@ sign in the file")
    if _RE_DAY_DATE.search(text):
        problems.append("day-level date or timestamp in the file")
    labels = sorted(pii_hits(text))
    if labels:
        problems.append(f"PII scan hit: {labels}")

    records: list[tuple[int, dict[str, Any]]] = []
    for number, line in enumerate(text.split("\n"), start=1):
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
        if line + "\n" != dump_jsonl([record]):
            problems.append(f"line {number}: not the canonical encoding")
        records.append((number, record))

    if len(records) > FAMILY_B_MAX_ROWS:
        problems.append(f"more than {FAMILY_B_MAX_ROWS} rows ({len(records)})")
    if len(records) < FAMILY_B_MIN_ROWS[cls]:
        problems.append(
            f"fewer rows than the class minimum ({len(records)} < {FAMILY_B_MIN_ROWS[cls]})"
        )

    ids: list[str] = []
    seen_pairs: dict[str, int] = {}
    months: set[Any] = set()
    for number, record in records:
        where = f"line {number}"
        problems += _key_problems(
            record, {"id", "month", "scrubbed", "profile_scope", "input", "output"}, set(), where
        )
        rec_id = record.get("id")
        if not (isinstance(rec_id, str) and _RE_ID.fullmatch(rec_id)):
            problems.append(f"{where}: id does not match ^[a-z0-9-]{{3,40}}$")
        else:
            ids.append(rec_id)
        month = record.get("month")
        months.add(month if isinstance(month, str) else None)
        if not (isinstance(month, str) and re.fullmatch(r"\d{4}-\d{2}", month)):
            problems.append(f"{where}: month is not YYYY-MM")
        if record.get("scrubbed") is not True:
            problems.append(f"{where}: scrubbed is not true")
        if record.get("profile_scope") != "maintainer":
            problems.append(f"{where}: profile_scope is not maintainer")
        problems += _record_problems(cls, record, where)
        problems += _invariant_problems(record, where)
        pair = json.dumps(
            [record.get("input"), record.get("output")], sort_keys=True, ensure_ascii=False
        )
        if pair in seen_pairs:
            problems.append(
                f"{where}: duplicate input and output (same as line {seen_pairs[pair]})"
            )
        else:
            seen_pairs[pair] = number

    if len(set(ids)) != len(ids):
        problems.append("duplicate ids")
    if ids != sorted(ids):
        problems.append("rows are not sorted by id")
    if records and len({m for m in months if m is not None}) < 2:
        problems.append("fewer than two months")
    problems += _coverage_problems(cls, [r for _, r in records])
    return problems


def _coverage_problems(cls: str, records: list[dict[str, Any]]) -> list[str]:
    """Per-class coverage invariants: the sample must exercise both sides of its verdict."""
    outputs = [r["output"] for r in records if isinstance(r.get("output"), dict)]
    if cls == "private_dedup_verdicts":
        # Booleans only: any other value is already a problem, and one that
        # cannot be hashed must not turn this validator into a traceback.
        values = {o.get("duplicate") for o in outputs if isinstance(o.get("duplicate"), bool)}
        if not (True in values and False in values):
            return ["coverage: duplicate true and false must both appear"]
    if (
        cls == "private_eligibility_verdicts"
        and len({str(o.get("geo_class")) for o in outputs}) < 2
    ):
        return ["coverage: geo_class needs at least two distinct values"]
    if (
        cls == "private_scoring"
        and len({o.get("tier") for o in outputs if o.get("tier") in _TIERS}) < 2
    ):
        return ["coverage: tier needs at least two distinct values (null counts as one)"]
    return []


class LedgerUnreadable(Exception):
    """The private ledger could not be read; the text is the error's class name only."""


def ledger_row_ids(ledger_path: Path) -> set[str]:
    """Row ids of the private ledger (``rows: [{id: P-01, ...}]``).

    Raises :class:`LedgerUnreadable` when the file cannot be read or parsed. The
    ledger is a private file until it has crossed and a YAML parser error quotes
    the offending line, so the original error is dropped on purpose (``from
    None``) and only its class name is kept. A ledger that parses but holds no
    list of rows has no row ids.
    """
    import yaml

    try:
        data = yaml.safe_load(ledger_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise LedgerUnreadable(type(exc).__name__) from None
    rows = data.get("rows") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return set()
    return {str(row["id"]) for row in rows if isinstance(row, dict) and "id" in row}


def awaiting_entry(cls: str, golden_dir: Path = GOLDEN) -> dict[str, Any]:
    """The MANIFEST entry of a class that waits for the private run (plan 11-05)."""
    base: dict[str, Any] = {
        "golden": None,
        "sha256": None,
        "status": STATUS_AWAITING,
        "producers": {PRIVATE_KEY: None},
        "producer_commit": None,
        "generated": None,
        "pins": [],
    }
    if cls == GATE_CLASS:
        return base | {
            "inputs": "synthetic",
            "input_files": {
                name: sha256_file(golden_dir / name)
                for name in ("gate_drafts.jsonl", "gate_fact_sheet.json")
            },
        }
    if cls in FAMILY_B_CLASSES:
        return base | {
            "inputs": "scrubbed",
            "profile_scope": "maintainer",
            "producer_row": None,
            "replay": FAMILY_B_REPLAY[cls],
        }
    raise ValueError(f"{cls!r} has no private registration")


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


def _class_problems(
    name: str, entry: Any, golden_dir: Path, private_ledger: Path = PRIVATE_LEDGER_PATH
) -> list[str]:
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

    if private and name != GATE_CLASS and name not in FAMILY_B_CLASSES:
        problems.append(
            f"{name}: only gate_verdicts and the Family B classes may name {PRIVATE_KEY!r}"
        )
    if name in FAMILY_B_CLASSES:
        problems += _family_b_problems(name, entry, golden_dir, private, private_ledger)
    return problems


def _family_b_problems(
    name: str, entry: dict[str, Any], golden_dir: Path, private: bool, private_ledger: Path
) -> list[str]:
    """Family B lifecycle rules for one manifest entry."""
    problems: list[str] = []
    if name in HARNESS:
        problems.append(f"{name}: a Family B class must have no HARNESS entry")
    if not private:
        problems.append(f"{name}: producers must be {{{PRIVATE_KEY!r}: ...}}")
    if entry.get("inputs") != "scrubbed":
        problems.append(f"{name}: inputs must be scrubbed")
    if entry.get("profile_scope") != "maintainer":
        problems.append(f"{name}: profile_scope must be maintainer")
    if entry.get("replay") != FAMILY_B_REPLAY[name]:
        problems.append(
            f"{name}: replay mode must be {FAMILY_B_REPLAY[name]!r}, got {entry.get('replay')!r}"
        )
    producers = entry.get("producers") if isinstance(entry.get("producers"), dict) else {}
    if entry.get("status") == STATUS_AWAITING:
        for key in ("golden", "sha256", "producer_commit", "producer_row", "generated"):
            if entry.get(key) is not None:
                problems.append(f"{name}: {key} must be null while awaiting_private_run")
        if producers.get(PRIVATE_KEY) is not None:
            problems.append(f"{name}: the private producer value must be null while awaiting")
    elif entry.get("status") == STATUS_FROZEN:
        row = entry.get("producer_row")
        if not (isinstance(row, str) and _RE_PRODUCER_ROW.fullmatch(row)):
            problems.append(f"{name}: producer_row must match ^P-\\d{{2,3}}$")
        elif private_ledger.is_file():
            try:
                known_rows = ledger_row_ids(private_ledger)
            except LedgerUnreadable as exc:
                problems.append(f"{name}: cannot read {private_ledger.name}: {exc}")
            else:
                if row not in known_rows:
                    problems.append(
                        f"{name}: producer_row {row} is not a row id of {private_ledger.name}"
                    )
        golden = entry.get("golden")
        if isinstance(golden, str) and (golden_dir / golden).is_file():
            problems += [f"{name}: {p}" for p in private_golden_problems(golden_dir / golden, name)]
    return problems


def manifest_pending(
    golden_dir: Path = GOLDEN, *, private_ledger: Path = PRIVATE_LEDGER_PATH
) -> list[str]:
    """Checks that cannot run yet: a frozen Family B producer_row while the ledger is absent.

    Never adds to :func:`manifest_problems`, so the suite is green before plan
    11-05 crosses ``PORT_LEDGER_PRIVATE.yaml``.
    """
    if private_ledger.is_file():
        return []
    manifest = load_manifest(golden_dir / "MANIFEST.json")
    pending = []
    for name in FAMILY_B_CLASSES:
        entry = manifest["classes"].get(name)
        if isinstance(entry, dict) and entry.get("status") == STATUS_FROZEN:
            pending.append(
                f"producer_row pending: {name} {entry.get('producer_row')}: "
                f"{PRIVATE_LEDGER_PATH.name} not crossed yet"
            )
    return pending


def manifest_problems(
    golden_dir: Path = GOLDEN, *, private_ledger: Path = PRIVATE_LEDGER_PATH
) -> list[str]:
    """Human-readable problems with the golden directory and its manifest.

    Empty means: every golden file is listed by exactly one class, exists and
    matches its sha256; every Kestrel producer file still hashes to the recorded
    git blob; the lifecycle rules (frozen vs awaiting) hold; and every Family B
    class is registered. A frozen Family B ``producer_row`` is checked against
    *private_ledger* when that file exists and skipped (see
    :func:`manifest_pending`) while it does not.
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

    for name in FAMILY_B_CLASSES:
        if name not in classes:
            problems.append(f"{name}: Family B class is not listed in the manifest")
    references: Counter[str] = Counter()
    for name, entry in sorted(classes.items()):
        problems += _class_problems(name, entry, golden_dir, private_ledger)
        if isinstance(entry, dict):
            if isinstance(entry.get("golden"), str):
                references[entry["golden"]] += 1
            if isinstance(entry.get("input_files"), dict):
                references.update(list(entry["input_files"]))
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
