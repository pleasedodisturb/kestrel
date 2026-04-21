"""AI provider factory — selects provider based on AI_PROVIDER env var."""

import json
import logging
import os
import sqlite3
from collections.abc import Callable

from career_os.ai.anthropic_provider import AnthropicProvider
from career_os.ai.base import AIProvider
from career_os.ai.mock_provider import MockProvider
from career_os.ai.ollama_provider import OllamaProvider
from career_os.ai.openai_provider import OpenAIProvider
from career_os.ai.openrouter_provider import OpenRouterProvider
from career_os.ai.together_provider import TogetherProvider

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
        model=os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4"),
    ),
    "anthropic": lambda: AnthropicProvider(
        api_key=_resolve_api_key("ANTHROPIC_API_KEY", "anthropic_api_key"),
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
    ),
    "ollama": lambda: OllamaProvider(
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        model=os.getenv("OLLAMA_MODEL", "llama3.3"),
    ),
    "together": lambda: TogetherProvider(
        api_key=_resolve_api_key("TOGETHER_API_KEY", "together_api_key"),
        model=os.getenv("TOGETHER_MODEL", "meta-llama/Llama-3.3-70B-Instruct-Turbo"),
    ),
    "openai": lambda: OpenAIProvider(
        api_key=_resolve_api_key("OPENAI_API_KEY", "openai_api_key"),
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    ),
}

_SUPPORTED_PROVIDERS = set(_PROVIDER_REGISTRY.keys())


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

    Expected format: comma-separated provider names, e.g.
    "openrouter,together,ollama". Providers that can't be instantiated
    (missing API key) are silently skipped.

    Returns None if no fallback is configured or only one provider resolves.
    """
    fallback_str = os.getenv("AI_PROVIDER_FALLBACK", "").strip()
    if not fallback_str:
        return None

    names = [n.strip().lower() for n in fallback_str.split(",") if n.strip()]
    if len(names) < 2:
        return None

    chain: list[AIProvider] = []
    for name in names:
        factory_fn = _PROVIDER_REGISTRY.get(name)
        if factory_fn is None:
            logger.warning("Fallback chain: skipping unknown provider '%s'", name)
            continue
        try:
            chain.append(factory_fn())
        except (ValueError, KeyError) as exc:
            # Missing API key or config — skip this provider
            logger.info("Fallback chain: skipping %s (%s)", name, exc)

    if len(chain) < 2:
        return None
    return chain


def get_ai_provider(provider_name: str | None = None) -> AIProvider:
    """Create and return the configured AI provider.

    Resolution order:
    1. Explicit `provider_name` argument
    2. AI_PROVIDER env var
    3. Default: "mock"

    If AI_PROVIDER_FALLBACK is set (comma-separated list of provider names),
    wraps the result in a FallbackProvider for automatic retry on quota/timeout.

    Both "mock" and "demo" resolve to MockProvider — "demo" is a friendlier
    user-facing alias so non-technical users don't think "mock" means broken.

    Raises:
        UnsupportedProviderError: If the provider name is not recognized.
    """
    name = (provider_name or os.getenv("AI_PROVIDER", "mock")).strip().lower()

    factory_fn = _PROVIDER_REGISTRY.get(name)
    if factory_fn is None:
        raise UnsupportedProviderError(name)

    # Check for fallback chain
    fallback_chain = _build_fallback_chain()
    if fallback_chain:
        from career_os.ai.fallback import FallbackProvider

        return FallbackProvider(fallback_chain)

    return factory_fn()
