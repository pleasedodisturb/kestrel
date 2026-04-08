"""Interview preparation service.

Generates personalized interview prep per application, cross-referencing:
- Company interview style (from company research)
- Role requirements (from job requirements / JD)
- User's skill gaps (from gap analysis)

Persists prep sessions and checklist progress in the database.

Covers:
- VAL-PREP-001: Personalized topic list per application
- VAL-PREP-002: Practice question generation (≥5 tailored, not generic)
- VAL-PREP-003: Prep checklist with time estimates and total
- VAL-PREP-004: Prep progress tracking (persists on revisit)
- VAL-PREP-005: No-research prompt for un-researched companies
- VAL-CROSS-009: Interview prep uses research and gaps
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from career_os.ai.factory import get_ai_provider
from career_os.models.interview_prep import InterviewPrepItem, InterviewPrepSession
from career_os.models.models import Application, Profile
from career_os.models.skills import JobRequirement, Skill, SkillHistory
from career_os.schemas.ai import AIFeature, InterviewPrepResult
from career_os.schemas.interview_prep import (
    InterviewPrepResponse,
    PrepChecklistItem,
    PrepQuestion,
    PrepTopic,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ApplicationNotFoundError(Exception):
    """Raised when the application is not found or doesn't belong to profile."""


class ProfileNotFoundError(Exception):
    """Raised when the profile doesn't exist."""


class PrepItemNotFoundError(Exception):
    """Raised when a prep checklist item is not found."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_profile(db: Session, profile_id: int) -> Profile:
    """Verify profile exists."""
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise ProfileNotFoundError(f"Profile {profile_id} not found")
    return profile


def _get_application(
    db: Session, application_id: int, profile_id: int
) -> Application:
    """Get application scoped by profile."""
    app_obj = (
        db.query(Application)
        .filter(
            Application.id == application_id,
            Application.profile_id == profile_id,
            Application.archived_at.is_(None),
        )
        .first()
    )
    if not app_obj:
        raise ApplicationNotFoundError(f"Application {application_id} not found")
    return app_obj


def _get_skill_gaps(
    db: Session, application_id: int, profile_id: int
) -> list[dict]:
    """Get skill gaps for an application (requirements vs skills).

    Each gap dict includes a ``distance`` field (0-3) so downstream
    consumers (prompt builder, mock provider) can distinguish resolved
    gaps (distance 0) from unresolved ones.
    """
    requirements = (
        db.query(JobRequirement)
        .filter(
            JobRequirement.application_id == application_id,
            JobRequirement.profile_id == profile_id,
        )
        .all()
    )

    if not requirements:
        return []

    skills = db.query(Skill).filter(Skill.profile_id == profile_id).all()
    skills_by_name = {s.name.lower().strip(): s for s in skills}

    gaps = []
    for req in requirements:
        skill_key = req.skill_name.lower().strip()
        current_skill = skills_by_name.get(skill_key)
        current_level = current_skill.proficiency if current_skill else None

        distance = _compute_distance(current_level, req.required_level)

        gaps.append({
            "skill_name": req.skill_name,
            "required_level": req.required_level,
            "current_level": current_level,
            "severity": req.severity,
            "distance": distance,
            "is_gap": distance > 0,
        })

    return gaps


def _compute_distance(current_level: str | None, required_level: str) -> int:
    """Compute gap distance between current and required proficiency.

    Returns 0 when the requirement is met, 1-2 for partial gaps,
    and 3 when the skill is missing entirely.
    """
    if current_level is None:
        return 3
    cur_idx = _proficiency_index(current_level)
    req_idx = _proficiency_index(required_level)
    if cur_idx >= req_idx:
        return 0
    return min(req_idx - cur_idx, 3)


def _proficiency_index(level: str) -> int:
    """Map proficiency to integer for comparison."""
    return {"beginner": 0, "intermediate": 1, "advanced": 2, "expert": 3}.get(
        level.lower(), 1
    )


def _check_company_researched(db: Session, company_name: str, profile_id: int) -> bool:
    """Check if a company has actual research data.

    Queries the company_research_reports table for an existing report
    for the application's company. Falls back to False if no report found,
    even if the company name is non-empty — ensuring prep triggers a
    research prompt when no research has actually been performed.
    """
    if not company_name or not company_name.strip():
        return False

    # Check for actual persisted company research report
    try:
        from career_os.models.company_research import CompanyResearchReportModel

        report = (
            db.query(CompanyResearchReportModel)
            .filter(
                sa_func.lower(CompanyResearchReportModel.company_name)
                == company_name.strip().lower(),
                CompanyResearchReportModel.profile_id == profile_id,
            )
            .first()
        )
        return report is not None
    except Exception:
        # If model doesn't exist yet (no migration), fall back gracefully
        # to checking non-empty company name
        return bool(company_name and company_name.strip())


def _get_company_research_data(
    db: Session, company_name: str, profile_id: int
) -> dict | None:
    """Fetch persisted company research data for inclusion in prep prompt.

    Returns a dict with tech_stack, culture, values_alignment, hiring_patterns,
    and industry_segment extracted from the CompanyResearchReportModel.
    Returns None if no research report exists.
    """
    if not company_name or not company_name.strip():
        return None

    try:
        from career_os.models.company_research import CompanyResearchReportModel

        report = (
            db.query(CompanyResearchReportModel)
            .filter(
                sa_func.lower(CompanyResearchReportModel.company_name)
                == company_name.strip().lower(),
                CompanyResearchReportModel.profile_id == profile_id,
            )
            .first()
        )
        if not report:
            return None

        research_data: dict = {
            "values_alignment_score": report.values_alignment_score,
            "industry_segment": report.industry_segment,
        }

        # Parse full report JSON for tech_stack, culture, hiring_patterns
        if report.report_json:
            try:
                full_report = json.loads(report.report_json)
                if isinstance(full_report, dict):
                    if "tech_stack" in full_report:
                        research_data["tech_stack"] = full_report["tech_stack"]
                    if "culture" in full_report:
                        research_data["culture"] = full_report["culture"]
                    if "culture_keywords" in full_report:
                        research_data["culture"] = full_report["culture_keywords"]
                    if "glassdoor" in full_report:
                        glass = full_report["glassdoor"]
                        if isinstance(glass, dict) and "culture_keywords" in glass:
                            research_data["culture"] = glass["culture_keywords"]
                    if "values_alignment" in full_report:
                        va = full_report["values_alignment"]
                        if isinstance(va, dict):
                            research_data["values_alignment_score"] = va.get(
                                "score", research_data.get("values_alignment_score")
                            )
                            research_data["values_rationale"] = va.get("rationale")
                    if "hiring_patterns" in full_report:
                        research_data["hiring_patterns"] = full_report["hiring_patterns"]
            except (json.JSONDecodeError, TypeError):
                pass

        return research_data
    except Exception:
        return None


def _strip_tz(dt: datetime | None) -> datetime | None:
    """Strip timezone info for safe comparison (SQLite may strip tz)."""
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def _is_prep_stale(
    db: Session,
    session: InterviewPrepSession,
    profile_id: int,
) -> bool:
    """Check if a prep session is stale due to dependent data changes.

    Returns True if skills, skill proficiency changes, job requirements,
    or company research have been modified after the prep session was
    created, meaning the prep should be regenerated.

    VAL-CROSS-015: Also checks SkillHistory for proficiency changes,
    not just Skill.updated_at (which may not update for all proficiency
    change paths).
    """
    session_created = _strip_tz(session.created_at)
    if session_created is None:
        return False

    # Check if any skills were updated after the prep was generated
    latest_skill_update = _strip_tz(
        db.query(sa_func.max(Skill.updated_at))
        .filter(Skill.profile_id == profile_id)
        .scalar()
    )

    if latest_skill_update and latest_skill_update > session_created:
        logger.info(
            "Prep session %d is stale: skills updated at %s > prep created at %s",
            session.id,
            latest_skill_update,
            session_created,
        )
        return True

    # VAL-CROSS-015: Check if skill proficiency was changed after prep
    # (SkillHistory tracks explicit proficiency changes, which is more
    # reliable than Skill.updated_at for detecting proficiency upgrades)
    latest_proficiency_change = _strip_tz(
        db.query(sa_func.max(SkillHistory.created_at))
        .filter(SkillHistory.profile_id == profile_id)
        .scalar()
    )

    if latest_proficiency_change and latest_proficiency_change > session_created:
        logger.info(
            "Prep session %d is stale: skill proficiency changed at %s "
            "> prep created at %s",
            session.id,
            latest_proficiency_change,
            session_created,
        )
        return True

    # Check if job requirements were added/modified after prep creation
    latest_req_created = _strip_tz(
        db.query(sa_func.max(JobRequirement.created_at))
        .filter(
            JobRequirement.application_id == session.application_id,
            JobRequirement.profile_id == profile_id,
        )
        .scalar()
    )

    if latest_req_created and latest_req_created > session_created:
        logger.info(
            "Prep session %d is stale: requirements updated at %s > prep created at %s",
            session.id,
            latest_req_created,
            session_created,
        )
        return True

    # Check if company research was added/updated after prep creation
    try:
        from career_os.models.company_research import CompanyResearchReportModel

        # Look up the application to get the company name
        app_obj = (
            db.query(Application)
            .filter(Application.id == session.application_id)
            .first()
        )
        if app_obj and app_obj.company and app_obj.company.strip():
            latest_research_update = _strip_tz(
                db.query(sa_func.max(CompanyResearchReportModel.updated_at))
                .filter(
                    sa_func.lower(CompanyResearchReportModel.company_name)
                    == app_obj.company.strip().lower(),
                    CompanyResearchReportModel.profile_id == profile_id,
                )
                .scalar()
            )

            if latest_research_update and latest_research_update > session_created:
                logger.info(
                    "Prep session %d is stale: company research updated at %s "
                    "> prep created at %s",
                    session.id,
                    latest_research_update,
                    session_created,
                )
                return True
    except Exception:
        # If the model/table doesn't exist yet, skip this check gracefully
        pass

    return False


def _delete_stale_session(db: Session, session: InterviewPrepSession) -> None:
    """Delete a stale prep session and its items to allow regeneration."""
    db.delete(session)
    db.flush()


def _build_prep_prompt(
    app_obj: Application,
    profile: Profile,
    gaps: list[dict],
    company_researched: bool,
    research_data: dict | None = None,
) -> str:
    """Build the AI prompt for interview preparation.

    Cross-references company style, role requirements, and skill gaps
    to produce personalized prep material. When company research data
    is available, includes tech stack, culture, values alignment, and
    hiring patterns so topics/questions reflect company-specific data
    (VAL-CROSS-009).
    """
    # Separate unresolved gaps (distance > 0) from resolved ones (distance 0)
    unresolved_gaps = [g for g in gaps if g.get("distance", 1) > 0]
    resolved_gaps = [g for g in gaps if g.get("distance", 1) == 0]

    gap_section = ""
    if unresolved_gaps:
        gap_lines = [
            f"  - {g['skill_name']} (required: {g['required_level']}, "
            f"current: {g['current_level'] or 'missing'}, "
            f"distance: {g.get('distance', '?')})"
            for g in unresolved_gaps
        ]
        gap_section = (
            "\n\nUser's UNRESOLVED skill gaps for this role "
            "(focus prep on these):\n"
            + "\n".join(gap_lines)
        )
    if resolved_gaps:
        resolved_lines = [
            f"  - {g['skill_name']} (met — current: {g['current_level']}, "
            f"required: {g['required_level']})"
            for g in resolved_gaps
        ]
        gap_section += (
            "\n\nSkills already meeting requirements (de-emphasize in prep):\n"
            + "\n".join(resolved_lines)
        )

    requirements_section = ""
    if gaps:
        req_lines = [
            f"  - {g['skill_name']} ({g['severity']}, {g['required_level']}, "
            f"distance: {g.get('distance', '?')})"
            for g in gaps
        ]
        requirements_section = (
            "\n\nRole requirements:\n" + "\n".join(req_lines)
        )

    # Build company research section from persisted research data
    research_section = ""
    if research_data:
        research_lines = ["\n\nCompany research data:"]
        tech_stack = research_data.get("tech_stack")
        if tech_stack:
            if isinstance(tech_stack, dict):
                for category, techs in tech_stack.items():
                    if techs:
                        tech_list = ", ".join(techs) if isinstance(techs, list) else str(techs)
                        research_lines.append(f"  - Tech stack ({category}): {tech_list}")
            elif isinstance(tech_stack, list):
                research_lines.append(f"  - Tech stack: {', '.join(tech_stack)}")
        culture = research_data.get("culture")
        if culture:
            if isinstance(culture, list):
                research_lines.append(f"  - Culture keywords: {', '.join(culture)}")
            else:
                research_lines.append(f"  - Culture: {culture}")
        va_score = research_data.get("values_alignment_score")
        if va_score is not None:
            research_lines.append(f"  - Values alignment score: {va_score}/10")
        va_rationale = research_data.get("values_rationale")
        if va_rationale:
            research_lines.append(f"  - Values alignment: {va_rationale}")
        hiring = research_data.get("hiring_patterns")
        if hiring and isinstance(hiring, dict):
            if hiring.get("active_postings"):
                research_lines.append(
                    f"  - Active postings: {hiring['active_postings']}"
                )
            if hiring.get("posting_velocity"):
                research_lines.append(
                    f"  - Posting velocity: {hiring['posting_velocity']}"
                )
            if hiring.get("top_departments"):
                research_lines.append(
                    f"  - Top departments: {', '.join(hiring['top_departments'])}"
                )
        industry = research_data.get("industry_segment")
        if industry:
            research_lines.append(f"  - Industry segment: {industry}")

        if len(research_lines) > 1:  # More than just the header
            research_section = "\n".join(research_lines)

    return f"""Generate personalized interview preparation for the following application.

Company: {app_obj.company}
Role: {app_obj.role}
{f"Job URL: {app_obj.url}" if app_obj.url else ""}
{f"Notes: {app_obj.notes}" if app_obj.notes else ""}

User profile:
- Name: {profile.name}
- Location: {profile.location or "Not specified"}
- Job family: {profile.job_family or "Not specified"}
{requirements_section}
{gap_section}
{research_section}

Generate:
1. Personalized topic list (cross-referencing company interview style, role requirements,
   and user's skill gaps). Each topic should have relevance (high/medium/low) and
   difficulty (high/medium/low). IMPORTANT: Focus topics on UNRESOLVED gaps (distance > 0).
   Omit or de-emphasize topics for skills already meeting requirements (distance 0).

2. At least 5 tailored practice questions specific to this role and company
   (NOT generic). Include category and difficulty for each. Prioritize questions
   targeting unresolved skill gaps.

3. Actionable prep checklist items with per-item time estimates in minutes
   and priority (high/medium/low). Prioritize items that address unresolved gaps.

4. Total estimated prep hours.

Return structured data.
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_or_create_interview_prep(
    db: Session,
    application_id: int,
    profile_id: int,
) -> InterviewPrepResponse:
    """Get or create interview prep for an application.

    If a prep session already exists, returns it with persisted progress.
    Otherwise, generates new prep via AI and persists it.

    Un-researched companies trigger a research prompt (VAL-PREP-005).

    Args:
        db: Database session.
        application_id: Application ID.
        profile_id: Profile ID.

    Returns:
        InterviewPrepResponse with topics, questions, checklist, and progress.

    Raises:
        ApplicationNotFoundError: If the application doesn't exist.
        ProfileNotFoundError: If the profile doesn't exist.
    """
    profile = _validate_profile(db, profile_id)
    app_obj = _get_application(db, application_id, profile_id)

    # Check for existing session
    session = (
        db.query(InterviewPrepSession)
        .filter(
            InterviewPrepSession.application_id == application_id,
            InterviewPrepSession.profile_id == profile_id,
        )
        .first()
    )

    if session:
        # Freshness check: regenerate if dependent data changed
        if _is_prep_stale(db, session, profile_id):
            logger.info(
                "Regenerating stale prep session %d for application %d",
                session.id,
                application_id,
            )
            _delete_stale_session(db, session)
            session = None
        else:
            return _build_response_from_session(session, app_obj)

    # Check if company has been researched (actual data, not just name)
    company_researched = _check_company_researched(db, app_obj.company, profile_id)

    # Build research prompt if company not researched
    research_prompt = None
    if not company_researched:
        research_prompt = (
            f"Company '{app_obj.company}' has not been researched yet. "
            f"Run company research first for better interview preparation: "
            f"POST /api/research/company with company_name='{app_obj.company}'"
        )

    # Get skill gaps for context
    gaps = _get_skill_gaps(db, application_id, profile_id)

    # Fetch company research data if available (VAL-CROSS-009)
    research_data = _get_company_research_data(db, app_obj.company, profile_id)

    # Generate prep via AI
    prompt = _build_prep_prompt(
        app_obj, profile, gaps, company_researched, research_data=research_data
    )

    try:
        provider = get_ai_provider()
        response = await provider.complete(
            prompt=prompt,
            feature=AIFeature.interview_prep,
            context={
                "application_id": application_id,
                "profile_id": profile_id,
                "company": app_obj.company,
                "role": app_obj.role,
                "research_data": research_data,
                "gaps": gaps,
            },
        )
        structured = response.structured
    except Exception as exc:
        logger.warning(
            "AI provider failed for interview prep (app %d): %s",
            application_id,
            exc,
        )
        structured = None

    # Parse AI response and persist
    session = _create_session_from_ai(
        db=db,
        app_obj=app_obj,
        profile_id=profile_id,
        structured=structured,
        company_researched=company_researched,
    )

    resp = _build_response_from_session(session, app_obj)
    if research_prompt:
        resp.research_prompt = research_prompt
    return resp


def update_prep_item(
    db: Session,
    item_id: int,
    profile_id: int,
    completed: bool,
) -> PrepChecklistItem:
    """Update a prep checklist item's completion state.

    Args:
        db: Database session.
        item_id: Checklist item ID.
        profile_id: Profile ID (for scoping).
        completed: New completion state.

    Returns:
        Updated PrepChecklistItem.

    Raises:
        PrepItemNotFoundError: If item not found or wrong profile.
    """
    _validate_profile(db, profile_id)

    prep_item = (
        db.query(InterviewPrepItem)
        .filter(
            InterviewPrepItem.id == item_id,
            InterviewPrepItem.profile_id == profile_id,
        )
        .first()
    )
    if not prep_item:
        raise PrepItemNotFoundError(f"Prep item {item_id} not found")

    prep_item.completed = completed
    prep_item.completed_at = datetime.now(UTC) if completed else None

    db.commit()
    db.refresh(prep_item)

    return PrepChecklistItem(
        id=prep_item.id,
        item=prep_item.item,
        time_minutes=prep_item.time_minutes,
        priority=prep_item.priority,
        completed=prep_item.completed,
        completed_at=prep_item.completed_at,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _create_session_from_ai(
    db: Session,
    app_obj: Application,
    profile_id: int,
    structured: InterviewPrepResult | object | None,
    company_researched: bool,
) -> InterviewPrepSession:
    """Create a new InterviewPrepSession from AI response."""

    topics_json: list[dict] = []
    questions_json: list[dict] = []
    checklist_items: list[dict] = []
    total_prep_hours = 0.0

    if isinstance(structured, InterviewPrepResult):
        topics_json = structured.topics
        questions_json = structured.questions
        checklist_items = structured.checklist
        total_prep_hours = structured.total_prep_hours

    session = InterviewPrepSession(
        application_id=app_obj.id,
        profile_id=profile_id,
        topics=json.dumps(topics_json),
        questions=json.dumps(questions_json),
        total_prep_hours=total_prep_hours,
        company_researched=company_researched,
    )
    db.add(session)
    db.flush()  # Get session.id

    # Create checklist items
    for item_data in checklist_items:
        prep_item = InterviewPrepItem(
            session_id=session.id,
            profile_id=profile_id,
            item=item_data.get("item", ""),
            time_minutes=item_data.get("time_minutes", 0),
            priority=item_data.get("priority", "medium"),
            completed=False,
        )
        db.add(prep_item)

    db.commit()
    db.refresh(session)
    return session


def _build_response_from_session(
    session: InterviewPrepSession,
    app_obj: Application,
) -> InterviewPrepResponse:
    """Build InterviewPrepResponse from a persisted session."""

    # Parse JSON fields
    topics_raw = json.loads(session.topics) if session.topics else []
    questions_raw = json.loads(session.questions) if session.questions else []

    topics = [PrepTopic(**t) for t in topics_raw]
    questions = [PrepQuestion(**q) for q in questions_raw]

    # Build checklist with progress state
    checklist = [
        PrepChecklistItem(
            id=item.id,
            item=item.item,
            time_minutes=item.time_minutes,
            priority=item.priority,
            completed=item.completed,
            completed_at=item.completed_at,
        )
        for item in session.items
    ]

    total_items = len(checklist)
    completed_items = sum(1 for c in checklist if c.completed)
    progress_percentage = (
        round((completed_items / total_items) * 100, 1) if total_items > 0 else 0.0
    )
    total_prep_minutes = sum(c.time_minutes for c in checklist)

    # Check if company research is needed
    research_prompt = None
    if not session.company_researched:
        research_prompt = (
            f"Company '{app_obj.company}' has not been researched yet. "
            f"Run company research first for better interview preparation: "
            f"POST /api/research/company with company_name='{app_obj.company}'"
        )

    return InterviewPrepResponse(
        application_id=app_obj.id,
        company=app_obj.company,
        role=app_obj.role,
        company_researched=session.company_researched,
        research_prompt=research_prompt,
        topics=topics,
        questions=questions,
        checklist=checklist,
        total_prep_minutes=total_prep_minutes,
        total_prep_hours=session.total_prep_hours or 0.0,
        progress_percentage=progress_percentage,
        completed_items=completed_items,
        total_items=total_items,
    )
