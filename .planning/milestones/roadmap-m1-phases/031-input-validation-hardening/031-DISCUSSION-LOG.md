# Phase 3.1: Input Validation Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-20
**Phase:** 031-input-validation-hardening
**Areas discussed:** Constraint strategy, Fuzz enforcement mode, Scope boundary, Non-ID integer fields, Path params vs body fields, Test verification, Query parameters, Error response format, xfail cleanup, Negative integer handling, Fuzz test settings tuning, Backward compatibility

---

## Constraint Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Per-field Pydantic Field() (Recommended) | Add ge=1, le=INT64_MAX to each integer Field() in schemas. Explicit, self-documenting, shows up in OpenAPI spec. | :heavy_check_mark: |
| Annotated type alias | Define SqliteInt once, reuse across all schemas. Less repetition. | |
| FastAPI middleware | Global exception handler that catches OverflowError and returns 422. Zero schema changes. | |

**User's choice:** Per-field Pydantic Field()
**Notes:** Existing pattern in codebase (50+ Field() usages). Self-documenting, flows into OpenAPI spec.

---

## ID Field Lower Bound

| Option | Description | Selected |
|--------|-------------|----------|
| ge=1 (Recommended) | IDs are auto-incremented starting at 1. Zero is never valid. | :heavy_check_mark: |
| ge=0 | More permissive. Allows 0 which would just 404 at DB layer. | |

**User's choice:** ge=1
**Notes:** None

---

## Fuzz Enforcement Mode

| Option | Description | Selected |
|--------|-------------|----------|
| Remove try/except entirely (Recommended) | Delete the warning-based catch. With Pydantic constraints, OverflowError should never happen. Any 500 = real bug. | :heavy_check_mark: |
| Keep try/except but assert False | Replace warnings.warn with pytest.fail(). More descriptive but same outcome. | |
| Allowlist known issues | Remove blanket catch, add allowlist for datetime/salary issues. | |

**User's choice:** Remove try/except entirely
**Notes:** None

---

## Scope Boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Integer bounds + fuzz only (Recommended) | Stay focused on G-430. Datetime and salary issues are separate concerns. | :heavy_check_mark: |
| Include all 3 deferred items | Fix everything in deferred-items.md in one pass. | |
| Include salary 500 only | Salary endpoint 500 fits naturally as input validation. | |

**User's choice:** Integer bounds + fuzz only
**Notes:** None

---

## Non-ID Integer Fields

| Option | Description | Selected |
|--------|-------------|----------|
| Domain-specific bounds (Recommended) | Each field gets bounds that make business sense (salary ge=0, priority ge=1 le=100, etc.) | :heavy_check_mark: |
| INT64 cap only | Just prevent OverflowError. Allow nonsense values. | |
| You decide | Claude picks reasonable domain bounds. | |

**User's choice:** Domain-specific bounds
**Notes:** None

---

## Path Params vs Body Fields

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, both path and body (Recommended) | Path params bypass Pydantic schema validation. Without Path(ge=1), huge path IDs still hit SQLite. | :heavy_check_mark: |
| Body/schema fields only | Only add Field() constraints. Path params still accept huge ints. | |

**User's choice:** Both path and body
**Notes:** None

---

## Test Verification

| Option | Description | Selected |
|--------|-------------|----------|
| Schemathesis passing is sufficient (Recommended) | Fuzz suite proves bounds work across entire API surface. Unit tests for Pydantic validation would test the framework. | :heavy_check_mark: |
| Add targeted 422 tests | Write tests that POST/GET with out-of-range ints. Belt-and-suspenders. | |
| Both | Schemathesis primary, plus 2-3 targeted regression anchors. | |

**User's choice:** Schemathesis passing is sufficient
**Notes:** None

---

## Query Parameters

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, with sensible defaults (Recommended) | limit: ge=1 le=100, offset: ge=0, page: ge=1. Prevents DoS via absurd values. | :heavy_check_mark: |
| INT64 cap only | Just prevent OverflowError. | |
| Out of scope | Query params aren't causing OverflowError. | |

**User's choice:** Yes, with sensible defaults
**Notes:** None

---

## Error Response Format

| Option | Description | Selected |
|--------|-------------|----------|
| FastAPI default is fine (Recommended) | Standard 422 with field name, error type, message. | :heavy_check_mark: |
| Custom error shape | Wrap in consistent error envelope. | |

**User's choice:** FastAPI default
**Notes:** None

---

## xfail Cleanup

| Option | Description | Selected |
|--------|-------------|----------|
| Leave xfail as-is (Recommended) | Datetime issue out of scope. xfail documents known issue. | :heavy_check_mark: |
| Remove TestAPIWorkflow entirely | Delete auto-discovered stateful test. | |
| Convert to skip | Change from xfail to pytest.skip. | |

**User's choice:** Leave xfail as-is, but create a Linear ticket for the datetime fix
**Notes:** User wants the datetime fix tracked and addressed in a later phase within this project.

---

## Negative Integer Handling (Full Audit)

| Option | Description | Selected |
|--------|-------------|----------|
| Full audit (Recommended) | Audit ALL integer fields for sensible lower bounds. One pass, done right. | :heavy_check_mark: |
| IDs and query params only | Less scope, less risk. | |
| You decide | Claude audits and applies reasonable bounds. | |

**User's choice:** Full audit
**Notes:** None

---

## Fuzz Test Settings Tuning

| Option | Description | Selected |
|--------|-------------|----------|
| Keep max_examples=50 (Recommended) | Solid fuzz baseline. With valid-range inputs, 50 examples test more business logic per run. | :heavy_check_mark: |
| Increase to 100 | More thorough but doubles test time. | |
| You decide | Claude picks based on CI time budget. | |

**User's choice:** Keep max_examples=50
**Notes:** None

---

## Backward Compatibility

| Option | Description | Selected |
|--------|-------------|----------|
| No compat concern (Recommended) | Self-hosted, single-user, co-deployed clients. Rejected values were already causing 500. | :heavy_check_mark: |
| Audit frontend/mobile first | Grep clients for out-of-range values before shipping. | |
| Add deprecation warning header | Return Warning HTTP header for a release cycle. | |

**User's choice:** No backward compatibility concern
**Notes:** None

---

## Claude's Discretion

- Exact domain-specific bounds for each non-ID field
- Order of schema file changes
- Commit grouping strategy
- Specific FastAPI Path()/Query() import patterns

## Deferred Ideas

- Datetime timezone suffix fix — create Linear ticket
- Intelligence/salary endpoint 500 — create Linear ticket
- Increase fuzz max_examples for nightly (Phase 4)
