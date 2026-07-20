"""AI provider factory — selects provider based on AI_PROVIDER env var."""

import json
import logging
import os
import sqlite3
from collections.abc import Callable

from career_os.ai.anthropic_provider import AnthropicProvider
from career_os.ai.base import AIProvider
from career_os.ai.gemini_provider import GeminiProvider
from career_os.ai.groq_provider import GroqProvider
from career_os.ai.huggingface_provider import HuggingFaceProvider
from career_os.ai.mistral_provider import MistralProvider
from career_os.ai.mock_provider import MockProvider
from career_os.ai.ollama_provider import OllamaProvider
from career_os.ai.openai_provider import DEFAULT_MODEL as OPENAI_DEFAULT_MODEL
from career_os.ai.openai_provider import OpenAIProvider
from career_os.ai.openrouter_provider import DEFAULT_MODEL as OPENROUTER_DEFAULT_MODEL
from career_os.ai.openrouter_provider import OpenRouterProvider
from career_os.ai.together_provider import TogetherProvider
from career_os.ai.xai_provider import XAIProvider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DB credential lookup — lightweight, no ORM dependency
# ---------------------------------------------------------------------------


def _read_credential_from_db(credential_key: str) -> str:
    """Read a credential value from the integration_configs table.

    Uses a direct SQLite connection to avoid circular imports with the
    full service layer.  Returns empty string if not found or on error.
    """
    from career_os.config import settings

    db_url = settings.database_url
    if not db_url.startswith("sqlite"):
        return ""

    db_path = db_url.replace("sqlite:///", "")
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT credentials FROM integration_configs WHERE name = ?",
            ("ai_providers",),
        ).fetchone()
        conn.close()
    except Exception:
        return ""

    if row is None or not row[0]:
        return ""
    try:
        creds = json.loads(row[0])
        return creds.get(credential_key, "")
    except (json.JSONDecodeError, TypeError):
        return ""


def _resolve_api_key(env_var: str, credential_key: str) -> str:
    """Resolve an API key: env var first, then DB-stored credential."""
    val = os.getenv(env_var, "")
    if val:
        return val
    return _read_credential_from_db(credential_key)


# ---------------------------------------------------------------------------
# Provider registry: name → factory callable.
# To add a new provider, add one entry here (+ its module).
# "demo" is a user-facing alias for "mock" so non-technical users don't
# think "mock" means broken.
# ---------------------------------------------------------------------------

_PROVIDER_REGISTRY: dict[str, Callable[[], AIProvider]] = {
    "mock": lambda: MockProvider(),
    "demo": lambda: MockProvider(),
    "openrouter": lambda: OpenRouterProvider(
        api_key=_resolve_api_key("OPENROUTER_API_KEY", "openrouter_api_key"),
        model=os.getenv("OPENROUTER_MODEL", OPENROUTER_DEFAULT_MODEL),
    ),
    "anthropic": lambda: AnthropicProvider(
        api_key=_resolve_api_key("ANTHROPIC_API_KEY", "anthropic_api_key"),
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5"),
    ),
    "ollama": lambda: OllamaProvider(
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        model=os.getenv("OLLAMA_MODEL", "llama3.3"),
    ),
    "openai": lambda: OpenAIProvider(
        api_key=_resolve_api_key("OPENAI_API_KEY", "openai_api_key"),
        # `or DEFAULT` (not just getenv's default): a set-but-empty OPENAI_MODEL
        # would otherwise send model="" and 400 every request.
        model=os.getenv("OPENAI_MODEL", "").strip() or OPENAI_DEFAULT_MODEL,
    ),
    "together": lambda: TogetherProvider(
        api_key=_resolve_api_key("TOGETHER_API_KEY", "together_api_key"),
        model=os.getenv("TOGETHER_MODEL", "meta-llama/Llama-3.3-70B-Instruct-Turbo"),
    ),
    "groq": lambda: GroqProvider(
        api_key=_resolve_api_key("GROQ_API_KEY", "groq_api_key"),
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
    ),
    "xai": lambda: XAIProvider(
        api_key=_resolve_api_key("XAI_API_KEY", "xai_api_key"),
        model=os.getenv("XAI_MODEL", "grok-3-mini"),
    ),
    "gemini": lambda: GeminiProvider(
        api_key=_resolve_api_key("GEMINI_API_KEY", "gemini_api_key"),
        model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
    ),
    "mistral": lambda: MistralProvider(
        api_key=_resolve_api_key("MISTRAL_API_KEY", "mistral_api_key"),
        # Mistral Small (not Large) is the default: a 2026-07 cost/quality
        # benchmark found Small the best-value scorer for bulk job filtering —
        # closest to premium Claude Opus at a fraction of the cost. Set
        # MISTRAL_MODEL=mistral-large-latest to opt into the flagship for deep work.
        model=os.getenv("MISTRAL_MODEL", "mistral-small-latest"),
    ),
    "huggingface": lambda: HuggingFaceProvider(
        api_key=_resolve_api_key("HF_API_KEY", "hf_api_key")
        or os.getenv("HUGGINGFACE_API_KEY", ""),
        model=os.getenv("HF_MODEL", "meta-llama/Llama-3.3-70B-Instruct"),
    ),
    "hf": lambda: HuggingFaceProvider(
        api_key=_resolve_api_key("HF_API_KEY", "hf_api_key")
        or os.getenv("HUGGINGFACE_API_KEY", ""),
        model=os.getenv("HF_MODEL", "meta-llama/Llama-3.3-70B-Instruct"),
    ),
}

_SUPPORTED_PROVIDERS = set(_PROVIDER_REGISTRY.keys())

# ---------------------------------------------------------------------------
# Premium-provider fallback guard (COE 2026-07-19, G-1371)
#
# `anthropic` (claude-sonnet-5 / opus-4-8) bills ~10-20x the cheap providers.
# It must NEVER be a *silent* terminal leg of a fallback chain: when the cheap
# providers ahead of it rate-limit or run out of credits, every dropped job
# cascades onto premium Claude with no alarm. Premium fallback is opt-in only.
#
# NOTE: `openrouter` is a *routing* provider whose cost depends on
# OPENROUTER_MODEL (its registry default is a premium Claude model). It is
# treated as premium-in-fallback whenever it would route to Anthropic — see
# `_openrouter_routes_anthropic` and `_is_premium_in_fallback` below (G-1378).
#
# SCOPE (G-1378): the codebase classifies only the `anthropic` family as PREMIUM
# (see COST_TIER in tests/test_billing_safety.py), and the OpenRouter regression
# this guards was the silent `anthropic/claude-sonnet-5` default. OpenRouter can
# also route to other pricey models (e.g. `openai/o1`), but their cost cannot be
# reliably inferred from the model name, so classifying them is out of scope:
# pointing OPENROUTER_MODEL at a costly non-Anthropic model is treated as the
# operator's deliberate choice (like an explicit primary `AI_PROVIDER=anthropic`).
# ---------------------------------------------------------------------------
_PREMIUM_PROVIDERS = frozenset({"anthropic"})

_ALLOW_PREMIUM_ENV = "AI_ALLOW_PREMIUM_FALLBACK"


def _premium_fallback_allowed() -> bool:
    """True only when premium providers are explicitly opted into as fallbacks."""
    return os.getenv(_ALLOW_PREMIUM_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _openrouter_routes_anthropic() -> bool:
    """True if `openrouter` would route to a premium Anthropic model.

    OpenRouter's model is OPENROUTER_MODEL, defaulting (when unset) to the same
    premium Claude model the factory constructs openrouter with
    (``OPENROUTER_DEFAULT_MODEL``). So it routes to Anthropic when the var is
    unset/empty (falls to that default) or explicitly points at ``anthropic/*``.

    Scoped to the Anthropic family on purpose (see the module NOTE above): the
    codebase's only PREMIUM tier is anthropic, and other OpenRouter models can't
    be cost-classified from their name. Non-Anthropic models are treated as the
    operator's deliberate choice and kept.
    """
    model = os.getenv("OPENROUTER_MODEL", "").strip().lower() or OPENROUTER_DEFAULT_MODEL.lower()
    return model.startswith("anthropic/")


def _is_premium_in_fallback(name: str) -> bool:
    """Whether provider ``name`` is a premium surprise-bill hazard as a fallback."""
    if name in _PREMIUM_PROVIDERS:
        return True
    return name == "openrouter" and _openrouter_routes_anthropic()


def _filter_premium(names: list[str]) -> list[str]:
    """Drop premium providers from a fallback chain unless explicitly opted in.

    Pure function (no I/O beyond env reads, no provider construction) so it is
    trivially testable. A premium provider reached as a silent fallback is a
    surprise-bill hazard (COE 2026-07-19); this also covers `openrouter` when it
    would route to Anthropic (G-1378). Set AI_ALLOW_PREMIUM_FALLBACK=1 to allow
    premium fallbacks deliberately.
    """
    if _premium_fallback_allowed():
        return names
    dropped = [n for n in names if _is_premium_in_fallback(n)]
    if dropped:
        logger.warning(
            "Fallback chain: dropping premium provider(s) %s — premium fallback is "
            "opt-in only (set %s=1 to allow). openrouter counts as premium when "
            "OPENROUTER_MODEL is unset or an anthropic/* model.",
            dropped,
            _ALLOW_PREMIUM_ENV,
        )
    return [n for n in names if not _is_premium_in_fallback(n)]


class UnsupportedProviderError(Exception):
    """Raised when AI_PROVIDER is set to an unsupported value."""

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name
        supported = ", ".join(sorted(_SUPPORTED_PROVIDERS))
        super().__init__(
            f"Unsupported AI provider: '{provider_name}'. "
            f"Supported providers: {supported}. "
            f"Set AI_PROVIDER env var to one of: {supported} "
            f"('demo' is an alias for 'mock')"
        )


def _build_fallback_chain() -> list[AIProvider] | None:
    """Build a fallback chain from AI_PROVIDER_FALLBACK env var.

    Returns a list of provider instances for each valid provider name in the
    comma-separated env var, or None if the env var is unset or only contains
    a single provider (no chain needed).

    Unknown provider names are silently skipped. Premium providers are dropped
    unless AI_ALLOW_PREMIUM_FALLBACK is set (see _filter_premium) — a premium
    provider reached as a silent fallback is a surprise-bill hazard (COE
    2026-07-19).
    """
    raw = os.getenv("AI_PROVIDER_FALLBACK", "").strip()
    if not raw:
        return None

    requested = [n.strip().lower() for n in raw.split(",") if n.strip()]
    names = _filter_premium(requested)
    providers: list[AIProvider] = []
    for name in names:
        factory_fn = _PROVIDER_REGISTRY.get(name)
        if factory_fn is not None:
            providers.append(factory_fn())
        else:
            logger.warning("Fallback chain: skipping unknown provider '%s'", name)

    if len(providers) < 2:
        # A chain needs >=2 legs; below that, get_ai_provider falls through to the
        # primary AI_PROVIDER (which defaults to "mock"). This is NOT a hard error,
        # so surface the degrade — especially when premium/unknown filtering
        # collapsed a chain the operator explicitly configured.
        if len(requested) >= 2:
            logger.warning(
                "Fallback chain %s collapsed to %d usable provider(s) after "
                "premium/unknown filtering — no fallback chain will be used; the "
                "primary AI_PROVIDER handles scoring (ensure it is a real cheap "
                "provider, not mock; set %s=1 to keep premium legs).",
                requested,
                len(providers),
                _ALLOW_PREMIUM_ENV,
            )
        return None
    return providers


def get_ai_provider(provider_name: str | None = None) -> AIProvider:
    """Create and return the configured AI provider.

    Resolution order:
    1. Explicit `provider_name` argument
    2. AI_PROVIDER_FALLBACK env var (builds a FallbackProvider chain)
    3. AI_PROVIDER env var
    4. Default: "mock"

    Both "mock" and "demo" resolve to MockProvider — "demo" is a friendlier
    user-facing alias so non-technical users don't think "mock" means broken.

    Raises:
        UnsupportedProviderError: If the provider name is not recognized.
    """
    # When no explicit name given, check for a fallback chain first
    if provider_name is None:
        chain = _build_fallback_chain()
        if chain is not None:
            from career_os.ai.fallback import FallbackProvider

            return FallbackProvider(chain)

    name = (provider_name or os.getenv("AI_PROVIDER", "mock")).strip().lower()

    factory_fn = _PROVIDER_REGISTRY.get(name)
    if factory_fn is None:
        raise UnsupportedProviderError(name)
    return factory_fn()
