"""Abstract base class for AI providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum

from career_os.schemas.ai import AIFeature, AIResponse


class ComplexityTier(StrEnum):
    """Task complexity tier for model routing.

    Routes AI calls to different models based on task complexity:
    - SIMPLE: Classification, extraction, keyword matching -> cheaper models (Haiku)
    - STANDARD: Generation, analysis -> default models (Sonnet)
    - COMPLEX: Deep reasoning, strategy -> most capable models (Opus)
    """

    SIMPLE = "simple"
    STANDARD = "standard"
    COMPLEX = "complex"


class ProviderQuotaError(Exception):
    """Raised when an AI provider returns 402/429 indicating quota exhaustion."""

    def __init__(self, provider: str, status_code: int, detail: str = "") -> None:
        self.provider = provider
        self.status_code = status_code
        message = f"{provider} quota/credits exhausted (HTTP {status_code})."
        if detail:
            message += f" {detail}"
        super().__init__(message)


class AIProvider(ABC):
    """Abstract AI provider interface.

    All AI providers must implement complete() and score().
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g. 'mock', 'openrouter')."""
        ...

    @property
    def privacy_tier(self) -> str:
        """Privacy tier for this provider (default: yellow).

        Subclasses may override to report their actual tier.
        See :class:`career_os.schemas.privacy.PrivacyTier` for values.
        """
        return "yellow"

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        *,
        feature: AIFeature = AIFeature.complete,
        context: dict | None = None,
        tier: ComplexityTier | None = None,
        **kwargs: object,
    ) -> AIResponse:
        """Generate a completion for the given prompt.

        Args:
            prompt: The input prompt text.
            feature: AI feature type controlling response schema.
            context: Optional context data.
            tier: Complexity tier for model routing. None defaults to STANDARD.
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
        *,
        tier: ComplexityTier | None = None,
        **kwargs: object,
    ) -> AIResponse:
        """Score a job against a profile.

        Args:
            job_description: Job posting text or structured data.
            profile_data: User profile data dict.
            tier: Complexity tier for model routing. None defaults to STANDARD.
            **kwargs: Provider-specific options.

        Returns:
            AIResponse with ScoreResult structured data.
        """
        ...

    async def batch_score(
        self,
        jobs: list[dict],
        profile_data: dict,
        **kwargs: object,
    ) -> str:
        """Submit batch scoring request. Returns batch ID.

        Default implementation raises NotImplementedError. Providers that
        support batch scoring (Anthropic) override this method.

        Args:
            jobs: List of dicts, each with at least 'id' and 'description' keys.
            profile_data: User profile data dict.

        Returns:
            Batch ID string for polling results.
        """
        raise NotImplementedError(f"{self.name} provider does not support batch scoring")

    async def get_batch_results(self, batch_id: str) -> dict:
        """Get results of a batch scoring request.

        Default implementation raises NotImplementedError. Providers that
        support batch scoring (Anthropic) override this method.

        Args:
            batch_id: The batch ID returned by batch_score().

        Returns:
            Dict with 'status' key and 'results' key (list of AIResponse)
            when status is 'ended'.
        """
        raise NotImplementedError(f"{self.name} provider does not support batch results")

    async def embed(self, text: str, **kwargs: object) -> list[float]:
        """Generate an embedding vector for the given text.

        Default implementation raises NotImplementedError. Providers that
        support embeddings (Ollama, future Voyage AI) override this method.
        Callers should catch NotImplementedError for graceful degradation.

        Args:
            text: The input text to embed.
            **kwargs: Provider-specific options (e.g. model override).

        Returns:
            A list of floats representing the embedding vector.
        """
        raise NotImplementedError(f"{self.name} provider does not support embeddings")
