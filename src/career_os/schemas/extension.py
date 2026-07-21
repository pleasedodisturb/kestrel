"""Pydantic request/response models for the browser-extension API (Phase 0).

These mirror the wire contract in the Phase-0 plan. 00-02/00-03 build the
extension client against exactly these shapes, so keep them stable.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PairRequest(BaseModel):
    """Body for POST /api/extension/pair."""

    pairing_code: str = Field(..., description="6-digit code shown by the running instance")


class InstanceInfo(BaseModel):
    """Non-sensitive identity of the Kestrel instance returned to the extension."""

    name: str = Field(..., description="Product brand name")
    version: str = Field(..., description="Running backend version")


class PairResponse(BaseModel):
    """Successful pairing response — the minted extension token + instance info."""

    token: str = Field(..., description="Opaque bearer token the extension stores")
    instance: InstanceInfo


class CaptureRequest(BaseModel):
    """Normalized job payload captured by the extension (Phase 0 stub target)."""

    url: str
    title: str
    company: str
    description: str
    location: str | None = None
    salary: str | None = None
    source: str | None = None


class CaptureResponse(BaseModel):
    """Stub capture response — accepted with an id, but NOT scored in Phase 0."""

    job_id: str
    status: str = "accepted"
    scored: bool = False


class StatusResponse(BaseModel):
    """Response for GET /api/extension/status."""

    ok: bool = True
    instance: InstanceInfo
