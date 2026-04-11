"""Tests for `career_os.api.intelligence` — role & industry intelligence endpoints.

Patches the `services.role_intelligence` functions referenced from the API
module so the HTTP layer can be tested without hitting the AI provider or
real DB-backed market intelligence.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from career_os.models.models import Profile
from career_os.schemas.role_intelligence import (
    AssessmentCriterion,
    InterviewFormatResponse,
    InterviewPatternsResponse,
    InterviewRound,
    QuestionCategory,
    SalaryBenchmark,
    SalaryBenchmarkResponse,
)
from career_os.services.role_intelligence import ProfileNotFoundError


@pytest.fixture(autouse=True)
def _seed_profile(db_session):
    db_session.add(Profile(id=1, name="P", email="p@p.com"))
    db_session.commit()
    return db_session


# ---------------------------------------------------------------------------
# /api/intelligence/interview-format
# ---------------------------------------------------------------------------


def test_interview_format_happy_path(client: TestClient):
    fake = InterviewFormatResponse(
        company="Acme",
        rounds=[
            InterviewRound(
                round_number=1,
                type="Phone Screen",
                description="Recruiter call",
                duration_minutes=30,
            )
        ],
        total_duration="2 weeks",
        process_description="Standard 3-stage loop",
    )
    with patch(
        "career_os.api.intelligence.get_interview_format",
        new=AsyncMock(return_value=fake),
    ) as svc:
        resp = client.get(
            "/api/intelligence/interview-format",
            params={"company": "Acme", "profile_id": 1, "role": "TPM"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["company"] == "Acme"
    assert body["rounds"][0]["type"] == "Phone Screen"
    svc.assert_awaited_once()
    kwargs = svc.await_args.kwargs
    assert kwargs["company"] == "Acme"
    assert kwargs["role"] == "TPM"
    assert kwargs["profile_id"] == 1


def test_interview_format_missing_required_query(client: TestClient):
    resp = client.get(
        "/api/intelligence/interview-format",
        params={"profile_id": 1},  # missing 'company'
    )
    assert resp.status_code == 422


def test_interview_format_profile_not_found(client: TestClient):
    with patch(
        "career_os.api.intelligence.get_interview_format",
        new=AsyncMock(side_effect=ProfileNotFoundError("nope")),
    ):
        resp = client.get(
            "/api/intelligence/interview-format",
            params={"company": "Acme", "profile_id": 999},
        )
    assert resp.status_code == 404


def test_interview_format_unexpected_error_500(client: TestClient):
    with patch(
        "career_os.api.intelligence.get_interview_format",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        resp = client.get(
            "/api/intelligence/interview-format",
            params={"company": "Acme", "profile_id": 1},
        )
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# /api/intelligence/salary
# ---------------------------------------------------------------------------


def test_salary_benchmark_happy_path(client: TestClient):
    fake = SalaryBenchmarkResponse(
        role="TPM",
        location="Berlin",
        company_stage="growth",
        benchmarks=SalaryBenchmark(low=80000, median=110000, high=140000, sample_size=42),
    )
    with patch(
        "career_os.api.intelligence.get_salary_benchmarks",
        return_value=fake,
    ) as svc:
        resp = client.get(
            "/api/intelligence/salary",
            params={
                "role": "TPM",
                "profile_id": 1,
                "location": "Berlin",
                "company_stage": "growth",
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["benchmarks"]["median"] == 110000
    svc.assert_called_once()
    assert svc.call_args.kwargs["location"] == "Berlin"
    assert svc.call_args.kwargs["company_stage"] == "growth"


def test_salary_benchmark_profile_not_found(client: TestClient):
    with patch(
        "career_os.api.intelligence.get_salary_benchmarks",
        side_effect=ProfileNotFoundError("nope"),
    ):
        resp = client.get(
            "/api/intelligence/salary",
            params={"role": "TPM", "profile_id": 999},
        )
    assert resp.status_code == 404


def test_salary_benchmark_missing_required_query(client: TestClient):
    resp = client.get("/api/intelligence/salary", params={"profile_id": 1})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# /api/intelligence/patterns
# ---------------------------------------------------------------------------


def test_interview_patterns_happy_path(client: TestClient):
    fake = InterviewPatternsResponse(
        role="TPM",
        question_categories=[
            QuestionCategory(
                name="Behavioral",
                description="Past behavior",
                example_questions=["Tell me about a conflict"],
            )
        ],
        assessment_criteria=[AssessmentCriterion(name="Communication", description="Clarity")],
        frequently_tested_skills=["Roadmapping"],
    )
    with patch(
        "career_os.api.intelligence.get_interview_patterns",
        new=AsyncMock(return_value=fake),
    ) as svc:
        resp = client.get(
            "/api/intelligence/patterns",
            params={"role": "TPM", "profile_id": 1},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "TPM"
    assert body["question_categories"][0]["name"] == "Behavioral"
    svc.assert_awaited_once()


def test_interview_patterns_profile_not_found(client: TestClient):
    with patch(
        "career_os.api.intelligence.get_interview_patterns",
        new=AsyncMock(side_effect=ProfileNotFoundError("nope")),
    ):
        resp = client.get(
            "/api/intelligence/patterns",
            params={"role": "TPM", "profile_id": 999},
        )
    assert resp.status_code == 404


def test_interview_patterns_unexpected_error_500(client: TestClient):
    with patch(
        "career_os.api.intelligence.get_interview_patterns",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        resp = client.get(
            "/api/intelligence/patterns",
            params={"role": "TPM", "profile_id": 1},
        )
    assert resp.status_code == 500
