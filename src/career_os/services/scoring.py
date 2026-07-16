"""Scoring service — AI-powered job scoring engine.

Scores jobs against the user's full profile (target roles, psychometric fit,
culture signals, salary expectations, values). Factors in M2 skills gaps
(readiness_score) and career goals (career_alignment).
"""

from __future__ import annotations

import json
import logging
import time

from sqlalchemy.orm import Session

from career_os.ai.base import ProviderQuotaError
from career_os.ai.factory import get_ai_provider
from career_os.ai.openrouter_provider import CreditsExhaustedError
from career_os.config import settings
from career_os.models.discovery import DiscoveredJob
from career_os.models.models import Application, Profile
from career_os.models.scoring import ScoredJob, ScoringFeedback, ScoringWeights
from career_os.models.skills import Goal, Skill
from career_os.schemas.ai import (
    ROLE_FIT_GATE_CEILING,
    RoleMatch,
    ScoreResult,
    apply_role_fit_gate,
    role_fit_gate_failed,
)
from career_os.services.red_flags import detect_data_driven_red_flags, detect_red_flags

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ProfileNotFoundError(Exception):
    """Raised when the referenced profile does not exist."""


class JobNotFoundError(Exception):
    """Raised when a discovered job or application is not found."""


class ProfileIncompleteError(Exception):
    """Raised when profile lacks required fields for meaningful scoring."""


class ScoringError(Exception):
    """Raised when scoring fails."""


# ---------------------------------------------------------------------------
# Default weights
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS: dict[str, float] = {
    "skills_match": 0.25,
    "career_alignment": 0.20,
    "culture_fit": 0.15,
    "salary_match": 0.15,
    "location_match": 0.10,
    "growth_potential": 0.10,
    "remote_preference": 0.05,
}

# Job-family-specific weight presets (VAL-CROSS-004, expanded G-301).
# When a profile's job_family changes, the scoring weights are regenerated
# with the preset for the new family.  Families not listed here fall back to
# DEFAULT_WEIGHTS.
#
# Each preset has 7 keys that must sum to 1.0:
#   skills_match, career_alignment, culture_fit, salary_match,
#   location_match, growth_potential, remote_preference
#
# Organized by sector for readability.
JOB_FAMILY_WEIGHTS: dict[str, dict[str, float]] = {
    # ── Technology ────────────────────────────────────────────────────────
    "TPM": {
        "skills_match": 0.20,
        "career_alignment": 0.25,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "SWE": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Product Engineer": {
        "skills_match": 0.30,
        "career_alignment": 0.20,
        "culture_fit": 0.15,
        "salary_match": 0.10,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "DevRel": {
        "skills_match": 0.15,
        "career_alignment": 0.20,
        "culture_fit": 0.25,
        "salary_match": 0.10,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.10,
    },
    "AI Program Lead": {
        "skills_match": 0.25,
        "career_alignment": 0.25,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Backend Engineer": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Frontend Engineer": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.10,
        "remote_preference": 0.10,
    },
    "Full-Stack Developer": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.10,
    },
    "Mobile Developer (iOS)": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Mobile Developer (Android)": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "DevOps Engineer": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Site Reliability Engineer (SRE)": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Platform Engineer": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Cloud Architect": {
        "skills_match": 0.30,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Solutions Architect": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Security Engineer": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "DevSecOps Engineer": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "QA Engineer": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "QA Automation Engineer": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "SDET": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Data Engineer": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "ML Engineer": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.05,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.20,
        "remote_preference": 0.05,
    },
    "MLOps Engineer": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "AI Research Scientist": {
        "skills_match": 0.30,
        "career_alignment": 0.20,
        "culture_fit": 0.05,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.20,
        "remote_preference": 0.05,
    },
    "Data Scientist": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.20,
        "remote_preference": 0.05,
    },
    "Data Analyst": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Business Intelligence Analyst": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Database Administrator": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Network Engineer": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Systems Administrator": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "IT Support": {
        "skills_match": 0.25,
        "career_alignment": 0.10,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.20,
        "growth_potential": 0.15,
        "remote_preference": 0.00,
    },
    "Cybersecurity Analyst": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Penetration Tester": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.05,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.10,
    },
    "Embedded Systems Engineer": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Firmware Engineer": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Game Developer": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.10,
        "location_match": 0.10,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Blockchain Developer": {
        "skills_match": 0.35,
        "career_alignment": 0.10,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.10,
    },
    "Technical Writer (Tech)": {
        "skills_match": 0.20,
        "career_alignment": 0.15,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.10,
    },
    "Release Manager": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Scrum Master": {
        "skills_match": 0.15,
        "career_alignment": 0.20,
        "culture_fit": 0.25,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.10,
        "remote_preference": 0.10,
    },
    "Engineering Manager": {
        "skills_match": 0.20,
        "career_alignment": 0.25,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "VP Engineering": {
        "skills_match": 0.15,
        "career_alignment": 0.30,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "CTO": {
        "skills_match": 0.15,
        "career_alignment": 0.30,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Chief Architect": {
        "skills_match": 0.25,
        "career_alignment": 0.25,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    # ── Product & Design ──────────────────────────────────────────────────
    "Product Manager": {
        "skills_match": 0.15,
        "career_alignment": 0.25,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Senior Product Manager": {
        "skills_match": 0.15,
        "career_alignment": 0.25,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.10,
        "remote_preference": 0.10,
    },
    "VP Product": {
        "skills_match": 0.10,
        "career_alignment": 0.30,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.10,
        "remote_preference": 0.10,
    },
    "Product Owner": {
        "skills_match": 0.15,
        "career_alignment": 0.20,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "UX Designer": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "UI Designer": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Product Designer": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "UX Researcher": {
        "skills_match": 0.20,
        "career_alignment": 0.15,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Design System Lead": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Creative Director": {
        "skills_match": 0.15,
        "career_alignment": 0.25,
        "culture_fit": 0.25,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Graphic Designer": {
        "skills_match": 0.30,
        "career_alignment": 0.10,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Motion Designer": {
        "skills_match": 0.30,
        "career_alignment": 0.10,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.10,
    },
    "Brand Designer": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.25,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Web Designer": {
        "skills_match": 0.30,
        "career_alignment": 0.10,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.10,
    },
    "Interaction Designer": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Service Designer": {
        "skills_match": 0.20,
        "career_alignment": 0.15,
        "culture_fit": 0.25,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Design Manager": {
        "skills_match": 0.20,
        "career_alignment": 0.25,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Head of Design": {
        "skills_match": 0.15,
        "career_alignment": 0.25,
        "culture_fit": 0.25,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    # ── Data & Analytics ──────────────────────────────────────────────────
    "Senior Data Analyst": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Analytics Engineer": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.20,
        "remote_preference": 0.05,
    },
    "Business Analyst": {
        "skills_match": 0.20,
        "career_alignment": 0.20,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Quantitative Analyst": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.05,
        "salary_match": 0.20,
        "location_match": 0.10,
        "growth_potential": 0.15,
        "remote_preference": 0.00,
    },
    "Statistician": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Research Analyst": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Market Research Analyst": {
        "skills_match": 0.20,
        "career_alignment": 0.15,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Pricing Analyst": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.10,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Revenue Analyst": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.10,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Fraud Analyst": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Risk Analyst": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Insights Analyst": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    # ── Finance & Accounting ──────────────────────────────────────────────
    "Financial Analyst": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Senior Financial Analyst": {
        "skills_match": 0.25,
        "career_alignment": 0.25,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "FP&A Analyst": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Investment Analyst": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.05,
        "salary_match": 0.25,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Portfolio Manager": {
        "skills_match": 0.20,
        "career_alignment": 0.25,
        "culture_fit": 0.05,
        "salary_match": 0.25,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Equity Research Analyst": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.05,
        "salary_match": 0.25,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Credit Analyst": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Risk Analyst (Finance)": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Treasury Analyst": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Fund Accountant": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Tax Accountant": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Auditor (Big 4)": {
        "skills_match": 0.20,
        "career_alignment": 0.25,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Management Accountant": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Controller": {
        "skills_match": 0.20,
        "career_alignment": 0.25,
        "culture_fit": 0.15,
        "salary_match": 0.20,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "CFO": {
        "skills_match": 0.15,
        "career_alignment": 0.30,
        "culture_fit": 0.15,
        "salary_match": 0.20,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Bookkeeper": {
        "skills_match": 0.25,
        "career_alignment": 0.10,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Accounts Payable/Receivable": {
        "skills_match": 0.20,
        "career_alignment": 0.10,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.20,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Payroll Specialist": {
        "skills_match": 0.25,
        "career_alignment": 0.10,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Compliance Officer (Finance)": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Anti-Money Laundering Analyst": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Actuary": {
        "skills_match": 0.35,
        "career_alignment": 0.20,
        "culture_fit": 0.05,
        "salary_match": 0.20,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Insurance Underwriter": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Loan Officer": {
        "skills_match": 0.15,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.20,
        "location_match": 0.25,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Financial Advisor": {
        "skills_match": 0.15,
        "career_alignment": 0.20,
        "culture_fit": 0.15,
        "salary_match": 0.25,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Wealth Manager": {
        "skills_match": 0.15,
        "career_alignment": 0.25,
        "culture_fit": 0.10,
        "salary_match": 0.25,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    # ── Legal ─────────────────────────────────────────────────────────────
    "Corporate Lawyer": {
        "skills_match": 0.25,
        "career_alignment": 0.25,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.15,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Litigation Attorney": {
        "skills_match": 0.25,
        "career_alignment": 0.25,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.15,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "IP Lawyer": {
        "skills_match": 0.30,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.15,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Employment Lawyer": {
        "skills_match": 0.25,
        "career_alignment": 0.25,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.15,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Tax Lawyer": {
        "skills_match": 0.30,
        "career_alignment": 0.20,
        "culture_fit": 0.05,
        "salary_match": 0.25,
        "location_match": 0.15,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Real Estate Attorney": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.20,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Criminal Defense Attorney": {
        "skills_match": 0.25,
        "career_alignment": 0.25,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.20,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Immigration Lawyer": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.20,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Regulatory Compliance Lawyer": {
        "skills_match": 0.30,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.10,
        "growth_potential": 0.05,
        "remote_preference": 0.05,
    },
    "Legal Counsel (In-house)": {
        "skills_match": 0.20,
        "career_alignment": 0.25,
        "culture_fit": 0.15,
        "salary_match": 0.20,
        "location_match": 0.10,
        "growth_potential": 0.05,
        "remote_preference": 0.05,
    },
    "Paralegal": {
        "skills_match": 0.25,
        "career_alignment": 0.10,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.20,
        "growth_potential": 0.15,
        "remote_preference": 0.00,
    },
    "Legal Secretary": {
        "skills_match": 0.20,
        "career_alignment": 0.10,
        "culture_fit": 0.15,
        "salary_match": 0.20,
        "location_match": 0.25,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Contract Manager": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Privacy/Data Protection Officer (DPO)": {
        "skills_match": 0.30,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.10,
        "growth_potential": 0.05,
        "remote_preference": 0.05,
    },
    # ── Marketing & Communications ────────────────────────────────────────
    "Marketing Manager": {
        "skills_match": 0.20,
        "career_alignment": 0.20,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.10,
        "remote_preference": 0.10,
    },
    "Digital Marketing Manager": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.10,
    },
    "Content Marketing Manager": {
        "skills_match": 0.20,
        "career_alignment": 0.15,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.10,
    },
    "SEO Specialist": {
        "skills_match": 0.30,
        "career_alignment": 0.10,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.20,
        "remote_preference": 0.10,
    },
    "SEM/PPC Specialist": {
        "skills_match": 0.30,
        "career_alignment": 0.10,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.20,
        "remote_preference": 0.10,
    },
    "Social Media Manager": {
        "skills_match": 0.20,
        "career_alignment": 0.10,
        "culture_fit": 0.25,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.10,
    },
    "Email Marketing Specialist": {
        "skills_match": 0.25,
        "career_alignment": 0.10,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.20,
        "remote_preference": 0.10,
    },
    "Growth Marketing Manager": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Brand Manager": {
        "skills_match": 0.15,
        "career_alignment": 0.20,
        "culture_fit": 0.25,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "PR Manager": {
        "skills_match": 0.15,
        "career_alignment": 0.20,
        "culture_fit": 0.25,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Communications Manager": {
        "skills_match": 0.15,
        "career_alignment": 0.20,
        "culture_fit": 0.25,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Copywriter": {
        "skills_match": 0.25,
        "career_alignment": 0.10,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.10,
    },
    "Content Strategist": {
        "skills_match": 0.20,
        "career_alignment": 0.15,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.10,
    },
    "Marketing Analyst": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.10,
    },
    "Influencer Marketing Manager": {
        "skills_match": 0.20,
        "career_alignment": 0.10,
        "culture_fit": 0.25,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Event Marketing Manager": {
        "skills_match": 0.15,
        "career_alignment": 0.15,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "CMO": {
        "skills_match": 0.10,
        "career_alignment": 0.30,
        "culture_fit": 0.20,
        "salary_match": 0.20,
        "location_match": 0.05,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Community Manager": {
        "skills_match": 0.15,
        "career_alignment": 0.10,
        "culture_fit": 0.30,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.10,
    },
    "Affiliate Marketing Manager": {
        "skills_match": 0.20,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.20,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.10,
    },
    # ── Sales & Business Development ──────────────────────────────────────
    "Account Executive": {
        "skills_match": 0.15,
        "career_alignment": 0.20,
        "culture_fit": 0.20,
        "salary_match": 0.20,
        "location_match": 0.10,
        "growth_potential": 0.15,
        "remote_preference": 0.00,
    },
    "Senior Account Executive": {
        "skills_match": 0.15,
        "career_alignment": 0.25,
        "culture_fit": 0.20,
        "salary_match": 0.20,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Sales Development Representative (SDR)": {
        "skills_match": 0.10,
        "career_alignment": 0.15,
        "culture_fit": 0.20,
        "salary_match": 0.20,
        "location_match": 0.10,
        "growth_potential": 0.25,
        "remote_preference": 0.00,
    },
    "Business Development Representative (BDR)": {
        "skills_match": 0.10,
        "career_alignment": 0.15,
        "culture_fit": 0.20,
        "salary_match": 0.20,
        "location_match": 0.10,
        "growth_potential": 0.25,
        "remote_preference": 0.00,
    },
    "Enterprise Sales": {
        "skills_match": 0.15,
        "career_alignment": 0.25,
        "culture_fit": 0.15,
        "salary_match": 0.25,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Inside Sales": {
        "skills_match": 0.10,
        "career_alignment": 0.15,
        "culture_fit": 0.20,
        "salary_match": 0.20,
        "location_match": 0.10,
        "growth_potential": 0.20,
        "remote_preference": 0.05,
    },
    "Solutions Consultant": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Pre-Sales Engineer": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Sales Engineer": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Account Manager": {
        "skills_match": 0.15,
        "career_alignment": 0.20,
        "culture_fit": 0.25,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Key Account Manager": {
        "skills_match": 0.15,
        "career_alignment": 0.25,
        "culture_fit": 0.20,
        "salary_match": 0.20,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Customer Success Manager": {
        "skills_match": 0.15,
        "career_alignment": 0.15,
        "culture_fit": 0.30,
        "salary_match": 0.15,
        "location_match": 0.05,
        "growth_potential": 0.10,
        "remote_preference": 0.10,
    },
    "VP Sales": {
        "skills_match": 0.10,
        "career_alignment": 0.30,
        "culture_fit": 0.15,
        "salary_match": 0.25,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Sales Operations Analyst": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Channel Sales Manager": {
        "skills_match": 0.15,
        "career_alignment": 0.20,
        "culture_fit": 0.20,
        "salary_match": 0.20,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Partnership Manager": {
        "skills_match": 0.10,
        "career_alignment": 0.20,
        "culture_fit": 0.25,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Revenue Operations Manager": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.05,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    # ── Human Resources ───────────────────────────────────────────────────
    "HR Manager": {
        "skills_match": 0.15,
        "career_alignment": 0.20,
        "culture_fit": 0.25,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "HR Business Partner": {
        "skills_match": 0.15,
        "career_alignment": 0.25,
        "culture_fit": 0.25,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Talent Acquisition Specialist": {
        "skills_match": 0.15,
        "career_alignment": 0.15,
        "culture_fit": 0.25,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Recruiter": {
        "skills_match": 0.10,
        "career_alignment": 0.15,
        "culture_fit": 0.25,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Technical Recruiter": {
        "skills_match": 0.20,
        "career_alignment": 0.15,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Executive Recruiter": {
        "skills_match": 0.10,
        "career_alignment": 0.25,
        "culture_fit": 0.20,
        "salary_match": 0.20,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Learning & Development Specialist": {
        "skills_match": 0.15,
        "career_alignment": 0.15,
        "culture_fit": 0.25,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.15,
        "remote_preference": 0.00,
    },
    "Compensation & Benefits Analyst": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.20,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "HR Operations": {
        "skills_match": 0.20,
        "career_alignment": 0.10,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "People Analytics": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "DEI Manager": {
        "skills_match": 0.10,
        "career_alignment": 0.20,
        "culture_fit": 0.30,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Employee Relations Specialist": {
        "skills_match": 0.15,
        "career_alignment": 0.15,
        "culture_fit": 0.30,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "CHRO": {
        "skills_match": 0.10,
        "career_alignment": 0.30,
        "culture_fit": 0.25,
        "salary_match": 0.20,
        "location_match": 0.05,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Organizational Development Consultant": {
        "skills_match": 0.15,
        "career_alignment": 0.20,
        "culture_fit": 0.25,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Employer Branding Specialist": {
        "skills_match": 0.15,
        "career_alignment": 0.15,
        "culture_fit": 0.25,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    # ── Operations & Supply Chain ─────────────────────────────────────────
    "Operations Manager": {
        "skills_match": 0.20,
        "career_alignment": 0.25,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.20,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Supply Chain Manager": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Logistics Manager": {
        "skills_match": 0.20,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.25,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Procurement Manager": {
        "skills_match": 0.20,
        "career_alignment": 0.20,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Warehouse Manager": {
        "skills_match": 0.15,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.30,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Inventory Analyst": {
        "skills_match": 0.25,
        "career_alignment": 0.10,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.25,
        "growth_potential": 0.15,
        "remote_preference": 0.00,
    },
    "Demand Planner": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Supply Planner": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Quality Assurance Manager (Manufacturing)": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.25,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Process Improvement Specialist": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.15,
        "remote_preference": 0.00,
    },
    "Lean/Six Sigma Consultant": {
        "skills_match": 0.30,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Fleet Manager": {
        "skills_match": 0.15,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.35,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Distribution Manager": {
        "skills_match": 0.20,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.25,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "COO": {
        "skills_match": 0.15,
        "career_alignment": 0.30,
        "culture_fit": 0.15,
        "salary_match": 0.20,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    # ── Healthcare & Life Sciences ────────────────────────────────────────
    "Physician (General)": {
        "skills_match": 0.30,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.25,
        "growth_potential": 0.00,
        "remote_preference": 0.00,
    },
    "Surgeon": {
        "skills_match": 0.35,
        "career_alignment": 0.20,
        "culture_fit": 0.05,
        "salary_match": 0.15,
        "location_match": 0.25,
        "growth_potential": 0.00,
        "remote_preference": 0.00,
    },
    "Nurse Practitioner": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.25,
        "growth_potential": 0.00,
        "remote_preference": 0.00,
    },
    "Registered Nurse": {
        "skills_match": 0.25,
        "career_alignment": 0.10,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.25,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Clinical Research Associate": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.15,
        "remote_preference": 0.00,
    },
    "Clinical Data Manager": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Pharmacist": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.25,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Pharmacy Technician": {
        "skills_match": 0.25,
        "career_alignment": 0.10,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.25,
        "growth_potential": 0.15,
        "remote_preference": 0.00,
    },
    "Medical Laboratory Scientist": {
        "skills_match": 0.30,
        "career_alignment": 0.10,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.25,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Radiographer": {
        "skills_match": 0.30,
        "career_alignment": 0.10,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.30,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Physical Therapist": {
        "skills_match": 0.30,
        "career_alignment": 0.10,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.25,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Occupational Therapist": {
        "skills_match": 0.30,
        "career_alignment": 0.10,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.25,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Mental Health Counselor": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.20,
        "salary_match": 0.10,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Psychologist": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.20,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Dentist": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.25,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Optometrist": {
        "skills_match": 0.30,
        "career_alignment": 0.10,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.30,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Veterinarian": {
        "skills_match": 0.30,
        "career_alignment": 0.10,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.30,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Biomedical Engineer": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.05,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.15,
        "remote_preference": 0.00,
    },
    "Regulatory Affairs Specialist (Pharma)": {
        "skills_match": 0.30,
        "career_alignment": 0.20,
        "culture_fit": 0.05,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Medical Science Liaison": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Health Informatics Specialist": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.15,
        "remote_preference": 0.00,
    },
    "Hospital Administrator": {
        "skills_match": 0.15,
        "career_alignment": 0.25,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.25,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    # ── Education & Research ──────────────────────────────────────────────
    "University Professor": {
        "skills_match": 0.25,
        "career_alignment": 0.25,
        "culture_fit": 0.15,
        "salary_match": 0.10,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Lecturer": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.10,
        "location_match": 0.20,
        "growth_potential": 0.15,
        "remote_preference": 0.00,
    },
    "High School Teacher": {
        "skills_match": 0.20,
        "career_alignment": 0.10,
        "culture_fit": 0.20,
        "salary_match": 0.10,
        "location_match": 0.30,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Primary School Teacher": {
        "skills_match": 0.15,
        "career_alignment": 0.10,
        "culture_fit": 0.25,
        "salary_match": 0.10,
        "location_match": 0.30,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Special Education Teacher": {
        "skills_match": 0.20,
        "career_alignment": 0.10,
        "culture_fit": 0.25,
        "salary_match": 0.10,
        "location_match": 0.25,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "School Counselor": {
        "skills_match": 0.20,
        "career_alignment": 0.10,
        "culture_fit": 0.25,
        "salary_match": 0.10,
        "location_match": 0.25,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Academic Researcher": {
        "skills_match": 0.30,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.10,
        "location_match": 0.15,
        "growth_potential": 0.15,
        "remote_preference": 0.00,
    },
    "Postdoctoral Researcher": {
        "skills_match": 0.30,
        "career_alignment": 0.20,
        "culture_fit": 0.05,
        "salary_match": 0.10,
        "location_match": 0.15,
        "growth_potential": 0.20,
        "remote_preference": 0.00,
    },
    "Lab Manager": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.25,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Curriculum Developer": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.20,
        "salary_match": 0.10,
        "location_match": 0.10,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Instructional Designer": {
        "skills_match": 0.25,
        "career_alignment": 0.10,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Education Technology Specialist": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "University Administrator": {
        "skills_match": 0.15,
        "career_alignment": 0.25,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Dean": {
        "skills_match": 0.10,
        "career_alignment": 0.30,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Librarian": {
        "skills_match": 0.20,
        "career_alignment": 0.10,
        "culture_fit": 0.20,
        "salary_match": 0.10,
        "location_match": 0.25,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    # ── Engineering (Non-Software) ────────────────────────────────────────
    "Mechanical Engineer": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.20,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Civil Engineer": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.25,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Electrical Engineer": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Chemical Engineer": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.05,
        "salary_match": 0.15,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Environmental Engineer": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Structural Engineer": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.05,
        "salary_match": 0.15,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Aerospace Engineer": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.05,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.15,
        "remote_preference": 0.00,
    },
    "Automotive Engineer": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.05,
        "salary_match": 0.15,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Industrial Engineer": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Manufacturing Engineer": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.25,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Materials Engineer": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.05,
        "salary_match": 0.15,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Robotics Engineer": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.05,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.15,
        "remote_preference": 0.00,
    },
    "Control Systems Engineer": {
        "skills_match": 0.35,
        "career_alignment": 0.15,
        "culture_fit": 0.05,
        "salary_match": 0.15,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Project Engineer": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Chief Engineer": {
        "skills_match": 0.25,
        "career_alignment": 0.25,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.15,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    # ── Construction & Trades ─────────────────────────────────────────────
    "Construction Project Manager": {
        "skills_match": 0.20,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.30,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Site Manager": {
        "skills_match": 0.20,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.30,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Architect": {
        "skills_match": 0.30,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Interior Designer": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Urban Planner": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.15,
        "salary_match": 0.10,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Quantity Surveyor": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.05,
        "salary_match": 0.15,
        "location_match": 0.25,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Building Inspector": {
        "skills_match": 0.25,
        "career_alignment": 0.10,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.35,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Electrician": {
        "skills_match": 0.30,
        "career_alignment": 0.10,
        "culture_fit": 0.05,
        "salary_match": 0.15,
        "location_match": 0.35,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Plumber": {
        "skills_match": 0.30,
        "career_alignment": 0.10,
        "culture_fit": 0.05,
        "salary_match": 0.15,
        "location_match": 0.35,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "HVAC Technician": {
        "skills_match": 0.30,
        "career_alignment": 0.10,
        "culture_fit": 0.05,
        "salary_match": 0.15,
        "location_match": 0.35,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Carpenter": {
        "skills_match": 0.30,
        "career_alignment": 0.10,
        "culture_fit": 0.05,
        "salary_match": 0.15,
        "location_match": 0.35,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Welder": {
        "skills_match": 0.30,
        "career_alignment": 0.10,
        "culture_fit": 0.05,
        "salary_match": 0.15,
        "location_match": 0.35,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Heavy Equipment Operator": {
        "skills_match": 0.25,
        "career_alignment": 0.10,
        "culture_fit": 0.05,
        "salary_match": 0.15,
        "location_match": 0.40,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    # ── Media & Entertainment ─────────────────────────────────────────────
    "Journalist": {
        "skills_match": 0.20,
        "career_alignment": 0.15,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Editor": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Video Producer": {
        "skills_match": 0.25,
        "career_alignment": 0.10,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.05,
    },
    "Photographer": {
        "skills_match": 0.25,
        "career_alignment": 0.10,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Sound Engineer": {
        "skills_match": 0.30,
        "career_alignment": 0.10,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.25,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Film Director": {
        "skills_match": 0.20,
        "career_alignment": 0.25,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Animator": {
        "skills_match": 0.30,
        "career_alignment": 0.10,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.10,
    },
    "VFX Artist": {
        "skills_match": 0.30,
        "career_alignment": 0.10,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.10,
    },
    "Music Producer": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Podcast Producer": {
        "skills_match": 0.20,
        "career_alignment": 0.10,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.15,
        "remote_preference": 0.10,
    },
    "Broadcast Engineer": {
        "skills_match": 0.30,
        "career_alignment": 0.10,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.25,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Art Director (Advertising)": {
        "skills_match": 0.20,
        "career_alignment": 0.20,
        "culture_fit": 0.25,
        "salary_match": 0.15,
        "location_match": 0.10,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    # ── Hospitality & Service ─────────────────────────────────────────────
    "Hotel Manager": {
        "skills_match": 0.15,
        "career_alignment": 0.20,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.25,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Restaurant Manager": {
        "skills_match": 0.15,
        "career_alignment": 0.15,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.30,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Chef (Head/Executive)": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.20,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Sous Chef": {
        "skills_match": 0.25,
        "career_alignment": 0.10,
        "culture_fit": 0.15,
        "salary_match": 0.15,
        "location_match": 0.25,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Event Planner": {
        "skills_match": 0.15,
        "career_alignment": 0.10,
        "culture_fit": 0.25,
        "salary_match": 0.15,
        "location_match": 0.25,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Wedding Planner": {
        "skills_match": 0.15,
        "career_alignment": 0.10,
        "culture_fit": 0.25,
        "salary_match": 0.15,
        "location_match": 0.25,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Travel Agent": {
        "skills_match": 0.15,
        "career_alignment": 0.10,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.10,
    },
    "Concierge": {
        "skills_match": 0.10,
        "career_alignment": 0.10,
        "culture_fit": 0.25,
        "salary_match": 0.15,
        "location_match": 0.30,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Barista Manager": {
        "skills_match": 0.15,
        "career_alignment": 0.10,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.30,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Food & Beverage Director": {
        "skills_match": 0.15,
        "career_alignment": 0.25,
        "culture_fit": 0.15,
        "salary_match": 0.20,
        "location_match": 0.20,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    # ── Government & Public Sector ────────────────────────────────────────
    "Policy Analyst": {
        "skills_match": 0.20,
        "career_alignment": 0.20,
        "culture_fit": 0.20,
        "salary_match": 0.10,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Government Affairs Specialist": {
        "skills_match": 0.15,
        "career_alignment": 0.25,
        "culture_fit": 0.20,
        "salary_match": 0.10,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Diplomat": {
        "skills_match": 0.10,
        "career_alignment": 0.30,
        "culture_fit": 0.20,
        "salary_match": 0.10,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Intelligence Analyst": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.10,
        "salary_match": 0.10,
        "location_match": 0.25,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Urban Planner (Government)": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.15,
        "salary_match": 0.10,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Grant Writer": {
        "skills_match": 0.25,
        "career_alignment": 0.10,
        "culture_fit": 0.20,
        "salary_match": 0.10,
        "location_match": 0.10,
        "growth_potential": 0.15,
        "remote_preference": 0.10,
    },
    "Nonprofit Program Manager": {
        "skills_match": 0.15,
        "career_alignment": 0.20,
        "culture_fit": 0.25,
        "salary_match": 0.10,
        "location_match": 0.15,
        "growth_potential": 0.15,
        "remote_preference": 0.00,
    },
    "Fundraiser/Development Officer": {
        "skills_match": 0.10,
        "career_alignment": 0.20,
        "culture_fit": 0.25,
        "salary_match": 0.10,
        "location_match": 0.15,
        "growth_potential": 0.15,
        "remote_preference": 0.05,
    },
    "Social Worker": {
        "skills_match": 0.20,
        "career_alignment": 0.10,
        "culture_fit": 0.25,
        "salary_match": 0.10,
        "location_match": 0.25,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Public Health Specialist": {
        "skills_match": 0.25,
        "career_alignment": 0.20,
        "culture_fit": 0.15,
        "salary_match": 0.10,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    # ── Real Estate ───────────────────────────────────────────────────────
    "Real Estate Agent": {
        "skills_match": 0.10,
        "career_alignment": 0.15,
        "culture_fit": 0.20,
        "salary_match": 0.25,
        "location_match": 0.25,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Property Manager": {
        "skills_match": 0.15,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.20,
        "location_match": 0.30,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Real Estate Analyst": {
        "skills_match": 0.25,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Mortgage Broker": {
        "skills_match": 0.15,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.25,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Commercial Real Estate Agent": {
        "skills_match": 0.10,
        "career_alignment": 0.20,
        "culture_fit": 0.15,
        "salary_match": 0.25,
        "location_match": 0.25,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Real Estate Developer": {
        "skills_match": 0.15,
        "career_alignment": 0.25,
        "culture_fit": 0.10,
        "salary_match": 0.25,
        "location_match": 0.20,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Appraiser": {
        "skills_match": 0.25,
        "career_alignment": 0.10,
        "culture_fit": 0.10,
        "salary_match": 0.20,
        "location_match": 0.30,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    # ── Agriculture & Environment ─────────────────────────────────────────
    "Agricultural Engineer": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.25,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Environmental Scientist": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.20,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Conservation Officer": {
        "skills_match": 0.20,
        "career_alignment": 0.15,
        "culture_fit": 0.15,
        "salary_match": 0.10,
        "location_match": 0.30,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Sustainability Manager": {
        "skills_match": 0.20,
        "career_alignment": 0.20,
        "culture_fit": 0.20,
        "salary_match": 0.15,
        "location_match": 0.15,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
    "Forester": {
        "skills_match": 0.25,
        "career_alignment": 0.10,
        "culture_fit": 0.10,
        "salary_match": 0.15,
        "location_match": 0.35,
        "growth_potential": 0.05,
        "remote_preference": 0.00,
    },
    "Marine Biologist": {
        "skills_match": 0.30,
        "career_alignment": 0.15,
        "culture_fit": 0.10,
        "salary_match": 0.10,
        "location_match": 0.25,
        "growth_potential": 0.10,
        "remote_preference": 0.00,
    },
}


# ---------------------------------------------------------------------------
# Scoring rubric & calibration (Epic 1 / G-269)
# ---------------------------------------------------------------------------

RUBRIC_VERSION = "v1.1"

SCORING_RUBRIC = """\
## Scoring Rubric

Use these band definitions to anchor your fit_score:

- **9-10 (Dream fit):** Role, skills, seniority, domain, and location all align. \
The candidate would be a top-5% applicant AND the role precisely matches their \
stated career goals and target job family. A prestigious company alone does not \
make a 9 — the role type must also be an exact match. Virtually no gaps.
- **7-8 (Strong fit):** Most dimensions match well. Minor gaps exist (e.g. one \
missing tool, slight seniority stretch) but the candidate is clearly competitive.
- **5-6 (Moderate fit):** Partial overlap — some skills transfer, but meaningful \
gaps in domain, seniority, or core requirements. Could succeed with ramp-up.
- **3-4 (Weak fit):** Few dimensions align. Major gaps in multiple areas. \
The candidate would need significant retraining or a career pivot.
- **1-2 (Poor fit):** Near-total mismatch on role type, skills, and domain. \
Applying would waste time for both sides.

### Calibration Examples

**Example 1 — Score: 2.0**
JD: "Senior .NET Developer — build enterprise ERP modules in C#/.NET, Azure DevOps, \
SQL Server. 5+ years .NET required."
Profile: TPM with Python/AI focus, no .NET or ERP experience.
Reasoning: Complete skills mismatch (Python vs .NET), wrong role type (TPM vs SWE), \
unrelated domain. Score: 2.0

**Example 2 — Score: 5.0**
JD: "Product Manager, Growth — own activation funnels, run A/B experiments, SQL \
proficiency, B2C SaaS experience."
Profile: TPM with some PM overlap, strong SQL, but B2B enterprise background.
Reasoning: Transferable analytical skills and SQL, but wrong domain (B2B vs B2C), \
no growth/activation experience. Center of the moderate range. Score: 5.0

**Example 3 — Score: 8.5**
JD: "Technical Program Manager, AI Platform — coordinate ML infrastructure teams, \
drive cross-functional delivery, Python scripting, stakeholder management."
Profile: TPM with strong AI/ML platform experience, Python proficiency, proven \
cross-functional leadership.
Reasoning: Direct role match, strong technical overlap, relevant domain experience. \
Minor gap: specific ML infra tooling. Score: 8.5

**Example 4 — Score: 7.5**
JD: "Staff TPM, AI Platform — own delivery roadmap for ML infrastructure, \
coordinate 6 engineering teams, Python scripting, budget oversight."
Profile: TPM with strong AI/ML platform experience, Python proficiency, proven \
cross-functional leadership.
Reasoning: Excellent role-type and domain match. Strong seniority fit. \
Missing: specific ML infrastructure tooling experience and budget management \
at staff level. Competitive but not top-5%. Score: 7.5
"""


def _build_job_family_modifiers(job_family: str | None) -> str:
    """Generate rubric modifiers based on the active job family weights.

    Highlights which dimensions carry more or less weight for the given
    job family so the AI calibrates accordingly.
    """
    if not job_family:
        return ""

    weights = _weights_for_job_family(job_family)
    if weights == DEFAULT_WEIGHTS:
        return ""

    # Identify dimensions that deviate meaningfully from the default
    modifier_lines: list[str] = []
    for dim, weight in weights.items():
        default_w = DEFAULT_WEIGHTS.get(dim, 0.0)
        diff = weight - default_w
        label = dim.replace("_", " ")
        if diff >= 0.05:
            modifier_lines.append(
                f"- For {job_family}: {label} is weighted higher ({weight:.0%} vs "
                f"default {default_w:.0%}) — gaps here are more penalizing."
            )
        elif diff <= -0.05:
            modifier_lines.append(
                f"- For {job_family}: {label} is weighted lower ({weight:.0%} vs "
                f"default {default_w:.0%}) — gaps here matter less."
            )

    if not modifier_lines:
        return ""

    return "\n### Job-Family Weight Modifiers\n" + "\n".join(modifier_lines) + "\n"


def _weights_for_job_family(job_family: str | None) -> dict[str, float]:
    """Return the default weight preset for a given job family.

    Falls back to DEFAULT_WEIGHTS for unknown or None job families.
    Lookup is case-insensitive with stripped whitespace.
    """
    if not job_family:
        return dict(DEFAULT_WEIGHTS)

    normalized = job_family.strip()
    # Try exact match first
    if normalized in JOB_FAMILY_WEIGHTS:
        return dict(JOB_FAMILY_WEIGHTS[normalized])

    # Try case-insensitive match
    lower = normalized.lower()
    for key, preset in JOB_FAMILY_WEIGHTS.items():
        if key.lower() == lower:
            return dict(preset)

    # Fuzzy match: check if any preset name is contained in or contains the query
    for preset_name, weights in JOB_FAMILY_WEIGHTS.items():
        if lower in preset_name.lower() or preset_name.lower() in lower:
            return dict(weights)

    return dict(DEFAULT_WEIGHTS)


# ---------------------------------------------------------------------------
# Weight management
# ---------------------------------------------------------------------------


def get_or_create_weights(db: Session, profile_id: int) -> ScoringWeights:
    """Get scoring weights for a profile, creating defaults if none exist.

    When creating new weights, uses job-family-specific defaults based on
    the profile's current job_family setting.
    """
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise ProfileNotFoundError(f"Profile {profile_id} not found")

    weights = db.query(ScoringWeights).filter(ScoringWeights.profile_id == profile_id).first()
    if not weights:
        preset = _weights_for_job_family(profile.job_family)
        weights = ScoringWeights(profile_id=profile_id, **preset)
        db.add(weights)
        db.commit()
        db.refresh(weights)

    return weights


def update_weights(db: Session, profile_id: int, data: dict[str, float]) -> ScoringWeights:
    """Update scoring weights for a profile. Marks existing scores as stale."""
    weights = get_or_create_weights(db, profile_id)

    for field_name, value in data.items():
        if hasattr(weights, field_name) and value is not None:
            setattr(weights, field_name, value)

    # Mark all existing scores as stale and null out cached fit_scores
    flag_stale_scores(db, profile_id)

    db.refresh(weights)
    return weights


def regenerate_weights_for_job_family(
    db: Session, profile_id: int, job_family: str | None
) -> ScoringWeights:
    """Delete existing scoring weights and recreate with job-family defaults.

    Called when a profile's job_family changes (VAL-CROSS-004) so that
    GET /api/scoring-weights returns job-family-appropriate values.
    """
    # Delete existing weights row if any
    db.query(ScoringWeights).filter(ScoringWeights.profile_id == profile_id).delete()
    db.flush()

    # Create fresh weights using the new job_family preset
    preset = _weights_for_job_family(job_family)
    weights = ScoringWeights(profile_id=profile_id, **preset)
    db.add(weights)
    db.commit()
    db.refresh(weights)
    return weights


# ---------------------------------------------------------------------------
# Profile data gathering (for scoring context)
# ---------------------------------------------------------------------------


def _gather_profile_data(db: Session, profile: Profile) -> dict:
    """Gather all profile data relevant for scoring.

    Includes skills, goals, and market positioning data (VAL-CROSS-010).
    """
    # Skills
    skills = db.query(Skill).filter(Skill.profile_id == profile.id).all()
    skills_data = [
        {
            "name": s.name,
            "category": s.category,
            "proficiency": s.proficiency,
        }
        for s in skills
    ]

    # Goals
    goals = db.query(Goal).filter(Goal.profile_id == profile.id, Goal.status == "active").all()
    goals_data = [
        {
            "title": g.title,
            "type": g.goal_type,
            "description": g.description,
        }
        for g in goals
    ]

    # Market positioning data (VAL-CROSS-010)
    market_data: dict = {}
    try:
        from career_os.services.market import get_market_positioning

        positioning = get_market_positioning(db, profile.id)
        market_data = {
            "positions": positioning.get("positions", []),
            "last_refreshed_at": positioning.get("last_refreshed_at"),
        }
    except Exception:
        # Market data is supplementary — scoring must not fail if unavailable
        logger.debug("Market positioning data unavailable for profile %d", profile.id)

    return {
        "name": profile.name,
        "location": profile.location,
        "job_family": profile.job_family,
        "email": profile.email,
        "skills": skills_data,
        "goals": goals_data,
        "market_positioning": market_data,
    }


# ---------------------------------------------------------------------------
# Single Job Scoring
# ---------------------------------------------------------------------------


def _validate_scoring_inputs(
    db: Session,
    profile_id: int,
    application_id: int | None,
    discovered_job_id: int | None,
) -> Profile:
    """Validate profile, discovered job, and application exist for scoring.

    Returns the Profile on success.
    Raises ProfileNotFoundError or JobNotFoundError on failure.
    """
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise ProfileNotFoundError(f"Profile {profile_id} not found")

    if discovered_job_id is not None:
        dj = (
            db.query(DiscoveredJob)
            .filter(
                DiscoveredJob.id == discovered_job_id,
                DiscoveredJob.profile_id == profile_id,
            )
            .first()
        )
        if not dj:
            raise JobNotFoundError(
                f"Discovered job {discovered_job_id} not found for profile {profile_id}"
            )

    if application_id is not None:
        app = (
            db.query(Application)
            .filter(
                Application.id == application_id,
                Application.profile_id == profile_id,
            )
            .first()
        )
        if not app:
            raise JobNotFoundError(
                f"Application {application_id} not found for profile {profile_id}"
            )

    return profile


def _gather_scoring_context(db: Session, profile: Profile, profile_id: int) -> dict:
    """Gather profile data and scoring weights into a single context dict."""
    weights = get_or_create_weights(db, profile_id)
    profile_data = _gather_profile_data(db, profile)
    profile_data["weights"] = weights.to_dict()
    return profile_data


def build_profile_data(db: Session, profile_id: int) -> dict:
    """Public entry point to gather profile data for batch scoring.

    Validates the profile exists and is complete enough for scoring,
    then returns the full scoring context (profile + weights).

    Args:
        db: Database session.
        profile_id: Profile ID to gather data for.

    Returns:
        Profile data dict suitable for AI provider scoring calls.

    Raises:
        ProfileNotFoundError: If the profile does not exist.
        ProfileIncompleteError: If required profile fields are missing.
    """
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise ProfileNotFoundError(f"Profile {profile_id} not found")

    # Basic completeness check — name is the minimum bar
    if not profile.name:
        raise ProfileIncompleteError("Profile is missing required fields for scoring (name).")

    return _gather_scoring_context(db, profile, profile_id)


def _gather_red_flag_metadata(
    db: Session,
    discovered_job_id: int | None,
    job_title: str | None,
) -> dict:
    """Gather metadata from linked DiscoveredJob for red-flag detection."""
    rf: dict = {"posted_at": None, "title": job_title, "salary": None, "location": None}
    if discovered_job_id is not None:
        dj_meta = db.query(DiscoveredJob).filter(DiscoveredJob.id == discovered_job_id).first()
        if dj_meta is not None:
            rf["posted_at"] = dj_meta.posted_at
            rf["title"] = rf["title"] or dj_meta.title
            rf["salary"] = dj_meta.salary_range
            rf["location"] = dj_meta.location
    return rf


# ---------------------------------------------------------------------------
# Desire Score — Option A (Derived from dimensional scores + goals)
# ---------------------------------------------------------------------------

# Default weights for deriving desire_score from dimensional sub-scores.
# career_trajectory = growth potential, company_fit = culture/reputation,
# compensation_fit = salary attractiveness.
DEFAULT_DESIRE_WEIGHTS: dict[str, float] = {
    "career_trajectory": 0.35,
    "company_fit": 0.35,
    "compensation_fit": 0.30,
}

# Keywords in goal titles/descriptions that shift desire weights.
_GOAL_WEIGHT_ADJUSTMENTS: dict[str, dict[str, float]] = {
    "leadership": {"career_trajectory": 0.50, "company_fit": 0.25, "compensation_fit": 0.25},
    "management": {"career_trajectory": 0.50, "company_fit": 0.25, "compensation_fit": 0.25},
    "compensation": {"career_trajectory": 0.20, "company_fit": 0.25, "compensation_fit": 0.55},
    "salary": {"career_trajectory": 0.20, "company_fit": 0.25, "compensation_fit": 0.55},
    "culture": {"career_trajectory": 0.25, "company_fit": 0.50, "compensation_fit": 0.25},
    "remote": {"career_trajectory": 0.25, "company_fit": 0.50, "compensation_fit": 0.25},
}


def _resolve_desire_weights(goals: list[dict]) -> dict[str, float]:
    """Determine desire weights based on user's active goals.

    If any goal title/description contains keywords like "leadership",
    "compensation", etc., we shift the weights to match user priorities.
    Falls back to DEFAULT_DESIRE_WEIGHTS if no keywords match.
    """
    if not goals:
        return dict(DEFAULT_DESIRE_WEIGHTS)

    all_goal_text = " ".join(
        f"{g.get('title', '')} {g.get('description', '')}".lower() for g in goals
    )

    for keyword, weights in _GOAL_WEIGHT_ADJUSTMENTS.items():
        if keyword in all_goal_text:
            return dict(weights)

    return dict(DEFAULT_DESIRE_WEIGHTS)


def compute_derived_desire_score(
    dimensional_scores: dict[str, float] | None,
    goals: list[dict] | None = None,
) -> float | None:
    """Compute desire_score as a weighted average of dimensional sub-scores.

    Option A: derived from existing dimensions — no additional AI call.

    Args:
        dimensional_scores: Dict with keys career_trajectory, company_fit,
            compensation_fit (each 0-10). None → returns None.
        goals: List of goal dicts with title/description for weight adjustment.

    Returns:
        Float 0-10 rounded to 1 decimal, or None if dimensions unavailable.
    """
    if dimensional_scores is None:
        return None

    # Check that the required dimensions are present
    required = ("career_trajectory", "company_fit", "compensation_fit")
    if not all(dimensional_scores.get(k) is not None for k in required):
        return None

    weights = _resolve_desire_weights(goals or [])

    score = sum(dimensional_scores[dim] * weight for dim, weight in weights.items())

    # Clamp to [0, 10]
    return round(max(0.0, min(10.0, score)), 1)


def _build_dim_columns(dim) -> dict[str, float | None]:
    """Build dimensional score columns dict from AI result."""
    if dim is None:
        return {
            "dim_technical_fit": None,
            "dim_seniority_alignment": None,
            "dim_compensation_fit": None,
            "dim_location_fit": None,
            "dim_career_trajectory": None,
            "dim_company_fit": None,
        }
    return {
        "dim_technical_fit": dim.technical_fit,
        "dim_seniority_alignment": dim.seniority_alignment,
        "dim_compensation_fit": dim.compensation_fit,
        "dim_location_fit": dim.location_fit,
        "dim_career_trajectory": dim.career_trajectory,
        "dim_company_fit": dim.company_fit,
    }


# ---------------------------------------------------------------------------
# Borderline 2-Pass Scoring (Epic 5 / G-273)
# ---------------------------------------------------------------------------


def _apply_role_fit_gate(score_data: ScoreResult) -> ScoreResult:
    """Enforce the role-fit hard gate (G-1335), logging when it fires.

    Thin logging wrapper over :func:`apply_role_fit_gate` so the service records
    a cap event. The actual cap logic is a pure schema-layer function shared with
    the multi-job batch path.
    """
    if role_fit_gate_failed(score_data) and score_data.fit_score > ROLE_FIT_GATE_CEILING:
        reasons: list[str] = []
        if score_data.role_match is not None and not score_data.role_match.is_same_role_family:
            reasons.append("role-family mismatch")
        if score_data.disqualifiers:
            reasons.append(f"disqualifiers={score_data.disqualifiers}")
        logger.info(
            "Role-fit gate: capping fit_score %.2f → %.1f (%s)",
            score_data.fit_score,
            ROLE_FIT_GATE_CEILING,
            ", ".join(reasons),
        )
    return apply_role_fit_gate(score_data)


def _average_score_results(a: ScoreResult, b: ScoreResult) -> ScoreResult:
    """Average two ScoreResult objects to reduce borderline scoring variance.

    Numeric fields are averaged.  For qualitative fields, the result with the
    higher fit_score contributes the reasoning/prep_notes (richer context).
    ATS keywords come from whichever result has more keywords.
    score_breakdown factors are deduplicated by factor name and their
    contributions averaged.
    """
    # Determine which result has the richer reasoning (higher fit_score wins)
    primary, secondary = (a, b) if a.fit_score >= b.fit_score else (b, a)

    # Average numeric fields
    avg_fit = round((a.fit_score + b.fit_score) / 2, 2)
    avg_readiness = round((a.readiness_score + b.readiness_score) / 2, 2)
    avg_career_alignment = round((a.career_alignment + b.career_alignment) / 2, 2)

    # Average dimensional scores if both are present
    from career_os.schemas.ai import DimensionalScores

    averaged_dims: DimensionalScores | None = None

    if a.dimensional_scores is not None and b.dimensional_scores is not None:
        ad = a.dimensional_scores
        bd = b.dimensional_scores
        averaged_dims = DimensionalScores(
            technical_fit=round((ad.technical_fit + bd.technical_fit) / 2, 2),
            seniority_alignment=round((ad.seniority_alignment + bd.seniority_alignment) / 2, 2),
            compensation_fit=round((ad.compensation_fit + bd.compensation_fit) / 2, 2),
            location_fit=round((ad.location_fit + bd.location_fit) / 2, 2),
            career_trajectory=round((ad.career_trajectory + bd.career_trajectory) / 2, 2),
            company_fit=round((ad.company_fit + bd.company_fit) / 2, 2),
        )
    else:
        averaged_dims = primary.dimensional_scores

    # Merge score_breakdown: deduplicate by factor name, average contributions
    breakdown_by_factor: dict[str, list] = {}
    from career_os.schemas.ai import ScoreBreakdownFactor

    for factor in list(a.score_breakdown) + list(b.score_breakdown):
        breakdown_by_factor.setdefault(factor.factor, []).append(factor)

    merged_breakdown: list[ScoreBreakdownFactor] = []
    for factor_name, factors in breakdown_by_factor.items():
        avg_contribution = round(sum(f.contribution for f in factors) / len(factors), 3)
        # Use description from whichever came from the primary (higher-score) result
        desc = next(
            (f.description for f in factors if f in primary.score_breakdown), factors[0].description
        )
        merged_breakdown.append(
            ScoreBreakdownFactor(
                factor=factor_name,
                contribution=avg_contribution,
                description=desc,
            )
        )

    # ATS keywords: keep the longer list
    ats_keywords = a.ats_keywords if len(a.ats_keywords) >= len(b.ats_keywords) else b.ats_keywords

    # Average desire score if both have it
    desire_score: float | None = None
    if a.desire_score is not None and b.desire_score is not None:
        desire_score = round((a.desire_score + b.desire_score) / 2, 2)
    else:
        desire_score = primary.desire_score

    # Carry forward the role-fit gate fields (G-1335), failing closed: if either
    # pass flagged a role mismatch or any disqualifier, the merged result
    # inherits it so the code-enforced cap still fires after averaging.
    role_mismatch = any(
        r.role_match is not None and not r.role_match.is_same_role_family for r in (a, b)
    )
    merged_role_match: RoleMatch | None = None
    if a.role_match is not None or b.role_match is not None:
        evidence = next(
            (
                r.role_match.evidence
                for r in (primary, secondary)
                if r.role_match is not None and r.role_match.evidence
            ),
            "",
        )
        merged_role_match = RoleMatch(is_same_role_family=not role_mismatch, evidence=evidence)
    merged_disqualifiers = list(dict.fromkeys([*a.disqualifiers, *b.disqualifiers]))

    return ScoreResult(
        role_match=merged_role_match,
        disqualifiers=merged_disqualifiers,
        fit_score=avg_fit,
        readiness_score=avg_readiness,
        career_alignment=avg_career_alignment,
        reasoning=primary.reasoning,
        estimated_salary=primary.estimated_salary,
        effort_flag=primary.effort_flag,
        prep_level=primary.prep_level,
        prep_notes=primary.prep_notes,
        score_breakdown=merged_breakdown,
        dimensional_scores=averaged_dims,
        ats_keywords=ats_keywords,
        desire_score=desire_score,
        desire_reasoning=primary.desire_reasoning,
    )


def _update_linked_scores(
    db: Session,
    fit_score: float,
    discovered_job_id: int | None,
    application_id: int | None,
) -> None:
    """Propagate fit_score to linked DiscoveredJob and/or Application."""
    if discovered_job_id is not None:
        dj = db.query(DiscoveredJob).filter(DiscoveredJob.id == discovered_job_id).first()
        if dj:
            dj.fit_score = fit_score
    if application_id is not None:
        app_record = db.query(Application).filter(Application.id == application_id).first()
        if app_record:
            app_record.fit_score = fit_score


async def score_job(
    db: Session,
    profile_id: int,
    job_description: str,
    *,
    job_url: str | None = None,
    job_title: str | None = None,
    job_company: str | None = None,
    discovered_job_id: int | None = None,
    application_id: int | None = None,
) -> ScoredJob:
    """Score a single job against a profile.

    Returns a ScoredJob record persisted in the database.
    """
    profile = _validate_scoring_inputs(db, profile_id, application_id, discovered_job_id)

    # Guard: profile must have target roles and location for meaningful scores
    if not profile.job_family or not profile.location:
        missing = []
        if not profile.job_family:
            missing.append("target roles")
        if not profile.location:
            missing.append("location")
        raise ProfileIncompleteError(
            f"Fill in your profile ({', '.join(missing)}) for personalized scores"
        )

    # Gather profile data and weights for scoring
    profile_data = _gather_scoring_context(db, profile, profile_id)

    # Fetch calibration examples when feature flag is enabled
    calibration_examples: list[dict] = []
    if settings.feedback_calibration_enabled:
        calibration_examples = get_feedback_calibration(db, profile_id)

    # Build scoring prompt with job context
    prompt = _build_scoring_prompt(
        job_description=job_description,
        job_title=job_title,
        job_company=job_company,
        job_url=job_url,
        profile_data=profile_data,
        calibration_examples=calibration_examples,
    )

    # Score via AI provider
    provider = get_ai_provider()
    response = await provider.score(
        job_description=prompt,
        profile_data=profile_data,
    )

    # Extract structured score result
    if response.structured and isinstance(response.structured, ScoreResult):
        score_data = response.structured
    else:
        raise ScoringError("AI provider did not return a valid ScoreResult")

    # Role-fit hard gate (G-1335): cap fit_score in code so company prestige +
    # domain can never substitute for role fit. Applied before the borderline
    # check so a gated (≤3) job also skips the extra second-pass AI call.
    score_data = _apply_role_fit_gate(score_data)

    # Borderline 2-pass scoring (Epic 5 / G-273)
    # When the first-pass score falls in the borderline zone, run a second pass
    # and average the results to reduce variance (~50% reduction per research).
    scoring_passes = 1
    if (
        settings.borderline_scoring_enabled
        and settings.borderline_low_threshold
        <= score_data.fit_score
        <= settings.borderline_high_threshold
    ):
        logger.info(
            "Borderline score %.2f (zone [%.1f, %.1f]), running second scoring pass",
            score_data.fit_score,
            settings.borderline_low_threshold,
            settings.borderline_high_threshold,
        )
        try:
            response2 = await provider.score(
                job_description=prompt,
                profile_data=profile_data,
            )
            if response2.structured and isinstance(response2.structured, ScoreResult):
                score_data2 = response2.structured
                score_data = _average_score_results(score_data, score_data2)
                scoring_passes = 2
                logger.info(
                    "Averaged borderline scores: pass1=%.2f pass2=%.2f → avg=%.2f",
                    score_data2.fit_score,  # original first-pass stored before averaging
                    response2.structured.fit_score,
                    score_data.fit_score,
                )
            else:
                logger.warning(
                    "Second scoring pass did not return a valid ScoreResult — "
                    "using single-pass score %.2f",
                    score_data.fit_score,
                )
        except Exception as exc:
            logger.warning(
                "Second scoring pass failed (%s) — using single-pass score %.2f",
                exc,
                score_data.fit_score,
            )

    # Re-apply the role-fit gate after averaging — the merged result fails closed
    # (inherits a mismatch/disqualifier flagged by either pass), so a borderline
    # job that a second pass reveals as a role mismatch still gets capped.
    score_data = _apply_role_fit_gate(score_data)

    # Serialize score_breakdown to JSON for storage
    breakdown_json = (
        json.dumps([f.model_dump() for f in score_data.score_breakdown])
        if score_data.score_breakdown
        else None
    )

    # Rule-based red flags (zero AI cost)
    rf = _gather_red_flag_metadata(db, discovered_job_id, job_title)
    red_flags = detect_red_flags(
        job_description,
        posted_at=rf["posted_at"],
        title=rf["title"],
        salary_range=rf["salary"],
        location=rf["location"],
    )

    # Data-driven red flags: ghost job and multi-city blast detection (G-270)
    # Only runs when we have company and title context from a discovered job.
    effective_title = rf["title"] or job_title
    if job_company and effective_title:
        ghost_flags = detect_data_driven_red_flags(
            db,
            company=job_company,
            title=effective_title,
            description=job_description,
            profile_id=profile_id,
        )
        red_flags = red_flags + ghost_flags

    red_flags_json = json.dumps(red_flags) if red_flags else None

    # Dimensional sub-scores
    dim_columns = _build_dim_columns(score_data.dimensional_scores)

    # ATS keywords: serialize the list of {keyword, category, matched} to JSON
    # text. Empty list → NULL so legacy rows remain unchanged.
    ats_keywords_json = (
        json.dumps([kw.model_dump() for kw in score_data.ats_keywords])
        if score_data.ats_keywords
        else None
    )

    # Desire score computation (dual-score architecture, G-275)
    desire_score = None
    desire_score_method = None
    desire_reasoning = None

    # Option B: AI-generated desire_score (if the provider returned one)
    if score_data.desire_score is not None:
        desire_score = score_data.desire_score
        desire_score_method = "ai_generated"
        desire_reasoning = score_data.desire_reasoning

    # Option A fallback: derive from dimensional scores + goals
    if desire_score is None and score_data.dimensional_scores is not None:
        dim_dict = {
            "career_trajectory": score_data.dimensional_scores.career_trajectory,
            "company_fit": score_data.dimensional_scores.company_fit,
            "compensation_fit": score_data.dimensional_scores.compensation_fit,
        }
        desire_score = compute_derived_desire_score(dim_dict, profile_data.get("goals"))
        if desire_score is not None:
            desire_score_method = "derived"

    # Persist the score
    scored_job = ScoredJob(
        profile_id=profile_id,
        discovered_job_id=discovered_job_id,
        application_id=application_id,
        fit_score=score_data.fit_score,
        readiness_score=score_data.readiness_score,
        career_alignment=score_data.career_alignment,
        reasoning=score_data.reasoning,
        estimated_salary=score_data.estimated_salary,
        effort_flag=score_data.effort_flag,
        prep_level=score_data.prep_level,
        prep_notes=score_data.prep_notes,
        score_breakdown=breakdown_json,
        red_flags=red_flags_json,
        ats_keywords=ats_keywords_json,
        is_stale=False,
        weights_snapshot=json.dumps({**profile_data["weights"], "rubric_version": RUBRIC_VERSION}),
        desire_score=desire_score,
        desire_score_method=desire_score_method,
        desire_reasoning=desire_reasoning,
        scoring_passes=scoring_passes,
        **dim_columns,
    )
    db.add(scored_job)

    # Propagate fit_score to linked records
    _update_linked_scores(db, score_data.fit_score, discovered_job_id, application_id)

    db.commit()
    db.refresh(scored_job)

    # Shadow-mode (G-1336, finding I): when SCORING_SHADOW_VARIANT is set, score
    # this same job with a DISTINCT candidate provider/model and log it beside the
    # live score — never surfaced. Fire-and-forget (its own task + DB session) so
    # it adds no latency to the live score, and fully defensive (a shadow failure
    # never breaks live scoring). No-ops cleanly if the variant can't resolve.
    if settings.scoring_shadow_variant.strip():
        from career_os.services.scoring_shadow import schedule_shadow_score

        schedule_shadow_score(
            profile_id=profile_id,
            prompt=prompt,
            profile_data=profile_data,
            primary_fit_score=score_data.fit_score,
            scored_job_id=scored_job.id,
            discovered_job_id=discovered_job_id,
            live_provider_name=provider.name,
        )

    # Distillation-label logging (G-1338, finding M): opportunistically record the
    # (structured signals, LLM score) training tuple for a future small local
    # feature model. No LLM cost — records what already happened. Off by default
    # (DISTILLATION_LOGGING_ENABLED) and fully defensive: a logging failure never
    # affects the already-committed score above.
    if settings.distillation_logging_enabled:
        from career_os.services.distillation import log_distillation_sample
        from career_os.services.esco_features import compute_esco_features

        # ESCO quantitative features (G-1338, finding L) — non-LLM structured
        # signals (skills-overlap + title→occupation axis). Best-effort and
        # additive: never changes what was sent to the LLM, only enriches the
        # (off-by-default) training tuple.
        esco = compute_esco_features(
            db,
            profile_id=profile_id,
            application_id=application_id,
            jd_title=job_title,
            candidate_role=profile_data.get("job_family"),
        )
        log_distillation_sample(
            db,
            profile_id=profile_id,
            score_result=score_data,
            profile_data=profile_data,
            scored_job_id=scored_job.id,
            discovered_job_id=discovered_job_id,
            rubric_version=RUBRIC_VERSION,
            extra_signals={"esco": esco} if esco else None,
        )

    return scored_job


def _format_skills_section(skills: list[dict]) -> list[str]:
    """Format skills into prompt lines."""
    if not skills:
        return []
    lines = ["\nSkills:"]
    for skill in skills[:20]:  # Limit to avoid huge prompts
        lines.append(f"  - {skill['name']} ({skill['category']}, {skill['proficiency']})")
    return lines


def _format_goals_section(goals: list[dict]) -> list[str]:
    """Format goals into prompt lines."""
    if not goals:
        return []
    lines = ["\nCareer Goals:"]
    for goal in goals[:5]:
        lines.append(f"  - {goal['title']} ({goal['type']})")
    return lines


def _format_market_section(market: dict) -> list[str]:
    """Format market positioning into prompt lines (VAL-CROSS-010)."""
    positions = market.get("positions", [])
    if not positions:
        return []
    lines = ["\nMarket Positioning:"]
    for pos in positions[:5]:
        lines.append(
            f"  - {pos['role_type']}: {pos['match_percentage']}% match "
            f"({pos['total_roles_analyzed']} roles analyzed)"
        )
    return lines


def _format_calibration_section(calibration_examples: list[dict]) -> list[str]:
    """Format feedback calibration examples into prompt lines.

    Tells the AI how the user previously corrected scores so it can adjust
    its scoring tendencies for this profile.
    """
    if not calibration_examples:
        return []
    lines = ["\nScoring Calibration (user corrections on past scores — adjust accordingly):"]
    for ex in calibration_examples:
        title = ex.get("job_title") or "Unknown role"
        company = ex.get("company") or "Unknown company"
        ai = ex.get("ai_score", "?")
        user = ex.get("user_score", "?")
        reason = ex.get("reason")
        line = f"  - {title} @ {company}: AI scored {ai}, user corrected to {user}"
        if reason:
            line += f" (reason: {reason})"
        lines.append(line)
    return lines


def _build_scoring_prompt(
    *,
    job_description: str,
    job_title: str | None = None,
    job_company: str | None = None,
    job_url: str | None = None,
    profile_data: dict,
    calibration_examples: list[dict] | None = None,
) -> str:
    """Build a scoring prompt combining job info and profile context."""
    parts = ["Score this job against the candidate profile.\n"]

    if job_title:
        parts.append(f"Job Title: {job_title}")
    if job_company:
        parts.append(f"Company: {job_company}")
    if job_url:
        parts.append(f"URL: {job_url}")
    parts.append(f"\nJob Description:\n{job_description}\n")

    parts.append("\nCandidate Profile:")
    parts.append(f"Name: {profile_data.get('name', 'Unknown')}")
    parts.append(f"Location: {profile_data.get('location', 'Unknown')}")
    parts.append(f"Job Family: {profile_data.get('job_family', 'Unknown')}")

    parts.extend(_format_skills_section(profile_data.get("skills", [])))
    parts.extend(_format_goals_section(profile_data.get("goals", [])))
    parts.extend(_format_market_section(profile_data.get("market_positioning", {})))

    # Scoring rubric with calibration examples (G-269)
    parts.append(f"\n{SCORING_RUBRIC}")
    # NB: the role-fit / anti-halo guardrails (G-1335) live in the provider
    # score preamble (ai/base.ROLE_FIT_GATE_PROMPT), NOT here. Keeping them out
    # of _build_scoring_prompt keeps the deterministic golden-set snapshot
    # (which hashes this prompt) stable, while real providers still receive the
    # guard via their own preamble.
    job_family = profile_data.get("job_family")
    family_modifiers = _build_job_family_modifiers(job_family)
    if family_modifiers:
        parts.append(family_modifiers)

    if profile_data.get("weights"):
        parts.append(f"\nScoring Weights: {json.dumps(profile_data['weights'])}")

    parts.extend(_format_calibration_section(calibration_examples or []))

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Batch Scoring
# ---------------------------------------------------------------------------


def _query_jobs_to_score(
    db: Session,
    profile_id: int,
    discovered_job_ids: list[int] | None,
    rescore_stale: bool,
) -> list:
    """Return the list of DiscoveredJob rows to score."""
    if discovered_job_ids:
        return (
            db.query(DiscoveredJob)
            .filter(
                DiscoveredJob.profile_id == profile_id,
                DiscoveredJob.id.in_(discovered_job_ids),
            )
            .all()
        )
    if rescore_stale:
        fresh_scored_ids = db.query(ScoredJob.discovered_job_id).filter(
            ScoredJob.profile_id == profile_id,
            ScoredJob.discovered_job_id.isnot(None),
            ScoredJob.is_stale.is_(False),
        )
        return (
            db.query(DiscoveredJob)
            .filter(
                DiscoveredJob.profile_id == profile_id,
                DiscoveredJob.id.notin_(fresh_scored_ids),
            )
            .all()
        )
    any_scored_ids = db.query(ScoredJob.discovered_job_id).filter(
        ScoredJob.profile_id == profile_id,
        ScoredJob.discovered_job_id.isnot(None),
    )
    return (
        db.query(DiscoveredJob)
        .filter(
            DiscoveredJob.profile_id == profile_id,
            DiscoveredJob.id.notin_(any_scored_ids),
        )
        .all()
    )


async def batch_score_discovery(
    db: Session,
    profile_id: int,
    *,
    discovered_job_ids: list[int] | None = None,
    rescore_stale: bool = False,
) -> dict:
    """Score multiple discovered jobs in batch.

    If discovered_job_ids is empty/None, scores all unscored jobs for the profile.
    Returns dict with scored_count, total_time_seconds, scores, errors.
    """
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise ProfileNotFoundError(f"Profile {profile_id} not found")

    # Guard: profile must have target roles and location for meaningful scores
    if not profile.job_family or not profile.location:
        missing = []
        if not profile.job_family:
            missing.append("target roles")
        if not profile.location:
            missing.append("location")
        raise ProfileIncompleteError(
            f"Fill in your profile ({', '.join(missing)}) for personalized scores"
        )

    start_time = time.monotonic()

    jobs = _query_jobs_to_score(db, profile_id, discovered_job_ids, rescore_stale)

    # --- Embedding pre-filter (Epic 4 / G-272) ---
    # Compute cosine similarity between profile and each job embedding.
    # In shadow mode (default): log similarities but score all jobs.
    # When enabled: skip jobs below threshold to save LLM costs.
    from career_os.services.embeddings import compute_job_similarities

    provider = get_ai_provider()
    prefilter_enabled = settings.embedding_prefilter_enabled
    threshold = settings.embedding_prefilter_threshold

    try:
        similarities = await compute_job_similarities(db, profile_id, jobs, provider)
    except Exception:
        logger.warning(
            "Embedding pre-filter failed — skipping, all %d jobs will be fully scored",
            len(jobs),
            exc_info=True,
        )
        similarities = {}

    if similarities:
        below = sum(1 for s in similarities.values() if s < threshold)
        above = len(similarities) - below
        no_embed = len(jobs) - len(similarities)

        if prefilter_enabled:
            # Actually filter: keep jobs above threshold + jobs without embeddings
            jobs = [j for j in jobs if similarities.get(j.id, threshold) >= threshold]
            logger.info(
                "Pre-filtered %d of %d jobs (threshold %.2f), sending %d to full scoring "
                "(%d without embeddings passed through)",
                below,
                below + above + no_embed,
                threshold,
                len(jobs),
                no_embed,
            )
        else:
            # Shadow mode: log but don't filter
            logger.info(
                "Shadow pre-filter: %d/%d jobs below threshold %.2f "
                "(would be filtered if enabled), %d without embeddings",
                below,
                below + above + no_embed,
                threshold,
                no_embed,
            )

    scores: list[ScoredJob] = []
    errors: list[dict[str, str]] = []
    credits_exhausted = False

    for job in jobs:
        try:
            description = job.description or f"{job.title} at {job.company} in {job.location}"
            scored = await score_job(
                db,
                profile_id,
                description,
                job_title=job.title,
                job_company=job.company,
                job_url=job.url,
                discovered_job_id=job.id,
                application_id=job.application_id,
            )
            scores.append(scored)
        except (CreditsExhaustedError, ProviderQuotaError):
            logger.warning(
                "AI credits exhausted after scoring %d/%d jobs — stopping batch",
                len(scores),
                len(jobs),
            )
            credits_exhausted = True
            break
        except Exception as exc:
            logger.warning("Failed to score job %d: %s", job.id, exc)
            errors.append(
                {
                    "discovered_job_id": str(job.id),
                    "error": str(exc),
                }
            )

    total_time = time.monotonic() - start_time

    result = {
        "scored_count": len(scores),
        "total_time_seconds": round(total_time, 2),
        "scores": scores,
        "errors": errors,
        "credits_exhausted": credits_exhausted,
    }

    # Relative/percentile batch scoring (G-1338, finding N): opt-in, off by
    # default. When enabled, attach a within-batch percentile/tier view derived
    # from the raw scores (raw fit_scores are never mutated). Strict identity when
    # off — no "relative" key is added, so default behavior is byte-for-byte
    # unchanged.
    if settings.relative_batch_scoring_enabled and scores:
        from career_os.services.relative_scoring import build_relative_view

        result["relative"] = build_relative_view(scores)

    return result


# ---------------------------------------------------------------------------
# Profile Switch — Flag Stale Scores
# ---------------------------------------------------------------------------


def flag_stale_scores(db: Session, profile_id: int) -> int:
    """Mark all scores for a profile as stale.

    Called when scoring weights change or profile is switched/updated.
    Also nulls out cached fit_score on DiscoveredJob and Application rows
    so stale scores don't render in the frontend.
    Returns the number of scores flagged as stale.
    """
    # Get IDs of affected discovered jobs and applications before marking stale
    stale_scores = (
        db.query(ScoredJob)
        .filter(
            ScoredJob.profile_id == profile_id,
            ScoredJob.is_stale.is_(False),
        )
        .all()
    )

    discovered_job_ids = {
        s.discovered_job_id for s in stale_scores if s.discovered_job_id is not None
    }
    application_ids = {s.application_id for s in stale_scores if s.application_id is not None}

    count = (
        db.query(ScoredJob)
        .filter(
            ScoredJob.profile_id == profile_id,
            ScoredJob.is_stale.is_(False),
        )
        .update({"is_stale": True})
    )

    # Null out cached fit_score on DiscoveredJob rows
    if discovered_job_ids:
        db.query(DiscoveredJob).filter(
            DiscoveredJob.id.in_(discovered_job_ids),
            DiscoveredJob.profile_id == profile_id,
        ).update({"fit_score": None}, synchronize_session="fetch")

    # Null out cached fit_score on Application rows
    if application_ids:
        db.query(Application).filter(
            Application.id.in_(application_ids),
            Application.profile_id == profile_id,
        ).update({"fit_score": None}, synchronize_session="fetch")

    db.commit()
    return count


# ---------------------------------------------------------------------------
# Score Context (Percentile / Rank)
# ---------------------------------------------------------------------------

_SCORE_CONTEXT_MIN_SCORES = 5  # minimum non-stale scores required for meaningful context


def compute_score_context(db: Session, profile_id: int, fit_score: float) -> dict | None:
    """Return percentile context for a score relative to the user's scoring history.

    Only computed when the profile has >= 5 non-stale scored jobs.  Returns
    ``None`` when there is insufficient data.

    The returned dict matches the ``ScoreContextResponse`` Pydantic schema:
        {
            "percentile": 82,       # score is higher than 82% of scored jobs
            "rank": 3,              # 3rd highest score
            "total_scored": 47,     # total non-stale scored jobs
            "avg_score": 5.3,       # average fit_score
            "score_band_count": 8,  # jobs in the same letter grade band
        }
    """
    from career_os.schemas.scoring import score_to_letter_grade

    # Count total non-stale scored jobs for this profile
    total_scored: int = (
        db.query(ScoredJob)
        .filter(
            ScoredJob.profile_id == profile_id,
            ScoredJob.is_stale.is_(False),
        )
        .count()
    )

    if total_scored < _SCORE_CONTEXT_MIN_SCORES:
        return None

    # Count how many scores are strictly below this score (for percentile)
    below_count: int = (
        db.query(ScoredJob)
        .filter(
            ScoredJob.profile_id == profile_id,
            ScoredJob.is_stale.is_(False),
            ScoredJob.fit_score < fit_score,
        )
        .count()
    )

    percentile = int(below_count / total_scored * 100)

    # Rank: count scores strictly above this score + 1
    above_count: int = (
        db.query(ScoredJob)
        .filter(
            ScoredJob.profile_id == profile_id,
            ScoredJob.is_stale.is_(False),
            ScoredJob.fit_score > fit_score,
        )
        .count()
    )
    rank = above_count + 1

    # Average score across all non-stale jobs
    from sqlalchemy import func as sa_func

    avg_result = (
        db.query(sa_func.avg(ScoredJob.fit_score))
        .filter(
            ScoredJob.profile_id == profile_id,
            ScoredJob.is_stale.is_(False),
        )
        .scalar()
    )
    avg_score = round(float(avg_result), 2) if avg_result is not None else 0.0

    # Jobs in the same letter grade band as fit_score
    target_grade = score_to_letter_grade(fit_score)
    all_scores = (
        db.query(ScoredJob.fit_score)
        .filter(
            ScoredJob.profile_id == profile_id,
            ScoredJob.is_stale.is_(False),
        )
        .all()
    )
    score_band_count = sum(1 for (s,) in all_scores if score_to_letter_grade(s) == target_grade)

    return {
        "percentile": percentile,
        "rank": rank,
        "total_scored": total_scored,
        "avg_score": avg_score,
        "score_band_count": score_band_count,
    }


# ---------------------------------------------------------------------------
# Profile Completeness (Epic 10 / G-278)
# ---------------------------------------------------------------------------

# Weights for each completeness component (sum = 100)
_COMPLETENESS_WEIGHTS: dict[str, int] = {
    "job_family": 15,
    "location": 15,
    "skills": 20,
    "goals": 15,
    "market_positioning": 10,
    "experiences": 15,
    "dream_companies": 10,
}

_MIN_SKILLS = 5
_MIN_GOALS = 1
_MIN_EXPERIENCES = 3  # proxy: Applications with status != 'discovered'
_HIGH_UNCERTAINTY_THRESHOLD = 50  # below this, show the improvement hint


def compute_profile_completeness(db: Session, profile_id: int) -> dict:
    """Compute profile richness and return a completeness dict.

    Returns a dict with:
        - ``completeness``: 0-100 float representing profile richness
        - ``confidence_range``: (low_bound, high_bound) tuple clamped to [0, 10]
        - ``missing_fields``: list of field suggestions (only when completeness < 50)

    Completeness components and their weights:
        job_family (+15%), location (+15%), >=5 skills (+20%),
        >=1 goal (+15%), market_positioning (+10%), >=3 experiences (+15%),
        dream_companies (+10%).

    Confidence interval formula:
        half_width = 3.0 * (1 - completeness / 100) + 0.3
    so at 100% -> ±0.3, at 50% -> ±1.8 (effective), at 25% -> ±3.075.

    Since there is no Experiences model yet, that component is always 0.
    """
    import json as _json

    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if profile is None:
        return {
            "completeness": 0.0,
            "confidence_range": (0.0, 10.0),
            "missing_fields": list(_COMPLETENESS_WEIGHTS.keys()),
        }

    skills = db.query(Skill).filter(Skill.profile_id == profile_id).all()
    goals = db.query(Goal).filter(Goal.profile_id == profile_id).all()

    # Evaluate each component
    has_job_family = bool(profile.job_family)
    has_location = bool(profile.location)
    has_enough_skills = len(skills) >= _MIN_SKILLS
    has_goals = len(goals) >= _MIN_GOALS
    has_market_data = profile.last_market_refreshed_at is not None
    # No Experiences model yet — proxy via applied/interviewing/offer/accepted applications
    # We conservatively treat this as 0 until the model exists.
    has_experiences = False  # always False until Experiences model is introduced

    # dream_companies is a JSON array stored as text
    has_dream_companies = False
    if profile.dream_companies:
        try:
            dc = _json.loads(profile.dream_companies)
            has_dream_companies = isinstance(dc, list) and len(dc) > 0
        except (ValueError, TypeError):
            has_dream_companies = bool(profile.dream_companies.strip())

    component_flags = {
        "job_family": has_job_family,
        "location": has_location,
        "skills": has_enough_skills,
        "goals": has_goals,
        "market_positioning": has_market_data,
        "experiences": has_experiences,
        "dream_companies": has_dream_companies,
    }

    completeness = float(
        sum(
            _COMPLETENESS_WEIGHTS[component]
            for component, present in component_flags.items()
            if present
        )
    )

    # half_width = 3.0 * (1 - completeness/100) + 0.3
    half_width = 3.0 * (1.0 - completeness / 100.0) + 0.3

    # We need a fit_score to center the range, but completeness is profile-level
    # (not score-specific), so we express it as a symmetric expansion around
    # the score midpoint.  Callers apply this to the actual fit_score.
    # Return raw half_width here; the API layer applies it to each score.
    low_bound = round(max(0.0, 5.0 - half_width), 2)
    high_bound = round(min(10.0, 5.0 + half_width), 2)

    missing_fields: list[str] = []
    if completeness < _HIGH_UNCERTAINTY_THRESHOLD:
        field_labels: dict[str, str] = {
            "job_family": "target job family",
            "location": "location preference",
            "skills": f"at least {_MIN_SKILLS} skills",
            "goals": "at least one career goal",
            "market_positioning": "market positioning data (refresh market)",
            "experiences": "past work experiences",
            "dream_companies": "dream companies list",
        }
        missing_fields = [
            field_labels[component] for component, present in component_flags.items() if not present
        ]

    return {
        "completeness": completeness,
        "confidence_range": (low_bound, high_bound),
        "missing_fields": missing_fields,
        "half_width": half_width,
    }


def apply_confidence_range(fit_score: float, half_width: float) -> tuple[float, float]:
    """Apply a half-width to a specific fit_score, clamped to [0, 10].

    Returns (low_bound, high_bound).
    """
    return (
        round(max(0.0, fit_score - half_width), 2),
        round(min(10.0, fit_score + half_width), 2),
    )


# ---------------------------------------------------------------------------
# Score Retrieval
# ---------------------------------------------------------------------------


def get_score_for_job(db: Session, profile_id: int, discovered_job_id: int) -> ScoredJob | None:
    """Get the latest non-stale score for a discovered job."""
    return (
        db.query(ScoredJob)
        .filter(
            ScoredJob.profile_id == profile_id,
            ScoredJob.discovered_job_id == discovered_job_id,
            ScoredJob.is_stale.is_(False),
        )
        .order_by(ScoredJob.created_at.desc())
        .first()
    )


def get_score_for_application(
    db: Session, profile_id: int, application_id: int
) -> ScoredJob | None:
    """Get the latest non-stale score for an application."""
    return (
        db.query(ScoredJob)
        .filter(
            ScoredJob.profile_id == profile_id,
            ScoredJob.application_id == application_id,
            ScoredJob.is_stale.is_(False),
        )
        .order_by(ScoredJob.created_at.desc())
        .first()
    )


# ---------------------------------------------------------------------------
# Feedback CRUD
# ---------------------------------------------------------------------------

#: Directions considered explicit user corrections
EXPLICIT_DIRECTIONS = {"too_high", "too_low", "correct"}

#: Directions considered implicit signals
IMPLICIT_DIRECTIONS = {"implicit_positive", "implicit_negative", "implicit_strong_positive"}

#: All valid feedback directions
VALID_DIRECTIONS = EXPLICIT_DIRECTIONS | IMPLICIT_DIRECTIONS


class FeedbackNotFoundError(Exception):
    """Raised when a scored_job is not found when submitting feedback."""


class InvalidFeedbackError(Exception):
    """Raised when feedback data is invalid."""


def submit_feedback(
    db: Session,
    *,
    scored_job_id: int,
    profile_id: int,
    direction: str,
    user_score: float | None = None,
    reason: str | None = None,
) -> ScoringFeedback:
    """Submit feedback on an AI-generated score.

    Validates that the scored_job exists and belongs to the profile, then
    creates a ScoringFeedback record snapshotting the original fit_score.

    Raises FeedbackNotFoundError if the scored_job does not exist.
    Raises InvalidFeedbackError if direction or user_score are invalid.
    """
    if direction not in VALID_DIRECTIONS:
        raise InvalidFeedbackError(
            f"Invalid direction '{direction}'. Must be one of: {sorted(VALID_DIRECTIONS)}"
        )
    if user_score is not None and not (0.0 <= user_score <= 10.0):
        raise InvalidFeedbackError("user_score must be between 0 and 10")

    scored_job = (
        db.query(ScoredJob)
        .filter(ScoredJob.id == scored_job_id, ScoredJob.profile_id == profile_id)
        .first()
    )
    if scored_job is None:
        raise FeedbackNotFoundError(f"ScoredJob {scored_job_id} not found for profile {profile_id}")

    feedback = ScoringFeedback(
        scored_job_id=scored_job_id,
        profile_id=profile_id,
        direction=direction,
        user_score=user_score,
        reason=reason,
        original_fit_score=scored_job.fit_score,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    # Distillation-label logging (G-1338, finding M): backfill the correction onto
    # the training tuple(s) for this scored job. No-op unless the flag is on;
    # never raises.
    from career_os.services.distillation import record_distillation_feedback

    record_distillation_feedback(
        db, scored_job_id=scored_job_id, direction=direction, user_score=user_score
    )

    return feedback


def record_implicit_feedback(
    db: Session,
    *,
    profile_id: int,
    direction: str,
    scored_job_id: int | None = None,
    discovered_job_id: int | None = None,
    application_id: int | None = None,
) -> ScoringFeedback | None:
    """Record an implicit feedback signal.

    Looks up the most recent ScoredJob linked to the given discovered_job_id
    or application_id, then creates a ScoringFeedback record. Returns None
    if no ScoredJob can be found (gracefully skipped).

    Called from service hooks — never fails loudly.
    """
    if direction not in IMPLICIT_DIRECTIONS:
        logger.warning("record_implicit_feedback: invalid direction '%s', skipping", direction)
        return None

    # Resolve scored_job_id from the linked entity if not supplied directly
    if scored_job_id is None:
        query = db.query(ScoredJob).filter(ScoredJob.profile_id == profile_id)
        if discovered_job_id is not None:
            query = query.filter(ScoredJob.discovered_job_id == discovered_job_id)
        elif application_id is not None:
            query = query.filter(ScoredJob.application_id == application_id)
        else:
            return None
        scored_job = query.order_by(ScoredJob.created_at.desc()).first()
        if scored_job is None:
            return None
        scored_job_id = scored_job.id
    else:
        scored_job = db.query(ScoredJob).filter(ScoredJob.id == scored_job_id).first()
        if scored_job is None:
            return None

    try:
        feedback = ScoringFeedback(
            scored_job_id=scored_job_id,
            profile_id=profile_id,
            direction=direction,
            user_score=None,
            reason=None,
            original_fit_score=scored_job.fit_score,
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)

        # Distillation-label logging (G-1338, finding M): backfill the implicit
        # correction onto the training tuple(s). No-op unless the flag is on.
        from career_os.services.distillation import record_distillation_feedback

        record_distillation_feedback(db, scored_job_id=scored_job_id, direction=direction)

        return feedback
    except Exception:
        logger.warning(
            "record_implicit_feedback: failed to record signal '%s' for scored_job %d",
            direction,
            scored_job_id,
            exc_info=True,
        )
        db.rollback()
        return None


def list_feedback(db: Session, profile_id: int) -> list[ScoringFeedback]:
    """List all feedback records for a profile, newest first."""
    return (
        db.query(ScoringFeedback)
        .filter(ScoringFeedback.profile_id == profile_id)
        .order_by(ScoringFeedback.created_at.desc())
        .all()
    )


def get_feedback_stats(db: Session, profile_id: int) -> dict:
    """Return summary statistics for feedback submitted by a profile.

    Returns:
        total_count, explicit_count, implicit_count,
        avg_deviation (or None), direction_counts.
    """
    records = list_feedback(db, profile_id)

    direction_counts: dict[str, int] = {}
    explicit_count = 0
    implicit_count = 0
    deviations: list[float] = []

    for r in records:
        direction_counts[r.direction] = direction_counts.get(r.direction, 0) + 1
        if r.direction in EXPLICIT_DIRECTIONS:
            explicit_count += 1
        else:
            implicit_count += 1
        if r.user_score is not None:
            deviations.append(abs(r.user_score - r.original_fit_score))

    avg_deviation = sum(deviations) / len(deviations) if deviations else None

    return {
        "total_count": len(records),
        "explicit_count": explicit_count,
        "implicit_count": implicit_count,
        "avg_deviation": avg_deviation,
        "direction_counts": direction_counts,
    }


# ---------------------------------------------------------------------------
# Calibration Summary (foundation for Epic 11 / Bayesian Learning)
# ---------------------------------------------------------------------------

#: Minimum number of explicit feedback records required before calibration is
#: returned. Below this threshold the data is too sparse to be meaningful.
CALIBRATION_MIN_FEEDBACK = 10

#: Maximum number of calibration examples injected into the scoring prompt.
CALIBRATION_MAX_EXAMPLES = 5


def get_feedback_calibration(db: Session, profile_id: int) -> list[dict]:
    """Return the most informative calibration examples for the scoring prompt.

    "Most informative" = largest absolute deviation between the user's score
    and the AI's original score. Only explicit corrections (too_high / too_low)
    with a user_score are considered.

    Returns an empty list when fewer than CALIBRATION_MIN_FEEDBACK explicit
    feedback records exist (data too sparse to calibrate).

    Each returned dict has keys:
        job_title, company, ai_score, user_score, reason, deviation
    """
    explicit_records = (
        db.query(ScoringFeedback)
        .filter(
            ScoringFeedback.profile_id == profile_id,
            ScoringFeedback.direction.in_(["too_high", "too_low"]),
            ScoringFeedback.user_score.isnot(None),
        )
        .all()
    )

    if len(explicit_records) < CALIBRATION_MIN_FEEDBACK:
        return []

    # Enrich with job metadata from the linked ScoredJob → DiscoveredJob/Application
    enriched: list[dict] = []
    for record in explicit_records:
        scored_job = db.query(ScoredJob).filter(ScoredJob.id == record.scored_job_id).first()
        job_title: str | None = None
        company: str | None = None
        if scored_job is not None:
            if scored_job.discovered_job_id is not None:
                dj = (
                    db.query(DiscoveredJob)
                    .filter(DiscoveredJob.id == scored_job.discovered_job_id)
                    .first()
                )
                if dj:
                    job_title = dj.title
                    company = dj.company
            elif scored_job.application_id is not None:
                app_rec = (
                    db.query(Application)
                    .filter(Application.id == scored_job.application_id)
                    .first()
                )
                if app_rec:
                    job_title = app_rec.role
                    company = app_rec.company

        deviation = abs(record.user_score - record.original_fit_score)  # type: ignore[operator]
        enriched.append(
            {
                "job_title": job_title,
                "company": company,
                "ai_score": record.original_fit_score,
                "user_score": record.user_score,
                "reason": record.reason,
                "deviation": deviation,
            }
        )

    # Sort by deviation descending, take top N
    enriched.sort(key=lambda x: x["deviation"], reverse=True)
    return enriched[:CALIBRATION_MAX_EXAMPLES]
