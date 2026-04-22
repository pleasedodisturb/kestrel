"""Tests for PII safety boundary enforcement.

Covers:
- DataSensitivity enum values
- FEATURE_SENSITIVITY classification (public vs personal)
- ZDR_SAFE_PROVIDERS set
- check_privacy_boundary: public features pass for any provider
- check_privacy_boundary: personal features pass for ZDR-safe providers
- check_privacy_boundary: personal features raise PrivacyError for non-ZDR providers
- PrivacyError message is user-friendly and actionable
- API returns 422 (not 500) when PrivacyError is raised from a service
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from career_os.ai.privacy import (
    FEATURE_SENSITIVITY,
    ZDR_SAFE_PROVIDERS,
    DataSensitivity,
    PrivacyError,
    check_privacy_boundary,
)

# ---------------------------------------------------------------------------
# Unit tests — DataSensitivity enum
# ---------------------------------------------------------------------------


def test_data_sensitivity_values():
    """DataSensitivity has PUBLIC and PERSONAL values."""
    assert DataSensitivity.PUBLIC == "public"
    assert DataSensitivity.PERSONAL == "personal"


# ---------------------------------------------------------------------------
# Unit tests — FEATURE_SENSITIVITY mapping
# ---------------------------------------------------------------------------


def test_scoring_is_public():
    """Scoring is classified as public — safe with any provider."""
    assert FEATURE_SENSITIVITY["score"] == DataSensitivity.PUBLIC


def test_gap_analysis_is_public():
    """Gap analysis is classified as public."""
    assert FEATURE_SENSITIVITY["gap_analysis"] == DataSensitivity.PUBLIC


def test_company_research_is_public():
    """Company research is classified as public."""
    assert FEATURE_SENSITIVITY["company_research"] == DataSensitivity.PUBLIC


def test_voice_cover_letter_is_personal():
    """Voice cover letter feature is classified as personal."""
    assert FEATURE_SENSITIVITY["voice_cover_letter"] == DataSensitivity.PERSONAL


def test_voice_coaching_is_personal():
    """Voice coaching feature is classified as personal."""
    assert FEATURE_SENSITIVITY["voice_coaching"] == DataSensitivity.PERSONAL


def test_interview_prep_is_personal():
    """Interview prep feature is classified as personal."""
    assert FEATURE_SENSITIVITY["interview_prep"] == DataSensitivity.PERSONAL


def test_star_stories_is_personal():
    """STAR stories feature is classified as personal."""
    assert FEATURE_SENSITIVITY["star_stories"] == DataSensitivity.PERSONAL


def test_coaching_is_personal():
    """Coaching feature is classified as personal."""
    assert FEATURE_SENSITIVITY["coaching"] == DataSensitivity.PERSONAL


def test_unknown_feature_defaults_to_public():
    """Features not in the map default to PUBLIC."""
    result = FEATURE_SENSITIVITY.get("unknown_feature", DataSensitivity.PUBLIC)
    assert result == DataSensitivity.PUBLIC


# ---------------------------------------------------------------------------
# Unit tests — ZDR_SAFE_PROVIDERS
# ---------------------------------------------------------------------------


def test_mock_is_zdr_safe():
    assert "mock" in ZDR_SAFE_PROVIDERS


def test_demo_is_zdr_safe():
    """'demo' alias for mock must also be ZDR-safe."""
    assert "demo" in ZDR_SAFE_PROVIDERS


def test_ollama_is_zdr_safe():
    assert "ollama" in ZDR_SAFE_PROVIDERS


def test_anthropic_is_zdr_safe():
    assert "anthropic" in ZDR_SAFE_PROVIDERS


def test_openrouter_is_not_zdr_safe():
    """OpenRouter requires explicit ZDR opt-in — not safe by default."""
    assert "openrouter" not in ZDR_SAFE_PROVIDERS


def test_together_is_not_zdr_safe():
    assert "together" not in ZDR_SAFE_PROVIDERS


def test_groq_is_not_zdr_safe():
    assert "groq" not in ZDR_SAFE_PROVIDERS


def test_xai_is_not_zdr_safe():
    assert "xai" not in ZDR_SAFE_PROVIDERS


def test_gemini_is_not_zdr_safe():
    assert "gemini" not in ZDR_SAFE_PROVIDERS


# ---------------------------------------------------------------------------
# Unit tests — check_privacy_boundary
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "provider",
    ["mock", "demo", "ollama", "anthropic", "openrouter", "groq", "together", "xai", "gemini"],
)
def test_public_feature_passes_any_provider(provider: str):
    """Public features (scoring) never raise PrivacyError regardless of provider."""
    # Should not raise
    check_privacy_boundary("score", provider)
    check_privacy_boundary("gap_analysis", provider)
    check_privacy_boundary("company_research", provider)


@pytest.mark.parametrize("provider", ["mock", "demo", "ollama", "anthropic"])
def test_personal_feature_passes_zdr_providers(provider: str):
    """Personal features pass for ZDR-safe providers."""
    # Should not raise
    check_privacy_boundary("voice_cover_letter", provider)
    check_privacy_boundary("interview_prep", provider)
    check_privacy_boundary("voice_coaching", provider)


@pytest.mark.parametrize("provider", ["openrouter", "together", "groq", "xai", "gemini"])
def test_personal_feature_blocked_non_zdr_providers(provider: str):
    """Personal features raise PrivacyError for non-ZDR providers."""
    with pytest.raises(PrivacyError) as exc_info:
        check_privacy_boundary("voice_cover_letter", provider)

    error_msg = str(exc_info.value)
    assert "personal data" in error_msg
    assert provider in error_msg
    assert "zero data retention" in error_msg


def test_privacy_error_message_mentions_safe_alternatives():
    """PrivacyError message tells the user which providers are safe."""
    with pytest.raises(PrivacyError) as exc_info:
        check_privacy_boundary("interview_prep", "openrouter")

    error_msg = str(exc_info.value)
    # Should mention at least one safe alternative
    assert any(p in error_msg for p in ["Ollama", "Anthropic", "OpenRouter"])


def test_privacy_error_message_mentions_feature_name():
    """PrivacyError message includes the feature name for context."""
    with pytest.raises(PrivacyError) as exc_info:
        check_privacy_boundary("voice_cover_letter", "together")

    assert "voice_cover_letter" in str(exc_info.value)


def test_check_privacy_boundary_case_insensitive_provider():
    """Provider name comparison is case-insensitive."""
    # Anthropic in uppercase — should still be recognised as safe
    check_privacy_boundary("voice_cover_letter", "ANTHROPIC")
    check_privacy_boundary("interview_prep", "Ollama")


def test_unknown_feature_passes_boundary():
    """Features not in FEATURE_SENSITIVITY default to PUBLIC — always pass."""
    check_privacy_boundary("some_new_feature", "openrouter")


# ---------------------------------------------------------------------------
# Integration test — PrivacyError returns HTTP 422
# ---------------------------------------------------------------------------


def test_privacy_error_returns_422_from_api():
    """PrivacyError raised in a service returns 422 (not 500) from the API.

    We patch the voice send_message service to raise PrivacyError and verify
    the API maps it to 422 with a structured JSON body.
    """
    from career_os.main import app

    client = TestClient(app, raise_server_exceptions=False)

    # Patch voice.send_message to raise PrivacyError
    with patch(
        "career_os.api.voice.send_message",
        new=AsyncMock(
            side_effect=PrivacyError(
                "'voice_cover_letter' handles personal data and requires a "
                "privacy-safe provider. Current provider 'openrouter' doesn't "
                "guarantee zero data retention."
            )
        ),
    ):
        response = client.post(
            "/api/voice/sessions/1/messages",
            json={"content": "Hello", "profile_id": 1},
        )

    assert response.status_code == 422
    body = response.json()
    assert "error" in body
    assert "personal data" in body["error"]
    assert "resolution" in body
