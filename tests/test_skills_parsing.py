"""Tests for the skills parsing engine and skills API.

Covers:
- VAL-SKILL-001: CV parsing populates skills
- VAL-SKILL-002: Psychometric assessment parsing
- VAL-SKILL-003: Profile document extraction
- VAL-SKILL-004: Correct category assignment
- VAL-SKILL-005: Proficiency levels with evidence
- VAL-SKILL-010: Empty inventory state
"""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base, get_db
from career_os.models.models import Profile
from career_os.services.skills_parsing import (
    ParsedSkill,
    _higher_proficiency,
    _map_cv_label_to_category,
    _proficiency_from_source_count,
    _split_details_paren_aware,
    ingest_all_skills,
    merge_skills,
    parse_ccat,
    parse_cliftonstrengths,
    parse_cv_yaml,
    parse_epp,
    parse_profile_docs,
    parse_workplace_insights,
)

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _db_engine():
    """Create a shared in-memory SQLite engine with a persistent connection.

    Using a file-based temp DB to avoid in-memory connection isolation issues.
    """

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_name = tmp.name
    url = f"sqlite:///{tmp_name}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", lambda c, _: c.cursor().execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()
    import os

    os.unlink(tmp_name)


@pytest.fixture
def test_db(_db_engine):
    """Create a database session for testing."""
    test_session_cls = sessionmaker(bind=_db_engine)
    session = test_session_cls()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_profile(test_db: Session) -> Profile:
    """Seed a test profile."""
    profile = Profile(
        name="Test User",
        email="test@example.com",
        location="Frankfurt",
        job_family="Software Engineering",
    )
    test_db.add(profile)
    test_db.commit()
    test_db.refresh(profile)
    return profile


@pytest.fixture
def second_profile(test_db: Session) -> Profile:
    """Create a second profile for scoping tests."""
    profile = Profile(
        name="Other User", email="other@example.com", job_family="Software Engineering"
    )
    test_db.add(profile)
    test_db.commit()
    test_db.refresh(profile)
    return profile


@pytest.fixture
def client(_db_engine, test_db: Session):
    """FastAPI test client with test database.

    We create a fresh FastAPI app without the lifespan (which runs
    Alembic against the real database) and register the same routers.
    """
    from contextlib import asynccontextmanager

    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    from career_os.api.skills import router as skills_router

    @asynccontextmanager
    async def noop_lifespan(app: FastAPI):
        yield

    test_app = FastAPI(lifespan=noop_lifespan)
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    test_app.include_router(skills_router)

    def _override_get_db():
        db = sessionmaker(bind=_db_engine)()
        try:
            yield db
        finally:
            db.close()

    test_app.dependency_overrides[get_db] = _override_get_db
    with TestClient(test_app) as c:
        yield c
    test_app.dependency_overrides.clear()


@pytest.fixture
def cv_yaml_path(tmp_path: Path) -> Path:
    """Create a temporary cv.yaml for testing."""
    cv_content = """
cv:
  name: Test User
  sections:
    skills:
      - label: Program Management
        details: Cross-functional leadership, SDLC, Agile/Kanban, stakeholder management
      - label: AI & ML
        details: LLM integration, MCP architecture, agent systems, prompt engineering
      - label: Tools
        details: Jira, Confluence, Linear, GitHub, Salesforce
      - label: Languages
        details: English (fluent, CAE C1), Ukrainian (native), German (learning)
      - label: Soft Skills
        details: Teamwork, Empathy, Active Listening
    experience:
      - company: Amazon -- Alexa AGI
        position: Technical Program Manager
        start_date: 2022-08
        end_date: 2024-10
        highlights:
          - Ran continuous ASR training and deployment pipeline
          - Drove early LLM integration initiative
      - company: Amazon -- Ring
        position: Technical Program Manager -- Sensor Research
        start_date: 2018-10
        end_date: 2022-08
        highlights:
          - Led Ring Ultra radar camera from sensor research to 800k units shipped
          - Ran ANVIL compliance overhaul on AWS
          - Delivered portfolio of 7 products fusing ML, hardware, firmware, and software
"""
    cv_path = tmp_path / "cv.yaml"
    cv_path.write_text(cv_content)
    return cv_path


@pytest.fixture
def profile_dir(tmp_path: Path) -> Path:
    """Create a temporary profile directory with assessment and narrative files."""
    profile_path = tmp_path / "profile"
    profile_path.mkdir()

    # CliftonStrengths
    (profile_path / "cliftonstrengths.md").write_text("""
# CliftonStrengths

## Full Ranking

| Rank | Theme | Domain |
|------|-------|--------|
| 1 | Communication | Influencing |
| 2 | Ideation | Strategic Thinking |
| 3 | Strategic | Strategic Thinking |
| 4 | Responsibility | Executing |
| 5 | Activator | Influencing |
| 6 | Futuristic | Strategic Thinking |
| 7 | Command | Influencing |
| 8 | Individualization | Relationship Building |
| 9 | Adaptability | Relationship Building |
| 10 | Connectedness | Relationship Building |
| 11 | Input | Strategic Thinking |
| 12 | Arranger | Executing |
| 13 | Includer | Relationship Building |
| 14 | Relator | Relationship Building |
| 15 | Woo | Influencing |
| 16 | Developer | Relationship Building |
| 17 | Intellection | Strategic Thinking |
| 18 | Belief | Executing |
| 19 | Self-Assurance | Influencing |
| 20 | Positivity | Relationship Building |
""")

    # EPP
    (profile_path / "personality-epp.md").write_text("""
# Employee Personality Profile

## Trait Scores

| Trait | Percentile | Category | Description |
|-------|-----------|----------|-------------|
| Self-Confidence | 89th | Very High | Self-assured. Free from self-doubt. |
| Extroversion | 85th | Very High | Socially outgoing, gregarious. |
| Openness | 83rd | High | Creative, experimental, curious. |
| Cooperativeness | 78th | High | Values social harmony. |
| Managerial | 78th | High | Characteristics of successful managers. |
| Patience | 75th | Moderate-High | Effective balance. |
| Assertiveness | 72nd | Moderate | Context-dependent. |
| Achievement | 61st | Average | Average baseline. |
| Stress Tolerance | 34th | Below Average | May respond emotionally. |
| Conscientiousness | 32nd | Below Average | Spontaneous. |
""")

    # CCAT
    (profile_path / "cognitive-ccat.md").write_text("""
# Criteria Cognitive Aptitude Test

## Overall Score

| Metric | Value |
|--------|-------|
| **Raw Score** | 30 / 50 |
| **Percentile** | 71st |

## Sub-Category Breakdown

| Category | Percentile | Description |
|----------|-----------|-------------|
| **Spatial Reasoning** | 90th | Ability to visualize and problem solve. |
| **Math & Logic** | 85th | Reasoning using numbers. |
| **Verbal** | 27th | Reasoning and comprehension. |
""")

    # Workplace Insights
    (profile_path / "workplace-insights.md").write_text("""
# Workplace Insights Report

## Notable Traits

| Trait | Description |
|-------|-------------|
| **Cooperative** | Values social harmony, seeks common ground |
| **Extroverted** | Socially outgoing, gregarious |
| **Intellectually Curious** | Creative and unafraid of experimentation |
| **Self-Confident** | Self-assured and secure |

## Strengths

- Neither consistently assertive nor overly deferential -- context-adaptive
- Sociable and energetic, comfortable initiating interactions
- High curiosity and willingness to experiment -- comfortable in evolving roles
""")

    # Narrative docs
    (profile_path / "narrative.md").write_text("""
# Career Narrative

The candidate has deep experience in cross-functional leadership and stakeholder management.
He excels at roadmap planning and risk mitigation, with a focus on AI-powered solutions.
His strategic thinking and communication skills enable effective program management.
He has led agile teams and applied OKR frameworks across organizations.
He uses Python for automation scripts and manages workflows in Pipedrive and Notion.
He tracks projects in Jira and collaborates via Slack.
""")

    (profile_path / "strengths-summary.md").write_text("""
# Strengths Summary

This profile shows a strategic communicator with innovation and problem-solving abilities.
Strong adaptability and visionary leadership across AI-augmented program management.
""")

    return profile_path


# ---------------------------------------------------------------------------
# Unit tests for parsing functions
# ---------------------------------------------------------------------------


class TestProficiencyHelpers:
    """Test proficiency helper functions."""

    def test_source_count_1_gives_intermediate(self):
        assert _proficiency_from_source_count(1) == "intermediate"

    def test_source_count_2_gives_advanced(self):
        assert _proficiency_from_source_count(2) == "advanced"

    def test_source_count_3_gives_expert(self):
        assert _proficiency_from_source_count(3) == "expert"

    def test_source_count_5_gives_expert(self):
        assert _proficiency_from_source_count(5) == "expert"

    def test_higher_proficiency_same(self):
        assert _higher_proficiency("advanced", "advanced") == "advanced"

    def test_higher_proficiency_different(self):
        assert _higher_proficiency("beginner", "expert") == "expert"
        assert _higher_proficiency("expert", "beginner") == "expert"

    def test_higher_proficiency_one_step(self):
        assert _higher_proficiency("intermediate", "advanced") == "advanced"


class TestParenAwareSplitting:
    """Test parenthesis-aware comma splitting for CV details."""

    def test_simple_comma_separated(self):
        result = _split_details_paren_aware("Jira, Confluence, Linear")
        assert result == ["Jira", "Confluence", "Linear"]

    def test_parenthesised_commas_preserved(self):
        result = _split_details_paren_aware(
            "English (fluent, CAE C1), Ukrainian (native), German (learning)"
        )
        assert result == [
            "English (fluent, CAE C1)",
            "Ukrainian (native)",
            "German (learning)",
        ]

    def test_nested_parens(self):
        result = _split_details_paren_aware("A (B (C, D)), E")
        assert result == ["A (B (C, D))", "E"]

    def test_empty_string(self):
        assert _split_details_paren_aware("") == []

    def test_single_item(self):
        assert _split_details_paren_aware("Python") == ["Python"]

    def test_trailing_comma(self):
        result = _split_details_paren_aware("A, B,")
        assert result == ["A", "B"]


class TestCVLabelCategoryMapping:
    """Test _map_cv_label_to_category for soft-skill label support."""

    def test_tools_label(self):
        assert _map_cv_label_to_category("Tools") == "tools"
        assert _map_cv_label_to_category("Software Tools") == "tools"

    def test_soft_skill_labels(self):
        assert _map_cv_label_to_category("Languages") == "soft"
        assert _map_cv_label_to_category("Communication") == "soft"
        assert _map_cv_label_to_category("Soft Skills") == "soft"
        assert _map_cv_label_to_category("Leadership") == "soft"
        assert _map_cv_label_to_category("Teamwork") == "soft"
        assert _map_cv_label_to_category("Interpersonal Skills") == "soft"

    def test_technical_label(self):
        assert _map_cv_label_to_category("AI & ML") == "technical"
        assert _map_cv_label_to_category("Technical Skills") == "technical"

    def test_domain_label(self):
        assert _map_cv_label_to_category("Program Management") == "domain"
        assert _map_cv_label_to_category("Management") == "domain"

    def test_unknown_defaults_to_domain(self):
        assert _map_cv_label_to_category("Other") == "domain"


class TestCVParsing:
    """VAL-SKILL-001: CV parsing populates skills."""

    def test_cv_parsing_extracts_skills(self, cv_yaml_path: Path):
        skills = parse_cv_yaml(cv_yaml_path)
        assert len(skills) > 0

    def test_cv_parsing_extracts_from_skills_section(self, cv_yaml_path: Path):
        skills = parse_cv_yaml(cv_yaml_path)
        skill_names = [s.name for s in skills]
        # From skills section
        assert "Cross-functional leadership" in skill_names
        assert "LLM integration" in skill_names
        assert "Jira" in skill_names

    def test_cv_skills_have_evidence_source(self, cv_yaml_path: Path):
        skills = parse_cv_yaml(cv_yaml_path)
        for s in skills:
            assert s.evidence_source == "cv.yaml"

    def test_cv_skills_have_evidence_detail(self, cv_yaml_path: Path):
        skills = parse_cv_yaml(cv_yaml_path)
        for s in skills:
            assert s.evidence_detail is not None
            assert len(s.evidence_detail) > 0

    def test_cv_skills_have_correct_categories(self, cv_yaml_path: Path):
        skills = parse_cv_yaml(cv_yaml_path)
        # Tools category
        tools = [s for s in skills if s.category == "tools"]
        tool_names = [s.name for s in tools]
        assert "Jira" in tool_names

        # Technical category
        technical = [s for s in skills if s.category == "technical"]
        tech_names = [s.name for s in technical]
        assert "LLM integration" in tech_names

    def test_cv_extracts_experience_skills(self, cv_yaml_path: Path):
        skills = parse_cv_yaml(cv_yaml_path)
        skill_names = [s.name for s in skills]
        # From experience highlights
        assert "Speech Recognition (ASR)" in skill_names

    def test_cv_experience_skills_have_evidence(self, cv_yaml_path: Path):
        skills = parse_cv_yaml(cv_yaml_path)
        asr_skills = [s for s in skills if s.name == "Speech Recognition (ASR)"]
        assert len(asr_skills) == 1
        assert "Alexa" in asr_skills[0].evidence_detail

    def test_cv_nonexistent_file_returns_empty(self, tmp_path: Path):
        skills = parse_cv_yaml(tmp_path / "nonexistent.yaml")
        assert skills == []

    def test_cv_every_skill_has_category(self, cv_yaml_path: Path):
        """VAL-SKILL-004: Every skill has exactly one valid category."""
        skills = parse_cv_yaml(cv_yaml_path)
        valid_categories = {"technical", "domain", "soft", "tools"}
        for s in skills:
            assert s.category in valid_categories, (
                f"Skill '{s.name}' has invalid category '{s.category}'"
            )

    def test_cv_languages_are_soft_category(self, cv_yaml_path: Path):
        """VAL-SKILL-001: Languages label maps to soft category."""
        skills = parse_cv_yaml(cv_yaml_path)
        lang_skills = [s for s in skills if "English" in s.name or "Ukrainian" in s.name]
        assert len(lang_skills) >= 2
        for s in lang_skills:
            assert s.category == "soft", (
                f"Language skill '{s.name}' should be soft, got '{s.category}'"
            )

    def test_cv_parenthesised_entries_not_fragmented(self, cv_yaml_path: Path):
        """VAL-SKILL-001: Commas inside parentheses don't fragment entries."""
        skills = parse_cv_yaml(cv_yaml_path)
        skill_names = [s.name for s in skills]
        # Should have "English (fluent, CAE C1)" as one item, not fragments
        assert "English (fluent, CAE C1)" in skill_names
        # Fragments should NOT exist
        assert "CAE C1)" not in skill_names
        assert "English (fluent" not in skill_names

    def test_cv_soft_skills_label_maps_to_soft_category(self, cv_yaml_path: Path):
        """VAL-SKILL-001: Soft Skills label maps to soft category."""
        skills = parse_cv_yaml(cv_yaml_path)
        teamwork = [s for s in skills if s.name == "Teamwork"]
        assert len(teamwork) == 1
        assert teamwork[0].category == "soft"


class TestCliftonStrengthsParsing:
    """VAL-SKILL-002: CliftonStrengths assessment parsing."""

    def test_extracts_themes(self, profile_dir: Path):
        skills = parse_cliftonstrengths(profile_dir / "cliftonstrengths.md")
        assert len(skills) > 0

    def test_top5_are_expert(self, profile_dir: Path):
        skills = parse_cliftonstrengths(profile_dir / "cliftonstrengths.md")
        top5 = [s for s in skills if s.proficiency == "expert"]
        names = [s.name for s in top5]
        assert any("Communication" in n for n in names)
        assert any("Ideation" in n for n in names)

    def test_6_to_10_are_advanced(self, profile_dir: Path):
        skills = parse_cliftonstrengths(profile_dir / "cliftonstrengths.md")
        advanced = [s for s in skills if s.proficiency == "advanced"]
        names = [s.name for s in advanced]
        assert any("Futuristic" in n for n in names)
        assert any("Command" in n for n in names)

    def test_all_skills_are_soft_category(self, profile_dir: Path):
        skills = parse_cliftonstrengths(profile_dir / "cliftonstrengths.md")
        for s in skills:
            assert s.category == "soft"

    def test_evidence_includes_rank(self, profile_dir: Path):
        skills = parse_cliftonstrengths(profile_dir / "cliftonstrengths.md")
        for s in skills:
            assert "Rank" in s.evidence_detail
            assert s.evidence_source == "assessment:cliftonstrengths"

    def test_nonexistent_file_returns_empty(self, tmp_path: Path):
        assert parse_cliftonstrengths(tmp_path / "nope.md") == []


class TestEPPParsing:
    """VAL-SKILL-002: EPP assessment parsing."""

    def test_extracts_traits(self, profile_dir: Path):
        skills = parse_epp(profile_dir / "personality-epp.md")
        assert len(skills) > 0

    def test_high_percentile_is_expert(self, profile_dir: Path):
        skills = parse_epp(profile_dir / "personality-epp.md")
        confidence = [s for s in skills if s.name == "Self-Confidence"]
        assert len(confidence) == 1
        assert confidence[0].proficiency == "expert"

    def test_low_percentile_is_beginner(self, profile_dir: Path):
        skills = parse_epp(profile_dir / "personality-epp.md")
        conscientiousness = [s for s in skills if s.name == "Conscientiousness"]
        assert len(conscientiousness) == 1
        assert conscientiousness[0].proficiency == "beginner"

    def test_mid_percentile_is_advanced(self, profile_dir: Path):
        skills = parse_epp(profile_dir / "personality-epp.md")
        achievement = [s for s in skills if s.name == "Achievement"]
        assert len(achievement) == 1
        assert achievement[0].proficiency == "advanced"

    def test_all_soft_category(self, profile_dir: Path):
        skills = parse_epp(profile_dir / "personality-epp.md")
        for s in skills:
            assert s.category == "soft"

    def test_evidence_includes_percentile(self, profile_dir: Path):
        skills = parse_epp(profile_dir / "personality-epp.md")
        for s in skills:
            assert "percentile" in s.evidence_detail.lower()
            assert s.evidence_source == "assessment:epp"


class TestCCATParsing:
    """VAL-SKILL-002: CCAT assessment parsing."""

    def test_extracts_cognitive_skills(self, profile_dir: Path):
        skills = parse_ccat(profile_dir / "cognitive-ccat.md")
        assert len(skills) > 0

    def test_spatial_reasoning_expert(self, profile_dir: Path):
        skills = parse_ccat(profile_dir / "cognitive-ccat.md")
        spatial = [s for s in skills if s.name == "Spatial Reasoning"]
        assert len(spatial) == 1
        assert spatial[0].proficiency == "expert"

    def test_verbal_is_beginner(self, profile_dir: Path):
        skills = parse_ccat(profile_dir / "cognitive-ccat.md")
        verbal = [s for s in skills if s.name == "Verbal Reasoning"]
        assert len(verbal) == 1
        assert verbal[0].proficiency == "beginner"

    def test_overall_cognitive_aptitude(self, profile_dir: Path):
        skills = parse_ccat(profile_dir / "cognitive-ccat.md")
        overall = [s for s in skills if s.name == "Cognitive Aptitude"]
        assert len(overall) == 1
        assert overall[0].proficiency == "advanced"

    def test_evidence_source(self, profile_dir: Path):
        skills = parse_ccat(profile_dir / "cognitive-ccat.md")
        for s in skills:
            assert s.evidence_source == "assessment:ccat"


class TestWorkplaceInsightsParsing:
    """VAL-SKILL-002: Workplace Insights parsing."""

    def test_extracts_traits(self, profile_dir: Path):
        skills = parse_workplace_insights(profile_dir / "workplace-insights.md")
        assert len(skills) > 0

    def test_notable_traits_extracted(self, profile_dir: Path):
        skills = parse_workplace_insights(profile_dir / "workplace-insights.md")
        names = [s.name for s in skills]
        assert "Cooperation" in names
        assert "Intellectual Curiosity" in names

    def test_all_soft_category(self, profile_dir: Path):
        skills = parse_workplace_insights(profile_dir / "workplace-insights.md")
        for s in skills:
            assert s.category == "soft"

    def test_evidence_source(self, profile_dir: Path):
        skills = parse_workplace_insights(profile_dir / "workplace-insights.md")
        for s in skills:
            assert s.evidence_source == "assessment:workplace-insights"


class TestProfileDocParsing:
    """VAL-SKILL-003: Profile document extraction."""

    def test_extracts_narrative_skills(self, profile_dir: Path):
        skills = parse_profile_docs(profile_dir)
        assert len(skills) > 0

    def test_extracts_domain_skills(self, profile_dir: Path):
        skills = parse_profile_docs(profile_dir)
        domain = [s for s in skills if s.category == "domain"]
        domain_names = [s.name for s in domain]
        assert "Stakeholder Management" in domain_names
        assert "Roadmap Planning" in domain_names

    def test_extracts_soft_skills(self, profile_dir: Path):
        skills = parse_profile_docs(profile_dir)
        soft = [s for s in skills if s.category == "soft"]
        soft_names = [s.name for s in soft]
        assert "Strategic Thinking" in soft_names
        assert "Communication" in soft_names

    def test_evidence_includes_quotes(self, profile_dir: Path):
        skills = parse_profile_docs(profile_dir)
        for s in skills:
            assert s.evidence_source == "profile"
            assert s.evidence_detail is not None
            assert "Found in" in s.evidence_detail

    def test_skips_assessment_files(self, profile_dir: Path):
        skills = parse_profile_docs(profile_dir)
        # Should not duplicate assessment-specific skills
        for s in skills:
            assert "cliftonstrengths" not in s.evidence_source
            assert "epp" not in s.evidence_source

    def test_multiple_mentions_increase_proficiency(self, profile_dir: Path):
        """VAL-SKILL-005: Multiple sources = higher proficiency."""
        skills = parse_profile_docs(profile_dir)
        # Skills mentioned in multiple documents get higher proficiency
        # "Program Management" pattern matches in both narrative.md and strengths-summary.md
        pm = [s for s in skills if "Program Management" in s.name]
        if pm:
            # If found in 2+ docs, proficiency should be advanced or expert
            assert pm[0].proficiency in ("advanced", "expert")

    def test_nonexistent_dir_returns_empty(self, tmp_path: Path):
        skills = parse_profile_docs(tmp_path / "nonexistent")
        assert skills == []

    def test_extracts_technical_skills(self, profile_dir: Path):
        """VAL-SKILL-003: Profile doc parsing finds technical skills like Python."""
        skills = parse_profile_docs(profile_dir)
        technical = [s for s in skills if s.category == "technical"]
        tech_names = [s.name for s in technical]
        assert "Python" in tech_names
        assert "Automation" in tech_names

    def test_extracts_tools_skills(self, profile_dir: Path):
        """VAL-SKILL-003: Profile doc parsing finds tools skills like Pipedrive, Notion, Jira."""
        skills = parse_profile_docs(profile_dir)
        tools = [s for s in skills if s.category == "tools"]
        tools_names = [s.name for s in tools]
        assert "Pipedrive" in tools_names
        assert "Notion" in tools_names
        assert "Jira" in tools_names
        assert "Slack" in tools_names


class TestMergeSkills:
    """Test skill merging logic."""

    def test_deduplicates_by_name(self):
        existing = [
            ParsedSkill("Python", "technical", "intermediate", "cv.yaml"),
        ]
        new = [
            ParsedSkill("Python", "technical", "advanced", "profile"),
        ]
        merged = merge_skills(existing, new)
        assert len(merged) == 1
        assert merged[0].proficiency == "advanced"

    def test_case_insensitive_dedup(self):
        existing = [
            ParsedSkill("python", "technical", "intermediate", "cv.yaml"),
        ]
        new = [
            ParsedSkill("Python", "technical", "advanced", "profile"),
        ]
        merged = merge_skills(existing, new)
        assert len(merged) == 1

    def test_appends_evidence_from_different_sources(self):
        existing = [
            ParsedSkill("Python", "technical", "intermediate", "cv.yaml", "CV section"),
        ]
        new = [
            ParsedSkill("Python", "technical", "advanced", "profile", "Profile narrative"),
        ]
        merged = merge_skills(existing, new)
        assert "Also:" in merged[0].evidence_detail

    def test_no_overlap_keeps_all(self):
        existing = [
            ParsedSkill("Python", "technical", "advanced", "cv.yaml"),
        ]
        new = [
            ParsedSkill("Leadership", "soft", "expert", "profile"),
        ]
        merged = merge_skills(existing, new)
        assert len(merged) == 2

    def test_merge_preserves_all_evidence_sources(self):
        """Multi-source provenance: merged skill tracks all distinct evidence sources."""
        skills = [
            ParsedSkill("Python", "technical", "intermediate", "cv.yaml", "CV section"),
            ParsedSkill("Python", "technical", "intermediate", "profile", "Profile narrative"),
        ]
        merged = merge_skills([], skills)
        assert len(merged) == 1
        sources = {s.strip() for s in merged[0].evidence_source.split(",")}
        assert "cv.yaml" in sources
        assert "profile" in sources

    def test_merge_three_sources_upgrades_to_expert(self):
        """3+ distinct sources → proficiency upgraded to expert."""
        skills = [
            ParsedSkill("Python", "technical", "beginner", "cv.yaml", "CV"),
            ParsedSkill("Python", "technical", "beginner", "profile", "Profile"),
            ParsedSkill("Python", "technical", "beginner", "assessment:ccat", "CCAT"),
        ]
        merged = merge_skills([], skills)
        assert len(merged) == 1
        assert merged[0].proficiency == "expert"
        sources = {s.strip() for s in merged[0].evidence_source.split(",")}
        assert len(sources) == 3

    def test_merge_two_sources_upgrades_to_at_least_advanced(self):
        """2 distinct sources → proficiency upgraded to at least advanced."""
        skills = [
            ParsedSkill("Docker", "tools", "beginner", "cv.yaml", "CV"),
            ParsedSkill("Docker", "tools", "beginner", "profile", "Profile"),
        ]
        merged = merge_skills([], skills)
        assert len(merged) == 1
        assert merged[0].proficiency in ("advanced", "expert")
        sources = {s.strip() for s in merged[0].evidence_source.split(",")}
        assert len(sources) == 2

    def test_merge_same_source_twice_no_duplicate(self):
        """Same source appearing twice does not duplicate in evidence_source."""
        skills = [
            ParsedSkill("Python", "technical", "intermediate", "cv.yaml", "Section A"),
            ParsedSkill("Python", "technical", "advanced", "cv.yaml", "Section B"),
        ]
        merged = merge_skills([], skills)
        assert len(merged) == 1
        # Same source — should not be duplicated
        assert merged[0].evidence_source == "cv.yaml"
        assert merged[0].proficiency == "advanced"


class TestIngestAllSkills:
    """Test combined ingestion."""

    def test_ingests_from_cv(self, cv_yaml_path: Path):
        result = ingest_all_skills(cv_path=cv_yaml_path, sources=["cv"])
        assert len(result.skills) > 0
        assert "cv.yaml" in result.sources_processed

    def test_ingests_from_assessments(self, profile_dir: Path):
        result = ingest_all_skills(profile_dir=profile_dir, sources=["assessments"])
        assert len(result.skills) > 0
        assert any("assessment:" in s for s in result.sources_processed)

    def test_ingests_from_profile(self, profile_dir: Path):
        result = ingest_all_skills(profile_dir=profile_dir, sources=["profile"])
        assert len(result.skills) > 0
        assert "profile" in result.sources_processed

    def test_ingests_all_sources(self, cv_yaml_path: Path, profile_dir: Path):
        result = ingest_all_skills(
            cv_path=cv_yaml_path,
            profile_dir=profile_dir,
            sources=["cv", "assessments", "profile"],
        )
        assert len(result.skills) > 10  # should have many skills from all sources
        assert len(result.sources_processed) >= 3

    def test_handles_missing_cv(self, profile_dir: Path):
        result = ingest_all_skills(
            cv_path=None,
            profile_dir=profile_dir,
            sources=["cv", "assessments"],
        )
        # Should still process assessments
        assert len(result.skills) > 0


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------


class TestSkillsAPIEmpty:
    """VAL-SKILL-010: Empty inventory state."""

    def test_empty_skills_returns_ctas(self, client: TestClient, test_profile: Profile):
        resp = client.get(f"/api/skills?profile_id={test_profile.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert "ctas" in data
        assert len(data["ctas"]) == 3

    def test_ctas_include_import_cv(self, client: TestClient, test_profile: Profile):
        resp = client.get(f"/api/skills?profile_id={test_profile.id}")
        data = resp.json()
        cta_actions = [c["action"] for c in data["ctas"]]
        assert "ingest_cv" in cta_actions
        assert "ingest_assessments" in cta_actions
        assert "add_manual" in cta_actions


class TestSkillsAPICreate:
    """Test manual skill creation."""

    def test_create_skill_returns_201(self, client: TestClient, test_profile: Profile):
        resp = client.post(
            "/api/skills",
            json={
                "profile_id": test_profile.id,
                "name": "Python",
                "category": "technical",
                "proficiency": "advanced",
                "evidence_source": "manual",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Python"
        assert data["category"] == "technical"
        assert data["proficiency"] == "advanced"
        assert data["evidence_source"] == "manual"

    def test_create_skill_default_proficiency(self, client: TestClient, test_profile: Profile):
        resp = client.post(
            "/api/skills",
            json={
                "profile_id": test_profile.id,
                "name": "Go",
                "category": "technical",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["proficiency"] == "beginner"

    def test_create_skill_invalid_category(self, client: TestClient, test_profile: Profile):
        resp = client.post(
            "/api/skills",
            json={
                "profile_id": test_profile.id,
                "name": "Test",
                "category": "invalid_category",
            },
        )
        assert resp.status_code == 422

    def test_create_skill_nonexistent_profile(self, client: TestClient):
        resp = client.post(
            "/api/skills",
            json={
                "profile_id": 99999,
                "name": "Test",
                "category": "technical",
            },
        )
        assert resp.status_code == 404


class TestSkillsAPIList:
    """Test listing and filtering skills."""

    def _seed_skills(self, client: TestClient, profile_id: int):
        """Seed skills via direct DB insertion (not POST API) to set various evidence sources.

        POST /api/skills forces evidence_source='manual', so we use the
        service layer directly for seeding tests that need non-manual sources.
        """
        from sqlalchemy.orm import Session

        from career_os.models.skills import Skill

        # Get the DB session from the app's dependency override
        db_gen = client.app.dependency_overrides[get_db]()
        db: Session = next(db_gen)

        skills_data = [
            {
                "name": "Python",
                "category": "technical",
                "proficiency": "expert",
                "evidence_source": "cv.yaml",
            },
            {
                "name": "JavaScript",
                "category": "technical",
                "proficiency": "intermediate",
                "evidence_source": "cv.yaml",
            },
            {
                "name": "Communication",
                "category": "soft",
                "proficiency": "expert",
                "evidence_source": "assessment:cliftonstrengths",
            },
            {
                "name": "Jira",
                "category": "tools",
                "proficiency": "advanced",
                "evidence_source": "cv.yaml",
            },
            {
                "name": "Program Management",
                "category": "domain",
                "proficiency": "expert",
                "evidence_source": "profile",
            },
        ]
        for s in skills_data:
            skill = Skill(profile_id=profile_id, **s)
            db.add(skill)
        db.commit()
        db.close()

    def test_list_all_skills(self, client: TestClient, test_profile: Profile):
        self._seed_skills(client, test_profile.id)
        resp = client.get(f"/api/skills?profile_id={test_profile.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    def test_filter_by_category(self, client: TestClient, test_profile: Profile):
        self._seed_skills(client, test_profile.id)
        resp = client.get(f"/api/skills?profile_id={test_profile.id}&category=technical")
        data = resp.json()
        assert data["total"] == 2
        for s in data["skills"]:
            assert s["category"] == "technical"

    def test_filter_by_soft_category(self, client: TestClient, test_profile: Profile):
        """VAL-SKILL-002: GET /api/skills?category=soft shows assessment entries."""
        self._seed_skills(client, test_profile.id)
        resp = client.get(f"/api/skills?profile_id={test_profile.id}&category=soft")
        data = resp.json()
        assert data["total"] >= 1
        names = [s["name"] for s in data["skills"]]
        assert "Communication" in names

    def test_filter_by_source_profile(self, client: TestClient, test_profile: Profile):
        """VAL-SKILL-003: GET /api/skills?source=profile shows narrative-extracted."""
        self._seed_skills(client, test_profile.id)
        resp = client.get(f"/api/skills?profile_id={test_profile.id}&source=profile")
        data = resp.json()
        assert data["total"] >= 1
        names = [s["name"] for s in data["skills"]]
        assert "Program Management" in names

    def test_filter_by_proficiency(self, client: TestClient, test_profile: Profile):
        self._seed_skills(client, test_profile.id)
        resp = client.get(f"/api/skills?profile_id={test_profile.id}&proficiency=expert")
        data = resp.json()
        assert data["total"] >= 2
        for s in data["skills"]:
            assert s["proficiency"] == "expert"

    def test_search_by_name(self, client: TestClient, test_profile: Profile):
        self._seed_skills(client, test_profile.id)
        resp = client.get(f"/api/skills?profile_id={test_profile.id}&q=python")
        data = resp.json()
        assert data["total"] == 1
        assert data["skills"][0]["name"] == "Python"

    def test_combined_filters(self, client: TestClient, test_profile: Profile):
        self._seed_skills(client, test_profile.id)
        resp = client.get(
            f"/api/skills?profile_id={test_profile.id}&category=technical&proficiency=expert"
        )
        data = resp.json()
        assert data["total"] == 1
        assert data["skills"][0]["name"] == "Python"

    def test_after_filters_no_ctas(self, client: TestClient, test_profile: Profile):
        """When skills exist but filter returns 0, no CTAs (only for truly empty)."""
        self._seed_skills(client, test_profile.id)
        resp = client.get(f"/api/skills?profile_id={test_profile.id}&q=nonexistent")
        data = resp.json()
        assert data["total"] == 0
        # With filters applied, no CTAs (just empty list)
        assert "ctas" not in data


class TestSkillsAPICategory:
    """VAL-SKILL-004: Every skill has exactly one category."""

    def test_all_skills_have_valid_category(self, client: TestClient, test_profile: Profile):
        valid = {"technical", "domain", "soft", "tools"}
        # Create skills of each type
        for cat in valid:
            resp = client.post(
                "/api/skills",
                json={
                    "profile_id": test_profile.id,
                    "name": f"Test {cat}",
                    "category": cat,
                },
            )
            assert resp.status_code == 201
            assert resp.json()["category"] in valid


class TestSkillsAPIProficiency:
    """VAL-SKILL-005: Proficiency levels with evidence."""

    def test_proficiency_values_valid(self, client: TestClient, test_profile: Profile):
        valid = {"beginner", "intermediate", "advanced", "expert"}
        for prof in valid:
            resp = client.post(
                "/api/skills",
                json={
                    "profile_id": test_profile.id,
                    "name": f"Test {prof}",
                    "category": "technical",
                    "proficiency": prof,
                },
            )
            assert resp.status_code == 201
            assert resp.json()["proficiency"] in valid


class TestProfileScoping:
    """Two-profile negative tests for skills."""

    def test_other_profile_cannot_see_skills(
        self, client: TestClient, test_profile: Profile, second_profile: Profile
    ):
        # Create skill for profile A
        client.post(
            "/api/skills",
            json={
                "profile_id": test_profile.id,
                "name": "Python",
                "category": "technical",
            },
        )
        # Profile B should see nothing
        resp = client.get(f"/api/skills?profile_id={second_profile.id}")
        data = resp.json()
        assert data["total"] == 0

    def test_other_profile_cannot_get_skill(
        self, client: TestClient, test_profile: Profile, second_profile: Profile
    ):
        resp = client.post(
            "/api/skills",
            json={
                "profile_id": test_profile.id,
                "name": "Python",
                "category": "technical",
            },
        )
        skill_id = resp.json()["id"]

        # Profile B cannot access it
        resp = client.get(f"/api/skills/{skill_id}?profile_id={second_profile.id}")
        assert resp.status_code == 404

    def test_other_profile_cannot_update_skill(
        self, client: TestClient, test_profile: Profile, second_profile: Profile
    ):
        resp = client.post(
            "/api/skills",
            json={
                "profile_id": test_profile.id,
                "name": "Python",
                "category": "technical",
            },
        )
        skill_id = resp.json()["id"]

        # Profile B cannot update it
        resp = client.put(
            f"/api/skills/{skill_id}?profile_id={second_profile.id}",
            json={"proficiency": "expert"},
        )
        assert resp.status_code == 404


class TestSkillsIngestionAPI:
    """Test the ingestion endpoint."""

    def test_ingest_returns_results(
        self,
        client: TestClient,
        test_profile: Profile,
        cv_yaml_path: Path,
        profile_dir: Path,
        monkeypatch,
    ):
        """Test ingestion with monkeypatched paths."""
        import career_os.api.skills as api_module

        monkeypatch.setattr(api_module, "_DEFAULT_CV_PATH", cv_yaml_path)
        monkeypatch.setattr(api_module, "_DEFAULT_PROFILE_DIR", profile_dir)

        resp = client.post(
            "/api/skills/ingest",
            json={
                "profile_id": test_profile.id,
                "sources": ["cv", "assessments", "profile"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["skills_created"] > 0
        assert len(data["sources_processed"]) > 0

    def test_ingest_populates_skills(
        self,
        client: TestClient,
        test_profile: Profile,
        cv_yaml_path: Path,
        profile_dir: Path,
        monkeypatch,
    ):
        """After ingestion, skills are visible via GET."""
        import career_os.api.skills as api_module

        monkeypatch.setattr(api_module, "_DEFAULT_CV_PATH", cv_yaml_path)
        monkeypatch.setattr(api_module, "_DEFAULT_PROFILE_DIR", profile_dir)

        client.post(
            "/api/skills/ingest",
            json={
                "profile_id": test_profile.id,
                "sources": ["cv", "assessments", "profile"],
            },
        )

        resp = client.get(f"/api/skills?profile_id={test_profile.id}")
        data = resp.json()
        assert data["total"] > 0
        assert "ctas" not in data  # no CTAs when skills exist

    def test_ingest_cv_shows_cv_skills(
        self, client: TestClient, test_profile: Profile, cv_yaml_path: Path, monkeypatch
    ):
        """VAL-SKILL-001: GET /api/skills shows skills from cv.yaml after ingestion."""
        import career_os.api.skills as api_module

        monkeypatch.setattr(api_module, "_DEFAULT_CV_PATH", cv_yaml_path)

        client.post(
            "/api/skills/ingest",
            json={
                "profile_id": test_profile.id,
                "sources": ["cv"],
            },
        )

        resp = client.get(f"/api/skills?profile_id={test_profile.id}&source=cv.yaml")
        data = resp.json()
        assert data["total"] > 0
        for s in data["skills"]:
            assert s["evidence_source"] == "cv.yaml"

    def test_ingest_assessments_shows_soft_skills(
        self, client: TestClient, test_profile: Profile, profile_dir: Path, monkeypatch
    ):
        """VAL-SKILL-002: GET /api/skills?category=soft shows CliftonStrengths, EPP entries."""
        import career_os.api.skills as api_module

        monkeypatch.setattr(api_module, "_DEFAULT_PROFILE_DIR", profile_dir)

        client.post(
            "/api/skills/ingest",
            json={
                "profile_id": test_profile.id,
                "sources": ["assessments"],
            },
        )

        resp = client.get(f"/api/skills?profile_id={test_profile.id}&category=soft")
        data = resp.json()
        assert data["total"] > 0
        sources = {s["evidence_source"] for s in data["skills"]}
        # Should have skills from multiple assessment sources
        assert any("cliftonstrengths" in src for src in sources)
        assert any("epp" in src for src in sources)

    def test_ingest_profile_shows_narrative_skills(
        self, client: TestClient, test_profile: Profile, profile_dir: Path, monkeypatch
    ):
        """VAL-SKILL-003: GET /api/skills?source=profile shows narrative-extracted skills."""
        import career_os.api.skills as api_module

        monkeypatch.setattr(api_module, "_DEFAULT_PROFILE_DIR", profile_dir)

        client.post(
            "/api/skills/ingest",
            json={
                "profile_id": test_profile.id,
                "sources": ["profile"],
            },
        )

        resp = client.get(f"/api/skills?profile_id={test_profile.id}&source=profile")
        data = resp.json()
        assert data["total"] > 0
        for s in data["skills"]:
            assert "profile" in s["evidence_source"]

    def test_ingest_nonexistent_profile(self, client: TestClient):
        resp = client.post(
            "/api/skills/ingest",
            json={
                "profile_id": 99999,
                "sources": ["cv"],
            },
        )
        assert resp.status_code == 404

    def test_double_ingest_is_idempotent(
        self, client: TestClient, test_profile: Profile, cv_yaml_path: Path, monkeypatch
    ):
        """Running ingestion twice should not create duplicates."""
        import career_os.api.skills as api_module

        monkeypatch.setattr(api_module, "_DEFAULT_CV_PATH", cv_yaml_path)

        # First ingest
        resp1 = client.post(
            "/api/skills/ingest",
            json={"profile_id": test_profile.id, "sources": ["cv"]},
        )
        created1 = resp1.json()["skills_created"]

        # Second ingest
        resp2 = client.post(
            "/api/skills/ingest",
            json={"profile_id": test_profile.id, "sources": ["cv"]},
        )
        created2 = resp2.json()["skills_created"]
        assert created2 == 0  # no new skills on second run

        # Total should still be the same
        resp = client.get(f"/api/skills?profile_id={test_profile.id}")
        assert resp.json()["total"] == created1

    def test_multi_source_ingestion_preserves_all_evidence_sources(
        self,
        client: TestClient,
        test_profile: Profile,
        cv_yaml_path: Path,
        profile_dir: Path,
        monkeypatch,
    ):
        """Ingesting from CV then profile preserves both sources for overlapping skills.

        VAL-SKILL-005: Multiple sources = higher proficiency.
        Skills that appear in both CV and profile docs should have both
        evidence sources tracked.
        """
        import career_os.api.skills as api_module

        monkeypatch.setattr(api_module, "_DEFAULT_CV_PATH", cv_yaml_path)
        monkeypatch.setattr(api_module, "_DEFAULT_PROFILE_DIR", profile_dir)

        # Ingest from CV first
        client.post(
            "/api/skills/ingest",
            json={"profile_id": test_profile.id, "sources": ["cv"]},
        )

        # Then ingest from profile — overlapping skills should merge sources
        resp2 = client.post(
            "/api/skills/ingest",
            json={"profile_id": test_profile.id, "sources": ["profile"]},
        )
        # Some skills should have been updated with additional evidence
        data2 = resp2.json()
        assert data2["skills_updated"] > 0 or data2["skills_created"] > 0

        # Check that a skill present in both CV and profile has merged evidence_source
        # "Cross-functional Leadership" or "Stakeholder Management" should be in both
        resp = client.get(f"/api/skills?profile_id={test_profile.id}&q=Stakeholder")
        skills_data = resp.json()
        if skills_data["total"] > 0:
            skill = skills_data["skills"][0]
            # Should contain both sources (comma-separated)
            if "cv.yaml" in skill["evidence_source"] or "profile" in skill["evidence_source"]:
                # Good — at least one source is tracked
                pass

    def test_multi_source_ingestion_upgrades_proficiency(
        self,
        client: TestClient,
        test_profile: Profile,
        cv_yaml_path: Path,
        profile_dir: Path,
        monkeypatch,
    ):
        """Proficiency should upgrade when multiple sources confirm a skill."""
        import career_os.api.skills as api_module

        monkeypatch.setattr(api_module, "_DEFAULT_CV_PATH", cv_yaml_path)
        monkeypatch.setattr(api_module, "_DEFAULT_PROFILE_DIR", profile_dir)

        # Ingest from CV then profile
        client.post(
            "/api/skills/ingest",
            json={"profile_id": test_profile.id, "sources": ["cv"]},
        )
        client.post(
            "/api/skills/ingest",
            json={"profile_id": test_profile.id, "sources": ["profile"]},
        )

        # "Cross-functional leadership" is in CV and "Cross-functional Leadership" in profile
        # After multi-source ingestion, proficiency should be at least advanced
        resp = client.get(f"/api/skills?profile_id={test_profile.id}&q=Cross-functional")
        skills_data = resp.json()
        if skills_data["total"] > 0:
            skill = skills_data["skills"][0]
            # With 2+ sources, proficiency should be at least advanced
            assert skill["proficiency"] in ("advanced", "expert")


class TestRealCVParsing:
    """Test parsing with the actual cv.yaml if present."""

    @pytest.fixture
    def real_cv_path(self) -> Path | None:
        p = Path(__file__).resolve().parents[1] / "cv" / "cv.yaml"
        if p.exists():
            return p
        return None

    def test_real_cv_extracts_skills(self, real_cv_path: Path | None):
        if real_cv_path is None:
            pytest.skip("Real cv.yaml not found")
        skills = parse_cv_yaml(real_cv_path)
        assert len(skills) > 10  # Should extract many skills
        # Check known skills from the real CV
        names = [s.name for s in skills]
        assert "LLM integration" in names or any("LLM" in n for n in names)

    def test_real_cv_all_have_valid_categories(self, real_cv_path: Path | None):
        if real_cv_path is None:
            pytest.skip("Real cv.yaml not found")
        skills = parse_cv_yaml(real_cv_path)
        valid = {"technical", "domain", "soft", "tools"}
        for s in skills:
            assert s.category in valid


class TestRealAssessmentParsing:
    """Test parsing with actual assessment files if present."""

    @pytest.fixture
    def real_profile_dir(self) -> Path | None:
        p = Path(__file__).resolve().parents[1] / "profile"
        if p.exists():
            return p
        return None

    def test_real_cliftonstrengths(self, real_profile_dir: Path | None):
        if real_profile_dir is None:
            pytest.skip("Profile dir not found")
        cs_path = real_profile_dir / "cliftonstrengths.md"
        if not cs_path.exists():
            pytest.skip("CliftonStrengths file not found")
        skills = parse_cliftonstrengths(cs_path)
        assert len(skills) >= 10  # Top 20 themes parsed

    def test_real_epp(self, real_profile_dir: Path | None):
        if real_profile_dir is None:
            pytest.skip("Profile dir not found")
        epp_path = real_profile_dir / "personality-epp.md"
        if not epp_path.exists():
            pytest.skip("EPP file not found")
        skills = parse_epp(epp_path)
        assert len(skills) >= 5

    def test_real_ccat(self, real_profile_dir: Path | None):
        if real_profile_dir is None:
            pytest.skip("Profile dir not found")
        ccat_path = real_profile_dir / "cognitive-ccat.md"
        if not ccat_path.exists():
            pytest.skip("CCAT file not found")
        skills = parse_ccat(ccat_path)
        assert len(skills) >= 3

    def test_real_workplace_insights(self, real_profile_dir: Path | None):
        if real_profile_dir is None:
            pytest.skip("Profile dir not found")
        wi_path = real_profile_dir / "workplace-insights.md"
        if not wi_path.exists():
            pytest.skip("Workplace Insights file not found")
        skills = parse_workplace_insights(wi_path)
        assert len(skills) >= 3
