"""Atomic, rotating SQLite snapshot of the Career-OS database.

Why this exists
---------------
On 2026-05-11 a downstream user's full job-search dataset (127 applications +
79 packages + 90 audit rows) was wiped by a single API call. The previous
recovery path was "hope a periodic backup happened to land in the right week."
This script makes recovery cheap and predictable:

  - Daily snapshot at a known location: data/snapshots/career_os-YYYY-MM-DD.db
  - Rotation keeps the last N days (default 7); older snapshots are pruned
  - SQLite online backup API (NOT plain ``cp``) so the snapshot is consistent
    even if the live DB is mid-transaction under WAL
  - Atomic publish: write to ``*.partial``, fsync, rename — a crash mid-script
    never leaves a corrupt file as the newest "good" snapshot

Usage
-----
    python tools/snapshot_db.py                 # default: data/career_os.db -> data/snapshots/
    python tools/snapshot_db.py --dry-run       # show what would happen, do not write
    python tools/snapshot_db.py --keep 14       # retain 14 days instead of 7
    python tools/snapshot_db.py --db PATH       # snapshot a different DB

Recovery
--------
    cp data/snapshots/career_os-2026-05-04.db data/career_os.db
    rm -f data/career_os.db-shm data/career_os.db-wal
    # restart the server, verify counts
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

DEFAULT_DB = Path("data/career_os.db")
DEFAULT_SNAPSHOT_DIR = Path("data/snapshots")
DEFAULT_KEEP = 7
SNAPSHOT_PREFIX = "career_os"


@dataclass
class SnapshotResult:
    snapshot_path: Path
    pruned: list[Path]
    dry_run: bool


def _snapshot_filename(when: date) -> str:
    return f"{SNAPSHOT_PREFIX}-{when.isoformat()}.db"


def _date_from_filename(name: str) -> date | None:
    prefix = f"{SNAPSHOT_PREFIX}-"
    suffix = ".db"
    if not (name.startswith(prefix) and name.endswith(suffix)):
        return None
    try:
        return date.fromisoformat(name[len(prefix):-len(suffix)])
    except ValueError:
        return None


def _list_snapshots(snapshot_dir: Path) -> list[Path]:
    if not snapshot_dir.exists():
        return []
    return sorted(
        p for p in snapshot_dir.iterdir()
        if p.is_file()
        and p.name.startswith(f"{SNAPSHOT_PREFIX}-")
        and p.name.endswith(".db")
    )


def _backup_sqlite(src: Path, dst: Path) -> None:
    """Use SQLite's online backup API to copy ``src`` to ``dst``.

    Reads the live DB consistently even with concurrent writers.
    """
    src_conn = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    try:
        dst_conn = sqlite3.connect(str(dst))
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()


def _fsync_file(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def snapshot(
    db_path: Path = DEFAULT_DB,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
    keep: int = DEFAULT_KEEP,
    when: date | None = None,
    dry_run: bool = False,
) -> SnapshotResult:
    """Create a dated snapshot and prune anything older than ``keep`` days.

    Today's snapshot replaces any previous one with the same date.
    """
    if not db_path.exists():
        raise FileNotFoundError(f"Source DB not found: {db_path}")
    when = when or date.today()

    target = snapshot_dir / _snapshot_filename(when)
    partial = target.with_suffix(target.suffix + ".partial")

    # Date-based retention: anything dated more than (keep - 1) days before
    # `when` is pruned. `keep=7` with today=2026-05-12 keeps 2026-05-06..12.
    # Filenames not matching the expected date pattern are left alone.
    cutoff = when - timedelta(days=keep - 1)
    existing = _list_snapshots(snapshot_dir)
    to_prune: list[Path] = []
    for p in existing:
        snap_date = _date_from_filename(p.name)
        if snap_date is not None and snap_date < cutoff:
            to_prune.append(p)

    if dry_run:
        return SnapshotResult(snapshot_path=target, pruned=to_prune, dry_run=True)

    snapshot_dir.mkdir(parents=True, exist_ok=True)
    if partial.exists():
        partial.unlink()
    _backup_sqlite(db_path, partial)
    _fsync_file(partial)
    os.replace(partial, target)
    _fsync_file(target)

    for p in to_prune:
        p.unlink()

    return SnapshotResult(snapshot_path=target, pruned=to_prune, dry_run=False)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB,
                        help=f"Source DB path (default: {DEFAULT_DB})")
    parser.add_argument("--snapshot-dir", type=Path, default=DEFAULT_SNAPSHOT_DIR,
                        help=f"Directory for snapshots (default: {DEFAULT_SNAPSHOT_DIR})")
    parser.add_argument("--keep", type=int, default=DEFAULT_KEEP,
                        help=f"Days of snapshots to retain (default: {DEFAULT_KEEP})")
    parser.add_argument("--dry-run", action="store_true", help="report only, do not write")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = snapshot(
            db_path=args.db,
            snapshot_dir=args.snapshot_dir,
            keep=args.keep,
            dry_run=args.dry_run,
        )
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    label = "[dry-run] would write" if result.dry_run else "wrote"
    print(f"{label}: {result.snapshot_path}")
    if result.pruned:
        verb = "would prune" if result.dry_run else "pruned"
        for p in result.pruned:
            print(f"  {verb}: {p}")
    elif args.dry_run:
        print("  nothing to prune")
    return 0


if __name__ == "__main__":
    sys.exit(main())
