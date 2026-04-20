"""Tests for the onboarding service layer (Plan 02 Task 2).

Covers all <behavior> items from 01-02-PLAN.md:
- get_onboarding_status with no existing state returns synthesized empty response
- mark_step_complete creates row on first call (D-13)
- mark_step_complete is idempotent (D-06)
- mark_step_complete raises OnboardingValidationError for unknown step names
- After all 7 steps complete, progress_pct == 100 and is_complete == True
- STEP_ORDER has 7 entries matching VALID_STEPS
"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base
from career_os.errors.onboarding import OnboardingValidationError
from career_os.models.models import Profile
from career_os.models.onboarding import OnboardingState
from career_os.schemas.onboarding import VALID_STEPS
from career_os.services.onboarding import (
    STEP_ORDER,
    get_onboarding_status,
    mark_step_complete,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mem_engine():
    """In-memory SQLite engine with all tables created."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _set_fk_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(mem_engine) -> Session:
    """Yield a fresh session per test."""
    Session_ = sessionmaker(bind=mem_engine, autocommit=False, autoflush=False)
    session = Session_()
    yield session
    session.close()


@pytest.fixture
def profile_id(db: Session) -> int:
    """Seed a minimal Profile and return its id."""
    p = Profile(name="Test User")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p.id


# ---------------------------------------------------------------------------
# STEP_ORDER integrity
# ---------------------------------------------------------------------------


def test_step_order_matches_valid_steps():
    """STEP_ORDER must equal VALID_STEPS from schemas (same 7 entries, same order)."""
    assert STEP_ORDER == VALID_STEPS
    assert len(STEP_ORDER) == 7


# ---------------------------------------------------------------------------
# get_onboarding_status — no existing state
# ---------------------------------------------------------------------------


def test_get_status_no_state_returns_empty_response(db: Session, profile_id: int):
    """Profile with no OnboardingState row gets synthesized empty response (A2)."""
    result = get_onboarding_status(profile_id, db)

    assert result.profile_id == profile_id
    assert result.is_complete is False
    assert result.progress_pct == 0
    assert result.next_step == "profile_started"
    assert result.current_step is None
    # No DB row should have been created
    assert db.query(OnboardingState).filter_by(profile_id=profile_id).first() is None


# ---------------------------------------------------------------------------
# mark_step_complete — first call creates row
# ---------------------------------------------------------------------------


def test_mark_step_creates_row_on_first_call(db: Session, profile_id: int):
    """First call to mark_step_complete creates the OnboardingState row (D-13)."""
    assert db.query(OnboardingState).filter_by(profile_id=profile_id).first() is None

    result = mark_step_complete("profile_started", "cli", profile_id, db)

    row = db.query(OnboardingState).filter_by(profile_id=profile_id).first()
    assert row is not None
    assert row.profile_started_at is not None
    assert row.profile_started_via == "cli"
    assert result.profile_started_at is not None
    assert result.profile_started_via == "cli"


def test_mark_step_sets_timestamp_and_via(db: Session, profile_id: int):
    """mark_step_complete sets server-side timestamp and via field (D-05, D-02)."""
    result = mark_step_complete("demo_seeded", "web", profile_id, db)

    assert result.demo_seeded_at is not None
    assert result.demo_seeded_via == "web"


# ---------------------------------------------------------------------------
# mark_step_complete — idempotency (D-06)
# ---------------------------------------------------------------------------


def test_mark_step_idempotent_preserves_original_timestamp(db: Session, profile_id: int):
    """Re-completing same step preserves original timestamp (D-06)."""
    first = mark_step_complete("profile_started", "cli", profile_id, db)
    original_ts = first.profile_started_at
    assert original_ts is not None

    second = mark_step_complete("profile_started", "web", profile_id, db)
    assert second.profile_started_at == original_ts
    # via should also remain unchanged (original value preserved)
    assert second.profile_started_via == "cli"


# ---------------------------------------------------------------------------
# mark_step_complete — validation (D-07, D-09)
# ---------------------------------------------------------------------------


def test_mark_step_raises_for_unknown_step(db: Session, profile_id: int):
    """Unknown step name raises OnboardingValidationError with expected fields."""
    with pytest.raises(OnboardingValidationError) as exc_info:
        mark_step_complete("nonexistent_step", "cli", profile_id, db)

    err = exc_info.value
    assert "nonexistent_step" in err.user_message
    assert "Valid steps are:" in err.resolution
    assert err.status_code == 422


# ---------------------------------------------------------------------------
# Progress computation
# ---------------------------------------------------------------------------


def test_progress_pct_zero_with_no_steps(db: Session, profile_id: int):
    """No steps completed → progress_pct == 0."""
    result = get_onboarding_status(profile_id, db)
    assert result.progress_pct == 0


def test_progress_pct_increases_with_each_step(db: Session, profile_id: int):
    """Each completed step increases progress_pct proportionally."""
    mark_step_complete("profile_started", "cli", profile_id, db)
    result = get_onboarding_status(profile_id, db)
    assert result.progress_pct == int((1 / 7) * 100)  # ~14


def test_all_steps_complete_gives_100_pct_and_is_complete(db: Session, profile_id: int):
    """After completing all 7 steps, progress_pct == 100 and is_complete == True."""
    for step in STEP_ORDER:
        mark_step_complete(step, "cli", profile_id, db)

    result = get_onboarding_status(profile_id, db)
    assert result.progress_pct == 100
    assert result.is_complete is True
    assert result.next_step is None


# ---------------------------------------------------------------------------
# next_step computation (D-04)
# ---------------------------------------------------------------------------


def test_next_step_is_first_incomplete_step(db: Session, profile_id: int):
    """next_step is always the first step in STEP_ORDER that has no timestamp."""
    # Complete only the first two steps
    mark_step_complete("profile_started", "cli", profile_id, db)
    mark_step_complete("profile_completed", "web", profile_id, db)

    result = get_onboarding_status(profile_id, db)
    assert result.next_step == "demo_seeded"  # third step, first incomplete


def test_next_step_none_when_all_complete(db: Session, profile_id: int):
    """next_step is None when all steps are complete."""
    for step in STEP_ORDER:
        mark_step_complete(step, "cli", profile_id, db)

    result = get_onboarding_status(profile_id, db)
    assert result.next_step is None
