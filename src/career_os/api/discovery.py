"""Discovery API routes - job discovery, search profiles, and discovery runs."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from career_os.api.constants import DESC_PROFILE_ID, RESP_404
from career_os.database import get_db
from career_os.schemas.discovery import (
    DiscoveredJobResponse,
    DiscoverRequest,
    DiscoverResponse,
    DiscoveryRunResponse,
    DiscoveryWarning,
    SearchProfileCreate,
    SearchProfileListResponse,
    SearchProfileResponse,
    SearchProfileUpdate,
)
from career_os.services.discovery import (
    ProfileNotFoundError,
    SearchProfileNotFoundError,
    create_search_profile,
    delete_search_profile,
    get_latest_discovery_run,
    get_search_profile,
    list_discovery_runs,
    list_search_profiles,
    run_discovery,
    update_search_profile,
)
from career_os.schemas.constraints import INT64_MAX

router = APIRouter(tags=["discovery"])


# ---------------------------------------------------------------------------
# Discovery sweep
# ---------------------------------------------------------------------------


@router.post("/api/discover", responses=RESP_404)
async def discover(
    payload: DiscoverRequest,
    db: Annotated[Session, Depends(get_db)],
) -> DiscoverResponse:
    """Trigger a discovery sweep across configured sources.

    Returns jobs from >=2 sources with deduplication. Individual source
    failures return warnings, don't block other sources.
    """
    try:
        result = await run_discovery(
            db,
            payload.profile_id,
            keywords=payload.keywords,
            locations=payload.locations,
            remote_only=payload.remote_only,
            sources=payload.sources,
            limit_per_source=payload.limit_per_source,
            search_profile_id=payload.search_profile_id,
        )
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SearchProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return DiscoverResponse(
        run_id=result["run_id"],
        total_found=result["total_found"],
        new_jobs=result["new_jobs"],
        duplicates=result["duplicates"],
        jobs=[DiscoveredJobResponse.model_validate(j) for j in result["jobs"]],
        warnings=[DiscoveryWarning(**w) for w in result["warnings"]],
        sources_queried=result["sources_queried"],
    )


# ---------------------------------------------------------------------------
# Search Profiles CRUD
# ---------------------------------------------------------------------------


@router.post(
    "/api/search-profiles",
    status_code=201,
    responses=RESP_404,
)
async def create_search_profile_endpoint(
    payload: SearchProfileCreate,
    db: Annotated[Session, Depends(get_db)],
) -> SearchProfileResponse:
    """Create a saved search profile."""
    try:
        sp = create_search_profile(
            db,
            payload.profile_id,
            payload.model_dump(exclude={"profile_id"}),
        )
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return SearchProfileResponse.model_validate(sp)


@router.get(
    "/api/search-profiles",
)
async def list_search_profiles_endpoint(
    profile_id: Annotated[int, Query(ge=1, le=INT64_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
    active_only: Annotated[bool, Query(description="Only active profiles")] = False,
) -> SearchProfileListResponse:
    """List saved search profiles for a profile."""
    profiles = list_search_profiles(db, profile_id, active_only=active_only)
    return SearchProfileListResponse(
        profiles=[SearchProfileResponse.model_validate(p) for p in profiles],
        total=len(profiles),
    )


@router.get(
    "/api/search-profiles/{sp_id}",
    responses=RESP_404,
)
async def get_search_profile_endpoint(
    sp_id: Annotated[int, Path(ge=1, le=INT64_MAX)],
    profile_id: Annotated[int, Query(ge=1, le=INT64_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> SearchProfileResponse:
    """Get a single search profile."""
    try:
        sp = get_search_profile(db, sp_id, profile_id=profile_id)
    except SearchProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SearchProfileResponse.model_validate(sp)


@router.put(
    "/api/search-profiles/{sp_id}",
    responses=RESP_404,
)
async def update_search_profile_endpoint(
    sp_id: Annotated[int, Path(ge=1, le=INT64_MAX)],
    payload: SearchProfileUpdate,
    profile_id: Annotated[int, Query(ge=1, le=INT64_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> SearchProfileResponse:
    """Update a search profile."""
    try:
        sp = update_search_profile(
            db,
            sp_id,
            profile_id,
            payload.model_dump(exclude_none=True),
        )
    except SearchProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SearchProfileResponse.model_validate(sp)


@router.delete(
    "/api/search-profiles/{sp_id}",
    status_code=204,
    responses=RESP_404,
)
async def delete_search_profile_endpoint(
    sp_id: Annotated[int, Path(ge=1, le=INT64_MAX)],
    profile_id: Annotated[int, Query(ge=1, le=INT64_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Delete a search profile."""
    try:
        delete_search_profile(db, sp_id, profile_id)
    except SearchProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Discovery Runs
# ---------------------------------------------------------------------------


@router.get(
    "/api/discovery-runs",
)
async def list_discovery_runs_endpoint(
    profile_id: Annotated[int, Query(ge=1, le=INT64_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100, description="Max results")] = 20,
) -> list[DiscoveryRunResponse]:
    """List discovery run history for a profile."""
    runs = list_discovery_runs(db, profile_id, limit=limit)
    return [DiscoveryRunResponse.model_validate(r) for r in runs]


@router.get("/api/discovery-runs/latest")
async def get_latest_discovery_run_endpoint(
    profile_id: Annotated[int, Query(ge=1, le=INT64_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> DiscoveryRunResponse | None:
    """Get the most recent completed discovery run for a profile."""
    run = get_latest_discovery_run(db, profile_id)
    if not run:
        return None
    return DiscoveryRunResponse.model_validate(run)
