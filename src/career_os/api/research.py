"""Company Research API routes.

Covers:
- VAL-RESEARCH-001: One-click company deep-dive
- VAL-RESEARCH-008: Partial report for obscure companies
- VAL-RESEARCH-009: Graceful degradation on source failures
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from career_os.api.constants import RESP_NOT_FOUND
from career_os.database import get_db
from career_os.schemas.research import (
    CompanyResearchReport,
    CompanyResearchRequest,
)
from career_os.services.company_research import (
    ProfileNotFoundError,
    ResearchError,
    research_company,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research", tags=["research"])


@router.post(
    "/company",
    responses={
        404: {"description": RESP_NOT_FOUND},
        500: {"description": "Internal server error"},
        502: {"description": "Bad gateway"},
    },
)
async def research_company_endpoint(
    request: CompanyResearchRequest,
    db: Annotated[Session, Depends(get_db)],
    simulate_partial: Annotated[
        bool,
        Query(
            description=(
                "When true, instructs the mock provider to return partial data "
                "with source_warnings for graceful degradation testing "
                "(VAL-RESEARCH-009)."
            ),
        ),
    ] = False,
) -> CompanyResearchReport:
    """Research a company and return a structured deep-dive report.

    Returns a report with tech stack (categorized), funding data,
    Glassdoor ratings + culture signals, values alignment score,
    ATS detection, hiring patterns, and industry classification.

    Obscure companies receive a partial report with default/empty
    sections. Source failures produce warnings rather than errors.

    When simulate_partial=true, the mock provider returns partial
    data with source_warnings to enable graceful degradation testing.
    """
    try:
        report = await research_company(
            db=db,
            company_name=request.company_name,
            profile_id=request.profile_id,
            company_url=request.company_url,
            simulate_partial=simulate_partial,
        )
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ResearchError as exc:
        raise HTTPException(status_code=502, detail=f"Research failed: {exc}") from exc
    except Exception as exc:
        logger.exception("Unexpected error during company research")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error during company research: {exc}",
        ) from exc

    return report
