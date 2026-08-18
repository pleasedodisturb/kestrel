"""End-to-end: build_label_set -> annotate -> calibrate.

The unit tests cover each stage in isolation, which is exactly why this file
exists: the stages agree on a contract that no single unit test looks at. The
sampler writes `_hidden.stratum`, `_hidden.repeat_of` and `_meta.strata[*].p_draw`;
the annotator keys labels by `index`; the calibrator reads all of those back and
divides by `p_draw`. A rename on either side of that boundary leaves every unit
test green and produces a report full of `n/a` -- or worse, a silently wrong
denominator.

This runs the three stages against a synthetic SQLite DB in a tmpdir and asserts
the numbers that can only be right if the whole chain lines up.
"""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import annotate as ann  # noqa: E402
import build_label_set as bls  # noqa: E402
import calibrate as cal  # noqa: E402

N_DE, N_US = 30, 70
PER_STRATUM, N_REPEATS = 12, 4


@pytest.fixture
def synthetic_db(tmp_path: Path) -> Path:
    db = tmp_path / "smoke.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """CREATE TABLE discovered_jobs (id INTEGER PRIMARY KEY, title TEXT, company TEXT,
           location TEXT, url TEXT, description TEXT, remote INTEGER, fit_score REAL)"""
    )
    rows = [
        (i, f"Engineer {i}", "Co DE", "Frankfurt, Germany", f"u{i}", "x" * 700, 0, 4.0 + i * 0.2)
        for i in range(1, N_DE + 1)
    ] + [
        (i, f"Engineer {i}", "Co US", "Austin, Texas, USA", f"u{i}", "y" * 700, 0, 3.0 + i * 0.05)
        for i in range(N_DE + 1, N_DE + N_US + 1)
    ]
    conn.executemany("INSERT INTO discovered_jobs VALUES (?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    return db


def _answers(n_items: int) -> list[str]:
    out: list[str] = []
    for i in range(n_items):
        out += ["y" if i % 2 == 0 else "n", "y" if i % 3 == 0 else "n"]
    return out


def test_pipeline_composes(synthetic_db, tmp_path):
    ls = tmp_path / "ls.json"
    log = tmp_path / "labels.jsonl"

    # --- stage 1 -------------------------------------------------------------
    assert bls.main([
        "--profile", "frankfurt", "--db", str(synthetic_db), "--out", str(ls),
        "--n-per-stratum", str(PER_STRATUM), "--n-repeats", str(N_REPEATS),
    ]) == 0

    data = json.loads(ls.read_text())
    items, meta = data["items"], data["_meta"]
    assert len(items) == PER_STRATUM * 2 + N_REPEATS

    # p_draw must reflect the real, unequal populations. These are the numbers
    # the calibrator divides by; if the sampler stops recording them honestly
    # every downstream rate is wrong in a way nothing else notices.
    assert meta["strata"]["KEEP"]["p_draw"] == pytest.approx(PER_STRATUM / N_DE)
    assert meta["strata"]["DROP"]["p_draw"] == pytest.approx(PER_STRATUM / N_US)
    assert meta["strata"]["KEEP"]["p_draw"] != meta["strata"]["DROP"]["p_draw"]

    # --- stage 2 -------------------------------------------------------------
    it = iter(_answers(len(items)))
    written = ann.annotate(items, {}, log, reader=lambda _p: next(it))
    assert written == len(items)

    labels = ann.load_labels(log)
    assert set(labels) == {i["index"] for i in items}

    # --- stage 3 -------------------------------------------------------------
    # The cross-stage joins: repeats pair by job_id, and every stratum resolves
    # to a weight. Either failing yields an empty or mis-weighted report.
    pairs = cal.repeat_pairs(items, labels)
    assert len(pairs) == N_REPEATS, "repeat_of -> job_id join broke across stages"

    conf = cal.weighted_confusion(items, labels, meta, "can_win_cold")
    assert sum(conf.values()) > 0
    # Repeats excluded: 24 real items, each weighted, so the total weight is the
    # sum of 1/p_draw over the non-repeat items only.
    expected_total = PER_STRATUM * (N_DE / PER_STRATUM) + PER_STRATUM * (N_US / PER_STRATUM)
    assert sum(conf.values()) == pytest.approx(expected_total)

    report = cal.build_report(data, labels, n_boot=120)
    for required in ("CALIBRATION REPORT", "not training", "CEILING", "NOT accuracy",
                     "not the population"):
        assert required in report, f"report lost its {required!r} guard"
    assert "n/a" not in report.split("SUGGESTED CUTOFF")[0], (
        "a statistic came back n/a, which means a cross-stage key stopped lining up"
    )


def test_calibrate_survives_a_partially_labelled_set(synthetic_db, tmp_path):
    """Stopping halfway is the normal case, not an error path."""
    ls = tmp_path / "ls.json"
    log = tmp_path / "labels.jsonl"
    bls.main([
        "--profile", "frankfurt", "--db", str(synthetic_db), "--out", str(ls),
        "--n-per-stratum", str(PER_STRATUM), "--n-repeats", str(N_REPEATS),
    ])
    data = json.loads(ls.read_text())
    items = data["items"]

    it = iter(_answers(6) + ["q"])
    ann.annotate(items, {}, log, reader=lambda _p: next(it))
    labels = ann.load_labels(log)
    assert 0 < len(labels) < len(items)

    report = cal.build_report(data, labels, n_boot=60)
    assert f"{len(labels)} labelled" in report
