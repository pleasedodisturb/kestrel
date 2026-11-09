"""Privacy rows for the validators that run over private files before they cross.

``private_golden_problems``, ``gate_verdict_problems`` and the ``generate_golden.py``
paths that print their findings run locally over files exported from the private
pipeline, and again in CI. Two properties are pinned here:

* **home family.** The producer (``tools/job_scorer.py::geo_eligibility``) never
  returns the literal ``home``: its home verdicts are ``home_local`` and
  ``home_relocate``. Every record whose ``geo_class`` names a home-family class
  must carry ``Home-NN`` tokens in ``location`` and in every ``offices`` element,
  and a ``geo_class`` that is not a string is held to the same rule (fail closed).
* **no echo.** A problem string ends up in terminals, agent transcripts,
  summaries and CI logs, so it must never repeat a value read from the file it
  rejects. Each key and value position of every record shape is driven with a
  sentinel (plain, key-shaped, email-shaped, path-shaped and a city name); the
  validator must still report a problem and no sentinel may appear in it.

Every value in this module is synthetic. Sentinels that would trip the
repository's secret and PII gates are assembled from fragments at runtime.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import pytest

from career_os.services.geo.classifier import ALL_CLASSES
from tests.replay import _support as S
from tests.replay._support import (
    FAMILY_B_CLASSES,
    GOLDEN,
    dump_jsonl,
    gate_verdict_problems,
    manifest_problems,
    private_golden_problems,
)
from tests.replay.test_golden import (
    _clean_private_rows,
    _copy_golden,
    _family_b_args,
    _gate_files,
    _gate_line,
    _register_gate,
    _reset_private_classes,
    _run,
    _write_private,
)

_ELIG, _SCORING = "private_eligibility_verdicts", "private_scoring"
_DEDUP, _DIGEST, _SCAN = "private_dedup_verdicts", "private_digest", "private_scan_arrivals"
_HOME_CLASSES = (_ELIG, _SCORING)

# The illustrative home city of PINNED_GEO_CONFIG, never a value of any real config.
_VERBATIM = "Limerick"

# The producer's own vocabulary, so this module holds no second list of classes.
_HOME_FAMILY = sorted(c for c in ALL_CLASSES if "home" in c)
_NOT_HOME = sorted(c for c in ALL_CLASSES if "home" not in c)
_HOME_SPELLINGS = [*_HOME_FAMILY, "home", "HOME_LOCAL", "Home_Relocate", "second_home_region"]


# ---------------------------------------------------------------------------
# Finding 1: the home region is tokenised on every home-family record
# ---------------------------------------------------------------------------


def _home_rows(
    cls: str, geo_class: Any, *, location: str = "Home-01", offices: list[Any] | None = None
) -> list[dict[str, Any]]:
    """A clean sample whose first record carries *geo_class* where its class records it."""
    rows = _clean_private_rows(cls)
    record = rows[0]
    holder = record["output"] if cls == _ELIG else record["input"]
    holder["geo_class"] = geo_class
    record["input"]["location"] = location
    if offices is not None:
        record["input"]["offices"] = offices
    return rows


def _problems(directory: Path, cls: str, rows: list[dict[str, Any]]) -> list[str]:
    return private_golden_problems(_write_private(directory, cls, rows), cls)


def test_the_producer_returns_home_classes_other_than_the_literal_home():
    """The rule must follow the producer: its home verdicts are never spelled ``home``."""
    assert len(ALL_CLASSES) == 7
    assert "home" not in ALL_CLASSES
    assert _HOME_FAMILY == ["home_local", "home_relocate"]
    assert set(_NOT_HOME) == set(ALL_CLASSES) - set(_HOME_FAMILY)


@pytest.mark.parametrize("cls", _HOME_CLASSES)
@pytest.mark.parametrize("geo_class", _HOME_SPELLINGS)
def test_home_family_record_must_tokenise_its_location(tmp_path, cls, geo_class):
    tokenised = _problems(tmp_path / "ok", cls, _home_rows(cls, geo_class))
    verbatim = _problems(tmp_path / "bad", cls, _home_rows(cls, geo_class, location=_VERBATIM))

    assert tokenised == []
    assert any("home location not tokenised" in p for p in verbatim), verbatim


@pytest.mark.parametrize("cls", _HOME_CLASSES)
@pytest.mark.parametrize("geo_class", _NOT_HOME)
def test_record_outside_the_home_family_keeps_a_verbatim_location(tmp_path, cls, geo_class):
    rows = _home_rows(cls, geo_class, location=_VERBATIM, offices=[_VERBATIM])

    assert "home" not in geo_class
    assert _problems(tmp_path, cls, rows) == []


@pytest.mark.parametrize("cls", _HOME_CLASSES)
@pytest.mark.parametrize("geo_class", _HOME_FAMILY)
@pytest.mark.parametrize(
    ("offices", "accepted"),
    [
        ([], True),
        (["Home-01"], True),
        (["Home-01", "Home-02"], True),
        ([_VERBATIM], False),
        (["Home-01", _VERBATIM], False),
        ([_VERBATIM, "Home-01"], False),
    ],
    ids=["none", "one-token", "two-tokens", "verbatim", "token-then-verbatim", "verbatim-first"],
)
def test_home_family_record_must_tokenise_every_office(tmp_path, cls, geo_class, offices, accepted):
    problems = _problems(tmp_path, cls, _home_rows(cls, geo_class, offices=offices))

    assert (problems == []) is accepted, problems
    assert any("home offices not tokenised" in p for p in problems) is not accepted


@pytest.mark.parametrize("cls", _HOME_CLASSES)
@pytest.mark.parametrize(
    "geo_class",
    [7, None, True, ["home_local"], {"home_local": 1}],
    ids=["int", "null", "bool", "list", "object"],
)
def test_geo_class_that_is_not_a_string_is_held_to_the_home_rule(tmp_path, cls, geo_class):
    verbatim = _problems(tmp_path / "bad", cls, _home_rows(cls, geo_class, location=_VERBATIM))
    tokenised = _problems(tmp_path / "ok", cls, _home_rows(cls, geo_class))

    assert any("geo_class is not a" in p for p in verbatim), verbatim
    assert any("home location not tokenised" in p for p in verbatim), verbatim
    assert tokenised != []
    assert not any("home location not tokenised" in p for p in tokenised)


def test_scoring_record_without_a_geo_class_is_outside_the_home_rule(tmp_path):
    """``geo_class`` is optional on the scoring input; an absent key carries no verdict."""
    rows = _clean_private_rows(_SCORING)
    del rows[0]["input"]["geo_class"]
    rows[0]["input"]["location"] = _VERBATIM

    assert "geo_class" not in rows[0]["input"]
    assert _problems(tmp_path, _SCORING, rows) == []


def test_readme_states_the_home_family_rule():
    flat = " ".join((GOLDEN / "README.md").read_text(encoding="utf-8").split())
    assert "home-family" in flat
    assert "`home_local`" in flat
    assert "`home_relocate`" in flat
    assert "every `offices` element" in flat
    assert "whose `geo_class` is `home`" not in flat


# ---------------------------------------------------------------------------
# Finding 2: no problem string repeats a value read from the file
# ---------------------------------------------------------------------------

_SENTINELS = {
    "plain": "ZqxSentinel7731",
    "key": "s" + "k" + "-" + "abcdefghijklmnop1234",
    "email": "".join(("zq.owner", "@", "example", ".org")),
    "path": "/".join(("", "Users", "zqowner", "ledger-notes.md")),
    "city": _VERBATIM,
}
_LABELS = list(_SENTINELS)

_WRAPS = {"raw": lambda s: s, "listed": lambda s: [s], "keyed": lambda s: {s: s}}
_KEY_FORMS = {"plain": "{}", "at": "{}_at", "date": "{}_date"}

_OPTIONAL_POSTING_VALUES: dict[str, Any] = {
    "salary": "band-b",
    "posted": "2000-01",
    "age_days": 3,
    "offices": ["Remote, Europe"],
    "remote_policy": "hybrid",
    "tags": ["platform"],
    "search_keyword": "product manager",
    "job_id": "Req-101",
    "recruiter": "Person-11",
    "contact": "Person-12",
    "email": "Email-11",
    "description": "",
    "dream_tier": False,
    "blocked": False,
    "soft_flag": False,
    "api_submittable": True,
    "ats_family": "greenhouse",
}


def _leaks(texts: Iterable[str], sentinel: str) -> list[str]:
    """The texts that repeat *sentinel* in any letter case."""
    needle = sentinel.casefold()
    return [text for text in texts if needle in text.casefold()]


def _full_posting(posting: dict[str, Any], *, home: bool = False) -> dict[str, Any]:
    """*posting* with every optional contract field present and valid."""
    full = posting | copy.deepcopy(_OPTIONAL_POSTING_VALUES)
    if home:
        full["offices"] = ["Home-02"]
    return full


def _full_rows(cls: str) -> list[dict[str, Any]]:
    """A clean sample whose first two records carry every key the contract allows."""
    rows = _clean_private_rows(cls)
    for record in rows[:2]:
        rec_in, rec_out = record["input"], record["output"]
        if cls == _SCAN:
            record["output"] = _full_posting(rec_out)
        elif cls == _DEDUP:
            record["input"] = {side: _full_posting(rec_in[side]) for side in ("a", "b")}
        elif cls == _ELIG:
            record["input"] = _full_posting(rec_in, home="home" in rec_out["geo_class"])
            rec_out |= {"blocked": False, "soft_flag": False}
        elif cls == _SCORING:
            record["input"] = _full_posting(rec_in)
            rec_out |= {"estimated_salary": "band-b", "floored": False, "reason_code": "model_fit"}
    return rows


def _node_paths(value: Any, prefix: tuple[Any, ...] = ()) -> Iterator[tuple[Any, ...]]:
    """The path of every key and list element below *value*, depth first."""
    if isinstance(value, dict):
        children = list(value.items())
    elif isinstance(value, list):
        children = list(enumerate(value))
    else:
        children = []
    for step, child in children:
        yield (*prefix, step)
        yield from _node_paths(child, (*prefix, step))


def _at(root: Any, path: tuple[Any, ...]) -> Any:
    for step in path:
        root = root[step]
    return root


def _mutations(record: dict[str, Any], sentinel: str) -> list[tuple[str, Any, bool]]:
    """Every single-position mutation of *record*: ``(name, mutate, also_alone)``.

    A value position takes the sentinel as a string, inside a list and as the key
    and value of an object. A key position is renamed to the sentinel, with and
    without a date-like suffix. Every object also gains one unknown key. Names
    are built from the clean record's own keys, never from the sentinel.
    """
    found: list[tuple[str, Any, bool]] = []
    paths = list(_node_paths(record))
    for path in paths:
        where = "/".join(str(step) for step in path)
        for form, wrap in _WRAPS.items():

            def set_value(target: dict[str, Any], path=path, wrap=wrap) -> None:
                _at(target, path[:-1])[path[-1]] = wrap(sentinel)

            found.append((f"value {where} as {form}", set_value, form == "keyed"))
        if isinstance(path[-1], str):
            for form, template in _KEY_FORMS.items():

                def rename(target: dict[str, Any], path=path, template=template) -> None:
                    parent = _at(target, path[:-1])
                    parent[template.format(sentinel)] = parent.pop(path[-1])

                found.append((f"key {where} renamed ({form})", rename, False))
    for path in [(), *(p for p in paths if isinstance(_at(record, p), dict))]:
        where = "/".join(str(step) for step in path) or "record"

        def add_key(target: dict[str, Any], path=path) -> None:
            _at(target, path)[sentinel] = sentinel

        found.append((f"unknown key added to {where}", add_key, False))
    return found


def _walk_failures(
    mutations: list[tuple[str, Any, bool]], run: Any, sentinel: str
) -> tuple[list[str], int]:
    """Run every mutation; return what went wrong and how many validator runs were made.

    ``run(mutate, companion)`` returns the problems of the mutated file. With
    *companion* the walked record also carries a known defect, so the validator
    is reporting on that record while the sentinel sits in it. The ``keyed``
    form is run a second time with no other defect: an object where a scalar or
    a list of scalars belongs must be reported on its own at every position.
    """
    failures: list[str] = []
    runs = 0
    for name, mutate, also_alone in mutations:
        for companion in (True, False) if also_alone else (True,):
            mode = "with a known defect" if companion else "alone"
            runs += 1
            try:
                problems = run(mutate, companion)
            except Exception as exc:  # a validator never raises: a traceback is output too
                failures.append(f"{name} ({mode}): raised {type(exc).__name__}")
                continue
            if not problems:
                failures.append(f"{name} ({mode}): no problem reported")
            elif _leaks(problems, sentinel):
                failures.append(f"{name} ({mode}): the value is repeated in a problem")
    return failures, runs


@pytest.mark.parametrize("cls", FAMILY_B_CLASSES)
def test_full_sample_is_clean_and_carries_every_contract_key(tmp_path, cls):
    """The walked records hold every key of the contract, so every position is driven."""
    rows = _full_rows(cls)
    record = rows[0]
    posting_keys = S._POSTING_REQUIRED | S._POSTING_OPTIONAL
    shape = S.FAMILY_B_SHAPES[cls]

    assert _problems(tmp_path, cls, rows) == []
    assert set(record) == {"id", "month", "scrubbed", "profile_scope", "input", "output"}
    if cls == _SCAN:
        assert set(record["output"]) == posting_keys
        assert set(record["input"]) == shape["input"][0] | shape["input"][1]
    elif cls == _DEDUP:
        assert set(record["input"]["a"]) == set(record["input"]["b"]) == posting_keys
        assert set(record["output"]) == shape["output"][0] | shape["output"][1]
    elif cls == _DIGEST:
        assert set(record["input"]["config"]) == {"mode", "min_score", "hours_old"}
        assert set(record["input"]["counts"]) == {"arrived", "scored", "shortlisted"}
        assert set(record["output"]["rows"][0]) == set(S._DIGEST_ROW_KEYS)
    else:
        extra = {"geo_class"} if cls == _SCORING else set()
        assert set(record["input"]) == posting_keys | extra
        assert set(record["output"]) == shape["output"][0] | shape["output"][1]


# Every class once, plus the home record of the eligibility sample (its second row).
_WALKED = [*((cls, 0) for cls in FAMILY_B_CLASSES), (_ELIG, 1)]


@pytest.mark.parametrize("label", _LABELS)
@pytest.mark.parametrize(("cls", "index"), _WALKED, ids=[f"{c}-row{i}" for c, i in _WALKED])
def test_private_golden_problems_never_repeat_a_planted_value(tmp_path, cls, index, label):
    sentinel = _SENTINELS[label]
    base = _full_rows(cls)

    def run(mutate: Any, companion: bool) -> list[str]:
        rows = list(base)
        rows[index] = copy.deepcopy(base[index])
        if companion:
            rows[index]["profile_scope"] = "generic"
        mutate(rows[index])
        return _problems(tmp_path, cls, rows)

    mutations = _mutations(base[index], sentinel)
    failures, runs = _walk_failures(mutations, run, sentinel)

    assert runs > len(mutations) >= 40
    assert failures == []


def _config_reason(rows: list[dict[str, Any]], sentinel: str) -> None:
    rows[0]["output"]["reason_code"] = f"blocked_{sentinel}"


def _duplicate_pair(rows: list[dict[str, Any]], sentinel: str) -> None:
    rows[0]["id"] = sentinel
    rows[1]["input"] = copy.deepcopy(rows[0]["input"])
    rows[1]["output"] = copy.deepcopy(rows[0]["output"])


def _duplicate_ids(rows: list[dict[str, Any]], sentinel: str) -> None:
    rows[0]["id"] = rows[1]["id"] = sentinel


def _home_family_spelling(rows: list[dict[str, Any]], sentinel: str) -> None:
    rows[0]["output"]["geo_class"] = f"home_{sentinel}"
    rows[0]["input"]["location"] = sentinel
    rows[0]["input"]["offices"] = [sentinel]


def _every_month(rows: list[dict[str, Any]], sentinel: str) -> None:
    for row in rows:
        row["month"] = sentinel


# (case, class, mutation of the full rows): cross-record and whole-file rules.
_FILE_CASES: list[tuple[str, str, Any]] = [
    ("config-reason-code", _DEDUP, _config_reason),
    ("duplicate-pair", _SCORING, _duplicate_pair),
    ("duplicate-ids", _SCORING, _duplicate_ids),
    ("home-family-spelling", _ELIG, _home_family_spelling),
    ("every-month", _DIGEST, _every_month),
]

# (case, text appended to a clean file).
_RAW_CASES: list[tuple[str, Any]] = [
    ("not-json", lambda s: s + "\n"),
    ("not-an-object", lambda s: json.dumps([s]) + "\n"),
    ("not-canonical", lambda s: '{ "id" : ' + json.dumps(s) + " }\n"),
    ("bare-string", lambda s: json.dumps(s) + "\n"),
]


@pytest.mark.parametrize("label", _LABELS)
@pytest.mark.parametrize(("case", "cls", "mutate"), _FILE_CASES, ids=[c[0] for c in _FILE_CASES])
def test_private_golden_file_rules_never_repeat_a_planted_value(tmp_path, case, cls, mutate, label):
    sentinel = _SENTINELS[label]
    rows = _full_rows(cls)
    mutate(rows, sentinel)

    problems = _problems(tmp_path, cls, rows)

    assert problems != [], case
    assert _leaks(problems, sentinel) == []


@pytest.mark.parametrize("label", _LABELS)
@pytest.mark.parametrize(("case", "build"), _RAW_CASES, ids=[c[0] for c in _RAW_CASES])
def test_private_golden_line_rules_never_repeat_a_planted_value(tmp_path, case, build, label):
    sentinel = _SENTINELS[label]
    path = tmp_path / f"{_SCORING}.jsonl"
    path.write_text(dump_jsonl(_full_rows(_SCORING)) + build(sentinel), encoding="utf-8")

    problems = private_golden_problems(path, _SCORING)

    assert problems != [], case
    assert _leaks(problems, sentinel) == []


def test_private_golden_problems_name_the_line_and_the_rule(tmp_path):
    """A problem gives the position and the rule, and counts what it will not name."""
    rows = _full_rows(_SCORING)
    rows[2]["output"]["note"] = "free text"
    rows[2]["output"]["other"] = "free text"
    rows[3]["output"]["reason_code"] = "blocked_company"
    rows[4]["input"]["seen_at"] = "soon"
    rows[6]["input"] = copy.deepcopy(rows[5]["input"])
    rows[6]["output"] = copy.deepcopy(rows[5]["output"])

    problems = _problems(tmp_path, _SCORING, rows)

    assert len(rows) == 20
    assert problems == [
        "line 3 output: 2 unknown key(s)",
        "line 4 output: config-derived reason code",
        "line 5 input: 1 unknown key(s)",
        "line 5: date field (a key ending _at or _date) is not month-level",
        "line 7: duplicate input and output (same as line 6)",
    ]


def test_private_digest_counts_are_reported_by_contract_name_only(tmp_path):
    """A known count is named; a key the contract does not know is only counted."""
    rows = _full_rows(_DIGEST)
    rows[0]["input"]["counts"]["arrived"] = -1
    rows[1]["input"]["counts"]["seen"] = "many"

    problems = _problems(tmp_path, _DIGEST, rows)

    assert len(rows) == 4
    assert problems == [
        "line 1 counts: arrived is not a non-negative integer",
        "line 2 counts: 1 unknown key(s)",
    ]


@pytest.mark.parametrize("label", _LABELS)
def test_gate_verdict_problems_never_repeat_a_planted_value(tmp_path, label):
    sentinel = _SENTINELS[label]
    base = [_gate_line("fact"), _gate_line("voice", "fail")]

    def run(mutate: Any, companion: bool) -> list[str]:
        lines = copy.deepcopy(base)
        if companion:
            lines[1]["verdict"] = "maybe"
        mutate(lines[0])
        verdicts, drafts = _gate_files(tmp_path, lines)
        return gate_verdict_problems(verdicts, drafts)

    mutations = _mutations(base[0], sentinel)
    failures, runs = _walk_failures(mutations, run, sentinel)

    assert gate_verdict_problems(*_gate_files(tmp_path, base)) == []
    assert runs > len(mutations) >= 17
    assert failures == []


@pytest.mark.parametrize("label", _LABELS)
@pytest.mark.parametrize(("case", "build"), _RAW_CASES, ids=[c[0] for c in _RAW_CASES])
def test_gate_verdict_line_rules_never_repeat_a_planted_value(tmp_path, case, build, label):
    sentinel = _SENTINELS[label]
    verdicts, drafts = _gate_files(tmp_path, [_gate_line("fact"), _gate_line("voice")])
    verdicts.write_text(verdicts.read_text(encoding="utf-8") + build(sentinel), encoding="utf-8")

    problems = gate_verdict_problems(verdicts, drafts)

    assert problems != [], case
    assert _leaks(problems, sentinel) == []


# ---------------------------------------------------------------------------
# Finding 2: the generator's CLI output (stdout and stderr together)
# ---------------------------------------------------------------------------

_LEDGER = "schema: 1\nrows:\n  - id: P-01\n    private: true\n"

# (case, ledger bytes): a ledger the reader cannot use. The YAML parser's own
# error text quotes the offending line, so the error must be named by class only.
_LEDGER_CASES: list[tuple[str, Any]] = [
    ("unterminated", lambda s: f"rows: [unterminated {s}\n".encode()),
    ("rows-not-a-list", lambda s: f"schema: 1\nrows: 7\nnote: {json.dumps(s)}\n".encode()),
    ("not-utf8", lambda s: b"\xff\xfe" + s.encode()),
]


def _planted_scoring_rows(sentinel: str) -> list[dict[str, Any]]:
    """A scoring sample with the sentinel at an id, a key, a value and a cross-record rule."""
    rows = _full_rows(_SCORING)
    rows[0]["id"] = sentinel
    rows[0]["output"][sentinel] = sentinel
    rows[0]["output"]["reason_code"] = f"blocked_{sentinel}"
    rows[0]["input"][f"{sentinel}_at"] = sentinel
    rows[0]["input"]["geo_class"] = f"home_{sentinel}"
    rows[0]["input"]["location"] = sentinel
    rows[1]["input"] = copy.deepcopy(rows[0]["input"])
    rows[1]["output"] = copy.deepcopy(rows[0]["output"])
    return rows


def _printed(capsys: pytest.CaptureFixture[str]) -> str:
    captured = capsys.readouterr()
    return captured.out + captured.err


@pytest.mark.parametrize("label", _LABELS)
def test_register_private_dry_run_never_prints_a_planted_value(tmp_path, capsys, label):
    sentinel = _SENTINELS[label]
    copy_dir = _copy_golden(tmp_path)
    _reset_private_classes(copy_dir)
    ledger = tmp_path / "ledger.yaml"
    ledger.write_text(_LEDGER, encoding="utf-8")
    bad = _write_private(tmp_path / "export", _SCORING, _planted_scoring_rows(sentinel))
    argv = [*_family_b_args(copy_dir, "c" * 40), "--file", str(bad), "--producer-row", "P-01"]

    code = _run([*argv, "--ledger", str(ledger), "--dry-run"])
    printed = _printed(capsys)

    assert code == 1
    assert printed.count(f"FAIL {_SCORING}: line ") >= 4
    assert _leaks([printed], sentinel) == []


@pytest.mark.parametrize("label", _LABELS)
def test_register_private_gate_dry_run_never_prints_a_planted_value(tmp_path, capsys, label):
    sentinel = _SENTINELS[label]
    copy_dir = _copy_golden(tmp_path)
    _reset_private_classes(copy_dir)
    bad = tmp_path / "gate_export.jsonl"
    lines = [
        {"draft_id": sentinel, "gate": sentinel, "verdict": sentinel, "reason_code": sentinel},
        {sentinel: sentinel},
    ]
    bad.write_text(dump_jsonl(lines) + sentinel + "\n", encoding="utf-8")

    code = _register_gate(copy_dir, bad, "--dry-run")
    printed = _printed(capsys)

    assert code == 1
    assert printed.count(f"FAIL {S.GATE_CLASS}: line ") >= 4
    assert _leaks([printed], sentinel) == []


@pytest.mark.parametrize("label", _LABELS)
@pytest.mark.parametrize(("case", "build"), _LEDGER_CASES, ids=[c[0] for c in _LEDGER_CASES])
def test_register_private_reports_an_unreadable_ledger_without_its_content(
    tmp_path, capsys, case, build, label
):
    sentinel = _SENTINELS[label]
    copy_dir = _copy_golden(tmp_path)
    _reset_private_classes(copy_dir)
    ledger = tmp_path / "ledger.yaml"
    ledger.write_bytes(build(sentinel))
    clean = _write_private(tmp_path / "export", _SCORING, _full_rows(_SCORING))
    argv = [*_family_b_args(copy_dir, "c" * 40), "--file", str(clean), "--producer-row", "P-01"]

    code = _run([*argv, "--ledger", str(ledger), "--dry-run"])
    printed = _printed(capsys)

    assert code == 1, case
    assert f"FAIL {_SCORING}: " in printed
    assert _leaks([printed], sentinel) == []


@pytest.mark.parametrize("label", _LABELS)
def test_check_mode_never_prints_a_planted_value_of_a_frozen_private_golden(
    tmp_path, capsys, label
):
    sentinel = _SENTINELS[label]
    copy_dir = _copy_golden(tmp_path)
    _reset_private_classes(copy_dir)
    ledger = tmp_path / "ledger.yaml"
    ledger.write_text(_LEDGER, encoding="utf-8")
    placed = _write_private(copy_dir, _SCORING, _full_rows(_SCORING))
    argv = [*_family_b_args(copy_dir, "c" * 40), "--file", str(placed), "--producer-row", "P-01"]
    frozen = _run([*argv, "--ledger", str(ledger)])
    capsys.readouterr()
    _write_private(copy_dir, _SCORING, _planted_scoring_rows(sentinel))

    code = _run(["--check", "--golden-dir", str(copy_dir)])
    printed = _printed(capsys)

    assert (frozen, code) == (0, 1)
    assert printed.count(f"PROBLEM {_SCORING}: line ") >= 4
    assert _leaks([printed], sentinel) == []


@pytest.mark.parametrize("label", _LABELS)
@pytest.mark.parametrize(("case", "build"), _LEDGER_CASES, ids=[c[0] for c in _LEDGER_CASES])
def test_manifest_checker_reports_an_unreadable_ledger_without_its_content(
    tmp_path, capsys, case, build, label
):
    sentinel = _SENTINELS[label]
    copy_dir = _copy_golden(tmp_path)
    _reset_private_classes(copy_dir)
    ledger = tmp_path / "ledger.yaml"
    ledger.write_text(_LEDGER, encoding="utf-8")
    placed = _write_private(copy_dir, _SCORING, _full_rows(_SCORING))
    argv = [*_family_b_args(copy_dir, "c" * 40), "--file", str(placed), "--producer-row", "P-01"]
    frozen = _run([*argv, "--ledger", str(ledger)])
    capsys.readouterr()
    ledger.write_bytes(build(sentinel))

    problems = manifest_problems(copy_dir, private_ledger=ledger)

    assert frozen == 0, case
    assert len(problems) == 1
    assert problems[0].startswith(f"{_SCORING}: ")
    assert _leaks(problems, sentinel) == []
