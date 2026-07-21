"""Tests for the in-package ESCO occupations fixture consumer (G-1351 Phase B).

Uses the real bundled fixture (no mocks) — this is the wheel-install path the
ticket exists to prove: a pip-installed user with no `scripts/` directory must
still be able to populate `esco_occupations` via `importlib.resources`.

Also covers the `kestrel occupations load` CLI command (G-1351 3-pass review
F8): fresh DB, already-loaded, --force, and the friendly missing-table error.
"""

from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

from career_os.cli.main import app
from career_os.database import Base
from career_os.services.occupation_taxonomy import (
    count_occupations,
    load_bundled_occupations,
    populate_occupations,
)

MIN_FIXTURE_ROWS = 2900

runner = CliRunner()


def test_load_bundled_occupations_returns_full_pillar() -> None:
    rows = load_bundled_occupations()
    assert len(rows) >= MIN_FIXTURE_ROWS
    first = rows[0]
    assert "concept_uri" in first
    assert "preferred_label" in first


def test_populate_occupations_inserts_full_fixture(db_session: Session) -> None:
    assert count_occupations(db_session) == 0

    result = populate_occupations(db_session)

    assert result["inserted"] >= MIN_FIXTURE_ROWS
    assert result["skipped"] == 0
    assert result["already_loaded"] is False
    assert count_occupations(db_session) == result["inserted"]


def test_populate_occupations_is_idempotent(db_session: Session) -> None:
    first = populate_occupations(db_session)
    count_after_first = count_occupations(db_session)

    second = populate_occupations(db_session)

    assert second["inserted"] == 0
    assert second["skipped"] == count_after_first
    assert second["already_loaded"] is True
    # No duplicates: row count unchanged.
    assert count_occupations(db_session) == first["inserted"]


def test_populate_occupations_force_does_not_duplicate(db_session: Session) -> None:
    first = populate_occupations(db_session)
    count_after_first = count_occupations(db_session)

    forced = populate_occupations(db_session, force=True)

    # force=True re-scans and finds nothing genuinely missing.
    assert forced["inserted"] == 0
    assert count_occupations(db_session) == count_after_first
    assert count_occupations(db_session) == first["inserted"]


# ---------------------------------------------------------------------------
# F8 — `kestrel occupations load` CLI coverage
# ---------------------------------------------------------------------------


def _set_sqlite_pragmas(dbapi_conn, connection_record) -> None:  # noqa: ANN001
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _make_engine_with_tables():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _set_sqlite_pragmas)
    Base.metadata.create_all(bind=engine)
    return engine


def test_occupations_load_cli_fresh_db(monkeypatch) -> None:
    engine = _make_engine_with_tables()
    testing_session_cls = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    import career_os.cli.main as cli_mod

    monkeypatch.setattr(cli_mod, "_get_session", lambda: testing_session_cls())

    result = runner.invoke(app, ["occupations", "load"])

    assert result.exit_code == 0
    assert "Loaded" in result.output

    session = testing_session_cls()
    assert count_occupations(session) >= MIN_FIXTURE_ROWS
    session.close()
    engine.dispose()


def test_occupations_load_cli_already_loaded(monkeypatch) -> None:
    engine = _make_engine_with_tables()
    testing_session_cls = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    import career_os.cli.main as cli_mod

    monkeypatch.setattr(cli_mod, "_get_session", lambda: testing_session_cls())

    # First run: loads.
    first = runner.invoke(app, ["occupations", "load"])
    assert first.exit_code == 0

    # Second run: already loaded, no re-scan.
    second = runner.invoke(app, ["occupations", "load"])
    assert second.exit_code == 0
    assert "Already loaded" in second.output

    engine.dispose()


def test_occupations_load_cli_force(monkeypatch) -> None:
    engine = _make_engine_with_tables()
    testing_session_cls = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    import career_os.cli.main as cli_mod

    monkeypatch.setattr(cli_mod, "_get_session", lambda: testing_session_cls())

    first = runner.invoke(app, ["occupations", "load"])
    assert first.exit_code == 0

    forced = runner.invoke(app, ["occupations", "load", "--force"])
    assert forced.exit_code == 0
    assert "Loaded" in forced.output

    engine.dispose()


def test_occupations_load_cli_missing_table_friendly_error(monkeypatch) -> None:
    """A fresh DB without migrations applied (no esco_occupations table) must
    print a friendly message and exit(1) — never a raw traceback."""
    # No Base.metadata.create_all() — the table genuinely does not exist.
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    testing_session_cls = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    import career_os.cli.main as cli_mod

    monkeypatch.setattr(cli_mod, "_get_session", lambda: testing_session_cls())

    result = runner.invoke(app, ["occupations", "load"])

    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert "esco_occupations" in result.output.lower() or "table not found" in result.output

    engine.dispose()
