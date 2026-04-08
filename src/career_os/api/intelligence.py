"""Role & Industry Intelligence API routes.

Covers:
- VAL-ROLE-INTEL-001: Interview format per company
- VAL-ROLE-INTEL-002: Salary benchmarks per role+location+size
- VAL-ROLE-INTEL-003: Common interview patterns per role type
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from career_os.database import get_db
from career_os.schemas.role_intelligence import (
    InterviewFormatResponse,
    InterviewPatternsResponse,
    SalaryBenchmarkResponse,
)
from career_os.services.role_intelligence import (
    ProfileNotFoundError,
    get_interview_format,
    get_interview_patterns,
    get_salary_benchmarks,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/intelligence", tags=["role-intelligence"])


# ---------------------------------------------------------------------------
# VAL-ROLE-INTEL-001: Interview format per company
# ---------------------------------------------------------------------------


@router.get("/interview-format", response_model=InterviewFormatResponse)
async def interview_format_endpoint(
    company: str = Query(..., min_length=1, description="Company name"),
    profile_id: int = Query(..., description="Profile ID"),
    role: str | None = Query(
        default=None, description="Optional role context for more specific results"
    ),
    db: Session = Depends(get_db),
) -> InterviewFormatResponse:
    """Get typical interview format for a company.

    Returns rounds with types, durations, and total process duration.
    Optionally accepts a role for more context-specific results.
    """
    try:
        return await get_interview_format(
            db=db,
            company=company,
            profile_id=profile_id,
            role=role,
        )
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error during interview format retrieval")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# VAL-ROLE-INTEL-002: Salary benchmarks per role+location+size
# ---------------------------------------------------------------------------


@router.get("/salary", response_model=SalaryBenchmarkResponse)
async def salary_benchmark_endpoint(
    role: str = Query(..., min_length=1, description="Role type to benchmark"),
    profile_id: int = Query(..., description="Profile ID"),
    location: str | None = Query(
        default=None, description="Optional location filter"
    ),
    company_stage: str | None = Query(
        default=None,
        description="Optional company stage filter (e.g., 'startup', 'growth', 'public')",
    ),
    db: Session = Depends(get_db),
) -> SalaryBenchmarkResponse:
    """Get salary benchmarks for a role type, optionally filtered by location and stage.

    Returns low (p25), median, and high (p75) compensation ranges
    based on discovered job data, contextualized by location and company stage.
    """
    try:
        return get_salary_benchmarks(
            db=db,
            role=role,
            profile_id=profile_id,
            location=location,
            company_stage=company_stage,
        )
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error during salary benchmark retrieval")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# VAL-ROLE-INTEL-003: Common interview patterns per role type
# ---------------------------------------------------------------------------


@router.get("/patterns", response_model=InterviewPatternsResponse)
async def interview_patterns_endpoint(
    role: str = Query(..., min_length=1, description="Role type"),
    profile_id: int = Query(..., description="Profile ID"),
    db: Session = Depends(get_db),
) -> InterviewPatternsResponse:
    """Get common interview patterns for a role type.

    Returns question categories, assessment criteria, and frequently
    tested skills specific to the given role type.
    """
    try:
        return await get_interview_patterns(
            db=db,
            role=role,
            profile_id=profile_id,
        )
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error during interview patterns retrieval")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {exc}",
        ) from exc
