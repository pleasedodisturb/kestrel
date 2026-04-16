"""Tests for the Scoring Rubric & Few-Shot Calibration (G-269, Epic 1).

Covers:
- SCORING_RUBRIC constant with band definitions and calibration examples
- RUBRIC_VERSION tracked in weights_snapshot
- Job-family-aware modifiers generated from JOB_FAMILY_WEIGHTS
- Rubric integration into _build_scoring_prompt()
- Token budget enforcement (<600 tokens / ~450 words)
- End-to-end scoring with rubric produces valid ScoreResult
- Golden set fixture structure validation
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from career_os.database import Base
from career_os.models.models import Profile
from career_os.schemas.ai import (
    AIFeature,
    AIResponse,
    ATSKeyword,
    DimensionalScores,
    ScoreBreakdownFactor,
    ScoreResult,
)
from career_os.services.scoring import (
    JOB_FAMILY_WEIGHTS,
    RUBRIC_VERSION,
    SCORING_RUBRIC,
    _build_job_family_modifiers,
    _build_scoring_prompt,
    score_job,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def db_session():
    """Create a fresh in-memory database for rubric tests."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)

    connection = engine.connect()
    test_session_cls = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = test_session_cls()

    profile = Profile(
        id=1,
        name="Test User",
        email="test@example.com",
        location="Frankfurt",
        job_family="TPM",
    )
    session.add(profile)
    session.commit()

    yield session
    session.close()
    connection.close()
    engine.dispose()


def _sample_profile_data(job_family: str = "TPM") -> dict:
    """Return a minimal profile_data dict for prompt building."""
    return {
        "name": "Test User",
        "location": "Frankfurt",
        "job_family": job_family,
        "skills": [
            {"name": "Python", "category": "programming", "proficiency": "advanced"},
            {"name": "Program Management", "category": "management", "proficiency": "expert"},
        ],
        "goals": [{"title": "Land AI TPM role", "type": "career", "description": ""}],
        "market_positioning": {},
        "weights": {
            "skills_match": 0.20,
            "career_alignment": 0.25,
            "culture_fit": 0.15,
            "salary_match": 0.15,
            "location_match": 0.10,
            "growth_potential": 0.10,
            "remote_preference": 0.05,
        },
    }


# ---------------------------------------------------------------------------
# Rubric constant tests
# ---------------------------------------------------------------------------


class TestScoringRubric:
    """Tests for the SCORING_RUBRIC constant."""

    def test_rubric_contains_band_definitions(self):
        """All five score bands must be defined in the rubric."""
        assert "9-10" in SCORING_RUBRIC
        assert "7-8" in SCORING_RUBRIC
        assert "5-6" in SCORING_RUBRIC
        assert "3-4" in SCORING_RUBRIC
        assert "1-2" in SCORING_RUBRIC

    def test_rubric_contains_calibration_examples(self):
        """Rubric must contain exactly 4 calibration examples."""
        assert "Example 1" in SCORING_RUBRIC
        assert "Example 2" in SCORING_RUBRIC
        assert "Example 3" in SCORING_RUBRIC
        assert "Example 4" in SCORING_RUBRIC

    def test_calibration_examples_cover_score_range(self):
        """Examples should have scores in bands [1-3], [4-6], [7-9]."""
        # Each example ends with "Score: X.X" — deduplicate since the score
        # value may appear in both the reasoning line and the summary.
        scores = sorted(set(float(m) for m in re.findall(r"Score:\s+(\d+\.?\d*)", SCORING_RUBRIC)))
        assert len(scores) == 4, f"Expected 4 unique example scores, found {scores}"

        # One in low band, one in mid band, one in high band
        assert any(1.0 <= s <= 3.0 for s in scores), f"No low-band score in {scores}"
        assert any(4.0 <= s <= 6.0 for s in scores), f"No mid-band score in {scores}"
        assert any(7.0 <= s <= 9.0 for s in scores), f"No high-band score in {scores}"

    def test_rubric_token_count_budget(self):
        """Rubric section should be <600 tokens (rough word count proxy: <450 words)."""
        word_count = len(SCORING_RUBRIC.split())
        assert word_count < 450, (
            f"SCORING_RUBRIC is {word_count} words, exceeds 450-word budget (~600 token proxy)"
        )

    def test_rubric_version_is_string(self):
        """RUBRIC_VERSION must be a non-empty string."""
        assert isinstance(RUBRIC_VERSION, str)
        assert len(RUBRIC_VERSION) > 0
        assert RUBRIC_VERSION == "v1.1"

    def test_rubric_contains_top_5_percent_language(self):
        """v1.1 dream-fit band must reference top-5% threshold."""
        assert "top-5%" in SCORING_RUBRIC

    def test_rubric_contains_example_4(self):
        """v1.1 must include a 4th calibration example."""
        assert "Example 4" in SCORING_RUBRIC

    def test_rubric_contains_score_7_5(self):
        """v1.1 Example 4 must use Score: 7.5."""
        assert "Score: 7.5" in SCORING_RUBRIC


# ---------------------------------------------------------------------------
# Rubric in prompt tests
# ---------------------------------------------------------------------------


class TestRubricInPrompt:
    """Verify _build_scoring_prompt includes the rubric."""

    def test_rubric_included_in_prompt(self):
        """Verify _build_scoring_prompt includes SCORING_RUBRIC text."""
        prompt = _build_scoring_prompt(
            job_description="Build AI products.",
            job_title="AI TPM",
            profile_data=_sample_profile_data(),
        )
        assert "Scoring Rubric" in prompt
        assert "9-10" in prompt
        assert "Example 1" in prompt

    def test_prompt_contains_weights_after_rubric(self):
        """Scoring weights should appear after the rubric section."""
        prompt = _build_scoring_prompt(
            job_description="Build AI products.",
            profile_data=_sample_profile_data(),
        )
        rubric_pos = prompt.index("Scoring Rubric")
        weights_pos = prompt.index("Scoring Weights")
        assert weights_pos > rubric_pos, "Weights should come after rubric in prompt"

    def test_prompt_includes_job_family_modifiers_for_swe(self):
        """SWE family should produce weight modifiers in the prompt."""
        prompt = _build_scoring_prompt(
            job_description="Build backend services.",
            profile_data=_sample_profile_data(job_family="SWE"),
        )
        assert "Job-Family Weight Modifiers" in prompt
        assert "SWE" in prompt

    def test_prompt_no_modifiers_for_unknown_family(self):
        """Unknown job family should not produce modifiers (uses DEFAULT_WEIGHTS)."""
        prompt = _build_scoring_prompt(
            job_description="Do things.",
            profile_data=_sample_profile_data(job_family="UnknownFamily"),
        )
        assert "Job-Family Weight Modifiers" not in prompt


# ---------------------------------------------------------------------------
# Job-family modifier tests
# ---------------------------------------------------------------------------


class TestJobFamilyModifiers:
    """For each family in JOB_FAMILY_WEIGHTS, verify a modifier string is produced."""

    def test_job_family_modifiers_generated_for_divergent_families(self):
        """Families with weight diffs >= 0.05 from defaults should produce modifiers.

        Some families (e.g. TPM) have very small diffs that don't clear the
        threshold — that's by design. We check that at least SWE and DevRel
        (which have large diffs) produce modifiers.
        """
        families_with_modifiers = [
            fam for fam in JOB_FAMILY_WEIGHTS if len(_build_job_family_modifiers(fam)) > 0
        ]
        assert len(families_with_modifiers) >= 2, (
            f"Expected at least 2 families with modifiers, got {families_with_modifiers}"
        )
        assert "SWE" in families_with_modifiers
        assert "DevRel" in families_with_modifiers

    def test_swe_highlights_skills_match(self):
        """SWE has skills_match=0.35 vs default 0.25 — should be flagged."""
        modifiers = _build_job_family_modifiers("SWE")
        assert "skills match" in modifiers.lower()
        assert "higher" in modifiers.lower()

    def test_devrel_highlights_culture_fit(self):
        """DevRel has culture_fit=0.25 vs default 0.15 — should be flagged."""
        modifiers = _build_job_family_modifiers("DevRel")
        assert "culture fit" in modifiers.lower()
        assert "higher" in modifiers.lower()

    def test_none_family_returns_empty(self):
        """None job family should return empty string."""
        assert _build_job_family_modifiers(None) == ""

    def test_default_weights_family_returns_empty(self):
        """A family whose weights exactly match DEFAULT_WEIGHTS returns empty."""
        # Construct a family that matches defaults — should return ""
        assert _build_job_family_modifiers("NonExistentFamily") == ""


# ---------------------------------------------------------------------------
# Rubric version in weights_snapshot tests
# ---------------------------------------------------------------------------


class TestRubricVersionInSnapshot:
    """Verify rubric_version appears in the weights_snapshot JSON."""

    @pytest.mark.asyncio
    async def test_rubric_version_in_weights_snapshot(self, db_session):
        """score_job should store rubric_version in weights_snapshot."""
        mock_score_result = ScoreResult(
            fit_score=7.5,
            reasoning="Good match for TPM role with AI focus. " * 5,
            estimated_salary="120-150k EUR",
            effort_flag="medium",
            prep_level="moderate",
            prep_notes="Review ML infrastructure patterns",
            readiness_score=72.0,
            career_alignment=7.0,
            score_breakdown=[
                ScoreBreakdownFactor(
                    factor="Technical skills", contribution=2.0, description="Strong Python"
                ),
                ScoreBreakdownFactor(
                    factor="Role alignment", contribution=1.5, description="Direct TPM match"
                ),
                ScoreBreakdownFactor(
                    factor="Domain fit", contribution=1.0, description="AI platform experience"
                ),
            ],
            dimensional_scores=DimensionalScores(
                technical_fit=7.0,
                seniority_alignment=8.0,
                compensation_fit=7.5,
                location_fit=9.0,
                career_trajectory=7.0,
                company_fit=6.5,
            ),
            ats_keywords=[
                ATSKeyword(keyword="Python", category="technical", matched=True),
                ATSKeyword(keyword="TPM", category="domain", matched=True),
                ATSKeyword(keyword="ML infrastructure", category="technical", matched=True),
            ],
        )

        mock_response = AIResponse(
            content="mocked",
            provider="mock",
            feature=AIFeature.score,
            structured=mock_score_result,
        )

        with patch("career_os.services.scoring.get_ai_provider") as mock_provider:
            provider_instance = AsyncMock()
            provider_instance.score.return_value = mock_response
            mock_provider.return_value = provider_instance

            scored = await score_job(
                db_session,
                profile_id=1,
                job_description="Technical Program Manager for AI platform team.",
                job_title="TPM, AI Platform",
                job_company="TestCorp",
            )

        snapshot = json.loads(scored.weights_snapshot)
        assert "rubric_version" in snapshot
        assert snapshot["rubric_version"] == RUBRIC_VERSION


# ---------------------------------------------------------------------------
# End-to-end integration test
# ---------------------------------------------------------------------------


class TestScoringWithRubricIntegration:
    """End-to-end: score_job with rubric returns a valid ScoreResult."""

    @pytest.mark.asyncio
    async def test_scoring_with_rubric_produces_valid_result(self, db_session):
        """Full pipeline: score_job produces a persisted ScoredJob with valid data."""
        mock_score_result = ScoreResult(
            fit_score=6.0,
            reasoning="Moderate fit — some skill overlap but domain mismatch. " * 4,
            estimated_salary="100-130k EUR",
            effort_flag="high",
            prep_level="significant",
            prep_notes="Need to learn cloud migration patterns",
            readiness_score=55.0,
            career_alignment=5.5,
            score_breakdown=[
                ScoreBreakdownFactor(
                    factor="Technical skills", contribution=1.0, description="Python transfers"
                ),
                ScoreBreakdownFactor(
                    factor="Domain", contribution=-1.5, description="No cloud migration exp"
                ),
                ScoreBreakdownFactor(
                    factor="Seniority", contribution=0.5, description="Appropriate level"
                ),
            ],
            dimensional_scores=DimensionalScores(
                technical_fit=5.0,
                seniority_alignment=7.0,
                compensation_fit=6.0,
                location_fit=8.0,
                career_trajectory=5.0,
                company_fit=4.0,
            ),
            ats_keywords=[
                ATSKeyword(keyword="Cloud migration", category="domain", matched=False),
                ATSKeyword(keyword="Python", category="technical", matched=True),
                ATSKeyword(keyword="PMP", category="certification", matched=False),
            ],
        )

        mock_response = AIResponse(
            content="mocked",
            provider="mock",
            feature=AIFeature.score,
            structured=mock_score_result,
        )

        with patch("career_os.services.scoring.get_ai_provider") as mock_provider:
            provider_instance = AsyncMock()
            provider_instance.score.return_value = mock_response
            mock_provider.return_value = provider_instance

            scored = await score_job(
                db_session,
                profile_id=1,
                job_description="Lead cloud migration projects for enterprise clients.",
                job_title="Project Manager, Cloud Migration",
                job_company="T-Systems",
            )

        # Validate the scored job
        assert scored.fit_score == 6.0
        assert scored.readiness_score == 55.0
        assert scored.career_alignment == 5.5
        assert scored.reasoning is not None
        assert len(scored.reasoning) >= 100
        assert scored.is_stale is False

        # Validate weights_snapshot includes rubric_version
        snapshot = json.loads(scored.weights_snapshot)
        assert snapshot["rubric_version"] == RUBRIC_VERSION

        # Validate the prompt passed to the provider included the rubric
        call_args = provider_instance.score.call_args
        prompt_passed = call_args.kwargs.get(
            "job_description", call_args.args[0] if call_args.args else ""
        )
        assert "Scoring Rubric" in prompt_passed


# ---------------------------------------------------------------------------
# Golden set fixture tests
# ---------------------------------------------------------------------------


class TestGoldenSetFixture:
    """Validate the golden set fixture structure."""

    @pytest.fixture()
    def golden_set(self):
        path = FIXTURES_DIR / "scoring_golden_set.json"
        assert path.exists(), f"Golden set fixture not found at {path}"
        with open(path) as f:
            return json.load(f)

    def test_golden_set_has_20_jobs(self, golden_set):
        """Golden set should have exactly 20 jobs."""
        assert len(golden_set) == 20

    def test_golden_set_covers_all_categories(self, golden_set):
        """Golden set should have jobs in reject, mediocre, strong, dream categories."""
        categories = {job["category"] for job in golden_set}
        assert categories == {"reject", "mediocre", "strong", "dream"}

    def test_golden_set_category_distribution(self, golden_set):
        """Distribution: 4 reject, 6 mediocre, 6 strong, 4 dream."""
        from collections import Counter

        counts = Counter(job["category"] for job in golden_set)
        assert counts["reject"] == 4
        assert counts["mediocre"] == 6
        assert counts["strong"] == 6
        assert counts["dream"] == 4

    def test_golden_set_has_required_fields(self, golden_set):
        """Every job must have id, category, expected_band, title, company, description."""
        required = {"id", "category", "expected_band", "title", "company", "description"}
        for job in golden_set:
            missing = required - set(job.keys())
            assert not missing, f"Job {job.get('id', '?')} missing fields: {missing}"

    def test_golden_set_expected_bands_valid(self, golden_set):
        """expected_band must be a 2-element list with values 1-10."""
        for job in golden_set:
            band = job["expected_band"]
            assert isinstance(band, list) and len(band) == 2
            assert 1 <= band[0] <= 10
            assert 1 <= band[1] <= 10
            assert band[0] <= band[1]

    def test_golden_set_unique_ids(self, golden_set):
        """All job IDs must be unique."""
        ids = [job["id"] for job in golden_set]
        assert len(ids) == len(set(ids))
