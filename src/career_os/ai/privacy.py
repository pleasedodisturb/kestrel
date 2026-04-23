"""Privacy metadata registry for AI providers.

Loads provider privacy policies from ``data/privacy_registry.json`` when
available, falling back to a hardcoded default.  Each entry carries a
``last_verified`` date so consumers (and users) know how fresh the data is.

Also provides PII safety boundary enforcement: personal-data features
(cover letters, interview prep, STAR stories, voice coaching) are blocked
from non-ZDR providers to prevent inadvertent personal data exposure.
"""

import json
import logging
from enum import StrEnum
from pathlib import Path

from career_os.schemas.privacy import DataRetention, PrivacyTier, ProviderPrivacyInfo

logger = logging.getLogger(__name__)

_REGISTRY_PATH = Path(__file__).resolve().parent.parent / "privacy_registry.json"

# ---------------------------------------------------------------------------
# Hardcoded fallback (used when the JSON file is absent or invalid)
# ---------------------------------------------------------------------------

_HARDCODED_REGISTRY: dict[str, ProviderPrivacyInfo] = {
    "mock": ProviderPrivacyInfo(
        provider="mock",
        tier=PrivacyTier.local,
        trains_on_data=False,
        human_review=False,
        retention=DataRetention(days=0, description="No data retained — mock provider"),
        dpa_available=False,
        gdpr_compliant=True,
        eu_banned=False,
        warnings=[],
        recommendation="Development/testing only",
        last_verified="2026-04-13",
    ),
    "ollama": ProviderPrivacyInfo(
        provider="ollama",
        tier=PrivacyTier.local,
        trains_on_data=False,
        human_review=False,
        retention=DataRetention(days=0, description="No data leaves the device"),
        dpa_available=False,
        gdpr_compliant=True,
        eu_banned=False,
        warnings=[],
        recommendation="Best privacy — all processing on-device",
        last_verified="2026-04-13",
    ),
    "openrouter": ProviderPrivacyInfo(
        provider="openrouter",
        tier=PrivacyTier.yellow,
        trains_on_data=False,
        human_review=False,
        retention=DataRetention(days=30, description="30-day prompt log retention"),
        dpa_available=False,
        gdpr_compliant=True,
        eu_banned=False,
        warnings=[
            "Prompt logging enabled under commercial license",
            "Data routed through third-party providers — check downstream policies",
        ],
        recommendation="Review OpenRouter privacy settings before sending sensitive data",
        last_verified="2026-04-13",
    ),
    "anthropic": ProviderPrivacyInfo(
        provider="anthropic",
        tier=PrivacyTier.green,
        trains_on_data=False,
        human_review=False,
        retention=DataRetention(days=7, description="7-day retention for abuse monitoring"),
        dpa_available=True,
        gdpr_compliant=True,
        eu_banned=False,
        warnings=[],
        recommendation="Recommended for EU users — strong privacy, DPA available",
        last_verified="2026-04-13",
    ),
    "gemini": ProviderPrivacyInfo(
        provider="gemini",
        tier=PrivacyTier.yellow,
        trains_on_data=False,
        human_review=False,
        retention=DataRetention(days=None, description="Varies by plan — free tier trains on data"),
        dpa_available=True,
        gdpr_compliant=True,
        eu_banned=False,
        warnings=[
            "Free tier trains on prompts — use paid API only",
            "Gemini free tier banned in EU (DMA non-compliance)",
        ],
        recommendation="Use paid API tier only; avoid free tier for sensitive data",
        last_verified="2026-04-13",
    ),
    "mistral": ProviderPrivacyInfo(
        provider="mistral",
        tier=PrivacyTier.green,
        trains_on_data=False,
        human_review=False,
        retention=DataRetention(days=30, description="30-day retention for paid API"),
        dpa_available=True,
        gdpr_compliant=True,
        eu_banned=False,
        warnings=[],
        recommendation="EU-headquartered — good choice for EU data sovereignty",
        last_verified="2026-04-13",
    ),
    "groq": ProviderPrivacyInfo(
        provider="groq",
        tier=PrivacyTier.green,
        trains_on_data=False,
        human_review=False,
        retention=DataRetention(days=0, description="No prompt data retained"),
        dpa_available=False,
        gdpr_compliant=True,
        eu_banned=False,
        warnings=[],
        recommendation="Fast inference, no data retention",
        last_verified="2026-04-13",
    ),
    "xai": ProviderPrivacyInfo(
        provider="xai",
        tier=PrivacyTier.red,
        trains_on_data=True,
        human_review=True,
        retention=DataRetention(days=None, description="Irrevocable data sharing — indefinite"),
        dpa_available=False,
        gdpr_compliant=False,
        eu_banned=False,
        warnings=[
            "Irrevocable data sharing program — prompts may be used for training",
            "Multiple active GDPR investigations by EU data protection authorities",
            "No opt-out mechanism for data sharing once submitted",
        ],
        recommendation="Avoid for sensitive or personal data. Red privacy tier.",
        last_verified="2026-04-21",
    ),
}

# ---------------------------------------------------------------------------
# Loading logic
# ---------------------------------------------------------------------------


def _load_registry(
    path: Path = _REGISTRY_PATH,
) -> dict[str, ProviderPrivacyInfo]:
    """Load the registry from a JSON file, falling back to hardcoded defaults."""
    if not path.exists():
        return dict(_HARDCODED_REGISTRY)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {name: ProviderPrivacyInfo.model_validate(entry) for name, entry in raw.items()}
    except Exception:
        logger.warning("Failed to load privacy registry from %s — using hardcoded fallback", path)
        return dict(_HARDCODED_REGISTRY)


PROVIDER_PRIVACY_REGISTRY: dict[str, ProviderPrivacyInfo] = _load_registry()


def reload_registry(path: Path = _REGISTRY_PATH) -> None:
    """Reload the privacy registry from disk (or reset to hardcoded defaults)."""
    PROVIDER_PRIVACY_REGISTRY.clear()
    PROVIDER_PRIVACY_REGISTRY.update(_load_registry(path))


def get_privacy_info(provider_name: str) -> ProviderPrivacyInfo | None:
    """Return privacy metadata for a provider, or None if unknown.

    Args:
        provider_name: Case-insensitive provider identifier.

    Returns:
        ProviderPrivacyInfo if the provider is in the registry, else None.
    """
    return PROVIDER_PRIVACY_REGISTRY.get(provider_name.lower())


# ---------------------------------------------------------------------------
# PII safety boundary — feature sensitivity classification
# ---------------------------------------------------------------------------


class DataSensitivity(StrEnum):
    """Sensitivity level of data handled by an AI feature.

    PUBLIC features only touch job descriptions, career preferences, and other
    non-personal data.  PERSONAL features touch CV content, cover letters,
    STAR stories, interview coaching, or other data that can identify the user.
    """

    PUBLIC = "public"
    PERSONAL = "personal"


# Map AIFeature string values to sensitivity levels.
# Features not listed default to PUBLIC.
FEATURE_SENSITIVITY: dict[str, DataSensitivity] = {
    # Public features — safe with any provider
    "score": DataSensitivity.PUBLIC,
    "gap_analysis": DataSensitivity.PUBLIC,
    "company_research": DataSensitivity.PUBLIC,
    "goal_recalibration": DataSensitivity.PUBLIC,
    "learning_recommendations": DataSensitivity.PUBLIC,
    "interview_format": DataSensitivity.PUBLIC,
    "interview_patterns": DataSensitivity.PUBLIC,
    "complete": DataSensitivity.PUBLIC,
    # Personal features — require a ZDR-safe provider
    "voice_cover_letter": DataSensitivity.PERSONAL,
    "voice_coaching": DataSensitivity.PERSONAL,
    "voice_job_evaluation": DataSensitivity.PERSONAL,
    "coaching": DataSensitivity.PERSONAL,
    "interview_prep": DataSensitivity.PERSONAL,
    "star_stories": DataSensitivity.PERSONAL,
}

# Providers that guarantee zero data retention by default.
# OpenRouter is excluded because ZDR requires explicit opt-in per request.
# Together, OpenAI, Groq, xAI, Gemini: not ZDR by default.
ZDR_SAFE_PROVIDERS: frozenset[str] = frozenset({"mock", "demo", "ollama", "anthropic"})


class PrivacyError(Exception):
    """Raised when a feature requires privacy guarantees the provider can't give.

    This is a user-visible error — the message is shown directly in the API
    response.  Keep the message clear and actionable.
    """

    pass


def check_privacy_boundary(feature: str, provider_name: str) -> None:
    """Enforce PII safety: block personal-data features from non-ZDR providers.

    Call this BEFORE invoking the AI provider for any personal feature.
    Scoring and other public features always pass through.

    Args:
        feature: AIFeature string value (e.g. ``"voice_cover_letter"``).
        provider_name: The active provider name (e.g. ``"openrouter"``).

    Raises:
        PrivacyError: If the feature handles personal data and the provider
            does not guarantee zero data retention.
    """
    sensitivity = FEATURE_SENSITIVITY.get(feature, DataSensitivity.PUBLIC)
    if sensitivity == DataSensitivity.PERSONAL and provider_name.lower() not in ZDR_SAFE_PROVIDERS:
        raise PrivacyError(
            f"'{feature}' handles personal data and requires a privacy-safe provider. "
            f"Current provider '{provider_name}' doesn't guarantee zero data retention. "
            f"Switch to Ollama (local, fully private), Anthropic (zero-day retention "
            f"policy, DPA available), or configure OpenRouter with ZDR enabled."
        )
