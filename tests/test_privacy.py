"""Tests for the privacy metadata framework."""

import pytest
from fastapi.testclient import TestClient

from career_os.ai.privacy import PROVIDER_PRIVACY_REGISTRY, get_privacy_info
from career_os.main import app
from career_os.schemas.privacy import (
    DataRetention,
    PrivacyTier,
    ProviderPrivacyInfo,
)


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestPrivacyTierEnum:
    """PrivacyTier enum covers expected values."""

    def test_all_tiers_present(self) -> None:
        assert set(PrivacyTier) == {
            PrivacyTier.local,
            PrivacyTier.green,
            PrivacyTier.yellow,
            PrivacyTier.red,
        }

    @pytest.mark.parametrize(
        "tier,expected",
        [
            (PrivacyTier.local, "local"),
            (PrivacyTier.green, "green"),
            (PrivacyTier.yellow, "yellow"),
            (PrivacyTier.red, "red"),
        ],
    )
    def test_tier_string_values(self, tier: PrivacyTier, expected: str) -> None:
        assert tier.value == expected
        assert str(tier) == expected


class TestProviderPrivacyInfoValidation:
    """Pydantic model validation for ProviderPrivacyInfo."""

    def test_minimal_valid_model(self) -> None:
        info = ProviderPrivacyInfo(
            provider="test",
            tier=PrivacyTier.green,
            retention=DataRetention(description="No retention"),
        )
        assert info.provider == "test"
        assert info.tier == PrivacyTier.green
        assert info.trains_on_data is False
        assert info.human_review is False
        assert info.dpa_available is False
        assert info.gdpr_compliant is True
        assert info.eu_banned is False
        assert info.warnings == []
        assert info.recommendation == ""

    def test_full_model(self) -> None:
        info = ProviderPrivacyInfo(
            provider="risky",
            tier=PrivacyTier.red,
            trains_on_data=True,
            human_review=True,
            retention=DataRetention(days=365, description="1 year"),
            dpa_available=False,
            gdpr_compliant=False,
            eu_banned=True,
            warnings=["Do not use"],
            recommendation="Avoid",
        )
        assert info.trains_on_data is True
        assert info.eu_banned is True
        assert info.retention.days == 365

    def test_retention_none_days(self) -> None:
        ret = DataRetention(days=None, description="Indefinite")
        assert ret.days is None


# ---------------------------------------------------------------------------
# Registry / get_privacy_info tests
# ---------------------------------------------------------------------------


class TestGetPrivacyInfo:
    """get_privacy_info lookups against the hardcoded registry."""

    def test_known_provider_mock(self) -> None:
        info = get_privacy_info("mock")
        assert info is not None
        assert info.tier == PrivacyTier.local
        assert info.trains_on_data is False

    def test_known_provider_anthropic(self) -> None:
        info = get_privacy_info("anthropic")
        assert info is not None
        assert info.tier == PrivacyTier.green
        assert info.dpa_available is True
        assert info.retention.days == 7

    def test_known_provider_openrouter(self) -> None:
        info = get_privacy_info("openrouter")
        assert info is not None
        assert info.tier == PrivacyTier.yellow
        assert len(info.warnings) > 0

    def test_known_provider_ollama(self) -> None:
        info = get_privacy_info("ollama")
        assert info is not None
        assert info.tier == PrivacyTier.local

    def test_unknown_provider_returns_none(self) -> None:
        assert get_privacy_info("nonexistent_provider") is None

    def test_case_insensitive_lookup(self) -> None:
        assert get_privacy_info("Anthropic") is not None
        assert get_privacy_info("MOCK") is not None

    def test_registry_has_expected_providers(self) -> None:
        expected = {"mock", "ollama", "openrouter", "anthropic", "gemini", "mistral", "groq"}
        assert expected == set(PROVIDER_PRIVACY_REGISTRY.keys())


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestPrivacyAPI:
    """HTTP tests for /api/ai/privacy endpoints."""

    def test_list_all_providers(self, client: TestClient) -> None:
        resp = client.get("/api/ai/privacy")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == len(PROVIDER_PRIVACY_REGISTRY)
        providers = {item["provider"] for item in data}
        assert "anthropic" in providers
        assert "mock" in providers

    def test_get_single_provider(self, client: TestClient) -> None:
        resp = client.get("/api/ai/privacy/anthropic")
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "anthropic"
        assert data["tier"] == "green"
        assert data["retention"]["days"] == 7

    def test_get_unknown_provider_404(self, client: TestClient) -> None:
        resp = client.get("/api/ai/privacy/does_not_exist")
        assert resp.status_code == 404
        assert "Unknown provider" in resp.json()["detail"]

    def test_response_schema_shape(self, client: TestClient) -> None:
        """Verify all expected fields are present in each item."""
        resp = client.get("/api/ai/privacy")
        assert resp.status_code == 200
        for item in resp.json():
            assert "provider" in item
            assert "tier" in item
            assert "trains_on_data" in item
            assert "retention" in item
            assert "gdpr_compliant" in item
            assert "warnings" in item
