"""Tests for tools.snapshot_db — atomic, rotating SQLite snapshots."""

from __future__ import annotations

import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from snapshot_db import (  # noqa: E402
    SNAPSHOT_PREFIX,
    _list_snapshots,
    snapshot,
)


@pytest.fixture
def live_db(tmp_path: Path) -> Path:
    """A live SQLite DB with one row, returned as a Path."""
    db_path = tmp_path / "career_os.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("CREATE TABLE apps (id INTEGER, name TEXT);")
    conn.execute("INSERT INTO apps VALUES (1, 'Acme')")
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def snapshot_dir(tmp_path: Path) -> Path:
    return tmp_path / "snapshots"


def _row_count(db: Path) -> int:
    conn = sqlite3.connect(str(db))
    try:
        return conn.execute("SELECT COUNT(*) FROM apps").fetchone()[0]
    finally:
        conn.close()


def _seed_snapshot(snapshot_dir: Path, when: date) -> Path:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    p = snapshot_dir / f"{SNAPSHOT_PREFIX}-{when.isoformat()}.db"
    sqlite3.connect(str(p)).close()
    return p


class TestSnapshotCreation:
    def test_creates_snapshot_with_data(self, live_db: Path, snapshot_dir: Path):
        result = snapshot(db_path=live_db, snapshot_dir=snapshot_dir, keep=7)
        assert result.snapshot_path.exists()
        assert _row_count(result.snapshot_path) == 1

    def test_filename_is_iso_dated(self, live_db: Path, snapshot_dir: Path):
        today = date(2026, 5, 12)
        result = snapshot(db_path=live_db, snapshot_dir=snapshot_dir, when=today, keep=7)
        assert result.snapshot_path.name == f"{SNAPSHOT_PREFIX}-2026-05-12.db"

    def test_dry_run_writes_nothing(self, live_db: Path, snapshot_dir: Path):
        result = snapshot(db_path=live_db, snapshot_dir=snapshot_dir, keep=7, dry_run=True)
        assert result.dry_run is True
        assert not result.snapshot_path.exists()
        assert not snapshot_dir.exists()

    def test_missing_source_raises(self, tmp_path: Path, snapshot_dir: Path):
        with pytest.raises(FileNotFoundError):
            snapshot(db_path=tmp_path / "does-not-exist.db", snapshot_dir=snapshot_dir)

    def test_overwrites_same_day_snapshot(self, live_db: Path, snapshot_dir: Path):
        today = date(2026, 5, 12)
        snapshot(db_path=live_db, snapshot_dir=snapshot_dir, when=today, keep=7)
        # Add another row, snapshot again on the same day.
        conn = sqlite3.connect(str(live_db))
        conn.execute("INSERT INTO apps VALUES (2, 'Globex')")
        conn.commit()
        conn.close()
        result = snapshot(db_path=live_db, snapshot_dir=snapshot_dir, when=today, keep=7)
        assert _row_count(result.snapshot_path) == 2


class TestRotation:
    def test_prunes_beyond_keep_window(self, live_db: Path, snapshot_dir: Path):
        today = date(2026, 5, 12)
        # Seed 9 prior dated snapshots, oldest first.
        seeded = [_seed_snapshot(snapshot_dir, today - timedelta(days=i)) for i in range(9, 0, -1)]
        result = snapshot(db_path=live_db, snapshot_dir=snapshot_dir, when=today, keep=7)
        remaining = _list_snapshots(snapshot_dir)
        # 7-day window includes today's new one + 6 most-recent prior.
        assert len(remaining) == 7
        assert result.snapshot_path in remaining
        # The two oldest from the seed should be in the pruned set.
        assert seeded[0] in result.pruned
        assert seeded[1] in result.pruned
        # The newest two seed entries should survive.
        assert seeded[-1] in remaining
        assert seeded[-2] in remaining

    def test_keep_one_only_today_survives(self, live_db: Path, snapshot_dir: Path):
        today = date(2026, 5, 12)
        _seed_snapshot(snapshot_dir, today - timedelta(days=1))
        _seed_snapshot(snapshot_dir, today - timedelta(days=2))
        result = snapshot(db_path=live_db, snapshot_dir=snapshot_dir, when=today, keep=1)
        remaining = _list_snapshots(snapshot_dir)
        assert remaining == [result.snapshot_path]

    def test_dry_run_reports_prune_set_without_acting(self, live_db: Path, snapshot_dir: Path):
        today = date(2026, 5, 12)
        old = _seed_snapshot(snapshot_dir, today - timedelta(days=30))
        result = snapshot(
            db_path=live_db, snapshot_dir=snapshot_dir, when=today, keep=7, dry_run=True
        )
        assert old in result.pruned
        # Nothing was actually written or pruned.
        assert old.exists()
        assert not result.snapshot_path.exists()


class TestAtomicity:
    def test_no_partial_file_lingers_on_success(self, live_db: Path, snapshot_dir: Path):
        snapshot(db_path=live_db, snapshot_dir=snapshot_dir, keep=7)
        partials = list(snapshot_dir.glob("*.partial"))
        assert partials == []

    def test_snapshot_isolated_from_live_writes(self, live_db: Path, snapshot_dir: Path):
        """A snapshot taken before a write must not reflect that write."""
        result = snapshot(db_path=live_db, snapshot_dir=snapshot_dir, keep=7)
        conn = sqlite3.connect(str(live_db))
        conn.execute("INSERT INTO apps VALUES (99, 'AfterSnapshot')")
        conn.commit()
        conn.close()
        assert _row_count(result.snapshot_path) == 1
        assert _row_count(live_db) == 2
