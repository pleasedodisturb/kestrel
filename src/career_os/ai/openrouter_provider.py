"""OpenRouter AI provider.

Connects to the OpenRouter API (https://openrouter.ai) for AI completions.
Requires OPENROUTER_API_KEY in environment.
"""

import json
import logging

import httpx

from career_os.ai.base import AIProvider
from career_os.schemas.ai import (
    AIFeature,
    AIResponse,
    CoachingResult,
    CompanyResearchResult,
    GapAnalysisResult,
    GoalRecalibrationResult,
    InterviewFormatResult,
    InterviewPatternsResult,
    InterviewPrepResult,
    LearningRecommendationsResult,
    ScoreResult,
)

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "anthropic/claude-sonnet-4"


class CreditsExhaustedError(Exception):
    """Raised when OpenRouter returns 402 or 429 indicating credits/quota exhaustion."""

    def __init__(self, status_code: int, detail: str = "") -> None:
        self.status_code = status_code
        message = (
            f"OpenRouter credits exhausted (HTTP {status_code}). "
            "Add credits at https://openrouter.ai"
        )
        if detail:
            message += f": {detail}"
        super().__init__(message)


class OpenRouterProvider(AIProvider):
    """AI provider backed by OpenRouter API."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        """Initialize with API key and optional model override.

        Args:
            api_key: OpenRouter API key.
            model: Model identifier (default: anthropic/claude-sonnet-4).
        """
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is required for OpenRouterProvider")
        self._api_key = api_key
        self._model = model

    @property
    def name(self) -> str:
        return "openrouter"

    async def complete(
        self,
        prompt: str,
        *,
        feature: AIFeature = AIFeature.complete,
        context: dict | None = None,
        **kwargs: object,
    ) -> AIResponse:
        """Send a completion request to OpenRouter."""
        messages = [{"role": "user", "content": prompt}]

        # Add system message for structured features
        system_msg = _system_prompt_for_feature(feature)
        if system_msg:
            messages.insert(0, {"role": "system", "content": system_msg})

        payload = {
            "model": self._model,
            "messages": messages,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://career-os.local",
                    "X-Title": "Career OS",
                },
                json=payload,
            )
            if response.status_code in (402, 429):
                detail = ""
                try:
                    body = response.json()
                    detail = body.get("error", {}).get("message", "")
                except Exception:
                    pass
                raise CreditsExhaustedError(status_code=response.status_code, detail=detail)
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        model_used = data.get("model", self._model)

        # Try to parse structured data for known features
        structured = _try_parse_structured(content, feature)

        return AIResponse(
            content=content,
            provider="openrouter",
            feature=feature,
            structured=structured,
            model=model_used,
        )

    async def score(
        self,
        job_description: str,
        profile_data: dict,
        **kwargs: object,
    ) -> AIResponse:
        """Score a job against a profile via OpenRouter."""
        prompt = (
            f"Score this job against the candidate profile. "
            f"Return a JSON object with: fit_score (0-10), reasoning (detailed, ≥100 chars), "
            f"estimated_salary (string), effort_flag (low/medium/high), prep_level, prep_notes, "
            f"readiness_score (0-100), career_alignment (0-10), "
            f"score_breakdown (array of ≥3 objects, each with: factor (string), "
            f"contribution (positive or negative float), description (string)).\n\n"
            f"Job Description:\n{job_description}\n\n"
            f"Profile:\n{json.dumps(profile_data, indent=2)}"
        )
        return await self.complete(prompt, feature=AIFeature.score)


def _system_prompt_for_feature(feature: AIFeature) -> str | None:
    """Return a system prompt tailored to the feature type."""
    prompts: dict[AIFeature, str] = {
        AIFeature.score: (
            "You are a career scoring AI. Return valid JSON matching the ScoreResult schema: "
            "fit_score (0-10), reasoning (≥100 chars with ≥3 specific factors), "
            "estimated_salary, effort_flag, prep_level, prep_notes, "
            "readiness_score (0-100), career_alignment (0-10), "
            "score_breakdown (REQUIRED array of ≥3 objects, each with: "
            "factor (string), contribution (positive or negative float), "
            "description (string explaining impact))."
        ),
        AIFeature.gap_analysis: (
            "You are a skills gap analysis AI. Return valid JSON with: gaps (list of "
            "{skill_name, required_level, current_level, severity, distance}), "
            "readiness_score (0-100), summary."
        ),
        AIFeature.coaching: (
            "You are a career coaching AI. Return valid JSON with: suggestions (list of "
            "{action, hours, weeks, difficulty, priority}), focus_area."
        ),
        AIFeature.goal_recalibration: (
            "You are a career goal recalibration AI. Return valid JSON with: "
            "recalibration_notes, suggested_adjustments (list), market_reality."
        ),
        AIFeature.interview_prep: (
            "You are an interview preparation AI. Return valid JSON with: topics (list), "
            "questions (list of ≥5), checklist (list with time_minutes), total_prep_hours."
        ),
        AIFeature.company_research: (
            "You are a company research AI. Return valid JSON with: tech_stack (dict with "
            "frontend/backend/infrastructure/analytics lists), funding (dict with stage, "
            "total_raised, lead_investor, last_round_date), glassdoor (dict with "
            "overall_rating, ceo_approval, culture_keywords, work_life_balance), "
            "values_alignment (dict with score 0-10 and rationale string), ats_platform "
            "(string or null), hiring_patterns (dict with active_postings, posting_velocity, "
            "top_departments), industry_segment (string), employee_count (string or null), "
            "news (list of {title, url, date, summary} or null)."
        ),
        AIFeature.learning_recommendations: (
            "You are a learning path recommender. Return valid JSON with: recommendations "
            "(list of {title, url, hours, provider, difficulty, type}), total_hours."
        ),
        AIFeature.interview_format: (
            "You are an interview format AI. Return valid JSON with: rounds (list of "
            "{round_number (int), type (string), description (string), duration_minutes (int)}), "
            "total_duration (string, e.g., '3-4 weeks'), "
            "process_description (string describing the overall interview process)."
        ),
        AIFeature.interview_patterns: (
            "You are an interview patterns AI. Return valid JSON with: question_categories "
            "(list of {name, description, example_questions (list of strings)}), "
            "assessment_criteria (list of {name, description}), "
            "frequently_tested_skills (list of strings)."
        ),
    }
    return prompts.get(feature)


def _try_parse_structured(
    content: str, feature: AIFeature
) -> (
    ScoreResult
    | GapAnalysisResult
    | CoachingResult
    | GoalRecalibrationResult
    | InterviewPrepResult
    | CompanyResearchResult
    | LearningRecommendationsResult
    | InterviewFormatResult
    | InterviewPatternsResult
    | None
):
    """Attempt to parse structured data from raw LLM content.

    Maps each ``AIFeature`` to its corresponding Pydantic schema and
    validates the extracted JSON.  Returns ``None`` when the feature is
    ``complete`` (unstructured) or when parsing/validation fails.
    """
    if feature == AIFeature.complete:
        return None

    try:
        # Try to extract JSON from the content (may be wrapped in markdown code block)
        text = content.strip()
        if text.startswith("```"):
            # Strip markdown code fences
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
        data = json.loads(text)

        schema_map: dict[AIFeature, type] = {
            AIFeature.score: ScoreResult,
            AIFeature.gap_analysis: GapAnalysisResult,
            AIFeature.coaching: CoachingResult,
            AIFeature.goal_recalibration: GoalRecalibrationResult,
            AIFeature.interview_prep: InterviewPrepResult,
            AIFeature.company_research: CompanyResearchResult,
            AIFeature.learning_recommendations: LearningRecommendationsResult,
            AIFeature.interview_format: InterviewFormatResult,
            AIFeature.interview_patterns: InterviewPatternsResult,
        }
        schema_cls = schema_map.get(feature)
        if schema_cls:
            return schema_cls.model_validate(data)
    except (json.JSONDecodeError, Exception) as exc:
        logger.debug("Could not parse structured response for %s: %s", feature, exc)

    return None
