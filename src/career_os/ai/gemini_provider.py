"""Google Gemini AI provider.

Connects to the Gemini REST API (https://generativelanguage.googleapis.com)
for AI completions.  Unlike OpenRouter/Together, Gemini uses Google's own
request format — NOT OpenAI-compatible.  Auth is via API key query parameter.

Requires GEMINI_API_KEY in environment.
"""

import json
import logging

import httpx

from career_os.ai.base import (
    ROLE_FIT_GATE_PROMPT,
    AIProvider,
    ProviderQuotaError,
    ProviderUnavailableError,
)
from career_os.ai.openrouter_provider import (
    _SCHEMA_MAP,
    _system_prompt_for_feature,
    _try_parse_structured,
)
from career_os.schemas.ai import AIFeature, AIResponse, TokenUsage

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-2.0-flash"


class GeminiProvider(AIProvider):
    """AI provider backed by the Google Gemini REST API.

    Privacy tier: **yellow** — free-tier usage trains Google's models.
    EU users should use the paid tier for data-processing-only guarantees.
    """

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        """Initialize with API key and optional model override.

        Args:
            api_key: Google Gemini API key.
            model: Model identifier (default: gemini-2.0-flash).
        """
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required for GeminiProvider")
        self._api_key = api_key
        self._model = model
        logger.warning("Gemini free tier: data used for training. EU users should use paid tier.")

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def privacy_tier(self) -> str:
        """Gemini free tier trains on data, EU users restricted — yellow tier."""
        return "yellow"

    def _build_url(self) -> str:
        """Build the generateContent URL for the configured model."""
        return f"{GEMINI_API_BASE}/{self._model}:generateContent"

    async def complete(
        self,
        prompt: str,
        *,
        feature: AIFeature = AIFeature.complete,
        context: dict | None = None,
        max_retries: int = 1,
        **kwargs: object,
    ) -> AIResponse:
        """Send a completion request to the Gemini API."""
        expects_structured = feature in _SCHEMA_MAP

        for attempt in range(1, max_retries + 2):
            user_content = prompt
            if attempt > 1:
                user_content += (
                    "\n\nIMPORTANT: Return ONLY valid JSON"
                    " with no surrounding text or markdown fences."
                )

            payload: dict = {
                "contents": [{"parts": [{"text": user_content}]}],
            }

            # Add system instruction for structured features
            system_msg = _system_prompt_for_feature(feature)
            if system_msg:
                payload["systemInstruction"] = {"parts": [{"text": system_msg}]}

            url = self._build_url()
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    url,
                    params={"key": self._api_key},
                    headers={"Content-Type": "application/json"},
                    json=payload,
                )
                if response.status_code == 429:
                    detail = _extract_error_detail(response)
                    raise ProviderQuotaError("gemini", response.status_code, detail)
                # Gemini auth uses ?key=<API_KEY> as a URL query param. Letting
                # response.raise_for_status() propagate would embed that URL
                # (with the key) in httpx.HTTPStatusError.__str__, which then
                # leaks into job["fit_reasoning"], the digest, artifacts, and
                # email. Translate non-2xx into a sanitized ProviderUnavailable
                # error before any URL/key reaches an exception string.
                if response.status_code >= 400:
                    detail = _extract_error_detail(response) or "see logs"
                    raise ProviderUnavailableError("gemini", response.status_code, detail)
                data = response.json()

            content = data["candidates"][0]["content"]["parts"][0]["text"]

            # Extract token usage from Gemini usageMetadata
            usage_meta = data.get("usageMetadata", {})
            usage = TokenUsage(
                input_tokens=usage_meta.get("promptTokenCount", 0),
                output_tokens=usage_meta.get("candidatesTokenCount", 0),
            )

            # Try to parse structured data for known features
            structured = _try_parse_structured(content, feature)

            if structured is not None or not expects_structured:
                return AIResponse(
                    content=content,
                    provider="gemini",
                    feature=feature,
                    structured=structured,
                    model=self._model,
                    usage=usage,
                )

            # Structured parse failed — retry if we have attempts left
            if attempt <= max_retries:
                logger.warning(
                    "Structured parse failed for %s, retrying (attempt %d/%d)",
                    feature,
                    attempt,
                    max_retries + 1,
                )

        # Exhausted retries — return last response without structured data
        return AIResponse(
            content=content,
            provider="gemini",
            feature=feature,
            structured=None,
            model=self._model,
            usage=usage,
        )

    async def score(
        self,
        job_description: str,
        profile_data: dict,
        **kwargs: object,
    ) -> AIResponse:
        """Score a job against a profile via the Gemini API."""
        prompt = (
            ROLE_FIT_GATE_PROMPT + f"Score this job against the candidate profile. "
            f"Return a JSON object with: fit_score (0-10), reasoning (detailed, >=100 chars), "
            f"estimated_salary (string), effort_flag (low/medium/high), prep_level, prep_notes, "
            f"readiness_score (0-100), career_alignment (0-10), "
            f"score_breakdown (array of >=3 objects, each with: factor (string), "
            f"contribution (positive or negative float), description (string)), "
            f"dimensional_scores (object with 6 floats 0-10: technical_fit, "
            f"seniority_alignment, compensation_fit, location_fit, career_trajectory, "
            f"company_fit), "
            f"ats_keywords (array of 10-15 objects, each with: keyword (string), "
            f"category (one of technical/soft_skill/tool/certification/domain), "
            f"matched (boolean -- true if the profile demonstrates this keyword)), "
            f"desire_score (0-10, how much the candidate would WANT this job -- "
            f"considering company reputation, growth potential, culture signals, "
            f"role excitement, compensation attractiveness, work-life balance), "
            f"desire_reasoning (string explaining what makes this job desirable "
            f"or undesirable from the candidate's perspective).\n\n"
            f"Job Description:\n{job_description}\n\n"
            f"Profile:\n{json.dumps(profile_data, indent=2)}"
        )
        return await self.complete(prompt, feature=AIFeature.score)


def _extract_error_detail(response: httpx.Response) -> str:
    """Best-effort extraction of error message from a Gemini error response."""
    try:
        body = response.json()
        error = body.get("error", {})
        return error.get("message", "") if isinstance(error, dict) else str(error)
    except Exception:
        return ""
