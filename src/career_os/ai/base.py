"""Abstract base class for AI providers."""

from abc import ABC, abstractmethod

from career_os.schemas.ai import AIFeature, AIResponse


class AIProvider(ABC):
    """Abstract AI provider interface.

    All AI providers must implement complete() and score().
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g. 'mock', 'openrouter')."""
        ...

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        *,
        feature: AIFeature = AIFeature.complete,
        context: dict | None = None,
        **kwargs: object,
    ) -> AIResponse:
        """Generate a completion for the given prompt.

        Args:
            prompt: The input prompt text.
            feature: AI feature type controlling response schema.
            context: Optional context data.
            **kwargs: Provider-specific options.

        Returns:
            AIResponse with content and optional structured data.
        """
        ...

    @abstractmethod
    async def score(
        self,
        job_description: str,
        profile_data: dict,
        **kwargs: object,
    ) -> AIResponse:
        """Score a job against a profile.

        Args:
            job_description: Job posting text or structured data.
            profile_data: User profile data dict.
            **kwargs: Provider-specific options.

        Returns:
            AIResponse with ScoreResult structured data.
        """
        ...
