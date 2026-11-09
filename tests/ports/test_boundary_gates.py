"""Guard-the-guard tests for the boundary validators, plus the MAP-09 enforcement tests.

Every validator in ``tests/ports/boundary.py`` is proven here against a minimal valid
synthetic example (it yields no problems) and one single-mutation case per rule (it
yields that rule's problem). Strings that would trip the repository's PII gates
(emails, key-shaped values) are assembled from fragments at runtime so no such literal
is committed.

The last two tests are strict xfails keyed on the Cut A and Retire cut lists
(MAP-09, open question OQ-9): they report XFAIL until the phase that writes a cut list
exists. That phase must make every cut-list item cite a verdict id and remove the marker
in the same PR, or the strict xfail turns the run red.
"""

import csv
import io
import unicodedata

import pytest
import yaml

from tests.eval.geo.replay import scrub_patterns
from tests.ports import boundary
from tests.ports.boundary import (
    ALLOWED_SOURCES,
    COUNTS_HEADER,
    REQUIRED_REFS,
    VERDICT_COLUMNS,
    VERDICTS_PATH,
    ArtifactMissing,
    CutListMissing,
    counts_problems,
    cut_list_items,
    find_cut_list,
    forbidden_hits,
    main,
    parse_verdict_list,
    private_rows_problems,
    require,
    uncited_items,
    verdict_problems,
)

# ---------------------------------------------------------------------------
# Verdict list fixtures
# ---------------------------------------------------------------------------

_COMMIT = "0123456789abcdef" * 2 + "01234567"
_VOCAB = (
    "Vocabulary: keep / scope-and-plan / park / remove "
    "(D-02's kept / trimmed / parked / cut map to these in that order)"
)
_SOURCE = f"Source: the private pipeline's repository, commit {_COMMIT}, window 2026-06 to 2026-10"


def _rows() -> list[list[str]]:
    """Two flows plus one feature per required ref, ids sorted, every cell valid."""
    rows = [
        ["F-01", "flow", "scan flow", "-", "keep", "generic", "yes", "12", "ran steadily"],
        [
            "F-02",
            "flow",
            "write flow",
            "-",
            "scope-and-plan",
            "specific",
            "partial",
            "3",
            "half built",
        ],
    ]
    for number, ref in enumerate(REQUIRED_REFS, start=1):
        rows.append(
            [
                f"X-{number:02d}",
                "feature",
                f"feature {ref}",
                ref,
                "remove",
                "generic",
                "no",
                "0",
                "superseded by the planned replacement",
            ]
        )
    return rows


def _table(rows: list[list[str]], header: tuple[str, ...] = VERDICT_COLUMNS) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def _verdict_text(
    rows: list[list[str]] | None = None,
    *,
    vocab: str | None = _VOCAB,
    source: str | None = _SOURCE,
    header: tuple[str, ...] = VERDICT_COLUMNS,
    tail: str = "",
) -> str:
    parts = [part for part in (vocab, source) if part is not None]
    parts.append(_table(_rows() if rows is None else rows, header))
    if tail:
        parts.append(tail)
    return "\n\n".join(parts) + "\n"


def _mutated(index: int, column: str, value: str) -> str:
    rows = _rows()
    rows[index][VERDICT_COLUMNS.index(column)] = value
    return _verdict_text(rows)


def _without_ticktick() -> str:
    return _verdict_text([r for r in _rows() if r[3] != "cut-a:ticktick"])


def _swapped() -> str:
    rows = _rows()
    rows[0], rows[1] = rows[1], rows[0]
    return _verdict_text(rows)


def _flow_after_features() -> str:
    rows = _rows()
    return _verdict_text([rows[0], *rows[2:], rows[1]])


def _duplicate_id() -> str:
    rows = _rows()
    return _verdict_text([rows[0], rows[0], *rows[1:]])


def _duplicate_name() -> str:
    rows = _rows()
    rows[1][2] = rows[0][2]
    return _verdict_text(rows)


def _short_row() -> str:
    rows = _rows()
    rows[0] = rows[0][:-1]
    return _verdict_text(rows)


def _second_table() -> str:
    return _verdict_text(tail=_table(_rows()[:1]))


_VERDICT_CASES = [
    ("duplicate-id", _duplicate_id, "duplicate id F-01"),
    ("duplicate-kind-name", _duplicate_name, "duplicate (kind, name)"),
    ("unsorted-ids", _swapped, "ids are not sorted"),
    ("flow-after-features", _flow_after_features, "ids are not sorted"),
    ("empty-table", lambda: _verdict_text([]), "verdict list has no rows"),
    ("no-table", lambda: _VOCAB + "\n\n" + _SOURCE + "\n", "no table found"),
    ("alias-verdict", lambda: _mutated(0, "verdict", "trimmed"), "D-02 alias"),
    ("unknown-verdict", lambda: _mutated(0, "verdict", "maybe"), "is not one of"),
    ("under-use-only", lambda: _mutated(2, "reason", "Unused."), "under-use alone"),
    ("under-use-variant", lambda: _mutated(2, "reason", "rarely used"), "under-use alone"),
    ("missing-required-ref", _without_ticktick, "missing required ref cut-a:ticktick"),
    ("bad-profile-scope", lambda: _mutated(0, "profile_scope", "mixed"), "profile_scope"),
    ("bad-non-technical", lambda: _mutated(0, "non_technical", "maybe"), "non_technical"),
    ("negative-count", lambda: _mutated(0, "count", "-3"), "not a non-negative integer"),
    ("id-kind-mismatch", lambda: _mutated(0, "id", "X-01"), "does not match kind flow"),
    ("reason-too-long", lambda: _mutated(0, "reason", "x" * 301), "longer than 300"),
    ("empty-reason", lambda: _mutated(0, "reason", ""), "reason is empty"),
    ("bad-ref", lambda: _mutated(0, "ref", "somewhere:else"), "is not '-' or a phase:slug"),
    ("extra-column", lambda: _verdict_text(header=(*VERDICT_COLUMNS, "note")), "header must be"),
    ("missing-vocabulary", lambda: _verdict_text(vocab=None), "'Vocabulary:'"),
    (
        "vocabulary-without-d02",
        lambda: _verdict_text(vocab="Vocabulary: keep / scope-and-plan / park / remove"),
        "'D-02'",
    ),
    (
        "source-without-commit",
        lambda: _verdict_text(
            source="Source: the private pipeline's repository, window 2026-06 to 2026-10"
        ),
        "40-hex commit",
    ),
    (
        "source-without-window",
        lambda: _verdict_text(source=f"Source: the private pipeline's repository {_COMMIT}"),
        "window",
    ),
    ("short-row", _short_row, "expected 9 cells"),
    ("second-table", _second_table, "more than one table"),
    (
        "iso-day-date-in-reason",
        lambda: _mutated(0, "reason", "ran on 2026-10-05"),
        "[iso-day-date]",
    ),
    ("url-in-reason", lambda: _mutated(0, "reason", "see https://example.invalid/x"), "[any-url]"),
    ("quote-in-reason", lambda: _mutated(0, "reason", 'said "no" twice'), "[quotation-marks]"),
]


def test_valid_verdict_list_passes_and_parses():
    """The minimal valid example is clean, so every mutation case below is a real signal."""
    text = _verdict_text()
    assert verdict_problems(text) == []
    rows = parse_verdict_list(text)
    assert len(rows) == 2 + len(REQUIRED_REFS)
    assert [r["id"] for r in rows][:3] == ["F-01", "F-02", "X-01"]


@pytest.mark.parametrize(
    ("case", "build", "expected"), _VERDICT_CASES, ids=[c[0] for c in _VERDICT_CASES]
)
def test_verdict_mutations_are_rejected(case, build, expected):
    """Each single mutation of a valid verdict list yields its specific problem."""
    problems = verdict_problems(build())
    assert any(expected in p for p in problems), f"{case}: got {problems}"
    assert problems != []


def test_verdict_problems_never_echo_matched_text():
    """A forbidden match is reported by label and count only, so logs cannot leak it."""
    problems = verdict_problems(_mutated(0, "reason", "ran on 2026-10-05"))
    assert any("[iso-day-date]" in p for p in problems)
    assert not any("2026-10-05" in p for p in problems)


def test_verdict_vocabulary_constants_match_d02_mapping():
    """D-02's four words map onto the canonical four in order, and nothing else is accepted."""
    assert boundary.VERDICTS == ("keep", "scope-and-plan", "park", "remove")
    assert list(boundary.D02_ALIASES.values()) == list(boundary.VERDICTS)
    assert list(boundary.D02_ALIASES) == ["kept", "trimmed", "parked", "cut"]


# ---------------------------------------------------------------------------
# Arrival counts
# ---------------------------------------------------------------------------


def _counts_rows() -> list[list[str]]:
    return [
        ["greenhouse", "2026-06", "10", "6", "5", "2", "1"],
        ["indeed", "2026-06", "7", "4", "3", "1", "0"],
        ["manual", "2026-07", "1", "1", "1", "1", "1"],
    ]


def _counts_text(rows=None, header=COUNTS_HEADER) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(_counts_rows() if rows is None else rows)
    return buffer.getvalue()


def _counts_with(index: int, column: int, value: str) -> str:
    rows = _counts_rows()
    rows[index][column] = value
    return _counts_text(rows)


_COUNTS_CASES = [
    # The month rule is named by row and column; the rejected cell is never repeated.
    ("day-level-month", lambda: _counts_with(0, 1, "2026-10-05"), "row 1: month is not one of"),
    ("month-outside-window", lambda: _counts_with(0, 1, "2026-05"), "row 1: month is not one of"),
    (
        "company-slug-source",
        lambda: _counts_with(0, 0, "acme-corp"),
        "not an allowed source family",
    ),
    ("negative-value", lambda: _counts_with(0, 2, "-1"), "not a non-negative integer"),
    ("decimal-value", lambda: _counts_with(0, 3, "1.5"), "not a non-negative integer"),
    ("extra-column", lambda: _counts_text(header=(*COUNTS_HEADER, "note")), "header must be"),
    (
        "duplicate-source-month",
        lambda: _counts_text(_counts_rows() + _counts_rows()[:1]),
        "duplicate (source, month)",
    ),
    ("short-row", lambda: _counts_text([["greenhouse", "2026-06", "1"]]), "expected 7 cells"),
    ("no-rows", lambda: _counts_text([]), "no rows"),
    ("empty-file", lambda: "", "no header"),
]


def test_valid_counts_pass():
    """The minimal valid counts file is clean, with zero as a legitimate recorded value."""
    assert counts_problems(_counts_text()) == []
    assert counts_problems(_counts_with(1, 6, "0")) == []


@pytest.mark.parametrize(
    ("case", "build", "expected"), _COUNTS_CASES, ids=[c[0] for c in _COUNTS_CASES]
)
def test_counts_mutations_are_rejected(case, build, expected):
    """Each single mutation of a valid counts file yields its specific problem."""
    problems = counts_problems(build())
    assert any(expected in p for p in problems), f"{case}: got {problems}"
    assert problems != []


def test_allowed_sources_match_the_registry():
    """ALLOWED_SOURCES is the scan registry's floor sources plus jobspy boards plus three extras."""
    from source_registry import FLOOR_SOURCES, JOBSPY_BOARDS  # tools/ is on sys.path via conftest

    expected = set(FLOOR_SOURCES) | set(JOBSPY_BOARDS) | {"arbeitsagentur", "manual", "other"}
    assert set(ALLOWED_SOURCES) == expected
    assert len(ALLOWED_SOURCES) == len(FLOOR_SOURCES) + len(JOBSPY_BOARDS) + 3


def test_counts_window_is_five_months():
    """The window is June to October 2026, month granularity only."""
    assert boundary.WINDOW_MONTHS == ("2026-06", "2026-07", "2026-08", "2026-09", "2026-10")
    assert all(len(month) == 7 for month in boundary.WINDOW_MONTHS)


# ---------------------------------------------------------------------------
# Private ledger rows
# ---------------------------------------------------------------------------


def _private_data() -> dict:
    return {
        "schema": 1,
        "rows": [
            {
                "id": "P-01",
                "private": True,
                "description": "nightly scorer",
                "run_status": "scheduled",
                "inputs": "scan output",
                "outputs": "scored list",
                "disposition": "port",
            },
            {
                "id": "P-02",
                "private": True,
                "description": "one-off exporter",
                "run_status": "dead",
                "inputs": "tracker",
                "outputs": "spreadsheet",
                "disposition": "delete",
                "reason": "superseded",
            },
        ],
    }


def _private_with(index: int, key: str, value) -> dict:
    data = _private_data()
    data["rows"][index][key] = value
    return data


def _private_unsorted() -> dict:
    data = _private_data()
    data["rows"].reverse()
    return data


def _private_duplicate() -> dict:
    data = _private_data()
    data["rows"][1]["id"] = "P-01"
    return data


def _private_no_reason() -> dict:
    data = _private_data()
    del data["rows"][1]["reason"]
    return data


_PRIVATE_CASES = [
    ("path-token", lambda: _private_with(0, "outputs", "writes to scripts/out"), "path-like token"),
    (
        "py-filename",
        lambda: _private_with(0, "description", "runs nightly_job.py"),
        "script filename",
    ),
    ("shell-filename", lambda: _private_with(0, "inputs", "calls run.sh"), "script filename"),
    ("path-key", lambda: _private_with(0, "path", "x"), "unexpected key 'path'"),
    ("glob-key", lambda: _private_with(0, "glob", "x"), "unexpected key 'glob'"),
    ("not-private", lambda: _private_with(0, "private", False), "private must be true"),
    ("bad-id", lambda: _private_with(0, "id", "P-1"), "does not match P-NN"),
    ("duplicate-id", _private_duplicate, "duplicate id P-01"),
    ("unsorted", _private_unsorted, "not sorted by id"),
    ("delete-without-reason", _private_no_reason, "needs a reason"),
    ("bad-run-status", lambda: _private_with(0, "run_status", "sometimes"), "invalid run_status"),
    ("bad-disposition", lambda: _private_with(0, "disposition", "archive"), "invalid disposition"),
    ("wrong-schema", lambda: {**_private_data(), "schema": 2}, "schema must be 1"),
    ("empty-rows", lambda: {"schema": 1, "rows": []}, "empty or missing"),
    ("not-a-mapping", lambda: ["P-01"], "must be a mapping"),
]


def test_valid_private_rows_pass_as_data_and_as_text():
    """The minimal example passes as parsed data and as YAML text."""
    data = _private_data()
    assert private_rows_problems(data) == []
    assert private_rows_problems(yaml.safe_dump(data)) == []


@pytest.mark.parametrize(
    ("case", "build", "expected"), _PRIVATE_CASES, ids=[c[0] for c in _PRIVATE_CASES]
)
def test_private_rows_mutations_are_rejected(case, build, expected):
    """Each single mutation of the private rows yields its specific problem."""
    problems = private_rows_problems(build())
    assert any(expected in p for p in problems), f"{case}: got {problems}"
    assert problems != []


def test_private_rows_reject_invalid_yaml_text():
    """Text that is not YAML is a problem, never an exception."""
    problems = private_rows_problems("rows: [unterminated")
    assert any("not valid YAML" in p for p in problems)
    assert problems != []


# ---------------------------------------------------------------------------
# forbidden_hits
# ---------------------------------------------------------------------------


def test_month_passes_and_day_is_rejected():
    """A month is allowed; a day is not (probe MAP-08 adjacency)."""
    assert forbidden_hits("window 2026-10 only") == {}
    assert forbidden_hits("it ran on 2026-10-05") == {"iso-day-date": ["2026-10-05"]}


def test_text_dates_are_rejected_but_month_and_year_is_not():
    """Day-and-month text dates in either order hit; a month with a year does not."""
    assert "text-day-date" in forbidden_hits("on 5 October we stopped")
    assert "text-day-date" in forbidden_hits("on October 5 we stopped")
    assert "text-day-date" in forbidden_hits("the 5th of October")
    assert forbidden_hits("in June 2026 it ran") == {}
    assert forbidden_hits("in 2026 June") == {}


@pytest.mark.parametrize("text", ["", "   ", "\n\t\n"])
def test_empty_text_is_a_hit(text):
    """Empty or blank text is rejected rather than passing (probe MAP-08 empty)."""
    assert forbidden_hits(text) == {"empty-text": [""]}
    assert forbidden_hits(text.encode("utf-8")) == {"empty-text": [""]}


def test_encoding_attacks_are_rejected():
    """Invalid UTF-8, zero-width and bidi characters are hits (probe MAP-08 encoding)."""
    assert forbidden_hits(b"\xff\xfe\x00 not text") == {"invalid-utf8": ["not valid UTF-8"]}
    assert forbidden_hits("a​b") == {"control-character": ["U+200B"]}
    assert forbidden_hits("a‮b") == {"control-character": ["U+202E"]}
    assert forbidden_hits("﻿byte order mark") == {"control-character": ["U+FEFF"]}


def test_control_characters_cannot_hide_a_pattern():
    """A zero-width space inside a date is reported and the date is still found."""
    hits = forbidden_hits("2026-10-​05")
    assert hits["control-character"] == ["U+200B"]
    assert hits["iso-day-date"] == ["2026-10-05"]


def test_nfc_equivalent_spellings_give_the_same_hits():
    """Composed and decomposed spellings of the same text report identical hits."""
    composed = unicodedata.normalize("NFC", "café on 5 October, price €12")
    decomposed = unicodedata.normalize("NFD", composed)
    assert composed != decomposed
    assert forbidden_hits(composed) == forbidden_hits(decomposed)
    assert set(forbidden_hits(composed)) == {"currency-amount", "text-day-date"}


def test_casefolding_applies_before_matching():
    """Upper-case spellings hit the same patterns as lower-case ones."""
    assert "text-day-date" in forbidden_hits("5 OCTOBER")
    assert "currency-amount" in forbidden_hits("12 EUR")
    assert "home-path" in forbidden_hits("/Users/someone/file")


def test_hits_are_sorted_by_label_and_deduplicated():
    """Labels iterate in sorted order and a repeated match is reported once."""
    hits = forbidden_hits("https://example.invalid/a on 2026-10-05 and again 2026-10-05")
    assert list(hits) == sorted(hits)
    assert hits["iso-day-date"] == ["2026-10-05"]


def test_extra_patterns_each_fire():
    """Each addition to scrub_patterns() is reachable under its documented label."""
    key = "s" + "k" + "-" + "abcdefghijklmnop1234"
    cases = {
        "any-url": "see https://example.invalid/path",
        "currency-amount": "costs $12 a month",
        "key-shaped": f"token {key}",
        "home-path": "stored under ~/notes",
        "private-side-path": "see private/notes",
        "quotation-marks": 'he said "no"',
    }
    for label, text in cases.items():
        assert label in forbidden_hits(text), f"{label} did not fire on {text!r}"
    assert "private-side-path" in forbidden_hits("under .claude/projects")
    assert "quotation-marks" in forbidden_hits("curly “quote”")


def test_apostrophes_and_plain_prose_are_allowed():
    """The private pipeline's repository (with an apostrophe) is the one allowed spelling."""
    assert forbidden_hits("the private pipeline's repository, window 2026-06 to 2026-10") == {}
    assert forbidden_hits("flow ran steadily and produced digests") == {}


def test_scrub_patterns_are_reused_not_copied():
    """forbidden_hits starts from scrub_patterns(): its email and tracking labels fire."""
    email = "someone" + "@" + "example" + ".com"
    tracking = "https://host.invalid/p" + "?" + "x=1"
    assert {"generic:email", "tracking:url-query"} <= set(scrub_patterns())
    assert "generic:email" in forbidden_hits(email)
    assert "tracking:url-query" in forbidden_hits(tracking)


# ---------------------------------------------------------------------------
# require and find_cut_list
# ---------------------------------------------------------------------------


def test_require_reads_text_and_raises_when_missing(tmp_path):
    """require returns UTF-8 text, and raises ArtifactMissing for an absent file."""
    present = tmp_path / "x.md"
    present.write_text("café", encoding="utf-8")
    assert require(present) == "café"
    with pytest.raises(ArtifactMissing, match="does not exist yet"):
        require(tmp_path / "absent.md")
    assert not (tmp_path / "absent.md").exists()


def test_find_cut_list_none_one_many(tmp_path, monkeypatch):
    """No cut list raises CutListMissing, one is returned, several is a loud ValueError."""
    monkeypatch.setattr(boundary, "PHASES_DIR", tmp_path)
    with pytest.raises(CutListMissing):
        find_cut_list("*-cut-a")
    first = tmp_path / "13-cut-a"
    first.mkdir()
    (first / "13-CUT-LIST.md").write_text("- x | verdict: X-01\n", encoding="utf-8")
    assert find_cut_list("*-cut-a") == first / "13-CUT-LIST.md"
    (tmp_path / "14-cut-a").mkdir()
    (tmp_path / "14-cut-a" / "14-CUT-LIST.md").write_text("- y\n", encoding="utf-8")
    with pytest.raises(ValueError, match="more than one"):
        find_cut_list("*-cut-a")
    assert (first / "13-CUT-LIST.md").exists()


# ---------------------------------------------------------------------------
# Cut list citation checker (MAP-09)
# ---------------------------------------------------------------------------

_KNOWN = {"F-01", "X-01", "X-02"}


def test_cut_list_items_are_parsed_in_file_order():
    """Items come back with line numbers, text and ids; non-item lines are ignored."""
    text = "# Cut list\n\n- first | verdict: X-01\nprose line\n- second | verdicts: X-02, F-01\n- third\n"
    assert cut_list_items(text) == [
        (3, "first", ["X-01"]),
        (5, "second", ["X-02", "F-01"]),
        (6, "third", []),
    ]
    assert [item[0] for item in cut_list_items(text)] == [3, 5, 6]


def test_all_cited_items_pass():
    """Every item citing a known id yields no uncited items."""
    text = "- a | verdict: X-01\n- b | verdict: X-02\n"
    assert uncited_items(text, _KNOWN) == []
    assert uncited_items(text, ["X-01", "X-02"]) == []


def test_one_item_citing_several_ids_and_several_items_citing_one_id_pass():
    """Adjacency: many ids on one item and one id on many items are both fine."""
    many_ids = "- a | verdicts: X-01, X-02, F-01\n"
    one_id = "- a | verdict: X-01\n- b | verdict: X-01\n"
    assert uncited_items(many_ids, _KNOWN) == []
    assert uncited_items(one_id, _KNOWN) == []


def test_uncited_and_unknown_items_are_reported_in_file_order():
    """Items with no clause or an unknown id come back in file order (probe MAP-09 ordering).

    Each entry describes the item (its line, which rule it breaks, the well-formed ids it
    cites) and never quotes the item's own text.
    """
    text = "- ok | verdict: X-01\n- bare\n- ghost | verdict: X-99\n- mixed | verdicts: X-01, X-99\n"
    assert uncited_items(text, _KNOWN) == [
        (2, "item cites no verdict id", []),
        (3, "item cites an unknown verdict id", ["X-99"]),
        (4, "item cites an unknown verdict id", ["X-01", "X-99"]),
    ]
    assert [item[0] for item in uncited_items(text, _KNOWN)] == [2, 3, 4]


@pytest.mark.parametrize("text", ["", "# only a heading\n\nsome prose\n"])
def test_an_empty_cut_list_is_a_failure(text):
    """A cut list with zero items yields one problem, so emptiness can never pass."""
    assert uncited_items(text, _KNOWN) == [(0, "cut list has no items", [])]
    assert cut_list_items(text) == []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_exits_zero_on_a_clean_file_and_one_otherwise(tmp_path, capsys):
    """Clean files exit 0 silently; a bad file exits 1 and prints file: problem lines."""
    good = tmp_path / "verdicts.md"
    good.write_text(_verdict_text(), encoding="utf-8")
    assert main(["--verdicts", str(good)]) == 0
    assert capsys.readouterr().out == ""
    bad = tmp_path / "bad.md"
    bad.write_text("not a verdict list\n", encoding="utf-8")
    assert main(["--verdicts", str(bad)]) == 1
    assert f"{bad}: no table found" in capsys.readouterr().out


def test_cli_checks_counts_and_private_rows(tmp_path, capsys):
    """Counts and private-row files are validated by their own contracts."""
    counts = tmp_path / "counts.csv"
    counts.write_text(_counts_text(), encoding="utf-8")
    rows = tmp_path / "rows.yaml"
    rows.write_text(yaml.safe_dump(_private_data()), encoding="utf-8")
    assert main(["--counts", str(counts), "--private-rows", str(rows)]) == 0
    rows.write_text(
        yaml.safe_dump(_private_with(0, "outputs", "writes to scripts/out")), encoding="utf-8"
    )
    assert main(["--counts", str(counts), "--private-rows", str(rows)]) == 1
    assert "path-like token" in capsys.readouterr().out


def test_cli_usage_errors_exit_two(capsys):
    """No arguments and unknown flags are usage errors."""
    assert main([]) == 2
    assert main(["--no-such-flag"]) == 2
    assert "usage" in capsys.readouterr().err.lower()


def test_cli_reports_unreadable_and_non_utf8_files(tmp_path, capsys):
    """A missing file and a non-UTF-8 file are problems (exit 1), never tracebacks."""
    assert main(["--verdicts", str(tmp_path / "absent.md")]) == 1
    binary = tmp_path / "bin.md"
    binary.write_bytes(b"\xff\xfe\x00")
    assert main(["--verdicts", str(binary)]) == 1
    out = capsys.readouterr().out
    assert "cannot read file" in out
    assert "invalid-utf8" in out


def test_cli_rejects_a_file_that_is_not_a_verdict_list():
    """The package marker file is not a verdict list, so the CLI exits 1 (plan verify command)."""
    assert main(["--verdicts", str(boundary.REPO_ROOT / "tests/ports/__init__.py")]) == 1
    assert main(["--verdicts", str(boundary.REPO_ROOT / "tests/ports/PORT_LEDGER.yaml")]) == 1


# ---------------------------------------------------------------------------
# MAP-09 enforcement: strict xfail until the cut list exists
# ---------------------------------------------------------------------------


# find_cut_list is the only call in each body that may raise CutListMissing, so a present
# cut list reaches both asserts and a fully cited one XPASSes strictly.


@pytest.mark.xfail(
    strict=True,
    raises=CutListMissing,
    reason="v2.0 Phase 13 Cut A writes its cut list; remove this marker in that PR",
)
def test_cut_a_cut_list_cites_a_verdict_for_every_item():
    """Every Cut A cut-list item cites a known verdict id (MAP-09)."""
    path = find_cut_list("*-cut-a")
    text = path.read_text(encoding="utf-8")
    known = {row["id"] for row in parse_verdict_list(require(VERDICTS_PATH))}
    assert cut_list_items(text), f"{path.name} has no cut-list items"
    assert uncited_items(text, known) == []


@pytest.mark.xfail(
    strict=True,
    raises=CutListMissing,
    reason="v2.0 Retire writes its cut list; remove this marker in that PR",
)
def test_retire_cut_list_cites_a_verdict_for_every_item():
    """Every Retire cut-list item cites a known verdict id (MAP-09)."""
    path = find_cut_list("*-retire")
    text = path.read_text(encoding="utf-8")
    known = {row["id"] for row in parse_verdict_list(require(VERDICTS_PATH))}
    assert cut_list_items(text), f"{path.name} has no cut-list items"
    assert uncited_items(text, known) == []
