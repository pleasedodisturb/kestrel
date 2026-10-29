"""Seed default data on first run."""

import logging

from sqlalchemy.orm import Session

from career_os.models.models import Profile

logger = logging.getLogger(__name__)

DEFAULT_PROFILE = {
    "name": "Kestrel User",
    "email": "user@example.com",
    "location": "Remote",
    "job_family": "Your Target Role",
}


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
