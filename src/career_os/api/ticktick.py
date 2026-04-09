"""TickTick bidirectional sync API routes."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from career_os.database import get_db
from career_os.models.models import Application, FollowUp
from career_os.models.skills import Goal
from career_os.schemas.ticktick import (
    TickTickConnectionTestResponse,
    TickTickPullResponse,
    TickTickPushRequest,
    TickTickPushResponse,
    TickTickSyncStatusResponse,
    TickTickSyncTaskResponse,
)
from career_os.services.ticktick_sync import (
    TickTickNotConfiguredError,
    TickTickSyncError,
    check_ticktick_connection,
    get_sync_status,
    sync_completions_from_ticktick,
    sync_follow_up_to_ticktick,
    sync_learning_goal_to_ticktick,
    sync_pipeline_action_to_ticktick,
)

router = APIRouter(prefix="/api/ticktick", tags=["ticktick"])


@router.get("/status")
async def ticktick_sync_status(
    profile_id: int = Query(..., description="Profile ID"),
    db: Session = Depends(get_db),
) -> TickTickSyncStatusResponse:
    """Get the current TickTick sync status for a profile."""
    status = get_sync_status(db, profile_id=profile_id)
    return TickTickSyncStatusResponse(
        total_tasks=status["total_tasks"],
        synced=status["synced"],
        completed=status["completed"],
        errors=status["errors"],
        last_sync_at=status["last_sync_at"],
        tasks=[
            TickTickSyncTaskResponse(
                id=t["id"],
                entity_type=t["entity_type"],
                entity_id=t["entity_id"],
                ticktick_task_id=t["ticktick_task_id"],
                title=t["title"],
                status=t["status"],
                last_synced_at=t["last_synced_at"],
                error_message=t["error_message"],
            )
            for t in status["tasks"]
        ],
    )


@router.post("/push")
async def ticktick_push(
    payload: TickTickPushRequest,
    db: Session = Depends(get_db),
) -> TickTickPushResponse:
    """Push a Career OS entity to TickTick.

    Supports: follow_up, learning_goal, pipeline_action.
    """
    try:
        if payload.entity_type == "follow_up":
            follow_up = (
                db.query(FollowUp)
                .filter(
                    FollowUp.id == payload.entity_id,
                    FollowUp.profile_id == payload.profile_id,
                )
                .first()
            )
            if not follow_up:
                raise HTTPException(status_code=404, detail="Follow-up not found")
            sync_task = sync_follow_up_to_ticktick(db, follow_up)

        elif payload.entity_type == "learning_goal":
            goal = (
                db.query(Goal)
                .filter(
                    Goal.id == payload.entity_id,
                    Goal.profile_id == payload.profile_id,
                )
                .first()
            )
            if not goal:
                raise HTTPException(status_code=404, detail="Learning goal not found")
            sync_task = sync_learning_goal_to_ticktick(db, goal)

        elif payload.entity_type == "pipeline_action":
            application = (
                db.query(Application)
                .filter(
                    Application.id == payload.entity_id,
                    Application.profile_id == payload.profile_id,
                )
                .first()
            )
            if not application:
                raise HTTPException(status_code=404, detail="Application not found")
            sync_task = sync_pipeline_action_to_ticktick(
                db, application, f"Action for {application.company}"
            )
        else:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid entity_type: {payload.entity_type}. "
                "Must be follow_up, learning_goal, or pipeline_action",
            )

        return TickTickPushResponse(
            success=True,
            message=f"Synced {payload.entity_type} {payload.entity_id} to TickTick",
            sync_task=TickTickSyncTaskResponse(
                id=sync_task.id,
                entity_type=sync_task.entity_type,
                entity_id=sync_task.entity_id,
                ticktick_task_id=sync_task.ticktick_task_id,
                title=sync_task.title,
                status=sync_task.status,
                last_synced_at=sync_task.last_synced_at,
                error_message=sync_task.error_message,
            ),
        )
    except TickTickNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TickTickSyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/pull")
async def ticktick_pull(
    profile_id: int = Query(..., description="Profile ID"),
    db: Session = Depends(get_db),
) -> TickTickPullResponse:
    """Pull completed tasks from TickTick and update Career OS entities."""
    try:
        stats = sync_completions_from_ticktick(db, profile_id=profile_id)
        return TickTickPullResponse(
            success=True,
            message=f"Sync completed: {stats['synced']} updated, "
            f"{stats['errors']} errors, {stats['skipped']} skipped",
            synced=stats["synced"],
            errors=stats["errors"],
            skipped=stats["skipped"],
        )
    except TickTickNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/test")
async def ticktick_test_connection(
    db: Session = Depends(get_db),
) -> TickTickConnectionTestResponse:
    """Test the TickTick API connection."""
    success, message = check_ticktick_connection(db)
    return TickTickConnectionTestResponse(
        success=success,
        message=message,
        tested_at=datetime.now(UTC),
    )
