"""Cost preset API routes."""

from fastapi import APIRouter, HTTPException

from career_os.schemas.presets import (
    ActivePresetResponse,
    PresetListResponse,
    PresetResponse,
    SetActivePresetRequest,
)
from career_os.services.presets import (
    apply_preset,
    get_active_preset_name,
    get_preset,
    list_presets,
)

router = APIRouter(prefix="/api/presets", tags=["presets"])


def _to_response(p) -> PresetResponse:
    """Convert a CostPreset dataclass to a Pydantic response."""
    return PresetResponse(
        name=p.name,
        display_name=p.display_name,
        description=p.description,
        estimated_cost=p.estimated_cost,
        provider=p.provider,
        model=p.model,
        prefilter_strategy=p.prefilter_strategy,
        batch_size=p.batch_size,
    )


@router.get("")
async def list_all_presets() -> PresetListResponse:
    """List all available cost presets with descriptions and estimated costs."""
    presets = list_presets()
    return PresetListResponse(
        presets=[_to_response(p) for p in presets],
        count=len(presets),
    )


@router.get("/active")
async def get_active_preset() -> ActivePresetResponse:
    """Get the currently active cost preset."""
    name = get_active_preset_name()
    preset = get_preset(name)
    # Should never be None since get_active_preset_name validates,
    # but guard defensively.
    if preset is None:  # pragma: no cover
        raise HTTPException(status_code=500, detail="Active preset not found in registry")
    return ActivePresetResponse(active=name, preset=_to_response(preset))


@router.put("/active")
async def set_active_preset(payload: SetActivePresetRequest) -> ActivePresetResponse:
    """Switch to a different cost preset.

    Applies provider, model, and pre-filter settings immediately
    for the running process.
    """
    try:
        preset = apply_preset(payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ActivePresetResponse(active=payload.name, preset=_to_response(preset))
