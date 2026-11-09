"""Boundary validators for artefacts that cross from the private pipeline into Kestrel.

Phase 11 (Map) plan 11-03. Only three private-derived files may enter this public
repository, and each has a contract that is checked here before anything crosses
(``python -m tests.ports.boundary`` over the private export, plan 11-05) and on every
CI run once the files exist (``tests/ports/test_map_artifacts.py``). Placement is the
primary control (decisions D-01..D-05); these validators are the first net and the CI
PII leak check plus gitleaks are the second. Committed text calls the private side
"the private pipeline" or "the private pipeline's repository", never by name or path.

Paths
-----
``VERDICTS_PATH``, ``COUNTS_PATH``, ``PRIVATE_ROWS_PATH`` and ``MANIFEST_PATH`` name the
crossing artefacts. ``require(path)`` returns their UTF-8 text or raises
``ArtifactMissing`` (the strict-xfail marker keys on it). ``find_cut_list(dir_glob)``
returns the single ``.planning/phases/{dir_glob}/*CUT-LIST.md`` file or raises
``CutListMissing``.

Verdict list contract (MAP-07, MAP-08, decisions D-12 and D-13)
---------------------------------------------------------------
One Markdown file with exactly, and nothing else but blank lines:

* the line ``VOCABULARY_LINE``: it starts ``Vocabulary:``, contains ``keep /
  scope-and-plan / park / remove`` and states that D-02's ``kept / trimmed / parked /
  cut`` map to them in that order (open question OQ-8; the rows themselves use only the
  canonical four);
* one line of the shape ``SOURCE_LINE_SHAPE``: it starts ``Source:`` and names ``the
  private pipeline's repository``, a 40-hex commit and the window ``2026-06 to 2026-10``;
* one pipe table with exactly the columns ``id, kind, name, ref, verdict,
  profile_scope, non_technical, count, reason``.

A heading, a prose line, a comment or words added to either header line are content
outside the structure these rules read, so they are problems (counted, never quoted).

Rules: a ``flow`` id matches ``F-NN`` or ``F-NNN`` and a ``feature`` id ``X-NN`` or
``X-NNN``; ids are unique and sorted (all flows before all features, numerically);
``(kind, name)`` is unique; ``verdict`` is one of ``VERDICTS``; ``profile_scope`` is
``specific`` or ``generic``; ``non_technical`` is ``yes``, ``no`` or ``partial``;
``count`` is a non-negative integer (observed runs or uses in the window); ``reason`` is
non-empty and at most 300 characters; a ``remove`` whose only reason is under-use is
rejected (MAP-07); ``ref`` is ``-`` or a ``phase:slug`` pair; every ``REQUIRED_REFS``
entry appears as a ``ref`` so every Cut A and Retire item can cite a verdict.

Arrival counts contract (MAP-04, decision D-09)
-----------------------------------------------
CSV with the exact header ``COUNTS_HEADER``. ``month`` is one of ``WINDOW_MONTHS``;
``source`` is one of ``ALLOWED_SOURCES`` (per-company ATS sources are rolled up to their
family); every count is a non-negative integer; ``(source, month)`` is unique. An absent
row means not recorded and ``0`` means a recorded zero. The funnel need not be monotone
(applications also arrive by hand), so no ordering between stages is asserted.
Definitions: ``arrived`` is postings fetched that month before any filter;
``survived_prefilter`` is arrivals that passed the deterministic prefilter; ``scored``
is arrivals that received a fit score; ``shortlisted`` is scored arrivals at or above
that day's digest threshold; ``applied`` is applications submitted that month whose job
came from that source (assumption A5).

Private ledger rows contract (MAP-01, decision D-05)
----------------------------------------------------
YAML with ``schema: 1`` and ``rows`` sorted by id, and no other top-level key
(``PRIVATE_TOP_KEYS``). Ids match ``P-NN`` and are unique.
Keys: ``id``, ``private`` (true), ``description``, ``run_status``, ``inputs``,
``outputs``, ``disposition`` and, for dead or delete rows, ``reason``. No path key, and
no text cell may hold a path-like token or a script filename. The file's text must be
exactly ``dump_private_rows(data)``: a comment, an anchor, a second key of the same name
(whose first value the loader drops) or a restyled scalar is text the row rules never
see, so anything but the canonical encoding is a problem.

Cut list contract (MAP-09)
--------------------------
A cut list is ``.planning/phases/NN-slug/NN-CUT-LIST.md``. Every item is one line,
``- {item} | verdict: {ID}`` or ``- {item} | verdicts: {ID}, {ID}``. ``cut_list_items``
returns ``(line_no, item, ids)`` in file order; ``uncited_items`` returns one
``(line_no, what, ids)`` entry, in file order, for each item that carries no verdict
clause or an id that is not a known verdict id, and one ``(0, "cut list has no items",
[])`` entry for a list with no items at all. ``what`` is a fixed description, never the
item's text.

Diagnostics never repeat the content they reject
------------------------------------------------
These validators run over private files before they cross, and what they return is
printed by the CLI and by a failing test, so it reaches terminals, agent transcripts,
summaries and CI logs. No string returned by ``verdict_problems``, ``counts_problems``,
``private_rows_problems`` or ``uncited_items``, and nothing the CLI prints about a file's
content, contains a value read from the file being validated: not a cell, not a header
cell, not a YAML key. A problem names the position (row number, and a column or key name
from this module's own constants) and the rule, and quotes only this module's constants
(the expected header, the allowed vocabularies). A row id is shown only after it has
matched the synthetic shape its contract gives it (``F-NN``, ``X-NN``, ``P-NN``);
anything else is named by position, counted, or replaced by ``MALFORMED_ID``. The
parsers (``parse_verdict_list``, ``cut_list_items``) and ``forbidden_hits`` return content
by design and are never printed.

A malformed file is a problem, never an exception
-------------------------------------------------
A traceback, and an exception's own text, can quote the line that caused it. The three
validators and the CLI therefore never raise on a file's content: an unreadable CSV or
YAML comes back as one problem naming the position (where the parser gives one) and the
error's class, and ``_fail_closed`` turns any exception nobody foresaw into one problem
with the class name only. The result is never empty in either case, so a file that
could not be read to the end can never pass.
"""

from __future__ import annotations

import argparse
import csv
import functools
import io
import re
import sys
import unicodedata
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

import yaml

from tests.eval.geo.replay import scrub_patterns

REPO_ROOT = Path(__file__).resolve().parents[2]
VERDICTS_PATH = REPO_ROOT / ".planning/phases/11-map/11-VERDICTS.md"
COUNTS_PATH = REPO_ROOT / ".planning/phases/11-map/11-ARRIVAL-COUNTS.csv"
PRIVATE_ROWS_PATH = REPO_ROOT / "tests/ports/PORT_LEDGER_PRIVATE.yaml"
MANIFEST_PATH = REPO_ROOT / "tests/replay/golden/MANIFEST.json"
PHASES_DIR = REPO_ROOT / ".planning/phases"


class ArtifactMissing(Exception):
    """A crossing artefact does not exist yet (plan 11-05 crosses it)."""


class CutListMissing(Exception):
    """A phase has not written its cut list yet (Cut A, Retire)."""


# ---------------------------------------------------------------------------
# Vocabulary and enumerations
# ---------------------------------------------------------------------------

VERDICTS = ("keep", "scope-and-plan", "park", "remove")
# Documentation only: the file itself must use the canonical four.
D02_ALIASES = {
    "kept": "keep",
    "trimmed": "scope-and-plan",
    "parked": "park",
    "cut": "remove",
}
VERDICT_COLUMNS = (
    "id",
    "kind",
    "name",
    "ref",
    "verdict",
    "profile_scope",
    "non_technical",
    "count",
    "reason",
)
PROFILE_SCOPES = ("specific", "generic")
NON_TECHNICAL = ("yes", "no", "partial")
REQUIRED_REFS = (
    "cut-a:ticktick",
    "cut-a:icalendar",
    "cut-a:worker",
    "cut-a:dashboard",
    "cut-a:bmad",
    "cut-a:workflows",
    "cut-a:release-channels",
    "cut-a:railway",
    "cut-a:web-app",
    "retire:tools",
    "retire:daily-scan-workflow",
    "retire:automation-glue",
    "retire:pushover",
)
MAX_REASON_CHARS = 300
# No line of a crossing artefact comes near this. A longer line is rejected unscanned: the
# forbidden-content patterns include one that is quadratic on a long uninterrupted word.
MAX_LINE_CHARS = 2000

COUNTS_HEADER = (
    "source",
    "month",
    "arrived",
    "survived_prefilter",
    "scored",
    "shortlisted",
    "applied",
)
WINDOW_MONTHS = ("2026-06", "2026-07", "2026-08", "2026-09", "2026-10")
# Equal to FLOOR_SOURCES plus JOBSPY_BOARDS in tools/source_registry.py plus three extras;
# tests/ports/test_boundary_gates.py proves the equality against the registry.
ALLOWED_SOURCES = frozenset(
    {
        "aijobs",
        "arbeitnow",
        "ashby",
        "germantechjobs",
        "greenhouse",
        "himalayas",
        "jobicy",
        "lever",
        "personio",
        "remoteok",
        "remotely.de",
        "remotive",
        "smartrecruiters",
        "startupjobs",
        "weworkremotely",
        "workable",
        "indeed",
        "linkedin",
        "glassdoor",
        "google",
        "zip_recruiter",
        "arbeitsagentur",
        "manual",
        "other",
    }
)

# The header lines of a verdict list. Anything else on them is free text.
VOCABULARY_LINE = (
    "Vocabulary: keep / scope-and-plan / park / remove "
    "(D-02's kept / trimmed / parked / cut map to these in that order)"
)
SOURCE_LINE_SHAPE = (
    "Source: the private pipeline's repository, commit <40 lowercase hex>, "
    "window 2026-06 to 2026-10"
)
_SOURCE_LINE = re.compile(
    r"Source: the private pipeline's repository, commit [0-9a-f]{40}, window 2026-06 to 2026-10"
)

# The only keys the private ledger may carry at its top level.
PRIVATE_TOP_KEYS = ("schema", "rows")
PRIVATE_RUN_STATUSES = ("scheduled", "by_hand", "dead")
PRIVATE_DISPOSITIONS = ("port", "keep_until_retire", "delete")
_PRIVATE_REQUIRED_KEYS = frozenset(
    {"id", "private", "description", "run_status", "inputs", "outputs", "disposition"}
)
_PRIVATE_ALLOWED_KEYS = _PRIVATE_REQUIRED_KEYS | {"reason"}
# Keys the contract forbids by name. A problem may name these; any other unexpected key
# is content of the file and is only counted.
_PRIVATE_NAMED_KEYS = ("path", "glob")
_PRIVATE_TEXT_KEYS = ("description", "inputs", "outputs", "reason")

# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------


def require(path: Path) -> str:
    """Return the UTF-8 text of a crossing artefact, or raise ArtifactMissing."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        shown = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
        raise ArtifactMissing(f"{shown} does not exist yet") from exc


def find_cut_list(dir_glob: str) -> Path:
    """Return the single ``.planning/phases/{dir_glob}/*CUT-LIST.md`` file.

    Raises CutListMissing when none exists yet and ValueError when several do, because a
    second cut list is an ambiguity that must fail loudly rather than hide as pending.
    """
    found = sorted(PHASES_DIR.glob(f"{dir_glob}/*CUT-LIST.md"))
    if not found:
        raise CutListMissing(f"no cut list matches .planning/phases/{dir_glob}/*CUT-LIST.md")
    if len(found) > 1:
        raise ValueError(f"more than one cut list matches {dir_glob}: {[str(p) for p in found]}")
    return found[0]


# ---------------------------------------------------------------------------
# Fail closed: a file's content never becomes a traceback
# ---------------------------------------------------------------------------

_UNFORESEEN = "could not be validated ({error}); the file is rejected"


def _fail_closed(validator: Callable[..., list[str]]) -> Callable[..., list[str]]:
    """Turn any exception a file provokes in *validator* into one problem string.

    Only the exception's class name is kept: its text, and the traceback it would print,
    can quote the file. The result is never empty, so a file the validator could not
    finish reading is rejected.
    """

    @functools.wraps(validator)
    def guarded(*args: object, **kwargs: object) -> list[str]:
        try:
            return validator(*args, **kwargs)
        except Exception as exc:  # any class: see the docstring
            return [_UNFORESEEN.format(error=type(exc).__name__)]

    return guarded


# ---------------------------------------------------------------------------
# Forbidden content (MAP-08, first net)
# ---------------------------------------------------------------------------

_MONTHS = (
    "january|february|march|april|may|june|july|august|september|october|november|december"
    "|jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec"
)
_CONTROL_CHARS = re.compile("[​-‏⁠﻿‪-‮⁦-⁩]")
_EXTRA_PATTERNS: dict[str, re.Pattern[str]] = {
    "iso-day-date": re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    "text-day-date": re.compile(
        rf"\b(?:{_MONTHS})\.?\s+\d{{1,2}}\b|\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:{_MONTHS})\b"
    ),
    "any-url": re.compile(r"https?://\S+"),
    "currency-amount": re.compile(r"[$€£]\s?\d|\b\d[\d,.]*\s?(?:usd|eur|gbp)\b"),
    "key-shaped": re.compile(r"\b(?:sk|pk|rk)-[a-z0-9_-]{12,}\b"),
    "home-path": re.compile(r"/users/|/home/|~/"),
    "private-side-path": re.compile(r"private/|retrospective/|\.claude/projects"),
    "quotation-marks": re.compile('["“”„‟«»‘’]'),
}


def forbidden_hits(data: str | bytes) -> dict[str, list[str]]:
    """Return ``{label: sorted matches}`` for everything a crossing file must not contain.

    Bytes are decoded strictly as UTF-8 (a failure is a hit). Zero-width and bidi control
    characters are hits and are then removed so they cannot hide a pattern. The text is
    NFC-normalised and casefolded, then checked against ``scrub_patterns()`` (one PII list,
    never a second copy) plus the additions in ``_EXTRA_PATTERNS``. Empty text is a hit.
    Labels are iterated in sorted order so failure messages are stable.
    """
    if isinstance(data, bytes):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return {"invalid-utf8": ["not valid UTF-8"]}
    else:
        text = data
    if not text.strip():
        return {"empty-text": [""]}
    hits: dict[str, list[str]] = {}
    controls = sorted({f"U+{ord(c):04X}" for c in _CONTROL_CHARS.findall(text)})
    if controls:
        hits["control-character"] = controls
    normalised = unicodedata.normalize("NFC", _CONTROL_CHARS.sub("", text)).casefold()
    patterns = {**scrub_patterns(), **_EXTRA_PATTERNS}
    for label, pattern in patterns.items():
        found = sorted({m.group(0) for m in pattern.finditer(normalised)})
        if found:
            hits[label] = found
    return {label: hits[label] for label in sorted(hits)}


def _over_cap(text: str) -> bool:
    """True when any line of *text* is longer than MAX_LINE_CHARS."""
    return any(len(line) > MAX_LINE_CHARS for line in text.splitlines())


def _hit_problems(text: str) -> list[str]:
    """Format forbidden_hits as problems that never echo the matched text.

    A file with a line over MAX_LINE_CHARS is rejected here, by position, and not scanned.
    """
    long_lines = [
        number
        for number, line in enumerate(text.splitlines(), start=1)
        if len(line) > MAX_LINE_CHARS
    ]
    if long_lines:
        return [
            f"{len(long_lines)} line(s) longer than {MAX_LINE_CHARS} characters "
            f"(first at line {long_lines[0]}); the file was not scanned for forbidden content"
        ]
    return [
        f"forbidden content [{label}]: {len(found)} distinct match(es)"
        for label, found in forbidden_hits(text).items()
    ]


# ---------------------------------------------------------------------------
# Verdict list (MAP-07, MAP-08)
# ---------------------------------------------------------------------------

_SEPARATOR_CELL = re.compile(r"^:?-{3,}:?$")
_FLOW_ID = re.compile(r"^F-\d{2,3}$")
_FEATURE_ID = re.compile(r"^X-\d{2,3}$")
_REF = re.compile(
    r"^(?:-|(?:cut-a|retire|find|filter|scan|score|track|write|connect|apply|install|private)"
    r":[a-z0-9-]+)$"
)
# What a problem shows in place of a cited id that does not have the id shape.
MALFORMED_ID = "<malformed id>"
_UNDER_USE = re.compile(r"^(?:unused|rarely used|low use|under-?used|not used)\.?$", re.IGNORECASE)
# No exported cell carries a path or a script name (export contract, D-05). Applied to the
# free-text cells of the verdict list and of the private ledger rows.
#
# A path is any slash or backslash: that covers POSIX, home-relative, Windows drive and UNC
# forms, and a single absolute segment, where the earlier word/word pattern knew only the
# first. Prose in these cells has no use for either character.
_PATH_LIKE = re.compile(r"[/\\]")
# A filename is a word, a dot and a known file kind. The kinds are listed, not guessed from
# shape, so that prose such as "e.g." or "v2.0" is not mistaken for one.
_SCRIPT_NAME = re.compile(
    r"[\w-]+\.(?:"
    r"py|pyc|ipynb|sh|bash|zsh|rb|pl|go|rs|js|cjs|mjs|jsx|ts|tsx|html?|css|sql|"
    r"ya?ml|json|jsonl|toml|ini|cfg|conf|env|lock|plist|xml|"
    r"csv|tsv|txt|log|md|rst|pdf|docx?|xlsx?|db|sqlite3?"
    r")\b",
    re.IGNORECASE,
)
_VERDICT_TEXT_COLUMNS = ("name", "reason")
_COMMIT = re.compile(r"\b[0-9a-f]{40}\b")


def _split_row(line: str) -> list[str]:
    """Split one pipe-table line into stripped cells."""
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    return [cell.strip() for cell in body.split("|")]


def _table_blocks(text: str) -> list[list[str]]:
    """Group contiguous lines that start with a pipe into tables."""
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith("|"):
            current.append(line)
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def _table_rows(block: list[str]) -> list[list[str]]:
    """Return the body rows of a table block, skipping the header and separator."""
    body = block[1:]
    if body and all(_SEPARATOR_CELL.match(cell) for cell in _split_row(body[0])):
        body = body[1:]
    return [_split_row(line) for line in body]


def parse_verdict_list(text: str) -> list[dict[str, str]]:
    """Return the verdict rows as dicts keyed by the table header (well-formed rows only)."""
    blocks = _table_blocks(text)
    if not blocks:
        return []
    header = _split_row(blocks[0][0])
    return [
        dict(zip(header, cells, strict=True))
        for cells in _table_rows(blocks[0])
        if len(cells) == len(header)
    ]


def _id_sort_key(kind: str, row_id: str) -> tuple[int, int] | None:
    """Sort key (flows first, then numeric) or None when the id is malformed."""
    pattern = _FLOW_ID if kind == "flow" else _FEATURE_ID if kind == "feature" else None
    if pattern is None or not pattern.match(row_id):
        return None
    return (0 if kind == "flow" else 1, int(row_id[2:]))


def _safe_id(value: object, *patterns: re.Pattern[str]) -> str | None:
    """Return *value* when it is an id of one of the contract shapes, else None.

    An id is content of the file being validated. It may be shown in a problem only
    after it has matched (in full) the synthetic shape its contract gives it.
    """
    if isinstance(value, str) and any(pattern.fullmatch(value) for pattern in patterns):
        return value
    return None


def _row_label(index: int, row_id: object, *patterns: re.Pattern[str]) -> str:
    """Name a row by its number, plus its id when the id has its contract shape."""
    shown = _safe_id(row_id, *patterns)
    return f"row {index} ({shown})" if shown else f"row {index}"


def _duplicate_problems(
    what: str, values: Iterable[tuple[int, object]], *patterns: re.Pattern[str]
) -> list[str]:
    """Report every value that occurs in more than one row, by row number.

    The value is shown only when it is an id of one of *patterns*; otherwise the row
    numbers alone identify it. Problems come in the order of each value's first row.
    """
    positions: dict[object, list[int]] = {}
    for index, value in values:
        positions.setdefault(value, []).append(index)
    problems: list[str] = []
    for value, rows in positions.items():
        if len(rows) > 1:
            shown = _safe_id(value, *patterns)
            where = ", ".join(str(index) for index in rows)
            problems.append(f"duplicate {what}{f' {shown}' if shown else ''} in rows {where}")
    return problems


def _verdict_header_problems(text: str) -> list[str]:
    """Check the Vocabulary and Source lines."""
    problems: list[str] = []
    lines = text.splitlines()
    vocab = [line for line in lines if line.startswith("Vocabulary:")]
    if len(vocab) != 1:
        problems.append("needs exactly one line starting 'Vocabulary:'")
    else:
        missing = [
            needle
            for needle in (
                "keep / scope-and-plan / park / remove",
                "D-02",
                "kept / trimmed / parked / cut",
            )
            if needle not in vocab[0]
        ]
        problems.extend(f"Vocabulary line must contain {needle!r}" for needle in missing)
        # Every part is there: then nothing else may be, or the line carries free text.
        if not missing and vocab[0].rstrip() != VOCABULARY_LINE:
            problems.append(f"Vocabulary line must be exactly {VOCABULARY_LINE!r}")
    source = [line for line in lines if line.startswith("Source:")]
    if len(source) != 1:
        problems.append("needs exactly one line starting 'Source:'")
    else:
        parts: list[str] = []
        if "the private pipeline's repository" not in source[0]:
            parts.append("Source line must name the private pipeline's repository")
        if not _COMMIT.search(source[0]):
            parts.append("Source line must carry a 40-hex commit")
        if "2026-06 to 2026-10" not in source[0]:
            parts.append("Source line must state the window 2026-06 to 2026-10")
        problems.extend(parts)
        if not parts and not _SOURCE_LINE.fullmatch(source[0].rstrip()):
            problems.append(f"Source line must be exactly: {SOURCE_LINE_SHAPE}")
    return problems


def _outside_line_problems(text: str) -> list[str]:
    """Count the lines that belong to neither header line nor a table.

    Such a line (a heading, prose, a comment) is content no rule here reads, so it may
    not cross. It is counted and located, never quoted.
    """
    outside = [
        number
        for number, line in enumerate(text.splitlines(), start=1)
        if line.strip()
        and not line.startswith(("Vocabulary:", "Source:"))
        and not line.lstrip().startswith("|")
    ]
    if not outside:
        return []
    return [
        f"{len(outside)} line(s) outside the Vocabulary line, the Source line and the table "
        f"(first at line {outside[0]})"
    ]


def _verdict_row_problems(label: str, row: dict[str, str]) -> list[str]:
    """Validate one verdict row's own cells; a problem names the column, never the cell."""
    problems: list[str] = []
    kind, row_id = row["kind"], row["id"]
    if kind not in ("flow", "feature"):
        problems.append(f"{label}: kind must be flow or feature")
    elif _id_sort_key(kind, row_id) is None:
        # kind is one of the two constants here, so it is safe to show.
        problems.append(f"{label}: id does not match kind {kind}")
    if not row["name"]:
        problems.append(f"{label}: name is empty")
    if not _REF.match(row["ref"]):
        problems.append(f"{label}: ref is not '-' or a phase:slug pair")
    verdict = row["verdict"]
    if verdict in D02_ALIASES:
        problems.append(f"{label}: verdict is a D-02 alias; use {D02_ALIASES[verdict]!r}")
    elif verdict not in VERDICTS:
        problems.append(f"{label}: verdict is not one of {VERDICTS}")
    if row["profile_scope"] not in PROFILE_SCOPES:
        problems.append(f"{label}: profile_scope is not specific or generic")
    if row["non_technical"] not in NON_TECHNICAL:
        problems.append(f"{label}: non_technical is not yes, no or partial")
    if not re.fullmatch(r"\d+", row["count"]):
        problems.append(f"{label}: count is not a non-negative integer")
    reason = row["reason"]
    if not reason:
        problems.append(f"{label}: reason is empty")
    elif len(reason) > MAX_REASON_CHARS:
        problems.append(f"{label}: reason is longer than {MAX_REASON_CHARS} characters")
    if verdict == "remove" and _UNDER_USE.match(reason):
        problems.append(f"{label}: a remove verdict cannot rest on under-use alone (MAP-07)")
    # Export contract: no cell carries a path or a script name. The other cells are held to
    # a vocabulary or a shape; these two are free text, so they get the private ledger's rule.
    for column in _VERDICT_TEXT_COLUMNS:
        if _PATH_LIKE.search(row[column]):
            problems.append(f"{label}: {column} holds a path-like token")
        if _SCRIPT_NAME.search(row[column]):
            problems.append(f"{label}: {column} holds a script filename")
    return problems


@_fail_closed
def verdict_problems(text: str) -> list[str]:
    """Return every problem in a verdict list (empty means it may cross)."""
    problems = _hit_problems(text)
    if _over_cap(text):
        return problems  # rejected by position; no pattern is run over an over-long line
    problems.extend(_verdict_header_problems(text))
    problems.extend(_outside_line_problems(text))
    blocks = _table_blocks(text)
    if not blocks:
        return [*problems, "no table found"]
    if len(blocks) > 1:
        problems.append("more than one table found")
    header = tuple(_split_row(blocks[0][0]))
    if header != VERDICT_COLUMNS:
        return [
            *problems,
            f"table header must be exactly {VERDICT_COLUMNS}, got {len(header)} column(s)",
        ]
    raw_rows = _table_rows(blocks[0])
    if not raw_rows:
        return [*problems, "verdict list has no rows"]
    rows: list[tuple[int, dict[str, str]]] = []
    for index, cells in enumerate(raw_rows, start=1):
        if len(cells) != len(header):
            problems.append(f"row {index}: expected {len(header)} cells, got {len(cells)}")
            continue
        row = dict(zip(header, cells, strict=True))
        rows.append((index, row))
        label = _row_label(index, row["id"], _FLOW_ID, _FEATURE_ID)
        problems.extend(_verdict_row_problems(label, row))
    problems.extend(
        _duplicate_problems("id", [(i, r["id"]) for i, r in rows], _FLOW_ID, _FEATURE_ID)
    )
    problems.extend(
        _duplicate_problems("(kind, name)", [(i, (r["kind"], r["name"])) for i, r in rows])
    )
    keys = [k for k in (_id_sort_key(r["kind"], r["id"]) for _, r in rows) if k is not None]
    if any(left > right for left, right in zip(keys, keys[1:], strict=False)):
        problems.append("ids are not sorted (flows before features, numerically)")
    present = {row["ref"] for _, row in rows}
    problems.extend(f"missing required ref {ref}" for ref in REQUIRED_REFS if ref not in present)
    return problems


# ---------------------------------------------------------------------------
# Arrival counts (MAP-04)
# ---------------------------------------------------------------------------


@_fail_closed
def counts_problems(text: str) -> list[str]:
    """Return every problem in the arrival-counts CSV (empty means it may cross)."""
    problems = _hit_problems(text)
    if _over_cap(text):
        return problems  # rejected by position; no pattern is run over an over-long line
    reader = csv.reader(io.StringIO(text))
    try:
        rows = list(reader)
    except csv.Error:
        # An oversized field or a bare carriage return. The error's text is not shown.
        return [*problems, f"not readable as CSV near line {reader.line_num} (csv.Error)"]
    if not rows:
        return [*problems, "counts file has no header"]
    if tuple(rows[0]) != COUNTS_HEADER:
        return [
            *problems,
            f"header must be exactly {COUNTS_HEADER}, got {len(rows[0])} column(s)",
        ]
    body = rows[1:]
    if not body:
        return [*problems, "counts file has no rows"]
    seen: dict[tuple[str, str], int] = {}
    for index, cells in enumerate(body, start=1):
        if len(cells) != len(COUNTS_HEADER):
            problems.append(f"row {index}: expected {len(COUNTS_HEADER)} cells, got {len(cells)}")
            continue
        source, month, *numbers = cells
        if source not in ALLOWED_SOURCES:
            problems.append(f"row {index}: source is not an allowed source family")
        if month not in WINDOW_MONTHS:
            problems.append(f"row {index}: month is not one of {WINDOW_MONTHS}")
        for name, value in zip(COUNTS_HEADER[2:], numbers, strict=True):
            if not re.fullmatch(r"\d+", value):
                problems.append(f"row {index}: {name} is not a non-negative integer")
        first = seen.setdefault((source, month), index)
        if first != index:
            problems.append(f"row {index}: duplicate (source, month) of row {first}")
    return problems


# ---------------------------------------------------------------------------
# Private ledger rows (MAP-01, D-05)
# ---------------------------------------------------------------------------

_PRIVATE_ID = re.compile(r"^P-\d{2}$")


def _private_row_problems(label: str, row: dict) -> list[str]:
    """Validate one anonymised private ledger row.

    A key of the row is content of the file: an unexpected key is named only when it is
    one of ``_PRIVATE_NAMED_KEYS`` and is counted otherwise. A missing key is one of this
    module's own names. No cell is ever shown.
    """
    problems: list[str] = []
    unexpected = set(row) - _PRIVATE_ALLOWED_KEYS
    for key in _PRIVATE_NAMED_KEYS:
        if key in unexpected:
            problems.append(f"{label}: unexpected key {key!r} (rows never carry paths or globs)")
    unnamed = len(unexpected - set(_PRIVATE_NAMED_KEYS))
    if unnamed:
        problems.append(f"{label}: {unnamed} unexpected key(s) (rows never carry paths or globs)")
    for key in sorted(_PRIVATE_REQUIRED_KEYS - set(row)):
        problems.append(f"{label}: missing key {key!r}")
    if row.get("private") is not True:
        problems.append(f"{label}: private must be true")
    if row.get("run_status") not in PRIVATE_RUN_STATUSES:
        allowed = ", ".join(PRIVATE_RUN_STATUSES)
        problems.append(f"{label}: invalid run_status (must be one of {allowed})")
    if row.get("disposition") not in PRIVATE_DISPOSITIONS:
        allowed = ", ".join(PRIVATE_DISPOSITIONS)
        problems.append(f"{label}: invalid disposition (must be one of {allowed})")
    needs_reason = row.get("run_status") == "dead" or row.get("disposition") == "delete"
    reason = row.get("reason")
    # Only text counts as a reason: str(None) is the word "None", which is not one.
    if needs_reason and not (isinstance(reason, str) and reason.strip()):
        problems.append(f"{label}: dead or delete row needs a reason")
    for key in _PRIVATE_TEXT_KEYS:
        if key not in row:
            # An absent required key is reported above; reason may be absent on a live row.
            continue
        value = row[key]
        if not isinstance(value, str) or not value.strip():
            problems.append(f"{label}: {key} must be a non-empty string")
            continue
        if _PATH_LIKE.search(value):
            problems.append(f"{label}: {key} holds a path-like token")
        if _SCRIPT_NAME.search(value):
            problems.append(f"{label}: {key} holds a script filename")
    return problems


def dump_private_rows(data: object) -> str:
    """Return the one encoding a private ledger file may have.

    Block-style YAML with keys in the order given, written by ``yaml.safe_dump``. The
    exporter writes the file with this function and ``private_rows_problems`` rejects
    any other text, so nothing can ride along outside the keys and values.
    """
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def _canonical_problems(data: object, raw: str) -> list[str]:
    """Report text that is not ``dump_private_rows(data)``, by its first differing line."""
    canonical = dump_private_rows(data)
    if raw == canonical:
        return []
    theirs, ours = raw.split("\n"), canonical.split("\n")
    line = next(
        (n for n, (a, b) in enumerate(zip(theirs, ours, strict=False), start=1) if a != b),
        min(len(theirs), len(ours)) + 1,
    )
    return [
        f"line {line}: not the canonical YAML encoding (write it with dump_private_rows; "
        "comments, anchors, duplicate keys and restyled text never cross)"
    ]


@_fail_closed
def private_rows_problems(data: object, raw: str | None = None) -> list[str]:
    """Return every problem in the anonymised private ledger rows.

    ``data`` is the parsed YAML, or the YAML text itself (then it is parsed here and used
    as the raw text). ``raw`` is the original text when ``data`` was parsed by the caller;
    without it the parsed data is re-serialised for the forbidden-content scan. When the
    text is known it must be the canonical encoding of the data.
    """
    if isinstance(data, str):
        raw = data
        try:
            data = yaml.safe_load(data)
        except Exception as exc:
            # Not only YAMLError: a scalar shaped like a date or an integer raises
            # ValueError, a wrong explicit tag AttributeError, deep nesting RecursionError.
            return [*_hit_problems(raw), f"not valid YAML: {type(exc).__name__}"]
    from_text = raw is not None
    if raw is None:
        raw = yaml.safe_dump(data, sort_keys=True, allow_unicode=True)
    problems = _hit_problems(raw)
    if _over_cap(raw):
        return problems  # rejected by position; no pattern is run over an over-long line
    if not isinstance(data, dict):
        return [*problems, "private rows must be a mapping with schema and rows"]
    unexpected = len(set(data) - set(PRIVATE_TOP_KEYS))
    if unexpected:
        allowed = " and ".join(PRIVATE_TOP_KEYS)
        problems.append(f"{unexpected} unexpected top-level key(s) (only {allowed} may appear)")
    if from_text:
        problems.extend(_canonical_problems(data, raw))
    if data.get("schema") != 1:
        problems.append("schema must be 1")
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        return [*problems, "private rows list is empty or missing"]
    placed: list[tuple[int, str]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            problems.append(f"row {index}: not a mapping")
            continue
        row_id = _safe_id(row.get("id"), _PRIVATE_ID)
        if row_id is None:
            problems.append(f"row {index}: id does not match P-NN")
        else:
            placed.append((index, row_id))
        problems.extend(_private_row_problems(_row_label(index, row_id, _PRIVATE_ID), row))
    problems.extend(_duplicate_problems("id", placed, _PRIVATE_ID))
    ids = [row_id for _, row_id in placed]
    if ids != sorted(ids):
        problems.append("rows are not sorted by id")
    return problems


# ---------------------------------------------------------------------------
# Cut lists (MAP-09)
# ---------------------------------------------------------------------------

_VERDICT_CLAUSE = re.compile(r"\|\s*verdicts?:\s*(?P<ids>.*)$", re.IGNORECASE)


def cut_list_items(text: str) -> list[tuple[int, str, list[str]]]:
    """Return ``(line_no, item, ids)`` for every ``- `` item line, in file order."""
    items: list[tuple[int, str, list[str]]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        if not stripped.startswith("- "):
            continue
        body = stripped[2:]
        clause = _VERDICT_CLAUSE.search(body)
        if clause is None:
            items.append((line_no, body.strip(), []))
            continue
        ids = [token for token in re.split(r"[,\s]+", clause.group("ids")) if token]
        items.append((line_no, body[: clause.start()].strip(), ids))
    return items


def uncited_items(text: str, known_ids: Iterable[str]) -> list[tuple[int, str, list[str]]]:
    """Return ``(line_no, what, ids)`` for items citing no verdict id or an unknown one.

    Entries come in file order. ``what`` is one of two fixed descriptions and never the
    item's own text, and ``ids`` keeps each cited id that has the ``F-NN`` or ``X-NN``
    shape and holds ``MALFORMED_ID`` in place of any other token, so a failing assertion
    on the result cannot print the cut list's content. A cut list with no items at all
    yields the single entry ``(0, "cut list has no items", [])`` so an empty list can
    never pass as fully cited.
    """
    known = set(known_ids)
    items = cut_list_items(text)
    if not items:
        return [(0, "cut list has no items", [])]
    found: list[tuple[int, str, list[str]]] = []
    for line_no, _item, ids in items:
        if not ids:
            found.append((line_no, "item cites no verdict id", []))
        elif any(cited not in known for cited in ids):
            shown = [_safe_id(cited, _FLOW_ID, _FEATURE_ID) or MALFORMED_ID for cited in ids]
            found.append((line_no, "item cites an unknown verdict id", shown))
    return found


# ---------------------------------------------------------------------------
# CLI: python -m tests.ports.boundary --verdicts P --counts P --private-rows P
# ---------------------------------------------------------------------------


@_fail_closed
def _check_file(path: Path, kind: str) -> list[str]:
    """Run the validator for ``kind`` over one file and return its problems."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        return [f"cannot read file: {type(exc).__name__}"]
    # Decode here and leave every scan to the validators, which apply the line cap first.
    # Scanning the bytes at this point ran the patterns over a file of any shape.
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return ["forbidden content [invalid-utf8]: file is not valid UTF-8"]
    if kind == "verdicts":
        return verdict_problems(text)
    if kind == "counts":
        return counts_problems(text)
    return private_rows_problems(text)


def main(argv: Sequence[str] | None = None) -> int:
    """Validate crossing artefacts; exit 0 clean, 1 on any problem, 2 on usage error."""
    parser = argparse.ArgumentParser(
        prog="python -m tests.ports.boundary",
        description="Validate artefacts before they cross from the private pipeline.",
    )
    parser.add_argument("--verdicts", type=Path, help="verdict list (Markdown)")
    parser.add_argument("--counts", type=Path, help="arrival counts (CSV)")
    parser.add_argument("--private-rows", type=Path, help="private ledger rows (YAML)")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2
    targets = [
        (args.verdicts, "verdicts"),
        (args.counts, "counts"),
        (args.private_rows, "private-rows"),
    ]
    chosen = [(path, kind) for path, kind in targets if path is not None]
    if not chosen:
        parser.print_usage(sys.stderr)
        return 2
    failed = False
    for path, kind in chosen:
        for problem in _check_file(path, kind):
            print(f"{path}: {problem}")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
