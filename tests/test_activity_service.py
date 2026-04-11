"""Unit tests for `career_os.services.activity`.

Complementary to `test_activity_log_extended.py`. Targets branches and side
effects not covered there:

- default `source="api"` when not provided
- explicit `source` overrides
- caller-controls-the-transaction contract (no implicit commit)
- ordering / multiple inserts on a single session
- application-scoped + entity-generic fields can coexist
- nullable fields stay null when omitted
"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base
from career_os.models.models import ActivityLog, Application, Profile
from career_os.services.activity import log_activity


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    connection = engine.connect()
    session = sessionmaker(bind=connection, autocommit=False, autoflush=False)()

    session.add(Profile(id=1, name="A", email="a@a.com"))
    session.commit()

    yield session
    session.close()
    connection.close()
    engine.dispose()


def test_log_activity_default_source(db: Session):
    """Default source is 'api' when not provided."""
    log = log_activity(db, profile_id=1, action="created")
    db.commit()
    db.refresh(log)
    assert log.source == "api"


def test_log_activity_does_not_commit(db: Session):
    """log_activity must not commit — caller controls the transaction."""
    log_activity(db, profile_id=1, action="staged")
    # Roll back before committing → row should NOT exist
    db.rollback()
    assert db.query(ActivityLog).count() == 0


def test_log_activity_explicit_source_overrides_default(db: Session):
    """Explicit source value is preserved."""
    log = log_activity(db, profile_id=1, action="cli_run", source="cli")
    db.commit()
    assert log.source == "cli"


def test_log_activity_multiple_entries_preserve_order(db: Session):
    """Multiple log entries persist with monotonic ids."""
    a = log_activity(db, profile_id=1, action="step_1")
    b = log_activity(db, profile_id=1, action="step_2")
    c = log_activity(db, profile_id=1, action="step_3")
    db.commit()

    rows = db.query(ActivityLog).order_by(ActivityLog.id).all()
    assert [r.action for r in rows] == ["step_1", "step_2", "step_3"]
    assert a.id < b.id < c.id


def test_log_activity_application_and_entity_fields_coexist(db: Session):
    """application_id + entity_type/entity_id can be set together."""
    app_obj = Application(profile_id=1, company="Co", role="Eng", status="discovered")
    db.add(app_obj)
    db.flush()

    log = log_activity(
        db,
        profile_id=1,
        application_id=app_obj.id,
        action="package_rendered",
        entity_type="cv_package",
        entity_id=99,
    )
    db.commit()
    db.refresh(log)

    assert log.application_id == app_obj.id
    assert log.entity_type == "cv_package"
    assert log.entity_id == 99


def test_log_activity_nullable_fields_stay_null(db: Session):
    """Optional fields default to None when omitted."""
    log = log_activity(db, profile_id=1, action="noop")
    db.commit()
    db.refresh(log)
    assert log.duration_ms is None
    assert log.error is None
    assert log.extra_data is None
    assert log.entity_type is None
    assert log.entity_id is None


def test_log_activity_with_long_details_persists_full_text(db: Session):
    """Large `details` blobs are stored verbatim (Text column)."""
    big = "x" * 10_000
    log = log_activity(db, profile_id=1, action="dump", details=big)
    db.commit()
    db.refresh(log)
    assert log.details is not None
    assert len(log.details) == 10_000
