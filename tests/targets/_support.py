"""Support code for the v2.0 mapping tables (Phase 11 Map, MAP-03, D-08).

Each ``tables/phase_NN_name.yaml`` file is pure data: input-to-output rows for a
behaviour a later v2.0 phase will build. ``test_mapping_tables.py`` turns every
row into one test item. While a table says ``pending: true`` its rows carry
``v2_pending`` and ``xfail(strict=True, raises=NotBuilt, reason="v2.0 Phase N")``:

* the target does not exist yet, so ``load_target`` raises ``NotBuilt`` and the
  item is reported XFAIL;
* if a row starts passing before its phase flips the table to ``pending: false``,
  strict xfail turns the run red (XPASS(strict)), so pending behaviour cannot go
  green by accident;
* any exception other than ``NotBuilt`` (a typo in a row, a broken import inside
  a module that does exist) is a real failure, never "pending".

A phase turns its rows green by setting ``pending: false`` in its own table,
which drops both marks for that phase only.
"""

from __future__ import annotations

import importlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import yaml

TABLES_DIR = Path(__file__).resolve().parent / "tables"

PHASE_RANGE = range(14, 22)

TARGET_RE = re.compile(r"^career_os(\.[a-z_][a-z0-9_]*)+:[A-Za-z_][A-Za-z0-9_]*$")
ROW_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
STEM_RE = re.compile(r"^phase_(\d{2})_([a-z][a-z0-9_]*)$")

HEADER_KEYS = frozenset(
    {"phase", "name", "title", "status", "pending", "sources", "tables", "pending_decision"}
)
REQUIRED_HEADER_KEYS = ("phase", "name", "title", "status", "pending", "sources", "tables")
ROW_KEYS = frozenset({"id", "input", "expect"})
TABLE_KEYS = frozenset({"target", "rows"})


class NotBuilt(Exception):
    """The target module or attribute does not exist yet."""


class TableError(Exception):
    """One or more mapping tables are structurally malformed."""


def load_target(spec: str) -> Any:
    """Resolve ``"dotted.module:attr"`` or raise ``NotBuilt`` if the target is missing.

    Only a missing target module (or a missing attribute on an existing module)
    reads as pending. A ``ModuleNotFoundError`` raised from inside an existing
    module, and every other ``ImportError``, propagate unchanged so a broken
    import in built code fails loudly instead of hiding as pending work.
    """
    module_name, sep, attr = spec.partition(":")
    if not sep or not module_name or not attr:
        raise ValueError(f"target spec must look like 'dotted.module:attr', got {spec!r}")
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        missing = exc.name or ""
        if missing and (module_name == missing or module_name.startswith(missing + ".")):
            raise NotBuilt(f"{module_name} does not exist yet") from exc
        raise
    try:
        return getattr(module, attr)
    except AttributeError as exc:
        raise NotBuilt(f"{module_name}:{attr} does not exist yet") from exc


@dataclass(frozen=True)
class Table:
    """One parsed ``phase_NN_name.yaml`` file."""

    stem: str
    raw: Mapping[str, Any] = field(default_factory=dict)

    @property
    def phase(self) -> Any:
        """The phase number declared in the file header."""
        return self.raw.get("phase")

    @property
    def name(self) -> Any:
        """The phase name declared in the file header."""
        return self.raw.get("name")

    @property
    def pending(self) -> Any:
        """True while the phase has not built its behaviour yet."""
        return self.raw.get("pending")

    @property
    def tables(self) -> Mapping[str, Any]:
        """Mapping of table name to ``{"target": spec, "rows": [...]}``."""
        value = self.raw.get("tables")
        return value if isinstance(value, Mapping) else {}

    def row_count(self) -> int:
        """Total rows across every named table in this file."""
        total = 0
        for body in self.tables.values():
            rows = body.get("rows") if isinstance(body, Mapping) else None
            total += len(rows) if isinstance(rows, list) else 0
        return total


def read_table(path: Path) -> Table:
    """Parse one table file with ``yaml.safe_load`` only."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Table(stem=path.stem, raw=data if isinstance(data, Mapping) else {})


def load_tables(directory: Path = TABLES_DIR, *, validate: bool = True) -> list[Table]:
    """Read every ``phase_*.yaml`` in sorted filename order.

    With ``validate`` (the default, used by the engine) a malformed table raises
    ``TableError`` so it is a collection error, on purpose. The inventory passes
    ``validate=False`` so it can report problems as ordinary test failures.
    """
    tables = [read_table(path) for path in sorted(directory.glob("phase_*.yaml"))]
    if validate:
        problems = [p for table in tables for p in table_problems(table, filename_stem=table.stem)]
        if problems:
            raise TableError("\n".join(problems))
    return tables


def build_params(tables: Iterable[Table]) -> list[Any]:
    """One ``pytest.param`` per row, in table-file and YAML order.

    Ids look like ``phase_15_filter::assess_decision::clean-job-admitted``. A
    pending table gets ``v2_pending`` plus a strict xfail pinned to ``NotBuilt``;
    a table with ``pending: false`` gets no marks.
    """
    params: list[Any] = []
    for table in tables:
        marks: list[Any] = []
        if table.pending:
            marks = [
                pytest.mark.v2_pending,
                pytest.mark.xfail(strict=True, raises=NotBuilt, reason=f"v2.0 Phase {table.phase}"),
            ]
        for table_name, body in table.tables.items():
            for row in body["rows"]:
                params.append(
                    pytest.param(
                        table,
                        table_name,
                        row,
                        id=f"{table.stem}::{table_name}::{row['id']}",
                        marks=marks,
                    )
                )
    return params


def project(result: Any, keys: Iterable[str]) -> dict[str, Any]:
    """Read each expected key from a mapping result or an attribute-bearing object.

    A missing key raises (``KeyError`` or ``AttributeError``): once a target
    exists, a result of the wrong shape is a real failure, never a pending one.
    """
    if isinstance(result, Mapping):
        return {key: result[key] for key in keys}
    return {key: getattr(result, key) for key in keys}


def observe_row(spec: str, row: Mapping[str, Any]) -> dict[str, Any]:
    """Call the target with the row's keyword input and project the expected keys."""
    target = load_target(spec)
    result = target(**row["input"])
    return project(result, row["expect"].keys())


def _canonical(value: Any) -> str:
    """Stable text form of a YAML value, for comparing row inputs and outputs."""
    return json.dumps(value, sort_keys=True, default=str)


def _non_string_keys(value: Any) -> list[Any]:
    """Mapping keys that are not strings, anywhere in a YAML value.

    YAML 1.1 reads an unquoted ``on``, ``off``, ``yes`` or ``no`` key as a
    boolean, which silently changes a row's meaning; such keys must be quoted.
    """
    found: list[Any] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                found.append(key)
            found.extend(_non_string_keys(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_non_string_keys(item))
    return found


def table_problems(table: Table, *, filename_stem: str) -> list[str]:
    """Human-readable structural problems in one table; an empty list means well formed."""
    problems: list[str] = []
    where = filename_stem

    stem_match = STEM_RE.match(filename_stem)
    if not stem_match:
        problems.append(f"{where}: filename must be phase_NN_name.yaml")
    raw = table.raw

    unknown = sorted(set(raw) - HEADER_KEYS)
    if unknown:
        problems.append(f"{where}: unexpected header keys {unknown}")
    for key in REQUIRED_HEADER_KEYS:
        if key not in raw:
            problems.append(f"{where}: missing header key {key!r}")

    phase = raw.get("phase")
    if isinstance(phase, bool) or not isinstance(phase, int):
        if "phase" in raw:
            problems.append(f"{where}: phase must be an integer, got {phase!r}")
    else:
        if phase not in PHASE_RANGE:
            problems.append(f"{where}: phase {phase} is outside 14..21")
        if stem_match and int(stem_match.group(1)) != phase:
            problems.append(
                f"{where}: phase {phase} does not match the filename number {stem_match.group(1)}"
            )
    name = raw.get("name")
    if "name" in raw and stem_match and name != stem_match.group(2):
        problems.append(f"{where}: name {name!r} does not match the filename name")

    status = raw.get("status")
    if "status" in raw and not (isinstance(status, str) and status.startswith("PROVISIONAL")):
        problems.append(f"{where}: status must be a string starting with 'PROVISIONAL'")
    if "title" in raw and not (isinstance(raw["title"], str) and raw["title"].strip()):
        problems.append(f"{where}: title must be a non-empty string")
    if "pending" in raw and not isinstance(raw["pending"], bool):
        problems.append(f"{where}: pending must be a boolean")
    sources = raw.get("sources")
    if "sources" in raw and not (
        isinstance(sources, list) and sources and all(isinstance(s, str) and s for s in sources)
    ):
        problems.append(f"{where}: sources must be a non-empty list of strings")
    if "pending_decision" in raw:
        decisions = raw["pending_decision"]
        if not (isinstance(decisions, list) and all(isinstance(d, str) and d for d in decisions)):
            problems.append(f"{where}: pending_decision must be a list of strings")

    tables = raw.get("tables")
    if "tables" in raw and not (isinstance(tables, Mapping) and tables):
        problems.append(f"{where}: tables must be a non-empty mapping")
        return problems
    for table_name, body in (tables or {}).items():
        problems.extend(_table_body_problems(f"{where}::{table_name}", body))
    return problems


def _table_body_problems(where: str, body: Any) -> list[str]:
    """Problems in one named table (target spec and rows)."""
    if not isinstance(body, Mapping):
        return [f"{where}: table must be a mapping with target and rows"]
    problems: list[str] = []
    extra = sorted(set(body) - TABLE_KEYS)
    if extra:
        problems.append(f"{where}: unexpected table keys {extra}")
    target = body.get("target")
    if not (isinstance(target, str) and TARGET_RE.match(target)):
        problems.append(
            f"{where}: target {target!r} is malformed or outside career_os "
            "(expected 'career_os.module:attr')"
        )
    rows = body.get("rows")
    if not isinstance(rows, list) or not rows:
        problems.append(f"{where}: table has no rows")
        return problems

    seen_ids: set[str] = set()
    expect_by_input: dict[str, str] = {}
    for index, row in enumerate(rows):
        label = f"{where}[{index}]"
        if not isinstance(row, Mapping):
            problems.append(f"{label}: row must be a mapping")
            continue
        keys = set(row)
        if keys != ROW_KEYS:
            missing = sorted(ROW_KEYS - keys)
            extra_keys = sorted(keys - ROW_KEYS)
            problems.append(
                f"{label}: row keys must be id, input, expect (missing {missing}, extra {extra_keys})"
            )
        row_id = row.get("id")
        if isinstance(row_id, str) and ROW_ID_RE.match(row_id):
            label = f"{where}[{row_id}]"
            if row_id in seen_ids:
                problems.append(f"{label}: duplicate row id")
            seen_ids.add(row_id)
        else:
            problems.append(f"{label}: id {row_id!r} must match {ROW_ID_RE.pattern}")
        bad_keys = _non_string_keys(row)
        if bad_keys:
            problems.append(
                f"{label}: non-string mapping keys {bad_keys!r} (quote on, off, yes and no keys)"
            )
            continue
        row_input = row.get("input")
        if "input" in row and not isinstance(row_input, Mapping):
            problems.append(f"{label}: input must be a mapping")
        expect = row.get("expect")
        if "expect" in row and not (isinstance(expect, Mapping) and expect):
            problems.append(f"{label}: empty expect (or not a mapping)")
        if isinstance(row_input, Mapping) and isinstance(expect, Mapping):
            key = _canonical(row_input)
            observed = _canonical(expect)
            if key in expect_by_input and expect_by_input[key] != observed:
                problems.append(
                    f"{label}: identical input with a different expect contradicts an earlier row"
                )
            expect_by_input.setdefault(key, observed)
    return problems
