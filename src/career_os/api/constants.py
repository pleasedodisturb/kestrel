"""Shared string constants for API route definitions (SonarCloud S1192)."""

# Query parameter descriptions
DESC_PROFILE_ID = "Profile ID"
DESC_ACTIVE_PROFILE_ID = "Active profile ID"
DESC_FILTER_BY_CATEGORY = "Filter by category"

# OpenAPI response descriptions (used 93+ times across 22 API files)
RESP_NOT_FOUND = "Not found"

# Shared OpenAPI responses dicts for common endpoint patterns.
# Using these avoids duplicating the same dict literal across dozens of routes.
RESP_404 = {404: {"description": RESP_NOT_FOUND}}
RESP_404_422 = {404: {"description": RESP_NOT_FOUND}, 422: {"description": "Validation error"}}
RESP_404_500 = {404: {"description": RESP_NOT_FOUND}, 500: {"description": "Internal server error"}}

# Error messages (used 3+ times within single files)
PROFILE_NOT_FOUND = "Profile not found"
TIME_SESSION_NOT_FOUND = "Time session not found"
