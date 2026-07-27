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
    """Job payload captured by the extension (Part B — now really scored).

    Two entry modes: structured fields (title+company scraped by the client) OR
    ``raw_text`` only (the backend runs one LLM extraction to fill the fields).
    ``profile_id`` defaults to the single-user self-hosted profile (1).
    """

    url: str = ""
    title: str = ""
    company: str = ""
    description: str = ""
    location: str | None = None
    salary: str | None = None
    source: str | None = None
    raw_text: str | None = Field(
        default=None,
        description="Unstructured page text for the LLM-extraction fallback",
    )
    profile_id: int = Field(default=1, description="Owning profile (single-user default 1)")


class CaptureResponse(BaseModel):
    """Capture response — the deduped DiscoveredJob id plus its fresh score + gap."""

    job_id: str
    status: str = "accepted"
    scored: bool = False
    discovered_job_id: int | None = None
    fit_score: float | None = None
    letter_grade: str | None = None
    score_breakdown: list | None = None
    gap: str | None = None


class PromoteRequest(BaseModel):
    """Body for POST /api/extension/promote — add a captured job to the pipeline."""

    discovered_job_id: int = Field(..., description="DiscoveredJob to promote to an Application")


class PromoteResponse(BaseModel):
    """Result of promoting a captured job — the linked Application id + status."""

    application_id: int
    status: str


class StatusResponse(BaseModel):
    """Response for GET /api/extension/status."""

    ok: bool = True
    instance: InstanceInfo
