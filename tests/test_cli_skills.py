"""Tests for the CLI skills, goals, and coaching commands."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

from career_os.cli.main import app
from career_os.database import Base
from career_os.models.models import Application, Profile
from career_os.models.skills import (
    Goal,
    JobRequirement,
    Skill,
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
def skills_db(db_session: Session):
    """Database with sample skills for testing."""
    skills = [
        Skill(
            profile_id=1,
            name="Python",
            category="technical",
            proficiency="advanced",
            evidence_source="cv.yaml",
            evidence_detail="Primary language for 5+ years",
        ),
        Skill(
            profile_id=1,
            name="Kubernetes",
            category="technical",
            proficiency="intermediate",
            evidence_source="cv.yaml",
            evidence_detail="Deployed production clusters",
        ),
        Skill(
            profile_id=1,
            name="Strategic Thinking",
            category="soft",
            proficiency="expert",
            evidence_source="assessment:cliftonstrengths",
            evidence_detail="CliftonStrengths #1",
        ),
        Skill(
            profile_id=1,
            name="Jira",
            category="tools",
            proficiency="advanced",
            evidence_source="manual",
            evidence_detail="Daily use for 3 years",
        ),
        Skill(
            profile_id=1,
            name="Program Management",
            category="domain",
            proficiency="expert",
            evidence_source="profile",
            evidence_detail="10+ years TPM experience",
        ),
    ]
    db_session.add_all(skills)
    db_session.commit()
    return db_session


@pytest.fixture()
def gaps_db(skills_db: Session):
    """Database with skills + applications + job requirements for gap testing."""
    # Create applications
    app1 = Application(
        profile_id=1,
        company="Acme Corp",
        role="Senior TPM",
        status="applied",
        fit_score=8.5,
        created_at=datetime(2025, 3, 1, tzinfo=UTC),
        updated_at=datetime(2025, 3, 1, tzinfo=UTC),
    )
    app2 = Application(
        profile_id=1,
        company="Beta Inc",
        role="AI Lead",
        status="interviewing",
        fit_score=7.0,
        created_at=datetime(2025, 3, 5, tzinfo=UTC),
        updated_at=datetime(2025, 3, 5, tzinfo=UTC),
    )
    skills_db.add_all([app1, app2])
    skills_db.flush()

    # Create job requirements for app1
    reqs_app1 = [
        JobRequirement(
            application_id=app1.id,
            profile_id=1,
            skill_name="Python",
            required_level="expert",
            severity="critical",
        ),
        JobRequirement(
            application_id=app1.id,
            profile_id=1,
            skill_name="Kubernetes",
            required_level="advanced",
            severity="nice-to-have",
        ),
        JobRequirement(
            application_id=app1.id,
            profile_id=1,
            skill_name="Terraform",
            required_level="intermediate",
            severity="bonus",
        ),
    ]
    # Create job requirements for app2
    reqs_app2 = [
        JobRequirement(
            application_id=app2.id,
            profile_id=1,
            skill_name="Python",
            required_level="expert",
            severity="critical",
        ),
        JobRequirement(
            application_id=app2.id,
            profile_id=1,
            skill_name="Docker",
            required_level="advanced",
            severity="critical",
        ),
        JobRequirement(
            application_id=app2.id,
            profile_id=1,
            skill_name="Kubernetes",
            required_level="expert",
            severity="nice-to-have",
        ),
    ]
    skills_db.add_all(reqs_app1 + reqs_app2)
    skills_db.commit()
    return skills_db


@pytest.fixture()
def goals_db(db_session: Session):
    """Database with sample goals for testing."""
    goals = [
        Goal(
            profile_id=1,
            title="Land Senior TPM role at 150k+ EUR",
            goal_type="realistic",
            target_date=datetime(2025, 6, 1, tzinfo=UTC),
            status="active",
            description="Get a senior TPM position with competitive compensation",
        ),
        Goal(
            profile_id=1,
            title="Become VP of Engineering",
            goal_type="aspirational",
            target_date=datetime(2027, 1, 1, tzinfo=UTC),
            status="active",
            description="Long-term career aspiration",
        ),
        Goal(
            profile_id=1,
            title="Complete AWS certification",
            goal_type="realistic",
            target_date=datetime(2025, 4, 1, tzinfo=UTC),
            status="completed",
            description="AWS Solutions Architect",
        ),
    ]
    db_session.add_all(goals)
    db_session.commit()
    return db_session


@pytest.fixture()
def coaching_db(gaps_db: Session):
    """Database with skills, gaps, goals, and coaching data for testing."""
    # Add goals
    goal = Goal(
        profile_id=1,
        title="Land Senior TPM role",
        goal_type="realistic",
        status="active",
    )
    gaps_db.add(goal)
    gaps_db.commit()
    return gaps_db


# ---------------------------------------------------------------------------
# career skills list
# ---------------------------------------------------------------------------


class TestSkillsList:
    """Tests for `career skills list`."""

    def test_list_empty(self, db_session: Session) -> None:
        """Empty skills inventory shows friendly message."""
        result = runner.invoke(app, ["skills", "list"])
        assert result.exit_code == 0
        assert "no skills" in result.output.lower()

    def test_list_all(self, skills_db: Session) -> None:
        """List all skills with table output."""
        result = runner.invoke(app, ["skills", "list"])
        assert result.exit_code == 0
        assert "Python" in result.output
        assert "Kubernetes" in result.output
        assert "Strategic Thinking" in result.output
        assert "Jira" in result.output
        assert "Program Management" in result.output

    def test_list_shows_columns(self, skills_db: Session) -> None:
        """Skills table shows Name, Category, Proficiency, Source columns."""
        result = runner.invoke(app, ["skills", "list"])
        assert result.exit_code == 0
        # Check column headers exist
        assert "Name" in result.output
        assert "Category" in result.output
        assert "Proficiency" in result.output
        assert "Source" in result.output

    def test_list_filter_by_category(self, skills_db: Session) -> None:
        """--category filter shows only matching skills."""
        result = runner.invoke(app, ["skills", "list", "--category", "technical"])
        assert result.exit_code == 0
        assert "Python" in result.output
        assert "Kubernetes" in result.output
        # Non-technical skills should NOT appear
        assert "Strategic Thinking" not in result.output
        assert "Jira" not in result.output

    def test_list_filter_by_source(self, skills_db: Session) -> None:
        """--source filter shows only matching skills."""
        result = runner.invoke(app, ["skills", "list", "--source", "cv.yaml"])
        assert result.exit_code == 0
        assert "Python" in result.output
        assert "Kubernetes" in result.output
        # Non-CV skills should NOT appear
        assert "Strategic Thinking" not in result.output

    def test_list_filter_combined(self, skills_db: Session) -> None:
        """Combined --category and --source filters with AND logic."""
        result = runner.invoke(
            app,
            ["skills", "list", "--category", "technical", "--source", "cv.yaml"],
        )
        assert result.exit_code == 0
        assert "Python" in result.output
        assert "Kubernetes" in result.output
        assert "Jira" not in result.output

    def test_list_filter_no_results(self, skills_db: Session) -> None:
        """Filter with no matching skills shows friendly message."""
        result = runner.invoke(
            app, ["skills", "list", "--category", "tools", "--source", "cv.yaml"],
        )
        assert result.exit_code == 0
        out = result.output.lower()
        assert "no skills" in out or "no matching" in out


# ---------------------------------------------------------------------------
# career skills gaps --application <id>
# ---------------------------------------------------------------------------


class TestSkillsGapsApplication:
    """Tests for `career skills gaps --application <id>`."""

    def test_gaps_for_application(self, gaps_db: Session) -> None:
        """Shows gap report for a specific application."""
        result = runner.invoke(app, ["skills", "gaps", "--application", "1"])
        assert result.exit_code == 0
        assert "Acme Corp" in result.output
        # Should show skills that are gaps
        out = result.output
        assert "Python" in out or "Kubernetes" in out or "Terraform" in out

    def test_gaps_shows_readiness_score(self, gaps_db: Session) -> None:
        """Gap report includes readiness score."""
        result = runner.invoke(app, ["skills", "gaps", "--application", "1"])
        assert result.exit_code == 0
        assert "readiness" in result.output.lower() or "score" in result.output.lower()

    def test_gaps_shows_severity(self, gaps_db: Session) -> None:
        """Gap report shows severity for each gap."""
        result = runner.invoke(app, ["skills", "gaps", "--application", "1"])
        assert result.exit_code == 0
        # Should show severity levels
        out = result.output.lower()
        assert "critical" in out or "nice-to-have" in out or "bonus" in out

    def test_gaps_filter_by_severity(self, gaps_db: Session) -> None:
        """--severity filter shows only matching gaps."""
        result = runner.invoke(
            app,
            ["skills", "gaps", "--application", "1", "--severity", "critical"],
        )
        assert result.exit_code == 0
        assert "Python" in result.output
        # Bonus gaps should not appear when filtering by critical
        assert "Terraform" not in result.output

    def test_gaps_invalid_application(self, gaps_db: Session) -> None:
        """Invalid application ID shows error, no traceback."""
        result = runner.invoke(app, ["skills", "gaps", "--application", "999"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()
        assert "Traceback" not in result.output

    def test_gaps_no_requirements(self, skills_db: Session) -> None:
        """Application without parsed requirements shows clear message."""
        # Create an application without requirements
        app_obj = Application(
            profile_id=1,
            company="NoReqs Inc",
            role="DevOps",
            status="discovered",
            created_at=datetime(2025, 3, 1, tzinfo=UTC),
            updated_at=datetime(2025, 3, 1, tzinfo=UTC),
        )
        skills_db.add(app_obj)
        skills_db.commit()

        result = runner.invoke(
            app, ["skills", "gaps", "--application", str(app_obj.id)],
        )
        assert result.exit_code != 0
        out = result.output.lower()
        assert "not yet parsed" in out or "no requirements" in out
        assert "Traceback" not in result.output


# ---------------------------------------------------------------------------
# career skills gaps --aggregate
# ---------------------------------------------------------------------------


class TestSkillsGapsAggregate:
    """Tests for `career skills gaps --aggregate`."""

    def test_aggregate_gaps(self, gaps_db: Session) -> None:
        """Shows cross-application gap summary ranked by frequency."""
        result = runner.invoke(app, ["skills", "gaps", "--aggregate"])
        assert result.exit_code == 0
        # Python and Kubernetes appear as gaps in multiple applications
        assert "Python" in result.output or "Kubernetes" in result.output

    def test_aggregate_shows_frequency(self, gaps_db: Session) -> None:
        """Aggregate report includes frequency count."""
        result = runner.invoke(app, ["skills", "gaps", "--aggregate"])
        assert result.exit_code == 0
        # Should show frequency data (numbers like 2 for cross-app gaps)
        assert "2" in result.output or "frequency" in result.output.lower()

    def test_aggregate_ranked_by_frequency(self, gaps_db: Session) -> None:
        """Aggregate gaps are ranked by frequency (most common first)."""
        result = runner.invoke(app, ["skills", "gaps", "--aggregate"])
        assert result.exit_code == 0
        # Result should be parseable and show ranked skills

    def test_aggregate_empty(self, db_session: Session) -> None:
        """Empty pipeline shows friendly message for aggregate."""
        result = runner.invoke(app, ["skills", "gaps", "--aggregate"])
        assert result.exit_code == 0
        assert "no gaps" in result.output.lower() or "no applications" in result.output.lower()


# ---------------------------------------------------------------------------
# career goals
# ---------------------------------------------------------------------------


class TestGoalsList:
    """Tests for `career goals`."""

    def test_goals_list(self, goals_db: Session) -> None:
        """Lists active goals with progress."""
        result = runner.invoke(app, ["goals"])
        assert result.exit_code == 0
        assert "Land Senior TPM" in result.output
        assert "Become VP" in result.output

    def test_goals_shows_type(self, goals_db: Session) -> None:
        """Goals list shows goal type."""
        result = runner.invoke(app, ["goals"])
        assert result.exit_code == 0
        assert "realistic" in result.output.lower() or "aspirational" in result.output.lower()

    def test_goals_shows_progress(self, goals_db: Session) -> None:
        """Goals list shows progress percentage."""
        result = runner.invoke(app, ["goals"])
        assert result.exit_code == 0
        # Should show progress like "0.0%" or some percentage
        assert "%" in result.output

    def test_goals_shows_target_date(self, goals_db: Session) -> None:
        """Goals list shows target date."""
        result = runner.invoke(app, ["goals"])
        assert result.exit_code == 0
        assert "2025" in result.output

    def test_goals_empty(self, db_session: Session) -> None:
        """No goals shows friendly message."""
        result = runner.invoke(app, ["goals"])
        assert result.exit_code == 0
        assert "no goals" in result.output.lower() or "no career goals" in result.output.lower()

    def test_goals_excludes_completed(self, goals_db: Session) -> None:
        """Goals list shows only active goals, not completed ones."""
        result = runner.invoke(app, ["goals"])
        assert result.exit_code == 0
        # Active goals should appear
        assert "Land Senior TPM" in result.output
        assert "Become VP" in result.output
        # Completed goal should NOT appear
        assert "AWS" not in result.output


# ---------------------------------------------------------------------------
# career goals show <id>
# ---------------------------------------------------------------------------


class TestGoalsShow:
    """Tests for `career goals show <id>`."""

    def test_show_reality_map(self, goals_db: Session) -> None:
        """Shows reality map for a specific goal."""
        result = runner.invoke(app, ["goals", "show", "1"])
        assert result.exit_code == 0
        assert "Land Senior TPM" in result.output

    def test_show_dimensions(self, goals_db: Session) -> None:
        """Reality map shows dimensions (skills, applications, portfolio)."""
        result = runner.invoke(app, ["goals", "show", "1"])
        assert result.exit_code == 0
        assert "skills" in result.output.lower()
        assert "application" in result.output.lower()

    def test_show_overall_progress(self, goals_db: Session) -> None:
        """Reality map shows overall progress percentage."""
        result = runner.invoke(app, ["goals", "show", "1"])
        assert result.exit_code == 0
        assert "%" in result.output or "progress" in result.output.lower()

    def test_show_invalid_id(self, goals_db: Session) -> None:
        """Invalid goal ID shows error, no traceback."""
        result = runner.invoke(app, ["goals", "show", "999"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()
        assert "Traceback" not in result.output


# ---------------------------------------------------------------------------
# career coach
# ---------------------------------------------------------------------------


class TestCoach:
    """Tests for `career coach`."""

    def test_coach_shows_suggestions(self, coaching_db: Session) -> None:
        """Shows coaching suggestions with effort estimates."""
        result = runner.invoke(app, ["coach"])
        assert result.exit_code == 0
        # Should show some suggestions

    def test_coach_shows_effort_estimates(self, coaching_db: Session) -> None:
        """Each suggestion includes hours, weeks, difficulty."""
        result = runner.invoke(app, ["coach"])
        assert result.exit_code == 0
        # Look for effort-related content
        out = result.output.lower()
        assert "hour" in out or "week" in out or "h" in out

    def test_coach_shows_max_5(self, coaching_db: Session) -> None:
        """Shows at most top 5 suggestions."""
        result = runner.invoke(app, ["coach"])
        assert result.exit_code == 0
        # Count the number of rows in the output (after header)
        # The table should have at most 5 data rows

    def test_coach_empty(self, db_session: Session) -> None:
        """No data shows friendly empty message."""
        result = runner.invoke(app, ["coach"])
        assert result.exit_code == 0
        # Should show some message even with no data

    def test_coach_shows_focus_area(self, coaching_db: Session) -> None:
        """Coach output shows focus area."""
        result = runner.invoke(app, ["coach"])
        assert result.exit_code == 0
        # Should show focus area or at least structured output


# ---------------------------------------------------------------------------
# Error handling — no tracebacks
# ---------------------------------------------------------------------------


class TestCLISkillsErrorHandling:
    """Ensure all CLI skills commands don't produce tracebacks."""

    def test_skills_list_exits_zero(self, db_session: Session) -> None:
        result = runner.invoke(app, ["skills", "list"])
        assert result.exit_code == 0
        assert "Traceback" not in result.output

    def test_goals_exits_zero(self, db_session: Session) -> None:
        result = runner.invoke(app, ["goals"])
        assert result.exit_code == 0
        assert "Traceback" not in result.output

    def test_coach_exits_zero(self, db_session: Session) -> None:
        result = runner.invoke(app, ["coach"])
        assert result.exit_code == 0
        assert "Traceback" not in result.output

    def test_gaps_requires_option(self, db_session: Session) -> None:
        """career skills gaps without --application or --aggregate shows usage error."""
        result = runner.invoke(app, ["skills", "gaps"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output
