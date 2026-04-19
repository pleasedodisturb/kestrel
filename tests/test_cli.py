"""Tests for the Typer CLI skeleton."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from typer.testing import CliRunner

from career_os.cli.main import app
from career_os.database import Base
from career_os.models.models import Profile

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

    import career_os.cli.main as cli_mod

    monkeypatch.setattr(cli_mod, "_get_session", lambda: testing_session_cls())

    session = testing_session_cls()
    profile = Profile(id=1, name="Test User", email="test@test.com", location="Frankfurt")
    session.add(profile)
    session.commit()

    yield session
    session.close()
    engine.dispose()


def test_career_help() -> None:
    """kestrel --help exits 0 and shows help text."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Kestrel" in result.output


def test_pipeline_subcommand_present() -> None:
    """kestrel --help lists pipeline as a subcommand."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "pipeline" in result.output


def test_pipeline_help() -> None:
    """career pipeline --help exits 0 and shows pipeline commands."""
    result = runner.invoke(app, ["pipeline", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output
    assert "add" in result.output
    assert "update" in result.output
    assert "stats" in result.output
    assert "follow-ups" in result.output


def test_pipeline_list(db_session) -> None:
    """career pipeline list exits 0."""
    result = runner.invoke(app, ["pipeline", "list"])
    assert result.exit_code == 0


def test_pipeline_stats(db_session) -> None:
    """career pipeline stats exits 0."""
    result = runner.invoke(app, ["pipeline", "stats"])
    assert result.exit_code == 0


def test_pipeline_follow_ups(db_session) -> None:
    """career pipeline follow-ups exits 0."""
    result = runner.invoke(app, ["pipeline", "follow-ups"])
    assert result.exit_code == 0
    assert "caught up" in result.output.lower() or "follow" in result.output.lower()
