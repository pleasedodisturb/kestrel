"""G-1578: starting the API or running the CSV migration never inserts demo rows.

The old ``seed_ghost_detection_records`` ran on every API boot and re-created
three fake applications (``GhostCo Applied``, ``GhostCo Interviewing``,
``RecentCo Applied``) whenever no ``source='seed'`` row existed, so deleting
them could never stick and they polluted every ghost check on a real DB.
Opt-in demo data lives in ``career_os.migration.demo_seed`` (``kestrel init``);
nothing seeds behind the user's back.
"""

from __future__ import annotations

import csv

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import career_os.migration.run_migration as run_migration_module
from career_os.database import Base
from career_os.models.models import Application, Profile

DEMO_COMPANIES = {"GhostCo Applied", "GhostCo Interviewing", "RecentCo Applied"}


@pytest.fixture
def temp_sessionmaker(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'boot.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(bind=engine, autocommit=False, autoflush=False)
    engine.dispose()


def _boot(monkeypatch, session_factory):
    import career_os.main as main_module

    monkeypatch.setattr(main_module, "SessionLocal", session_factory)
    monkeypatch.setattr(main_module, "_auto_migrate", lambda: None)
    monkeypatch.setattr(main_module, "_startup_populate_occupations", lambda: None)
    monkeypatch.setattr(main_module, "start_scheduler", lambda: None)
    monkeypatch.setattr(main_module, "stop_scheduler", lambda: None)
    monkeypatch.setattr(main_module, "start_ticktick_scheduler", lambda: None)
    monkeypatch.setattr(main_module, "stop_ticktick_scheduler", lambda: None)
    return main_module


def _applications(session_factory) -> list[tuple[str, str | None]]:
    db = session_factory()
    try:
        return [(a.company, a.source) for a in db.query(Application).all()]
    finally:
        db.close()


@pytest.mark.asyncio
async def test_boot_on_db_with_real_applications_adds_no_demo_rows(monkeypatch, temp_sessionmaker):
    db = temp_sessionmaker()
    profile = Profile(name="Owner")
    db.add(profile)
    db.commit()
    db.add(Application(profile_id=profile.id, company="RealCo", role="TPM", status="applied"))
    db.commit()
    db.close()

    main_module = _boot(monkeypatch, temp_sessionmaker)
    async with main_module.lifespan(main_module.app):
        pass

    rows = _applications(temp_sessionmaker)
    assert rows == [("RealCo", None)], rows


@pytest.mark.asyncio
async def test_boot_twice_after_demo_rows_deleted_keeps_them_gone(monkeypatch, temp_sessionmaker):
    """The original bug: delete the rows, restart, they come back."""
    main_module = _boot(monkeypatch, temp_sessionmaker)
    for _ in range(2):
        async with main_module.lifespan(main_module.app):
            pass
        db = temp_sessionmaker()
        db.query(Application).filter(Application.source == "seed").delete()
        db.commit()
        db.close()
        async with main_module.lifespan(main_module.app):
            pass

    rows = _applications(temp_sessionmaker)
    assert not [r for r in rows if r[1] == "seed" or r[0] in DEMO_COMPANIES], rows


@pytest.mark.asyncio
async def test_boot_on_empty_db_still_creates_default_profile(monkeypatch, temp_sessionmaker):
    main_module = _boot(monkeypatch, temp_sessionmaker)
    async with main_module.lifespan(main_module.app):
        pass

    db = temp_sessionmaker()
    try:
        assert db.query(Profile).count() == 1
        assert db.query(Application).count() == 0
    finally:
        db.close()


def test_csv_migration_adds_no_demo_rows(monkeypatch, temp_sessionmaker, tmp_path):
    csv_path = tmp_path / "applications.csv"
    with csv_path.open("w", newline="") as fh:
        csv.writer(fh).writerow(["company", "role", "status"])
    packages = tmp_path / "packages"
    packages.mkdir()

    monkeypatch.setattr(run_migration_module, "SessionLocal", temp_sessionmaker)
    results = run_migration_module.run_full_migration(csv_path=csv_path, packages_path=packages)

    assert "ghost_seed" not in results
    rows = _applications(temp_sessionmaker)
    assert not [r for r in rows if r[1] == "seed" or r[0] in DEMO_COMPANIES], rows
