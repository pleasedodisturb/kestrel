"""Tests for `career_os.api.research` — POST /api/research/company.

Patches the underlying `research_company` service so the HTTP layer is
exercised in isolation. Covers the happy path, the simulate_partial flag,
and each documented error mapping.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from career_os.models.models import Profile
from career_os.schemas.research import (
    CompanyResearchReport,
    ValuesAlignmentReport,
)
from career_os.services.company_research import (
    ProfileNotFoundError,
    ResearchError,
)


@pytest.fixture(autouse=True)
def _seed_profile(db_session):
    db_session.add(Profile(id=1, name="P", email="p@p.com"))
    db_session.commit()
    return db_session


def _build_report(name: str = "Acme") -> CompanyResearchReport:
    return CompanyResearchReport(
        company_name=name,
        values_alignment=ValuesAlignmentReport(score=7.5, rationale="Strong builder culture"),
    )


def test_research_company_happy_path(client: TestClient):
    fake = _build_report("Mistral")
    with patch(
        "career_os.api.research.research_company",
        new=AsyncMock(return_value=fake),
    ) as research:
        resp = client.post(
            "/api/research/company",
            json={"company_name": "Mistral", "profile_id": 1},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["company_name"] == "Mistral"
    assert body["values_alignment"]["score"] == pytest.approx(7.5)
    research.assert_awaited_once()
    kwargs = research.await_args.kwargs
    assert kwargs["company_name"] == "Mistral"
    assert kwargs["profile_id"] == 1
    assert kwargs["simulate_partial"] is False


def test_research_company_simulate_partial_query_param(client: TestClient):
    fake = _build_report("Obscure Co")
    with patch(
        "career_os.api.research.research_company",
        new=AsyncMock(return_value=fake),
    ) as research:
        resp = client.post(
            "/api/research/company?simulate_partial=true",
            json={"company_name": "Obscure Co", "profile_id": 1},
        )

    assert resp.status_code == 200
    assert research.await_args.kwargs["simulate_partial"] is True


def test_research_company_profile_not_found_returns_404(client: TestClient):
    with patch(
        "career_os.api.research.research_company",
        new=AsyncMock(side_effect=ProfileNotFoundError("Profile 99 not found")),
    ):
        resp = client.post(
            "/api/research/company",
            json={"company_name": "Acme", "profile_id": 99},
        )
    assert resp.status_code == 404
    assert "Profile 99" in resp.json()["detail"]


def test_research_company_research_error_returns_502(client: TestClient):
    with patch(
        "career_os.api.research.research_company",
        new=AsyncMock(side_effect=ResearchError("upstream gone")),
    ):
        resp = client.post(
            "/api/research/company",
            json={"company_name": "Acme", "profile_id": 1},
        )
    assert resp.status_code == 502
    assert "upstream gone" in resp.json()["detail"]


def test_research_company_unexpected_error_returns_500(client: TestClient):
    with patch(
        "career_os.api.research.research_company",
        new=AsyncMock(side_effect=RuntimeError("kaboom")),
    ):
        resp = client.post(
            "/api/research/company",
            json={"company_name": "Acme", "profile_id": 1},
        )
    assert resp.status_code == 500
    assert "kaboom" in resp.json()["detail"]


def test_research_company_validation_error_on_missing_field(client: TestClient):
    """Missing company_name is a 422 from Pydantic."""
    resp = client.post(
        "/api/research/company",
        json={"profile_id": 1},
    )
    assert resp.status_code == 422
