"""Tests for the CLI interview prep commands: research, interview-prep, stories.

Covers:
- VAL-CLI-PREP-001: `career research <company>` outputs formatted report
- VAL-CLI-PREP-002: `career interview-prep <id>` outputs topics, questions, checklist
- VAL-CLI-PREP-003: `career interview-prep stories` lists and manages stories
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
from career_os.models.interview_prep import InterviewPrepItem, InterviewPrepSession
from career_os.models.models import Application, Profile
from career_os.models.skills import JobRequirement
from career_os.models.star_stories import StarStory
from career_os.schemas.research import (
    CompanyResearchReport,
    FundingReport,
    GlassdoorReport,
    HiringPatternsReport,
    SourceWarning,
    TechStackReport,
    ValuesAlignmentReport,
)

runner = CliRunner()


def _set_sqlite_pragmas(dbapi_conn, connection_record) -> None:  # noqa: ANN001
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture()
def db_session(monkeypatch, tmp_path):
    """Create a file-based SQLite database for testing."""
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
def app_with_prep(db_session: Session):
    """Database with an application and interview prep session."""
    app_obj = Application(
        id=1,
        profile_id=1,
        company="Stripe",
        role="Senior TPM",
        url="https://stripe.com/jobs/1",
        status="interviewing",
        created_at=datetime(2025, 3, 1, tzinfo=UTC),
    )
    db_session.add(app_obj)
    db_session.flush()

    # Create job requirements (for gap context)
    reqs = [
        JobRequirement(
            application_id=1,
            profile_id=1,
            skill_name="Python",
            required_level="advanced",
            severity="critical",
        ),
        JobRequirement(
            application_id=1,
            profile_id=1,
            skill_name="Kubernetes",
            required_level="intermediate",
            severity="nice-to-have",
        ),
    ]
    db_session.add_all(reqs)

    # Create an existing interview prep session
    session = InterviewPrepSession(
        application_id=1,
        profile_id=1,
        topics=json.dumps(
            [
                {
                    "topic": "System Design at Scale",
                    "relevance": "high",
                    "difficulty": "high",
                    "source": "JD requirement",
                },
                {
                    "topic": "Payment Processing Architecture",
                    "relevance": "high",
                    "difficulty": "medium",
                    "source": "company style",
                },
                {
                    "topic": "Cross-functional Leadership",
                    "relevance": "medium",
                    "difficulty": "low",
                    "source": "skill gap",
                },
            ]
        ),
        questions=json.dumps(
            [
                {
                    "question": "Describe a time you led a cross-team initiative at scale.",
                    "category": "behavioral",
                    "difficulty": "medium",
                },
                {
                    "question": "How would you design a global payment processing system?",
                    "category": "system_design",
                    "difficulty": "high",
                },
                {
                    "question": "Tell me about a project where you handled conflicting priorities.",
                    "category": "behavioral",
                    "difficulty": "medium",
                },
                {
                    "question": "How do you ensure reliability in distributed systems?",
                    "category": "technical",
                    "difficulty": "high",
                },
                {
                    "question": "Walk me through your approach to incident management.",
                    "category": "technical",
                    "difficulty": "medium",
                },
            ]
        ),
        total_prep_hours=4.5,
        company_researched=True,
    )
    db_session.add(session)
    db_session.flush()

    # Add checklist items
    items = [
        InterviewPrepItem(
            session_id=session.id,
            profile_id=1,
            item="Review Stripe's tech blog posts",
            time_minutes=30,
            priority="high",
            completed=False,
        ),
        InterviewPrepItem(
            session_id=session.id,
            profile_id=1,
            item="Practice system design questions",
            time_minutes=60,
            priority="high",
            completed=True,
            completed_at=datetime(2025, 3, 5, tzinfo=UTC),
        ),
        InterviewPrepItem(
            session_id=session.id,
            profile_id=1,
            item="Prepare STAR stories for behavioral questions",
            time_minutes=45,
            priority="medium",
            completed=False,
        ),
    ]
    db_session.add_all(items)
    db_session.commit()

    return db_session


@pytest.fixture()
def stories_db(db_session: Session):
    """Database with STAR stories."""
    stories = [
        StarStory(
            profile_id=1,
            title="Led Cross-Team Migration",
            situation="Legacy payment system was causing 3% error rate",
            task="Lead migration to new payment processing platform",
            action="Coordinated 4 teams, established migration plan, ran canary deploys",
            result="Reduced error rate to 0.1%, saved $2M annually",
            skill_tags="Python,Program Management,Kubernetes",
            created_at=datetime(2025, 2, 1, tzinfo=UTC),
            updated_at=datetime(2025, 2, 1, tzinfo=UTC),
        ),
        StarStory(
            profile_id=1,
            title="Scaled AI Pipeline",
            situation="ML inference latency exceeded SLA targets",
            task="Optimize pipeline to meet 100ms p99 target",
            action="Profiled bottlenecks, implemented batching, added caching layer",
            result="Achieved 50ms p99, 3x throughput improvement",
            skill_tags="Python,Machine Learning,AWS",
            created_at=datetime(2025, 1, 15, tzinfo=UTC),
            updated_at=datetime(2025, 1, 15, tzinfo=UTC),
        ),
    ]
    db_session.add_all(stories)
    db_session.commit()
    return db_session


# ---------------------------------------------------------------------------
# VAL-CLI-PREP-001: career research <company>
# ---------------------------------------------------------------------------


class TestResearchCommand:
    """Tests for `career research <company>` command."""

    def test_research_outputs_structured_report(self, db_session: Session) -> None:
        """career research <company> produces a formatted report, exit 0."""
        mock_report = CompanyResearchReport(
            company_name="Stripe",
            tech_stack=TechStackReport(
                frontend=["React", "TypeScript"],
                backend=["Ruby", "Go", "Python"],
                infrastructure=["AWS", "Kubernetes"],
                analytics=["Snowflake", "dbt"],
            ),
            funding=FundingReport(
                stage="Series I",
                total_raised="$8.7B",
                lead_investor="Sequoia Capital",
                last_round_date="2023-03",
            ),
            glassdoor=GlassdoorReport(
                overall_rating=4.2,
                ceo_approval=89,
                culture_keywords=["innovative", "fast-paced", "mission-driven"],
                work_life_balance=3.8,
            ),
            values_alignment=ValuesAlignmentReport(
                score=8.5,
                rationale="Strong alignment with innovation and AI-first culture values.",
            ),
            ats_platform="Greenhouse",
            hiring_patterns=HiringPatternsReport(
                active_postings=150,
                posting_velocity="40/month",
                top_departments=["Engineering", "Product", "Design"],
            ),
            industry_segment="Enterprise SaaS / Financial Infrastructure",
            employee_count="8000+",
            warnings=[],
        )

        with patch(
            "career_os.cli.main._run_research_async",
            return_value=mock_report,
        ):
            result = runner.invoke(app, ["research", "Stripe"])

        assert result.exit_code == 0
        # Verify structured report sections
        assert "Stripe" in result.output
        assert "Tech Stack" in result.output
        assert "Funding" in result.output
        assert "Glassdoor" in result.output or "Culture" in result.output
        assert "Values Alignment" in result.output
        assert "Hiring" in result.output
        assert "Industry" in result.output

    def test_research_shows_tech_stack_categories(self, db_session: Session) -> None:
        """Report includes categorized tech stack."""
        mock_report = CompanyResearchReport(
            company_name="Acme",
            tech_stack=TechStackReport(
                frontend=["React"],
                backend=["Python", "Go"],
                infrastructure=["AWS"],
                analytics=["Looker"],
            ),
            values_alignment=ValuesAlignmentReport(score=7.0, rationale="Good."),
            warnings=[],
        )

        with patch(
            "career_os.cli.main._run_research_async",
            return_value=mock_report,
        ):
            result = runner.invoke(app, ["research", "Acme"])

        assert result.exit_code == 0
        # Check tech sections present
        assert "React" in result.output
        assert "Python" in result.output

    def test_research_partial_report_for_obscure_company(self, db_session: Session) -> None:
        """Obscure companies get partial report without crashing."""
        mock_report = CompanyResearchReport(
            company_name="TinyStartup",
            tech_stack=TechStackReport(),
            funding=FundingReport(),
            glassdoor=GlassdoorReport(),
            values_alignment=ValuesAlignmentReport(score=5.0, rationale="No data available."),
            hiring_patterns=HiringPatternsReport(),
            warnings=[
                SourceWarning(source="glassdoor", error="No data found"),
                SourceWarning(source="funding", error="Not available"),
            ],
        )

        with patch(
            "career_os.cli.main._run_research_async",
            return_value=mock_report,
        ):
            result = runner.invoke(app, ["research", "TinyStartup"])

        assert result.exit_code == 0
        assert "TinyStartup" in result.output
        # Warnings should be shown
        assert "Warning" in result.output or "⚠" in result.output

    def test_research_error_handling(self, db_session: Session) -> None:
        """Research failure shows error, no traceback, exit 1."""
        with patch(
            "career_os.cli.main._run_research_async",
            side_effect=Exception("API unavailable"),
        ):
            result = runner.invoke(app, ["research", "FakeCompany"])

        assert result.exit_code == 1
        assert "Error" in result.output
        assert "Traceback" not in result.output

    def test_research_no_company_shows_usage(self, db_session: Session) -> None:
        """Missing company argument shows usage error."""
        result = runner.invoke(app, ["research"])

        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# VAL-CLI-PREP-002: career interview-prep <id>
# ---------------------------------------------------------------------------


class TestInterviewPrepCommand:
    """Tests for `career interview-prep <id>` command."""

    def test_prep_outputs_topics_questions_checklist(self, app_with_prep: Session) -> None:
        """career interview-prep <id> outputs topics, questions, checklist."""
        result = runner.invoke(app, ["interview-prep", "1"])

        assert result.exit_code == 0
        # Topics section
        assert "Topic" in result.output
        # Topics should reference company/role context (contextual, not canned)
        assert "Stripe" in result.output
        assert "Senior TPM" in result.output or "TPM" in result.output
        # Questions section
        assert "Question" in result.output
        # Checklist section
        assert "Checklist" in result.output
        # Progress info
        assert "Progress" in result.output or "%" in result.output

    def test_prep_shows_progress_state(self, app_with_prep: Session) -> None:
        """Checklist shows completed/uncompleted items with progress."""
        result = runner.invoke(app, ["interview-prep", "1"])

        assert result.exit_code == 0
        # Should show progress tracking
        assert "Progress" in result.output or "%" in result.output

    def test_prep_invalid_id_shows_error(self, db_session: Session) -> None:
        """Invalid application ID shows error, no traceback."""
        result = runner.invoke(app, ["interview-prep", "999"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "Error" in result.output
        assert "Traceback" not in result.output

    def test_prep_generates_new_session(self, db_session: Session) -> None:
        """When no existing prep session, generates one via AI."""
        # Create application without existing prep
        app_obj = Application(
            id=1,
            profile_id=1,
            company="TestCorp",
            role="Engineer",
            url="https://test.com",
            status="interviewing",
        )
        db_session.add(app_obj)
        db_session.commit()

        with patch("career_os.cli.main._run_interview_prep_async") as mock_prep:
            from career_os.schemas.interview_prep import (
                InterviewPrepResponse,
                PrepChecklistItem,
                PrepQuestion,
                PrepTopic,
            )

            mock_prep.return_value = InterviewPrepResponse(
                application_id=1,
                company="TestCorp",
                role="Engineer",
                company_researched=True,
                topics=[
                    PrepTopic(
                        topic="Coding Basics",
                        relevance="high",
                        difficulty="medium",
                    ),
                ],
                questions=[
                    PrepQuestion(
                        question="How would you design a REST API?",
                        category="technical",
                        difficulty="medium",
                    ),
                ],
                checklist=[
                    PrepChecklistItem(
                        id=1,
                        item="Review fundamentals",
                        time_minutes=30,
                        priority="high",
                    ),
                ],
                total_prep_minutes=30,
                total_prep_hours=0.5,
                progress_percentage=0.0,
                completed_items=0,
                total_items=1,
            )

            result = runner.invoke(app, ["interview-prep", "1"])

        assert result.exit_code == 0
        assert "TestCorp" in result.output

    def test_prep_shows_company_and_role(self, app_with_prep: Session) -> None:
        """Output includes company and role as context."""
        result = runner.invoke(app, ["interview-prep", "1"])

        assert result.exit_code == 0
        assert "Stripe" in result.output
        assert "Senior TPM" in result.output


# ---------------------------------------------------------------------------
# VAL-CLI-PREP-003: career interview-prep stories
# ---------------------------------------------------------------------------


class TestStoriesCommand:
    """Tests for `career interview-prep stories` subcommands."""

    def test_stories_list(self, stories_db: Session) -> None:
        """career interview-prep stories lists stories with titles and skills."""
        result = runner.invoke(app, ["interview-prep", "stories"])

        assert result.exit_code == 0
        assert "Led Cross-Team Migration" in result.output
        assert "Scaled AI Pipeline" in result.output
        # Should show skill tags
        assert "Python" in result.output
        # "Program Management" may be line-wrapped in the table
        assert "Program" in result.output and "Management" in result.output
        # Should show usage count column
        assert "Used" in result.output

    def test_stories_list_empty(self, db_session: Session) -> None:
        """Empty stories shows friendly message."""
        result = runner.invoke(app, ["interview-prep", "stories"])

        assert result.exit_code == 0
        assert "No STAR stories" in result.output or "no stories" in result.output.lower()

    def test_stories_add(self, db_session: Session) -> None:
        """career interview-prep stories add creates a new story."""
        result = runner.invoke(
            app,
            [
                "interview-prep",
                "stories",
                "add",
                "--title",
                "Improved CI Pipeline",
                "--situation",
                "Build times exceeded 30 minutes",
                "--task",
                "Reduce CI pipeline to under 10 minutes",
                "--action",
                "Parallelized tests, added caching, split builds",
                "--result",
                "Achieved 7 minute builds, 3x developer productivity",
                "--tags",
                "CI/CD,DevOps,Python",
            ],
        )

        assert result.exit_code == 0
        assert (
            "Improved CI Pipeline" in result.output
            or "Created" in result.output
            or "✓" in result.output
        )

        # Verify story persisted
        story = db_session.query(StarStory).filter(StarStory.profile_id == 1).first()
        assert story is not None
        assert story.title == "Improved CI Pipeline"
        assert "CI/CD" in story.skill_tags

    def test_stories_view(self, stories_db: Session) -> None:
        """career interview-prep stories view <id> shows full story."""
        story = stories_db.query(StarStory).filter(StarStory.profile_id == 1).first()
        result = runner.invoke(app, ["interview-prep", "stories", "view", str(story.id)])

        assert result.exit_code == 0
        assert story.title in result.output
        assert "Situation" in result.output
        assert "Task" in result.output
        assert "Action" in result.output
        assert "Result" in result.output

    def test_stories_view_invalid_id(self, db_session: Session) -> None:
        """View nonexistent story shows error, no traceback."""
        result = runner.invoke(app, ["interview-prep", "stories", "view", "999"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "Error" in result.output
        assert "Traceback" not in result.output

    def test_stories_edit(self, stories_db: Session) -> None:
        """career interview-prep stories edit <id> updates story."""
        story = stories_db.query(StarStory).filter(StarStory.profile_id == 1).first()
        result = runner.invoke(
            app,
            [
                "interview-prep",
                "stories",
                "edit",
                str(story.id),
                "--title",
                "Updated Title",
            ],
        )

        assert result.exit_code == 0
        assert "Updated" in result.output or "✓" in result.output

        # Verify update persisted
        stories_db.refresh(story)
        assert story.title == "Updated Title"

    def test_stories_edit_tags(self, stories_db: Session) -> None:
        """Editing tags updates skill_tags."""
        story = stories_db.query(StarStory).filter(StarStory.profile_id == 1).first()
        result = runner.invoke(
            app,
            [
                "interview-prep",
                "stories",
                "edit",
                str(story.id),
                "--tags",
                "Python,AWS,Docker",
            ],
        )

        assert result.exit_code == 0

        # Verify tags updated
        stories_db.refresh(story)
        assert "Docker" in story.skill_tags

    def test_stories_edit_invalid_id(self, db_session: Session) -> None:
        """Edit nonexistent story shows error."""
        result = runner.invoke(
            app,
            ["interview-prep", "stories", "edit", "999", "--title", "New"],
        )

        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "Error" in result.output


# ---------------------------------------------------------------------------
# Fix #5: CLI stories list shows usage count
# ---------------------------------------------------------------------------


class TestStoriesUsageCount:
    """Test that CLI stories list shows usage count column."""

    def test_usage_count_column_displayed(self, stories_db: Session) -> None:
        """Stories list shows 'Used' column header."""
        result = runner.invoke(app, ["interview-prep", "stories"])

        assert result.exit_code == 0
        assert "Used" in result.output

    def test_usage_count_zero_with_no_requirements(self, stories_db: Session) -> None:
        """Usage count is 0 when no job requirements exist."""
        result = runner.invoke(app, ["interview-prep", "stories"])

        assert result.exit_code == 0
        # Both stories should show 0 usage
        # Output contains "0" in the Used column
        lines = result.output.split("\n")
        # Find lines with story IDs - they should contain "0"
        for line in lines:
            if "Led Cross-Team" in line or "Scaled AI" in line:
                assert "0" in line

    def test_usage_count_matches_requirements(self, stories_db: Session) -> None:
        """Usage count reflects how many applications match story skills."""
        from career_os.models.models import Application
        from career_os.models.skills import JobRequirement

        # Create an application with requirements that match story skills
        app_obj = Application(
            profile_id=1,
            company="TestCo",
            role="Engineer",
            status="applied",
        )
        stories_db.add(app_obj)
        stories_db.flush()

        # Add a requirement matching "Python" (in both stories)
        req = JobRequirement(
            application_id=app_obj.id,
            profile_id=1,
            skill_name="Python",
            required_level="advanced",
            severity="critical",
        )
        stories_db.add(req)
        stories_db.commit()

        result = runner.invoke(app, ["interview-prep", "stories"])

        assert result.exit_code == 0
        # Both stories have Python tag, so each should show usage 1
        assert "1" in result.output
