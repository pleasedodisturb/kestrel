"""Tests for Phase 2 ActivityLog extensions and shared log_activity helper."""

import json

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base
from career_os.models.models import Profile
from career_os.services.activity import log_activity


@pytest.fixture(autouse=True)
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    connection = engine.connect()
    session = sessionmaker(bind=connection, autocommit=False, autoflush=False)()

    # Seed profile
    session.add(Profile(id=1, name="Test", email="t@t.com"))
    session.commit()

    yield session
    session.close()
    connection.close()
    engine.dispose()


def test_log_activity_basic(db: Session):
    """Basic log entry with just required fields."""
    log = log_activity(db, profile_id=1, action="test_action")
    db.commit()
    db.refresh(log)

    assert log.id is not None
    assert log.profile_id == 1
    assert log.action == "test_action"
    assert log.source == "api"
    assert log.application_id is None
    assert log.entity_type is None
    assert log.entity_id is None


def test_log_activity_with_entity_fields(db: Session):
    """Log entry with Phase 2 entity-generic fields."""
    log = log_activity(
        db,
        profile_id=1,
        action="contact_created",
        entity_type="contact",
        entity_id=42,
        details="Created contact Jane Doe at Mistral",
        source="cli",
        duration_ms=150,
    )
    db.commit()
    db.refresh(log)

    assert log.entity_type == "contact"
    assert log.entity_id == 42
    assert log.duration_ms == 150
    assert log.source == "cli"
    assert "Jane Doe" in log.details


def test_log_activity_with_error(db: Session):
    """Log entry recording a failure."""
    log = log_activity(
        db,
        profile_id=1,
        action="auto_apply_failed",
        entity_type="submission",
        entity_id=7,
        error="ConnectionTimeout: lever.co did not respond",
        duration_ms=30000,
    )
    db.commit()
    db.refresh(log)

    assert log.error is not None
    assert "ConnectionTimeout" in log.error
    assert log.duration_ms == 30000


def test_log_activity_with_extra_data(db: Session):
    """Log entry with JSON metadata blob."""
    meta = json.dumps({"template": "tpm", "variant": "senior"})
    log = log_activity(
        db,
        profile_id=1,
        action="cv_rendered",
        entity_type="cv_package",
        entity_id=3,
        extra_data=meta,
    )
    db.commit()
    db.refresh(log)

    assert log.extra_data is not None
    parsed = json.loads(log.extra_data)
    assert parsed["template"] == "tpm"


def test_log_activity_backward_compat(db: Session):
    """Legacy application-scoped logging still works."""
    from career_os.models.models import Application

    app_obj = Application(profile_id=1, company="Acme", role="TPM", status="discovered")
    db.add(app_obj)
    db.flush()

    log = log_activity(
        db,
        profile_id=1,
        application_id=app_obj.id,
        action="created",
        details="Created application",
    )
    db.commit()
    db.refresh(log)

    assert log.application_id == app_obj.id
    assert log.entity_type is None  # legacy call didn't set it
