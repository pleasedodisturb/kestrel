"""OpenRouter AI provider.

Connects to the OpenRouter API (https://openrouter.ai) for AI completions.
Requires OPENROUTER_API_KEY in environment.
"""

import json
import logging
import re

import httpx

from career_os.ai.base import AIProvider, ComplexityTier
from career_os.ai.observability import observe, update_current_generation
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
    TokenUsage,
)

logger = logging.getLogger(__name__)

# Compact JSON separators — eliminates whitespace tokens (~30% reduction on profile data)
_COMPACT = (",", ":")

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


def _extract_error_detail(response: httpx.Response) -> str:
    """Best-effort extraction of error message from an OpenRouter error response."""
    try:
        body = response.json()
        return body.get("error", {}).get("message", "")
    except Exception:
        return ""


_TIER_MODELS: dict[ComplexityTier, str] = {
    ComplexityTier.SIMPLE: "anthropic/claude-haiku-4-5",
    ComplexityTier.STANDARD: "anthropic/claude-sonnet-4",
    ComplexityTier.COMPLEX: "anthropic/claude-opus-4",
}


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

    def _resolve_model(self, tier: ComplexityTier | None) -> str:
        """Return the model to use for a request.

        If the provider was constructed with an explicit model override,
        that always wins.  Otherwise, the tier selects the model from
        ``_TIER_MODELS``.  If tier is None, STANDARD is used.
        """
        if self._model != DEFAULT_MODEL:
            return self._model
        effective_tier = tier or ComplexityTier.STANDARD
        return _TIER_MODELS[effective_tier]

    @observe(name="openrouter-complete", as_type="generation")
    async def complete(
        self,
        prompt: str,
        *,
        feature: AIFeature = AIFeature.complete,
        context: dict | None = None,
        tier: ComplexityTier | None = None,
        max_retries: int = 1,
        **kwargs: object,
    ) -> AIResponse:
        """Send a completion request to OpenRouter."""
        model = self._resolve_model(tier)
        update_current_generation(
            model=model,
            metadata={"feature": feature.value, "tier": (tier or "standard")},
        )
        expects_structured = feature in _SCHEMA_MAP

        for attempt in range(1, max_retries + 2):  # 1-based, up to max_retries+1
            user_content = prompt
            if attempt > 1:
                user_content += (
                    "\n\nIMPORTANT: Return ONLY valid JSON"
                    " with no surrounding text or markdown fences."
                )

            messages: list[dict[str, str]] = [
                {"role": "user", "content": user_content},
            ]

            # Add system message for structured features
            system_msg = _system_prompt_for_feature(feature)
            if system_msg:
                messages.insert(0, {"role": "system", "content": system_msg})

            payload = {
                "model": model,
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
                    detail = _extract_error_detail(response)
                    raise CreditsExhaustedError(status_code=response.status_code, detail=detail)
                response.raise_for_status()
                data = response.json()

            content = data["choices"][0]["message"]["content"]
            model_used = data.get("model", self._model)

            # Extract token usage from OpenAI-format response
            usage_data = data.get("usage", {})
            usage = TokenUsage(
                input_tokens=usage_data.get("prompt_tokens", 0),
                output_tokens=usage_data.get("completion_tokens", 0),
            )

            # Try to parse structured data for known features
            structured = _try_parse_structured(content, feature)

            if structured is not None or not expects_structured:
                update_current_generation(
                    usage_details={
                        "input": usage.input_tokens,
                        "output": usage.output_tokens,
                    },
                )
                return AIResponse(
                    content=content,
                    provider="openrouter",
                    feature=feature,
                    structured=structured,
                    model=model_used,
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
            provider="openrouter",
            feature=feature,
            structured=None,
            model=model_used,
        )

    async def score(
        self,
        job_description: str,
        profile_data: dict,
        *,
        tier: ComplexityTier | None = None,
        **kwargs: object,
    ) -> AIResponse:
        """Score a job against a profile via OpenRouter."""
        prompt = (
            f"Score this job against the candidate profile. "
            f"Return a JSON object with: fit_score (0-10), reasoning (detailed, ≥100 chars), "
            f"estimated_salary (string), effort_flag (low/medium/high), prep_level, prep_notes, "
            f"readiness_score (0-100), career_alignment (0-10), "
            f"score_breakdown (array of ≥3 objects, each with: factor (string), "
            f"contribution (positive or negative float), description (string)), "
            f"dimensional_scores (object with 6 floats 0-10: technical_fit, "
            f"seniority_alignment, compensation_fit, location_fit, career_trajectory, "
            f"company_fit), "
            f"ats_keywords (array of 10-15 objects, each with: keyword (string), "
            f"category (one of technical/soft_skill/tool/certification/domain), "
            f"matched (boolean — true if the profile demonstrates this keyword)), "
            f"desire_score (0-10, how much the candidate would WANT this job — "
            f"considering company reputation, growth potential, culture signals, "
            f"role excitement, compensation attractiveness, work-life balance), "
            f"desire_reasoning (string explaining what makes this job desirable "
            f"or undesirable from the candidate's perspective).\n\n"
            f"Job Description:\n{job_description}\n\n"
            f"Profile:\n{json.dumps(profile_data, separators=_COMPACT)}"
        )
        return await self.complete(prompt, feature=AIFeature.score, tier=tier)


def _system_prompt_for_feature(feature: AIFeature) -> str | None:
    """Return a compressed system prompt tailored to the feature type.

    Prompts use telegraphic notation to minimize token count while preserving
    all schema constraints. Compression techniques: remove filler words, use
    shorthand types (:str, :0-10), inline options with |, enumerate with ×.
    """
    prompts: dict[AIFeature, str] = {
        AIFeature.score: (
            "Career scoring AI. Valid JSON output:\n"
            "fit_score:0-10, reasoning:str≥100ch with ≥3 factors, "
            "estimated_salary:str, effort_flag:low|medium|high, "
            "prep_level:str, prep_notes:str, "
            "readiness_score:0-100, career_alignment:0-10, "
            "score_breakdown:[≥3×{factor:str, contribution:±float, description:str}], "
            "dimensional_scores:{technical_fit,seniority_alignment,compensation_fit,"
            "location_fit,career_trajectory,company_fit}:each 0-10, "
            "ats_keywords:[10-15×{keyword:str, "
            "category:technical|soft_skill|tool|certification|domain, "
            "matched:bool (true iff profile demonstrates it)}]."
        ),
        AIFeature.gap_analysis: (
            "Skills gap analysis AI. Valid JSON: "
            "gaps:[{skill_name,required_level,current_level,severity,distance}], "
            "readiness_score:0-100, summary:str."
        ),
        AIFeature.coaching: (
            "Career coaching AI. Valid JSON: "
            "suggestions:[{action,hours,weeks,difficulty,priority}], focus_area:str."
        ),
        AIFeature.goal_recalibration: (
            "Goal recalibration AI. Valid JSON: "
            "recalibration_notes:str, suggested_adjustments:list, market_reality:str."
        ),
        AIFeature.interview_prep: (
            "Interview prep AI. Valid JSON: "
            "topics:list, questions:[≥5], checklist:[{...,time_minutes}], total_prep_hours:num."
        ),
        AIFeature.company_research: (
            "Company research AI. Valid JSON:\n"
            "tech_stack:{frontend,backend,infrastructure,analytics:[str]}, "
            "funding:{stage,total_raised,lead_investor,last_round_date}, "
            "glassdoor:{overall_rating,ceo_approval,culture_keywords,work_life_balance}, "
            "values_alignment:{score:0-10,rationale:str}, ats_platform:str|null, "
            "hiring_patterns:{active_postings,posting_velocity,top_departments}, "
            "industry_segment:str, employee_count:str|null, "
            "news:[{title,url,date,summary}]|null."
        ),
        AIFeature.learning_recommendations: (
            "Learning recommender. Valid JSON: "
            "recommendations:[{title,url,hours,provider,difficulty,type}], total_hours:num."
        ),
        AIFeature.interview_format: (
            "Interview format AI. Valid JSON: "
            "rounds:[{round_number:int,type:str,description:str,duration_minutes:int}], "
            "total_duration:str (e.g. '3-4 weeks'), process_description:str."
        ),
        AIFeature.interview_patterns: (
            "Interview patterns AI. Valid JSON: "
            "question_categories:[{name,description,example_questions:[str]}], "
            "assessment_criteria:[{name,description}], frequently_tested_skills:[str]."
        ),
    }
    return prompts.get(feature)


_SCHEMA_MAP: dict[AIFeature, type] = {
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


def _extract_first_json_object(text: str) -> str | None:
    """Extract the first top-level ``{...}`` block using brace-depth counting.

    Returns the substring from the first ``{`` to its matching ``}`` or
    ``None`` if no balanced block is found.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            if in_string:
                escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


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
            # Handle partial closing fence too
            end = -1 if lines[-1].startswith("```") else len(lines)
            text = "\n".join(lines[1:end]) if len(lines) > 2 else text

        # Strip trailing commas before } or ] (common LLM artifact)
        text = re.sub(r",\s*([}\]])", r"\1", text)

        # Try direct parse first
        data = None
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try extracting the first JSON object from surrounding text
            extracted = _extract_first_json_object(text)
            if extracted:
                extracted = re.sub(r",\s*([}\]])", r"\1", extracted)
                data = json.loads(extracted)

        if data is None:
            raise ValueError("No JSON object found in content")

        schema_cls = _SCHEMA_MAP.get(feature)
        if schema_cls:
            return schema_cls.model_validate(data)
    except Exception as exc:
        logger.warning(
            "Could not parse structured response for %s: %s | raw (first 200 chars): %.200s",
            feature,
            exc,
            content,
        )

    return None
