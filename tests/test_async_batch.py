"""Tests for async batch scoring service and API routes.

Covers batch submission, status checking, result retrieval, and error
handling for both the service layer and the FastAPI endpoints.
All HTTP calls to AI providers are mocked.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from career_os.ai.base import AIProvider
from career_os.schemas.ai import AIFeature, AIResponse, ScoreResult
from career_os.services.async_batch import (
    BatchNotReadyError,
    BatchResultError,
    BatchStatus,
    BatchSubmissionError,
    check_batch_status,
    retrieve_batch_results,
    submit_batch,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_JOBS = [
    {"id": "job-1", "description": "Senior Python engineer at Acme Corp"},
    {"id": "job-2", "description": "Staff ML engineer at BigCo"},
]

SAMPLE_PROFILE_DATA = {
    "name": "Test User",
    "location": "Berlin",
    "job_family": "Software Engineering",
    "skills": [{"name": "Python", "category": "technical", "proficiency": 8}],
    "goals": [{"title": "Senior IC", "type": "career", "description": "Grow to senior"}],
}


def _make_score_result() -> ScoreResult:
    """Create a minimal valid ScoreResult for testing."""
    return ScoreResult(
        fit_score=7.5,
        reasoning="Good fit because the candidate has strong Python skills " * 3,
        estimated_salary="$150k-180k",
        effort_flag="medium",
        prep_level="moderate",
        prep_notes="Review system design",
        readiness_score=75.0,
        career_alignment=8.0,
        score_breakdown=[
            {"factor": "skills", "contribution": 2.0, "description": "Strong Python match"},
            {"factor": "seniority", "contribution": 1.5, "description": "Right level"},
            {"factor": "location", "contribution": -0.5, "description": "Remote OK"},
        ],
        dimensional_scores={
            "technical_fit": 8.0,
            "seniority_alignment": 7.5,
            "compensation_fit": 7.0,
            "location_fit": 6.5,
            "career_trajectory": 8.5,
            "company_fit": 7.0,
        },
        ats_keywords=[],
        desire_score=7.0,
        desire_reasoning="Good company culture signals",
    )


def _make_ai_response(structured: ScoreResult | None = None) -> AIResponse:
    """Create an AIResponse with optional structured ScoreResult."""
    return AIResponse(
        content='{"fit_score": 7.5}',
        provider="anthropic",
        feature=AIFeature.score,
        structured=structured,
        model="claude-sonnet-4-20250514",
    )


class FakeProvider(AIProvider):
    """Fake AI provider for testing batch operations."""

    def __init__(
        self,
        *,
        batch_id: str = "batch_abc123",
        batch_status: str = "ended",
        batch_results: dict | None = None,
        raise_on_batch_score: Exception | None = None,
        raise_on_get_results: Exception | None = None,
    ) -> None:
        self._batch_id = batch_id
        self._batch_status = batch_status
        self._batch_results = batch_results or {}
        self._raise_on_batch_score = raise_on_batch_score
        self._raise_on_get_results = raise_on_get_results

    @property
    def name(self) -> str:
        return "fake"

    async def complete(self, prompt, **kwargs):
        return _make_ai_response()

    async def score(self, job_description, profile_data, **kwargs):
        return _make_ai_response(_make_score_result())

    async def batch_score(self, jobs, profile_data, **kwargs):
        if self._raise_on_batch_score:
            raise self._raise_on_batch_score
        return self._batch_id

    async def get_batch_results(self, batch_id):
        if self._raise_on_get_results:
            raise self._raise_on_get_results
        return {"status": self._batch_status, "results": self._batch_results}


class NoSupportProvider(AIProvider):
    """Provider that does not support batch operations."""

    @property
    def name(self) -> str:
        return "nosupport"

    async def complete(self, prompt, **kwargs):
        return _make_ai_response()

    async def score(self, job_description, profile_data, **kwargs):
        return _make_ai_response()

    # Deliberately does NOT override batch_score / get_batch_results
    # so the base class NotImplementedError fires.


# ---------------------------------------------------------------------------
# Service layer tests: submit_batch
# ---------------------------------------------------------------------------


class TestSubmitBatch:
    """Tests for the submit_batch service function."""

    @pytest.mark.asyncio
    async def test_submit_batch_returns_batch_id(self):
        provider = FakeProvider(batch_id="batch_xyz789")
        batch_id = await submit_batch(provider, SAMPLE_JOBS, SAMPLE_PROFILE_DATA)
        assert batch_id == "batch_xyz789"
        assert isinstance(batch_id, str)

    @pytest.mark.asyncio
    async def test_submit_batch_empty_jobs_raises(self):
        provider = FakeProvider()
        with pytest.raises(BatchSubmissionError, match="empty batch"):
            await submit_batch(provider, [], SAMPLE_PROFILE_DATA)

    @pytest.mark.asyncio
    async def test_submit_batch_missing_id_raises(self):
        provider = FakeProvider()
        bad_jobs = [{"description": "no id here"}]
        with pytest.raises(BatchSubmissionError, match="'id' and 'description'"):
            await submit_batch(provider, bad_jobs, SAMPLE_PROFILE_DATA)

    @pytest.mark.asyncio
    async def test_submit_batch_missing_description_raises(self):
        provider = FakeProvider()
        bad_jobs = [{"id": "1"}]
        with pytest.raises(BatchSubmissionError, match="'id' and 'description'"):
            await submit_batch(provider, bad_jobs, SAMPLE_PROFILE_DATA)

    @pytest.mark.asyncio
    async def test_submit_batch_unsupported_provider(self):
        provider = NoSupportProvider()
        with pytest.raises(BatchSubmissionError, match="does not support"):
            await submit_batch(provider, SAMPLE_JOBS, SAMPLE_PROFILE_DATA)

    @pytest.mark.asyncio
    async def test_submit_batch_provider_error(self):
        provider = FakeProvider(raise_on_batch_score=RuntimeError("API down"))
        with pytest.raises(BatchSubmissionError, match="Batch submission failed"):
            await submit_batch(provider, SAMPLE_JOBS, SAMPLE_PROFILE_DATA)


# ---------------------------------------------------------------------------
# Service layer tests: check_batch_status
# ---------------------------------------------------------------------------


class TestCheckBatchStatus:
    """Tests for the check_batch_status service function."""

    @pytest.mark.asyncio
    async def test_check_status_in_progress(self):
        provider = FakeProvider(batch_status="in_progress")
        result = await check_batch_status(provider, "batch_123")
        assert result["status"] == BatchStatus.in_progress
        assert result["batch_id"] == "batch_123"
        assert result["provider"] == "fake"

    @pytest.mark.asyncio
    async def test_check_status_ended(self):
        provider = FakeProvider(batch_status="ended")
        result = await check_batch_status(provider, "batch_456")
        assert result["status"] == BatchStatus.ended
        assert result["batch_id"] == "batch_456"

    @pytest.mark.asyncio
    async def test_check_status_unknown_maps_correctly(self):
        provider = FakeProvider(batch_status="some_weird_status")
        result = await check_batch_status(provider, "batch_789")
        assert result["status"] == BatchStatus.unknown
        assert result["provider"] == "fake"

    @pytest.mark.asyncio
    async def test_check_status_unsupported_provider(self):
        provider = NoSupportProvider()
        with pytest.raises(BatchResultError, match="does not support"):
            await check_batch_status(provider, "batch_123")

    @pytest.mark.asyncio
    async def test_check_status_provider_error(self):
        provider = FakeProvider(raise_on_get_results=RuntimeError("Network error"))
        with pytest.raises(BatchResultError, match="Batch status check failed"):
            await check_batch_status(provider, "batch_123")


# ---------------------------------------------------------------------------
# Service layer tests: retrieve_batch_results
# ---------------------------------------------------------------------------


class TestRetrieveBatchResults:
    """Tests for the retrieve_batch_results service function."""

    @pytest.mark.asyncio
    async def test_retrieve_results_success(self):
        score = _make_score_result()
        ai_resp = _make_ai_response(structured=score)
        provider = FakeProvider(
            batch_status="ended",
            batch_results={"job-1": ai_resp, "job-2": ai_resp},
        )
        results = await retrieve_batch_results(provider, "batch_done")
        assert len(results) == 2
        assert results[0]["job_id"] in ("job-1", "job-2")
        assert results[0]["score_result"].fit_score == 7.5
        assert results[0]["error"] is None

    @pytest.mark.asyncio
    async def test_retrieve_results_not_ready(self):
        provider = FakeProvider(batch_status="in_progress")
        with pytest.raises(BatchNotReadyError, match="not ready"):
            await retrieve_batch_results(provider, "batch_pending")

    @pytest.mark.asyncio
    async def test_retrieve_results_with_none_response(self):
        provider = FakeProvider(
            batch_status="ended",
            batch_results={"job-1": None},
        )
        results = await retrieve_batch_results(provider, "batch_partial")
        assert len(results) == 1
        assert results[0]["score_result"] is None
        assert results[0]["error"] == "No response from provider"

    @pytest.mark.asyncio
    async def test_retrieve_results_unstructured_response(self):
        ai_resp = _make_ai_response(structured=None)
        provider = FakeProvider(
            batch_status="ended",
            batch_results={"job-1": ai_resp},
        )
        results = await retrieve_batch_results(provider, "batch_unstructured")
        assert len(results) == 1
        assert results[0]["score_result"] is None
        assert results[0]["error"] == "Provider returned unstructured response"

    @pytest.mark.asyncio
    async def test_retrieve_results_unsupported_provider(self):
        provider = NoSupportProvider()
        with pytest.raises(BatchResultError, match="does not support"):
            await retrieve_batch_results(provider, "batch_123")

    @pytest.mark.asyncio
    async def test_retrieve_results_provider_error(self):
        provider = FakeProvider(raise_on_get_results=RuntimeError("Fetch failed"))
        with pytest.raises(BatchResultError, match="retrieval failed"):
            await retrieve_batch_results(provider, "batch_123")


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


from career_os.main import app  # noqa: E402


class TestBatchSubmitEndpoint:
    """Tests for POST /api/score/batch/submit."""

    def test_submit_success(self, db_session, profile):
        """Successful batch submission returns 202 with batch_id."""
        client = TestClient(app)

        with patch(
            "career_os.api.batch.get_ai_provider",
            return_value=FakeProvider(batch_id="batch_api_123"),
        ):
            resp = client.post(
                "/api/score/batch/submit",
                json={
                    "profile_id": profile.id,
                    "jobs": [
                        {"id": "j1", "description": "Python dev at StartupCo"},
                        {"id": "j2", "description": "Backend eng at BigCorp"},
                    ],
                },
            )

        assert resp.status_code == 202
        data = resp.json()
        assert data["batch_id"] == "batch_api_123"
        assert data["provider"] == "fake"
        assert data["job_count"] == 2

    def test_submit_profile_not_found(self, db_session):
        """Non-existent profile returns 404."""
        client = TestClient(app)

        with patch(
            "career_os.api.batch.get_ai_provider",
            return_value=FakeProvider(),
        ):
            resp = client.post(
                "/api/score/batch/submit",
                json={
                    "profile_id": 99999,
                    "jobs": [{"id": "j1", "description": "Some job"}],
                },
            )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_submit_empty_jobs_rejected(self, db_session, profile):
        """Empty jobs list is rejected by Pydantic validation (422)."""
        client = TestClient(app)
        resp = client.post(
            "/api/score/batch/submit",
            json={"profile_id": profile.id, "jobs": []},
        )
        assert resp.status_code == 422

    def test_submit_provider_failure(self, db_session, profile):
        """Provider batch submission failure returns 502."""
        client = TestClient(app)

        failing_provider = FakeProvider(
            raise_on_batch_score=RuntimeError("Provider exploded"),
        )
        with patch(
            "career_os.api.batch.get_ai_provider",
            return_value=failing_provider,
        ):
            resp = client.post(
                "/api/score/batch/submit",
                json={
                    "profile_id": profile.id,
                    "jobs": [{"id": "j1", "description": "Some job"}],
                },
            )

        assert resp.status_code == 502
        assert "failed" in resp.json()["detail"].lower()


class TestBatchStatusEndpoint:
    """Tests for GET /api/score/batch/{batch_id}/status."""

    def test_status_in_progress(self):
        client = TestClient(app)

        with patch(
            "career_os.api.batch.get_ai_provider",
            return_value=FakeProvider(batch_status="in_progress"),
        ):
            resp = client.get(
                "/api/score/batch/batch_123/status",
                params={"provider": "anthropic"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["batch_id"] == "batch_123"
        assert data["status"] == "in_progress"

    def test_status_ended(self):
        client = TestClient(app)

        with patch(
            "career_os.api.batch.get_ai_provider",
            return_value=FakeProvider(batch_status="ended"),
        ):
            resp = client.get("/api/score/batch/batch_456/status")

        assert resp.status_code == 200
        assert resp.json()["status"] == "ended"

    def test_status_provider_error(self):
        client = TestClient(app)

        with patch(
            "career_os.api.batch.get_ai_provider",
            return_value=FakeProvider(raise_on_get_results=RuntimeError("boom")),
        ):
            resp = client.get("/api/score/batch/batch_789/status")

        assert resp.status_code == 502
        assert "failed" in resp.json()["detail"].lower()


class TestBatchResultsEndpoint:
    """Tests for GET /api/score/batch/{batch_id}/results."""

    def test_results_success(self):
        client = TestClient(app)
        score = _make_score_result()
        ai_resp = _make_ai_response(structured=score)

        with patch(
            "career_os.api.batch.get_ai_provider",
            return_value=FakeProvider(
                batch_status="ended",
                batch_results={"job-1": ai_resp},
            ),
        ):
            resp = client.get("/api/score/batch/batch_done/results")

        assert resp.status_code == 200
        data = resp.json()
        assert data["batch_id"] == "batch_done"
        assert data["total"] == 1
        assert data["successful"] == 1
        assert data["failed"] == 0
        assert data["results"][0]["job_id"] == "job-1"
        assert data["results"][0]["score_result"]["fit_score"] == 7.5

    def test_results_not_ready_returns_202(self):
        client = TestClient(app)

        with patch(
            "career_os.api.batch.get_ai_provider",
            return_value=FakeProvider(batch_status="in_progress"),
        ):
            resp = client.get("/api/score/batch/batch_pending/results")

        assert resp.status_code == 202
        assert "still processing" in resp.json()["detail"].lower()

    def test_results_with_errors(self):
        client = TestClient(app)
        ai_resp_no_structured = _make_ai_response(structured=None)

        with patch(
            "career_os.api.batch.get_ai_provider",
            return_value=FakeProvider(
                batch_status="ended",
                batch_results={"job-1": ai_resp_no_structured},
            ),
        ):
            resp = client.get("/api/score/batch/batch_errors/results")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["successful"] == 0
        assert data["failed"] == 1
        assert data["results"][0]["error"] is not None

    def test_results_provider_error(self):
        client = TestClient(app)

        with patch(
            "career_os.api.batch.get_ai_provider",
            return_value=FakeProvider(raise_on_get_results=RuntimeError("boom")),
        ):
            resp = client.get("/api/score/batch/batch_err/results")

        assert resp.status_code == 502


# ---------------------------------------------------------------------------
# BatchStatus enum tests
# ---------------------------------------------------------------------------


class TestBatchStatusEnum:
    """Tests for BatchStatus enum values."""

    def test_batch_status_values(self):
        assert BatchStatus.in_progress == "in_progress"
        assert BatchStatus.ended == "ended"
        assert BatchStatus.canceled == "canceled"
        assert BatchStatus.failed == "failed"
        assert BatchStatus.expired == "expired"
        assert BatchStatus.unknown == "unknown"

    def test_batch_status_from_string(self):
        status = BatchStatus("ended")
        assert status == BatchStatus.ended
        assert status.value == "ended"
