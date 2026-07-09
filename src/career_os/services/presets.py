"""Cost preset service — one setting controls provider, model, pre-filter, and batch size.

Five tiers:
  free    — OpenRouter free models or Groq/Cerebras, $0/mo
  budget  — GPT-4o-mini via OpenRouter, ~$0.81/mo (DEFAULT)
  quality — Sonnet scoring + Opus generation, $5-25/mo
  private — ZDR providers (Together.ai) or Ollama, $0 + hardware
  custom  — User configures everything manually
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from career_os.config import settings


@dataclass(frozen=True)
class CostPreset:
    """Immutable definition of a cost preset."""

    name: str
    display_name: str
    description: str
    estimated_cost: str
    provider: str
    model: str
    prefilter_strategy: str  # strict | moderate | off
    batch_size: int
    extra: dict[str, Any] = field(default_factory=dict)


PRESETS: dict[str, CostPreset] = {
    "free": CostPreset(
        name="free",
        display_name="Free",
        description=(
            "Zero-cost tier using OpenRouter free models or Groq/Cerebras. "
            "Rate-limited; suitable for exploration and testing."
        ),
        estimated_cost="$0/mo",
        provider="openrouter",
        model="meta-llama/llama-3.3-70b-instruct:free",
        prefilter_strategy="strict",
        batch_size=5,
    ),
    "budget": CostPreset(
        name="budget",
        display_name="Budget",
        description=(
            "GPT-4o-mini via OpenRouter. Reliable JSON output, "
            "low cost. Recommended default for active job searches."
        ),
        estimated_cost="~$0.81/mo",
        provider="openrouter",
        model="openai/gpt-4o-mini",
        prefilter_strategy="strict",
        batch_size=10,
    ),
    "quality": CostPreset(
        name="quality",
        display_name="Quality",
        description=(
            "Sonnet for scoring, Opus for generation. Best reasoning and nuance at higher cost."
        ),
        estimated_cost="$5-25/mo",
        provider="openrouter",
        model="anthropic/claude-sonnet-5",
        prefilter_strategy="moderate",
        batch_size=15,
    ),
    "private": CostPreset(
        name="private",
        display_name="Private",
        description=(
            "Zero data retention providers (Together.ai) or local Ollama. "
            "Your data never leaves your control."
        ),
        estimated_cost="$0 + hardware",
        provider="together",
        model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
        prefilter_strategy="strict",
        batch_size=5,
    ),
    "custom": CostPreset(
        name="custom",
        display_name="Custom",
        description="User-configured provider, model, and settings. Full control.",
        estimated_cost="varies",
        provider="",  # user sets via env/config
        model="",
        prefilter_strategy="",
        batch_size=0,
    ),
}

DEFAULT_PRESET = "budget"

# Module-level active preset name — persists for the process lifetime.
_active_preset: str = ""


def _resolve_initial_preset() -> str:
    """Return the preset name from settings, falling back to DEFAULT_PRESET."""
    raw = getattr(settings, "cost_preset", DEFAULT_PRESET)
    return raw if raw in PRESETS else DEFAULT_PRESET


def get_active_preset_name() -> str:
    """Return the currently active preset name."""
    global _active_preset  # noqa: PLW0603
    if not _active_preset:
        _active_preset = _resolve_initial_preset()
    return _active_preset


def get_preset(name: str) -> CostPreset | None:
    """Look up a preset by name.  Returns None if unknown."""
    return PRESETS.get(name)


def list_presets() -> list[CostPreset]:
    """Return all available presets in display order."""
    return list(PRESETS.values())


def apply_preset(name: str) -> CostPreset:
    """Activate a preset, updating runtime settings.

    For the 'custom' preset no settings are changed — the user is expected
    to configure provider/model via environment variables or the API.

    Raises ValueError if *name* is not a recognised preset.
    """
    preset = PRESETS.get(name)
    if preset is None:
        raise ValueError(f"Unknown preset '{name}'. Valid presets: {', '.join(PRESETS)}")

    global _active_preset  # noqa: PLW0603
    _active_preset = name

    # Custom preset: user manages settings themselves.
    if name == "custom":
        return preset

    # Apply non-custom preset values to the runtime settings object.
    # These are in-process overrides; they do NOT write to .env.
    settings.ai_provider = preset.provider
    settings.prefilter_strategy = preset.prefilter_strategy

    # Model field depends on provider
    _MODEL_FIELD_MAP: dict[str, str] = {
        "openrouter": "openrouter_model",
        "anthropic": "anthropic_model",
        "together": "together_model",
        "ollama": "ollama_model",
    }
    model_attr = _MODEL_FIELD_MAP.get(preset.provider)
    if model_attr:
        setattr(settings, model_attr, preset.model)

    return preset
