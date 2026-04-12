"""Privacy metadata registry for AI providers.

Maps provider names to their privacy characteristics based on
documented policies as of 2026-Q2.
"""

from career_os.schemas.privacy import DataRetention, PrivacyTier, ProviderPrivacyInfo

PROVIDER_PRIVACY_REGISTRY: dict[str, ProviderPrivacyInfo] = {
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
    ),
}


def get_privacy_info(provider_name: str) -> ProviderPrivacyInfo | None:
    """Return privacy metadata for a provider, or None if unknown.

    Args:
        provider_name: Case-insensitive provider identifier.

    Returns:
        ProviderPrivacyInfo if the provider is in the registry, else None.
    """
    return PROVIDER_PRIVACY_REGISTRY.get(provider_name.lower())
