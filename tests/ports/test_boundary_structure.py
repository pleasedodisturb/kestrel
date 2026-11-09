"""Top-level and malformed-input rows for the boundary validators.

Two more ways a private value could get past ``tests/ports/boundary.py`` or out
through its messages, pinned here:

* **content outside the validated structure.** A validator that checks the rows
  it knows and ignores everything around them lets free text cross: a top-level
  YAML key, a YAML comment, a duplicate key whose first value the loader drops, a
  prose line or a heading around the verdict table, words appended to the
  Vocabulary or Source line. The script-name and path checks only look at the
  cells they know, so such text is not even held to them. The CSV was already
  closed (every cell is a vocabulary word or digits, a blank or comment line is a
  row of the wrong width, a byte-order mark is a forbidden character); its rows
  are pinned so it stays closed.
* **malformed input.** A hostile or broken file must come back as a problem
  string, never as an exception: a traceback, and an exception's own text, can
  quote the line that caused it. The inputs below are the ones a fuzz run and a
  reading of the parsers found (an oversized CSV field, a bare carriage return,
  a YAML scalar that looks like a date or an integer and is not one, an explicit
  tag on the wrong scalar, nesting deep enough to exhaust the stack), plus a
  last-resort guard for anything else.

Every row is driven with the five sentinels of ``test_boundary_no_echo``: the
validator must report a problem, the CLI must exit 1 without a traceback, and no
sentinel may appear in a problem or in what the CLI prints.
"""

import subprocess
import sys
from collections.abc import Callable
from typing import Any

import pytest
import yaml

from tests.ports import boundary
from tests.ports.boundary import (
    COUNTS_HEADER,
    counts_problems,
    main,
    private_rows_problems,
    verdict_problems,
)
from tests.ports.test_boundary_gates import (
    _SOURCE,
    _VOCAB,
    _counts_text,
    _private_data,
    _rows,
    _table,
    _verdict_text,
)
from tests.ports.test_boundary_no_echo import _LABELS, _SENTINELS, _leaks

Case = tuple[str, str, Callable[[str], str]]

_VALIDATE: dict[str, Callable[[str], list[str]]] = {
    "verdicts": verdict_problems,
    "counts": counts_problems,
    "private-rows": private_rows_problems,
}


def _canonical(data: Any) -> str:
    """The one encoding a private ledger may have (what ``dump_private_rows`` writes)."""
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def _ledger(**top_level: Any) -> str:
    return _canonical(_private_data() | top_level)


def _ledger_with(old: str, new: str) -> str:
    text = _ledger()
    assert text.count(old) == 1, old
    return text.replace(old, new)


def _described(sentinel: str) -> dict:
    data = _private_data()
    data["rows"][0]["description"] = sentinel
    return data


def _verdict_doc(*, before: str = "", vocab: str = _VOCAB, source: str = _SOURCE) -> str:
    return f"{vocab}\n\n{source}\n\n{before}{_table(_rows())}\n"


# ---------------------------------------------------------------------------
# Content outside the validated structure
# ---------------------------------------------------------------------------

_DESCRIPTION = "  description: nightly scorer\n"

# Open before the fix: each of these is free text the validator did not look at.
_OUTSIDE: list[Case] = [
    ("private-rows", "top-level-key", lambda s: _ledger(notes=s)),
    ("private-rows", "top-level-key-is-the-sentinel", lambda s: _ledger(**{s: "note"})),
    (
        "private-rows",
        "top-level-key-of-another-type",
        lambda s: _canonical(_private_data() | {7: s}),
    ),
    ("private-rows", "two-top-level-keys", lambda s: _ledger(notes=s, more=s)),
    ("private-rows", "comment-first-line", lambda s: f"# {s}\n" + _ledger()),
    ("private-rows", "comment-last-line", lambda s: _ledger() + f"# {s}\n"),
    (
        "private-rows",
        "comment-after-a-value",
        lambda s: _ledger_with("schema: 1\n", f"schema: 1  # {s}\n"),
    ),
    (
        "private-rows",
        "comment-between-rows",
        lambda s: _ledger_with("- id: P-02\n", f"# {s}\n- id: P-02\n"),
    ),
    (
        "private-rows",
        "duplicate-key-hides-the-first-value",
        lambda s: _ledger_with(_DESCRIPTION, f"  description: {s}\n{_DESCRIPTION}"),
    ),
    (
        "private-rows",
        "block-scalar-header-comment",
        lambda s: _ledger_with(_DESCRIPTION, f"  description: | # {s}\n    nightly scorer\n"),
    ),
    (
        "private-rows",
        "anchor-and-alias",
        lambda s: _ledger_with(
            f"{_DESCRIPTION}  run_status: scheduled\n  inputs: scan output\n",
            f"  description: &note {s}\n  run_status: scheduled\n  inputs: *note\n",
        ),
    ),
    ("private-rows", "document-marker", lambda s: "---\n" + _canonical(_described(s))),
    (
        "private-rows",
        "flow-style",
        lambda s: yaml.safe_dump(_described(s), default_flow_style=True),
    ),
    (
        "private-rows",
        "restyled-scalar",
        lambda s: _canonical(_described(s)).replace(f"description: {s}", f"description: '{s}'"),
    ),
    ("verdicts", "prose-first-line", lambda s: f"{s}\n\n" + _verdict_doc()),
    ("verdicts", "heading", lambda s: f"# {s}\n\n" + _verdict_doc()),
    ("verdicts", "prose-before-the-table", lambda s: _verdict_doc(before=f"{s}\n\n")),
    ("verdicts", "prose-after-the-table", lambda s: _verdict_doc() + f"\n{s}\n"),
    ("verdicts", "line-adjoining-the-table", lambda s: _verdict_doc() + f"{s}\n"),
    ("verdicts", "html-comment", lambda s: _verdict_doc() + f"\n<!-- {s} -->\n"),
    ("verdicts", "indented-vocabulary-copy", lambda s: _verdict_doc() + f"\n  Vocabulary: {s}\n"),
    ("verdicts", "vocabulary-tail", lambda s: _verdict_doc(vocab=f"{_VOCAB} {s}")),
    (
        "verdicts",
        "vocabulary-middle",
        lambda s: _verdict_doc(vocab=_VOCAB.replace("remove (", f"remove {s} (")),
    ),
    ("verdicts", "source-tail", lambda s: _verdict_doc(source=f"{_SOURCE} {s}")),
    (
        "verdicts",
        "source-middle",
        lambda s: _verdict_doc(source=_SOURCE.replace(", window", f" {s}, window")),
    ),
]

# Closed before the fix; pinned so they stay closed.
_ALREADY_CLOSED: list[Case] = [
    (
        "verdicts",
        "text-after-the-last-pipe",
        lambda s: _verdict_doc().replace("ran steadily |", f"ran steadily | {s}"),
    ),
    (
        "verdicts",
        "text-before-the-first-pipe",
        lambda s: _verdict_doc().replace("| F-02 |", f"{s} | F-02 |"),
    ),
    ("verdicts", "second-table", lambda s: _verdict_doc() + "\n" + _table([[s] * 9]) + "\n"),
    ("counts", "comment-line", lambda s: _counts_text() + f"# {s}\n"),
    ("counts", "comment-line-of-row-width", lambda s: _counts_text() + f"# {s},,,,,,\n"),
    ("counts", "row-after-a-blank-line", lambda s: _counts_text() + f"\n{s},2026-08,1,1,1,1,1\n"),
    ("counts", "rows-after-two-blank-lines", lambda s: _counts_text() + f"\n\n{s}\n"),
    (
        "counts",
        "quoted-cell-over-two-lines",
        lambda s: _counts_text() + f'"manual\n{s}",2026-08,1,1,1,1,1\n',
    ),
    ("counts", "text-before-the-header", lambda s: f"{s}\n" + _counts_text()),
    ("private-rows", "second-document", lambda s: _ledger() + f"---\nnotes: {s}\n"),
    (
        "private-rows",
        "unknown-tag",
        lambda s: _ledger_with("schema: 1\n", "schema: !custom 1\n") + f"notes: {s}\n",
    ),
]

# ---------------------------------------------------------------------------
# Malformed input: each of these raised out of a validator before the fix
# ---------------------------------------------------------------------------

_CSV_FIELD_LIMIT = 131072
# One cell longer than the csv module's field limit. Semicolons, not letters: the
# forbidden-content patterns scan a long run of word characters in quadratic time.
_OVERSIZED = ";" * (_CSV_FIELD_LIMIT + 1)

_MALFORMED: list[Case] = [
    (
        "counts",
        "oversized-field",
        lambda s: _counts_text() + s + _OVERSIZED + ",2026-08,1,1,1,1,1\n",
    ),
    ("counts", "bare-carriage-return", lambda s: _counts_text() + f"man\r{s},2026-08,1,1,1,1,1\n"),
    ("private-rows", "impossible-date", lambda s: _ledger() + f"when: 2001-99-99\nnotes: {s}\n"),
    (
        "private-rows",
        "integer-too-long-to-convert",
        lambda s: _ledger() + f"big: {'9' * 5000}\nnotes: {s}\n",
    ),
    (
        "private-rows",
        "explicit-tag-on-the-wrong-scalar",
        lambda s: (
            _ledger_with("disposition: port\n", "disposition: !!timestamp port\n") + f"notes: {s}\n"
        ),
    ),
    (
        "private-rows",
        "nesting-deeper-than-the-stack",
        lambda s: _ledger() + f"notes: {s}\ndeep: {'[' * 5000}\n",
    ),
]


def _params(cases: list[Case]) -> list[Any]:
    return [pytest.param(kind, build, id=f"{kind}:{name}") for kind, name, build in cases]


def _run_cli(tmp_path, capsys, kind: str, text: str) -> tuple[int, str]:
    export = tmp_path / "export.txt"
    export.write_text(text, encoding="utf-8", newline="")
    code = main([f"--{kind}", str(export)])
    captured = capsys.readouterr()
    return code, captured.out + captured.err


@pytest.mark.parametrize("label", _LABELS)
@pytest.mark.parametrize(("kind", "build"), _params([*_OUTSIDE, *_ALREADY_CLOSED]))
def test_content_outside_the_validated_structure_is_rejected(tmp_path, capsys, kind, build, label):
    sentinel = _SENTINELS[label]
    text = build(sentinel)

    problems = _VALIDATE[kind](text)
    code, printed = _run_cli(tmp_path, capsys, kind, text)

    assert sentinel in text
    assert problems != []
    assert _leaks(problems, sentinel) == []
    assert code == 1
    assert _leaks([printed], sentinel) == []


@pytest.mark.parametrize("label", _LABELS)
@pytest.mark.parametrize(("kind", "build"), _params(_MALFORMED))
def test_malformed_input_is_a_problem_and_never_an_exception(tmp_path, capsys, kind, build, label):
    sentinel = _SENTINELS[label]
    text = build(sentinel)

    problems = _VALIDATE[kind](text)
    code, printed = _run_cli(tmp_path, capsys, kind, text)

    assert sentinel in text
    assert problems != []
    assert all(isinstance(problem, str) for problem in problems)
    assert _leaks(problems, sentinel) == []
    assert code == 1
    assert "Traceback" not in printed
    assert _leaks([printed], sentinel) == []


def test_the_case_tables_cover_each_artefact():
    kinds = {kind for kind, _name, _build in [*_OUTSIDE, *_ALREADY_CLOSED, *_MALFORMED]}
    names = [f"{kind}:{name}" for kind, name, _build in [*_OUTSIDE, *_ALREADY_CLOSED, *_MALFORMED]]

    assert kinds == set(_VALIDATE)
    assert len(names) == len(set(names)) >= 40
    assert {kind for kind, _name, _build in _OUTSIDE} == {"private-rows", "verdicts"}
    assert {kind for kind, _name, _build in _MALFORMED} == {"counts", "private-rows"}


@pytest.mark.parametrize(
    ("kind", "text"),
    [
        ("verdicts", "﻿" + _verdict_doc()),
        ("counts", "﻿" + _counts_text()),
        ("private-rows", "﻿" + _ledger()),
        ("counts", _counts_text() + "\n"),
        ("private-rows", _ledger() + "\n"),
        ("private-rows", _ledger().replace("\n", "\r\n")),
        ("private-rows", yaml.safe_dump(_private_data(), indent=4)),
    ],
    ids=[
        "verdicts-bom",
        "counts-bom",
        "private-rows-bom",
        "counts-trailing-blank-line",
        "private-rows-trailing-blank-line",
        "private-rows-crlf",
        "private-rows-reindented",
    ],
)
def test_structure_that_carries_no_words_is_rejected_too(tmp_path, capsys, kind, text):
    """A byte-order mark, a stray blank line or a restyled file holds no words and still fails."""
    problems = _VALIDATE[kind](text)
    code, printed = _run_cli(tmp_path, capsys, kind, text)

    assert problems != []
    assert code == 1
    assert "Traceback" not in printed


# ---------------------------------------------------------------------------
# What stays valid, and the wording
# ---------------------------------------------------------------------------


def test_the_canonical_files_still_pass():
    data = _private_data()

    assert verdict_problems(_verdict_doc()) == []
    assert verdict_problems(_verdict_text()) == []
    assert counts_problems(_counts_text()) == []
    assert private_rows_problems(_ledger()) == []
    assert private_rows_problems(data) == []
    assert private_rows_problems(data, _canonical(data)) == []
    assert private_rows_problems(yaml.safe_dump(data)) == []


def test_the_module_states_the_structure_as_constants():
    data = _private_data()

    assert boundary.PRIVATE_TOP_KEYS == ("schema", "rows")
    assert boundary.dump_private_rows(data) == _canonical(data)
    assert yaml.safe_load(boundary.dump_private_rows(data)) == data
    assert boundary.VOCABULARY_LINE == _VOCAB
    commit = _SOURCE.split("commit ")[1][:40]
    assert "<40 lowercase hex>" in boundary.SOURCE_LINE_SHAPE
    assert boundary.SOURCE_LINE_SHAPE.replace("<40 lowercase hex>", commit) == _SOURCE


def test_top_level_keys_are_counted_and_never_named():
    assert private_rows_problems(_ledger(notes="free text", more="free text")) == [
        "2 unexpected top-level key(s) (only schema and rows may appear)"
    ]
    assert private_rows_problems(_private_data() | {"notes": "free text"}) == [
        "1 unexpected top-level key(s) (only schema and rows may appear)"
    ]
    assert private_rows_problems({"rows": _private_data()["rows"], 7: "x"}) == [
        "1 unexpected top-level key(s) (only schema and rows may appear)",
        "schema must be 1",
    ]


def test_a_ledger_that_is_not_canonical_names_its_first_differing_line():
    rule = (
        "not the canonical YAML encoding (write it with dump_private_rows; comments, anchors, "
        "duplicate keys and restyled text never cross)"
    )
    commented = _ledger_with("- id: P-02\n", "# a note\n- id: P-02\n")
    duplicated = _ledger_with(_DESCRIPTION, f"  description: other words\n{_DESCRIPTION}")

    assert private_rows_problems("# a note\n" + _ledger()) == [f"line 1: {rule}"]
    assert private_rows_problems(commented) == [f"line 10: {rule}"]
    assert private_rows_problems(duplicated) == [f"line 5: {rule}"]
    assert private_rows_problems(_private_data(), _ledger() + "# a note\n") == [f"line 18: {rule}"]


def test_lines_outside_the_verdict_structure_are_counted_by_position():
    doc = _verdict_doc()

    assert verdict_problems(f"# Verdicts\n\n{doc}\nA closing remark.\nAnd one more.\n") == [
        "3 line(s) outside the Vocabulary line, the Source line and the table (first at line 1)"
    ]
    assert verdict_problems(f"{doc}\nA closing remark.\n") == [
        "1 line(s) outside the Vocabulary line, the Source line and the table (first at line 23)"
    ]
    assert verdict_problems(_verdict_doc(vocab=f"{_VOCAB} and more")) == [
        f"Vocabulary line must be exactly {boundary.VOCABULARY_LINE!r}"
    ]
    assert verdict_problems(_verdict_doc(source=f"{_SOURCE} and more")) == [
        f"Source line must be exactly: {boundary.SOURCE_LINE_SHAPE}"
    ]


def test_malformed_input_problems_name_the_position_and_the_rule():
    oversized = _counts_text() + _OVERSIZED + ",2026-08,1,1,1,1,1\n"
    carriage = _counts_text() + "man\rual,2026-08,1,1,1,1,1\n"

    assert counts_problems(oversized) == ["not readable as CSV near line 5 (csv.Error)"]
    assert counts_problems(carriage) == ["not readable as CSV near line 5 (csv.Error)"]
    assert private_rows_problems(_ledger() + "when: 2001-99-99\n") == [
        "forbidden content [iso-day-date]: 1 distinct match(es)",
        "not valid YAML: ValueError",
    ]
    assert private_rows_problems(_ledger() + f"deep: {'[' * 5000}\n") == [
        "not valid YAML: RecursionError"
    ]


# ---------------------------------------------------------------------------
# The last-resort guard: an exception nobody foresaw
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("label", _LABELS)
@pytest.mark.parametrize(
    ("kind", "build"),
    [
        ("verdicts", _verdict_text),
        ("counts", _counts_text),
        ("private-rows", _ledger),
    ],
    ids=["verdicts", "counts", "private-rows"],
)
def test_an_unforeseen_exception_becomes_one_problem(
    tmp_path, capsys, monkeypatch, kind, build, label
):
    sentinel = _SENTINELS[label]

    def explode(_data: object) -> dict:
        raise RuntimeError(f"near the line that says {sentinel}")

    monkeypatch.setattr(boundary, "forbidden_hits", explode)

    problems = _VALIDATE[kind](build())
    code, printed = _run_cli(tmp_path, capsys, kind, build())

    assert problems == ["could not be validated (RuntimeError); the file is rejected"]
    assert code == 1
    assert printed.count("could not be validated (RuntimeError); the file is rejected") == 1
    assert "Traceback" not in printed
    assert _leaks([*problems, printed], sentinel) == []


def test_the_real_cli_exits_one_without_a_traceback_on_an_oversized_field(tmp_path):
    """The reported reproduction, through ``python -m tests.ports.boundary`` in a subprocess."""
    sentinel = _SENTINELS["key"]
    export = tmp_path / "counts.csv"
    header = ",".join(COUNTS_HEADER)
    export.write_text(f"{header}\n{sentinel}{_OVERSIZED},2026-06,1,1,1,1,1\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "tests.ports.boundary", "--counts", str(export)],
        cwd=boundary.REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 1
    assert "Traceback" not in proc.stdout + proc.stderr
    assert f"{export}: not readable as CSV near line 2 (csv.Error)" in proc.stdout.splitlines()
    assert sentinel not in proc.stdout + proc.stderr
