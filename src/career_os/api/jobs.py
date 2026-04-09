"""Jobs Search & Filter API routes (Milestone 3)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from career_os.database import get_db
from career_os.schemas.jobs import (
    JobSearchResponse,
    JobSearchResult,
    SavedSearchCreate,
    SavedSearchListResponse,
    SavedSearchResponse,
    SavedSearchUpdate,
)
from career_os.services.jobs import (
    ProfileNotFoundError,
    SavedSearchNotFoundError,
    create_saved_search,
    delete_saved_search,
    get_saved_search,
    list_saved_searches,
    search_jobs,
    update_saved_search,
)

router = APIRouter(tags=["jobs"])


# ---------------------------------------------------------------------------
# Job Search & Filter
# ---------------------------------------------------------------------------


@router.get("/api/jobs")
async def search_jobs_endpoint(
    profile_id: int = Query(..., description="Profile ID"),
    q: str | None = Query(None, description="Full-text search query"),
    source: str | None = Query(None, description="Filter by source name"),
    remote: bool | None = Query(None, description="Filter by remote status"),
    salary_min: int | None = Query(None, description="Min salary (numeric)"),
    salary_max: int | None = Query(None, description="Max salary (numeric)"),
    score_min: float | None = Query(None, description="Min fit score"),
    score_max: float | None = Query(None, description="Max fit score"),
    date_from: str | None = Query(None, description="Date from (ISO 8601)"),
    date_to: str | None = Query(None, description="Date to (ISO 8601)"),
    company: str | None = Query(None, description="Filter by company name"),
    location: str | None = Query(None, description="Filter by location"),
    sort: str | None = Query(None, description="Sort by: score, date, salary, readiness"),
    order: str | None = Query(None, description="Sort order: asc, desc"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db),
) -> JobSearchResponse:
    """Search, filter, sort, and paginate discovered jobs.

    Supports full-text search across title/company/description/location,
    multi-facet filters with AND logic, sort by score/date/salary/readiness
    in asc/desc order, and pagination.

    Empty search (no query or filters) returns all jobs paginated.
    """
    try:
        result = search_jobs(
            db,
            profile_id,
            q=q,
            source=source,
            remote=remote,
            salary_min=salary_min,
            salary_max=salary_max,
            score_min=score_min,
            score_max=score_max,
            date_from=date_from,
            date_to=date_to,
            company=company,
            location=location,
            sort=sort,
            order=order,
            page=page,
            page_size=page_size,
        )
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Convert the job dicts to response models
    job_responses = []
    for item in result["jobs"]:
        job_obj = item["job"]
        readiness = item["readiness_score"]
        job_data = JobSearchResult.model_validate(job_obj)
        job_data.readiness_score = readiness
        job_responses.append(job_data)

    return JobSearchResponse(
        jobs=job_responses,
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"],
    )


# ---------------------------------------------------------------------------
# Saved Searches CRUD
# ---------------------------------------------------------------------------


@router.post(
    "/api/saved-searches",
    status_code=201,
)
async def create_saved_search_endpoint(
    payload: SavedSearchCreate,
    db: Session = Depends(get_db),
) -> SavedSearchResponse:
    """Create a saved search/filter combination."""
    try:
        ss = create_saved_search(
            db,
            payload.profile_id,
            {
                "name": payload.name,
                "config": payload.config.model_dump(exclude_none=True),
            },
        )
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return SavedSearchResponse.model_validate(ss)


@router.get(
    "/api/saved-searches",
)
async def list_saved_searches_endpoint(
    profile_id: int = Query(..., description="Profile ID"),
    db: Session = Depends(get_db),
) -> SavedSearchListResponse:
    """List all saved searches for a profile."""
    searches = list_saved_searches(db, profile_id)
    return SavedSearchListResponse(
        searches=[SavedSearchResponse.model_validate(s) for s in searches],
        total=len(searches),
    )


@router.get(
    "/api/saved-searches/{search_id}",
)
async def get_saved_search_endpoint(
    search_id: int,
    profile_id: int = Query(..., description="Profile ID"),
    db: Session = Depends(get_db),
) -> SavedSearchResponse:
    """Get a single saved search."""
    try:
        ss = get_saved_search(db, search_id, profile_id=profile_id)
    except SavedSearchNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SavedSearchResponse.model_validate(ss)


@router.put(
    "/api/saved-searches/{search_id}",
)
async def update_saved_search_endpoint(
    search_id: int,
    payload: SavedSearchUpdate,
    profile_id: int = Query(..., description="Profile ID"),
    db: Session = Depends(get_db),
) -> SavedSearchResponse:
    """Update a saved search."""
    update_data: dict = {}
    if payload.name is not None:
        update_data["name"] = payload.name
    if payload.config is not None:
        update_data["config"] = payload.config.model_dump(exclude_none=True)

    try:
        ss = update_saved_search(db, search_id, profile_id, update_data)
    except SavedSearchNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return SavedSearchResponse.model_validate(ss)


@router.delete(
    "/api/saved-searches/{search_id}",
    status_code=204,
)
async def delete_saved_search_endpoint(
    search_id: int,
    profile_id: int = Query(..., description="Profile ID"),
    db: Session = Depends(get_db),
) -> None:
    """Delete a saved search."""
    try:
        delete_saved_search(db, search_id, profile_id)
    except SavedSearchNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
