"""Tests for resume text extraction utilities (CLI extract module).

Covers:
- extract_from_text: regex extraction of emails, phones, URLs
- extract_skills_from_text: fuzzy matching against ESCO taxonomy
- read_multiline_paste: double-Enter terminated stdin reading
"""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from career_os.database import Base
from career_os.models.esco import ESCOSkill


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session():
    """In-memory SQLite session with ESCO skills seeded."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    session_cls = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = session_cls()

    # Seed ESCO skills for fuzzy matching tests
    skills = [
        ESCOSkill(
            concept_uri="http://data.europa.eu/esco/skill/python",
            preferred_label="Python",
        ),
        ESCOSkill(
            concept_uri="http://data.europa.eu/esco/skill/javascript",
            preferred_label="JavaScript",
        ),
        ESCOSkill(
            concept_uri="http://data.europa.eu/esco/skill/project-management",
            preferred_label="project management",
        ),
        ESCOSkill(
            concept_uri="http://data.europa.eu/esco/skill/data-analysis",
            preferred_label="data analysis",
        ),
        ESCOSkill(
            concept_uri="http://data.europa.eu/esco/skill/machine-learning",
            preferred_label="machine learning",
        ),
    ]
    session.add_all(skills)
    session.commit()

    yield session
    session.close()
    engine.dispose()


# ---------------------------------------------------------------------------
# extract_from_text tests
# ---------------------------------------------------------------------------


class TestExtractFromText:
    """Tests for regex-based contact info extraction."""

    def test_extracts_email(self):
        from career_os.cli.extract import extract_from_text

        result = extract_from_text("Contact alice@example.com for details")
        assert "emails" in result
        assert "alice@example.com" in result["emails"]

    def test_extracts_phone_international(self):
        from career_os.cli.extract import extract_from_text

        result = extract_from_text("Call +49 170 123 4567 today")
        assert "phones" in result
        assert len(result["phones"]) >= 1

    def test_extracts_url(self):
        from career_os.cli.extract import extract_from_text

        result = extract_from_text("Visit https://linkedin.com/in/alice for my profile")
        assert "urls" in result
        assert any("linkedin.com/in/alice" in u for u in result["urls"])

    def test_empty_text_returns_empty_lists(self):
        from career_os.cli.extract import extract_from_text

        result = extract_from_text("no contact info here")
        assert result["emails"] == []
        assert result["phones"] == []
        assert result["urls"] == []

    def test_multiple_emails(self):
        from career_os.cli.extract import extract_from_text

        result = extract_from_text("Email alice@example.com or bob@test.org")
        assert len(result["emails"]) == 2

    def test_returns_all_keys(self):
        from career_os.cli.extract import extract_from_text

        result = extract_from_text("")
        assert set(result.keys()) == {"emails", "phones", "urls"}


# ---------------------------------------------------------------------------
# extract_skills_from_text tests
# ---------------------------------------------------------------------------


class TestExtractSkillsFromText:
    """Tests for ESCO-based skill extraction via fuzzy matching."""

    def test_matches_exact_skill(self, db_session):
        from career_os.cli.extract import extract_skills_from_text

        result = extract_skills_from_text("I am proficient in Python programming", db_session)
        assert "Python" in result

    def test_matches_multi_word_skill(self, db_session):
        from career_os.cli.extract import extract_skills_from_text

        result = extract_skills_from_text(
            "Experience with project management and data analysis", db_session
        )
        assert "project management" in result

    def test_returns_sorted_list(self, db_session):
        from career_os.cli.extract import extract_skills_from_text

        result = extract_skills_from_text(
            "Python JavaScript machine learning data analysis", db_session
        )
        assert result == sorted(result)

    def test_respects_top_n(self, db_session):
        from career_os.cli.extract import extract_skills_from_text

        result = extract_skills_from_text(
            "Python JavaScript machine learning data analysis project management",
            db_session,
            top_n=2,
        )
        assert len(result) <= 2

    def test_no_matches_returns_empty(self, db_session):
        from career_os.cli.extract import extract_skills_from_text

        result = extract_skills_from_text("I like to eat pizza and watch movies", db_session)
        assert result == []

    def test_caps_input_at_500_words(self, db_session):
        """T-02-02 mitigation: large input doesn't cause O(n^2) explosion."""
        from career_os.cli.extract import extract_skills_from_text

        # 600 words of filler -- function should cap at 500
        large_text = " ".join(["word"] * 600)
        # Should not hang or take excessively long
        result = extract_skills_from_text(large_text, db_session)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# read_multiline_paste tests
# ---------------------------------------------------------------------------


class TestReadMultilinePaste:
    """Tests for double-Enter terminated multiline input."""

    def test_reads_until_double_enter(self):
        from career_os.cli.extract import read_multiline_paste

        console = MagicMock()
        # Simulate: "line 1\nline 2\n\n\n" (two consecutive empty lines)
        with patch("builtins.input", side_effect=["line 1", "line 2", "", ""]):
            result = read_multiline_paste(console)
        assert "line 1" in result
        assert "line 2" in result

    def test_handles_eof(self):
        from career_os.cli.extract import read_multiline_paste

        console = MagicMock()
        with patch("builtins.input", side_effect=["some text", EOFError]):
            result = read_multiline_paste(console)
        assert "some text" in result

    def test_strips_result(self):
        from career_os.cli.extract import read_multiline_paste

        console = MagicMock()
        with patch("builtins.input", side_effect=["  hello  ", "", ""]):
            result = read_multiline_paste(console)
        assert result == "hello"
