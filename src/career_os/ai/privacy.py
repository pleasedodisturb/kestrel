"""Privacy metadata registry for AI providers.

Loads provider privacy policies from ``data/privacy_registry.json`` when
available, falling back to a hardcoded default.  Each entry carries a
``last_verified`` date so consumers (and users) know how fresh the data is.
"""

import json
import logging
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
