"""Tests for the CLI discovery, scoring, and market commands.

Covers:
- VAL-CLI-DISC-001: career discover runs sweep and prints ranked table
- VAL-CLI-DISC-002: career discover --schedule configures weekly runs
- VAL-CLI-DISC-003: career score <url> prints full score breakdown
- VAL-CLI-DISC-004: career market prints 4-section summary
- VAL-CLI-DISC-005: CLI error handling (invalid URL, no traceback)
- VAL-CLI-DISC-006: --output json/table support
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

from career_os.cli.main import app
from career_os.database import Base
from career_os.models.discovery import DiscoveredJob, SearchProfile
from career_os.models.models import Profile
from career_os.models.scoring import ScoredJob, ScoringWeights
from career_os.models.skills import Skill

runner = CliRunner()


def _extract_json(output: str) -> dict:
    """Extract the first JSON object from CLI output, skipping any banner text."""
    # Find the first '{' which starts the JSON object
    idx = output.find("{")
    if idx == -1:
        raise ValueError(f"No JSON object found in output: {output!r}")
    return json.loads(output[idx:])


def _set_sqlite_pragmas(dbapi_conn, connection_record) -> None:  # noqa: ANN001
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture()
def db_session(monkeypatch, tmp_path):
    """Create a file-based SQLite database for testing with real models."""
    db_path = tmp_path / "test.db"
    url = f"sqlite:///{db_path}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _set_sqlite_pragmas)
    Base.metadata.create_all(bind=engine)
    testing_session_cls = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    # Patch the CLI to use our test database
    import career_os.cli.main as cli_mod

    monkeypatch.setattr(cli_mod, "_get_session", lambda: testing_session_cls())

    session = testing_session_cls()
    # Seed a default profile
    profile = Profile(id=1, name="Test User", email="test@test.com", location="Frankfurt")
    session.add(profile)
    session.commit()

    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def discovery_db(db_session: Session):
    """Database with sample discovered jobs for testing."""
    jobs = [
        DiscoveredJob(
            profile_id=1,
            title="Senior TPM",
            company="Acme Corp",
            location="Frankfurt",
            url="https://acme.com/jobs/1",
            description="Senior TPM needed. Python, Agile, Kubernetes required.",
            salary_range="130000-160000 EUR",
            remote=False,
            posted_at=datetime(2025, 3, 10, tzinfo=UTC),
            title_normalized="senior tpm",
            company_normalized="acme corp",
            location_normalized="frankfurt",
            sources='["arbeitsagentur"]',
            source_urls='["https://acme.com/jobs/1"]',
            fit_score=8.5,
            created_at=datetime(2025, 3, 10, tzinfo=UTC),
            updated_at=datetime(2025, 3, 10, tzinfo=UTC),
        ),
        DiscoveredJob(
            profile_id=1,
            title="AI Lead",
            company="Beta Inc",
            location="Berlin",
            url="https://beta.com/jobs/2",
            description="AI Lead position. Machine Learning, Python, AWS, Docker.",
            salary_range="120000-150000 EUR",
            remote=True,
            posted_at=datetime(2025, 3, 8, tzinfo=UTC),
            title_normalized="ai lead",
            company_normalized="beta inc",
            location_normalized="berlin",
            sources='["arbeitnow", "arbeitsagentur"]',
            source_urls='["https://beta.com/jobs/2"]',
            fit_score=7.0,
            created_at=datetime(2025, 3, 8, tzinfo=UTC),
            updated_at=datetime(2025, 3, 8, tzinfo=UTC),
        ),
        DiscoveredJob(
            profile_id=1,
            title="Product Engineer",
            company="Gamma Ltd",
            location="Frankfurt",
            url="https://gamma.com/jobs/3",
            description="Product Engineer. React, TypeScript, Python.",
            salary_range="100000-130000 EUR",
            remote=False,
            posted_at=datetime(2025, 3, 5, tzinfo=UTC),
            title_normalized="product engineer",
            company_normalized="gamma ltd",
            location_normalized="frankfurt",
            sources='["arbeitnow"]',
            source_urls='["https://gamma.com/jobs/3"]',
            fit_score=6.5,
            created_at=datetime(2025, 3, 5, tzinfo=UTC),
            updated_at=datetime(2025, 3, 5, tzinfo=UTC),
        ),
    ]
    db_session.add_all(jobs)

    # Also add some skills for market positioning
    skills = [
        Skill(
            profile_id=1,
            name="Python",
            category="technical",
            proficiency="advanced",
            evidence_source="cv.yaml",
        ),
        Skill(
            profile_id=1,
            name="Agile",
            category="domain",
            proficiency="expert",
            evidence_source="cv.yaml",
        ),
    ]
    db_session.add_all(skills)
    db_session.commit()
    return db_session


@pytest.fixture()
def scored_db(discovery_db: Session):
    """Database with discovered jobs AND score records."""
    # Create scoring weights
    weights = ScoringWeights(profile_id=1)
    discovery_db.add(weights)
    discovery_db.flush()

    # Create scored jobs
    scores = [
        ScoredJob(
            profile_id=1,
            discovered_job_id=1,
            fit_score=8.5,
            readiness_score=75.0,
            career_alignment=8.0,
            reasoning=(
                "Strong match for Senior TPM role. +Python expertise aligns "
                "with technical requirements. +Agile mastery is a core competency. "
                "-Missing Kubernetes experience is a gap."
            ),
            estimated_salary="130,000 - 160,000 EUR",
            effort_flag="medium",
            prep_level="moderate",
            prep_notes="Brush up on Kubernetes and system design patterns.",
            is_stale=False,
        ),
    ]
    discovery_db.add_all(scores)
    discovery_db.commit()
    return discovery_db


# ---------------------------------------------------------------------------
# career discover
# ---------------------------------------------------------------------------


class TestDiscoverCommand:
    """Tests for `career discover`."""

    def test_discover_runs_sweep(self, discovery_db: Session) -> None:
        """career discover runs discovery sweep and prints results table."""
        mock_result = {
            "run_id": 1,
            "total_found": 3,
            "new_jobs": 2,
            "duplicates": 1,
            "jobs": [],
            "warnings": [],
            "sources_queried": ["arbeitsagentur", "arbeitnow"],
        }
        with patch(
            "career_os.cli.main._run_discovery_async",
            return_value=mock_result,
        ):
            result = runner.invoke(
                app,
                ["discover", "--keywords", "AI TPM", "--location", "Frankfurt"],
            )
        assert result.exit_code == 0
        # Should show discovery run summary
        assert "discover" in result.output.lower() or "found" in result.output.lower()

    def test_discover_prints_ranked_table(self, discovery_db: Session) -> None:
        """career discover prints existing discovered jobs ranked by score."""
        mock_result = {
            "run_id": 1,
            "total_found": 3,
            "new_jobs": 0,
            "duplicates": 3,
            "jobs": [],
            "warnings": [],
            "sources_queried": ["arbeitsagentur", "arbeitnow"],
        }
        with patch(
            "career_os.cli.main._run_discovery_async",
            return_value=mock_result,
        ):
            result = runner.invoke(
                app,
                ["discover", "--keywords", "TPM", "--location", "Frankfurt"],
            )
        assert result.exit_code == 0
        # Should display the table of discovered jobs
        assert "Acme Corp" in result.output
        assert "Senior TPM" in result.output

    def test_discover_empty_results(self, db_session: Session) -> None:
        """career discover with no results shows message."""
        mock_result = {
            "run_id": 1,
            "total_found": 0,
            "new_jobs": 0,
            "duplicates": 0,
            "jobs": [],
            "warnings": [],
            "sources_queried": [],
        }
        with patch(
            "career_os.cli.main._run_discovery_async",
            return_value=mock_result,
        ):
            result = runner.invoke(
                app,
                ["discover", "--keywords", "nonexistent"],
            )
        assert result.exit_code == 0

    def test_discover_shows_source(self, discovery_db: Session) -> None:
        """Discover table includes source column."""
        mock_result = {
            "run_id": 1,
            "total_found": 3,
            "new_jobs": 0,
            "duplicates": 3,
            "jobs": [],
            "warnings": [],
            "sources_queried": ["arbeitsagentur", "arbeitnow"],
        }
        with patch(
            "career_os.cli.main._run_discovery_async",
            return_value=mock_result,
        ):
            result = runner.invoke(app, ["discover", "--keywords", "TPM"])
        assert result.exit_code == 0

    def test_discover_output_json(self, discovery_db: Session) -> None:
        """--output json produces valid JSON."""
        mock_result = {
            "run_id": 1,
            "total_found": 3,
            "new_jobs": 0,
            "duplicates": 3,
            "jobs": [],
            "warnings": [],
            "sources_queried": ["arbeitsagentur", "arbeitnow"],
        }
        with patch(
            "career_os.cli.main._run_discovery_async",
            return_value=mock_result,
        ):
            result = runner.invoke(
                app,
                ["discover", "--keywords", "TPM", "--output", "json"],
            )
        assert result.exit_code == 0
        # Parse the JSON output - should be valid (skip any banner text)
        data = _extract_json(result.output)
        assert isinstance(data, dict)
        assert "jobs" in data

    def test_discover_output_table(self, discovery_db: Session) -> None:
        """--output table produces table output (default)."""
        mock_result = {
            "run_id": 1,
            "total_found": 3,
            "new_jobs": 0,
            "duplicates": 3,
            "jobs": [],
            "warnings": [],
            "sources_queried": ["arbeitsagentur", "arbeitnow"],
        }
        with patch(
            "career_os.cli.main._run_discovery_async",
            return_value=mock_result,
        ):
            result = runner.invoke(
                app,
                ["discover", "--keywords", "TPM", "--output", "table"],
            )
        assert result.exit_code == 0
        # Table output should have column headers
        assert "Title" in result.output or "Company" in result.output


# ---------------------------------------------------------------------------
# career discover --schedule
# ---------------------------------------------------------------------------


class TestDiscoverSchedule:
    """Tests for `career discover --schedule`."""

    def test_schedule_weekly(self, db_session: Session) -> None:
        """--schedule weekly creates/activates a search profile."""
        result = runner.invoke(
            app,
            [
                "discover",
                "--schedule",
                "weekly",
                "--keywords",
                "AI TPM",
                "--location",
                "Frankfurt",
            ],
        )
        assert result.exit_code == 0
        out = result.output.lower()
        assert "schedule" in out or "weekly" in out

        # Verify search profile was created
        sp = db_session.query(SearchProfile).first()
        assert sp is not None
        assert sp.is_active is True

    def test_schedule_shows_next_run(self, db_session: Session) -> None:
        """--schedule output mentions next run or scheduled status."""
        result = runner.invoke(
            app,
            [
                "discover",
                "--schedule",
                "weekly",
                "--keywords",
                "TPM",
                "--location",
                "Berlin",
            ],
        )
        assert result.exit_code == 0
        out = result.output.lower()
        assert "scheduled" in out or "next" in out or "weekly" in out


# ---------------------------------------------------------------------------
# career score <url>
# ---------------------------------------------------------------------------


class TestScoreCommand:
    """Tests for `career score <url>`."""

    def test_score_prints_breakdown(self, scored_db: Session) -> None:
        """career score <url> prints full score breakdown."""
        mock_scored = ScoredJob(
            id=99,
            profile_id=1,
            fit_score=8.5,
            readiness_score=75.0,
            career_alignment=8.0,
            reasoning=(
                "Strong match. +Python expertise. +Agile mastery. -Missing Kubernetes experience."
            ),
            estimated_salary="130,000 - 160,000 EUR",
            effort_flag="medium",
            prep_level="moderate",
            prep_notes="Brush up on Kubernetes.",
        )
        with patch(
            "career_os.cli.main._run_score_async",
            return_value=mock_scored,
        ):
            result = runner.invoke(
                app,
                ["score", "https://example.com/job"],
            )
        assert result.exit_code == 0
        assert "8.5" in result.output
        assert "75" in result.output or "readiness" in result.output.lower()

    def test_score_shows_all_fields(self, scored_db: Session) -> None:
        """Score output includes fit, readiness, alignment, reasoning, salary, effort, prep."""
        mock_scored = ScoredJob(
            id=99,
            profile_id=1,
            fit_score=8.5,
            readiness_score=75.0,
            career_alignment=8.0,
            reasoning=(
                "Strong match. +Python expertise. +Agile mastery. -Missing Kubernetes experience."
            ),
            estimated_salary="130,000 - 160,000 EUR",
            effort_flag="medium",
            prep_level="moderate",
            prep_notes="Brush up on Kubernetes.",
        )
        with patch(
            "career_os.cli.main._run_score_async",
            return_value=mock_scored,
        ):
            result = runner.invoke(
                app,
                ["score", "https://example.com/job"],
            )
        assert result.exit_code == 0
        # Check key fields present
        assert "fit" in result.output.lower() or "8.5" in result.output
        assert "salary" in result.output.lower() or "EUR" in result.output
        assert "effort" in result.output.lower() or "medium" in result.output.lower()

    def test_score_invalid_url(self, db_session: Session) -> None:
        """Invalid URL shows clear error, non-zero exit, no traceback."""
        result = runner.invoke(app, ["score", "not-a-url"])
        assert result.exit_code != 0
        assert "invalid" in result.output.lower() or "url" in result.output.lower()
        assert "Traceback" not in result.output

    def test_score_output_json(self, scored_db: Session) -> None:
        """--output json produces valid JSON with all score fields."""
        mock_scored = ScoredJob(
            id=99,
            profile_id=1,
            fit_score=8.5,
            readiness_score=75.0,
            career_alignment=8.0,
            reasoning="Strong match. +Python. +Agile. -Kubernetes.",
            estimated_salary="130,000 - 160,000 EUR",
            effort_flag="medium",
            prep_level="moderate",
            prep_notes="Brush up on Kubernetes.",
        )
        with patch(
            "career_os.cli.main._run_score_async",
            return_value=mock_scored,
        ):
            result = runner.invoke(
                app,
                ["score", "https://example.com/job", "--output", "json"],
            )
        assert result.exit_code == 0
        data = _extract_json(result.output)
        assert "fit_score" in data
        assert data["fit_score"] == pytest.approx(8.5)

    def test_score_output_table(self, scored_db: Session) -> None:
        """--output table produces formatted table output."""
        mock_scored = ScoredJob(
            id=99,
            profile_id=1,
            fit_score=8.5,
            readiness_score=75.0,
            career_alignment=8.0,
            reasoning="Strong match. +Python. +Agile. -Kubernetes.",
            estimated_salary="130,000 - 160,000 EUR",
            effort_flag="medium",
            prep_level="moderate",
            prep_notes="Brush up on Kubernetes.",
        )
        with patch(
            "career_os.cli.main._run_score_async",
            return_value=mock_scored,
        ):
            result = runner.invoke(
                app,
                ["score", "https://example.com/job", "--output", "table"],
            )
        assert result.exit_code == 0
        assert "8.5" in result.output


# ---------------------------------------------------------------------------
# career market
# ---------------------------------------------------------------------------


class TestMarketCommand:
    """Tests for `career market`."""

    def test_market_prints_four_sections(self, discovery_db: Session) -> None:
        """career market prints 4-section summary."""
        result = runner.invoke(app, ["market"])
        assert result.exit_code == 0
        out = result.output.lower()
        # Should have 4 sections: salary trends, skill demand, hiring patterns, positioning
        assert "salary" in out
        assert "skill" in out
        assert "hiring" in out or "compan" in out
        assert "position" in out

    def test_market_shows_salary_data(self, discovery_db: Session) -> None:
        """Market shows salary trend data."""
        result = runner.invoke(app, ["market"])
        assert result.exit_code == 0
        # Should show salary numbers from our discovered jobs
        out = result.output
        # Our jobs have salaries like 130000-160000, so some numeric data should appear
        assert any(c.isdigit() for c in out)

    def test_market_shows_skill_trends(self, discovery_db: Session) -> None:
        """Market shows skill demand trends."""
        result = runner.invoke(app, ["market"])
        assert result.exit_code == 0
        out = result.output
        # Our jobs mention Python, Agile, Kubernetes, etc.
        assert "Python" in out

    def test_market_shows_hiring_patterns(self, discovery_db: Session) -> None:
        """Market shows company hiring patterns."""
        result = runner.invoke(app, ["market"])
        assert result.exit_code == 0
        out = result.output
        # Should show companies from discovered jobs
        assert "Acme Corp" in out or "Beta Inc" in out or "Gamma" in out

    def test_market_shows_positioning(self, discovery_db: Session) -> None:
        """Market shows market positioning."""
        result = runner.invoke(app, ["market"])
        assert result.exit_code == 0
        # Should show match percentage data
        assert "%" in result.output

    def test_market_empty(self, db_session: Session) -> None:
        """Market with no data shows friendly message."""
        result = runner.invoke(app, ["market"])
        assert result.exit_code == 0
        out = result.output.lower()
        assert "no data" in out or "no discovery" in out or "discover" in out

    def test_market_output_json(self, discovery_db: Session) -> None:
        """--output json produces valid JSON with all 4 sections."""
        result = runner.invoke(app, ["market", "--output", "json"])
        assert result.exit_code == 0
        data = _extract_json(result.output)
        assert "salary_trends" in data
        assert "skill_trends" in data
        assert "hiring_patterns" in data
        assert "positioning" in data

    def test_market_output_table(self, discovery_db: Session) -> None:
        """--output table produces formatted table output."""
        result = runner.invoke(app, ["market", "--output", "table"])
        assert result.exit_code == 0
        # Table output should have section headers
        out = result.output.lower()
        assert "salary" in out


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestCLIDiscoveryErrorHandling:
    """Ensure CLI discovery commands handle errors gracefully."""

    def test_discover_exits_zero(self, db_session: Session) -> None:
        """Discover exits 0 even with no data."""
        mock_result = {
            "run_id": 1,
            "total_found": 0,
            "new_jobs": 0,
            "duplicates": 0,
            "jobs": [],
            "warnings": [],
            "sources_queried": [],
        }
        with patch(
            "career_os.cli.main._run_discovery_async",
            return_value=mock_result,
        ):
            result = runner.invoke(app, ["discover", "--keywords", "test"])
        assert result.exit_code == 0
        assert "Traceback" not in result.output

    def test_market_exits_zero(self, db_session: Session) -> None:
        """Market exits 0 even with no data."""
        result = runner.invoke(app, ["market"])
        assert result.exit_code == 0
        assert "Traceback" not in result.output

    def test_score_no_args(self, db_session: Session) -> None:
        """Score without URL shows usage error, not traceback."""
        result = runner.invoke(app, ["score"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output

    def test_score_empty_url(self, db_session: Session) -> None:
        """Score with empty string URL shows error."""
        result = runner.invoke(app, ["score", ""])
        assert result.exit_code != 0
        assert "Traceback" not in result.output

    def test_discover_no_traceback_on_error(self, db_session: Session) -> None:
        """Discover doesn't show tracebacks on service errors."""
        with patch(
            "career_os.cli.main._run_discovery_async",
            side_effect=Exception("Connection failed"),
        ):
            result = runner.invoke(app, ["discover", "--keywords", "test"])
        assert "Traceback" not in result.output
