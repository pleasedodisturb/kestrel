"""Tests for batch scoring — multi-job-per-prompt scoring service."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from career_os.schemas.ai import AIFeature, AIResponse, ScoreResult
from career_os.services.batch_scoring import (
    DEFAULT_BATCH_SIZE,
    _extract_json_array,
    batch_score_jobs,
    build_batch_prompt,
    chunk_jobs,
    get_batch_size,
    parse_batch_response,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_PROFILE = {
    "name": "Alice Engineer",
    "location": "Berlin, Germany",
    "job_family": "SWE",
    "skills": [{"name": "Python", "level": 8}],
    "goals": [],
    "weights": {"skills_match": 0.3, "career_alignment": 0.2},
}

SAMPLE_JOBS = [
    {
        "id": "101",
        "title": "Backend Engineer",
        "company": "Acme Corp",
        "description": "Build APIs with Python and FastAPI. 3+ years experience required.",
    },
    {
        "id": "102",
        "title": "Frontend Developer",
        "company": "Widget Inc",
        "description": "React and TypeScript SPA development. Remote friendly.",
    },
    {
        "id": "103",
        "title": "Data Engineer",
        "company": "DataCo",
        "description": "ETL pipelines with Spark and Airflow. SQL expertise needed.",
    },
]


def _make_score_dict(job_id: str, fit_score: float = 7.5) -> dict:
    """Build a valid ScoreResult dict with the given job_id."""
    return {
        "job_id": job_id,
        "fit_score": fit_score,
        "reasoning": "A" * 100,
        "estimated_salary": "$120k-150k",
        "effort_flag": "medium",
        "prep_level": "moderate",
        "prep_notes": "Brush up on system design",
        "readiness_score": 75.0,
        "career_alignment": 8.0,
        "score_breakdown": [
            {"factor": "skills", "contribution": 2.0, "description": "Strong Python"},
            {"factor": "experience", "contribution": 1.5, "description": "3+ years"},
            {"factor": "location", "contribution": -0.5, "description": "Remote ok"},
        ],
        "dimensional_scores": {
            "technical_fit": 8.0,
            "seniority_alignment": 7.0,
            "compensation_fit": 7.5,
            "location_fit": 9.0,
            "career_trajectory": 7.0,
            "company_fit": 6.5,
        },
        "ats_keywords": [
            {"keyword": "Python", "category": "technical", "matched": True},
            {"keyword": "FastAPI", "category": "tool", "matched": True},
        ],
        "desire_score": 7.0,
        "desire_reasoning": "Good growth opportunity at a solid company",
    }


# ---------------------------------------------------------------------------
# get_batch_size
# ---------------------------------------------------------------------------


class TestGetBatchSize:
    def test_default_when_env_not_set(self):
        with patch.dict("os.environ", {}, clear=False):
            # Remove BATCH_SCORING_SIZE if present
            import os

            os.environ.pop("BATCH_SCORING_SIZE", None)
            result = get_batch_size()
            assert result == DEFAULT_BATCH_SIZE
            assert result == 10

    def test_reads_from_env(self):
        with patch.dict("os.environ", {"BATCH_SCORING_SIZE": "25"}):
            result = get_batch_size()
            assert result == 25

    def test_invalid_env_returns_default(self):
        with patch.dict("os.environ", {"BATCH_SCORING_SIZE": "abc"}):
            result = get_batch_size()
            assert result == DEFAULT_BATCH_SIZE

    def test_zero_env_returns_default(self):
        with patch.dict("os.environ", {"BATCH_SCORING_SIZE": "0"}):
            result = get_batch_size()
            assert result == DEFAULT_BATCH_SIZE

    def test_negative_env_returns_default(self):
        with patch.dict("os.environ", {"BATCH_SCORING_SIZE": "-5"}):
            result = get_batch_size()
            assert result == DEFAULT_BATCH_SIZE


# ---------------------------------------------------------------------------
# build_batch_prompt
# ---------------------------------------------------------------------------


class TestBuildBatchPrompt:
    def test_prompt_contains_all_jobs(self):
        prompt, ordered_ids = build_batch_prompt(SAMPLE_JOBS, SAMPLE_PROFILE)
        assert "101" in prompt
        assert "102" in prompt
        assert "103" in prompt
        assert len(ordered_ids) == 3
        assert set(ordered_ids) == {"101", "102", "103"}

    def test_prompt_contains_profile(self):
        prompt, _ = build_batch_prompt(SAMPLE_JOBS, SAMPLE_PROFILE)
        assert "Alice Engineer" in prompt
        assert "Berlin" in prompt

    def test_position_randomization(self):
        """Run multiple times and verify order varies (statistical check)."""
        orders_seen: set[tuple[str, ...]] = set()
        for _ in range(50):
            _, ordered_ids = build_batch_prompt(SAMPLE_JOBS, SAMPLE_PROFILE)
            orders_seen.add(tuple(ordered_ids))
        # With 3 jobs and 50 attempts, we should see more than 1 order
        # (probability of all same is (1/6)^49 ≈ 0)
        assert len(orders_seen) > 1
        # All orders should contain the same IDs
        for order in orders_seen:
            assert set(order) == {"101", "102", "103"}

    def test_prompt_contains_job_metadata(self):
        prompt, _ = build_batch_prompt(SAMPLE_JOBS, SAMPLE_PROFILE)
        assert "Backend Engineer" in prompt
        assert "Acme Corp" in prompt
        assert "Build APIs" in prompt

    def test_prompt_requests_json_array(self):
        prompt, _ = build_batch_prompt(SAMPLE_JOBS, SAMPLE_PROFILE)
        assert "JSON ARRAY" in prompt
        assert "job_id" in prompt


# ---------------------------------------------------------------------------
# _extract_json_array
# ---------------------------------------------------------------------------


class TestExtractJsonArray:
    def test_plain_array(self):
        text = '[{"a": 1}, {"a": 2}]'
        result = _extract_json_array(text)
        assert result is not None
        assert len(result) == 2
        assert result[0]["a"] == 1

    def test_markdown_fenced_array(self):
        text = '```json\n[{"a": 1}]\n```'
        result = _extract_json_array(text)
        assert result is not None
        assert len(result) == 1

    def test_array_with_surrounding_text(self):
        text = 'Here are the results:\n[{"a": 1}]\nDone.'
        result = _extract_json_array(text)
        assert result is not None
        assert result[0]["a"] == 1

    def test_trailing_commas_handled(self):
        text = '[{"a": 1,}, {"a": 2,},]'
        result = _extract_json_array(text)
        assert result is not None
        assert len(result) == 2

    def test_no_array_returns_none(self):
        text = "This is not JSON at all"
        result = _extract_json_array(text)
        assert result is None

    def test_object_not_array_returns_none(self):
        text = '{"a": 1}'
        result = _extract_json_array(text)
        assert result is None


# ---------------------------------------------------------------------------
# parse_batch_response
# ---------------------------------------------------------------------------


class TestParseBatchResponse:
    def test_parses_valid_response(self):
        scores = [_make_score_dict("101", 7.5), _make_score_dict("102", 6.0)]
        content = json.dumps(scores)
        results = parse_batch_response(content, ["101", "102"])
        assert "101" in results
        assert "102" in results
        assert results["101"].fit_score == 7.5
        assert results["102"].fit_score == 6.0

    def test_positional_fallback_when_no_job_ids(self):
        """When response lacks job_id fields, uses positional mapping."""
        scores = [_make_score_dict("ignored", 7.5), _make_score_dict("ignored", 6.0)]
        # Remove job_id from each
        for s in scores:
            del s["job_id"]
        content = json.dumps(scores)
        results = parse_batch_response(content, ["101", "102"])
        assert "101" in results
        assert "102" in results
        assert results["101"].fit_score == 7.5
        assert results["102"].fit_score == 6.0

    def test_invalid_json_returns_empty(self):
        results = parse_batch_response("not json at all", ["101"])
        assert results == {}

    def test_partial_parse_skips_invalid(self):
        """Valid scores are kept, invalid ones skipped."""
        valid = _make_score_dict("101", 8.0)
        invalid = {"job_id": "102", "fit_score": "not_a_number"}
        content = json.dumps([valid, invalid])
        results = parse_batch_response(content, ["101", "102"])
        assert "101" in results
        assert "102" not in results
        assert results["101"].fit_score == 8.0


# ---------------------------------------------------------------------------
# chunk_jobs
# ---------------------------------------------------------------------------


class TestChunkJobs:
    def test_even_split(self):
        jobs = [{"id": str(i)} for i in range(10)]
        chunks = chunk_jobs(jobs, 5)
        assert len(chunks) == 2
        assert len(chunks[0]) == 5
        assert len(chunks[1]) == 5

    def test_remainder_chunk(self):
        jobs = [{"id": str(i)} for i in range(7)]
        chunks = chunk_jobs(jobs, 3)
        assert len(chunks) == 3
        assert len(chunks[0]) == 3
        assert len(chunks[1]) == 3
        assert len(chunks[2]) == 1

    def test_single_item(self):
        jobs = [{"id": "1"}]
        chunks = chunk_jobs(jobs, 10)
        assert len(chunks) == 1
        assert len(chunks[0]) == 1

    def test_empty_list(self):
        chunks = chunk_jobs([], 10)
        assert chunks == []


# ---------------------------------------------------------------------------
# batch_score_jobs (integration with mock provider)
# ---------------------------------------------------------------------------


class TestBatchScoreJobs:
    @pytest.mark.asyncio
    async def test_successful_batch_scoring(self):
        """Full batch scoring with a mocked provider returning valid array."""
        scores = [_make_score_dict("101", 7.5), _make_score_dict("102", 6.0)]
        mock_response = AIResponse(
            content=json.dumps(scores),
            provider="mock",
            feature=AIFeature.score,
            structured=None,
            model="mock-v1",
        )
        provider = AsyncMock()
        provider.complete = AsyncMock(return_value=mock_response)

        results = await batch_score_jobs(provider, SAMPLE_JOBS[:2], SAMPLE_PROFILE, batch_size=10)

        assert "101" in results
        assert "102" in results
        assert results["101"].fit_score == 7.5
        assert results["102"].fit_score == 6.0
        # Should have called complete once (all fit in one batch)
        provider.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_to_individual_on_parse_failure(self):
        """When batch parsing fails, falls back to individual scoring."""
        # Batch returns garbage
        batch_response = AIResponse(
            content="not valid json",
            provider="mock",
            feature=AIFeature.score,
            structured=None,
            model="mock-v1",
        )
        # Individual fallback returns valid score
        individual_response = AIResponse(
            content="{}",
            provider="mock",
            feature=AIFeature.score,
            structured=ScoreResult.model_validate(_make_score_dict("101")),
            model="mock-v1",
        )
        provider = AsyncMock()
        provider.complete = AsyncMock(return_value=batch_response)
        provider.score = AsyncMock(return_value=individual_response)

        results = await batch_score_jobs(provider, [SAMPLE_JOBS[0]], SAMPLE_PROFILE, batch_size=10)

        assert "101" in results
        assert results["101"].fit_score == 7.5
        # complete was called for batch, score for fallback
        provider.complete.assert_called_once()
        provider.score.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_batches(self):
        """Jobs are split across multiple batches."""
        batch1_scores = [_make_score_dict("101", 7.0)]
        batch2_scores = [_make_score_dict("102", 8.0)]

        responses = [
            AIResponse(
                content=json.dumps(batch1_scores),
                provider="mock",
                feature=AIFeature.score,
                structured=None,
                model="mock-v1",
            ),
            AIResponse(
                content=json.dumps(batch2_scores),
                provider="mock",
                feature=AIFeature.score,
                structured=None,
                model="mock-v1",
            ),
        ]
        provider = AsyncMock()
        provider.complete = AsyncMock(side_effect=responses)

        results = await batch_score_jobs(
            provider,
            SAMPLE_JOBS[:2],
            SAMPLE_PROFILE,
            batch_size=1,  # Force 1-per-batch
        )

        assert len(results) == 2
        assert provider.complete.call_count == 2

    @pytest.mark.asyncio
    async def test_empty_jobs_returns_empty(self):
        provider = AsyncMock()
        results = await batch_score_jobs(provider, [], SAMPLE_PROFILE)
        assert results == {}
        provider.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_batch_exception_triggers_fallback(self):
        """If the batch call raises, jobs go to individual fallback."""
        individual_response = AIResponse(
            content="{}",
            provider="mock",
            feature=AIFeature.score,
            structured=ScoreResult.model_validate(_make_score_dict("101")),
            model="mock-v1",
        )
        provider = AsyncMock()
        provider.complete = AsyncMock(side_effect=Exception("API error"))
        provider.score = AsyncMock(return_value=individual_response)

        results = await batch_score_jobs(provider, [SAMPLE_JOBS[0]], SAMPLE_PROFILE, batch_size=10)

        assert "101" in results
        assert results["101"].fit_score == 7.5
        provider.score.assert_called_once()

    @pytest.mark.asyncio
    async def test_configurable_batch_size_from_env(self):
        """batch_size=None reads from environment."""
        scores = [_make_score_dict("101")]
        mock_response = AIResponse(
            content=json.dumps(scores),
            provider="mock",
            feature=AIFeature.score,
            structured=None,
            model="mock-v1",
        )
        provider = AsyncMock()
        provider.complete = AsyncMock(return_value=mock_response)

        with patch.dict("os.environ", {"BATCH_SCORING_SIZE": "5"}):
            results = await batch_score_jobs(provider, [SAMPLE_JOBS[0]], SAMPLE_PROFILE)

        assert "101" in results
        assert results["101"].fit_score == 7.5
