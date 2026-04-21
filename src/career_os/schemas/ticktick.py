"""Pydantic schemas for TickTick Sync API."""

from datetime import datetime

from pydantic import BaseModel, Field


class TickTickSyncTaskResponse(BaseModel):
    """Response schema for a single sync task mapping."""

    id: int
    entity_type: str
    entity_id: int
    ticktick_task_id: str
    title: str
    status: str
    last_synced_at: datetime | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}


class TickTickSyncStatusResponse(BaseModel):
    """Response schema for overall TickTick sync status."""

    total_tasks: int
    synced: int
    completed: int
    errors: int
    last_sync_at: str | None = None
    tasks: list[TickTickSyncTaskResponse]


class TickTickPushRequest(BaseModel):
    """Request to push a specific entity to TickTick."""

    entity_type: str = Field(..., description="Type: follow_up | learning_goal | pipeline_action")
    entity_id: int = Field(..., description="ID of the entity to sync")
    profile_id: int = Field(..., description="Profile ID")


class TickTickPushResponse(BaseModel):
    """Response after pushing an entity to TickTick."""

    success: bool
    message: str
    sync_task: TickTickSyncTaskResponse | None = None


class TickTickPullResponse(BaseModel):
    """Response after pulling completions from TickTick."""

    success: bool
    message: str
    synced: int = 0
    errors: int = 0
    skipped: int = 0


class TickTickConnectionTestResponse(BaseModel):
    """Response from testing TickTick connection."""

    success: bool
    message: str
    tested_at: datetime
