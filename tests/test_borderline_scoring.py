"""Tests for Borderline 2-Pass Scoring (Epic 5 / G-273).

Covers:
- Borderline detection: scores in [4.0, 6.5] trigger a second AI call
- Non-borderline scores use a single pass
- _average_score_results() numeric precision and qualitative field selection
- Graceful fallback when second pass fails
- scoring_passes column tracking on ScoredJob
- BORDERLINE_SCORING_ENABLED=false disables 2-pass entirely
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base
from career_os.models.models import Profile
from career_os.schemas.ai import ATSKeyword, DimensionalScores, ScoreBreakdownFactor, ScoreResult
from career_os.services.scoring import _average_score_results, score_job

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_score_result(
    fit_score: float,
    readiness_score: float = 70.0,
    career_alignment: float = 7.0,
    reasoning: str = "Test reasoning",
    ats_keywords: list[ATSKeyword] | None = None,
    desire_score: float | None = None,
) -> ScoreResult:
    """Build a minimal valid ScoreResult for testing."""
    return ScoreResult(
        fit_score=fit_score,
        readiness_score=readiness_score,
        career_alignment=career_alignment,
        reasoning=reasoning,
        estimated_salary="$100k-$120k",
        effort_flag="medium",
        prep_level="moderate",
        prep_notes="Prep note",
        score_breakdown=[
            ScoreBreakdownFactor(factor="skills_match", contribution=2.0, description="Good match"),
            ScoreBreakdownFactor(
                factor="career_alignment", contribution=1.5, description="Aligned"
            ),
            ScoreBreakdownFactor(factor="culture_fit", contribution=1.0, description="Culture ok"),
        ],
        dimensional_scores=DimensionalScores(
            technical_fit=fit_score,
            seniority_alignment=fit_score,
            compensation_fit=fit_score,
            location_fit=fit_score,
            career_trajectory=fit_score,
            company_fit=fit_score,
        ),
        ats_keywords=ats_keywords
        or [
            ATSKeyword(keyword="Python", category="technical", matched=True),
            ATSKeyword(keyword="FastAPI", category="tool", matched=True),
        ],
        desire_score=desire_score,
        desire_reasoning="Desirable role" if desire_score is not None else None,
    )


def _make_ai_response(score_result: ScoreResult) -> MagicMock:
    """Wrap a ScoreResult in a mock AIResponse."""
    resp = MagicMock()
    resp.structured = score_result
    return resp


# ---------------------------------------------------------------------------
# Database fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session() -> Session:
    """Fresh in-memory SQLite session for each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk_pragma(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    connection = engine.connect()
    session_cls = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = session_cls()

    profile = Profile(
        id=1,
        name="Test User",
        email="test@example.com",
        location="Berlin",
        job_family="TPM",
    )
    session.add(profile)
    session.commit()

    yield session
    session.close()
    connection.close()
    engine.dispose()


# ---------------------------------------------------------------------------
# Unit tests for _average_score_results()
# ---------------------------------------------------------------------------


class TestAverageScoreResults:
    def test_numeric_averaging(self):
        """Averaging two ScoreResults produces correct numeric means."""
        a = _make_score_result(fit_score=4.0, readiness_score=60.0, career_alignment=6.0)
        b = _make_score_result(fit_score=6.0, readiness_score=80.0, career_alignment=8.0)

        result = _average_score_results(a, b)

        assert result.fit_score == 5.0
        assert result.readiness_score == 70.0
        assert result.career_alignment == 7.0

    def test_preserves_better_reasoning(self):
        """The result with the higher fit_score contributes the reasoning."""
        a = _make_score_result(fit_score=5.0, reasoning="Low reasoning")
        b = _make_score_result(fit_score=6.5, reasoning="High reasoning")

        result = _average_score_results(a, b)

        assert result.reasoning == "High reasoning"

    def test_preserves_better_reasoning_when_a_wins(self):
        """When a has higher fit_score, a's reasoning is used."""
        a = _make_score_result(fit_score=6.5, reasoning="A reasoning")
        b = _make_score_result(fit_score=5.0, reasoning="B reasoning")

        result = _average_score_results(a, b)

        assert result.reasoning == "A reasoning"

    def test_dimensional_scores_averaged(self):
        """Dimensional scores are averaged element-wise."""
        a = _make_score_result(fit_score=4.0)
        b = _make_score_result(fit_score=6.0)

        result = _average_score_results(a, b)

        assert result.dimensional_scores is not None
        assert result.dimensional_scores.technical_fit == 5.0
        assert result.dimensional_scores.career_trajectory == 5.0

    def test_dimensional_scores_fallback_when_one_missing(self):
        """When only one result has dimensional scores, primary's dims are kept."""
        a = _make_score_result(fit_score=6.5)
        b = _make_score_result(fit_score=5.0)
        b = b.model_copy(update={"dimensional_scores": None})

        result = _average_score_results(a, b)

        # a has higher score so it's primary — its dimensional_scores survive
        assert result.dimensional_scores is not None
        assert result.dimensional_scores.technical_fit == 6.5

    def test_score_breakdown_factors_deduplicated_and_averaged(self):
        """score_breakdown factors with the same name are merged with averaged contributions."""
        a = _make_score_result(fit_score=5.0)
        b = _make_score_result(fit_score=6.0)
        # Both have the same 3 factors from _make_score_result

        result = _average_score_results(a, b)

        factor_names = [f.factor for f in result.score_breakdown]
        # No duplicates
        assert len(factor_names) == len(set(factor_names))
        # skills_match contribution should be averaged: (2.0 + 2.0) / 2 = 2.0
        skills_factor = next(f for f in result.score_breakdown if f.factor == "skills_match")
        assert skills_factor.contribution == 2.0

    def test_ats_keywords_keep_longer_list(self):
        """ATS keywords come from whichever result has more keywords."""
        short_kws = [ATSKeyword(keyword="Python", category="technical", matched=True)]
        long_kws = [
            ATSKeyword(keyword="Python", category="technical", matched=True),
            ATSKeyword(keyword="FastAPI", category="tool", matched=True),
            ATSKeyword(keyword="Docker", category="tool", matched=False),
        ]
        a = _make_score_result(fit_score=5.0, ats_keywords=short_kws)
        b = _make_score_result(fit_score=6.0, ats_keywords=long_kws)

        result = _average_score_results(a, b)

        assert len(result.ats_keywords) == 3

    def test_desire_score_averaged_when_both_present(self):
        """desire_score is averaged when both results have it."""
        a = _make_score_result(fit_score=4.5, desire_score=4.0)
        b = _make_score_result(fit_score=6.0, desire_score=6.0)

        result = _average_score_results(a, b)

        assert result.desire_score == 5.0

    def test_desire_score_falls_back_to_primary_when_one_missing(self):
        """desire_score falls back to primary's value when one is None."""
        a = _make_score_result(fit_score=6.5, desire_score=7.0)
        b = _make_score_result(fit_score=5.0, desire_score=None)

        result = _average_score_results(a, b)

        assert result.desire_score == 7.0

    def test_fit_score_rounded_to_two_decimals(self):
        """fit_score is rounded to 2 decimal places after averaging."""
        a = _make_score_result(fit_score=4.1)
        b = _make_score_result(fit_score=6.2)

        result = _average_score_results(a, b)

        # 4.1 + 6.2 = 10.3 / 2 = 5.15
        assert result.fit_score == 5.15


# ---------------------------------------------------------------------------
# Integration tests for score_job() borderline detection
# ---------------------------------------------------------------------------


class TestBorderlineScoring:
    @pytest.mark.asyncio
    async def test_borderline_triggers_second_pass(self, db_session: Session):
        """Score in [4.0, 6.5] triggers a second scoring call."""
        borderline_result = _make_score_result(fit_score=5.0)
        mock_response = _make_ai_response(borderline_result)

        mock_provider = AsyncMock()
        mock_provider.score.return_value = mock_response

        with (
            patch("career_os.services.scoring.get_ai_provider", return_value=mock_provider),
            patch("career_os.services.scoring.settings") as mock_settings,
        ):
            mock_settings.feedback_calibration_enabled = False
            mock_settings.borderline_scoring_enabled = True
            mock_settings.borderline_low_threshold = 4.0
            mock_settings.borderline_high_threshold = 6.5

            await score_job(
                db_session,
                profile_id=1,
                job_description="Senior TPM role at Datadog",
                job_title="Senior TPM",
                job_company="Datadog",
            )

        # Should have been called twice (first pass + second pass)
        assert mock_provider.score.call_count == 2

    @pytest.mark.asyncio
    async def test_non_borderline_single_pass_high(self, db_session: Session):
        """Score above borderline zone (>6.5) → only 1 scoring call."""
        high_result = _make_score_result(fit_score=8.0)
        mock_response = _make_ai_response(high_result)

        mock_provider = AsyncMock()
        mock_provider.score.return_value = mock_response

        with (
            patch("career_os.services.scoring.get_ai_provider", return_value=mock_provider),
            patch("career_os.services.scoring.settings") as mock_settings,
        ):
            mock_settings.feedback_calibration_enabled = False
            mock_settings.borderline_scoring_enabled = True
            mock_settings.borderline_low_threshold = 4.0
            mock_settings.borderline_high_threshold = 6.5

            await score_job(
                db_session,
                profile_id=1,
                job_description="Dream TPM role",
                job_title="Principal TPM",
                job_company="Anthropic",
            )

        assert mock_provider.score.call_count == 1

    @pytest.mark.asyncio
    async def test_non_borderline_single_pass_low(self, db_session: Session):
        """Score below borderline zone (<4.0) → only 1 scoring call."""
        low_result = _make_score_result(fit_score=2.0)
        mock_response = _make_ai_response(low_result)

        mock_provider = AsyncMock()
        mock_provider.score.return_value = mock_response

        with (
            patch("career_os.services.scoring.get_ai_provider", return_value=mock_provider),
            patch("career_os.services.scoring.settings") as mock_settings,
        ):
            mock_settings.feedback_calibration_enabled = False
            mock_settings.borderline_scoring_enabled = True
            mock_settings.borderline_low_threshold = 4.0
            mock_settings.borderline_high_threshold = 6.5

            await score_job(
                db_session,
                profile_id=1,
                job_description="Unrelated .NET developer role",
                job_title=".NET Developer",
                job_company="SAP",
            )

        assert mock_provider.score.call_count == 1

    @pytest.mark.asyncio
    async def test_scoring_passes_tracked_two(self, db_session: Session):
        """ScoredJob.scoring_passes is 2 when borderline triggers second pass."""
        borderline_result = _make_score_result(fit_score=5.0)
        mock_response = _make_ai_response(borderline_result)

        mock_provider = AsyncMock()
        mock_provider.score.return_value = mock_response

        with (
            patch("career_os.services.scoring.get_ai_provider", return_value=mock_provider),
            patch("career_os.services.scoring.settings") as mock_settings,
        ):
            mock_settings.feedback_calibration_enabled = False
            mock_settings.borderline_scoring_enabled = True
            mock_settings.borderline_low_threshold = 4.0
            mock_settings.borderline_high_threshold = 6.5

            scored_job = await score_job(
                db_session,
                profile_id=1,
                job_description="TPM role at Datadog",
                job_title="TPM",
                job_company="Datadog",
            )

        assert scored_job.scoring_passes == 2

    @pytest.mark.asyncio
    async def test_scoring_passes_tracked_one(self, db_session: Session):
        """ScoredJob.scoring_passes is 1 for non-borderline scores."""
        high_result = _make_score_result(fit_score=9.0)
        mock_response = _make_ai_response(high_result)

        mock_provider = AsyncMock()
        mock_provider.score.return_value = mock_response

        with (
            patch("career_os.services.scoring.get_ai_provider", return_value=mock_provider),
            patch("career_os.services.scoring.settings") as mock_settings,
        ):
            mock_settings.feedback_calibration_enabled = False
            mock_settings.borderline_scoring_enabled = True
            mock_settings.borderline_low_threshold = 4.0
            mock_settings.borderline_high_threshold = 6.5

            scored_job = await score_job(
                db_session,
                profile_id=1,
                job_description="Dream TPM role",
                job_title="Head of TPM",
                job_company="Anthropic",
            )

        assert scored_job.scoring_passes == 1

    @pytest.mark.asyncio
    async def test_second_pass_failure_fallback(self, db_session: Session):
        """If second pass raises, original score is used and scoring_passes stays 1."""
        borderline_result = _make_score_result(fit_score=5.5)
        first_response = _make_ai_response(borderline_result)

        mock_provider = AsyncMock()
        # First call succeeds, second raises
        mock_provider.score.side_effect = [first_response, RuntimeError("Provider timeout")]

        with (
            patch("career_os.services.scoring.get_ai_provider", return_value=mock_provider),
            patch("career_os.services.scoring.settings") as mock_settings,
        ):
            mock_settings.feedback_calibration_enabled = False
            mock_settings.borderline_scoring_enabled = True
            mock_settings.borderline_low_threshold = 4.0
            mock_settings.borderline_high_threshold = 6.5

            # Should NOT raise — fallback to single score
            scored_job = await score_job(
                db_session,
                profile_id=1,
                job_description="Borderline TPM role",
                job_title="TPM",
                job_company="T-Systems",
            )

        assert scored_job.scoring_passes == 1
        assert scored_job.fit_score == 5.5

    @pytest.mark.asyncio
    async def test_borderline_disabled_via_config(self, db_session: Session):
        """When BORDERLINE_SCORING_ENABLED=false, always single pass regardless of score."""
        borderline_result = _make_score_result(fit_score=5.0)
        mock_response = _make_ai_response(borderline_result)

        mock_provider = AsyncMock()
        mock_provider.score.return_value = mock_response

        with (
            patch("career_os.services.scoring.get_ai_provider", return_value=mock_provider),
            patch("career_os.services.scoring.settings") as mock_settings,
        ):
            mock_settings.feedback_calibration_enabled = False
            mock_settings.borderline_scoring_enabled = False  # disabled
            mock_settings.borderline_low_threshold = 4.0
            mock_settings.borderline_high_threshold = 6.5

            scored_job = await score_job(
                db_session,
                profile_id=1,
                job_description="TPM role in borderline zone",
                job_title="TPM",
                job_company="Personio",
            )

        assert mock_provider.score.call_count == 1
        assert scored_job.scoring_passes == 1

    @pytest.mark.asyncio
    async def test_boundary_values_inclusive(self, db_session: Session):
        """Exactly 4.0 and 6.5 are in the borderline zone (inclusive bounds)."""
        for fit_score in (4.0, 6.5):
            borderline_result = _make_score_result(fit_score=fit_score)
            mock_response = _make_ai_response(borderline_result)

            mock_provider = AsyncMock()
            mock_provider.score.return_value = mock_response

            with (
                patch("career_os.services.scoring.get_ai_provider", return_value=mock_provider),
                patch("career_os.services.scoring.settings") as mock_settings,
            ):
                mock_settings.feedback_calibration_enabled = False
                mock_settings.borderline_scoring_enabled = True
                mock_settings.borderline_low_threshold = 4.0
                mock_settings.borderline_high_threshold = 6.5

                await score_job(
                    db_session,
                    profile_id=1,
                    job_description=f"Role with score {fit_score}",
                    job_title="TPM",
                    job_company="Test Corp",
                )

            assert mock_provider.score.call_count == 2, (
                f"Expected 2 calls for borderline score {fit_score}"
            )

    @pytest.mark.asyncio
    async def test_averaging_log_reports_distinct_passes(self, db_session: Session, caplog):
        """WR-03: the averaging log reports the TRUE pass-1 value and pass-2 value
        distinctly — not pass-2 twice (the pre-fix bug logged the average as pass1)."""
        import logging

        # Distinct pass-1 (5.0) and pass-2 (6.0) → average 5.5.
        pass1 = _make_score_result(fit_score=5.0)
        pass2 = _make_score_result(fit_score=6.0)

        mock_provider = AsyncMock()
        mock_provider.score.side_effect = [_make_ai_response(pass1), _make_ai_response(pass2)]

        with (
            patch("career_os.services.scoring.get_ai_provider", return_value=mock_provider),
            patch("career_os.services.scoring.settings") as mock_settings,
            caplog.at_level(logging.INFO, logger="career_os.services.scoring"),
        ):
            mock_settings.feedback_calibration_enabled = False
            mock_settings.borderline_scoring_enabled = True
            mock_settings.borderline_low_threshold = 4.0
            mock_settings.borderline_high_threshold = 6.5

            await score_job(
                db_session,
                profile_id=1,
                job_description="Borderline TPM role",
                job_title="TPM",
                job_company="Datadog",
            )

        avg_logs = [
            r.getMessage() for r in caplog.records if "Averaged borderline" in r.getMessage()
        ]
        assert len(avg_logs) == 1
        # True pass-1 (5.00) and pass-2 (6.00) are distinct; average is 5.50.
        assert "pass1=5.00 pass2=6.00" in avg_logs[0]
        assert "avg=5.50" in avg_logs[0]

    @pytest.mark.asyncio
    async def test_second_pass_invalid_response_uses_fallback(self, db_session: Session):
        """If second pass returns non-ScoreResult, original score is used."""
        borderline_result = _make_score_result(fit_score=5.0)
        first_response = _make_ai_response(borderline_result)

        # Second response has structured=None (malformed)
        bad_response = MagicMock()
        bad_response.structured = None

        mock_provider = AsyncMock()
        mock_provider.score.side_effect = [first_response, bad_response]

        with (
            patch("career_os.services.scoring.get_ai_provider", return_value=mock_provider),
            patch("career_os.services.scoring.settings") as mock_settings,
        ):
            mock_settings.feedback_calibration_enabled = False
            mock_settings.borderline_scoring_enabled = True
            mock_settings.borderline_low_threshold = 4.0
            mock_settings.borderline_high_threshold = 6.5

            scored_job = await score_job(
                db_session,
                profile_id=1,
                job_description="Borderline role",
                job_title="TPM",
                job_company="Test Corp",
            )

        assert scored_job.scoring_passes == 1
        assert scored_job.fit_score == 5.0
