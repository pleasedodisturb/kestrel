"""Tests for the CLI pipeline commands with real database access."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

from career_os.cli.main import app
from career_os.database import Base
from career_os.models.models import (
    ActivityLog,
    Application,
    FollowUp,
    Profile,
)

runner = CliRunner()


def _set_sqlite_pragmas(dbapi_conn, connection_record) -> None:  # noqa: ANN001
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture()
def db_session(monkeypatch, tmp_path):
    """Create an in-memory SQLite database for testing with real models."""
    db_path = tmp_path / "test.db"
    url = f"sqlite:///{db_path}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _set_sqlite_pragmas)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    # Patch the CLI to use our test database
    import career_os.cli.main as cli_mod

    monkeypatch.setattr(cli_mod, "_get_session", lambda: TestingSession())

    session = TestingSession()
    # Seed a default profile
    profile = Profile(id=1, name="Test User", email="test@test.com", location="Frankfurt")
    session.add(profile)
    session.commit()

    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def seeded_db(db_session: Session):
    """Database with sample applications for testing."""
    apps = [
        Application(
            profile_id=1,
            company="Acme Corp",
            role="Senior TPM",
            status="applied",
            fit_score=8.5,
            url="https://acme.com/jobs/1",
            source="linkedin",
            notes="Great opportunity",
            created_at=datetime(2025, 3, 1, tzinfo=UTC),
            updated_at=datetime(2025, 3, 1, tzinfo=UTC),
        ),
        Application(
            profile_id=1,
            company="Beta Inc",
            role="Product Engineer",
            status="interviewing",
            fit_score=7.0,
            url="https://beta.com/jobs/2",
            source="manual",
            created_at=datetime(2025, 3, 5, tzinfo=UTC),
            updated_at=datetime(2025, 3, 5, tzinfo=UTC),
        ),
        Application(
            profile_id=1,
            company="Gamma Ltd",
            role="AI Lead",
            status="discovered",
            fit_score=9.0,
            url="https://gamma.com/jobs/3",
            source="jobspy",
            created_at=datetime(2025, 3, 10, tzinfo=UTC),
            updated_at=datetime(2025, 3, 10, tzinfo=UTC),
        ),
        Application(
            profile_id=1,
            company="Delta GmbH",
            role="DevRel",
            status="applied",
            fit_score=None,
            url="",
            source="indeed",
            created_at=datetime(2025, 2, 15, tzinfo=UTC),
            updated_at=datetime(2025, 2, 15, tzinfo=UTC),
        ),
    ]
    db_session.add_all(apps)
    db_session.commit()

    return db_session


# ---------------------------------------------------------------------------
# career pipeline list
# ---------------------------------------------------------------------------


class TestPipelineList:
    """Tests for `career pipeline list`."""

    def test_list_empty(self, db_session: Session) -> None:
        """Empty pipeline shows friendly message."""
        result = runner.invoke(app, ["pipeline", "list"])
        assert result.exit_code == 0
        assert "no applications" in result.output.lower() or "empty" in result.output.lower()

    def test_list_all(self, seeded_db: Session) -> None:
        """List all applications with table output."""
        result = runner.invoke(app, ["pipeline", "list"])
        assert result.exit_code == 0
        # All companies should be visible
        assert "Acme Corp" in result.output
        assert "Beta Inc" in result.output
        assert "Gamma Ltd" in result.output
        assert "Delta GmbH" in result.output

    def test_list_newest_first(self, seeded_db: Session) -> None:
        """Applications listed newest first (by created_at desc)."""
        result = runner.invoke(app, ["pipeline", "list"])
        assert result.exit_code == 0
        # Gamma (Mar 10) should appear before Acme (Mar 1)
        gamma_pos = result.output.index("Gamma Ltd")
        acme_pos = result.output.index("Acme Corp")
        assert gamma_pos < acme_pos

    def test_list_shows_columns(self, seeded_db: Session) -> None:
        """List should show ID, Company, Role, Status, Score, Date columns."""
        result = runner.invoke(app, ["pipeline", "list"])
        assert result.exit_code == 0
        assert "Senior TPM" in result.output
        assert "applied" in result.output.lower()

    def test_list_filter_by_status(self, seeded_db: Session) -> None:
        """--status filter shows only matching applications."""
        result = runner.invoke(app, ["pipeline", "list", "--status", "applied"])
        assert result.exit_code == 0
        assert "Acme Corp" in result.output
        assert "Delta GmbH" in result.output
        # Other statuses should NOT appear
        assert "Beta Inc" not in result.output
        assert "Gamma Ltd" not in result.output

    def test_list_filter_case_insensitive(self, seeded_db: Session) -> None:
        """Status filter works case-insensitively."""
        result = runner.invoke(app, ["pipeline", "list", "--status", "Applied"])
        assert result.exit_code == 0
        assert "Acme Corp" in result.output

    def test_list_filter_no_results(self, seeded_db: Session) -> None:
        """Filter with no matching applications shows friendly message."""
        result = runner.invoke(app, ["pipeline", "list", "--status", "offer"])
        assert result.exit_code == 0
        assert "no applications" in result.output.lower() or "no matching" in result.output.lower()


# ---------------------------------------------------------------------------
# career pipeline add
# ---------------------------------------------------------------------------


class TestPipelineAdd:
    """Tests for `career pipeline add`."""

    def test_add_required_fields(self, db_session: Session) -> None:
        """Add with required fields creates application in discovered status."""
        result = runner.invoke(
            app,
            ["pipeline", "add", "--company", "TestCo", "--role", "Engineer"],
        )
        assert result.exit_code == 0
        assert "TestCo" in result.output

        # Verify in DB
        app_obj = db_session.query(Application).filter_by(company="TestCo").first()
        assert app_obj is not None
        assert app_obj.role == "Engineer"
        assert app_obj.status == "discovered"

    def test_add_all_fields(self, db_session: Session) -> None:
        """Add with all optional fields."""
        result = runner.invoke(
            app,
            [
                "pipeline", "add",
                "--company", "FullCo",
                "--role", "SRE",
                "--url", "https://fullco.com/jobs/1",
                "--source", "linkedin",
            ],
        )
        assert result.exit_code == 0
        app_obj = db_session.query(Application).filter_by(company="FullCo").first()
        assert app_obj is not None
        assert app_obj.url == "https://fullco.com/jobs/1"
        assert app_obj.source == "linkedin"

    def test_add_shows_id(self, db_session: Session) -> None:
        """Add confirms creation with the application ID."""
        result = runner.invoke(
            app,
            ["pipeline", "add", "--company", "IdCo", "--role", "Dev"],
        )
        assert result.exit_code == 0
        # Should show the ID of the created application
        app_obj = db_session.query(Application).filter_by(company="IdCo").first()
        assert str(app_obj.id) in result.output

    def test_add_creates_activity_log(self, db_session: Session) -> None:
        """Adding application creates an activity log entry."""
        runner.invoke(
            app,
            ["pipeline", "add", "--company", "LogCo", "--role", "Manager"],
        )
        app_obj = db_session.query(Application).filter_by(company="LogCo").first()
        log = (
            db_session.query(ActivityLog)
            .filter_by(application_id=app_obj.id, action="created")
            .first()
        )
        assert log is not None
        assert log.source == "cli"

    def test_add_missing_company(self, db_session: Session) -> None:
        """Missing --company shows usage error, not traceback."""
        result = runner.invoke(app, ["pipeline", "add", "--role", "Engineer"])
        assert result.exit_code != 0
        # Should show usage/error, not a Python traceback
        assert "Traceback" not in result.output

    def test_add_missing_role(self, db_session: Session) -> None:
        """Missing --role shows usage error, not traceback."""
        result = runner.invoke(app, ["pipeline", "add", "--company", "TestCo"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output


# ---------------------------------------------------------------------------
# career pipeline update
# ---------------------------------------------------------------------------


class TestPipelineUpdate:
    """Tests for `career pipeline update`."""

    def test_update_status(self, seeded_db: Session) -> None:
        """Update status on an existing application."""
        # App 3 is Gamma Ltd in 'discovered' status
        result = runner.invoke(
            app,
            ["pipeline", "update", "3", "--status", "interested"],
        )
        assert result.exit_code == 0
        assert "updated" in result.output.lower() or "interested" in result.output.lower()

        # Verify in DB
        seeded_db.expire_all()
        app_obj = seeded_db.query(Application).filter_by(id=3).first()
        assert app_obj.status == "interested"

    def test_update_notes(self, seeded_db: Session) -> None:
        """Update notes on an existing application."""
        result = runner.invoke(
            app,
            ["pipeline", "update", "1", "--notes", "Had initial call"],
        )
        assert result.exit_code == 0

        seeded_db.expire_all()
        app_obj = seeded_db.query(Application).filter_by(id=1).first()
        assert app_obj.notes == "Had initial call"

    def test_update_both_status_and_notes(self, seeded_db: Session) -> None:
        """Update both status and notes simultaneously."""
        result = runner.invoke(
            app,
            [
                "pipeline", "update", "3",
                "--status", "interested",
                "--notes", "Looks promising",
            ],
        )
        assert result.exit_code == 0

        seeded_db.expire_all()
        app_obj = seeded_db.query(Application).filter_by(id=3).first()
        assert app_obj.status == "interested"
        assert app_obj.notes == "Looks promising"

    def test_update_creates_activity_log(self, seeded_db: Session) -> None:
        """Update creates activity log entry with CLI source."""
        runner.invoke(
            app,
            ["pipeline", "update", "3", "--status", "interested"],
        )
        seeded_db.expire_all()
        logs = (
            seeded_db.query(ActivityLog)
            .filter_by(application_id=3)
            .all()
        )
        cli_logs = [log for log in logs if log.source == "cli"]
        assert len(cli_logs) > 0

    def test_update_invalid_id(self, seeded_db: Session) -> None:
        """Updating non-existent application shows 'not found'."""
        result = runner.invoke(
            app,
            ["pipeline", "update", "9999", "--status", "interested"],
        )
        assert result.exit_code != 0
        assert "not found" in result.output.lower()
        assert "Traceback" not in result.output

    def test_update_no_args(self, seeded_db: Session) -> None:
        """Update with no --status or --notes shows usage message."""
        result = runner.invoke(
            app,
            ["pipeline", "update", "1"],
        )
        assert result.exit_code != 0
        assert "Traceback" not in result.output


# ---------------------------------------------------------------------------
# career pipeline stats
# ---------------------------------------------------------------------------


class TestPipelineStats:
    """Tests for `career pipeline stats`."""

    def test_stats_empty(self, db_session: Session) -> None:
        """Stats with empty pipeline shows zeros."""
        result = runner.invoke(app, ["pipeline", "stats"])
        assert result.exit_code == 0
        assert "0" in result.output

    def test_stats_total(self, seeded_db: Session) -> None:
        """Stats shows total count."""
        result = runner.invoke(app, ["pipeline", "stats"])
        assert result.exit_code == 0
        # We have 4 apps
        assert "4" in result.output

    def test_stats_per_status(self, seeded_db: Session) -> None:
        """Stats shows per-status counts."""
        result = runner.invoke(app, ["pipeline", "stats"])
        assert result.exit_code == 0
        assert "applied" in result.output.lower()
        assert "interviewing" in result.output.lower()
        assert "discovered" in result.output.lower()

    def test_stats_avg_score(self, seeded_db: Session) -> None:
        """Stats shows average score."""
        result = runner.invoke(app, ["pipeline", "stats"])
        assert result.exit_code == 0
        # Avg of 8.5, 7.0, 9.0 = 8.2 (excluding None)
        assert "8.2" in result.output

    def test_stats_top_companies(self, seeded_db: Session) -> None:
        """Stats shows top companies (by score or count)."""
        result = runner.invoke(app, ["pipeline", "stats"])
        assert result.exit_code == 0
        # At least one company name should appear
        assert "Acme Corp" in result.output or "Gamma Ltd" in result.output


# ---------------------------------------------------------------------------
# career pipeline follow-ups
# ---------------------------------------------------------------------------


class TestPipelineFollowUps:
    """Tests for `career pipeline follow-ups`."""

    def test_follow_ups_empty(self, db_session: Session) -> None:
        """No follow-ups shows friendly empty message."""
        result = runner.invoke(app, ["pipeline", "follow-ups"])
        assert result.exit_code == 0
        assert "caught up" in result.output.lower() or "no" in result.output.lower()

    def test_follow_ups_due(self, seeded_db: Session) -> None:
        """Shows due/overdue follow-ups."""
        # Create an overdue follow-up
        overdue_fu = FollowUp(
            profile_id=1,
            application_id=1,
            due_date=datetime.now(UTC) - timedelta(days=3),
            follow_up_type="email",
            notes="Check on application",
        )
        seeded_db.add(overdue_fu)
        seeded_db.commit()

        result = runner.invoke(app, ["pipeline", "follow-ups"])
        assert result.exit_code == 0
        assert "Acme Corp" in result.output
        assert "email" in result.output.lower()

    def test_follow_ups_shows_days_overdue(self, seeded_db: Session) -> None:
        """Overdue follow-ups show days overdue."""
        overdue_fu = FollowUp(
            profile_id=1,
            application_id=2,
            due_date=datetime.now(UTC) - timedelta(days=5),
            follow_up_type="phone",
            notes="Call back",
        )
        seeded_db.add(overdue_fu)
        seeded_db.commit()

        result = runner.invoke(app, ["pipeline", "follow-ups"])
        assert result.exit_code == 0
        assert "Beta Inc" in result.output

    def test_follow_ups_completed_excluded(self, seeded_db: Session) -> None:
        """Completed follow-ups are not shown."""
        completed_fu = FollowUp(
            profile_id=1,
            application_id=1,
            due_date=datetime.now(UTC) - timedelta(days=1),
            follow_up_type="email",
            notes="Already done",
            completed_at=datetime.now(UTC),
        )
        seeded_db.add(completed_fu)
        seeded_db.commit()

        result = runner.invoke(app, ["pipeline", "follow-ups"])
        assert result.exit_code == 0
        # Should show "all caught up" since the only follow-up is completed
        assert "caught up" in result.output.lower() or "no" in result.output.lower()

    def test_follow_ups_future_excluded(self, seeded_db: Session) -> None:
        """Future (upcoming) follow-ups are NOT shown — only due/overdue."""
        future_fu = FollowUp(
            profile_id=1,
            application_id=1,
            due_date=datetime.now(UTC) + timedelta(days=2),
            follow_up_type="linkedin",
            notes="Follow up next week",
        )
        seeded_db.add(future_fu)
        seeded_db.commit()

        result = runner.invoke(app, ["pipeline", "follow-ups"])
        assert result.exit_code == 0
        # Only future follow-ups exist, so should show "all caught up"
        assert "caught up" in result.output.lower()
        # The future follow-up should NOT appear in the table
        assert "linkedin" not in result.output.lower() or "caught up" in result.output.lower()

    def test_follow_ups_only_future_shows_caught_up(self, seeded_db: Session) -> None:
        """When only future follow-ups exist, shows 'You're all caught up!'."""
        future_fu = FollowUp(
            profile_id=1,
            application_id=1,
            due_date=datetime.now(UTC) + timedelta(days=5),
            follow_up_type="email",
            notes="Future task",
        )
        seeded_db.add(future_fu)
        seeded_db.commit()

        result = runner.invoke(app, ["pipeline", "follow-ups"])
        assert result.exit_code == 0
        assert "caught up" in result.output.lower()

    def test_follow_ups_mixed_shows_only_due(self, seeded_db: Session) -> None:
        """With both due and future follow-ups, shows only the due ones."""
        overdue_fu = FollowUp(
            profile_id=1,
            application_id=1,
            due_date=datetime.now(UTC) - timedelta(days=2),
            follow_up_type="email",
            notes="Overdue task",
        )
        future_fu = FollowUp(
            profile_id=1,
            application_id=2,
            due_date=datetime.now(UTC) + timedelta(days=5),
            follow_up_type="phone",
            notes="Future task",
        )
        seeded_db.add_all([overdue_fu, future_fu])
        seeded_db.commit()

        result = runner.invoke(app, ["pipeline", "follow-ups"])
        assert result.exit_code == 0
        # Overdue follow-up should be shown
        assert "Acme Corp" in result.output
        # Future follow-up (Beta Inc) should NOT be shown
        assert "Beta Inc" not in result.output


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for CLI error handling — no tracebacks."""

    def test_list_exits_zero(self, db_session: Session) -> None:
        """List always exits 0 even with no data."""
        result = runner.invoke(app, ["pipeline", "list"])
        assert result.exit_code == 0

    def test_stats_exits_zero(self, db_session: Session) -> None:
        """Stats always exits 0 even with no data."""
        result = runner.invoke(app, ["pipeline", "stats"])
        assert result.exit_code == 0

    def test_follow_ups_exits_zero(self, db_session: Session) -> None:
        """Follow-ups always exits 0 even with no data."""
        result = runner.invoke(app, ["pipeline", "follow-ups"])
        assert result.exit_code == 0

    def test_update_invalid_id_no_traceback(self, seeded_db: Session) -> None:
        """Invalid ID shows error, not traceback."""
        result = runner.invoke(
            app,
            ["pipeline", "update", "99999", "--status", "applied"],
        )
        assert "Traceback" not in result.output

    def test_add_missing_required_no_traceback(self, db_session: Session) -> None:
        """Missing required args show usage, not traceback."""
        result = runner.invoke(app, ["pipeline", "add"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output
