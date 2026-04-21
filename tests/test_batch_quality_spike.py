"""Tests for the batch scoring quality spike (G-453).

Validates that the batch scoring pipeline is structurally sound:
- Batch scoring returns same number of results as individual scoring
- All batch results have valid ScoreResult schema
- Batch and individual scoring use the same provider interface
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from career_os.ai.mock_provider import MockProvider
from career_os.schemas.ai import ScoreResult
from career_os.services.batch_scoring import (
    batch_score_jobs,
    build_batch_prompt,
    chunk_jobs,
    parse_batch_response,
)

GOLDEN_SET = Path(__file__).resolve().parent / "fixtures" / "scoring_golden_set.json"


@pytest.fixture
def golden_data():
    """Load golden set jobs and profile."""
    data = json.loads(GOLDEN_SET.read_text())
    return data["jobs"], data["profile"]


@pytest.fixture
def provider():
    """Return a MockProvider instance."""
    return MockProvider()


class TestBatchReturnsMatchingCount:
    """Batch scoring returns same number of results as individual."""

    @pytest.mark.asyncio
    async def test_batch_returns_same_count_as_individual(self, provider, golden_data):
        """Batch and individual scoring produce results for all 20 golden set jobs."""
        jobs, profile = golden_data

        # Individual scoring
        individual_results = {}
        for job in jobs:
            response = await provider.score(
                job_description=job.get("description", ""),
                profile_data=profile,
            )
            if response.structured and isinstance(response.structured, ScoreResult):
                individual_results[str(job["id"])] = response.structured

        # Batch scoring
        batch_results = await batch_score_jobs(
            provider=provider,
            jobs=jobs,
            profile_data=profile,
            batch_size=10,
        )

        assert len(individual_results) == len(jobs)
        assert len(batch_results) == len(jobs)
        assert len(batch_results) == len(individual_results)

    @pytest.mark.asyncio
    async def test_batch_covers_all_job_ids(self, provider, golden_data):
        """Every job ID from the input appears in the batch results."""
        jobs, profile = golden_data

        batch_results = await batch_score_jobs(
            provider=provider,
            jobs=jobs,
            profile_data=profile,
            batch_size=10,
        )

        input_ids = {str(j["id"]) for j in jobs}
        result_ids = set(batch_results.keys())
        assert result_ids == input_ids


class TestBatchSchemaCompliance:
    """All batch results have valid ScoreResult schema."""

    @pytest.mark.asyncio
    async def test_all_batch_results_are_valid_score_results(self, provider, golden_data):
        """Every result from batch scoring validates as a ScoreResult."""
        jobs, profile = golden_data

        batch_results = await batch_score_jobs(
            provider=provider,
            jobs=jobs,
            profile_data=profile,
            batch_size=10,
        )

        for job_id, score_result in batch_results.items():
            assert isinstance(score_result, ScoreResult), (
                f"Job {job_id}: expected ScoreResult, got {type(score_result)}"
            )
            # Re-validate through Pydantic to catch any drift
            validated = ScoreResult.model_validate(score_result.model_dump())
            assert validated.fit_score >= 0.0
            assert validated.fit_score <= 10.0
            assert len(validated.reasoning) >= 100
            assert len(validated.score_breakdown) >= 3

    @pytest.mark.asyncio
    async def test_batch_results_have_dimensional_scores(self, provider, golden_data):
        """Batch results include dimensional scores with all 6 dimensions."""
        jobs, profile = golden_data

        batch_results = await batch_score_jobs(
            provider=provider,
            jobs=jobs,
            profile_data=profile,
            batch_size=10,
        )

        for job_id, score_result in batch_results.items():
            dim = score_result.dimensional_scores
            assert dim is not None, f"Job {job_id}: missing dimensional_scores"
            assert 0.0 <= dim.technical_fit <= 10.0
            assert 0.0 <= dim.seniority_alignment <= 10.0
            assert 0.0 <= dim.compensation_fit <= 10.0
            assert 0.0 <= dim.location_fit <= 10.0
            assert 0.0 <= dim.career_trajectory <= 10.0
            assert 0.0 <= dim.company_fit <= 10.0


class TestProviderInterfaceConsistency:
    """Batch and individual scoring use the same provider interface."""

    @pytest.mark.asyncio
    async def test_both_paths_use_mock_provider(self, provider, golden_data):
        """Both individual and batch scoring go through MockProvider."""
        jobs, profile = golden_data
        single_job = jobs[0]

        # Individual
        ind_response = await provider.score(
            job_description=single_job.get("description", ""),
            profile_data=profile,
        )
        assert ind_response.provider == "mock"
        assert ind_response.model == "mock-v1"

        # Batch (uses provider.complete() then falls back to provider.score())
        batch_results = await batch_score_jobs(
            provider=provider,
            jobs=[single_job],
            profile_data=profile,
            batch_size=10,
        )
        assert str(single_job["id"]) in batch_results
        # The result is a ScoreResult from the same mock provider
        sr = batch_results[str(single_job["id"])]
        assert isinstance(sr, ScoreResult)
        assert sr.fit_score >= 0.0

    def test_build_batch_prompt_produces_valid_prompt(self, golden_data):
        """build_batch_prompt() generates a prompt string and ordered IDs."""
        jobs, profile = golden_data

        prompt, ordered_ids = build_batch_prompt(jobs[:5], profile)

        assert isinstance(prompt, str)
        assert len(prompt) > 100
        assert len(ordered_ids) == 5
        # All job IDs should appear in the ordered list
        assert set(ordered_ids) == {str(j["id"]) for j in jobs[:5]}

    def test_chunk_jobs_splits_correctly(self, golden_data):
        """chunk_jobs() produces correct batch sizes."""
        jobs, _ = golden_data

        chunks = chunk_jobs(jobs, 10)
        assert len(chunks) == 2  # 20 jobs / 10 = 2 batches
        assert len(chunks[0]) == 10
        assert len(chunks[1]) == 10

        # Uneven split
        chunks_7 = chunk_jobs(jobs, 7)
        assert len(chunks_7) == 3  # ceil(20/7) = 3
        assert len(chunks_7[0]) == 7
        assert len(chunks_7[1]) == 7
        assert len(chunks_7[2]) == 6

    def test_parse_batch_response_rejects_plain_text(self):
        """parse_batch_response() returns empty dict for non-JSON responses."""
        result = parse_batch_response(
            "Mock AI response to: Score each of the following",
            ["id-1", "id-2"],
        )
        assert result == {}

    @pytest.mark.asyncio
    async def test_empty_job_list_returns_empty(self, provider, golden_data):
        """batch_score_jobs() with empty input returns empty dict."""
        _, profile = golden_data

        result = await batch_score_jobs(
            provider=provider,
            jobs=[],
            profile_data=profile,
            batch_size=10,
        )
        assert result == {}
