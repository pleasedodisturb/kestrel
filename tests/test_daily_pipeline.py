"""Tests for tools/daily_pipeline.py — all pipeline steps."""

import csv
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

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
        assert config.location == "Frankfurt"
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
            {"title": "AI Product Manager", "company": "ML Startup", "description": "Build AI platform with innovation"},
        ]
        result = _fallback_score(jobs)
        # "ai", "product", "ml", "platform", "startup", "innovation" = 6 positive
        assert result[0]["fit_score"] >= 7

    def test_negative_signals_decrease_score(self):
        jobs = [
            {"title": "PMO Coordinator", "company": "Admin Corp", "description": "PMBOK methodology administrator"},
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
            {"title": "AI ML Product Platform Innovation Builder Remote Startup Founding Technical Program",
             "company": "", "description": ""},
        ]
        result = _fallback_score(jobs)
        assert result[0]["fit_score"] <= 10

        jobs = [
            {"title": "PMBOK PMO Coordinator Administrator Sachbearbeiter",
             "company": "", "description": ""},
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
        csv_path.write_text("date_applied,company,role,url,source,status,salary_range,contact,next_step,notes,fit_score\n")

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
