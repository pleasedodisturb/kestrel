"""Tests for the kestrel doctor health check command."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from typer.testing import CliRunner

from career_os.cli.main import app
from career_os.database import Base
from career_os.models.models import Application, Profile

runner = CliRunner()


def _set_sqlite_pragmas(dbapi_conn, connection_record) -> None:  # noqa: ANN001
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture()
def db_session(monkeypatch, tmp_path):
    """Create a temporary SQLite database with tables and a default profile."""
    db_path = tmp_path / "test.db"
    url = f"sqlite:///{db_path}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _set_sqlite_pragmas)
    Base.metadata.create_all(bind=engine)
    testing_session_cls = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    import career_os.cli.doctor as doctor_mod

    monkeypatch.setattr(doctor_mod, "_get_session", lambda: testing_session_cls())

    session = testing_session_cls()
    profile = Profile(id=1, name="Test User", email="test@test.com", location="Frankfurt")
    session.add(profile)
    session.commit()

    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def db_session_no_profile(monkeypatch, tmp_path):
    """Create a temporary SQLite database with tables but NO profile."""
    db_path = tmp_path / "test_empty.db"
    url = f"sqlite:///{db_path}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _set_sqlite_pragmas)
    Base.metadata.create_all(bind=engine)
    testing_session_cls = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    import career_os.cli.doctor as doctor_mod

    monkeypatch.setattr(doctor_mod, "_get_session", lambda: testing_session_cls())

    session = testing_session_cls()
    yield session
    session.close()
    engine.dispose()


def test_doctor_all_pass(db_session) -> None:
    """kestrel doctor with healthy DB + profile shows all green checks and exit code 0."""
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    # Should show pass indicators
    assert "Python" in result.output
    assert "Database" in result.output or "connected" in result.output
    assert "profile" in result.output.lower() or "Profile" in result.output


def test_doctor_missing_profile(db_session_no_profile) -> None:
    """kestrel doctor with missing profile shows red X with resolution."""
    result = runner.invoke(app, ["doctor"])
    # Should fail because no profile
    assert result.exit_code == 1
    # Should mention resolution
    assert "kestrel init" in result.output


def test_doctor_python_version_check(db_session) -> None:
    """kestrel doctor shows Python version check (always passes in test env)."""
    result = runner.invoke(app, ["doctor"])
    assert "Python" in result.output


def test_doctor_db_connection_failure(monkeypatch) -> None:
    """kestrel doctor with DB connection failure shows red X with resolution."""
    import career_os.cli.doctor as doctor_mod

    def _broken_session():
        raise RuntimeError("Connection refused")

    monkeypatch.setattr(doctor_mod, "_get_session", _broken_session)

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    # Should not show a traceback
    assert "Traceback" not in result.output


def test_doctor_output_contains_header(db_session) -> None:
    """kestrel doctor output contains a health-related header."""
    result = runner.invoke(app, ["doctor"])
    output_lower = result.output.lower()
    assert "doctor" in output_lower or "health" in output_lower or "check" in output_lower


def test_doctor_shows_summary(db_session) -> None:
    """kestrel doctor shows a summary line like 'N/M checks passed'."""
    result = runner.invoke(app, ["doctor"])
    assert "checks passed" in result.output.lower() or "passed" in result.output.lower()


def test_doctor_no_stack_traces(db_session_no_profile) -> None:
    """kestrel doctor never shows stack traces even on failures."""
    result = runner.invoke(app, ["doctor"])
    assert "Traceback" not in result.output
    assert "raise " not in result.output
