"""Abstract base class for AI providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum

from career_os.schemas.ai import AIFeature, AIResponse

# ---------------------------------------------------------------------------
# Role-fit gate + anti-halo preamble (G-1335)
# ---------------------------------------------------------------------------
# Prepended to every real provider's score prompt (the single-scorer preamble
# and the multi-job batch prompt). Counters the halo effect where a prestigious
# company + hot domain haloes the holistic fit number for a job the candidate's
# role family cannot actually do. Company prestige lives on the DESIRE axis, not
# the FIT axis. The two extra fields (role_match, disqualifiers) let the scoring
# service enforce a code-side cap post-parse (see schemas.ai.apply_role_fit_gate).
#
# Intentionally NOT part of career_os.services.scoring._build_scoring_prompt, so
# the deterministic golden-set snapshot (which hashes that prompt) stays stable
# while real providers still receive the guardrails here.
ROLE_FIT_GATE_PROMPT = (
    "IMPORTANT — role-fit gate (anti-halo): Company prestige and a hot domain must "
    "NEVER substitute for role fit. A famous company hiring for the WRONG role family "
    "(e.g. a SWE/SRE/designer/partnerships role for a PM/TPM candidate) is a POOR fit "
    "even if the candidate would love to work there — that enthusiasm is a desire "
    "signal, not fit.\n"
    "Reason before you score: write the evidence FIRST and the number last, list the "
    "reasons to REJECT before the reasons to hire, and name at least one JD-grounded "
    "weakness (an 'against' point) for every dimension — never an all-positive rationale.\n"
    "Score FIT by tier: PRIMARY (dominant) = technical_fit + seniority_alignment; "
    "SECONDARY = career_trajectory, compensation_fit, location_fit; MINOR (capped) = "
    "company_fit, which scores culture / values / company size / work style ONLY — NOT "
    "domain prestige or brand — and may move the overall fit by at most ±1 and can NEVER "
    "rescue a role the candidate cannot do. Put prestige / 'I'd love to work there' into "
    "desire_score, not fit.\n"
    "Emit two extra fields FIRST, before fit_score:\n"
    "- role_match: an object with is_same_role_family (bool — true ONLY if the job's "
    "role/occupation is the same family as the candidate's target job family) and "
    "evidence (string: the job title + core responsibilities vs the target role).\n"
    "- disqualifiers: an array of strings for HARD blockers grounded in the JD (missing "
    "mandatory license/clearance/visa, a hard location conflict, or seniority off by >1 "
    "level); empty array if none.\n"
    "If is_same_role_family is false OR disqualifiers is non-empty, the fit_score will be "
    "CAPPED AT 3 in code — score it that low, do not inflate.\n"
    "Worked anchors — negative: a 'Staff Software Engineer, Inference' role at a top-tier "
    "AI lab for a Technical Program Manager candidate → role_match.is_same_role_family = "
    "false; SWE ≠ TPM, so FIT ~2/10 even though prestige/domain are high (that love goes "
    "to desire). Positive: a 'Technical Program Manager, AI Platform' role for that same "
    "candidate with matching domain + seniority → is_same_role_family = true, FIT ~8-9/10.\n\n"
)


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


class ProviderUnavailableError(Exception):
    """Raised when an AI provider returns 404 / model-routing failure / similar
    "service unavailable" indicators (e.g., OpenRouter 'no allowed providers
    available for the selected model'). Distinct from quota exhaustion: the
    provider has capacity but cannot serve the requested model.
    """

    def __init__(self, provider: str, status_code: int, detail: str = "") -> None:
        self.provider = provider
        self.status_code = status_code
        message = f"{provider} unavailable (HTTP {status_code})."
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
