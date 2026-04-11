"""Mock AI provider returning deterministic structured responses.

Used for testing and development. Returns valid schema responses for every
AI-dependent feature across M2-M5.
"""

import hashlib

from career_os.ai.base import AIProvider
from career_os.schemas.ai import (
    AIFeature,
    AIResponse,
    ATSKeyword,
    CoachingResult,
    CompanyResearchResult,
    DimensionalScores,
    GapAnalysisResult,
    GoalRecalibrationResult,
    InterviewFormatResult,
    InterviewPatternsResult,
    InterviewPrepResult,
    LearningRecommendationsResult,
    ScoreBreakdownFactor,
    ScoreResult,
)

# Static pool of 12 keywords used by the mock provider to build a deterministic
# ATS checklist. Distinct categories so the UI checklist has variety to show.
_MOCK_ATS_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("Python", "technical"),
    ("React", "technical"),
    ("TypeScript", "technical"),
    ("FastAPI", "technical"),
    ("PostgreSQL", "technical"),
    ("Docker", "tool"),
    ("Kubernetes", "tool"),
    ("AWS", "tool"),
    ("Terraform", "tool"),
    ("Communication", "soft_skill"),
    ("Agile/Scrum", "domain"),
    ("AWS Solutions Architect", "certification"),
)


class MockProvider(AIProvider):
    """Mock AI provider returning deterministic, schema-valid responses."""

    @property
    def name(self) -> str:
        return "mock"

    async def complete(
        self,
        prompt: str,
        *,
        feature: AIFeature = AIFeature.complete,
        context: dict | None = None,
        **kwargs: object,
    ) -> AIResponse:
        """Return deterministic response based on feature type."""
        handler = _FEATURE_HANDLERS.get(feature, _handle_complete)
        return handler(prompt, context)

    async def score(
        self,
        job_description: str,
        profile_data: dict,
        **kwargs: object,
    ) -> AIResponse:
        """Return deterministic scoring response."""
        return _handle_score(job_description, {"profile": profile_data})


def _deterministic_seed(text: str) -> int:
    """Produce a deterministic integer seed from input text."""
    return int(hashlib.md5(text.encode()).hexdigest()[:8], 16)


# ---------------------------------------------------------------------------
# Feature handlers — one per AIFeature
# ---------------------------------------------------------------------------


def _handle_complete(prompt: str, context: dict | None) -> AIResponse:
    """Generic completion — no structured data."""
    return AIResponse(
        content=f"Mock AI response to: {prompt[:120]}",
        provider="mock",
        feature=AIFeature.complete,
        structured=None,
        model="mock-v1",
    )


def _compute_career_alignment(base: float, prompt: str, context: dict | None) -> float:
    """Compute career_alignment incorporating active goals (VAL-SCORE-003).

    If profile data contains goals, we check keyword overlap between each
    goal's title/description and the job prompt.  More overlap → higher
    career_alignment (up to 10.0).  No goals → base value unchanged.
    """
    goals: list[dict] = []
    if context and "profile" in context:
        goals = context["profile"].get("goals", [])
    elif context:
        goals = context.get("goals", [])

    if not goals:
        return base

    prompt_lower = prompt.lower()

    # Count how many goals have meaningful keyword overlap with the prompt
    matching_goals = 0
    for goal in goals:
        goal_text = f"{goal.get('title', '')} {goal.get('description', '')}".lower()
        goal_words = {w for w in goal_text.split() if len(w) > 3}  # skip short words
        if any(word in prompt_lower for word in goal_words):
            matching_goals += 1

    if matching_goals == 0:
        return base

    # Boost: +1.5 per matching goal, capped at 10.0
    boost = matching_goals * 1.5
    return min(10.0, round(base + boost, 1))


def _handle_score(prompt: str, context: dict | None) -> AIResponse:
    """Scoring response with deterministic but varied scores.

    Different job descriptions produce different (but deterministic) scores.
    The seed is derived from the prompt content, so the same job always gets
    the same score, but different jobs get different scores.

    If context contains 'weights', those weights influence the score variation
    to satisfy VAL-SCORE-005 (weight changes produce different results).

    Career alignment is influenced by active goals: if goal keywords overlap
    with the job prompt, career_alignment receives a measurable boost
    (VAL-SCORE-003).
    """
    seed = _deterministic_seed(prompt)

    # Include weights in seed if provided (so weight changes produce different scores)
    weights_str = ""
    if context and "profile" in context and "weights" in context["profile"]:
        weights_str = str(context["profile"]["weights"])
    elif context and "weights" in context:
        weights_str = str(context["weights"])
    if weights_str:
        seed = (seed + _deterministic_seed(weights_str)) % (2**32)

    fit = round(1.0 + (seed % 90) / 10.0, 1)  # 1.0–9.9
    fit = min(fit, 10.0)
    readiness = round(20.0 + (seed % 800) / 10.0, 1)  # 20–99.9
    readiness = min(readiness, 100.0)

    # Career alignment: base from seed, boosted by goal overlap (VAL-SCORE-003)
    career_base = round(1.0 + (seed % 90) / 10.0, 1)  # 1.0–9.9
    career_base = min(career_base, 10.0)
    career = _compute_career_alignment(career_base, prompt, context)

    # Vary effort and prep level based on seed
    effort_flags = ["low", "medium", "high"]
    prep_levels = ["light", "moderate", "intensive"]
    effort_flag = effort_flags[seed % 3]
    prep_level = prep_levels[(seed // 3) % 3]

    # Generate salary estimate that varies
    base_salary = 100000 + (seed % 8) * 10000
    salary_high = base_salary + 30000
    estimated_salary = f"{base_salary:,}–{salary_high:,} EUR"

    # Build score breakdown factors (always ≥3 with +/- contributions)
    breakdown_factors = [
        ScoreBreakdownFactor(
            factor="Technical Leadership Skills",
            contribution=round((seed % 5 + 1) * 0.5, 1),
            description="Strong alignment on technical leadership skills",
        ),
        ScoreBreakdownFactor(
            factor="AI/ML Program Management",
            contribution=round((seed % 4 + 1) * 0.3, 1),
            description="Profile shows relevant AI/ML program management experience",
        ),
        ScoreBreakdownFactor(
            factor="Location Match",
            contribution=round((seed % 3 + 1) * 0.4, 1),
            description="Location preference matches target region",
        ),
        ScoreBreakdownFactor(
            factor="Industry Domain Gap",
            contribution=round(-((seed % 3 + 1) * 0.2), 1),
            description="Minor gap in specific industry domain",
        ),
        ScoreBreakdownFactor(
            factor="Career Trajectory",
            contribution=round((seed % 4 + 1) * 0.3, 1),
            description="Career trajectory alignment with role growth potential",
        ),
    ]

    # Build a multi-factor reasoning string (always ≥100 chars, ≥3 factors)
    factors = [
        f"Strong alignment on technical leadership skills (+{(seed % 5 + 1) * 0.5:.1f})",
        f"Profile shows relevant AI/ML program management experience (+{(seed % 4 + 1) * 0.3:.1f})",
        f"Location preference matches target region (+{(seed % 3 + 1) * 0.4:.1f})",
        f"Minor gap in specific industry domain (−{(seed % 3 + 1) * 0.2:.1f})",
        f"Career trajectory alignment with role growth potential (+{(seed % 4 + 1) * 0.3:.1f})",
    ]
    reasoning = ". ".join(factors) + f". Overall a solid fit with score {fit}/10."

    # Dimensional sub-scores: six deterministic floats derived from the seed.
    # Each dimension gets a distinct seed offset so they're not all the same
    # value, but they're all bounded to [0, 10].
    def _dim(offset: int) -> float:
        return round(((seed + offset * 7) % 101) / 10.0, 1)

    dimensional = DimensionalScores(
        technical_fit=_dim(0),
        seniority_alignment=_dim(1),
        compensation_fit=_dim(2),
        location_fit=_dim(3),
        career_trajectory=_dim(4),
        company_fit=_dim(5),
    )

    # ATS keywords: all 12 from the static pool, with seed-derived matched flag
    # and the category pre-assigned in the pool.
    ats_keywords = [
        ATSKeyword(
            keyword=keyword,
            category=category,  # type: ignore[arg-type]
            matched=((seed + idx) % 2 == 0),
        )
        for idx, (keyword, category) in enumerate(_MOCK_ATS_KEYWORDS)
    ]

    structured = ScoreResult(
        fit_score=fit,
        reasoning=reasoning,
        estimated_salary=estimated_salary,
        effort_flag=effort_flag,
        prep_level=prep_level,
        prep_notes=(
            f"Brush up on domain-specific terminology and prepare {(seed % 3) + 2} STAR stories."
        ),
        readiness_score=readiness,
        career_alignment=career,
        score_breakdown=breakdown_factors,
        dimensional_scores=dimensional,
        ats_keywords=ats_keywords,
    )
    return AIResponse(
        content=structured.reasoning,
        provider="mock",
        feature=AIFeature.score,
        structured=structured,
        model="mock-v1",
    )


def _handle_gap_analysis(prompt: str, context: dict | None) -> AIResponse:
    """Gap analysis with deterministic gaps."""
    structured = GapAnalysisResult(
        gaps=[
            {
                "skill_name": "Kubernetes",
                "required_level": "advanced",
                "current_level": "intermediate",
                "severity": "nice_to_have",
                "distance": 1,
            },
            {
                "skill_name": "Terraform",
                "required_level": "intermediate",
                "current_level": "beginner",
                "severity": "critical",
                "distance": 2,
            },
            {
                "skill_name": "GraphQL",
                "required_level": "intermediate",
                "current_level": "none",
                "severity": "bonus",
                "distance": 3,
            },
        ],
        readiness_score=72.5,
        summary=(
            "Profile meets most core requirements. "
            "Terraform is the highest-priority gap (critical). "
            "Kubernetes needs a slight upgrade. GraphQL is a bonus."
        ),
    )
    return AIResponse(
        content=structured.summary,
        provider="mock",
        feature=AIFeature.gap_analysis,
        structured=structured,
        model="mock-v1",
    )


def _handle_coaching(prompt: str, context: dict | None) -> AIResponse:
    """Coaching suggestions response."""
    structured = CoachingResult(
        suggestions=[
            {
                "action": "Complete Terraform fundamentals course",
                "hours": 20,
                "weeks": 3,
                "difficulty": "medium",
                "priority": 1,
            },
            {
                "action": "Build a side project deploying to Kubernetes",
                "hours": 15,
                "weeks": 2,
                "difficulty": "medium",
                "priority": 2,
            },
            {
                "action": "Write 3 STAR stories covering leadership gaps",
                "hours": 4,
                "weeks": 1,
                "difficulty": "low",
                "priority": 3,
            },
            {
                "action": "Network with 5 professionals in target companies",
                "hours": 5,
                "weeks": 2,
                "difficulty": "low",
                "priority": 4,
            },
            {
                "action": "Update LinkedIn headline and about section",
                "hours": 2,
                "weeks": 1,
                "difficulty": "low",
                "priority": 5,
            },
        ],
        focus_area="Infrastructure as Code (Terraform)",
    )
    return AIResponse(
        content="Focus on closing the Terraform gap first — it appears in 6 of your top targets.",
        provider="mock",
        feature=AIFeature.coaching,
        structured=structured,
        model="mock-v1",
    )


def _handle_goal_recalibration(prompt: str, context: dict | None) -> AIResponse:
    """Goal recalibration response."""
    structured = GoalRecalibrationResult(
        recalibration_notes=(
            "Market data indicates strong demand for AI TPM roles in Frankfurt. "
            "Salary expectations of 120-160k EUR are realistic for your experience level. "
            "Consider expanding to fully remote EU roles to increase opportunity pool."
        ),
        suggested_adjustments=[
            {
                "goal": "Senior TPM at tier-1 tech",
                "adjustment": "Expand from Frankfurt-only to remote-EU",
                "reason": "3x more openings in remote-EU vs Frankfurt-only",
            },
            {
                "goal": "160k EUR base",
                "adjustment": "Target 140-160k for Frankfurt, 130-150k for remote",
                "reason": "Remote roles trade slight salary for flexibility",
            },
        ],
        market_reality=(
            "AI TPM roles up 23% YoY in DACH region. "
            "Average time-to-hire is 6-8 weeks. "
            "Remote-EU positions outnumber Frankfurt-local 3:1."
        ),
    )
    return AIResponse(
        content=structured.recalibration_notes,
        provider="mock",
        feature=AIFeature.goal_recalibration,
        structured=structured,
        model="mock-v1",
    )


def _extract_research_fields(
    research_data: dict,
) -> tuple[list[str], list, object, dict]:
    """Extract tech_stack, culture_keywords, values_score, hiring_patterns from research data.

    Handles tech_stack as either a dict (category -> list) or a flat list.
    Returns (tech_list, culture_keywords, values_score, hiring_patterns).
    """
    tech_stack = research_data.get("tech_stack", {})
    culture_keywords = research_data.get("culture", [])
    values_score = research_data.get("values_alignment_score")
    hiring_patterns = research_data.get("hiring_patterns", {})

    # Flatten tech stack for prompt inclusion
    tech_list: list[str] = []
    if isinstance(tech_stack, dict):
        for _cat, techs in tech_stack.items():
            if isinstance(techs, list):
                tech_list.extend(techs)
    elif isinstance(tech_stack, list):
        tech_list = list(tech_stack)

    return tech_list, culture_keywords, values_score, hiring_patterns


def _add_research_topics(
    topic_pool, tech_list, culture_keywords, values_score, hiring_patterns, company
):
    """Append research-derived topics to the topic pool (VAL-CROSS-009)."""
    if tech_list:
        topic_pool.append(
            {
                "topic": f"{company} tech stack deep-dive: {', '.join(tech_list[:4])}",
                "relevance": "high",
                "difficulty": "medium",
            }
        )
    if culture_keywords and isinstance(culture_keywords, list):
        topic_pool.append(
            {
                "topic": f"{company} culture fit: {', '.join(culture_keywords[:3])}",
                "relevance": "high",
                "difficulty": "low",
            }
        )
    if values_score is not None:
        topic_pool.append(
            {
                "topic": f"Values alignment discussion ({company}, score: {values_score}/10)",
                "relevance": "medium",
                "difficulty": "low",
            }
        )
    if not hiring_patterns or not hiring_patterns.get("top_departments"):
        return
    depts = hiring_patterns["top_departments"]
    if isinstance(depts, list) and depts:
        topic_pool.append(
            {
                "topic": f"{company} hiring focus areas: {', '.join(depts[:3])}",
                "relevance": "medium",
                "difficulty": "low",
            }
        )


def _add_gap_or_keyword_topics(topic_pool, gap_data, unresolved_gaps, prompt_lower):
    """Append gap-driven or keyword-fallback topics (VAL-CROSS-015)."""
    if gap_data:
        for gap in unresolved_gaps:
            skill = gap["skill_name"]
            distance = gap.get("distance", 1)
            severity = gap.get("severity", "nice-to-have")
            relevance = "high" if severity == "critical" else "medium"
            difficulty = "high" if distance >= 2 else "medium"
            topic_pool.append(
                {
                    "topic": f"Gap area: {skill} (distance {distance}, {severity})",
                    "relevance": relevance,
                    "difficulty": difficulty,
                }
            )
        return

    keyword_topics = {
        "kubernetes": {
            "topic": "Container orchestration and Kubernetes",
            "relevance": "high",
            "difficulty": "high",
        },
        "python": {
            "topic": "Python best practices and architecture",
            "relevance": "medium",
            "difficulty": "medium",
        },
    }
    for keyword, topic_entry in keyword_topics.items():
        if keyword in prompt_lower:
            topic_pool.append(topic_entry)


def _build_topic_pool(
    tech_list: list[str],
    culture_keywords: list,
    values_score: object,
    hiring_patterns: dict,
    unresolved_gaps: list[dict],
    unresolved_skill_names: set[str],
    gap_data: list[dict],
    role: str,
    company: str,
    prompt_lower: str,
) -> list[dict]:
    """Build the topic pool from research data, gaps, and prompt keywords.

    Returns the topic list capped at 7 items.
    """
    topic_pool = [
        {
            "topic": f"{company} engineering culture and values",
            "relevance": "high",
            "difficulty": "low",
        },
        {
            "topic": f"Technical leadership for {role}",
            "relevance": "high",
            "difficulty": "medium",
        },
        {
            "topic": f"System design relevant to {company}",
            "relevance": "medium",
            "difficulty": "high",
        },
    ]

    _add_research_topics(
        topic_pool, tech_list, culture_keywords, values_score, hiring_patterns, company
    )
    _add_gap_or_keyword_topics(topic_pool, gap_data, unresolved_gaps, prompt_lower)

    role_lower = role.lower()
    if ("program management" in prompt_lower or "tpm" in role_lower) and (
        not gap_data or "program management" in unresolved_skill_names
    ):
        topic_pool.append(
            {
                "topic": "Cross-functional program delivery",
                "relevance": "high",
                "difficulty": "medium",
            }
        )
    if "ai" in prompt_lower or "ml" in prompt_lower:
        topic_pool.append(
            {
                "topic": "AI/ML lifecycle and deployment strategies",
                "relevance": "high",
                "difficulty": "medium",
            }
        )

    # Ensure at least 3 topics
    if len(topic_pool) < 3:
        topic_pool.append(
            {
                "topic": "Behavioral interview preparation",
                "relevance": "medium",
                "difficulty": "low",
            }
        )

    return topic_pool[:7]  # Cap at 7


def _build_mock_questions(
    tech_list: list[str],
    culture_keywords: list,
    unresolved_gaps: list[dict],
    gap_data: list[dict],
    role: str,
    company: str,
    prompt_lower: str,
) -> list[dict]:
    """Build the practice questions list from context, research, and gaps.

    Returns the questions list capped at 8 items.
    """
    questions = [
        {
            "question": (
                "Tell me about a time you delivered a complex "
                f"project at a company similar to {company}."
            ),
            "category": "behavioral",
            "difficulty": "medium",
        },
        {
            "question": f"How would you approach the first 90 days as {role} at {company}?",
            "category": "product",
            "difficulty": "medium",
        },
        {
            "question": f"Walk me through your approach to technical decision-making for {role}.",
            "category": "technical",
            "difficulty": "high",
        },
        {
            "question": "How do you handle conflicting priorities from senior stakeholders?",
            "category": "behavioral",
            "difficulty": "low",
        },
        {
            "question": f"Design a system relevant to {company}'s domain at scale.",
            "category": "system_design",
            "difficulty": "high",
        },
    ]

    # Add research-derived questions (VAL-CROSS-009)
    if tech_list:
        questions.append(
            {
                "question": (
                    f"How would you work with {company}'s tech stack "
                    f"({', '.join(tech_list[:3])}) to deliver {role} objectives?"
                ),
                "category": "technical",
                "difficulty": "medium",
            }
        )
    if culture_keywords and isinstance(culture_keywords, list):
        questions.append(
            {
                "question": (
                    f"How do your working values align with {company}'s "
                    f"culture of {', '.join(culture_keywords[:2])}?"
                ),
                "category": "behavioral",
                "difficulty": "low",
            }
        )

    # VAL-CROSS-015: Add gap-targeted questions only for UNRESOLVED gaps
    if gap_data:
        for gap in unresolved_gaps:
            skill = gap["skill_name"]
            distance = gap.get("distance", 1)
            questions.append(
                {
                    "question": (
                        f"Describe your experience with {skill} and how you "
                        f"would close the gap to the required level for this role."
                    ),
                    "category": "technical",
                    "difficulty": "high" if distance >= 2 else "medium",
                }
            )
    else:
        # Fallback: keyword-based gap questions (legacy path)
        if "kubernetes" in prompt_lower:
            questions.append(
                {
                    "question": (
                        "Explain your experience with container "
                        "orchestration and Kubernetes in production."
                    ),
                    "category": "technical",
                    "difficulty": "high",
                }
            )
        if "program management" in prompt_lower:
            questions.append(
                {
                    "question": (
                        "Describe a program you managed with multiple interdependent workstreams."
                    ),
                    "category": "behavioral",
                    "difficulty": "medium",
                }
            )

    return questions[:8]  # Cap at 8


def _build_mock_checklist(
    tech_list: list[str],
    unresolved_gaps: list[dict],
    role: str,
    company: str,
) -> list[dict]:
    """Build the checklist items from context, research, and gaps."""
    checklist = [
        {
            "item": f"Research {company}'s recent news and product launches",
            "time_minutes": 30,
            "priority": "high",
        },
        {
            "item": f"Prepare 3 STAR stories relevant to {role}",
            "time_minutes": 45,
            "priority": "high",
        },
        {
            "item": f"Study {company}'s tech stack and engineering blog",
            "time_minutes": 30,
            "priority": "high",
        },
        {
            "item": f"Practice system design problems relevant to {company}'s domain",
            "time_minutes": 60,
            "priority": "medium",
        },
        {
            "item": "Prepare thoughtful questions about team and role",
            "time_minutes": 15,
            "priority": "medium",
        },
        {
            "item": "Review salary negotiation talking points",
            "time_minutes": 20,
            "priority": "low",
        },
    ]

    # Add research-derived checklist items (VAL-CROSS-009)
    if tech_list:
        checklist.append(
            {
                "item": f"Review {company}'s key technologies: {', '.join(tech_list[:3])}",
                "time_minutes": 30,
                "priority": "high",
            }
        )

    # VAL-CROSS-015: Add gap-specific checklist items for UNRESOLVED gaps
    for gap in unresolved_gaps:
        skill = gap["skill_name"]
        severity = gap.get("severity", "nice-to-have")
        priority = "high" if severity == "critical" else "medium"
        checklist.append(
            {
                "item": f"Study {skill} to close skill gap for {role}",
                "time_minutes": 30,
                "priority": priority,
            }
        )

    return checklist


def _handle_interview_prep(prompt: str, context: dict | None) -> AIResponse:
    """Interview preparation response — varies by application company/role.

    Derives topics, questions, and checklist items from the prompt context
    (company, role, gaps) so different applications produce different prep.

    When research_data is present in context (VAL-CROSS-009), incorporates
    company-specific tech stack, culture, values alignment, and hiring
    patterns into topics and questions.

    VAL-CROSS-015: Uses gap data (with distances) from context to drive
    topic generation. Unresolved gaps (distance > 0) produce focused topics;
    resolved gaps (distance 0) are omitted or de-emphasized.
    """
    prompt_lower = prompt.lower()

    # Extract company and role from context or prompt
    company = (context or {}).get("company", "")
    role = (context or {}).get("role", "")
    research_data = (context or {}).get("research_data") or {}
    gap_data: list[dict] = (context or {}).get("gaps") or []

    if not company:
        # Try to parse from prompt
        for line in prompt.split("\n"):
            if line.strip().startswith("Company:"):
                company = line.split(":", 1)[1].strip()
            elif line.strip().startswith("Role:"):
                role = line.split(":", 1)[1].strip()

    # --- Classify gaps by resolution status ---
    unresolved_gaps = [g for g in gap_data if g.get("distance", 1) > 0]
    unresolved_skill_names = {g["skill_name"].lower() for g in unresolved_gaps}

    # --- Extract research details for enrichment ---
    tech_list, culture_keywords, values_score, hiring_patterns = _extract_research_fields(
        research_data
    )

    # --- Build topics, questions, and checklist via helpers ---
    topics = _build_topic_pool(
        tech_list,
        culture_keywords,
        values_score,
        hiring_patterns,
        unresolved_gaps,
        unresolved_skill_names,
        gap_data,
        role,
        company,
        prompt_lower,
    )

    questions = _build_mock_questions(
        tech_list,
        culture_keywords,
        unresolved_gaps,
        gap_data,
        role,
        company,
        prompt_lower,
    )

    checklist = _build_mock_checklist(tech_list, unresolved_gaps, role, company)

    total_minutes = sum(item["time_minutes"] for item in checklist)
    total_hours = round(total_minutes / 60, 1)

    structured = InterviewPrepResult(
        topics=topics,
        questions=questions,
        checklist=checklist,
        total_prep_hours=total_hours,
    )
    return AIResponse(
        content=f"Personalized interview prep generated for {role} at {company}.",
        provider="mock",
        feature=AIFeature.interview_prep,
        structured=structured,
        model="mock-v1",
    )


def _handle_company_research(prompt: str, context: dict | None) -> AIResponse:
    """Company research response.

    Deterministic but varies by company name. Well-known companies get full
    data; obscure companies get partial data with empty sections. Different
    companies produce different values alignment scores.

    When context.simulate_partial=True (VAL-RESEARCH-009), returns partial
    data with missing sections to enable graceful degradation testing.
    """
    seed = _deterministic_seed(prompt)
    prompt_lower = prompt.lower()

    # VAL-RESEARCH-009: simulate_partial returns partial data with missing sections
    simulate_partial = (context or {}).get("simulate_partial", False)
    if simulate_partial:
        structured = CompanyResearchResult(
            tech_stack={
                "frontend": ["React", "TypeScript"],
                "backend": [],
                "infrastructure": [],
                "analytics": [],
            },
            funding={
                "stage": "Series B",
                "total_raised": "$50M",
                "lead_investor": None,
                "last_round_date": None,
            },
            glassdoor={
                "overall_rating": None,
                "ceo_approval": None,
                "culture_keywords": [],
                "work_life_balance": None,
            },
            values_alignment=5.0,
            ats_platform=None,
            hiring_patterns={
                "active_postings": None,
                "posting_velocity": None,
                "top_departments": [],
            },
            industry_segment=None,
            employee_count=None,
            news=[],
        )
        return AIResponse(
            content=(
                "Partial data returned (simulate_partial=true). "
                "Some sections are missing or incomplete."
            ),
            provider="mock",
            feature=AIFeature.company_research,
            structured=structured,
            model="mock-v1",
        )

    # Determine if this is an "obscure" company based on seed or keywords
    is_obscure = "obscure" in prompt_lower or "unknown" in prompt_lower

    # Well-known company data by keyword match
    if "stripe" in prompt_lower:
        structured = CompanyResearchResult(
            tech_stack={
                "frontend": ["React", "TypeScript", "Next.js"],
                "backend": ["Ruby", "Go", "Java", "Python"],
                "infrastructure": ["AWS", "Kubernetes", "Terraform"],
                "analytics": ["Spark", "Presto", "Redshift"],
            },
            funding={
                "stage": "Series I",
                "total_raised": "$8.7B",
                "lead_investor": "Sequoia Capital",
                "last_round_date": "2023-03",
            },
            glassdoor={
                "overall_rating": 4.3,
                "ceo_approval": 92,
                "culture_keywords": ["innovative", "meritocratic", "intense", "transparent"],
                "work_life_balance": 3.5,
            },
            values_alignment={
                "score": 8.5,
                "rationale": (
                    "Stripe strongly aligns with innovation and AI-first culture, "
                    "high autonomy and ownership, and collaborative engineering teams. "
                    "Known for transparency and impact-driven product development."
                ),
            },
            ats_platform="Greenhouse",
            hiring_patterns={
                "active_postings": 150,
                "posting_velocity": "30/month",
                "top_departments": ["Engineering", "Product", "Finance"],
            },
            industry_segment="Fintech / Payment Infrastructure",
            employee_count="8000-10000",
            news=[
                {
                    "title": "Stripe launches new AI-powered fraud detection",
                    "url": "https://stripe.com/blog/ai-fraud-detection",
                    "date": "2025-06-15",
                    "summary": "Stripe announced an AI-powered fraud detection system.",
                },
                {
                    "title": "Stripe expands European operations",
                    "url": "https://stripe.com/blog/europe-expansion",
                    "date": "2025-05-01",
                    "summary": "New offices in Frankfurt and Berlin.",
                },
            ],
        )
        return AIResponse(
            content=(
                "Company research completed for Stripe. "
                "Strong engineering culture with fintech focus."
            ),
            provider="mock",
            feature=AIFeature.company_research,
            structured=structured,
            model="mock-v1",
        )

    if "datadog" in prompt_lower:
        structured = CompanyResearchResult(
            tech_stack={
                "frontend": ["React", "TypeScript", "Ember.js"],
                "backend": ["Go", "Python", "Java"],
                "infrastructure": ["Kubernetes", "Terraform", "GCP", "AWS"],
                "analytics": ["Kafka", "Cassandra", "Druid"],
            },
            funding={
                "stage": "Public (DDOG)",
                "total_raised": "$648M",
                "lead_investor": "ICONIQ Growth",
                "last_round_date": "2019-09",
            },
            glassdoor={
                "overall_rating": 4.1,
                "ceo_approval": 88,
                "culture_keywords": ["fast-paced", "collaborative", "data-driven"],
                "work_life_balance": 3.6,
            },
            values_alignment={
                "score": 7.0,
                "rationale": (
                    "Datadog aligns well with collaborative engineering teams "
                    "and continuous learning culture. Fast-paced environment supports "
                    "impact-driven development but may challenge work-life balance."
                ),
            },
            ats_platform="Greenhouse",
            hiring_patterns={
                "active_postings": 200,
                "posting_velocity": "40/month",
                "top_departments": ["Engineering", "Sales", "Product"],
            },
            industry_segment="Enterprise SaaS / Observability Platform",
            employee_count="5000-7000",
            news=[
                {
                    "title": "Datadog launches new AI observability features",
                    "url": "https://datadog.com/blog/ai-observability",
                    "date": "2025-04-20",
                    "summary": "New ML-powered anomaly detection and root cause analysis.",
                },
            ],
        )
        return AIResponse(
            content=(
                "Company research completed for Datadog. "
                "Observability leader with strong engineering."
            ),
            provider="mock",
            feature=AIFeature.company_research,
            structured=structured,
            model="mock-v1",
        )

    if "evilcorp" in prompt_lower or "misaligned" in prompt_lower:
        # Company with low values alignment for testing VAL-RESEARCH-005
        structured = CompanyResearchResult(
            tech_stack={
                "frontend": ["jQuery", "Bootstrap"],
                "backend": ["PHP", "MySQL"],
                "infrastructure": ["On-premise", "VMware"],
                "analytics": ["Excel"],
            },
            funding={
                "stage": "Series A",
                "total_raised": "$5M",
                "lead_investor": "Generic VC",
                "last_round_date": "2022-06",
            },
            glassdoor={
                "overall_rating": 2.3,
                "ceo_approval": 35,
                "culture_keywords": ["micromanagement", "bureaucratic", "rigid"],
                "work_life_balance": 2.0,
            },
            values_alignment={
                "score": 2.0,
                "rationale": (
                    "Poor alignment with user's values. Micromanagement culture conflicts "
                    "with high autonomy and ownership. Rigid structure opposes innovation "
                    "and collaborative engineering teams."
                ),
            },
            ats_platform="Workday",
            hiring_patterns={
                "active_postings": 5,
                "posting_velocity": "1/month",
                "top_departments": ["Sales"],
            },
            industry_segment="Legacy Enterprise / Consulting",
            employee_count="200-500",
            news=[],
        )
        return AIResponse(
            content="Company research completed. Culture signals suggest poor alignment.",
            provider="mock",
            feature=AIFeature.company_research,
            structured=structured,
            model="mock-v1",
        )

    if is_obscure:
        # Obscure company: partial report with minimal data (VAL-RESEARCH-008)
        structured = CompanyResearchResult(
            tech_stack={
                "frontend": [],
                "backend": [],
                "infrastructure": [],
                "analytics": [],
            },
            funding={
                "stage": None,
                "total_raised": None,
                "lead_investor": None,
                "last_round_date": None,
            },
            glassdoor={
                "overall_rating": None,
                "ceo_approval": None,
                "culture_keywords": [],
                "work_life_balance": None,
            },
            values_alignment=5.0,
            ats_platform=None,
            hiring_patterns={
                "active_postings": None,
                "posting_velocity": None,
                "top_departments": [],
            },
            industry_segment=None,
            employee_count=None,
            news=[],
        )
        return AIResponse(
            content="Limited data available. Company appears to be a small or early-stage startup.",
            provider="mock",
            feature=AIFeature.company_research,
            structured=structured,
            model="mock-v1",
        )

    # Default: deterministic varied response based on seed
    ats_options = ["Greenhouse", "Lever", "Ashby", "Workday", "Personio", None]
    ats_platform = ats_options[seed % len(ats_options)]

    values_score = round(1.0 + (seed % 90) / 10.0, 1)
    values_score = min(values_score, 10.0)

    active_postings = 10 + (seed % 200)
    velocity = f"{(seed % 30) + 2}/month"
    employee_est = f"{500 + (seed % 50) * 100}-{1000 + (seed % 50) * 100}"

    structured = CompanyResearchResult(
        tech_stack={
            "frontend": ["React", "TypeScript", "Next.js"],
            "backend": ["Python", "Go", "gRPC"],
            "infrastructure": ["Kubernetes", "Terraform", "AWS"],
            "analytics": ["Snowflake", "dbt", "Looker"],
        },
        funding={
            "stage": "Series C",
            "total_raised": "$120M",
            "lead_investor": "Sequoia Capital",
            "last_round_date": "2025-09",
        },
        glassdoor={
            "overall_rating": round(2.5 + (seed % 25) / 10.0, 1),
            "ceo_approval": 50 + (seed % 50),
            "culture_keywords": ["innovative", "fast-paced", "collaborative"],
            "work_life_balance": round(2.5 + (seed % 25) / 10.0, 1),
        },
        values_alignment={
            "score": values_score,
            "rationale": (
                "Alignment analysis based on company culture signals and user values. "
                "Score reflects match on innovation, autonomy, and collaboration dimensions."
            ),
        },
        ats_platform=ats_platform,
        hiring_patterns={
            "active_postings": active_postings,
            "posting_velocity": velocity,
            "top_departments": ["Engineering", "Product", "Data"],
        },
        industry_segment="Enterprise SaaS / AI Platform",
        employee_count=employee_est,
        news=[
            {
                "title": "Company announces new product launch",
                "date": "2025-06-01",
                "summary": "Recent product development and market expansion.",
            },
        ],
    )
    return AIResponse(
        content="Company research completed. Strong engineering culture with AI focus.",
        provider="mock",
        feature=AIFeature.company_research,
        structured=structured,
        model="mock-v1",
    )


def _handle_learning_recommendations(prompt: str, context: dict | None) -> AIResponse:
    """Learning recommendations response."""
    structured = LearningRecommendationsResult(
        recommendations=[
            {
                "title": "Terraform Up & Running (3rd ed.)",
                "url": "https://www.oreilly.com/library/view/terraform-up/9781098116743/",
                "hours": 20,
                "provider": "O'Reilly",
                "difficulty": "intermediate",
                "type": "paid",
            },
            {
                "title": "HashiCorp Terraform Associate Certification",
                "url": "https://learn.hashicorp.com/collections/terraform/certification",
                "hours": 15,
                "provider": "HashiCorp Learn",
                "difficulty": "intermediate",
                "type": "free",
            },
            {
                "title": "Kubernetes for Developers — Hands-On",
                "url": "https://kubernetes.io/docs/tutorials/",
                "hours": 10,
                "provider": "Kubernetes Docs",
                "difficulty": "intermediate",
                "type": "free",
            },
        ],
        total_hours=45.0,
    )
    return AIResponse(
        content="Learning recommendations generated. Start with Terraform fundamentals.",
        provider="mock",
        feature=AIFeature.learning_recommendations,
        structured=structured,
        model="mock-v1",
    )


def _handle_interview_format(prompt: str, context: dict | None) -> AIResponse:
    """Interview format response — deterministic per company.

    Different companies produce different interview round structures.
    Uses seed from prompt to vary the number of rounds and types.
    """
    seed = _deterministic_seed(prompt)
    prompt_lower = prompt.lower()

    # Company-specific formats for well-known companies
    if "stripe" in prompt_lower:
        structured = InterviewFormatResult(
            rounds=[
                {
                    "round_number": 1,
                    "type": "Recruiter Screen",
                    "description": (
                        "Initial call with recruiter to discuss "
                        "role, background, and salary expectations."
                    ),
                    "duration_minutes": 30,
                },
                {
                    "round_number": 2,
                    "type": "Hiring Manager Interview",
                    "description": (
                        "Deep dive into leadership experience, "
                        "program management approach, and team dynamics."
                    ),
                    "duration_minutes": 45,
                },
                {
                    "round_number": 3,
                    "type": "Technical Interview",
                    "description": (
                        "System design and technical problem-solving. "
                        "Covers architecture decisions and trade-offs."
                    ),
                    "duration_minutes": 60,
                },
                {
                    "round_number": 4,
                    "type": "Cross-functional Panel",
                    "description": (
                        "Interviews with engineering, product, and design stakeholders."
                    ),
                    "duration_minutes": 60,
                },
                {
                    "round_number": 5,
                    "type": "Executive Interview",
                    "description": (
                        "Final round with senior leadership. "
                        "Focus on strategic thinking and culture fit."
                    ),
                    "duration_minutes": 45,
                },
            ],
            total_duration="3-4 weeks",
            process_description=(
                "Stripe's interview process typically involves 5 rounds "
                "over 3-4 weeks. The process starts with a recruiter screen, "
                "followed by hiring manager and technical interviews, "
                "a cross-functional panel, and a final executive round."
            ),
        )
        return AIResponse(
            content="Stripe interview format: 5 rounds over 3-4 weeks.",
            provider="mock",
            feature=AIFeature.interview_format,
            structured=structured,
            model="mock-v1",
        )

    if "google" in prompt_lower:
        structured = InterviewFormatResult(
            rounds=[
                {
                    "round_number": 1,
                    "type": "Phone Screen",
                    "description": "Technical phone screen with coding or system design questions.",
                    "duration_minutes": 45,
                },
                {
                    "round_number": 2,
                    "type": "On-site: Coding",
                    "description": "Whiteboard coding focusing on algorithms and data structures.",
                    "duration_minutes": 45,
                },
                {
                    "round_number": 3,
                    "type": "On-site: System Design",
                    "description": "Large-scale system design discussion.",
                    "duration_minutes": 45,
                },
                {
                    "round_number": 4,
                    "type": "On-site: Behavioral (Googleyness)",
                    "description": "Behavioral interview assessing leadership and collaboration.",
                    "duration_minutes": 45,
                },
            ],
            total_duration="4-6 weeks",
            process_description=(
                "Google's interview process typically involves 4 rounds: "
                "phone screen followed by 3 on-site interviews "
                "covering coding, system design, and behavioral questions."
            ),
        )
        return AIResponse(
            content="Google interview format: 4 rounds over 4-6 weeks.",
            provider="mock",
            feature=AIFeature.interview_format,
            structured=structured,
            model="mock-v1",
        )

    # Default: deterministic varied response based on seed
    num_rounds = 3 + (seed % 3)  # 3-5 rounds
    round_types = [
        "Phone Screen",
        "Technical Interview",
        "Behavioral Interview",
        "System Design",
        "Hiring Manager",
        "Panel Interview",
        "Take-Home Assignment",
    ]
    rounds = []
    for i in range(num_rounds):
        rtype = round_types[(seed + i) % len(round_types)]
        rounds.append(
            {
                "round_number": i + 1,
                "type": rtype,
                "description": f"Standard {rtype.lower()} covering role-relevant competencies.",
                "duration_minutes": 30 + ((seed + i) % 4) * 15,  # 30-75 min
            }
        )

    weeks = f"{2 + (seed % 3)}-{3 + (seed % 4)} weeks"
    structured = InterviewFormatResult(
        rounds=rounds,
        total_duration=weeks,
        process_description=(
            f"Typical interview process with {num_rounds} rounds over {weeks}. "
            "Includes screening, technical, and behavioral assessments."
        ),
    )
    return AIResponse(
        content=f"Interview format: {num_rounds} rounds over {weeks}.",
        provider="mock",
        feature=AIFeature.interview_format,
        structured=structured,
        model="mock-v1",
    )


def _handle_interview_patterns(prompt: str, context: dict | None) -> AIResponse:
    """Interview patterns response — deterministic per role type.

    Different role types produce distinct question categories, assessment
    criteria, and frequently tested skills.
    """
    prompt_lower = prompt.lower()

    # Role-specific patterns
    if "tpm" in prompt_lower or "technical program" in prompt_lower:
        structured = InterviewPatternsResult(
            question_categories=[
                {
                    "name": "Program Management",
                    "description": "Questions about managing complex, cross-functional programs.",
                    "example_questions": [
                        "Describe a program you managed from inception to delivery.",
                        "How do you handle scope creep in a large program?",
                        "Walk me through your approach to program risk management.",
                    ],
                },
                {
                    "name": "Stakeholder Management",
                    "description": (
                        "Questions about managing relationships with senior stakeholders."
                    ),
                    "example_questions": [
                        "How do you handle conflicting priorities from different stakeholders?",
                        "Describe a time you had to influence without authority.",
                    ],
                },
                {
                    "name": "Technical Depth",
                    "description": "Questions assessing technical understanding and system design.",
                    "example_questions": [
                        "Explain a complex technical concept to a non-technical stakeholder.",
                        "How do you evaluate technical trade-offs in architecture decisions?",
                    ],
                },
                {
                    "name": "Leadership & Execution",
                    "description": "Questions about team leadership and driving execution.",
                    "example_questions": [
                        "Tell me about a time you led a team through a crisis.",
                        "How do you prioritize when everything is urgent?",
                    ],
                },
            ],
            assessment_criteria=[
                {
                    "name": "Strategic Thinking",
                    "description": (
                        "Ability to see the big picture and align programs with business goals."
                    ),
                },
                {
                    "name": "Cross-functional Collaboration",
                    "description": (
                        "Effectiveness in working across engineering, product, and design."
                    ),
                },
                {
                    "name": "Technical Acumen",
                    "description": (
                        "Depth of technical understanding for informed decision-making."
                    ),
                },
                {
                    "name": "Communication",
                    "description": (
                        "Clarity and effectiveness in communicating with diverse audiences."
                    ),
                },
                {
                    "name": "Execution & Delivery",
                    "description": ("Track record of delivering complex programs on time."),
                },
            ],
            frequently_tested_skills=[
                "Program Management",
                "Stakeholder Management",
                "Agile/Scrum",
                "Risk Management",
                "Technical Communication",
                "Cross-functional Leadership",
                "System Design",
            ],
        )
    elif "product engineer" in prompt_lower:
        structured = InterviewPatternsResult(
            question_categories=[
                {
                    "name": "Coding & Algorithms",
                    "description": "Hands-on coding challenges testing problem-solving skills.",
                    "example_questions": [
                        "Implement a function to merge sorted arrays efficiently.",
                        "Design a rate limiter for an API endpoint.",
                    ],
                },
                {
                    "name": "System Design",
                    "description": "Large-scale system architecture discussions.",
                    "example_questions": [
                        "Design a real-time collaboration feature like Google Docs.",
                        "How would you architect a notification system at scale?",
                    ],
                },
                {
                    "name": "Product Sense",
                    "description": "Questions about product thinking and user empathy.",
                    "example_questions": [
                        "How would you improve the onboarding experience for our product?",
                        "Describe a feature you built that had significant user impact.",
                    ],
                },
                {
                    "name": "Frontend/Full-stack",
                    "description": "Questions about UI architecture and frontend best practices.",
                    "example_questions": [
                        "How do you approach state management in a complex React app?",
                        "Explain the trade-offs between SSR and CSR.",
                    ],
                },
            ],
            assessment_criteria=[
                {
                    "name": "Coding Proficiency",
                    "description": "Clean, efficient, well-structured code.",
                },
                {
                    "name": "System Design Skills",
                    "description": ("Ability to design scalable, maintainable systems."),
                },
                {
                    "name": "Product Thinking",
                    "description": ("User-centric approach to feature development."),
                },
                {
                    "name": "Technical Depth",
                    "description": ("Deep understanding of full-stack technologies."),
                },
                {
                    "name": "Collaboration",
                    "description": (
                        "Working effectively with designers, PMs, and other engineers."
                    ),
                },
            ],
            frequently_tested_skills=[
                "JavaScript/TypeScript",
                "React",
                "System Design",
                "API Design",
                "Database Design",
                "Product Thinking",
                "Testing",
            ],
        )
    elif "devrel" in prompt_lower or "developer relation" in prompt_lower:
        structured = InterviewPatternsResult(
            question_categories=[
                {
                    "name": "Technical Communication",
                    "description": (
                        "Questions about explaining complex topics to developer audiences."
                    ),
                    "example_questions": [
                        "Create a tutorial for integrating our API.",
                        "How would you explain a complex concept in a 5-minute lightning talk?",
                    ],
                },
                {
                    "name": "Community Building",
                    "description": "Questions about growing and engaging developer communities.",
                    "example_questions": [
                        "How would you grow an open-source community from scratch?",
                        "Describe your approach to handling negative feedback publicly.",
                    ],
                },
                {
                    "name": "Content Creation",
                    "description": "Questions about creating developer-focused content.",
                    "example_questions": [
                        "Walk me through your content strategy for a new SDK launch.",
                        "How do you measure the impact of developer content?",
                    ],
                },
            ],
            assessment_criteria=[
                {
                    "name": "Technical Credibility",
                    "description": ("Ability to earn trust from developer audiences."),
                },
                {
                    "name": "Communication Skills",
                    "description": "Writing, speaking, and teaching ability.",
                },
                {
                    "name": "Community Engagement",
                    "description": ("Track record of building developer communities."),
                },
                {
                    "name": "Empathy",
                    "description": ("Understanding developer pain points and needs."),
                },
            ],
            frequently_tested_skills=[
                "Technical Writing",
                "Public Speaking",
                "Community Management",
                "Content Strategy",
                "API Knowledge",
                "Developer Experience",
            ],
        )
    else:
        # Generic patterns for other role types
        structured = InterviewPatternsResult(
            question_categories=[
                {
                    "name": "Behavioral",
                    "description": (
                        "Questions about past experiences and behavior in work situations."
                    ),
                    "example_questions": [
                        "Tell me about a time you overcame a significant challenge.",
                        "Describe a situation where you had to adapt to change quickly.",
                    ],
                },
                {
                    "name": "Technical",
                    "description": "Questions testing domain-specific technical knowledge.",
                    "example_questions": [
                        "Walk me through a technical project you led.",
                        "How do you approach technical problem-solving?",
                    ],
                },
                {
                    "name": "Culture Fit",
                    "description": "Questions about work style and team dynamics.",
                    "example_questions": [
                        "What kind of work environment do you thrive in?",
                        "How do you handle disagreements with teammates?",
                    ],
                },
            ],
            assessment_criteria=[
                {
                    "name": "Problem Solving",
                    "description": ("Analytical and creative problem-solving ability."),
                },
                {
                    "name": "Teamwork",
                    "description": "Ability to work effectively in a team.",
                },
                {
                    "name": "Communication",
                    "description": "Clear and effective communication skills.",
                },
            ],
            frequently_tested_skills=[
                "Problem Solving",
                "Communication",
                "Teamwork",
                "Adaptability",
                "Domain Knowledge",
            ],
        )

    return AIResponse(
        content="Interview patterns generated for role type.",
        provider="mock",
        feature=AIFeature.interview_patterns,
        structured=structured,
        model="mock-v1",
    )


def _handle_voice_cover_letter(prompt: str, context: dict | None) -> AIResponse:
    """Voice cover letter brainstorming response.

    References profile strengths and target role from context.
    """
    company = (context or {}).get("company", "the company")
    role = (context or {}).get("role", "the role")
    profile = (context or {}).get("profile", {})
    name = profile.get("name", "the candidate")

    content = (
        f"Based on your profile strengths, here's a draft approach for your cover letter "
        f"to {company} for the {role} position:\n\n"
        f"Dear Hiring Team,\n\n"
        f"I'm {name}, and I bring a unique combination of technical leadership "
        f"and program management experience that aligns well with this role. "
        f"My background in AI/ML program delivery, cross-functional collaboration, "
        f"and hands-on engineering gives me a strong foundation for contributing "
        f"from day one.\n\n"
        f"Key strengths to highlight:\n"
        f"- Technical leadership across distributed teams\n"
        f"- AI/ML program delivery and stakeholder management\n"
        f"- Strategic thinking with hands-on execution capability\n\n"
        f"Would you like me to expand on any of these points or adjust the tone?"
    )
    return AIResponse(
        content=content,
        provider="mock",
        feature=AIFeature.voice_cover_letter,
        structured=None,
        model="mock-v1",
    )


def _count_user_messages(prompt: str) -> int:
    """Count user message turns in the conversation history of a prompt.

    The voice service embeds conversation history in the prompt as:
        Conversation so far:
        Assistant: <welcome>
        User: <first msg>
        Assistant: <question>
        User: <answer>
        ...

        User: <current input>   ← final "User:" outside history section
        Assistant:

    We count User: lines inside the "Conversation so far:" block only,
    stopping when we hit an empty line (which separates history from the
    trailing user input / assistant prompt lines).
    """
    lines = prompt.split("\n")
    user_turns = 0
    in_conversation = False
    for line in lines:
        stripped = line.strip()
        if "conversation so far" in stripped.lower():
            in_conversation = True
            continue
        if in_conversation:
            # Empty line signals end of the conversation history section
            if not stripped:
                in_conversation = False
                continue
            if stripped.startswith("User:"):
                user_turns += 1
    return user_turns


def _handle_voice_coaching(prompt: str, context: dict | None) -> AIResponse:
    """Voice coaching session response with role-relevant questions and feedback.

    Uses conversation history length to decide the response type
    (VAL-VOICE-003):
    - First turn (0-1 user messages in history): return a role-relevant
      coaching question so the user has something concrete to answer.
    - Subsequent turns (2+ user messages): return answer-specific
      feedback/critique on what the user said.
    """
    user_msg_count = _count_user_messages(prompt)

    if user_msg_count >= 2:
        # Subsequent turn → give feedback/critique on the user's answer
        content = (
            "Thank you for that response. Here's my feedback:\n\n"
            "**Strengths:**\n"
            "- You provided context and demonstrated awareness of the challenge\n"
            "- Your approach shows strong stakeholder management skills\n"
            "- Good use of concrete examples to support your points\n\n"
            "**Areas for improvement:**\n"
            "- Try to quantify the impact more specifically (numbers, timelines, "
            "percentage improvements)\n"
            "- Structure your answer more clearly using the STAR format: "
            "Situation → Task → Action → Result\n"
            "- Consider adding what you learned from the experience and how "
            "it shaped your approach going forward\n\n"
            "**Suggested improvement:** Start with a one-sentence summary of the "
            "situation, then clearly separate your specific actions from the team's "
            "actions. End with measurable results.\n\n"
            "Would you like to try answering again with these suggestions, "
            "or move on to another question?"
        )
    else:
        # First turn (0-1 user messages) → always ask a coaching question
        content = (
            "Great, let's get started with your coaching session. "
            "Here's a role-relevant question for you:\n\n"
            "Tell me about a time when you had to manage conflicting priorities "
            "from multiple senior stakeholders. How did you approach the situation, "
            "and what was the outcome?\n\n"
            "Take your time to think through the STAR format: Situation, Task, "
            "Action, Result. I'll provide detailed feedback on your response."
        )

    return AIResponse(
        content=content,
        provider="mock",
        feature=AIFeature.voice_coaching,
        structured=None,
        model="mock-v1",
    )


def _handle_voice_job_evaluation(prompt: str, context: dict | None) -> AIResponse:
    """Voice job evaluation response with scored assessment and pros/cons."""
    company = (context or {}).get("company", "the company")
    role = (context or {}).get("role", "the role")
    app_data = (context or {}).get("application", {})
    fit_score = app_data.get("fit_score", 7.5)
    salary = app_data.get("salary_range", "Not disclosed")

    content = (
        f"Here's my evaluation of the {role} position at {company}:\n\n"
        f"**Overall Score: {fit_score or 7.5}/10**\n\n"
        f"**Pros:**\n"
        f"- Role aligns with your technical leadership experience\n"
        f"- Company shows strong AI/ML focus matching your expertise\n"
        f"- Location/remote compatibility looks good\n"
        f"- Salary range ({salary}) appears within your target range\n\n"
        f"**Cons:**\n"
        f"- May require ramping up on industry-specific domain knowledge\n"
        f"- Interview process could be lengthy (4-6 weeks typical)\n"
        f"- Some skills gaps may need addressing before interview\n\n"
        f"**Recommendation:** This looks like a strong opportunity worth pursuing. "
        f"I'd suggest prioritizing it in your pipeline.\n\n"
        f"Would you like to dive deeper into any specific aspect?"
    )
    return AIResponse(
        content=content,
        provider="mock",
        feature=AIFeature.voice_job_evaluation,
        structured=None,
        model="mock-v1",
    )


# Map features to handlers
_FEATURE_HANDLERS: dict = {
    AIFeature.complete: _handle_complete,
    AIFeature.score: _handle_score,
    AIFeature.gap_analysis: _handle_gap_analysis,
    AIFeature.coaching: _handle_coaching,
    AIFeature.goal_recalibration: _handle_goal_recalibration,
    AIFeature.interview_prep: _handle_interview_prep,
    AIFeature.company_research: _handle_company_research,
    AIFeature.learning_recommendations: _handle_learning_recommendations,
    AIFeature.interview_format: _handle_interview_format,
    AIFeature.interview_patterns: _handle_interview_patterns,
    AIFeature.voice_cover_letter: _handle_voice_cover_letter,
    AIFeature.voice_coaching: _handle_voice_coaching,
    AIFeature.voice_job_evaluation: _handle_voice_job_evaluation,
}
