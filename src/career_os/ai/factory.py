"""AI provider factory — selects provider based on AI_PROVIDER env var."""

import os

from career_os.ai.base import AIProvider
from career_os.ai.mock_provider import MockProvider
from career_os.ai.openrouter_provider import OpenRouterProvider

# Registry of supported provider names → constructors
_SUPPORTED_PROVIDERS = {"mock", "openrouter"}


class UnsupportedProviderError(Exception):
    """Raised when AI_PROVIDER is set to an unsupported value."""

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name
        supported = ", ".join(sorted(_SUPPORTED_PROVIDERS))
        super().__init__(
            f"Unsupported AI provider: '{provider_name}'. "
            f"Supported providers: {supported}. "
            f"Set AI_PROVIDER env var to one of: {supported}"
        )


def get_ai_provider(provider_name: str | None = None) -> AIProvider:
    """Create and return the configured AI provider.

    Resolution order:
    1. Explicit `provider_name` argument
    2. AI_PROVIDER env var
    3. Default: "mock"

    Raises:
        UnsupportedProviderError: If the provider name is not recognized.
    """
    name = provider_name or os.getenv("AI_PROVIDER", "mock")
    name = name.strip().lower()

    if name == "mock":
        return MockProvider()

    if name == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        model = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4")
        return OpenRouterProvider(api_key=api_key, model=model)

    raise UnsupportedProviderError(name)
