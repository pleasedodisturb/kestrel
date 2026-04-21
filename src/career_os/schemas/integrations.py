"""Pydantic schemas for Integration Configuration API."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from career_os.schemas.constraints import INT64_MAX, INT64_MIN


def _ensure_utc(v: Any) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime) and v.tzinfo is None:
        return v.replace(tzinfo=UTC)
    return v


# ---- Integration definitions ----


class IntegrationFieldDef(BaseModel):
    """Describes a single credential field for an integration."""

    key: str
    label: str
    field_type: str = "password"  # password | text | url
    placeholder: str = ""
    required: bool = True


class IntegrationDef(BaseModel):
    """Static definition of a known integration."""

    name: str
    display_name: str
    description: str
    credential_fields: list[IntegrationFieldDef]


# ---- API request/response schemas ----


class IntegrationConfigUpdate(BaseModel):
    """Request body for PUT /api/integrations/{name}/config."""

    enabled: bool | None = Field(default=None, description="Enable or disable integration")
    credentials: dict[str, str] | None = Field(
        default=None, description="Credential key-value pairs"
    )


class IntegrationConnectionTestResult(BaseModel):
    """Inline connection test result returned with PUT responses."""

    success: bool
    message: str
    tested_at: datetime | None = None

    @field_validator("tested_at", mode="before")
    @classmethod
    def _ensure_timestamps_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


class IntegrationConfigResponse(BaseModel):
    """Response schema for a single integration config."""

    name: str
    display_name: str
    description: str
    enabled: bool
    credential_fields: list[IntegrationFieldDef]
    credentials_set: dict[str, bool]  # which credential fields have values (no secrets!)
    status: str  # not_configured | connected | error | disabled
    status_message: str | None = None
    last_tested_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    connection_test: IntegrationConnectionTestResult | None = None

    model_config = {"from_attributes": True}

    @field_validator("last_tested_at", "created_at", "updated_at", mode="before")
    @classmethod
    def _ensure_timestamps_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


class IntegrationListResponse(BaseModel):
    """Response schema for listing all integrations."""

    integrations: list[IntegrationConfigResponse]
    count: int = Field(..., ge=INT64_MIN, le=INT64_MAX)


class IntegrationTestResponse(BaseModel):
    """Response from testing an integration's connection."""

    name: str
    success: bool
    message: str
    tested_at: datetime

    @field_validator("tested_at", mode="before")
    @classmethod
    def _ensure_timestamps_utc(cls, v: Any) -> datetime | None:
        return _ensure_utc(v)


# ---- Registry of known integrations ----

KNOWN_INTEGRATIONS: list[IntegrationDef] = [
    IntegrationDef(
        name="ticktick",
        display_name="TickTick",
        description="Bidirectional task sync with TickTick",
        credential_fields=[
            IntegrationFieldDef(
                key="api_token",
                label="API Token",
                field_type="password",
                placeholder="Your TickTick API token",
            ),
            IntegrationFieldDef(
                key="project_id",
                label="Project ID",
                field_type="text",
                placeholder="TickTick project ID for career tasks",
                required=False,
            ),
        ],
    ),
    IntegrationDef(
        name="calendar",
        display_name="Calendar",
        description="Interview scheduling and follow-up sync to calendar",
        credential_fields=[
            IntegrationFieldDef(
                key="provider",
                label="Provider",
                field_type="text",
                placeholder="ical | google | fantastical",
            ),
            IntegrationFieldDef(
                key="calendar_url",
                label="Calendar URL / ID",
                field_type="url",
                placeholder="CalDAV URL or Google Calendar ID",
                required=False,
            ),
            IntegrationFieldDef(
                key="api_key",
                label="API Key",
                field_type="password",
                placeholder="API key (if applicable)",
                required=False,
            ),
        ],
    ),
    IntegrationDef(
        name="pushover",
        display_name="Pushover",
        description="Push notifications for follow-ups, ghost alerts, and discoveries",
        credential_fields=[
            IntegrationFieldDef(
                key="user_key",
                label="User Key",
                field_type="password",
                placeholder="Pushover user key",
            ),
            IntegrationFieldDef(
                key="app_token",
                label="App Token",
                field_type="password",
                placeholder="Pushover application token",
            ),
        ],
    ),
    IntegrationDef(
        name="voice",
        display_name="Voice Mode",
        description="Voice-driven interaction via SuperWhisper, MacWhisper, or system dictation",
        credential_fields=[
            IntegrationFieldDef(
                key="stt_provider",
                label="STT Provider",
                field_type="text",
                placeholder="superwhisper | macwhisper | system",
                required=False,
            ),
        ],
    ),
    IntegrationDef(
        name="ai_providers",
        display_name="AI Providers",
        description="Configure AI provider API keys and preferences",
        credential_fields=[
            IntegrationFieldDef(
                key="default_provider",
                label="Default Provider",
                field_type="text",
                placeholder="mock | openrouter | anthropic | openai | gemini | together",
            ),
            IntegrationFieldDef(
                key="openrouter_api_key",
                label="OpenRouter API Key",
                field_type="password",
                placeholder="sk-or-...",
                required=False,
            ),
            IntegrationFieldDef(
                key="anthropic_api_key",
                label="Anthropic API Key",
                field_type="password",
                placeholder="sk-ant-...",
                required=False,
            ),
            IntegrationFieldDef(
                key="openai_api_key",
                label="OpenAI API Key",
                field_type="password",
                placeholder="sk-...",
                required=False,
            ),
            IntegrationFieldDef(
                key="gemini_api_key",
                label="Google Gemini API Key",
                field_type="password",
                placeholder="AI...",
                required=False,
            ),
            IntegrationFieldDef(
                key="together_api_key",
                label="Together AI API Key",
                field_type="password",
                placeholder="...",
                required=False,
            ),
        ],
    ),
]

# Quick lookup by name
INTEGRATION_REGISTRY: dict[str, IntegrationDef] = {i.name: i for i in KNOWN_INTEGRATIONS}
