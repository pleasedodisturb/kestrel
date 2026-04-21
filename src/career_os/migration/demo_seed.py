"""Seed demo job data for onboarding aha-moment."""

import json
import logging
from datetime import UTC, datetime, timedelta
from importlib.resources import files

from sqlalchemy.orm import Session

from career_os.models.models import Application

logger = logging.getLogger(__name__)


def seed_demo_data(db: Session, profile_id: int) -> int:
    """Seed demo jobs from fixture. Idempotent: delete-then-insert (per D-04).

    Returns:
        Number of records created.
    """
    # D-04: Delete existing demo records first (idempotent replace)
    deleted = (
        db.query(Application)
        .filter(
            Application.is_demo.is_(True),
            Application.profile_id == profile_id,
        )
        .delete()
    )
    if deleted > 0:
        logger.info("Deleted %d existing demo records before re-seeding", deleted)

    # Load fixture via importlib.resources (works in editable and wheel installs)
    fixture_path = files("career_os.fixtures").joinpath("demo_jobs.json")
    jobs = json.loads(fixture_path.read_text(encoding="utf-8"))

    now = datetime.now(UTC)
    created = 0
    for job in jobs:
        created_at = now - timedelta(days=job["days_ago"])
        app = Application(
            profile_id=profile_id,
            company=job["company"],
            role=job["role"],
            source="demo",
            status="discovered",
            fit_score=job["fit_score"],
            salary_range=job["salary_range"],
            notes=job.get("notes", ""),
            is_demo=True,
            created_at=created_at,
            updated_at=created_at,
        )
        db.add(app)
        created += 1

    db.commit()
    logger.info("Seeded %d demo job records", created)
    return created
