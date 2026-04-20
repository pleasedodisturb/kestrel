"""Tests for the kestrel init interactive wizard command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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
    db_path = tmp_path / "test_init.db"
    url = f"sqlite:///{db_path}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _set_sqlite_pragmas)
    Base.metadata.create_all(bind=engine)
    testing_session_cls = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    # Patch _get_session in both init and main modules
    import career_os.cli.init as init_mod
    import career_os.cli.main as main_mod

    monkeypatch.setattr(init_mod, "_get_session", lambda: testing_session_cls())
    monkeypatch.setattr(main_mod, "_get_session", lambda: testing_session_cls())

    session = testing_session_cls()
    profile = Profile(id=1, name="Test User", email="test@test.com", location="Frankfurt")
    session.add(profile)
    session.commit()

    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def db_session_empty(monkeypatch, tmp_path):
    """Create a temporary SQLite database with tables but NO profile."""
    db_path = tmp_path / "test_init_empty.db"
    url = f"sqlite:///{db_path}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _set_sqlite_pragmas)
    Base.metadata.create_all(bind=engine)
    testing_session_cls = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    import career_os.cli.init as init_mod
    import career_os.cli.main as main_mod

    monkeypatch.setattr(init_mod, "_get_session", lambda: testing_session_cls())
    monkeypatch.setattr(main_mod, "_get_session", lambda: testing_session_cls())

    session = testing_session_cls()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def mock_tty():
    """Mock sys.stdin.isatty() to return True for interactive wizard tests."""
    mock_sys = MagicMock()
    mock_sys.stdin.isatty.return_value = True
    with patch("career_os.cli.init.sys", mock_sys):
        yield mock_sys


# ---------------------------------------------------------------------------
# CLI-04: --skip creates default profile
# ---------------------------------------------------------------------------


def test_init_skip(db_session) -> None:
    """kestrel init --skip creates profile and exits 0 with success message."""
    result = runner.invoke(app, ["init", "--skip"])
    assert result.exit_code == 0
    assert "Default profile created" in result.output or "profile" in result.output.lower()


def test_init_skip_no_existing_profile(db_session_empty) -> None:
    """kestrel init --skip creates a new profile when none exists."""
    result = runner.invoke(app, ["init", "--skip"])
    assert result.exit_code == 0
    # Command output confirms profile was created
    assert "Default profile created" in result.output or "profile" in result.output.lower()


# ---------------------------------------------------------------------------
# CLI-02: Happy path wizard
# ---------------------------------------------------------------------------


def test_init_happy_path(db_session, mock_tty) -> None:
    """kestrel init walks through questions, saves profile, exits 0."""
    answers = iter(["Alice", "Berlin", "Software Engineer", "80000-120000", "senior"])
    with patch("career_os.cli.init.Prompt.ask", side_effect=lambda *a, **kw: next(answers)):
        with patch("career_os.cli.init.Confirm.ask", return_value=True):
            result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "Profile saved" in result.output


# ---------------------------------------------------------------------------
# All answers skipped (empty)
# ---------------------------------------------------------------------------


def test_init_all_skipped(db_session, mock_tty) -> None:
    """kestrel init with all empty answers still completes without error."""
    with patch("career_os.cli.init.Prompt.ask", return_value=""):
        with patch("career_os.cli.init.Confirm.ask", return_value=True):
            result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "Profile saved" in result.output


# ---------------------------------------------------------------------------
# PROF-03: Confirmation rejected
# ---------------------------------------------------------------------------


def test_init_confirm_rejected(db_session, mock_tty) -> None:
    """kestrel init with Confirm.ask=False exits with 'Cancelled'."""
    with patch("career_os.cli.init.Prompt.ask", return_value="test"):
        with patch("career_os.cli.init.Confirm.ask", return_value=False):
            result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "Cancelled" in result.output


# ---------------------------------------------------------------------------
# CLI-03: Non-TTY detection
# ---------------------------------------------------------------------------


def test_non_tty_detection(db_session) -> None:
    """kestrel init in non-TTY environment exits with guidance message."""
    # Don't use mock_tty here -- we want isatty to return False
    with patch("career_os.cli.init.sys") as mock_sys:
        mock_sys.stdin.isatty.return_value = False
        result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "Non-interactive" in result.output or "non-interactive" in result.output.lower()
    assert "--skip" in result.output


# ---------------------------------------------------------------------------
# CLI-05: Step indicator
# ---------------------------------------------------------------------------


def test_step_indicator(db_session, mock_tty) -> None:
    """kestrel init shows 'Step X/5' progress indicator."""
    answers = iter(["a", "b", "c", "d", "e"])
    with patch("career_os.cli.init.Prompt.ask", side_effect=lambda *a, **kw: next(answers)):
        with patch("career_os.cli.init.Confirm.ask", return_value=True):
            result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "Step 1/5" in result.output
    assert "Step 5/5" in result.output


# ---------------------------------------------------------------------------
# CLI-08: Next-step suggestion
# ---------------------------------------------------------------------------


def test_next_step_suggestion(db_session, mock_tty) -> None:
    """kestrel init prints next-step suggestion after successful save."""
    answers = iter(["Alice", "Berlin", "SWE", "100k", "senior"])
    with patch("career_os.cli.init.Prompt.ask", side_effect=lambda *a, **kw: next(answers)):
        with patch("career_os.cli.init.Confirm.ask", return_value=True):
            result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "pipeline" in result.output.lower()


# ---------------------------------------------------------------------------
# CLI-01: First-run callback
# ---------------------------------------------------------------------------


def test_first_run_callback_shows_panel(db_session) -> None:
    """First-run callback shows Welcome Panel when onboarding incomplete."""
    # pipeline list will trigger the callback before trying to list apps
    result = runner.invoke(app, ["pipeline", "list"])
    # The callback should show "Welcome to Kestrel" because onboarding is incomplete
    assert "Welcome to Kestrel" in result.output


def test_first_run_callback_hidden_when_complete(db_session) -> None:
    """First-run callback does NOT show Panel when onboarding is complete."""
    from career_os.models.models import _utcnow
    from career_os.models.onboarding import OnboardingState

    # Mark all onboarding steps as complete
    now = _utcnow()
    state = OnboardingState(
        profile_id=1,
        current_step="completed",
        profile_started_at=now,
        profile_completed_at=now,
        demo_seeded_at=now,
        welcome_completed_at=now,
        tour_completed_at=now,
        feedback_prompted_at=now,
        completed_at=now,
    )
    db_session.add(state)
    db_session.commit()

    result = runner.invoke(app, ["pipeline", "list"])
    assert "Welcome to Kestrel" not in result.output


# ---------------------------------------------------------------------------
# D-14: Resume detection (--force)
# ---------------------------------------------------------------------------


def test_init_already_completed_shows_message(db_session, mock_tty) -> None:
    """kestrel init on already-completed profile shows 'already set up' message."""
    from career_os.models.models import _utcnow
    from career_os.models.onboarding import OnboardingState

    now = _utcnow()
    state = OnboardingState(
        profile_id=1,
        current_step="profile_completed",
        profile_started_at=now,
        profile_completed_at=now,
    )
    db_session.add(state)
    db_session.commit()

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "already set up" in result.output.lower() or "--force" in result.output


# ---------------------------------------------------------------------------
# D-14: Resume from last step (partial completion)
# ---------------------------------------------------------------------------


def test_resume_from_last_step(db_session, mock_tty) -> None:
    """kestrel init shows 'Welcome back' when profile started but not completed."""
    from career_os.models.models import _utcnow
    from career_os.models.onboarding import OnboardingState

    # Mark profile_started but NOT profile_completed
    now = _utcnow()
    state = OnboardingState(
        profile_id=1,
        current_step="profile_started",
        profile_started_at=now,
    )
    db_session.add(state)
    db_session.commit()

    answers = iter(["Alice", "Berlin", "SWE", "100k", "senior"])
    confirm_answers = iter([False, True])  # No to paste, Yes to save
    with patch("career_os.cli.init.Prompt.ask", side_effect=lambda *a, **kw: next(answers)):
        with patch(
            "career_os.cli.init.Confirm.ask",
            side_effect=lambda *a, **kw: next(confirm_answers),
        ):
            result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "Welcome back" in result.output or "Resuming" in result.output


def test_resume_prefills_existing_values(db_session, mock_tty) -> None:
    """kestrel init pre-fills existing profile values as defaults when resuming."""
    from career_os.models.models import _utcnow
    from career_os.models.onboarding import OnboardingState

    # Update profile with some existing values
    profile = db_session.query(Profile).first()
    profile.name = "Existing Name"
    profile.location = "Munich"

    # Mark profile_started but NOT profile_completed to trigger resume
    now = _utcnow()
    state = OnboardingState(
        profile_id=1,
        current_step="profile_started",
        profile_started_at=now,
    )
    db_session.add(state)
    db_session.commit()

    # Track the defaults passed to Prompt.ask
    prompt_defaults = []

    def capture_defaults(*args, **kwargs):
        prompt_defaults.append(kwargs.get("default", ""))
        return kwargs.get("default", "") or "test"

    confirm_answers = iter([False, True])  # No to paste, Yes to save
    with patch("career_os.cli.init.Prompt.ask", side_effect=capture_defaults):
        with patch(
            "career_os.cli.init.Confirm.ask",
            side_effect=lambda *a, **kw: next(confirm_answers),
        ):
            result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    # The first default should be "Existing Name" and second "Munich"
    assert "Existing Name" in prompt_defaults
    assert "Munich" in prompt_defaults


# ---------------------------------------------------------------------------
# PROF-02: Resume paste extraction
# ---------------------------------------------------------------------------


def test_resume_paste_extracts_email(db_session, mock_tty) -> None:
    """kestrel init shows extracted email when resume paste is accepted."""
    answers = iter(["Alice", "Berlin", "SWE", "100k", "senior"])
    confirm_answers = iter([True, True])  # Yes to paste, Yes to save
    with (
        patch("career_os.cli.init.Prompt.ask", side_effect=lambda *a, **kw: next(answers)),
        patch(
            "career_os.cli.init.Confirm.ask",
            side_effect=lambda *a, **kw: next(confirm_answers),
        ),
        patch(
            "career_os.cli.init.read_multiline_paste",
            return_value="Contact alice@test.com for details",
        ),
        patch(
            "career_os.cli.init.extract_skills_from_text",
            return_value=[],
        ),
    ):
        result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "alice@test.com" in result.output


def test_resume_paste_declined(db_session, mock_tty) -> None:
    """kestrel init skips paste step when user declines."""
    answers = iter(["Alice", "Berlin", "SWE", "100k", "senior"])
    confirm_answers = iter([False, True])  # No to paste, Yes to save
    with patch("career_os.cli.init.Prompt.ask", side_effect=lambda *a, **kw: next(answers)):
        with patch(
            "career_os.cli.init.Confirm.ask",
            side_effect=lambda *a, **kw: next(confirm_answers),
        ):
            result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "Found in your resume" not in result.output


def test_extracted_skills_saved(db_session, mock_tty) -> None:
    """kestrel init saves extracted skills to the Skill table."""
    from career_os.models.skills import Skill

    answers = iter(["Alice", "Berlin", "SWE", "100k", "senior"])
    confirm_answers = iter([True, True])  # Yes to paste, Yes to save
    with (
        patch("career_os.cli.init.Prompt.ask", side_effect=lambda *a, **kw: next(answers)),
        patch(
            "career_os.cli.init.Confirm.ask",
            side_effect=lambda *a, **kw: next(confirm_answers),
        ),
        patch(
            "career_os.cli.init.read_multiline_paste",
            return_value="I know Python and TypeScript very well",
        ),
        patch(
            "career_os.cli.init.extract_skills_from_text",
            return_value=["Python", "TypeScript"],
        ),
    ):
        result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "Skills" in result.output

    # Verify skills were saved to DB
    skills = db_session.query(Skill).filter(Skill.profile_id == 1).all()
    skill_names = [s.name for s in skills]
    assert "Python" in skill_names
    assert "TypeScript" in skill_names
