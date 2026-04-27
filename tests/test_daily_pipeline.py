"""Tests for tools/daily_pipeline.py — all pipeline steps."""

import os
import sys
from unittest.mock import patch

import pytest
from daily_pipeline import (
    PipelineConfig,
    _fallback_score,
    step_dedup_against_tracking,
    step_filter,
    step_generate_digest,
)

# ==================== PipelineConfig ====================


class TestPipelineConfig:
    def test_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            config = PipelineConfig()
        assert config.mode == "api-only"
        assert config.min_score == 5
        assert config.hours_old == 24
        assert config.location == "Berlin"
        assert config.dry_run is False
        assert config.openai_key == ""

    def test_env_overrides(self):
        env = {
            "PIPELINE_MODE": "all",
            "PIPELINE_MIN_SCORE": "7",
            "PIPELINE_HOURS_OLD": "48",
            "PIPELINE_LOCATION": "Munich",
            "PIPELINE_DRY_RUN": "1",
            "OPENAI_API_KEY": "sk-test-key",
        }
        with patch.dict(os.environ, env, clear=True):
            config = PipelineConfig()
        assert config.mode == "all"
        assert config.min_score == 7
        assert config.hours_old == 48
        assert config.location == "Munich"
        assert config.dry_run is True
        assert config.openai_key == "sk-test-key"

    def test_paths_set(self):
        config = PipelineConfig()
        assert "daily-scan-" in config.digest_path.name
        assert "scraped_raw_" in config.raw_path.name
        assert config.csv_path.name == "applications.csv"
        assert config.profile_path.name == "target-roles.md"


# ==================== Fallback scoring ====================


class TestFallbackScore:
    def test_positive_signals_increase_score(self):
        jobs = [
            {
                "title": "AI Product Manager",
                "company": "ML Startup",
                "description": "Build AI platform with innovation",
            },
        ]
        result = _fallback_score(jobs)
        # "ai", "product", "ml", "platform", "startup", "innovation" = 6 positive
        assert result[0]["fit_score"] >= 7

    def test_negative_signals_decrease_score(self):
        jobs = [
            {
                "title": "PMO Coordinator",
                "company": "Admin Corp",
                "description": "PMBOK methodology administrator",
            },
        ]
        result = _fallback_score(jobs)
        # "coordinator" + "pmbok" + "administrator" = 3 negative, no positive
        assert result[0]["fit_score"] <= 3

    def test_neutral_job(self):
        jobs = [
            {"title": "Software Engineer", "company": "Generic", "description": "Write code"},
        ]
        result = _fallback_score(jobs)
        assert result[0]["fit_score"] == 3  # base with no signals (conservative)

    def test_score_capped_at_bounds(self):
        jobs = [
            {
                "title": "AI ML Product Platform Innovation Builder Remote Startup Founding Technical Program",
                "company": "",
                "description": "",
            },
        ]
        result = _fallback_score(jobs)
        assert result[0]["fit_score"] <= 10

        jobs = [
            {
                "title": "PMBOK PMO Coordinator Administrator Sachbearbeiter",
                "company": "",
                "description": "",
            },
        ]
        result = _fallback_score(jobs)
        assert result[0]["fit_score"] >= 1

    def test_adds_all_required_fields(self):
        jobs = [{"title": "Test", "company": "Co", "description": ""}]
        result = _fallback_score(jobs)
        assert "fit_score" in result[0]
        assert "fit_reasoning" in result[0]
        assert "estimated_salary" in result[0]
        assert "effort_flag" in result[0]
        assert "prep_level" in result[0]
        assert "prep_notes" in result[0]


# ==================== Dedup against tracking ====================


def _force_csv_fallback():
    """Hide career_os.database so step_dedup falls back to CSV path."""
    saved = sys.modules.get("career_os.database")
    stub = type(sys)("career_os.database")
    sys.modules["career_os.database"] = stub
    return saved


def _restore_db_module(saved):
    if saved is not None:
        sys.modules["career_os.database"] = saved
    else:
        sys.modules.pop("career_os.database", None)


class TestStepDedupAgainstTracking:
    def test_removes_tracked_jobs(self, tmp_tracking_dir):
        config = PipelineConfig()
        config.csv_path = tmp_tracking_dir / "applications.csv"

        jobs = [
            {"title": "Senior PM", "company": "Existing Co", "fit_score": 8},  # already tracked
            {"title": "New Role", "company": "New Co", "fit_score": 7},  # new
        ]

        # Force CSV fallback so the test CSV fixtures are used instead of real DB
        saved = _force_csv_fallback()
        try:
            result = step_dedup_against_tracking(config, jobs)
        finally:
            _restore_db_module(saved)
        assert len(result) == 1
        assert result[0]["company"] == "New Co"

    def test_case_insensitive_matching(self, tmp_tracking_dir):
        config = PipelineConfig()
        config.csv_path = tmp_tracking_dir / "applications.csv"

        jobs = [
            {"title": "SENIOR PM", "company": "existing co", "fit_score": 8},
        ]

        # Force CSV fallback so the test CSV fixtures are used instead of real DB
        saved = _force_csv_fallback()
        try:
            result = step_dedup_against_tracking(config, jobs)
        finally:
            _restore_db_module(saved)
        assert len(result) == 0  # should match despite case

    def test_no_csv_file(self, tmp_path):
        config = PipelineConfig()
        config.csv_path = tmp_path / "nonexistent.csv"

        jobs = [{"title": "Test", "company": "Co", "fit_score": 5}]
        result = step_dedup_against_tracking(config, jobs)
        assert len(result) == 1  # nothing to dedup against

    def test_empty_csv(self, tmp_path):
        csv_path = tmp_path / "applications.csv"
        csv_path.write_text(
            "date_applied,company,role,url,source,status,salary_range,contact,next_step,notes,fit_score\n"
        )

        config = PipelineConfig()
        config.csv_path = csv_path

        jobs = [{"title": "Test", "company": "Co", "fit_score": 5}]
        result = step_dedup_against_tracking(config, jobs)
        assert len(result) == 1


# ==================== Filter step ====================


class TestStepFilter:
    def test_filters_by_min_score(self, sample_jobs):
        config = PipelineConfig()
        config.min_score = 6

        result = step_filter(config, sample_jobs)
        assert all(j["fit_score"] >= 6 for j in result)
        assert len(result) == 3  # 9, 7, 6 pass; 2 does not

    def test_sorts_descending(self, sample_jobs):
        config = PipelineConfig()
        config.min_score = 1

        result = step_filter(config, sample_jobs)
        scores = [j["fit_score"] for j in result]
        assert scores == sorted(scores, reverse=True)

    def test_high_threshold_filters_most(self, sample_jobs):
        config = PipelineConfig()
        config.min_score = 8

        result = step_filter(config, sample_jobs)
        assert len(result) == 1
        assert result[0]["fit_score"] == 9

    def test_zero_threshold_keeps_all(self, sample_jobs):
        config = PipelineConfig()
        config.min_score = 0

        result = step_filter(config, sample_jobs)
        assert len(result) == len(sample_jobs)

    def test_empty_input(self):
        config = PipelineConfig()
        config.min_score = 5
        assert step_filter(config, []) == []


# ==================== Digest generation ====================


class TestStepGenerateDigest:
    def test_generates_markdown(self, tmp_path, sample_jobs):
        config = PipelineConfig()
        config.tracking_dir = tmp_path
        config.digest_path = tmp_path / "daily-scan-2026-03-11.md"

        digest = step_generate_digest(config, sample_jobs, sample_jobs, sample_jobs[:2])

        assert "# Daily Job Scan" in digest
        assert "## Stats" in digest
        assert "## New Roles Found" in digest
        assert "Mistral AI" in digest
        assert "## Quick adds" in digest

    def test_writes_file(self, tmp_path, sample_jobs):
        config = PipelineConfig()
        config.tracking_dir = tmp_path
        config.digest_path = tmp_path / "daily-scan-2026-03-11.md"

        step_generate_digest(config, sample_jobs, sample_jobs, sample_jobs[:1])

        assert config.digest_path.exists()
        content = config.digest_path.read_text()
        assert "Mistral AI" in content

    def test_empty_filtered_shows_no_results_message(self, tmp_path):
        config = PipelineConfig()
        config.tracking_dir = tmp_path
        config.digest_path = tmp_path / "daily-scan-2026-03-11.md"

        digest = step_generate_digest(config, [], [], [])

        assert "No new roles found above threshold" in digest
        assert "## New Roles Found" not in digest

    def test_stats_section(self, tmp_path, sample_jobs):
        config = PipelineConfig()
        config.tracking_dir = tmp_path
        config.digest_path = tmp_path / "daily-scan-2026-03-11.md"

        digest = step_generate_digest(config, sample_jobs, sample_jobs, sample_jobs[:2])

        assert f"**Total scraped:** {len(sample_jobs)}" in digest
        assert f"**Score >= {config.min_score} (new):** 2" in digest

    def test_scoring_details_section(self, tmp_path, sample_jobs):
        config = PipelineConfig()
        config.tracking_dir = tmp_path
        config.digest_path = tmp_path / "daily-scan-2026-03-11.md"

        digest = step_generate_digest(config, sample_jobs, sample_jobs, sample_jobs[:2])

        assert "## Scoring Details" in digest
        assert "Strong AI focus" in digest  # from fit_reasoning

    def test_github_actions_summary(self, tmp_path, sample_jobs):
        summary_file = tmp_path / "summary.md"
        config = PipelineConfig()
        config.tracking_dir = tmp_path
        config.digest_path = tmp_path / "daily-scan-2026-03-11.md"

        with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary_file)}):
            step_generate_digest(config, sample_jobs, sample_jobs, sample_jobs[:1])

        assert summary_file.exists()
        assert "Daily Job Scan" in summary_file.read_text()


# ==================== G-564: Failure-rate alarm + regression guard ====================
#
# These tests cover the loud-fail behavior introduced when the AI scoring
# regression (PR #96 era — Llama 3.3 free routing 404s for a week) was
# silently degrading scoring. The new contract:
#   - if more than SCORING_MAX_FAILURE_RATE of AI-attempted jobs fail to
#     score, raise RuntimeError so the workflow fails LOUD
#   - tools/daily_pipeline.py never imports the openai SDK directly
#     (regression guard against re-introducing the hand-rolled client)


class TestScoringFailureRateAlarm:
    """The failure-rate alarm raises when chain is broken (G-564)."""

    @staticmethod
    def _build_failing_provider(fail_count: int, success_count: int):
        """Build an AsyncMock provider that fails N times then succeeds M times.

        Returned provider's .complete() is awaitable. The first N calls raise
        a generic Exception; subsequent calls return a parseable AIResponse.
        """
        from unittest.mock import AsyncMock

        from career_os.schemas.ai import AIFeature, AIResponse

        ok_response = AIResponse(
            content='{"score": 7, "reasoning": "ok", "estimated_salary": "120k", '
            '"effort_flag": "low", "prep_level": 1, "prep_notes": "", '
            '"review_flag": false, "review_reason": ""}',
            provider="mock",
            feature=AIFeature.complete,
            structured=None,
            model="mock-model",
        )

        side_effects: list = []
        for _ in range(fail_count):
            side_effects.append(RuntimeError("provider boom"))
        for _ in range(success_count):
            side_effects.append(ok_response)

        provider = AsyncMock()
        provider.name = "mock-chain"
        provider.complete.side_effect = side_effects
        return provider

    def test_failure_rate_above_threshold_raises(self, tmp_path):
        """When >50% of AI calls fail, step_score raises RuntimeError."""
        import asyncio

        import daily_pipeline

        config = daily_pipeline.PipelineConfig()
        config.tracking_dir = tmp_path
        config.scored_path = tmp_path / "scored.json"
        config.profile_path = tmp_path / "profile.md"
        config.profile_path.write_text("test profile")

        # 4 jobs, 3 fail = 75% failure rate (above default 50%)
        provider = self._build_failing_provider(fail_count=3, success_count=1)
        jobs = [
            {"title": "Engineer", "company": f"C{i}", "description": "desc", "remote": False}
            for i in range(4)
        ]

        with patch.dict(os.environ, {"SCORING_MAX_FAILURE_RATE": "0.50"}):
            with pytest.raises(RuntimeError, match="failure rate"):
                asyncio.run(daily_pipeline._step_score_async(config, jobs, provider))

    def test_failure_rate_below_threshold_returns_normally(self, tmp_path):
        """When failure rate is under threshold, scoring completes."""
        import asyncio

        import daily_pipeline

        config = daily_pipeline.PipelineConfig()
        config.tracking_dir = tmp_path
        config.scored_path = tmp_path / "scored.json"
        config.profile_path = tmp_path / "profile.md"
        config.profile_path.write_text("test profile")

        # 4 jobs, 1 fails = 25% failure rate (below 50%)
        provider = self._build_failing_provider(fail_count=1, success_count=3)
        jobs = [
            {"title": "Engineer", "company": f"C{i}", "description": "desc", "remote": False}
            for i in range(4)
        ]

        with patch.dict(os.environ, {"SCORING_MAX_FAILURE_RATE": "0.50"}):
            result = asyncio.run(daily_pipeline._step_score_async(config, jobs, provider))

        assert len(result) == 4
        assert config.scored_path.exists()

    def test_threshold_configurable(self, tmp_path):
        """Strict threshold (10%) catches lower failure rates."""
        import asyncio

        import daily_pipeline

        config = daily_pipeline.PipelineConfig()
        config.tracking_dir = tmp_path
        config.scored_path = tmp_path / "scored.json"
        config.profile_path = tmp_path / "profile.md"
        config.profile_path.write_text("test profile")

        # 10 jobs, 2 fail = 20% failure rate
        provider = self._build_failing_provider(fail_count=2, success_count=8)
        jobs = [
            {"title": "Eng", "company": f"C{i}", "description": "x", "remote": False}
            for i in range(10)
        ]

        with patch.dict(os.environ, {"SCORING_MAX_FAILURE_RATE": "0.10"}):
            with pytest.raises(RuntimeError, match="20%"):
                asyncio.run(daily_pipeline._step_score_async(config, jobs, provider))

    def test_zero_ai_attempts_does_not_raise(self, tmp_path):
        """When all jobs are pre-filtered (zero AI attempts), no division-by-
        zero, no spurious raise — defensive against an edge case."""
        import asyncio

        import daily_pipeline

        config = daily_pipeline.PipelineConfig()
        config.tracking_dir = tmp_path
        config.scored_path = tmp_path / "scored.json"
        config.profile_path = tmp_path / "profile.md"
        config.profile_path.write_text("test profile")

        # Provider should never be called — all jobs hit pre-filter (nurse/driver
        # titles are in REJECT_TITLE_PATTERNS in tools/job_scorer.py)
        provider = self._build_failing_provider(fail_count=0, success_count=0)
        jobs = [
            {
                "title": "Registered Nurse",
                "company": "Hospital",
                "description": "",
                "remote": False,
            },
            {"title": "Truck Driver", "company": "Logistics", "description": "", "remote": False},
        ]

        result = asyncio.run(daily_pipeline._step_score_async(config, jobs, provider))
        assert len(result) == 2
        # Provider was never called because all jobs were pre-filtered
        provider.complete.assert_not_called()


class TestNoHandrolledOpenAIClient:
    """Regression guard: tools/daily_pipeline.py must NEVER re-introduce the
    hand-rolled OpenAI client. All AI access goes through the provider stack
    at src/career_os/ai/. Re-introducing the bare openai SDK creates the
    silent-degradation risk that broke daily-scan in G-564."""

    def test_no_openai_import_in_daily_pipeline_source(self):
        """Source file must not contain `from openai import` or `OpenAI(api_key=`."""
        import inspect

        import daily_pipeline

        source = inspect.getsource(daily_pipeline)
        assert "from openai import" not in source, (
            "Hand-rolled OpenAI import re-introduced. All AI calls must go "
            "through career_os.ai.factory.get_ai_provider(). See G-564."
        )
        assert "OpenAI(api_key=" not in source, (
            "Hand-rolled OpenAI client re-introduced. Use the provider stack."
        )
        # The class name AsyncOpenAI (Eyas-side) is also banned:
        assert "AsyncOpenAI(api_key=" not in source

    def test_step_score_uses_provider_factory(self):
        """step_score must delegate to career_os.ai.factory.get_ai_provider."""
        import inspect

        import daily_pipeline

        source = inspect.getsource(daily_pipeline.step_score)
        assert "get_ai_provider" in source, (
            "step_score should obtain its provider via "
            "career_os.ai.factory.get_ai_provider — not construct one inline."
        )
