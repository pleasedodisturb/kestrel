# Phase 3: Advanced Testing - Pattern Map

**Mapped:** 2026-04-20
**Files analyzed:** 10 new/modified files
**Analogs found:** 5 / 10

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tests/regression/__init__.py` | config | -- | -- | boilerplate |
| `tests/regression/test_golden_set.py` | test | CRUD (scoring pipeline) | `tests/test_scoring_rubric.py` | exact |
| `tests/property/__init__.py` | config | -- | -- | boilerplate |
| `tests/property/test_scoring_properties.py` | test | transform (invariants) | `tests/test_scoring_rubric.py` | role-match |
| `tests/property/test_state_machine.py` | test | event-driven (transitions) | `tests/test_scoring_rubric.py` | partial |
| `tests/fuzz/__init__.py` | config | -- | -- | boilerplate |
| `tests/fuzz/test_api_fuzz.py` | test | request-response (ASGI) | `tests/test_scoring.py` | partial |
| `pyproject.toml` | config | -- | `pyproject.toml` (self) | exact |
| `.gitignore` | config | -- | `.gitignore` (self) | exact |
| `tests/regression/conftest.py` (optional) | config | -- | `tests/conftest.py` | role-match |

## Pattern Assignments

### `tests/regression/test_golden_set.py` (test, CRUD/scoring pipeline)

**Analog:** `tests/test_scoring_rubric.py`

**Imports pattern** (lines 1-41):
```python
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from career_os.database import Base
from career_os.models.models import Profile
from career_os.schemas.ai import (
    AIFeature,
    AIResponse,
    ATSKeyword,
    DimensionalScores,
    ScoreBreakdownFactor,
    ScoreResult,
)
from career_os.services.scoring import score_job
```

**Fixture directory pattern** (lines 47-48):
```python
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
```

**DB session fixture pattern** (lines 50-80):
```python
@pytest.fixture()
def db_session():
    """Create a fresh in-memory database for rubric tests."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)

    connection = engine.connect()
    test_session_cls = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = test_session_cls()

    profile = Profile(
        id=1,
        name="Test User",
        email="test@example.com",
        location="Frankfurt",
        job_family="TPM",
    )
    session.add(profile)
    session.commit()

    yield session
    session.close()
    connection.close()
    engine.dispose()
```

**Golden set fixture loading pattern** (lines 425-434):
```python
@pytest.fixture()
def golden_set(self):
    path = FIXTURES_DIR / "scoring_golden_set.json"
    assert path.exists(), f"Golden set fixture not found at {path}"
    with open(path) as f:
        data = json.load(f)
    # Support both legacy (bare array) and profile-aware (wrapper) formats
    if isinstance(data, list):
        return data
    return data["jobs"]
```

**Async score_job call with mock provider pattern** (lines 269-329):
```python
@pytest.mark.asyncio
async def test_rubric_version_in_weights_snapshot(self, db_session):
    mock_score_result = ScoreResult(
        fit_score=7.5,
        reasoning="Good match for TPM role with AI focus. " * 5,
        estimated_salary="120-150k EUR",
        effort_flag="medium",
        prep_level="moderate",
        prep_notes="Review ML infrastructure patterns",
        readiness_score=72.0,
        career_alignment=7.0,
        score_breakdown=[
            ScoreBreakdownFactor(factor="Technical skills", contribution=2.0, description="Strong Python"),
            ScoreBreakdownFactor(factor="Role alignment", contribution=1.5, description="Direct TPM match"),
            ScoreBreakdownFactor(factor="Domain fit", contribution=1.0, description="AI platform experience"),
        ],
        dimensional_scores=DimensionalScores(
            technical_fit=7.0, seniority_alignment=8.0, compensation_fit=7.5,
            location_fit=9.0, career_trajectory=7.0, company_fit=6.5,
        ),
        ats_keywords=[
            ATSKeyword(keyword="Python", category="technical", matched=True),
            ATSKeyword(keyword="TPM", category="domain", matched=True),
            ATSKeyword(keyword="ML infrastructure", category="technical", matched=True),
        ],
    )

    mock_response = AIResponse(
        content="mocked", provider="mock", feature=AIFeature.score,
        structured=mock_score_result,
    )

    with patch("career_os.services.scoring.get_ai_provider") as mock_provider:
        provider_instance = AsyncMock()
        provider_instance.score.return_value = mock_response
        mock_provider.return_value = provider_instance

        scored = await score_job(
            db_session, profile_id=1,
            job_description="Technical Program Manager for AI platform team.",
            job_title="TPM, AI Platform", job_company="TestCorp",
        )
```

**Key design note:** For the golden set, the planner should consider creating a `DeterministicScoringMockProvider` (or patching `_handle_score`) that returns varied scores based on input hashing (using the existing `_deterministic_seed()` function from `mock_provider.py` lines 108-110), so band assertions are meaningful per RESEARCH.md recommendation.

---

### `tests/property/test_scoring_properties.py` (test, transform/invariants)

**Analog:** `tests/test_scoring_rubric.py` (for structure) + Hypothesis patterns from RESEARCH.md

**Imports pattern** -- combine project scoring imports with hypothesis:
```python
from hypothesis import given, settings, strategies as st
import pytest

from career_os.schemas.ai import ScoreResult, ScoreBreakdownFactor, ATSKeyword, DimensionalScores
from career_os.schemas.applications import ApplicationStatus, VALID_TRANSITIONS
```

**Core ScoreResult schema** (from `src/career_os/schemas/ai.py`, verified in RESEARCH.md):
```python
# ScoreResult field constraints (property tests must use these ranges):
# fit_score: float = Field(..., ge=0, le=10)         -- 0-10 scale
# readiness_score: float = Field(..., ge=0, le=100)  -- 0-100 scale
# career_alignment: float = Field(..., ge=0, le=10)  -- 0-10 scale
```

**Marker pattern** -- tests use `@pytest.mark.property`:
```python
@pytest.mark.property
@given(fit_score=st.floats(min_value=0, max_value=10))
@settings(max_examples=200)
def test_score_always_in_range(fit_score):
    """fit_score is always 0-10 (Pydantic enforces this)."""
    ...
```

---

### `tests/property/test_state_machine.py` (test, event-driven/transitions)

**Analog:** `src/career_os/schemas/applications.py` (data source, not test analog)

**VALID_TRANSITIONS dict** (lines 31-64 of `schemas/applications.py`):
```python
VALID_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.discovered: {ApplicationStatus.interested, ApplicationStatus.ghosted},
    ApplicationStatus.interested: {ApplicationStatus.discovered, ApplicationStatus.applied, ApplicationStatus.ghosted},
    ApplicationStatus.applied: {ApplicationStatus.interested, ApplicationStatus.discovered, ApplicationStatus.interviewing, ApplicationStatus.ghosted},
    ApplicationStatus.interviewing: {ApplicationStatus.applied, ApplicationStatus.interested, ApplicationStatus.discovered, ApplicationStatus.offer, ApplicationStatus.ghosted},
    ApplicationStatus.offer: {ApplicationStatus.interviewing, ApplicationStatus.accepted, ApplicationStatus.rejected, ApplicationStatus.ghosted},
    ApplicationStatus.accepted: {ApplicationStatus.discovered},
    ApplicationStatus.rejected: {ApplicationStatus.discovered},
    ApplicationStatus.ghosted: {ApplicationStatus.discovered},
}
```

**is_valid_transition function** (lines 81-91):
```python
def is_valid_transition(from_status: str, to_status: str) -> bool:
    try:
        from_s = ApplicationStatus(from_status.strip().lower())
        to_s = ApplicationStatus(to_status.strip().lower())
    except ValueError:
        return False
```

**Hypothesis stateful pattern** -- from RESEARCH.md (no codebase analog):
```python
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize
from hypothesis import strategies as st
from career_os.schemas.applications import ApplicationStatus, VALID_TRANSITIONS, is_valid_transition

class ApplicationStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.current_status = None

    @initialize()
    def start(self):
        self.current_status = ApplicationStatus.discovered

    @rule(target_status=st.sampled_from(list(ApplicationStatus)))
    def attempt_transition(self, target_status):
        if is_valid_transition(self.current_status, target_status):
            self.current_status = target_status
        assert self.current_status in ApplicationStatus.__members__.values()
        assert self.current_status in VALID_TRANSITIONS

TestApplicationStateMachine = ApplicationStateMachine.TestCase
```

---

### `tests/fuzz/test_api_fuzz.py` (test, request-response/ASGI)

**Analog:** `tests/test_scoring.py` (for FastAPI app import pattern)

**App import pattern** (from `tests/conftest.py` lines 12, 63-65):
```python
from career_os.main import app
```

**TestClient pattern** (from `tests/conftest.py` lines 62-65):
```python
@pytest.fixture
def client() -> TestClient:
    """Create a FastAPI test client."""
    return TestClient(app)
```

**Schemathesis ASGI pattern** -- from RESEARCH.md (no codebase analog):
```python
import schemathesis
from hypothesis import settings
from career_os.main import app

schema = schemathesis.openapi.from_asgi("/openapi.json", app)

@pytest.mark.fuzz
@schema.parametrize()
@settings(max_examples=50)
def test_api_no_500(case):
    """No endpoint returns 500 on valid-schema inputs."""
    response = case.call_and_validate()
    assert response.status_code < 500
```

---

### `pyproject.toml` (config modification)

**Current pytest config** (lines 96-106):
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
timeout = 30
markers = [
    "unit: Pure logic tests with no external dependencies (auto-applied)",
    "integration: Tests using database, API client, or external fixtures (auto-applied)",
    "slow: Tests exceeding 5s runtime (auto-detected after execution)",
    "smoke: Health check tests (manually applied, 1-2 tests)",
    "regression: Golden set regression tests (Phase 3, ADV-01)",
]
```

**Required modifications:**
1. Add `property` and `fuzz` markers to the markers list
2. Add `addopts = "-m 'not regression and not property and not fuzz'"` to exclude advanced tests from default run (D-11)
3. Add `hypothesis>=6.152.0` and `schemathesis>=4.15.0` to `[project.optional-dependencies] dev`

---

## Shared Patterns

### Database Session Fixture
**Source:** `tests/conftest.py` lines 73-107, also `tests/test_scoring_rubric.py` lines 50-80
**Apply to:** `tests/regression/test_golden_set.py`

The project has two patterns:
1. **Shared fixture** from `conftest.py` -- uses `db_session` fixture with dependency override on the FastAPI app
2. **Local fixture** from individual test files (e.g., `test_scoring_rubric.py`) -- self-contained db_session with profile seeding

Golden set tests should use approach 2 (local fixture) to seed the specific profile data matching the golden set fixture's `profile` section.

### MockProvider Deterministic Seed
**Source:** `src/career_os/ai/mock_provider.py` lines 108-110
**Apply to:** `tests/regression/test_golden_set.py` (for creating DeterministicScoringMockProvider)
```python
def _deterministic_seed(text: str) -> int:
    """Produce a deterministic integer seed from input text."""
    return int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
```

### Test Class Organization
**Source:** `tests/test_scoring.py` (throughout), `tests/test_scoring_rubric.py` (throughout)
**Apply to:** All new test files

Pattern: Group related tests in classes with docstrings referencing requirement IDs:
```python
class TestGoldenSetTPM:
    """Golden set regression for TPM job family (ADV-01)."""
```

### Marker Application
**Source:** `tests/conftest.py` lines 25-49
**Apply to:** All new test files

The `pytest_collection_modifyitems` hook auto-marks tests as `unit` or `integration` based on fixture usage. New tests using `db_session` will be auto-marked `integration`. The explicit `@pytest.mark.regression`, `@pytest.mark.property`, and `@pytest.mark.fuzz` markers are additive and used for selection/exclusion.

### Golden Set Fixture Format
**Source:** `tests/fixtures/scoring_golden_set.json` (lines 1-15 shown)
**Apply to:** `tests/regression/test_golden_set.py`
```json
{
  "profile": {
    "job_family": "TPM",
    "location": "Berlin, Germany",
    "key_skills": ["Python", "AI/ML", "Program Management"]
  },
  "jobs": [
    {
      "id": "gs-01",
      "category": "reject",
      "expected_band": [1, 3],
      "title": "Senior .NET Developer",
      "company": "SAP SE",
      "location": "Walldorf, Germany",
      "description": "Build enterprise ERP modules in C#/.NET 8..."
    }
  ]
}
```

### score_job Function Signature
**Source:** `src/career_os/services/scoring.py` line 3212
**Apply to:** `tests/regression/test_golden_set.py`
```python
async def score_job(
    db: Session,
    profile_id: int,
    job_description: str,
    *,
    job_url: str | None = None,
    job_title: str | None = None,
    job_company: str | None = None,
    discovered_job_id: int | None = None,
    application_id: int | None = None,
) -> ScoredJob:
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `tests/property/test_scoring_properties.py` | test | transform | No Hypothesis property tests exist yet -- use RESEARCH.md patterns |
| `tests/property/test_state_machine.py` | test | event-driven | No RuleBasedStateMachine tests exist yet -- use RESEARCH.md patterns |
| `tests/fuzz/test_api_fuzz.py` | test | request-response | No Schemathesis tests exist yet -- use RESEARCH.md patterns |

## Metadata

**Analog search scope:** `tests/`, `src/career_os/`
**Files scanned:** 8 analog candidates read, 3 strong matches found
**Pattern extraction date:** 2026-04-20
