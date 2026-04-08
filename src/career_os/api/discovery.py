"""Discovery API routes — job discovery, search profiles, and discovery runs."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

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
    get_search_profile,
    list_discovery_runs,
    list_search_profiles,
    run_discovery,
    update_search_profile,
)

router = APIRouter(tags=["discovery"])


# ---------------------------------------------------------------------------
# Discovery sweep
# ---------------------------------------------------------------------------


@router.post("/api/discover", response_model=DiscoverResponse)
async def discover(
    payload: DiscoverRequest,
    db: Session = Depends(get_db),
) -> DiscoverResponse:
    """Trigger a discovery sweep across configured sources.

    Returns jobs from ≥2 sources with deduplication. Individual source
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
    response_model=SearchProfileResponse,
    status_code=201,
)
async def create_search_profile_endpoint(
    payload: SearchProfileCreate,
    db: Session = Depends(get_db),
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
    response_model=SearchProfileListResponse,
)
async def list_search_profiles_endpoint(
    profile_id: int = Query(..., description="Profile ID"),
    active_only: bool = Query(False, description="Only active profiles"),
    db: Session = Depends(get_db),
) -> SearchProfileListResponse:
    """List saved search profiles for a profile."""
    profiles = list_search_profiles(db, profile_id, active_only=active_only)
    return SearchProfileListResponse(
        profiles=[SearchProfileResponse.model_validate(p) for p in profiles],
        total=len(profiles),
    )


@router.get(
    "/api/search-profiles/{sp_id}",
    response_model=SearchProfileResponse,
)
async def get_search_profile_endpoint(
    sp_id: int,
    profile_id: int = Query(..., description="Profile ID"),
    db: Session = Depends(get_db),
) -> SearchProfileResponse:
    """Get a single search profile."""
    try:
        sp = get_search_profile(db, sp_id, profile_id=profile_id)
    except SearchProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SearchProfileResponse.model_validate(sp)


@router.put(
    "/api/search-profiles/{sp_id}",
    response_model=SearchProfileResponse,
)
async def update_search_profile_endpoint(
    sp_id: int,
    payload: SearchProfileUpdate,
    profile_id: int = Query(..., description="Profile ID"),
    db: Session = Depends(get_db),
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
)
async def delete_search_profile_endpoint(
    sp_id: int,
    profile_id: int = Query(..., description="Profile ID"),
    db: Session = Depends(get_db),
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
    response_model=list[DiscoveryRunResponse],
)
async def list_discovery_runs_endpoint(
    profile_id: int = Query(..., description="Profile ID"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    db: Session = Depends(get_db),
) -> list[DiscoveryRunResponse]:
    """List discovery run history for a profile."""
    runs = list_discovery_runs(db, profile_id, limit=limit)
    return [DiscoveryRunResponse.model_validate(r) for r in runs]
