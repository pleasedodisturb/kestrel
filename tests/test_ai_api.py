"""Tests for `career_os.api.ai` — POST /api/ai/complete and GET /api/ai/provider.

Complementary to `tests/test_ai_health.py` (which only covers /health).
The mock provider is selected via `AI_PROVIDER=mock` so no real network
traffic occurs. Error mappings are exercised by patching `get_ai_provider`.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from career_os.ai.factory import UnsupportedProviderError
from career_os.schemas.ai import AIResponse


@pytest.fixture(autouse=True)
def _auto_db(db_session):
    return db_session


# ---------------------------------------------------------------------------
# POST /api/ai/complete
# ---------------------------------------------------------------------------


def test_ai_complete_happy_path_with_mock_provider(client: TestClient):
    with patch.dict(os.environ, {"AI_PROVIDER": "mock"}):
        resp = client.post(
            "/api/ai/complete",
            json={"prompt": "Hello world"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "mock"
    assert "content" in body
    assert isinstance(body["content"], str)


def test_ai_complete_validation_error_on_empty_prompt(client: TestClient):
    """Pydantic enforces min_length=1 on the prompt field."""
    resp = client.post("/api/ai/complete", json={"prompt": ""})
    assert resp.status_code == 422


def test_ai_complete_missing_prompt_returns_422(client: TestClient):
    resp = client.post("/api/ai/complete", json={})
    assert resp.status_code == 422


def test_ai_complete_unsupported_provider_returns_422(client: TestClient):
    with patch(
        "career_os.api.ai.get_ai_provider",
        side_effect=UnsupportedProviderError("nonsense"),
    ):
        resp = client.post(
            "/api/ai/complete",
            json={"prompt": "Hi"},
        )
    assert resp.status_code == 422
    assert "configuration error" in resp.json()["detail"].lower()


def test_ai_complete_value_error_returns_422(client: TestClient):
    """A ValueError from get_ai_provider also maps to 422."""
    with patch(
        "career_os.api.ai.get_ai_provider",
        side_effect=ValueError("missing API key"),
    ):
        resp = client.post(
            "/api/ai/complete",
            json={"prompt": "Hi"},
        )
    assert resp.status_code == 422
    assert "missing API key" in resp.json()["detail"]


def test_ai_complete_value_error_during_complete_returns_422(client: TestClient):
    """ValueError raised by provider.complete() also maps to 422."""
    fake_provider = MagicMock()
    fake_provider.complete = AsyncMock(side_effect=ValueError("bad config"))
    with patch("career_os.api.ai.get_ai_provider", return_value=fake_provider):
        resp = client.post(
            "/api/ai/complete",
            json={"prompt": "Hi"},
        )
    assert resp.status_code == 422


def test_ai_complete_provider_runtime_error_returns_502(client: TestClient):
    """A non-ValueError exception during complete() maps to 502."""
    fake_provider = MagicMock()
    fake_provider.complete = AsyncMock(side_effect=RuntimeError("upstream down"))
    with patch("career_os.api.ai.get_ai_provider", return_value=fake_provider):
        resp = client.post(
            "/api/ai/complete",
            json={"prompt": "Hi"},
        )
    assert resp.status_code == 502
    assert "upstream down" in resp.json()["detail"]


def test_ai_complete_passes_feature_and_context(client: TestClient):
    """Custom feature and context kwargs are forwarded to the provider."""
    fake_provider = MagicMock()
    fake_provider.complete = AsyncMock(
        return_value=AIResponse(
            content="ok",
            provider="mock",
            feature="coaching",
        )
    )
    with patch("career_os.api.ai.get_ai_provider", return_value=fake_provider):
        resp = client.post(
            "/api/ai/complete",
            json={
                "prompt": "Hi",
                "feature": "coaching",
                "context": {"profile_id": 1},
            },
        )
    assert resp.status_code == 200
    fake_provider.complete.assert_awaited_once()
    kwargs = fake_provider.complete.await_args.kwargs
    assert kwargs["prompt"] == "Hi"
    assert kwargs["feature"] == "coaching"
    assert kwargs["context"] == {"profile_id": 1}


# ---------------------------------------------------------------------------
# GET /api/ai/provider
# ---------------------------------------------------------------------------


def test_get_provider_happy_path(client: TestClient):
    with patch.dict(os.environ, {"AI_PROVIDER": "mock"}):
        resp = client.get("/api/ai/provider")
    assert resp.status_code == 200
    assert resp.json() == {"provider": "mock"}


def test_get_provider_unsupported_returns_422(client: TestClient):
    with patch(
        "career_os.api.ai.get_ai_provider",
        side_effect=UnsupportedProviderError("nope"),
    ):
        resp = client.get("/api/ai/provider")
    assert resp.status_code == 422


def test_get_provider_value_error_returns_422(client: TestClient):
    with patch(
        "career_os.api.ai.get_ai_provider",
        side_effect=ValueError("bad config"),
    ):
        resp = client.get("/api/ai/provider")
    assert resp.status_code == 422
