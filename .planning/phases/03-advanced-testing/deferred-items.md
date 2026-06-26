# Phase 03: Deferred Items

## Discovered by Schemathesis Fuzzing (Plan 03-03)

### 1. OverflowError on large integer inputs (multiple endpoints)

**Severity:** Medium
**Endpoints:** calendar, contacts, applications, goals, skills, star-stories, voice, ticktick, and others
**Description:** `profile_id` and other integer path/body parameters exceeding INT64 max (e.g., 9223372036854775808) cause unhandled `OverflowError: Python int too large to convert to SQLite INTEGER`. The OpenAPI schema specifies `integer` without `maximum` constraint.
**Fix:** Add `le=9223372036854775807` (INT64 max) constraints to Pydantic Field definitions for all integer IDs, or add a global middleware/exception handler for OverflowError.

### 2. Datetime fields missing timezone suffix (RFC 3339)

**Severity:** Low
**Endpoints:** All endpoints returning `created_at` / `updated_at` fields
**Description:** Response datetime fields like `2026-04-20T13:53:06.860820` lack timezone suffix but OpenAPI schema specifies `format: date-time` (RFC 3339 requires timezone, e.g., `Z` or `+00:00`).
**Fix:** Use `datetime.datetime.now(datetime.timezone.utc)` in model defaults, or configure SQLAlchemy column defaults to include timezone.

### 3. Intelligence/salary endpoint returns 500

**Severity:** Medium
**Endpoint:** `GET /api/intelligence/salary`
**Description:** Returns HTTP 500 on certain fuzzed query parameter combinations.
**Fix:** Investigate endpoint error handling and add input validation.
