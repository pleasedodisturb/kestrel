"""Seed default data on first run."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from career_os.models.models import Application, Profile

logger = logging.getLogger(__name__)

DEFAULT_PROFILE = {
    "name": "Kestrel User",
    "email": "user@example.com",
    "location": "Remote",
    "job_family": "Your Target Role",
}

# Aged seed records for ghost detection testing (VAL-PIPE-011).
# These need created_at in the past so the ghost detection thresholds fire.
GHOST_SEED_RECORDS = [
    {
        "company": "GhostCo Applied",
        "role": "Senior Engineer",
        "status": "applied",
        "source": "seed",
        "notes": "Aged seed record for ghost detection testing (applied >14d ago)",
        "days_ago": 18,
    },
    {
        "company": "GhostCo Interviewing",
        "role": "Staff Engineer",
        "status": "interviewing",
        "source": "seed",
        "notes": "Aged seed record for ghost detection testing (interviewing >7d ago)",
        "days_ago": 10,
    },
    {
        "company": "RecentCo Applied",
        "role": "TPM",
        "status": "applied",
        "source": "seed",
        "notes": "Recent seed record — should NOT trigger ghost detection",
        "days_ago": 3,
    },
]


def seed_default_profile(db: Session) -> Profile:
    """Create the default profile if none exists.

    Args:
        db: SQLAlchemy session.

    Returns:
        The default (or existing first) profile.
    """
    existing = db.query(Profile).first()
    if existing:
        logger.info("Default profile already exists: %s (id=%d)", existing.name, existing.id)
        return existing

    profile = Profile(**DEFAULT_PROFILE)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    logger.info("Created default profile: %s (id=%d)", profile.name, profile.id)
    return profile


def seed_ghost_detection_records(db: Session, profile_id: int) -> int:
    """Create aged application records for ghost detection validation.

    Idempotent: skips if records with source='seed' already exist.

    Returns:
        Number of records created.
    """
    existing = (
        db.query(Application)
        .filter(Application.source == "seed", Application.profile_id == profile_id)
        .count()
    )
    if existing > 0:
        logger.info("Ghost seed records already exist (%d), skipping", existing)
        return 0

    now = datetime.now(UTC)
    created = 0
    for record in GHOST_SEED_RECORDS:
        created_at = now - timedelta(days=record["days_ago"])
        app = Application(
            profile_id=profile_id,
            company=record["company"],
            role=record["role"],
            status=record["status"],
            source=record["source"],
            notes=record["notes"],
            created_at=created_at,
            updated_at=created_at,
        )
        db.add(app)
        created += 1

    db.commit()
    logger.info("Seeded %d ghost detection test records", created)
    return created
