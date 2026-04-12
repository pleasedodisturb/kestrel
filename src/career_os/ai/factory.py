"""AI provider factory — selects provider based on AI_PROVIDER env var."""

import os
from collections.abc import Callable

from career_os.ai.base import AIProvider
from career_os.ai.mock_provider import MockProvider
from career_os.ai.openrouter_provider import OpenRouterProvider

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
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
        model=os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4"),
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


def get_ai_provider(provider_name: str | None = None) -> AIProvider:
    """Create and return the configured AI provider.

    Resolution order:
    1. Explicit `provider_name` argument
    2. AI_PROVIDER env var
    3. Default: "mock"

    Both "mock" and "demo" resolve to MockProvider — "demo" is a friendlier
    user-facing alias so non-technical users don't think "mock" means broken.

    Raises:
        UnsupportedProviderError: If the provider name is not recognized.
    """
    name = (provider_name or os.getenv("AI_PROVIDER", "mock")).strip().lower()

    factory_fn = _PROVIDER_REGISTRY.get(name)
    if factory_fn is None:
        raise UnsupportedProviderError(name)
    return factory_fn()
