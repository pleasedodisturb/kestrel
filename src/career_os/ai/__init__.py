"""AI provider abstraction package."""

from career_os.ai.base import AIProvider
from career_os.ai.factory import UnsupportedProviderError, get_ai_provider
from career_os.ai.mock_provider import MockProvider
from career_os.ai.openrouter_provider import OpenRouterProvider

__all__ = [
    "AIProvider",
    "MockProvider",
    "OpenRouterProvider",
    "UnsupportedProviderError",
    "get_ai_provider",
]
