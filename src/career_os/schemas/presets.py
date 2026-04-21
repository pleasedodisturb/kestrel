"""Pydantic schemas for the Cost Presets API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PresetResponse(BaseModel):
    """Single preset returned by the API."""

    name: str
    display_name: str
    description: str
    estimated_cost: str
    provider: str
    model: str
    prefilter_strategy: str
    batch_size: int


class PresetListResponse(BaseModel):
    """Response for GET /api/presets."""

    presets: list[PresetResponse]
    count: int


class ActivePresetResponse(BaseModel):
    """Response for GET /api/presets/active."""

    active: str = Field(description="Name of the currently active preset")
    preset: PresetResponse


class SetActivePresetRequest(BaseModel):
    """Request body for PUT /api/presets/active."""

    name: str = Field(description="Preset name to activate")
