# Phase 1: Onboarding State Foundation - Research

**Researched:** 2026-04-20
**Domain:** Python backend -- SQLAlchemy model, FastAPI REST endpoints, structured error handling
**Confidence:** HIGH

## Summary

Phase 1 delivers three backend-only artifacts: (1) an `OnboardingState` SQLAlchemy model with per-step timestamp fields persisted in a new `onboarding_states` table, (2) two REST endpoints (`GET/PATCH /api/onboarding/status`) for reading and updating onboarding progress, and (3) an `OnboardingError` exception hierarchy with `user_message`/`resolution` fields and a FastAPI exception handler that prevents stack traces from reaching users.

The codebase has well-established patterns for all three concerns. Models use SQLAlchemy 2.0 mapped columns with `Mapped[]` type annotations. API routes follow a consistent `APIRouter(prefix="/api/<domain>")` pattern with Pydantic v2 schemas. Service-layer exceptions are per-module classes inheriting from `Exception` -- currently ~50 distinct exception classes with no shared base. Alembic migrations run automatically on startup via `_auto_migrate()` in `main.py`, and `render_as_batch=True` is already configured for SQLite compatibility.

**Primary recommendation:** Follow existing codebase conventions exactly. The new onboarding domain is structurally identical to existing domains (profiles, gaps, learning) -- same model/schema/service/API layering, same FK pattern, same test fixture approach. The only novel element is the FastAPI exception handler registration, which has one precedent (SlowAPI rate limiter).

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Step-per-action granularity -- each onboarding action gets its own timestamp field (profile_started_at, profile_completed_at, demo_seeded_at, welcome_completed_at, tour_completed_at, feedback_prompted_at, completed_at)
- **D-02:** Track source surface per step -- each completed step records `via` field ('cli' | 'web') to understand user paths without telemetry
- **D-03:** Include `current_step` string field for resume-from-last-step capability
- **D-04:** `GET /api/onboarding/status` returns full state plus computed `next_step`, `is_complete` boolean, and `progress_pct` integer -- frontend/CLI should not need to derive what comes next
- **D-05:** `PATCH /api/onboarding/status` accepts `{"step": "<step_name>", "via": "cli"|"web"}` -- marks a step complete, sets timestamp server-side, returns full state (same shape as GET)
- **D-06:** PATCH is idempotent -- re-patching the same step is a no-op (no error, returns current state)
- **D-07:** No server-side step ordering enforcement -- steps can be completed in any order (CLI and web have different flows)
- **D-08:** Flat hierarchy with fields -- single `OnboardingError` base class with `user_message`, `resolution`, and `status_code` attributes
- **D-09:** Two subclasses only: `OnboardingValidationError` (422 -- bad input) and `OnboardingStateError` (409 -- invalid state transition)
- **D-10:** FastAPI exception handler catches `OnboardingError` and returns `{"error": user_message, "resolution": resolution}` -- no stack traces reach the user
- **D-11:** Separate `onboarding_states` table with `profile_id` FK (unique, non-nullable) -- one-to-one relationship with Profile
- **D-12:** Profile table remains unchanged -- onboarding is a lifecycle concern, not profile data
- **D-13:** OnboardingState row created when onboarding begins (first PATCH call), not when profile is created

### Claude's Discretion
- Alembic migration structure and naming
- Internal service method signatures
- Test fixture approach
- Whether next_step computation lives in model, schema, or service layer

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INF-01 | Onboarding state persisted in backend DB (per-profile, timestamps not booleans), shared between CLI and web | D-01 through D-03, D-11 through D-13 define exact model shape. SQLAlchemy `Mapped[datetime | None]` pattern verified in existing models. |
| INF-02 | `OnboardingError` exception hierarchy with `user_message` and `resolution` fields | D-08 through D-10 define hierarchy. FastAPI `app.add_exception_handler()` pattern verified (SlowAPI precedent in main.py:148). |
| INF-03 | `GET/PATCH /api/onboarding/status` endpoints for state tracking | D-04 through D-07 define API contract. Existing router pattern (profiles.py) provides exact template. |

</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Onboarding state persistence | Database / Storage | -- | SQLite table with Alembic migration, owned by backend |
| Onboarding REST API | API / Backend | -- | FastAPI routes, Pydantic validation, session injection |
| Step completion logic | API / Backend | -- | Service layer computes next_step, progress, idempotency |
| Error hierarchy + handler | API / Backend | -- | Exception classes + FastAPI exception handler |
| next_step / progress computation | API / Backend | -- | Server-side derivation per D-04; clients consume, never compute |

## Standard Stack

### Core

All packages are already installed in the project. No new dependencies required.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | >=0.115.0 | REST API framework | Already used, defines all API routes [VERIFIED: pyproject.toml] |
| SQLAlchemy | >=2.0 | ORM, model definitions | Already used, Mapped[] column pattern [VERIFIED: pyproject.toml] |
| Pydantic | >=2.10.0 | Request/response schemas | Already used, v2 with model_validate [VERIFIED: pyproject.toml] |
| Alembic | >=1.15.0 | Database migrations | Already used, auto-runs on startup [VERIFIED: pyproject.toml] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | (dev dep) | Test framework | All unit/integration tests [VERIFIED: pyproject.toml] |
| FastAPI TestClient | (bundled) | API testing | HTTP-level endpoint tests [VERIFIED: tests/conftest.py] |

### Alternatives Considered

None -- this phase uses only existing project dependencies. No new packages needed.

**Installation:**
```bash
# No installation needed -- all dependencies already in pyproject.toml
```

## Architecture Patterns

### System Architecture Diagram

```
PATCH /api/onboarding/status {"step":"profile_completed","via":"web"}
         |
         v
  [FastAPI Router]  ── exception handler ──> {"error": msg, "resolution": hint}
         |                                        ^
         v                                        |
  [Onboarding Service]                   OnboardingError raised
         |
         ├── get_or_create_state(profile_id)
         ├── mark_step_complete(step, via)  [idempotent]
         ├── compute_next_step()
         └── compute_progress_pct()
         |
         v
  [OnboardingState Model]  ──FK──>  [Profile]
  (onboarding_states table)         (profiles table)

GET /api/onboarding/status?profile_id=X
         |
         v
  [FastAPI Router] -> [Service] -> [Model query] -> OnboardingStatusResponse
```

### Recommended Project Structure

```
src/career_os/
├── models/
│   └── onboarding.py          # OnboardingState model
├── schemas/
│   └── onboarding.py          # Pydantic request/response schemas
├── services/
│   └── onboarding.py          # Business logic, step computation
├── api/
│   └── onboarding.py          # FastAPI router (GET/PATCH)
├── errors/
│   └── onboarding.py          # OnboardingError hierarchy
└── main.py                    # Register router + exception handler
alembic/versions/
└── xxxx_add_onboarding_states_table.py
tests/
└── test_onboarding_api.py     # Endpoint + service tests
```

### Pattern 1: Model Definition (follow existing convention exactly)

**What:** SQLAlchemy 2.0 mapped column model with timestamp fields
**When to use:** The OnboardingState table definition

```python
# Source: verified from src/career_os/models/models.py (Profile pattern)
from sqlalchemy import DateTime, Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from career_os.database import Base
from career_os.models.models import FK_PROFILES_ID, _utcnow

class OnboardingState(Base):
    __tablename__ = "onboarding_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(FK_PROFILES_ID), nullable=False, unique=True, index=True
    )
    current_step: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Step timestamps (D-01) -- None means not completed
    profile_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    profile_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    demo_seeded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    welcome_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tour_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    feedback_prompted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Source surface tracking (D-02)
    profile_started_via: Mapped[str | None] = mapped_column(String(10), nullable=True)
    profile_completed_via: Mapped[str | None] = mapped_column(String(10), nullable=True)
    demo_seeded_via: Mapped[str | None] = mapped_column(String(10), nullable=True)
    welcome_completed_via: Mapped[str | None] = mapped_column(String(10), nullable=True)
    tour_completed_via: Mapped[str | None] = mapped_column(String(10), nullable=True)
    feedback_prompted_via: Mapped[str | None] = mapped_column(String(10), nullable=True)
    completed_via: Mapped[str | None] = mapped_column(String(10), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)
```

### Pattern 2: API Route (follow profiles.py pattern)

**What:** FastAPI router with dependency injection
**When to use:** The onboarding endpoints

```python
# Source: verified from src/career_os/api/profiles.py
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from career_os.database import get_db

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

@router.get("/status")
async def get_onboarding_status(
    profile_id: Annotated[int, Query(description="Profile ID")],
    db: Annotated[Session, Depends(get_db)],
) -> OnboardingStatusResponse:
    ...
```

### Pattern 3: Pydantic Schema (follow profiles.py pattern)

**What:** Request/response models with `from_attributes`
**When to use:** API input/output validation

```python
# Source: verified from src/career_os/schemas/profiles.py
from pydantic import BaseModel, Field
from typing import Literal

class OnboardingStepUpdate(BaseModel):
    step: str = Field(..., description="Step name to mark complete")
    via: Literal["cli", "web"] = Field(..., description="Source surface")

class OnboardingStatusResponse(BaseModel):
    profile_id: int
    current_step: str | None
    next_step: str | None
    is_complete: bool
    progress_pct: int
    # ... timestamp fields ...
    model_config = {"from_attributes": True}
```

### Pattern 4: FastAPI Exception Handler

**What:** App-level exception handler for OnboardingError hierarchy
**When to use:** Registered once in main.py

```python
# Source: verified pattern from main.py:148 (SlowAPI handler registration)
# In main.py:
from career_os.errors.onboarding import OnboardingError

@app.exception_handler(OnboardingError)
async def onboarding_error_handler(request: Request, exc: OnboardingError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.user_message, "resolution": exc.resolution},
    )
```

### Pattern 5: Error Hierarchy (D-08, D-09)

**What:** Flat exception hierarchy with structured fields
**When to use:** All onboarding error cases

```python
class OnboardingError(Exception):
    """Base onboarding error with user-facing fields."""
    def __init__(self, user_message: str, resolution: str, status_code: int = 400):
        self.user_message = user_message
        self.resolution = resolution
        self.status_code = status_code
        super().__init__(user_message)

class OnboardingValidationError(OnboardingError):
    """Bad input (422)."""
    def __init__(self, user_message: str, resolution: str):
        super().__init__(user_message, resolution, status_code=422)

class OnboardingStateError(OnboardingError):
    """Invalid state transition (409)."""
    def __init__(self, user_message: str, resolution: str):
        super().__init__(user_message, resolution, status_code=409)
```

### Anti-Patterns to Avoid

- **Duplicating ProfileNotFoundError:** The codebase has ~15 copies of `ProfileNotFoundError` across services. For onboarding, raise HTTPException(404) directly in the route (matching profiles.py pattern) rather than creating yet another copy.
- **Computing next_step in the schema:** Pydantic schemas should be data containers. Put computation in the service layer where it can be tested independently.
- **Step ordering in the model:** D-07 says no server-side ordering. The step sequence for `next_step` computation should be a simple list in the service layer, not enforced via DB constraints.
- **Creating OnboardingState on Profile creation:** D-13 explicitly says lazy creation on first PATCH, not eager on profile creation. Don't add a Profile `after_insert` event.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Database migrations | Manual SQL DDL | Alembic autogenerate | Handles SQLite batch mode, version tracking, auto-run on startup |
| Request validation | Manual if/else checks | Pydantic Field validators + Literal types | `via: Literal["cli", "web"]` handles validation automatically |
| Timestamp generation | Manual datetime calls | `_utcnow()` factory + SQLAlchemy defaults | Already standardized across the codebase |
| FK enforcement | Application-level checks | SQLAlchemy FK + DB constraint | `PRAGMA foreign_keys=ON` already enabled via event listener |

**Key insight:** This phase introduces zero new libraries. Every building block exists in the codebase. The risk is deviation from established patterns, not missing capabilities.

## Common Pitfalls

### Pitfall 1: Alembic Import of New Model
**What goes wrong:** New model file (`models/onboarding.py`) not imported in `alembic/env.py`, so autogenerate produces empty migration.
**Why it happens:** Alembic only sees models registered on `Base.metadata`. Models in separate files must be imported.
**How to avoid:** Add `from career_os.models import onboarding as _onboarding  # noqa: E402, F401` to `alembic/env.py` alongside existing model imports.
**Warning signs:** `alembic revision --autogenerate` produces a migration with empty `upgrade()`.

### Pitfall 2: SQLite Batch Mode for ALTER TABLE
**What goes wrong:** SQLite doesn't support `ALTER TABLE ... ADD COLUMN` with constraints in all cases.
**Why it happens:** SQLite has limited ALTER TABLE support compared to PostgreSQL.
**How to avoid:** Already mitigated -- `render_as_batch=True` is configured in `alembic/env.py` for both online and offline modes. New table creation (CREATE TABLE) is unaffected, but verify the generated migration uses batch mode if any ALTER is needed.
**Warning signs:** Migration fails with "near CONSTRAINT: syntax error".

### Pitfall 3: Unique Constraint on profile_id
**What goes wrong:** One-to-one relationship (D-11) requires `unique=True` on `profile_id` column. Forgetting this allows multiple onboarding states per profile.
**Why it happens:** ForeignKey doesn't imply uniqueness by default.
**How to avoid:** Explicitly set `unique=True` on the `profile_id` mapped_column.
**Warning signs:** Second PATCH for same profile creates duplicate rows instead of updating.

### Pitfall 4: Idempotent PATCH Timestamp Preservation
**What goes wrong:** Re-patching a completed step overwrites the original timestamp with a new one.
**Why it happens:** Naive implementation sets timestamp on every PATCH without checking if already set.
**How to avoid:** Service layer must check `if getattr(state, f"{step}_at") is not None: return state` before setting timestamp (D-06 idempotency).
**Warning signs:** Timestamps change on repeat requests for the same step.

### Pitfall 5: Missing Profile Validation
**What goes wrong:** PATCH with non-existent profile_id creates orphaned onboarding state or fails with cryptic FK error.
**Why it happens:** D-13 says create-on-first-PATCH. If profile doesn't exist, FK constraint fails.
**How to avoid:** Query profile first, raise HTTPException(404) if not found (matching profiles.py pattern), then create/update onboarding state.
**Warning signs:** 500 error with IntegrityError traceback instead of clean 404.

### Pitfall 6: Test Fixture DB Session Sharing
**What goes wrong:** Tests that create onboarding state don't see data because test session is different from app session.
**Why it happens:** conftest.py uses a shared connection pattern with dependency override.
**How to avoid:** Follow the exact `db_session` fixture pattern in `tests/conftest.py` -- it uses `app.dependency_overrides[get_db]` so both test code and the FastAPI app see the same in-memory tables.
**Warning signs:** GET returns empty after POST/PATCH in same test.

## Code Examples

### Alembic Migration Generation

```bash
# Source: standard Alembic workflow [VERIFIED: alembic/env.py config]
cd /Users/pleasedodisturb/Projects/kestrel-onboarding
alembic revision --autogenerate -m "add_onboarding_states_table"
```

### Test Pattern (follow conftest.py fixtures)

```python
# Source: verified from tests/conftest.py
def test_get_onboarding_status(client, db_session, profile):
    """GET returns default state for profile with no onboarding."""
    response = client.get(f"/api/onboarding/status?profile_id={profile.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["is_complete"] is False
    assert data["progress_pct"] == 0

def test_patch_step_idempotent(client, db_session, profile):
    """PATCH same step twice is no-op (D-06)."""
    payload = {"step": "profile_completed", "via": "cli"}
    r1 = client.patch(f"/api/onboarding/status?profile_id={profile.id}", json=payload)
    ts1 = r1.json()["profile_completed_at"]
    r2 = client.patch(f"/api/onboarding/status?profile_id={profile.id}", json=payload)
    ts2 = r2.json()["profile_completed_at"]
    assert ts1 == ts2  # timestamp unchanged
```

### Service Layer next_step Computation (Claude's discretion)

```python
# Recommended: service layer with ordered step list
STEP_ORDER = [
    "profile_started",
    "profile_completed",
    "demo_seeded",
    "welcome_completed",
    "tour_completed",
    "feedback_prompted",
]

def compute_next_step(state: OnboardingState) -> str | None:
    """Return first incomplete step, or None if all done."""
    for step in STEP_ORDER:
        if getattr(state, f"{step}_at") is None:
            return step
    return None

def compute_progress_pct(state: OnboardingState) -> int:
    """Return percentage of steps completed (0-100)."""
    total = len(STEP_ORDER)
    done = sum(1 for s in STEP_ORDER if getattr(state, f"{s}_at") is not None)
    return int((done / total) * 100)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Boolean `is_onboarded` flag | Per-step timestamps (D-01) | This project | Enables resume, progress tracking, analytics |
| Per-service exception classes | Shared base with structured fields (D-08) | This phase | First structured error pattern in this codebase |
| Manual try/except in routes | App-level exception handler (D-10) | This phase | Eliminates boilerplate in onboarding routes |

**Note on error pattern evolution:** The codebase currently has ~50 per-service exception classes with no shared base and manual `try/except` → `HTTPException` conversion in every route. The onboarding error hierarchy (D-08 through D-10) is a deliberate improvement. However, this phase should NOT refactor existing exceptions -- only onboarding errors use the new pattern. Future phases may adopt it.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `completed_at` timestamp field tracks overall onboarding completion (separate from individual step timestamps) | Architecture Patterns | Minor -- field name could be `onboarding_completed_at` for clarity |
| A2 | GET endpoint for non-existent onboarding state should return a default "empty" response (all nulls, 0%) rather than 404 | Architecture Patterns | Medium -- if 404 is intended, frontend must handle it differently |
| A3 | The `via` field per step is stored as a separate column per step (e.g., `profile_completed_via`) rather than a JSON blob | Code Examples | Low -- column-per-step is consistent with D-01 timestamp pattern |

## Open Questions

1. **GET behavior when no OnboardingState exists**
   - What we know: D-13 says row created on first PATCH, not on profile creation
   - What's unclear: Should GET for a profile with no onboarding state return a synthesized "empty" response (200 with all nulls) or 404?
   - Recommendation: Return 200 with synthesized empty state (all timestamps null, `is_complete=false`, `progress_pct=0`). This is simpler for frontends -- they don't need to distinguish "hasn't started" from "error". Mark as A2 assumption.

2. **Step name validation**
   - What we know: D-05 accepts `{"step": "<step_name>"}`. D-07 says no ordering enforcement.
   - What's unclear: Should invalid step names (e.g., `{"step": "nonexistent_step"}`) return 422?
   - Recommendation: Yes -- validate step names against the known set using `Literal` type or explicit check. Invalid names are a client bug and should fail fast with `OnboardingValidationError`.

3. **Relationship direction on Profile model**
   - What we know: D-12 says Profile table unchanged
   - What's unclear: Should Profile model get a `relationship()` backref to OnboardingState?
   - Recommendation: Add `onboarding_state` relationship on Profile for convenience (D-12 says table unchanged, not model unchanged). This is a Python-side addition only, no migration needed.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (installed as dev dep) |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `pytest tests/test_onboarding_api.py -x -v` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INF-01 | OnboardingState persisted per-profile with timestamps | unit | `pytest tests/test_onboarding_api.py::test_state_persisted -x` | Wave 0 |
| INF-01 | State survives server restart (DB-backed) | integration | `pytest tests/test_onboarding_api.py::test_state_survives_restart -x` | Wave 0 |
| INF-02 | OnboardingError has user_message + resolution | unit | `pytest tests/test_onboarding_api.py::test_error_fields -x` | Wave 0 |
| INF-02 | Exception handler returns structured JSON, no stack trace | integration | `pytest tests/test_onboarding_api.py::test_error_response_format -x` | Wave 0 |
| INF-03 | GET returns full state + computed fields | integration | `pytest tests/test_onboarding_api.py::test_get_status -x` | Wave 0 |
| INF-03 | PATCH marks step complete with timestamp | integration | `pytest tests/test_onboarding_api.py::test_patch_step -x` | Wave 0 |
| INF-03 | PATCH is idempotent (D-06) | integration | `pytest tests/test_onboarding_api.py::test_patch_idempotent -x` | Wave 0 |
| INF-03 | PATCH returns 404 for non-existent profile | integration | `pytest tests/test_onboarding_api.py::test_patch_missing_profile -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_onboarding_api.py -x -v`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_onboarding_api.py` -- covers INF-01, INF-02, INF-03
- [ ] No new framework install needed -- pytest already configured

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | API key auth middleware already exists (optional) |
| V3 Session Management | no | Stateless REST, no session tokens in this phase |
| V4 Access Control | yes | Profile ID scoping -- ensure user can only read/write own profile's onboarding state |
| V5 Input Validation | yes | Pydantic Literal type for `via` field, step name validation |
| V6 Cryptography | no | No secrets or encryption in onboarding state |

### Known Threat Patterns for FastAPI + SQLite

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| IDOR on profile_id | Tampering | Validate profile_id exists and belongs to caller (when auth enabled) |
| Invalid step injection | Tampering | Validate step name against known set (Literal or explicit check) |
| Mass assignment | Tampering | Pydantic schema restricts accepted fields to `step` and `via` only |

## Project Constraints (from CLAUDE.md)

- **Testing:** Every piece of code must have tests, written alongside the code
- **Python style:** Ruff linting (line-length=100, select E/F/I/UP/B/SIM), `ruff check --fix && ruff format`
- **Commits:** Conventional commit format with Linear ticket ID in scope, must have body
- **Architecture:** Layered (API -> Service -> Model -> Database), schemas parallel API routes
- **Migrations:** Alembic with auto-run on startup

## Sources

### Primary (HIGH confidence)
- `src/career_os/models/models.py` -- Model pattern (Mapped[], timestamps, FK constants)
- `src/career_os/api/profiles.py` -- API route pattern (router, deps, responses)
- `src/career_os/schemas/profiles.py` -- Pydantic v2 schema pattern (model_config, field_validator)
- `src/career_os/database.py` -- Session factory, get_db dependency, WAL mode
- `src/career_os/main.py` -- Router registration, exception handler registration, auto-migrate
- `src/career_os/services/gap_analysis.py` -- Service exception pattern
- `alembic/env.py` -- render_as_batch=True, model imports
- `tests/conftest.py` -- Test fixture pattern (db_engine, db_session, profile, dependency override)
- `pyproject.toml` -- Package versions (FastAPI >=0.115.0, SQLAlchemy >=2.0, Pydantic >=2.10.0, Alembic >=1.15.0)

### Secondary (MEDIUM confidence)
- Exception handler pattern verified from SlowAPI registration in main.py:148

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all packages already installed, versions verified from pyproject.toml
- Architecture: HIGH -- every pattern directly verified from existing codebase files
- Pitfalls: HIGH -- derived from actual codebase conventions and SQLite-specific constraints

**Research date:** 2026-04-20
**Valid until:** 2026-05-20 (stable -- backend patterns unlikely to change)
