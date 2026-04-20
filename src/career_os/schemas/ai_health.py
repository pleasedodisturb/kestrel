"""Pydantic schemas for AI provider health dashboard."""

from pydantic import BaseModel, Field

from career_os.schemas.constraints import INT64_MAX, INT64_MIN


class ProviderCredits(BaseModel):
    """Credit/quota information for an AI provider."""

    remaining: float | None = Field(None, description="Remaining credits/tokens")
    total: float | None = Field(None, description="Total credits/tokens quota")
    unit: str = Field("credits", description="Unit of measurement (credits, tokens, USD)")


class ProviderRateLimit(BaseModel):
    """Rate limit information for an AI provider."""

    requests_per_minute: int | None = Field(None, ge=INT64_MIN, le=INT64_MAX, description="RPM limit")
    tokens_per_minute: int | None = Field(None, ge=INT64_MIN, le=INT64_MAX, description="TPM limit")


class ProviderHealthStatus(BaseModel):
    """Health status for a single AI provider."""

    name: str = Field(..., description="Provider identifier")
    display_name: str = Field(..., description="Human-readable provider name")
    status: str = Field(
        ...,
        description="Health status: reachable | unreachable | not_configured | error",
    )
    is_default: bool = Field(False, description="Whether this is the currently active provider")
    error_message: str | None = Field(
        None, description="Error details if status is error/unreachable"
    )
    credits: ProviderCredits | None = Field(None, description="Credit/quota info if available")
    rate_limit: ProviderRateLimit | None = Field(None, description="Rate limit info if available")
    response_time_ms: float | None = Field(None, description="Ping response time in milliseconds")


class AIHealthResponse(BaseModel):
    """Response from GET /api/ai/health."""

    providers: list[ProviderHealthStatus] = Field(..., description="Health status per provider")
    default_provider: str = Field(..., description="Name of the current default provider")
