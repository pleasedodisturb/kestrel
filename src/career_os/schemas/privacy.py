"""Privacy metadata schemas for AI provider transparency."""

from enum import StrEnum

from pydantic import BaseModel, Field


class PrivacyTier(StrEnum):
    """Privacy tier classification for AI providers.

    Tiers indicate how a provider handles user data, from most private
    (local) to highest risk (red).
    """

    local = "local"  # Data stays on device (Ollama, local models)
    green = "green"  # Cloud, no training, strong privacy (Anthropic, Groq, Together)
    yellow = "yellow"  # Safe by default, review settings (OpenRouter, Gemini paid)
    red = "red"  # Privacy risk (Gemini free, Chinese direct APIs)


class DataRetention(BaseModel):
    """Data retention policy description."""

    days: int | None = Field(None, description="Retention in days, None=indefinite")
    description: str = Field(..., description="Human-readable retention policy")


class ProviderPrivacyInfo(BaseModel):
    """Privacy metadata for a single AI provider."""

    provider: str
    tier: PrivacyTier
    trains_on_data: bool = False
    human_review: bool = False
    retention: DataRetention
    dpa_available: bool = False
    gdpr_compliant: bool = True
    eu_banned: bool = False  # True for Gemini free tier
    warnings: list[str] = Field(default_factory=list)
    recommendation: str = ""  # e.g. "Recommended for EU users"
    last_verified: str = ""  # ISO date when the policy was last verified, e.g. "2026-04-13"
