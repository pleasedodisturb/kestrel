"""Pydantic schemas for TickTick Sync API."""

from datetime import datetime

from pydantic import BaseModel, Field

from career_os.schemas.constraints import INT64_MAX, INT64_MIN


class TickTickSyncTaskResponse(BaseModel):
    """Response schema for a single sync task mapping."""

    id: int = Field(..., ge=1, le=INT64_MAX)
    entity_type: str
    entity_id: int = Field(..., ge=1, le=INT64_MAX)
    ticktick_task_id: str
    title: str
    status: str
    last_synced_at: datetime | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}


class TickTickSyncStatusResponse(BaseModel):
    """Response schema for overall TickTick sync status."""

    total_tasks: int = Field(..., ge=INT64_MIN, le=INT64_MAX)
    synced: int = Field(..., ge=INT64_MIN, le=INT64_MAX)
    completed: int = Field(..., ge=INT64_MIN, le=INT64_MAX)
    errors: int = Field(..., ge=INT64_MIN, le=INT64_MAX)
    last_sync_at: str | None = None
    tasks: list[TickTickSyncTaskResponse]


class TickTickPushRequest(BaseModel):
    """Request to push a specific entity to TickTick."""

    entity_type: str = Field(..., description="Type: follow_up | learning_goal | pipeline_action")
    entity_id: int = Field(..., ge=1, le=INT64_MAX, description="ID of the entity to sync")
    profile_id: int = Field(..., ge=1, le=INT64_MAX, description="Profile ID")


class TickTickPushResponse(BaseModel):
    """Response after pushing an entity to TickTick."""

    success: bool
    message: str
    sync_task: TickTickSyncTaskResponse | None = None


class TickTickPullResponse(BaseModel):
    """Response after pulling completions from TickTick."""

    success: bool
    message: str
    synced: int = Field(default=0, ge=INT64_MIN, le=INT64_MAX)
    errors: int = Field(default=0, ge=INT64_MIN, le=INT64_MAX)
    skipped: int = Field(default=0, ge=INT64_MIN, le=INT64_MAX)


class TickTickConnectionTestResponse(BaseModel):
    """Response from testing TickTick connection."""

    success: bool
    message: str
    tested_at: datetime
