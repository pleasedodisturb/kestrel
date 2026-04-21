"""Tests for the discovery pre-filter (G-439).

Covers:
- PrefilterConfig defaults and construction
- PrefilterStrategy enum values
- run_prefilter with OFF strategy (passthrough)
- run_prefilter with MODERATE strategy (title OR skills)
- run_prefilter with STRICT strategy (title OR skills, NOT blacklisted)
- Metrics tracking (filter rate, signal counts)
- Edge cases: empty jobs, missing fields, empty keywords
- _build_prefilter_config from settings
- Integration with discovery pipeline
"""

from __future__ import annotations

import json
import logging
from unittest.mock import patch

import pytest

from career_os.discovery.prefilter import (
    PrefilterConfig,
    PrefilterMetrics,
    PrefilterStrategy,
    _compile_patterns,
    _industry_blacklisted,
    _skill_density_passes,
    _title_matches,
    run_prefilter,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tech_config() -> PrefilterConfig:
    """A realistic prefilter config for a software engineer profile."""
    return PrefilterConfig(
        strategy=PrefilterStrategy.STRICT,
        title_keywords=[
            "software engineer",
            "backend engineer",
            "frontend engineer",
            "full stack",
            "platform engineer",
            "sre",
            "devops engineer",
        ],
        skill_keywords=[
            "python",
            "javascript",
            "typescript",
            "react",
            "docker",
            "kubernetes",
            "sql",
            "aws",
            "fastapi",
            "django",
        ],
        min_skill_matches=2,
        blacklist_industries=[
            "healthcare",
            "dental",
            "veterinary",
            "agriculture",
            "trucking",
            "plumbing",
        ],
    )


@pytest.fixture
def sample_jobs() -> list[dict]:
    """A mix of relevant and irrelevant jobs for prefilter testing."""
    return [
        {
            "title": "Senior Software Engineer",
            "company": "Stripe",
            "location": "Remote",
            "description": "Build payment APIs with Python and React. Docker experience required.",
            "industry": "technology",
        },
        {
            "title": "Backend Engineer",
            "company": "Datadog",
            "location": "New York",
            "description": "Observability platform. Python, Kubernetes, AWS.",
            "industry": "technology",
        },
        {
            "title": "Dental Hygienist",
            "company": "Sunrise Dental",
            "location": "Phoenix, AZ",
            "description": "Patient care and dental cleaning procedures.",
            "industry": "dental",
        },
        {
            "title": "Truck Driver CDL-A",
            "company": "UPS Freight",
            "location": "Dallas, TX",
            "description": "Long haul driving, CDL-A required.",
            "industry": "trucking",
        },
        {
            "title": "IT Specialist",
            "company": "Acme Corp",
            "location": "Chicago",
            "description": "Internal IT support. Experience with python and sql databases.",
            "industry": "technology",
        },
        {
            "title": "Warehouse Associate",
            "company": "Amazon",
            "location": "Phoenix, AZ",
            "description": "Pick and pack orders in warehouse facility.",
            "industry": "retail",
        },
    ]


# ---------------------------------------------------------------------------
# Unit tests: helper functions
# ---------------------------------------------------------------------------


class TestCompilePatterns:
    def test_compiles_basic_keywords(self):
        patterns = _compile_patterns(["python", "react"])
        assert len(patterns) == 2
        assert patterns[0].search("I know Python well")

    def test_case_insensitive(self):
        patterns = _compile_patterns(["Docker"])
        assert patterns[0].search("docker is great")
        assert patterns[0].search("DOCKER containers")

    def test_skips_empty_strings(self):
        patterns = _compile_patterns(["python", "", "react", ""])
        assert len(patterns) == 2

    def test_escapes_special_chars(self):
        patterns = _compile_patterns(["c++", "node.js"])
        assert patterns[0].search("I use c++ daily")
        assert patterns[1].search("Built with node.js")


class TestTitleMatches:
    def test_matches_exact_keyword(self):
        patterns = _compile_patterns(["software engineer"])
        assert _title_matches("Senior Software Engineer", patterns) is True
        assert _title_matches("Dental Hygienist", patterns) is False

    def test_matches_substring(self):
        patterns = _compile_patterns(["backend engineer"])
        assert _title_matches("Staff Backend Engineer, Platform", patterns) is True

    def test_no_patterns_no_match(self):
        assert _title_matches("Software Engineer", []) is False


class TestSkillDensityPasses:
    def test_passes_with_enough_skills(self):
        patterns = _compile_patterns(["python", "react", "docker"])
        desc = "Build with Python and React. Docker experience a plus."
        assert _skill_density_passes(desc, patterns, min_matches=2) is True
        assert _skill_density_passes(desc, patterns, min_matches=3) is True

    def test_fails_with_too_few_skills(self):
        patterns = _compile_patterns(["python", "react", "docker"])
        desc = "Build with Python. No other relevant skills."
        assert _skill_density_passes(desc, patterns, min_matches=2) is False

    def test_zero_min_always_passes(self):
        patterns = _compile_patterns(["python"])
        assert _skill_density_passes("no skills here", patterns, min_matches=0) is True


class TestIndustryBlacklisted:
    def test_blacklisted_industry(self):
        blacklist = {"healthcare", "dental", "trucking"}
        assert _industry_blacklisted("healthcare", blacklist) is True
        assert _industry_blacklisted("Healthcare", blacklist) is True

    def test_non_blacklisted_industry(self):
        blacklist = {"healthcare", "dental"}
        assert _industry_blacklisted("technology", blacklist) is False

    def test_empty_industry(self):
        blacklist = {"healthcare"}
        assert _industry_blacklisted("", blacklist) is False

    def test_whitespace_handling(self):
        blacklist = {"healthcare"}
        assert _industry_blacklisted("  healthcare  ", blacklist) is True


# ---------------------------------------------------------------------------
# Unit tests: run_prefilter
# ---------------------------------------------------------------------------


class TestRunPrefilterOff:
    def test_off_passes_all_jobs(self, sample_jobs):
        config = PrefilterConfig(strategy=PrefilterStrategy.OFF)
        passed, metrics = run_prefilter(sample_jobs, config)
        assert len(passed) == len(sample_jobs)
        assert metrics.passed == len(sample_jobs)
        assert metrics.filtered == 0
        assert metrics.strategy == "off"

    def test_off_with_empty_list(self):
        config = PrefilterConfig(strategy=PrefilterStrategy.OFF)
        passed, metrics = run_prefilter([], config)
        assert len(passed) == 0
        assert metrics.total == 0
        assert metrics.filter_rate == 0.0


class TestRunPrefilterModerate:
    def test_moderate_passes_title_matches(self, sample_jobs, tech_config):
        tech_config.strategy = PrefilterStrategy.MODERATE
        passed, metrics = run_prefilter(sample_jobs, tech_config)
        titles = {j["title"] for j in passed}
        assert "Senior Software Engineer" in titles
        assert "Backend Engineer" in titles
        assert "Dental Hygienist" not in titles

    def test_moderate_passes_skill_matches_without_title(self, tech_config):
        """IT Specialist has python+sql skills but no matching title keyword."""
        tech_config.strategy = PrefilterStrategy.MODERATE
        jobs = [
            {
                "title": "IT Specialist",
                "description": "Python scripting and SQL database management.",
                "industry": "technology",
            },
        ]
        passed, metrics = run_prefilter(jobs, tech_config)
        assert len(passed) == 1
        assert metrics.skill_matches == 1

    def test_moderate_ignores_industry(self, tech_config):
        """Moderate mode should NOT filter by industry."""
        tech_config.strategy = PrefilterStrategy.MODERATE
        jobs = [
            {
                "title": "Software Engineer",
                "description": "Python and React development.",
                "industry": "healthcare",
            },
        ]
        passed, metrics = run_prefilter(jobs, tech_config)
        assert len(passed) == 1
        assert metrics.industry_rejections == 1  # counted but not acted on
        assert metrics.filtered == 0


class TestRunPrefilterStrict:
    def test_strict_filters_blacklisted_industry(self, tech_config):
        """Even with matching title, blacklisted industry is rejected in strict mode."""
        jobs = [
            {
                "title": "Software Engineer",
                "description": "Build healthcare systems with Python.",
                "industry": "healthcare",
            },
        ]
        passed, metrics = run_prefilter(jobs, tech_config)
        assert len(passed) == 0
        assert metrics.filtered == 1
        assert metrics.industry_rejections == 1

    def test_strict_passes_relevant_tech_jobs(self, sample_jobs, tech_config):
        passed, metrics = run_prefilter(sample_jobs, tech_config)
        titles = {j["title"] for j in passed}
        # Tech jobs with title or skill match, not blacklisted
        assert "Senior Software Engineer" in titles
        assert "Backend Engineer" in titles
        assert "IT Specialist" in titles  # has skills, tech industry
        # Filtered: dental (blacklisted), trucker (no match), warehouse (no match)
        assert "Dental Hygienist" not in titles
        assert "Truck Driver CDL-A" not in titles
        assert "Warehouse Associate" not in titles

    def test_strict_rejects_no_signal_no_blacklist(self, tech_config):
        """Jobs with no title/skill match are rejected even if industry is clean."""
        jobs = [
            {
                "title": "Cashier",
                "description": "Handle cash register and customer service.",
                "industry": "retail",
            },
        ]
        passed, metrics = run_prefilter(jobs, tech_config)
        assert len(passed) == 0
        assert metrics.filtered == 1


class TestPrefilterMetrics:
    def test_filter_rate_calculation(self):
        m = PrefilterMetrics(total=100, passed=40, filtered=60)
        assert m.filter_rate == 60.0

    def test_filter_rate_zero_total(self):
        m = PrefilterMetrics(total=0, passed=0, filtered=0)
        assert m.filter_rate == 0.0

    def test_metrics_track_all_signals(self, sample_jobs, tech_config):
        _, metrics = run_prefilter(sample_jobs, tech_config)
        assert metrics.total == 6
        assert metrics.title_matches >= 2  # at least SWE + Backend
        assert metrics.skill_matches >= 2  # jobs with python+react etc
        assert metrics.industry_rejections >= 2  # dental + trucking
        assert metrics.passed + metrics.filtered == metrics.total


class TestPrefilterEdgeCases:
    def test_missing_fields_treated_as_empty(self, tech_config):
        """Jobs missing title/description/industry should not crash."""
        jobs = [
            {"company": "Mystery Corp"},
            {"title": "Software Engineer"},
        ]
        passed, metrics = run_prefilter(jobs, tech_config)
        # First job: no title, no desc, no industry -> no signal -> filtered
        # Second job: title match, no industry -> not blacklisted -> passes
        assert metrics.total == 2
        assert len(passed) == 1
        assert passed[0]["title"] == "Software Engineer"

    def test_empty_keywords_passes_nothing_in_moderate(self):
        """With no keywords configured, moderate filters everything."""
        config = PrefilterConfig(
            strategy=PrefilterStrategy.MODERATE,
            title_keywords=[],
            skill_keywords=[],
        )
        jobs = [{"title": "Software Engineer", "description": "Python dev"}]
        passed, metrics = run_prefilter(jobs, config)
        assert len(passed) == 0
        assert metrics.filtered == 1


class TestPrefilterLogging:
    def test_logs_metrics(self, sample_jobs, tech_config, caplog):
        with caplog.at_level(logging.INFO, logger="career_os.discovery.prefilter"):
            run_prefilter(sample_jobs, tech_config)
        assert any("Prefilter [strict]" in msg for msg in caplog.messages)
        assert any("filtered" in msg for msg in caplog.messages)

    def test_off_logs_passthrough(self, sample_jobs, caplog):
        config = PrefilterConfig(strategy=PrefilterStrategy.OFF)
        with caplog.at_level(logging.INFO, logger="career_os.discovery.prefilter"):
            run_prefilter(sample_jobs, config)
        assert any("Prefilter OFF" in msg for msg in caplog.messages)


# ---------------------------------------------------------------------------
# Integration: _build_prefilter_config
# ---------------------------------------------------------------------------


class TestBuildPrefilterConfig:
    def test_reads_strategy_from_settings(self):
        from career_os.services.discovery import _build_prefilter_config

        with patch("career_os.config.settings") as mock_settings:
            mock_settings.prefilter_strategy = "moderate"
            config = _build_prefilter_config()
            assert config.strategy == PrefilterStrategy.MODERATE

    def test_default_blacklist_industries(self):
        from career_os.services.discovery import _build_prefilter_config

        with patch("career_os.config.settings") as mock_settings:
            mock_settings.prefilter_strategy = "strict"
            config = _build_prefilter_config()
            assert "healthcare" in config.blacklist_industries
            assert "dental" in config.blacklist_industries
            assert len(config.blacklist_industries) >= 10

    def test_search_profile_overrides_keywords(self):
        from career_os.services.discovery import _build_prefilter_config

        # Create a mock SearchProfile with filter overrides
        class MockSearchProfile:
            filters = json.dumps(
                {
                    "prefilter_title_keywords": ["data scientist", "ml engineer"],
                    "prefilter_skill_keywords": ["pytorch", "tensorflow"],
                    "prefilter_blacklist_industries": ["mining"],
                }
            )

        with patch("career_os.config.settings") as mock_settings:
            mock_settings.prefilter_strategy = "strict"
            config = _build_prefilter_config(MockSearchProfile())
            assert config.title_keywords == ["data scientist", "ml engineer"]
            assert config.skill_keywords == ["pytorch", "tensorflow"]
            assert config.blacklist_industries == ["mining"]

    def test_off_strategy_from_settings(self):
        from career_os.services.discovery import _build_prefilter_config

        with patch("career_os.config.settings") as mock_settings:
            mock_settings.prefilter_strategy = "off"
            config = _build_prefilter_config()
            assert config.strategy == PrefilterStrategy.OFF


# ---------------------------------------------------------------------------
# Strategy enum
# ---------------------------------------------------------------------------


class TestPrefilterStrategy:
    def test_enum_values(self):
        assert PrefilterStrategy.STRICT.value == "strict"
        assert PrefilterStrategy.MODERATE.value == "moderate"
        assert PrefilterStrategy.OFF.value == "off"

    def test_from_string(self):
        assert PrefilterStrategy("strict") == PrefilterStrategy.STRICT
        assert PrefilterStrategy("moderate") == PrefilterStrategy.MODERATE
        assert PrefilterStrategy("off") == PrefilterStrategy.OFF
