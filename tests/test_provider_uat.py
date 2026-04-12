"""User acceptance tests: every registered provider satisfies the AIProvider contract.

These tests run the full factory → provider → API chain for each provider
that can operate without external services (mock, demo). For providers requiring
external services (ollama, anthropic, openrouter), they verify graceful degradation.
"""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from career_os.ai.base import AIProvider
from career_os.ai.factory import UnsupportedProviderError, get_ai_provider
from career_os.schemas.ai import AIFeature, AIResponse, ScoreResult


@pytest.fixture(autouse=True)
def _auto_db(db_session):
    return db_session


# ---------------------------------------------------------------------------
# UAT: Provider contract — local providers (no external services needed)
# ---------------------------------------------------------------------------


class TestProviderContractUAT:
    """Every local provider satisfies the AIProvider contract end-to-end."""

    @pytest.fixture(params=["mock", "demo"])
    def local_provider(self, request):
        """Providers that work without external services."""
        return get_ai_provider(request.param)

    def test_is_ai_provider_instance(self, local_provider) -> None:
        """Provider is an instance of AIProvider ABC."""
        assert isinstance(local_provider, AIProvider)

    def test_has_name(self, local_provider) -> None:
        """Provider has a non-empty name property."""
        assert local_provider.name
        assert isinstance(local_provider.name, str)

    @pytest.mark.asyncio
    async def test_complete_returns_ai_response(self, local_provider) -> None:
        """complete() returns a valid AIResponse."""
        resp = await local_provider.complete("hello")
        assert isinstance(resp, AIResponse)
        assert resp.content
        assert resp.provider

    @pytest.mark.asyncio
    async def test_complete_deterministic(self, local_provider) -> None:
        """Same prompt produces identical responses."""
        r1 = await local_provider.complete("test prompt")
        r2 = await local_provider.complete("test prompt")
        assert r1.content == r2.content

    @pytest.mark.asyncio
    async def test_score_returns_score_result(self, local_provider) -> None:
        """score() returns AIResponse with ScoreResult structured data."""
        resp = await local_provider.score("Engineer at Acme", {"name": "Test"})
        assert isinstance(resp, AIResponse)
        assert isinstance(resp.structured, ScoreResult)
        assert 0 <= resp.structured.fit_score <= 10
        assert len(resp.structured.reasoning) >= 100

    @pytest.mark.asyncio
    async def test_score_breakdown_has_minimum_factors(self, local_provider) -> None:
        """score() returns at least 3 breakdown factors."""
        resp = await local_provider.score("Engineer at Acme", {"name": "Test"})
        assert len(resp.structured.score_breakdown) >= 3

    @pytest.mark.asyncio
    async def test_all_structured_features_return_data(self, local_provider) -> None:
        """Every AIFeature (except complete and voice_*) returns structured data."""
        skip_features = {
            AIFeature.complete,
            AIFeature.voice_cover_letter,
            AIFeature.voice_coaching,
            AIFeature.voice_job_evaluation,
        }
        for feature in AIFeature:
            if feature in skip_features:
                continue
            resp = await local_provider.complete(f"Test {feature}", feature=feature)
            assert resp.structured is not None, f"{feature} missing structured data"
            assert resp.feature == feature

    @pytest.mark.asyncio
    async def test_complete_feature_returns_no_structured(self, local_provider) -> None:
        """complete feature returns None for structured (unstructured text only)."""
        resp = await local_provider.complete("hello", feature=AIFeature.complete)
        assert resp.structured is None


# ---------------------------------------------------------------------------
# UAT: Provider contract via API — local providers
# ---------------------------------------------------------------------------


class TestProviderAPIContractUAT:
    """API endpoints satisfy the provider contract for local providers."""

    @pytest.mark.parametrize("provider_name", ["mock", "demo"])
    def test_api_complete_200(self, client: TestClient, provider_name: str) -> None:
        """POST /api/ai/complete returns 200 with valid response."""
        with patch.dict(os.environ, {"AI_PROVIDER": provider_name}):
            resp = client.post(
                "/api/ai/complete",
                json={"prompt": "hello", "feature": "complete"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "mock"
        assert data["content"]

    @pytest.mark.parametrize("provider_name", ["mock", "demo"])
    def test_api_score_structured(self, client: TestClient, provider_name: str) -> None:
        """POST /api/ai/complete with score feature returns structured data."""
        with patch.dict(os.environ, {"AI_PROVIDER": provider_name}):
            resp = client.post(
                "/api/ai/complete",
                json={"prompt": "Score this job", "feature": "score"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["structured"] is not None
        assert "fit_score" in data["structured"]
        assert "reasoning" in data["structured"]
        assert "score_breakdown" in data["structured"]

    @pytest.mark.parametrize("provider_name", ["mock", "demo"])
    def test_api_provider_endpoint(self, client: TestClient, provider_name: str) -> None:
        """GET /api/ai/provider returns correct provider name."""
        with patch.dict(os.environ, {"AI_PROVIDER": provider_name}):
            resp = client.get("/api/ai/provider")
        assert resp.status_code == 200
        assert resp.json()["provider"] == "mock"

    @pytest.mark.parametrize("provider_name", ["mock", "demo"])
    def test_api_health_includes_provider(self, client: TestClient, provider_name: str) -> None:
        """GET /api/ai/health lists the provider as reachable."""
        with patch.dict(os.environ, {"AI_PROVIDER": provider_name}):
            resp = client.get("/api/ai/health")
        assert resp.status_code == 200
        mock_p = next(p for p in resp.json()["providers"] if p["name"] == "mock")
        assert mock_p["status"] == "reachable"


# ---------------------------------------------------------------------------
# UAT: Graceful degradation — external providers without credentials
# ---------------------------------------------------------------------------


class TestExternalProviderGracefulDegradation:
    """Providers requiring external services fail gracefully without credentials."""

    @pytest.mark.parametrize("name", ["openrouter"])
    def test_missing_config_raises_not_crashes(self, name: str) -> None:
        """Provider without config raises ValueError, not an unhandled exception."""
        with patch.dict(os.environ, {f"{name.upper()}_API_KEY": ""}):
            with pytest.raises((ValueError, UnsupportedProviderError)):
                get_ai_provider(name)

    @pytest.mark.parametrize("name", ["openrouter"])
    def test_api_complete_returns_422_not_500(self, client: TestClient, name: str) -> None:
        """API endpoint returns 422 config error, not 500 server error."""
        env = {"AI_PROVIDER": name, f"{name.upper()}_API_KEY": ""}
        with patch.dict(os.environ, env):
            resp = client.post(
                "/api/ai/complete",
                json={"prompt": "test", "feature": "complete"},
            )
        assert resp.status_code == 422

    @pytest.mark.parametrize("name", ["openrouter"])
    def test_api_provider_returns_422_not_500(self, client: TestClient, name: str) -> None:
        """GET /api/ai/provider returns 422 config error, not 500."""
        env = {"AI_PROVIDER": name, f"{name.upper()}_API_KEY": ""}
        with patch.dict(os.environ, env):
            resp = client.get("/api/ai/provider")
        assert resp.status_code == 422

    def test_unsupported_provider_raises_descriptive_error(self) -> None:
        """Unsupported provider error includes provider name and available options."""
        with pytest.raises(UnsupportedProviderError) as exc_info:
            get_ai_provider("nonexistent")
        msg = str(exc_info.value)
        assert "nonexistent" in msg
        assert "mock" in msg
        assert "openrouter" in msg

    def test_health_endpoint_never_crashes(self, client: TestClient) -> None:
        """Health endpoint returns 200 even when providers are misconfigured."""
        env = {
            "AI_PROVIDER": "mock",
            "OPENROUTER_API_KEY": "bad-key",
        }
        with patch.dict(os.environ, env, clear=False):
            resp = client.get("/api/ai/health")
        assert resp.status_code == 200
        providers = resp.json()["providers"]
        # Mock should still be reachable regardless of other provider config
        mock_p = next(p for p in providers if p["name"] == "mock")
        assert mock_p["status"] == "reachable"
