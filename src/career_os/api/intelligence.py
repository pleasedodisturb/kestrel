"""Role & Industry Intelligence API routes.

Covers:
- VAL-ROLE-INTEL-001: Interview format per company
- VAL-ROLE-INTEL-002: Salary benchmarks per role+location+size
- VAL-ROLE-INTEL-003: Common interview patterns per role type
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from career_os.api.constants import DESC_PROFILE_ID, RESP_404_500
from career_os.database import get_db
from career_os.schemas.constraints import INT32_MAX
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


@router.get(
    "/interview-format",
    responses=RESP_404_500,
)
async def interview_format_endpoint(
    company: Annotated[str, Query(min_length=1, description="Company name")],
    profile_id: Annotated[int, Query(ge=1, le=INT32_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
    role: Annotated[
        str | None, Query(description="Optional role context for more specific results")
    ] = None,
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


@router.get(
    "/salary",
    responses=RESP_404_500,
)
async def salary_benchmark_endpoint(
    role: Annotated[str, Query(min_length=1, description="Role type to benchmark")],
    profile_id: Annotated[int, Query(ge=1, le=INT32_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
    location: Annotated[str | None, Query(description="Optional location filter")] = None,
    company_stage: Annotated[
        str | None,
        Query(description="Optional company stage filter (e.g., 'startup', 'growth', 'public')"),
    ] = None,
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


@router.get(
    "/patterns",
    responses=RESP_404_500,
)
async def interview_patterns_endpoint(
    role: Annotated[str, Query(min_length=1, description="Role type")],
    profile_id: Annotated[int, Query(ge=1, le=INT32_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
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
