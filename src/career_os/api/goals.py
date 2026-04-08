"""Career Goals API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from career_os.database import get_db
from career_os.schemas.goals import (
    AlternativePath,
    AlternativesResponse,
    GoalCreate,
    GoalListResponse,
    GoalResponse,
    GoalUpdate,
    ProgressDimension,
    ProgressResponse,
    RealityMapDimension,
    RealityMapResponse,
    RecalibrationResponse,
)
from career_os.services.goals import (
    GoalNotFoundError,
    ProfileNotFoundError,
    create_goal,
    delete_goal,
    get_alternatives,
    get_goal,
    get_progress,
    get_reality_map,
    list_goals,
    recalibrate_goal,
    update_goal,
)

router = APIRouter(prefix="/api/goals", tags=["goals"])


@router.get("", response_model=GoalListResponse)
async def list_goals_endpoint(
    profile_id: int = Query(..., description="Profile to list goals for"),
    status: str | None = Query(default=None, description="Filter by status"),
    goal_type: str | None = Query(default=None, description="Filter by type"),
    db: Session = Depends(get_db),
) -> GoalListResponse:
    """List career goals with optional filters."""
    goals, total = list_goals(db, profile_id, status=status, goal_type=goal_type)
    return GoalListResponse(
        goals=[GoalResponse.model_validate(g) for g in goals],
        total=total,
    )


@router.get("/{goal_id}", response_model=GoalResponse)
async def get_goal_endpoint(
    goal_id: int,
    profile_id: int = Query(..., description="Active profile ID"),
    db: Session = Depends(get_db),
) -> GoalResponse:
    """Get a single goal by ID."""
    try:
        goal = get_goal(db, goal_id, profile_id)
    except GoalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return GoalResponse.model_validate(goal)


@router.post("", response_model=GoalResponse, status_code=201)
async def create_goal_endpoint(
    payload: GoalCreate,
    db: Session = Depends(get_db),
) -> GoalResponse:
    """Create a new career goal."""
    try:
        goal = create_goal(
            db,
            payload.profile_id,
            {
                "title": payload.title,
                "goal_type": payload.goal_type.value,
                "target_date": payload.target_date,
                "status": payload.status.value,
                "description": payload.description,
            },
        )
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return GoalResponse.model_validate(goal)


@router.put("/{goal_id}", response_model=GoalResponse)
async def update_goal_endpoint(
    goal_id: int,
    payload: GoalUpdate,
    profile_id: int = Query(..., description="Active profile ID"),
    db: Session = Depends(get_db),
) -> GoalResponse:
    """Update a goal's fields."""
    update_data = payload.model_dump(exclude_unset=True)
    # Convert enum values to strings
    if "goal_type" in update_data and update_data["goal_type"] is not None:
        update_data["goal_type"] = str(update_data["goal_type"])
    if "status" in update_data and update_data["status"] is not None:
        update_data["status"] = str(update_data["status"])
    try:
        goal = update_goal(db, goal_id, profile_id, update_data)
    except GoalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return GoalResponse.model_validate(goal)


@router.delete("/{goal_id}", status_code=204)
async def delete_goal_endpoint(
    goal_id: int,
    profile_id: int = Query(..., description="Active profile ID"),
    db: Session = Depends(get_db),
) -> None:
    """Delete a goal."""
    try:
        delete_goal(db, goal_id, profile_id)
    except GoalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{goal_id}/reality-map", response_model=RealityMapResponse)
async def get_reality_map_endpoint(
    goal_id: int,
    profile_id: int = Query(..., description="Active profile ID"),
    db: Session = Depends(get_db),
) -> RealityMapResponse:
    """Get goal-to-reality mapping.

    Shows current state, required state, and delta across
    skills, applications, and portfolio dimensions.
    """
    try:
        result = get_reality_map(db, goal_id, profile_id)
    except GoalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return RealityMapResponse(
        goal_id=result["goal_id"],
        title=result["title"],
        goal_type=result["goal_type"],
        dimensions=[RealityMapDimension(**d) for d in result["dimensions"]],
        overall_progress=result["overall_progress"],
    )


@router.get("/{goal_id}/progress", response_model=ProgressResponse)
async def get_progress_endpoint(
    goal_id: int,
    profile_id: int = Query(..., description="Active profile ID"),
    db: Session = Depends(get_db),
) -> ProgressResponse:
    """Get progress tracking across applications, learning, portfolio."""
    try:
        result = get_progress(db, goal_id, profile_id)
    except GoalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ProgressResponse(
        goal_id=result["goal_id"],
        title=result["title"],
        dimensions=[ProgressDimension(**d) for d in result["dimensions"]],
        overall_progress=result["overall_progress"],
    )


@router.put("/{goal_id}/recalibrate", response_model=RecalibrationResponse)
async def recalibrate_goal_endpoint(
    goal_id: int,
    profile_id: int = Query(..., description="Active profile ID"),
    db: Session = Depends(get_db),
) -> RecalibrationResponse:
    """AI-powered goal recalibration with market-data-backed suggestions."""
    try:
        result = await recalibrate_goal(db, goal_id, profile_id)
    except GoalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return RecalibrationResponse(
        goal_id=result["goal_id"],
        title=result["title"],
        recalibration_notes=result["recalibration_notes"],
        suggested_adjustments=result["suggested_adjustments"],
        market_reality=result["market_reality"],
    )


@router.get("/{goal_id}/alternatives", response_model=AlternativesResponse)
async def get_alternatives_endpoint(
    goal_id: int,
    profile_id: int = Query(..., description="Active profile ID"),
    db: Session = Depends(get_db),
) -> AlternativesResponse:
    """Get alternative path analysis (employment, freelance, consulting)."""
    try:
        result = await get_alternatives(db, goal_id, profile_id)
    except GoalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return AlternativesResponse(
        goal_id=result["goal_id"],
        title=result["title"],
        paths=[AlternativePath(**p) for p in result["paths"]],
    )
