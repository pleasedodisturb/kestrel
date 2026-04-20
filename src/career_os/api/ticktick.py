"""TickTick bidirectional sync API routes."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from career_os.api.constants import DESC_PROFILE_ID, RESP_404
from career_os.database import get_db
from career_os.models.models import Application, FollowUp
from career_os.models.skills import Goal
from career_os.models.ticktick_sync import TickTickSyncTask
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
from career_os.schemas.constraints import INT64_MAX

router = APIRouter(prefix="/api/ticktick", tags=["ticktick"])


@router.get("/status")
async def ticktick_sync_status(
    profile_id: Annotated[int, Query(ge=1, le=INT64_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
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


@router.post(
    "/push",
    responses={
        **RESP_404,
        400: {"description": "Bad request"},
        422: {"description": "Validation error"},
        502: {"description": "Bad gateway"},
    },
)
async def ticktick_push(
    payload: TickTickPushRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TickTickPushResponse:
    """Push a Career OS entity to TickTick.

    Supports: follow_up, learning_goal, pipeline_action.
    """
    try:
        sync_task = _resolve_and_sync(db, payload)
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


def _resolve_and_sync(db: Session, payload: TickTickPushRequest) -> TickTickSyncTask:
    """Look up the entity and sync it to TickTick."""
    if payload.entity_type == "follow_up":
        entity = _fetch_entity(db, FollowUp, payload.entity_id, payload.profile_id, "Follow-up")
        return sync_follow_up_to_ticktick(db, entity)

    if payload.entity_type == "learning_goal":
        entity = _fetch_entity(db, Goal, payload.entity_id, payload.profile_id, "Learning goal")
        return sync_learning_goal_to_ticktick(db, entity)

    if payload.entity_type == "pipeline_action":
        entity = _fetch_entity(
            db, Application, payload.entity_id, payload.profile_id, "Application"
        )
        return sync_pipeline_action_to_ticktick(db, entity, f"Action for {entity.company}")

    raise HTTPException(
        status_code=422,
        detail=f"Invalid entity_type: {payload.entity_type}. "
        "Must be follow_up, learning_goal, or pipeline_action",
    )


def _fetch_entity(db: Session, model, entity_id: int, profile_id: int, label: str):
    """Query a model by id + profile_id, raising 404 if missing."""
    obj = db.query(model).filter(model.id == entity_id, model.profile_id == profile_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return obj


@router.post("/pull", responses={400: {"description": "Bad request"}})
async def ticktick_pull(
    profile_id: Annotated[int, Query(ge=1, le=INT64_MAX, description=DESC_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
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
    db: Annotated[Session, Depends(get_db)],
) -> TickTickConnectionTestResponse:
    """Test the TickTick API connection."""
    success, message = check_ticktick_connection(db)
    return TickTickConnectionTestResponse(
        success=success,
        message=message,
        tested_at=datetime.now(UTC),
    )
