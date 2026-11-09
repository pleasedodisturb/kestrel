"""Inventory meta-test for the v2.0 mapping tables (Phase 11 Map, MAP-03).

Guards the guard: the engine in ``test_mapping_tables.py`` only proves anything
while the tables are well formed, pinned, and every pending row carries a strict
xfail that expects ``NotBuilt``. These tests fail when a table loses or gains an
unpinned row, when a structure rule is broken, or when a mark weakens, and they
prove the checker with deliberately bad tables of their own.

Renumbering a phase is a search-and-replace of its ``phase:`` field, its
filename and its pin below.
"""

import copy

import pytest
import yaml

from tests.targets._support import (
    TABLES_DIR,
    NotBuilt,
    Table,
    TableError,
    build_params,
    load_tables,
    load_target,
    observe_row,
    project,
    read_table,
    table_problems,
)

# Rows per table file. Deleting or adding a row without touching this pin fails
# the build, so a rewrite of a table is always a visible, deliberate diff.
EXPECTED_ROWS = {
    "phase_15_filter": 12,
}


def _mark_names(param):
    return [mark.name for mark in param.marks]


def test_tables_have_no_structural_problems():
    """Every shipped table passes the structural checker."""
    tables = load_tables(validate=False)
    problems = [p for table in tables for p in table_problems(table, filename_stem=table.stem)]
    assert tables
    assert problems == []


def test_row_counts_match_pins():
    """Each file's row total equals its EXPECTED_ROWS pin."""
    counts = {table.stem: table.row_count() for table in load_tables(validate=False)}
    assert counts == EXPECTED_ROWS
    assert sum(counts.values()) == sum(EXPECTED_ROWS.values())


def test_every_table_file_is_pinned():
    """No table file exists without a pin, and no pin names a missing file."""
    stems = {table.stem for table in load_tables(validate=False)}
    assert stems == set(EXPECTED_ROWS)
    assert len(stems) == len(EXPECTED_ROWS)


def test_pending_params_carry_strict_xfail_and_v2_pending():
    """Pending rows have v2_pending and a strict, NotBuilt-pinned xfail with the exact reason."""
    tables = load_tables(validate=False)
    params = build_params(tables)
    assert len(params) == sum(EXPECTED_ROWS.values())
    for param in params:
        table = param.values[0]
        names = _mark_names(param)
        if not table.pending:
            assert names == [], f"{param.id}: a table with pending: false must carry no marks"
            continue
        assert names.count("v2_pending") == 1, f"{param.id}: missing v2_pending"
        xfails = [mark for mark in param.marks if mark.name == "xfail"]
        assert len(xfails) == 1, f"{param.id}: expected exactly one xfail mark"
        assert xfails[0].kwargs == {
            "strict": True,
            "raises": NotBuilt,
            "reason": f"v2.0 Phase {table.phase}",
        }, f"{param.id}: xfail must be strict, raises=NotBuilt, exact reason"


def test_param_ids_follow_file_order():
    """Ids are phase_NN_name::table::row-id, in YAML order, identical across runs."""
    expected = []
    for table in load_tables(validate=False):
        raw = yaml.safe_load((TABLES_DIR / f"{table.stem}.yaml").read_text(encoding="utf-8"))
        for table_name, body in raw["tables"].items():
            expected.extend(f"{table.stem}::{table_name}::{row['id']}" for row in body["rows"])
    first = [param.id for param in build_params(load_tables(validate=False))]
    second = [param.id for param in build_params(load_tables(validate=False))]
    assert first == expected
    assert second == first
    assert len(set(first)) == len(first)


def test_pending_false_drops_marks_for_that_phase_only():
    """Flipping one table to pending: false removes only that table's marks."""
    body = {
        "target": "career_os.services.example:thing",
        "rows": [{"id": "a", "input": {}, "expect": {"x": 1}}],
    }
    header = {"title": "T", "status": "PROVISIONAL", "sources": ["s"], "tables": {"t": body}}
    pending = Table("phase_15_filter", {**header, "phase": 15, "name": "filter", "pending": True})
    done = Table("phase_16_scan", {**header, "phase": 16, "name": "scan", "pending": False})
    params = build_params([pending, done])
    assert [_mark_names(p) for p in params] == [["v2_pending", "xfail"], []]
    assert [p.id for p in params] == ["phase_15_filter::t::a", "phase_16_scan::t::a"]


def _good_table():
    """A minimal well-formed table dict, used as the base for the bad-table cases."""
    return {
        "phase": 15,
        "name": "filter",
        "title": "Filter",
        "status": "PROVISIONAL until review",
        "pending": True,
        "sources": ["SUMMARY.md"],
        "tables": {
            "decision": {
                "target": "career_os.services.assess:assess",
                "rows": [
                    {"id": "one", "input": {"job": "a"}, "expect": {"decision": "admit"}},
                    {"id": "two", "input": {"job": "b"}, "expect": {"decision": "exclude"}},
                ],
            }
        },
    }


def _rows(data):
    return data["tables"]["decision"]["rows"]


def _duplicate_id(data):
    _rows(data)[1]["id"] = "one"


def _contradiction(data):
    _rows(data)[1]["input"] = {"job": "a"}


def _zero_rows(data):
    data["tables"]["decision"]["rows"] = []


def _empty_expect(data):
    _rows(data)[0]["expect"] = {}


def _target_outside_package(data):
    data["tables"]["decision"]["target"] = "json.tool:main"


def _target_malformed(data):
    data["tables"]["decision"]["target"] = "career_os.services.assess.assess"


def _row_missing_input(data):
    del _rows(data)[0]["input"]


def _row_extra_key(data):
    _rows(data)[0]["notes"] = "free text"


def _bad_row_id(data):
    _rows(data)[0]["id"] = "Not Valid"


def _status_not_provisional(data):
    data["status"] = "FINAL"


def _pending_not_bool(data):
    data["pending"] = "yes"


def _pending_decision_not_strings(data):
    data["pending_decision"] = [1, 2]


def _no_sources(data):
    data["sources"] = []


def _phase_13(data):
    data["phase"] = 13


def _keep(data):
    """Leave the table unchanged; the filename alone is the defect."""


def _unknown_header_key(data):
    data["pendng"] = True


BAD_TABLES = [
    ("duplicate-id", "phase_15_filter", _duplicate_id, "duplicate row id"),
    ("contradiction", "phase_15_filter", _contradiction, "contradicts"),
    ("zero-rows", "phase_15_filter", _zero_rows, "no rows"),
    ("empty-expect", "phase_15_filter", _empty_expect, "empty expect"),
    ("phase-filename-mismatch", "phase_16_filter", _keep, "does not match the filename number"),
    ("phase-13", "phase_13_filter", _phase_13, "outside 14..21"),
    ("target-outside-package", "phase_15_filter", _target_outside_package, "'json.tool:main'"),
    (
        "target-malformed",
        "phase_15_filter",
        _target_malformed,
        "'career_os.services.assess.assess'",
    ),
    ("row-missing-input", "phase_15_filter", _row_missing_input, "missing ['input']"),
    ("row-extra-key", "phase_15_filter", _row_extra_key, "extra ['notes']"),
    ("bad-row-id", "phase_15_filter", _bad_row_id, "'Not Valid'"),
    ("status-not-provisional", "phase_15_filter", _status_not_provisional, "PROVISIONAL"),
    ("pending-not-bool", "phase_15_filter", _pending_not_bool, "pending must be a boolean"),
    (
        "pending-decision-not-strings",
        "phase_15_filter",
        _pending_decision_not_strings,
        "pending_decision must be a list of strings",
    ),
    ("no-sources", "phase_15_filter", _no_sources, "sources must be a non-empty list"),
    ("unknown-header-key", "phase_15_filter", _unknown_header_key, "unexpected header keys"),
    ("bad-filename", "phase_filter", _keep, "filename must be phase_NN_name.yaml"),
]


def test_checker_accepts_the_good_base_table(tmp_path):
    """The base table used by the bad-table cases is itself clean (the cases are not vacuous)."""
    path = tmp_path / "phase_15_filter.yaml"
    path.write_text(yaml.safe_dump(_good_table()), encoding="utf-8")
    problems = table_problems(read_table(path), filename_stem=path.stem)
    assert problems == []
    assert read_table(path).row_count() == 2


@pytest.mark.parametrize(
    ("case", "stem", "mutate", "expected"), BAD_TABLES, ids=[case[0] for case in BAD_TABLES]
)
def test_table_checker_flags_bad_tables(tmp_path, case, stem, mutate, expected):
    """Each deliberately bad table yields its own specific problem."""
    data = copy.deepcopy(_good_table())
    mutate(data)
    path = tmp_path / f"{stem}.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    problems = table_problems(read_table(path), filename_stem=stem)
    assert problems
    assert any(expected in problem for problem in problems), (expected, problems)


def test_load_tables_rejects_a_malformed_directory(tmp_path):
    """The engine's strict load fails on a bad table; the inventory's lenient load does not."""
    data = _good_table()
    _zero_rows(data)
    (tmp_path / "phase_15_filter.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(TableError, match="no rows") as info:
        load_tables(tmp_path)
    assert "phase_15_filter::decision" in str(info.value)
    assert [t.stem for t in load_tables(tmp_path, validate=False)] == ["phase_15_filter"]


def test_load_target_raises_not_built_only_for_missing_targets(tmp_path, monkeypatch):
    """A missing module or attribute reads as pending; a broken import inside a module does not."""
    with pytest.raises(NotBuilt):
        load_target("career_os.services.no_such_module_for_map03:thing")
    with pytest.raises(NotBuilt):
        load_target("career_os.config:no_such_attribute_for_map03")
    from career_os.config import settings

    assert load_target("career_os.config:settings") is settings

    package = tmp_path / "pkg_map03_broken"
    package.mkdir()
    (package / "__init__.py").write_text(
        "import module_that_does_not_exist_map03\n", encoding="utf-8"
    )
    nested = tmp_path / "pkg_map03_nested"
    nested.mkdir()
    (nested / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(ModuleNotFoundError) as info:
        load_target("pkg_map03_broken:thing")
    assert info.value.name == "module_that_does_not_exist_map03"
    assert not isinstance(info.value, NotBuilt)
    with pytest.raises(NotBuilt):
        load_target("pkg_map03_nested.child:thing")


def test_load_target_rejects_a_spec_without_an_attribute():
    """A spec that is not module:attr is a programming error, not a pending target."""
    with pytest.raises(ValueError, match="dotted.module:attr") as no_attr:
        load_target("career_os.config")
    with pytest.raises(ValueError, match="dotted.module:attr") as no_module:
        load_target(":settings")
    assert "'career_os.config'" in str(no_attr.value)
    assert "':settings'" in str(no_module.value)


def test_project_reads_mappings_and_objects_and_raises_on_missing_keys():
    """project() reads expected keys from either shape and never invents a missing one."""

    class Result:
        decision = "admit"
        reason_codes = ()

    assert project({"decision": "admit", "extra": 1}, ["decision"]) == {"decision": "admit"}
    assert project(Result(), ["decision", "reason_codes"]) == {
        "decision": "admit",
        "reason_codes": (),
    }
    with pytest.raises(KeyError):
        project({"decision": "admit"}, ["geo_class"])
    with pytest.raises(AttributeError):
        project(Result(), ["geo_class"])


def test_engine_observation_is_not_vacuous_against_a_built_target(tmp_path, monkeypatch):
    """With a real target, observe_row returns the real output, so a wrong expect would differ."""
    package = tmp_path / "pkg_map03_target"
    package.mkdir()
    (package / "__init__.py").write_text(
        "def double(*, x):\n    return {'value': x * 2, 'unused': 0}\n", encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    row = {"id": "r", "input": {"x": 4}, "expect": {"value": 8}}
    observed = observe_row("pkg_map03_target:double", row)
    assert observed == row["expect"]
    assert observed != {"value": 9}
