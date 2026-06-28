# Phase 3.1: Input Validation Hardening - Context

**Gathered:** 2026-04-20
**Status:** Ready for planning

<domain>
## Phase Boundary

API endpoints reject out-of-range integers at the Pydantic layer, enabling strict fuzz enforcement. All integer fields across schemas and route path parameters get explicit bounds. Schemathesis fuzz tests switch from warning-based FUZZ-500 catch to hard-failure mode (any 500 or unhandled exception = test failure).

</domain>

<decisions>
## Implementation Decisions

### Constraint Strategy
- **D-01:** Per-field Pydantic `Field()` constraints on every integer field in schemas. Explicit, self-documenting, flows into OpenAPI spec so Schemathesis generates in-range values. No type aliases, no middleware, no magic.
- **D-02:** ID fields (profile_id, application_id, contact_id, etc.) use `ge=1, le=9223372036854775807` (SQLite INT64 max). Zero is never a valid auto-incremented ID.
- **D-03:** Path parameters in API route signatures also get explicit bounds via `Annotated[int, Path(ge=1, le=9223372036854775807)]`. Path params bypass Pydantic schema validation — without Path() annotation, `/api/profiles/9999999999999999999` still hits SQLite and crashes.

### Non-ID Integer Fields
- **D-04:** Full audit of ALL integer fields for sensible domain-specific bounds, not just INT64 cap. Examples: salary ge=0 le=10_000_000, priority ge=1 le=100, days ge=1 le=3650. One pass, done right.
- **D-05:** Fields that already have correct bounds (e.g., `distance: ge=0 le=3` in gaps.py, `reminder_minutes_before: ge=0 le=10080` in calendar.py) are left untouched.

### Query Parameters
- **D-06:** Query parameters (limit, offset, page) get explicit bounds with sensible defaults. limit: ge=1 le=100 (default 50). offset: ge=0. page: ge=1. Prevents absurd values that could DoS the DB, and flows into OpenAPI spec for Schemathesis.

### Fuzz Enforcement Mode
- **D-07:** Remove the try/except warning-based catch in `test_api_no_500` entirely. With Pydantic constraints in place, OverflowError should never happen on valid-schema inputs. Any 500 or unhandled exception is a real bug and fails the test immediately.
- **D-08:** Keep `max_examples=50` and existing hypothesis settings. 50 examples per endpoint is a solid fuzz baseline. With valid-range inputs (thanks to Pydantic bounds in OpenAPI), 50 examples test more business logic per run.

### Scope Boundary
- **D-09:** Phase scope is strictly integer bounds + fuzz hardening per G-430. Datetime timezone suffix and intelligence/salary 500 (from Phase 3 deferred-items.md) are out of scope — separate tickets.
- **D-10:** TestAPIWorkflow xfail stays as-is (datetime schema mismatch). Create a Linear ticket for the datetime fix so it's tracked and addressed in a later phase.

### Verification
- **D-11:** Schemathesis passing in hard-failure mode is sufficient verification. No dedicated unit tests for Pydantic validation — that would be testing the framework, not our code. The fuzz suite proves the bounds work across the entire API surface.

### Backward Compatibility
- **D-12:** No backward compatibility concern. Self-hosted single-user app with co-deployed clients. Any value that would now be rejected (422) was already causing a 500 crash. Tightening validation is strictly an improvement.

### Error Response Format
- **D-13:** FastAPI default 422 validation error response is fine. No custom error envelope. Standard, well-documented, clients already expect it.

### Claude's Discretion
- Exact domain-specific bounds for each non-ID field (within reasonable ranges based on field semantics)
- Order of schema file changes (which files to modify first)
- Whether to group commits by concern or by file
- Specific FastAPI `Path()` / `Query()` import patterns

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Fuzz Tests (modify these)
- `tests/fuzz/test_api_fuzz.py` — Current warning-based FUZZ-500 catch to be removed (D-07)
- `tests/fuzz/conftest.py` — Fuzz test fixtures (auth disabled, clean DB)

### Pydantic Schemas (modify these)
- `src/career_os/schemas/` — All schema files with integer fields need audit (D-01, D-04)
- `src/career_os/schemas/profiles.py` — Profile schemas (no integer bounds currently)
- `src/career_os/schemas/applications.py` — Application schemas + VALID_TRANSITIONS
- `src/career_os/schemas/jobs.py` — Job schemas with salary_min/salary_max
- `src/career_os/schemas/contacts.py` — Contact schemas
- `src/career_os/schemas/calendar.py` — Already has some bounds (reminder_minutes ge=0 le=10080)
- `src/career_os/schemas/gaps.py` — Already has some bounds (distance ge=0 le=3)
- `src/career_os/schemas/star_stories.py` — Star story schemas
- `src/career_os/schemas/voice.py` — Voice profile schemas
- `src/career_os/schemas/ticktick.py` — TickTick sync schemas
- `src/career_os/schemas/learning.py` — Learning resource schemas
- `src/career_os/schemas/analytics.py` — Analytics response schemas (mostly output, but audit anyway)
- `src/career_os/schemas/coaching.py` — Coaching schemas with priority field
- `src/career_os/schemas/ai_health.py` — Provider health schemas
- `src/career_os/schemas/privacy.py` — Privacy/retention schemas with days field
- `src/career_os/schemas/scoring.py` — Scoring schemas
- `src/career_os/schemas/ai.py` — AI schemas with token counts

### API Routes (modify path params)
- `src/career_os/api/` — All route files with integer path parameters need `Path(ge=1, le=...)` (D-03)
- `src/career_os/api/profiles.py` — profile_id path params
- `src/career_os/api/applications.py` — application_id path params
- `src/career_os/api/contacts.py` — contact_id path params
- `src/career_os/api/skills.py` — skill_id path params
- `src/career_os/api/scoring.py` — various ID path params
- `src/career_os/api/gaps.py` — application_id path params
- `src/career_os/api/star_stories.py` — application_id path params
- `src/career_os/api/interview_prep.py` — application_id path params
- `src/career_os/api/ticktick.py` — entity_id, profile_id params

### Deferred Items (reference, out of scope)
- `.planning/phases/03-advanced-testing/deferred-items.md` — Datetime timezone and salary 500 issues (D-09, D-10)

### Phase 3 Context (prior decisions)
- `.planning/phases/03-advanced-testing/03-CONTEXT.md` — Phase 3 decisions carried forward

### Requirements
- `.planning/REQUIREMENTS.md` — ADV-03 acceptance criteria (strengthened by this phase)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Field()` already used extensively across schemas (~50+ usages) — adding bounds is the existing pattern
- `tests/fuzz/conftest.py` — StaticPool in-memory DB, auth disabled fixtures — reusable as-is
- Existing bounds precedents: `gaps.py` has `ge=0, le=3`, `calendar.py` has `ge=0, le=10080`

### Established Patterns
- Schemas use `Field(...)` for required and `Field(default=None)` for optional — add ge/le to these
- Path params are bare `int` type hints in route signatures — need `Annotated[int, Path(...)]` wrapper
- Query params likely similar pattern — need `Annotated[int, Query(...)]` wrapper

### Integration Points
- OpenAPI spec at `/openapi.json` auto-generates from Pydantic schemas and FastAPI annotations — bounds will appear automatically
- Schemathesis reads OpenAPI spec — bounded integer ranges will constrain generated fuzz values
- `pyproject.toml` — no changes needed (markers, deps already configured from Phase 3)

</code_context>

<specifics>
## Specific Ideas

- INT64 max constant: `SQLITE_INT64_MAX = 9223372036854775807` — define once, reference everywhere for readability
- The audit should produce a table/checklist of every integer field changed, so reviewers can verify completeness
- After removing the try/except, run the full fuzz suite locally to confirm zero failures before committing

</specifics>

<deferred>
## Deferred Ideas

- **Datetime timezone suffix fix** — Response datetime fields lack timezone suffix (RFC 3339). Needs its own ticket (D-10). Affects TestAPIWorkflow xfail.
- **Intelligence/salary endpoint 500** — Separate input validation issue, needs investigation first. Own ticket.
- **Increase fuzz max_examples for nightly** — Consider bumping to 100-200 in Phase 4's ci-nightly.yml for deeper coverage.

</deferred>

---

*Phase: 031-input-validation-hardening*
*Context gathered: 2026-04-20*
