"""Shared Profile fixture data to avoid duplicating constructor kwargs across test modules."""

DEFAULT_PROFILE_KWARGS = dict(
    name="Test User",
    email="test@example.com",
    location="Frankfurt",
    job_family="Software Engineering",
)
SECOND_PROFILE_KWARGS = dict(
    name="Other User",
    email="other@example.com",
    location="Berlin",
    job_family="Software Engineering",
)
