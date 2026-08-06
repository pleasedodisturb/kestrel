"""Tests for the spike_prefilter module."""

from __future__ import annotations

import sys
from pathlib import Path

# Add tools/ to path so we can import the spike module directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spike_prefilter import (
    ExperimentResults,
    FilterResult,
    SyntheticJob,
    _evaluate_filter,
    filter_by_industry_blacklist,
    filter_by_salary,
    filter_by_skill_density,
    filter_by_title,
    filter_combined,
    filter_combined_strict,
    generate_jobs,
    run_experiment,
)

# ---------------------------------------------------------------------------
# Job generation tests
# ---------------------------------------------------------------------------


class TestGenerateJobs:
    def test_correct_count(self):
        jobs = generate_jobs(500, "software-engineer", seed=1)
        assert len(jobs) == 500

    def test_correct_count_large(self):
        jobs = generate_jobs(10_000, "software-engineer", seed=42)
        assert len(jobs) == 10_000

    def test_all_scores_in_range(self):
        jobs = generate_jobs(1000, "software-engineer", seed=1)
        for job in jobs:
            assert 1 <= job.ground_truth_score <= 10, f"Job {job.id} score out of range"

    def test_distribution_has_all_tiers(self):
        """With 1000 jobs, all three relevance tiers should be populated."""
        jobs = generate_jobs(1000, "software-engineer", seed=1)
        high = [j for j in jobs if j.ground_truth_score >= 7]
        mid = [j for j in jobs if 4 <= j.ground_truth_score <= 6]
        low = [j for j in jobs if j.ground_truth_score <= 3]
        assert len(high) > 0, "No high-relevance jobs generated"
        assert len(mid) > 0, "No mid-relevance jobs generated"
        assert len(low) > 0, "No low-relevance jobs generated"

    def test_distribution_proportions(self):
        """~20% high, ~20% mid, ~60% low with some tolerance."""
        jobs = generate_jobs(5000, "software-engineer", seed=1)
        high = len([j for j in jobs if j.ground_truth_score >= 7])
        mid = len([j for j in jobs if 4 <= j.ground_truth_score <= 6])
        low = len([j for j in jobs if j.ground_truth_score <= 3])
        # Allow 5% tolerance
        assert 0.12 < high / 5000 < 0.28, f"High proportion {high/5000:.2f} outside range"
        assert 0.12 < mid / 5000 < 0.28, f"Mid proportion {mid/5000:.2f} outside range"
        assert 0.50 < low / 5000 < 0.70, f"Low proportion {low/5000:.2f} outside range"

    def test_deterministic_with_same_seed(self):
        jobs_a = generate_jobs(100, "software-engineer", seed=99)
        jobs_b = generate_jobs(100, "software-engineer", seed=99)
        for a, b in zip(jobs_a, jobs_b):
            assert a.title == b.title
            assert a.ground_truth_score == b.ground_truth_score
            assert a.company == b.company

    def test_different_seeds_produce_different_data(self):
        jobs_a = generate_jobs(100, "software-engineer", seed=1)
        jobs_b = generate_jobs(100, "software-engineer", seed=2)
        # At least some titles should differ
        diffs = sum(1 for a, b in zip(jobs_a, jobs_b) if a.title != b.title)
        assert diffs > 0

    def test_all_profiles_generate(self):
        for profile in ["software-engineer", "product-manager", "data-scientist"]:
            jobs = generate_jobs(100, profile, seed=1)
            assert len(jobs) == 100


# ---------------------------------------------------------------------------
# Filter result metric tests
# ---------------------------------------------------------------------------


class TestFilterResult:
    def test_precision(self):
        fr = FilterResult(strategy_name="t", passed_ids={0, 1, 2}, total_jobs=10)
        fr.true_positives = 2
        fr.false_positives = 1
        assert abs(fr.precision - 2 / 3) < 0.001

    def test_recall(self):
        fr = FilterResult(strategy_name="t", passed_ids={0, 1, 2}, total_jobs=10)
        fr.true_positives = 2
        fr.false_negatives = 1
        assert abs(fr.recall - 2 / 3) < 0.001

    def test_f1(self):
        fr = FilterResult(strategy_name="t", passed_ids={0, 1, 2}, total_jobs=10)
        fr.true_positives = 2
        fr.false_positives = 1
        fr.false_negatives = 1
        p = 2 / 3
        r = 2 / 3
        expected_f1 = 2 * p * r / (p + r)
        assert abs(fr.f1 - expected_f1) < 0.001

    def test_eliminated_pct(self):
        fr = FilterResult(strategy_name="t", passed_ids={0, 1, 2}, total_jobs=10)
        assert abs(fr.eliminated_pct - 70.0) < 0.001

    def test_zero_division_safe(self):
        fr = FilterResult(strategy_name="t", passed_ids=set(), total_jobs=10)
        assert fr.precision == 0.0
        assert fr.recall == 0.0
        assert fr.f1 == 0.0


# ---------------------------------------------------------------------------
# Individual filter tests
# ---------------------------------------------------------------------------


def _make_job(
    id: int,
    title: str = "SWE",
    salary_min: int | None = None,
    salary_max: int | None = None,
    description: str = "",
    industry: str = "technology",
    score: int = 5,
) -> SyntheticJob:
    return SyntheticJob(
        id=id,
        title=title,
        company="TestCo",
        location="Remote",
        salary_min=salary_min,
        salary_max=salary_max,
        description=description,
        industry=industry,
        ground_truth_score=score,
    )


class TestTitleFilter:
    def test_matches_relevant_title(self):
        jobs = [_make_job(0, title="Senior Software Engineer")]
        passed = filter_by_title(jobs, "software-engineer")
        assert 0 in passed

    def test_rejects_irrelevant_title(self):
        jobs = [_make_job(0, title="Dental Hygienist")]
        passed = filter_by_title(jobs, "software-engineer")
        assert 0 not in passed

    def test_case_insensitive(self):
        jobs = [_make_job(0, title="SENIOR SOFTWARE ENGINEER")]
        passed = filter_by_title(jobs, "software-engineer")
        assert 0 in passed

    def test_partial_match(self):
        jobs = [_make_job(0, title="Junior Software Engineer at Google")]
        passed = filter_by_title(jobs, "software-engineer")
        assert 0 in passed


class TestSalaryFilter:
    def test_passes_in_range(self):
        jobs = [_make_job(0, salary_min=100_000, salary_max=150_000)]
        passed = filter_by_salary(jobs, "software-engineer")
        assert 0 in passed

    def test_rejects_out_of_range(self):
        jobs = [_make_job(0, salary_min=20_000, salary_max=30_000)]
        passed = filter_by_salary(jobs, "software-engineer")
        assert 0 not in passed

    def test_passes_no_salary(self):
        jobs = [_make_job(0)]
        passed = filter_by_salary(jobs, "software-engineer")
        assert 0 in passed

    def test_passes_overlapping_range(self):
        # Job range partially overlaps profile range
        jobs = [_make_job(0, salary_min=70_000, salary_max=100_000)]
        passed = filter_by_salary(jobs, "software-engineer")
        assert 0 in passed


class TestSkillDensityFilter:
    def test_passes_with_enough_skills(self):
        jobs = [_make_job(0, description="Requires python, react, and docker")]
        passed = filter_by_skill_density(jobs, "software-engineer", min_matches=2)
        assert 0 in passed

    def test_rejects_with_too_few_skills(self):
        jobs = [_make_job(0, description="Must have CDL-A license")]
        passed = filter_by_skill_density(jobs, "software-engineer", min_matches=2)
        assert 0 not in passed

    def test_min_matches_threshold(self):
        jobs = [_make_job(0, description="python experience required")]
        passed_1 = filter_by_skill_density(jobs, "software-engineer", min_matches=1)
        passed_2 = filter_by_skill_density(jobs, "software-engineer", min_matches=2)
        assert 0 in passed_1
        assert 0 not in passed_2


class TestIndustryBlacklistFilter:
    def test_passes_tech(self):
        jobs = [_make_job(0, industry="technology")]
        passed = filter_by_industry_blacklist(jobs, "software-engineer")
        assert 0 in passed

    def test_rejects_healthcare(self):
        jobs = [_make_job(0, industry="healthcare")]
        passed = filter_by_industry_blacklist(jobs, "software-engineer")
        assert 0 not in passed

    def test_case_insensitive(self):
        jobs = [_make_job(0, industry="Healthcare")]
        passed = filter_by_industry_blacklist(jobs, "software-engineer")
        assert 0 not in passed


# ---------------------------------------------------------------------------
# Combined filter tests
# ---------------------------------------------------------------------------


class TestCombinedFilters:
    def test_combined_passes_strong_match(self):
        jobs = [
            _make_job(
                0,
                title="Senior Software Engineer",
                salary_min=120_000,
                salary_max=180_000,
                description="python, react, docker, kubernetes, aws",
                industry="technology",
            )
        ]
        passed = filter_combined(jobs, "software-engineer")
        assert 0 in passed

    def test_combined_rejects_no_signals(self):
        jobs = [
            _make_job(
                0,
                title="Dental Hygienist",
                salary_min=25_000,
                salary_max=35_000,
                description="dental tools and patient care",
                industry="healthcare",
            )
        ]
        passed = filter_combined(jobs, "software-engineer")
        assert 0 not in passed

    def test_strict_requires_title_or_skills(self):
        # Has matching industry but no title/skill match
        jobs = [
            _make_job(
                0,
                title="Office Manager",
                description="manage office supplies",
                industry="technology",
            )
        ]
        passed = filter_combined_strict(jobs, "software-engineer")
        assert 0 not in passed

    def test_strict_rejects_blacklisted_industry_despite_title(self):
        # Has matching title but blacklisted industry
        jobs = [
            _make_job(
                0,
                title="Software Engineer",
                description="python, react",
                industry="healthcare",
            )
        ]
        passed = filter_combined_strict(jobs, "software-engineer")
        assert 0 not in passed


# ---------------------------------------------------------------------------
# Evaluation function tests
# ---------------------------------------------------------------------------


class TestEvaluateFilter:
    def test_confusion_matrix_sums_to_total(self):
        jobs = generate_jobs(500, "software-engineer", seed=42)
        passed = filter_by_title(jobs, "software-engineer")
        result = _evaluate_filter("test", passed, jobs, relevance_threshold=6)
        total = (
            result.true_positives
            + result.false_positives
            + result.true_negatives
            + result.false_negatives
        )
        assert total == 500

    def test_perfect_filter(self):
        """A filter that passes exactly the relevant jobs should have perfect metrics."""
        jobs = generate_jobs(200, "software-engineer", seed=1)
        relevant_ids = {j.id for j in jobs if j.ground_truth_score >= 6}
        result = _evaluate_filter("perfect", relevant_ids, jobs, relevance_threshold=6)
        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.f1 == 1.0
        assert result.false_negatives == 0
        assert result.false_positives == 0

    def test_pass_all_filter(self):
        """A filter that passes everything should have recall=1.0."""
        jobs = generate_jobs(200, "software-engineer", seed=1)
        all_ids = {j.id for j in jobs}
        result = _evaluate_filter("all", all_ids, jobs, relevance_threshold=6)
        assert result.recall == 1.0
        assert result.false_negatives == 0
        assert result.eliminated_pct == 0.0

    def test_pass_none_filter(self):
        """A filter that passes nothing should have recall=0.0."""
        jobs = generate_jobs(200, "software-engineer", seed=1)
        result = _evaluate_filter("none", set(), jobs, relevance_threshold=6)
        assert result.recall == 0.0
        assert result.eliminated_pct == 100.0


# ---------------------------------------------------------------------------
# Full experiment test
# ---------------------------------------------------------------------------


class TestRunExperiment:
    def test_returns_results(self):
        results = run_experiment("software-engineer", n_jobs=200, seed=1)
        assert isinstance(results, ExperimentResults)
        assert results.total_jobs == 200
        assert len(results.filter_results) == 6

    def test_all_profiles(self):
        for profile in ["software-engineer", "product-manager", "data-scientist"]:
            results = run_experiment(profile, n_jobs=100, seed=1)
            assert results.profile_name == profile
            assert results.total_jobs == 100

    def test_relevant_irrelevant_sum(self):
        results = run_experiment("software-engineer", n_jobs=500, seed=42)
        assert results.relevant_jobs + results.irrelevant_jobs == 500


# ---------------------------------------------------------------------------
# Self-test runner test
# ---------------------------------------------------------------------------


class TestSelfTests:
    def test_self_tests_pass(self):
        from spike_prefilter import _run_self_tests

        assert _run_self_tests() is True
