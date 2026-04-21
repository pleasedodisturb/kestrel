"""Pydantic schemas for Interview Preparation API.

Covers:
- VAL-PREP-001: Personalized topic list per application
- VAL-PREP-002: Practice question generation (≥5 tailored)
- VAL-PREP-003: Prep checklist with time estimates and total
- VAL-PREP-004: Prep progress tracking (persists on revisit)
- VAL-PREP-005: No-research prompt for un-researched companies
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Topic schema
# ---------------------------------------------------------------------------


class PrepTopic(BaseModel):
    """A topic from the personalized topic list (VAL-PREP-001)."""

    topic: str = Field(..., description="Topic name/title")
    relevance: str = Field(..., description="Relevance level: high, medium, low")
    difficulty: str = Field(..., description="Difficulty level: high, medium, low")
    source: str | None = Field(
        default=None,
        description="Where this topic was derived from (JD requirement, skill gap, company style)",
    )


# ---------------------------------------------------------------------------
# Question schema
# ---------------------------------------------------------------------------


class PrepQuestion(BaseModel):
    """A practice question (VAL-PREP-002)."""

    question: str = Field(..., description="The practice question text")
    category: str = Field(
        ..., description="Question category (behavioral, technical, system_design, product, etc.)"
    )
    difficulty: str = Field(..., description="Difficulty: high, medium, low")


# ---------------------------------------------------------------------------
# Checklist item schemas
# ---------------------------------------------------------------------------


class PrepChecklistItem(BaseModel):
    """A checklist item with time estimate and progress tracking (VAL-PREP-003/004)."""

    id: int = Field(..., description="Item ID for progress updates")
    item: str = Field(..., description="Checklist item description")
    time_minutes: int = Field(..., ge=0, description="Estimated time in minutes")
    priority: str = Field(..., description="Priority: high, medium, low")
    completed: bool = Field(default=False, description="Completion state")
    completed_at: datetime | None = Field(default=None, description="When the item was completed")


class PrepItemUpdate(BaseModel):
    """Request body for updating checklist item completion state."""

    completed: bool = Field(..., description="New completion state")


# ---------------------------------------------------------------------------
# Full interview prep response
# ---------------------------------------------------------------------------


class InterviewPrepResponse(BaseModel):
    """Full interview prep response for an application.

    Combines AI-generated topics, questions, and checklist items with
    persisted progress state.
    """

    application_id: int = Field(..., description="Application this prep is for")
    company: str = Field(..., description="Company name")
    role: str = Field(..., description="Role title")
    company_researched: bool = Field(..., description="Whether the company has been researched")
    research_prompt: str | None = Field(
        default=None,
        description="Prompt to research the company first (if not yet researched)",
    )
    topics: list[PrepTopic] = Field(
        default_factory=list,
        description="Personalized topic list (VAL-PREP-001)",
    )
    questions: list[PrepQuestion] = Field(
        default_factory=list,
        description="Practice questions (≥5 tailored) (VAL-PREP-002)",
    )
    checklist: list[PrepChecklistItem] = Field(
        default_factory=list,
        description="Prep checklist with time estimates (VAL-PREP-003)",
    )
    total_prep_minutes: int = Field(
        default=0, description="Total estimated preparation time in minutes"
    )
    total_prep_hours: float = Field(default=0.0, description="Total estimated preparation hours")
    progress_percentage: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Percentage of checklist items completed (VAL-PREP-004)",
    )
    completed_items: int = Field(default=0, description="Number of completed checklist items")
    total_items: int = Field(default=0, description="Total number of checklist items")
