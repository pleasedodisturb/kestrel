"""Tests for tools/build_label_set.py.

The load-bearing property is BLINDNESS: no filter-derived field may be reachable
from what the annotator sees. A leak does not crash anything and does not look
wrong in the output. It quietly turns "does the filter agree with the human"
into "does the human agree with the filter", and every downstream metric gets
*better* as the corruption gets worse. So the leak test here is written as an
allow-list over the visible keys, not a deny-list over known-bad ones: a new
field added to the item shape fails this test until someone decides, explicitly,
which side of the blind it belongs on.

The other two properties are unrecoverable-after-the-fact: per-stratum draw
probabilities and repeat tagging. Both are asserted at the point they are
written, because there is no later moment at which they could be checked.
"""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_label_set  # noqa: E402
from build_label_set import build_item, load_population, main, pick_repeats  # noqa: E402

# Everything an annotator is allowed to see. Anything else on the item is a bug.
VISIBLE_KEYS = {"index", "title", "company", "location", "description", "_hidden"}


def _make_db(tmp_path: Path, rows: list[dict]) -> Path:
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE discovered_jobs (
            id INTEGER PRIMARY KEY, title TEXT, company TEXT, location TEXT,
            url TEXT, description TEXT, remote INTEGER, fit_score REAL
        )
        """
    )
    conn.executemany(
        "INSERT INTO discovered_jobs VALUES (:id,:title,:company,:location,"
        ":url,:description,:remote,:fit_score)",
        rows,
    )
    conn.commit()
    conn.close()
    return db


def _row(i: int, location: str, *, desc_len: int = 600, remote: int = 0) -> dict:
    return {
        "id": i,
        "title": f"Engineer {i}",
        "company": f"Co {i}",
        "location": location,
        "url": f"https://example.test/{i}",
        "description": "x" * desc_len,
        "remote": remote,
        "fit_score": 7.5,
    }


@pytest.fixture
def profile():
    from career_os.services.geo import presets

    return presets.FRANKFURT_PROFILE


# ---------------------------------------------------------------- blindness


def test_visible_item_exposes_no_filter_derived_field():
    """The annotator payload carries only what a human reads off the posting."""
    rec = {
        "job_id": 1, "title": "T", "company": "C", "location": "Berlin",
        "url": "u", "description": "d", "remote": True,
        "geo_class": "home_relocate", "fit_score": 9.9,
    }
    item = build_item(rec, 1, "KEEP", repeat_of=None)

    assert set(item) == VISIBLE_KEYS, (
        f"unexpected top-level keys on the annotator item: {set(item) - VISIBLE_KEYS}. "
        "A new field must be explicitly placed above or below the blind."
    )

    # The specific things that would anchor a rater.
    visible = {k: v for k, v in item.items() if k != "_hidden"}
    blob = json.dumps(visible)
    for leaked in ("geo_class", "home_relocate", "fit_score", "9.9", "stratum", "KEEP"):
        assert leaked not in blob, f"{leaked!r} reachable without opening _hidden"


def test_every_filter_derived_field_is_under_hidden():
    rec = {
        "job_id": 42, "title": "T", "company": "C", "location": "L",
        "url": "u", "description": "d", "remote": False,
        "geo_class": "foreign", "fit_score": 3.0,
    }
    hidden = build_item(rec, 1, "DROP", repeat_of=None)["_hidden"]
    expected = (
        "job_id", "url", "stratum", "geo_class",
        "fit_score", "remote", "repeat", "repeat_of",
    )
    for field in expected:
        assert field in hidden, f"{field} must live under _hidden"


def test_leak_is_actually_detectable():
    """Mutation check: prove the blindness test above can fail.

    A guard never observed failing is not a guard. This mutates the item shape
    the way a careless edit would and asserts the allow-list catches it.
    """
    rec = {
        "job_id": 1, "title": "T", "company": "C", "location": "L",
        "url": "u", "description": "d", "remote": False,
        "geo_class": "home_local", "fit_score": 8.0,
    }
    item = build_item(rec, 1, "KEEP", repeat_of=None)
    item["fit_score"] = rec["fit_score"]  # the careless edit
    assert set(item) != VISIBLE_KEYS, "the allow-list failed to notice a leaked field"


# ------------------------------------------------------------ stratum weights


def test_meta_records_draw_probability_per_stratum(tmp_path, profile, capsys):
    """p_draw must be COMPUTED from the population, not assumed.

    Population sizes are chosen so that neither stratum's true p_draw is a
    round number (25 -> 0.4, 80 -> 0.125). An earlier version of this test used
    20 KEEP postings, making the true value exactly 0.5 -- so replacing the
    computation with the constant 0.5 passed. The assertion was fine; the
    fixture could not discriminate. Do not "simplify" these counts.
    """
    rows = [_row(i, "Frankfurt, Germany") for i in range(1, 26)]          # 25
    rows += [_row(i, "Austin, Texas, USA") for i in range(26, 106)]        # 80
    db = _make_db(tmp_path, rows)
    out = tmp_path / "ls.json"

    main(["--profile", "frankfurt", "--db", str(db), "--out", str(out),
          "--n-per-stratum", "10", "--n-repeats", "2"])

    meta = json.loads(out.read_text())["_meta"]
    keep, drop = meta["strata"]["KEEP"], meta["strata"]["DROP"]

    assert keep["sampled"] == 10 and drop["sampled"] == 10
    assert (keep["population"], drop["population"]) == (25, 80)

    # Exact values, not just "different from each other" -- a pair of wrong
    # constants would also be different from each other.
    assert keep["p_draw"] == pytest.approx(0.4)
    assert drop["p_draw"] == pytest.approx(0.125)

    # Balanced sample, unbalanced population: this inequality is the entire
    # reason the numbers have to be recorded at draw time.
    assert keep["p_draw"] != drop["p_draw"]
    assert meta["population_base_rate_keep"] == pytest.approx(25 / 105)


def test_population_split_uses_the_supplied_profile(tmp_path, profile):
    rows = [_row(1, "Frankfurt, Germany"), _row(2, "Austin, Texas, USA")]
    db = _make_db(tmp_path, rows)
    keep, drop = load_population(db, profile, min_desc=100)
    assert [r["job_id"] for r in keep] == [1]
    assert [r["job_id"] for r in drop] == [2]


# -------------------------------------------------------------- repeat items


def test_repeats_are_tagged_at_draw_time():
    sample = [
        ({"job_id": i, "geo_class": "home_local"}, "KEEP") for i in range(1, 6)
    ]
    import random

    chosen = pick_repeats(sample, 2, random.Random(0))
    items = [build_item(
        {**r, "title": "t", "company": "c", "location": "l", "url": "u",
         "description": "d", "remote": False, "fit_score": None},
        1, "REPEAT", repeat_of=r["job_id"]) for r in chosen]
    assert all(i["_hidden"]["repeat"] is True for i in items)
    assert all(i["_hidden"]["repeat_of"] is not None for i in items)


def test_repeats_prefer_the_decision_boundary():
    """Self-consistency measured on obvious items overstates the ceiling."""
    import random

    sample = [({"job_id": 1, "geo_class": "home_local"}, "KEEP"),
              ({"job_id": 2, "geo_class": "visa_free_relocate"}, "KEEP"),
              ({"job_id": 3, "geo_class": "foreign"}, "DROP"),
              ({"job_id": 4, "geo_class": "visa_required_relocate"}, "KEEP")]
    chosen = pick_repeats(sample, 2, random.Random(0))
    assert {r["job_id"] for r in chosen} == {2, 4}, "boundary items must be drawn first"


def test_repeat_shortfall_is_reported_not_silent(capsys):
    import random

    chosen = pick_repeats([({"job_id": 1, "geo_class": "foreign"}, "DROP")], 5, random.Random(0))
    assert len(chosen) == 1
    assert "only 1 repeat candidates" in capsys.readouterr().err


# ------------------------------------------------------------- determinism etc


def test_same_seed_produces_identical_output(tmp_path, profile):
    rows = [_row(i, "Frankfurt, Germany") for i in range(1, 16)]
    rows += [_row(i, "Austin, Texas, USA") for i in range(16, 31)]
    db = _make_db(tmp_path, rows)
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    for out in (a, b):
        main(["--profile", "frankfurt", "--db", str(db), "--out", str(out),
              "--n-per-stratum", "5", "--n-repeats", "2", "--seed", "99"])
    ja, jb = json.loads(a.read_text()), json.loads(b.read_text())
    assert ja["items"] == jb["items"]


def test_short_descriptions_are_excluded(tmp_path, profile, capsys):
    rows = [_row(1, "Frankfurt, Germany", desc_len=10),
            _row(2, "Frankfurt, Germany", desc_len=600)]
    db = _make_db(tmp_path, rows)
    keep, _ = load_population(db, profile, min_desc=500)
    assert [r["job_id"] for r in keep] == [2]
    assert "skipped 1 postings" in capsys.readouterr().err


def test_unknown_profile_fails_loudly_and_lists_options():
    with pytest.raises(SystemExit) as exc:
        build_label_set.load_profile("atlantis")
    assert "unknown profile" in str(exc.value)
    assert "frankfurt" in str(exc.value)


def test_profile_has_no_default():
    """A defaulted profile would label your postings against a stranger."""
    with pytest.raises(SystemExit):
        main(["--db", "/nonexistent"])


def test_missing_database_fails_loudly(tmp_path, profile):
    with pytest.raises(SystemExit) as exc:
        load_population(tmp_path / "nope.db", profile, min_desc=1)
    assert "no database" in str(exc.value)


def test_indices_are_assigned_after_shuffle(tmp_path, profile):
    """Order must not leak the stratum: strata are interleaved, not blocked."""
    rows = [_row(i, "Frankfurt, Germany") for i in range(1, 21)]
    rows += [_row(i, "Austin, Texas, USA") for i in range(21, 41)]
    db = _make_db(tmp_path, rows)
    out = tmp_path / "ls.json"
    main(["--profile", "frankfurt", "--db", str(db), "--out", str(out),
          "--n-per-stratum", "10", "--n-repeats", "0"])
    items = json.loads(out.read_text())["items"]

    assert [i["index"] for i in items] == list(range(1, len(items) + 1))
    strata = [i["_hidden"]["stratum"] for i in items]
    assert strata != sorted(strata), "items are still grouped by stratum after shuffle"
