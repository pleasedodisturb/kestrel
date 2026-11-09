"""Cell rules the earlier boundary passes left open (review round 2, G-2039).

Two holes, both returning ``[]`` before the fix:

- Private ledger: a text cell set to null was skipped, and the "dead or delete row needs a
  reason" check read ``str(None)`` as a reason. A row with every text cell null, marked
  dead and delete, crossed with no description and no justification.
- Verdict list: the export contract says no cell carries a path or a script name, but only
  the private ledger's cells were held to that. A ``reason`` or ``name`` naming a private
  script passed.

Problems name the row, the column and the rule, never the cell (the no-echo rule).
"""

from __future__ import annotations

import pytest

from tests.ports.boundary import dump_private_rows, private_rows_problems, verdict_problems
from tests.ports.test_boundary_gates import _mutated, _private_data, _private_with, _verdict_text

_TEXT_KEYS = ("description", "inputs", "outputs", "reason")


def _ledger_problems(data: dict) -> list[str]:
    """Validate the canonical text of *data*, the way a crossed file is validated."""
    return private_rows_problems(dump_private_rows(data))


# ---------------------------------------------------------------------------
# Private ledger: null text cells
# ---------------------------------------------------------------------------


def test_the_untouched_fixtures_are_valid():
    """Guard for every case below: the starting points carry no problem of their own."""
    assert _ledger_problems(_private_data()) == []
    assert verdict_problems(_verdict_text()) == []


@pytest.mark.parametrize("key", _TEXT_KEYS)
def test_a_null_text_cell_is_rejected(key):
    # Row 1 is the dead/delete row and carries all four text keys.
    problems = _ledger_problems(_private_with(1, key, None))

    assert problems != []
    assert any(f"{key} must be a non-empty string" in p for p in problems), problems


def test_a_dead_delete_row_with_every_text_cell_null_is_rejected():
    """The reviewer's reproduction: nothing but nulls, and it authorised a deletion."""
    data = _private_data()
    for key in _TEXT_KEYS:
        data["rows"][1][key] = None

    problems = _ledger_problems(data)

    assert any("dead or delete row needs a reason" in p for p in problems), problems
    for key in _TEXT_KEYS:
        assert any(f"{key} must be a non-empty string" in p for p in problems), (key, problems)


@pytest.mark.parametrize("reason", [None, "", "   ", 0, False, [], {}])
def test_a_dead_or_delete_row_needs_a_reason_that_is_text(reason):
    problems = _ledger_problems(_private_with(1, "reason", reason))

    assert problems != []
    assert any("dead or delete row needs a reason" in p for p in problems), problems


def test_a_live_row_may_still_omit_the_reason():
    """Row 0 is scheduled/port and has no reason key: absent is fine, null is not."""
    data = _private_data()
    assert "reason" not in data["rows"][0]
    assert _ledger_problems(data) == []

    problems = _ledger_problems(_private_with(0, "reason", None))
    assert any("reason must be a non-empty string" in p for p in problems), problems


# ---------------------------------------------------------------------------
# Verdict list: no path and no script name in a free-text cell
# ---------------------------------------------------------------------------

_SCRIPTS = [
    "nightly_job.py",
    "run-scan.sh",
    "digest.ipynb",
    "config.yaml",
    "export.csv",
    # Review round 3 widened the list: any common file kind, not only the first nine.
    "load.sql",
    "settings.toml",
    "notes.txt",
    "jobs.db",
    "agent.plist",
    "samples.jsonl",
]
_PATHS = [
    "tools/nightly",
    "src/pipeline/score",
    "docs/sessions/notes",
    # Review round 3: the rule knew only word/word. A path is any slash or backslash.
    r"C:\work\pipeline",
    r"\\server\share\notes",
    r"notes\archive",
    "/tmp",
    "~/notes",
]


@pytest.mark.parametrize("key", _TEXT_KEYS)
@pytest.mark.parametrize("path", _PATHS)
def test_a_ledger_cell_holding_a_path_is_rejected(key, path):
    problems = _ledger_problems(_private_with(1, key, f"kept under {path} now"))

    assert any(f"{key} holds a path-like token" in p for p in problems), problems
    assert not any(path in p for p in problems), problems


@pytest.mark.parametrize("key", _TEXT_KEYS)
@pytest.mark.parametrize("script", _SCRIPTS)
def test_a_ledger_cell_naming_a_script_is_rejected(key, script):
    problems = _ledger_problems(_private_with(1, key, f"replaced {script} last quarter"))

    assert any(f"{key} holds a script filename" in p for p in problems), problems
    assert not any(script in p for p in problems), problems


@pytest.mark.parametrize("column", ["name", "reason"])
@pytest.mark.parametrize("script", _SCRIPTS)
def test_a_verdict_cell_naming_a_script_is_rejected(column, script):
    problems = verdict_problems(_mutated(0, column, f"replaced {script} last quarter"))

    assert any(f"{column} holds a script filename" in p for p in problems), problems
    assert not any(script in p for p in problems), problems


@pytest.mark.parametrize("column", ["name", "reason"])
@pytest.mark.parametrize("path", _PATHS)
def test_a_verdict_cell_holding_a_path_is_rejected(column, path):
    problems = verdict_problems(_mutated(0, column, f"lives under {path} today"))

    assert any(f"{column} holds a path-like token" in p for p in problems), problems
    assert not any(path in p for p in problems), problems


@pytest.mark.parametrize("column", ["name", "reason"])
def test_plain_words_with_dots_and_dashes_are_not_mistaken_for_scripts(column):
    """The rule is about filenames and paths, not punctuation: these stay valid."""
    for text in ["v2.0 scope, kept as is", "scope-and-plan candidate", "ran e.g. weekly"]:
        assert verdict_problems(_mutated(0, column, text)) == [], text
    assert verdict_problems(_verdict_text()) == []
