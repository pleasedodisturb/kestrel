"""No-echo rows for the boundary validators (``tests/ports/boundary.py``).

The validators run over the private export before anything crosses, and what they
return is printed to terminals, agent transcripts, summaries and CI logs. So a
problem must never repeat the content it rejects: it names a position (row number,
a column or key name of the module's own) and a rule, and quotes only the module's
own constants. ``_hit_problems`` already reported forbidden content by label and
count; these rows hold the structural checks to the same rule.

Every validator is driven position by position (each cell, each header cell, each
YAML key and value, each cut-list item and id) with five sentinels: a plain
distinctive one, a key-shaped one, an email-shaped one, a path-shaped one and a
city name. For each input the validator must still report a problem, the CLI must
exit 1, and no sentinel may appear in a returned problem or in what the CLI
prints. Sentinels that would trip the repository's secret and PII gates are
assembled from fragments at runtime; every value here is synthetic.
"""

import copy
import json
from collections.abc import Callable, Iterable
from typing import Any

import pytest
import yaml

from tests.ports.boundary import (
    COUNTS_HEADER,
    VERDICT_COLUMNS,
    VERDICTS,
    WINDOW_MONTHS,
    counts_problems,
    main,
    private_rows_problems,
    uncited_items,
    verdict_problems,
)
from tests.ports.test_boundary_gates import (
    _SOURCE,
    _VOCAB,
    _counts_rows,
    _counts_text,
    _private_data,
    _rows,
    _table,
    _verdict_text,
)

_SENTINELS = {
    "plain": "ZqxSentinel7731",
    "key": "s" + "k" + "-" + "abcdefghijklmnop1234",
    "email": "".join(("zq.owner", "@", "example", ".org")),
    "path": "/".join(("", "Users", "zqowner", "ledger-notes.md")),
    "city": "Limerick",
}
_LABELS = list(_SENTINELS)

# A cell that may hold free text is valid with a sentinel in it, so its row also
# carries one known defect: the validator is then reporting on that very row.
_FREE_TEXT_COLUMNS = ("name", "reason")
_FREE_TEXT_KEYS = ("description", "inputs", "outputs", "reason")

Case = tuple[str, Callable[[str], Any]]


def _leaks(texts: Iterable[str], sentinel: str) -> list[str]:
    """The texts that repeat *sentinel* in any letter case."""
    needle = sentinel.casefold()
    return [text for text in texts if needle in text.casefold()]


def _col(name: str) -> int:
    return VERDICT_COLUMNS.index(name)


# ---------------------------------------------------------------------------
# Verdict list: every cell, every header cell, both header lines, the prose
# ---------------------------------------------------------------------------


def _verdict_cell(index: int, column: str) -> Callable[[str], str]:
    def build(sentinel: str) -> str:
        rows = _rows()
        if column in _FREE_TEXT_COLUMNS:
            rows[index][_col("count")] = "-1"
        rows[index][_col(column)] = sentinel
        return _verdict_text(rows)

    return build


def _verdict_header(position: int) -> Callable[[str], str]:
    def build(sentinel: str) -> str:
        header = list(VERDICT_COLUMNS)
        header[position] = sentinel
        return _verdict_text(header=tuple(header))

    return build


def _verdict_rows(mutate: Callable[[list[list[str]], str], Any]) -> Callable[[str], str]:
    def build(sentinel: str) -> str:
        rows = _rows()
        return _verdict_text(mutate(rows, sentinel) or rows)

    return build


def _same_cell(column: str) -> Callable[[list[list[str]], str], None]:
    def mutate(rows: list[list[str]], sentinel: str) -> None:
        rows[0][_col(column)] = rows[1][_col(column)] = sentinel

    return mutate


_VERDICT_NO_ECHO: list[Case] = [
    *(
        (f"row{index + 1}-cell-{column}", _verdict_cell(index, column))
        for index in (0, 2)
        for column in VERDICT_COLUMNS
    ),
    *((f"header-{name}", _verdict_header(pos)) for pos, name in enumerate(VERDICT_COLUMNS)),
    ("header-extra-column", lambda s: _verdict_text(header=(*VERDICT_COLUMNS, s))),
    ("row-of-sentinels", _verdict_rows(lambda rows, s: [[s] * len(VERDICT_COLUMNS), *rows])),
    ("short-row", _verdict_rows(lambda rows, s: [[s, s], *rows])),
    ("long-row", _verdict_rows(lambda rows, s: [[*rows[0], s], *rows[1:]])),
    ("duplicate-malformed-id", _verdict_rows(_same_cell("id"))),
    ("duplicate-kind-name", _verdict_rows(_same_cell("name"))),
    ("vocabulary-line", lambda s: _verdict_text(vocab=f"Vocabulary: {s}")),
    ("second-vocabulary-line", lambda s: _verdict_text(tail=f"Vocabulary: {s}")),
    ("source-line", lambda s: _verdict_text(source=f"Source: {s}")),
    ("second-source-line", lambda s: _verdict_text(tail=f"Source: {s}")),
    ("second-table", lambda s: _verdict_text(tail=_table([[s] * len(VERDICT_COLUMNS)]))),
    ("prose-and-no-table", lambda s: f"{_VOCAB}\n\n{_SOURCE}\n\n{s}\n"),
    ("only-the-sentinel", lambda s: f"{s}\n"),
]

# ---------------------------------------------------------------------------
# Arrival counts: every cell, every header cell, the row shape
# ---------------------------------------------------------------------------


def _counts_cell(column: int) -> Callable[[str], str]:
    def build(sentinel: str) -> str:
        rows = _counts_rows()
        rows[0][column] = sentinel
        return _counts_text(rows)

    return build


def _counts_header(position: int) -> Callable[[str], str]:
    def build(sentinel: str) -> str:
        header = list(COUNTS_HEADER)
        header[position] = sentinel
        return _counts_text(header=tuple(header))

    return build


def _counts_duplicate_pair(sentinel: str) -> str:
    rows = _counts_rows()
    rows[0][0] = rows[1][0] = sentinel
    rows[0][1] = rows[1][1] = sentinel
    return _counts_text(rows)


_COUNTS_NO_ECHO: list[Case] = [
    *((f"cell-{name}", _counts_cell(pos)) for pos, name in enumerate(COUNTS_HEADER)),
    *((f"header-{name}", _counts_header(pos)) for pos, name in enumerate(COUNTS_HEADER)),
    ("header-extra-column", lambda s: _counts_text(header=(*COUNTS_HEADER, s))),
    ("row-of-sentinels", lambda s: _counts_text([[s] * len(COUNTS_HEADER)])),
    ("short-row", lambda s: _counts_text([[s, s]])),
    ("long-row", lambda s: _counts_text([[*_counts_rows()[0], s]])),
    ("duplicate-source-month", _counts_duplicate_pair),
    ("only-the-sentinel", lambda s: f"{s}\n"),
]

# ---------------------------------------------------------------------------
# Private ledger rows: every key and value of a row, and the top level
# ---------------------------------------------------------------------------

_WRAPS: dict[str, Callable[[str], Any]] = {
    "raw": lambda s: s,
    "listed": lambda s: [s],
    "keyed": lambda s: {s: s},
}
_ROW_KEYS = ("id", "private", "description", "run_status", "inputs", "outputs", "disposition")


def _private_value(index: int, key: str, form: str, *, companion: bool) -> Callable[[str], dict]:
    def build(sentinel: str) -> dict:
        data = _private_data()
        if companion:
            data["rows"][index]["private"] = False
        data["rows"][index][key] = _WRAPS[form](sentinel)
        return data

    return build


def _private_renamed(key: str) -> Callable[[str], dict]:
    def build(sentinel: str) -> dict:
        data = _private_data()
        data["rows"][0][sentinel] = data["rows"][0].pop(key)
        return data

    return build


def _private_top(mutate: Callable[[dict, str], Any]) -> Callable[[str], Any]:
    def build(sentinel: str) -> Any:
        data = _private_data()
        return mutate(data, sentinel) or data

    return build


def _mixed_unknown_keys(data: dict, sentinel: str) -> None:
    data["rows"][0][sentinel] = sentinel
    data["rows"][0][7] = sentinel


_PRIVATE_NO_ECHO: list[Case] = [
    # every value, in three forms, on a row that also carries a known defect
    *(
        (f"value-{key}-{form}", _private_value(index, key, form, companion=True))
        for index, keys in ((0, _ROW_KEYS), (1, ("reason",)))
        for key in keys
        for form in _WRAPS
    ),
    # an object where a scalar belongs must be reported on its own at every key
    *(
        (f"value-{key}-keyed-alone", _private_value(index, key, "keyed", companion=False))
        for index, keys in ((0, _ROW_KEYS), (1, ("reason",)))
        for key in keys
    ),
    # a constrained scalar must be reported on its own too
    *(
        (f"value-{key}-raw-alone", _private_value(0, key, "raw", companion=False))
        for key in _ROW_KEYS
        if key not in _FREE_TEXT_KEYS
    ),
    *((f"key-{key}-renamed", _private_renamed(key)) for key in _ROW_KEYS),
    ("unknown-key-added", _private_top(lambda d, s: d["rows"][0].update({s: s}))),
    ("unknown-keys-of-mixed-type", _private_top(_mixed_unknown_keys)),
    ("row-is-the-sentinel", _private_top(lambda d, s: d["rows"].insert(0, s))),
    ("rows-is-the-sentinel", _private_top(lambda d, s: d.update(rows=s))),
    ("schema-is-the-sentinel", _private_top(lambda d, s: d.update(schema=s))),
    ("top-level-key-renamed", _private_top(lambda d, s: d.update({s: d.pop("rows")}))),
    ("top-level-list", lambda s: [s]),
    ("top-level-wrong-schema-and-key", _private_top(lambda d, s: d.update({"schema": 2, s: s}))),
]

# YAML text that never becomes data, or that is not a mapping.
_PRIVATE_TEXT_NO_ECHO: list[Case] = [
    ("unterminated", lambda s: f"rows: [unterminated {s}\n"),
    ("undefined-alias", lambda s: f"schema: 1\nnote: {json.dumps(s)}\nrows: *{_alnum(s)}\n"),
    ("bare-scalar", lambda s: f"{s}\n"),
]


def _alnum(sentinel: str) -> str:
    return "".join(ch for ch in sentinel if ch.isalnum())


def _as_yaml(value: Any) -> str:
    if isinstance(value, str):
        return value
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)


# ---------------------------------------------------------------------------
# The rows themselves
# ---------------------------------------------------------------------------

_VALIDATORS: dict[str, tuple[Callable[[Any], list[str]], list[Case], Callable[[Any], str]]] = {
    "verdicts": (verdict_problems, _VERDICT_NO_ECHO, str),
    "counts": (counts_problems, _COUNTS_NO_ECHO, str),
    "private-rows": (private_rows_problems, [*_PRIVATE_NO_ECHO, *_PRIVATE_TEXT_NO_ECHO], _as_yaml),
}
_ALL_CASES = [
    pytest.param(kind, build, id=f"{kind}:{name}")
    for kind, (_validate, cases, _to_text) in _VALIDATORS.items()
    for name, build in cases
]


def test_every_position_of_every_artefact_is_driven():
    """The tables above cover each column, header cell and row key, not one example."""
    names = {
        kind: {name for name, _build in cases} for kind, (_v, cases, _t) in _VALIDATORS.items()
    }

    assert {f"row1-cell-{c}" for c in VERDICT_COLUMNS} <= names["verdicts"]
    assert {f"row3-cell-{c}" for c in VERDICT_COLUMNS} <= names["verdicts"]
    assert {f"header-{c}" for c in VERDICT_COLUMNS} <= names["verdicts"]
    assert {f"cell-{c}" for c in COUNTS_HEADER} <= names["counts"]
    assert {f"header-{c}" for c in COUNTS_HEADER} <= names["counts"]
    assert set(_ROW_KEYS) | {"reason"} == set().union(*(row for row in _private_data()["rows"]))
    assert {f"value-{k}-{form}" for k in (*_ROW_KEYS, "reason") for form in _WRAPS} <= names[
        "private-rows"
    ]
    assert {f"key-{k}-renamed" for k in _ROW_KEYS} <= names["private-rows"]
    assert len(_ALL_CASES) == sum(len(cases) for _v, cases, _t in _VALIDATORS.values()) >= 100


@pytest.mark.parametrize("label", _LABELS)
@pytest.mark.parametrize(("kind", "build"), _ALL_CASES)
def test_structural_problems_never_repeat_a_planted_value(tmp_path, capsys, kind, build, label):
    sentinel = _SENTINELS[label]
    validate, _cases, to_text = _VALIDATORS[kind]
    payload = build(sentinel)
    export = tmp_path / "export.txt"
    export.write_text(to_text(payload), encoding="utf-8")

    problems = validate(copy.deepcopy(payload))
    code = main([f"--{kind}", str(export)])
    captured = capsys.readouterr()
    printed = captured.out + captured.err

    assert sentinel.casefold() in to_text(payload).casefold()
    assert problems != []
    assert _leaks(problems, sentinel) == []
    assert code == 1
    assert printed.count(f"{export}: ") >= 1
    assert _leaks([printed], sentinel) == []


def test_clean_artefacts_still_pass_with_no_sentinel():
    """The base examples the rows above mutate are clean, so each problem is the mutation's."""
    assert verdict_problems(_verdict_text()) == []
    assert counts_problems(_counts_text()) == []
    assert private_rows_problems(_private_data()) == []


# ---------------------------------------------------------------------------
# The reviewer's reproduction, and the position-and-rule wording
# ---------------------------------------------------------------------------


def test_cli_does_not_print_a_key_shaped_source_cell(tmp_path, capsys):
    """A counts CSV whose source cell is key-shaped: redacted once, and not printed again."""
    key = _SENTINELS["key"]
    rows = _counts_rows()
    rows[0][0] = key
    export = tmp_path / "counts.csv"
    export.write_text(_counts_text(rows), encoding="utf-8")

    code = main(["--counts", str(export)])
    printed = capsys.readouterr()

    assert code == 1
    assert printed.out.splitlines() == [
        f"{export}: forbidden content [key-shaped]: 1 distinct match(es)",
        f"{export}: row 1: source is not an allowed source family",
    ]
    assert key not in printed.out + printed.err


def test_verdict_problems_name_the_position_and_the_rule():
    rows = _rows()
    rows[0][_col("kind")] = "thing"
    rows[1][_col("verdict")] = "maybe"
    rows[2][_col("count")] = "many"
    rows[3][_col("id")] = "Z-9"
    rows[4][_col("ref")] = "somewhere:else"
    rows[5][_col("profile_scope")] = "mixed"
    rows[6][_col("non_technical")] = "perhaps"
    rows[7][_col("verdict")] = "trimmed"

    problems = verdict_problems(_verdict_text(rows))

    assert len(rows) == 15
    assert problems == [
        "row 1 (F-01): kind must be flow or feature",
        f"row 2 (F-02): verdict is not one of {VERDICTS}",
        "row 3 (X-01): count is not a non-negative integer",
        "row 4: id does not match kind feature",
        "row 5 (X-03): ref is not '-' or a phase:slug pair",
        "row 6 (X-04): profile_scope is not specific or generic",
        "row 7 (X-05): non_technical is not yes, no or partial",
        "row 8 (X-06): verdict is a D-02 alias; use 'scope-and-plan'",
        "missing required ref cut-a:worker",
    ]


def test_verdict_table_problems_give_positions_and_counts():
    rows = _rows()
    duplicate_id = [rows[0], rows[0], *rows[1:]]
    renamed = _rows()
    renamed[1][_col("name")] = renamed[0][_col("name")]
    malformed = _rows()
    malformed[0][_col("id")] = malformed[1][_col("id")] = "nope"
    header = (*VERDICT_COLUMNS, "note")

    assert verdict_problems(_verdict_text(duplicate_id)) == [
        "duplicate id F-01 in rows 1, 2",
        "duplicate (kind, name) in rows 1, 2",
    ]
    assert verdict_problems(_verdict_text(renamed)) == ["duplicate (kind, name) in rows 1, 2"]
    assert verdict_problems(_verdict_text(malformed)) == [
        "row 1: id does not match kind flow",
        "row 2: id does not match kind flow",
        "duplicate id in rows 1, 2",
    ]
    assert verdict_problems(_verdict_text(header=header)) == [
        f"table header must be exactly {VERDICT_COLUMNS}, got 10 column(s)"
    ]


def test_counts_problems_name_the_position_and_the_rule():
    rows = _counts_rows()
    rows.append(list(rows[0]))
    rows[1][0] = "acme-corp"
    rows[1][1] = "2026-05"
    rows[2][3] = "1.5"

    problems = counts_problems(_counts_text(rows))
    header_problems = counts_problems(_counts_text(header=(*COUNTS_HEADER, "note")))

    assert problems == [
        "row 2: source is not an allowed source family",
        f"row 2: month is not one of {WINDOW_MONTHS}",
        "row 3: survived_prefilter is not a non-negative integer",
        "row 4: duplicate (source, month) of row 1",
    ]
    assert header_problems == [f"header must be exactly {COUNTS_HEADER}, got 8 column(s)"]


def test_private_rows_problems_name_the_position_and_the_rule():
    data = _private_data()
    data["rows"][0] |= {"run_status": "sometimes", "path": "x", "note": "y", 7: "z"}
    data["rows"][1] |= {"id": "P-1", "disposition": "archive"}

    problems = private_rows_problems(data)

    assert len(data["rows"]) == 2
    assert problems == [
        "row 0 (P-01): unexpected key 'path' (rows never carry paths or globs)",
        "row 0 (P-01): 2 unexpected key(s) (rows never carry paths or globs)",
        "row 0 (P-01): invalid run_status (must be one of scheduled, by_hand, dead)",
        "row 1: id does not match P-NN",
        "row 1: invalid disposition (must be one of port, keep_until_retire, delete)",
    ]


# ---------------------------------------------------------------------------
# Cut-list citations: an uncited item is described, never quoted
# ---------------------------------------------------------------------------

_KNOWN = {"F-01", "X-01", "X-02"}

_CUT_LIST_NO_ECHO: list[Case] = [
    ("item-without-clause", lambda s: f"- {s}\n"),
    ("item-with-unknown-id", lambda s: f"- {s} | verdict: X-99\n"),
    ("id-is-the-sentinel", lambda s: f"- item | verdict: {s}\n"),
    ("known-id-then-sentinel", lambda s: f"- {s} | verdicts: X-01, {s}\n"),
    ("sentinel-then-known-id", lambda s: f"- {s} | verdicts: {s}, X-01\n"),
    ("clause-without-ids", lambda s: f"- {s} | verdict:\n"),
]


@pytest.mark.parametrize("label", _LABELS)
@pytest.mark.parametrize(
    ("case", "build"), _CUT_LIST_NO_ECHO, ids=[c[0] for c in _CUT_LIST_NO_ECHO]
)
def test_uncited_items_never_repeat_a_planted_value(case, build, label):
    sentinel = _SENTINELS[label]
    text = "# Cut list\n\n- cited | verdict: X-01\n" + build(sentinel)

    found = uncited_items(text, _KNOWN)

    assert [line_no for line_no, _what, _ids in found] == [4], case
    assert _leaks([repr(found)], sentinel) == []


def test_uncited_items_describe_the_item_and_keep_only_well_formed_ids():
    text = (
        "- ok | verdict: X-01\n"
        "- bare\n"
        "- ghost | verdict: X-99\n"
        "- mixed | verdicts: X-01, X-99\n"
        "- odd | verdicts: F-01, not-an-id\n"
    )

    found = uncited_items(text, _KNOWN)

    assert [line_no for line_no, _what, _ids in found] == [2, 3, 4, 5]
    assert found == [
        (2, "item cites no verdict id", []),
        (3, "item cites an unknown verdict id", ["X-99"]),
        (4, "item cites an unknown verdict id", ["X-01", "X-99"]),
        (5, "item cites an unknown verdict id", ["F-01", "<malformed id>"]),
    ]
