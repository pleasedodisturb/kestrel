# Phase 3: Advanced Testing - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-20
**Phase:** 03-advanced-testing
**Areas discussed:** Golden set design, Property test scope, API fuzzing strategy, Test data & fixtures, CI integration, Failure thresholds, Test tagging & markers

---

## Golden Set Design

| Option | Description | Selected |
|--------|-------------|----------|
| Diverse job families | 5-8 families, 3-5 cases per band, aligned with G-301 presets | ✓ |
| Tech-focused only | Start with tech/engineering jobs only | |
| Minimal per-band | 1-2 cases per band across 2-3 families | |

**User's choice:** Diverse job families
**Notes:** Aligns with the 288 job family presets already shipped

---

## Band Definition

| Option | Description | Selected |
|--------|-------------|----------|
| Band ranges (e.g., 70-85) | Tolerance range per case, catches gross regressions without brittleness | ✓ |
| Exact scores | Pin to exact expected values | |
| Relative ordering only | Assert case A > case B, no absolute values | |

**User's choice:** Band ranges
**Notes:** AI scoring naturally drifts between rubric versions

---

## Property Test AI Handling

| Option | Description | Selected |
|--------|-------------|----------|
| MockProvider with fixed responses | Tests pipeline correctness without real AI | ✓ |
| Real provider with seeded inputs | E2E but slow and costly | |
| Recorded responses (VCR-style) | Deterministic but stale | |

**User's choice:** MockProvider with fixed responses

---

## Additional Properties

| Option | Description | Selected |
|--------|-------------|----------|
| Band monotonicity | Score up → band never down | ✓ |
| State machine completeness | All statuses have transitions, none leads to undefined | ✓ |
| Idempotent rescoring | Same input always produces same output | ✓ |

**User's choice:** All three selected

---

## API Fuzzing Auth

| Option | Description | Selected |
|--------|-------------|----------|
| Auth disabled for fuzzing | AUTH_ENABLED=false, pure contract testing | ✓ |
| Static API key | Tests auth + contract together | |
| Mix: both modes | Two runs, one per mode | |

**User's choice:** Auth disabled

---

## Stateful Mode

| Option | Description | Selected |
|--------|-------------|----------|
| Application lifecycle chain | create profile → create app → update status → add contact | ✓ |
| All CRUD chains | Auto-detect all sequences | |
| Stateless only | Individual endpoint fuzzing only | |

**User's choice:** Application lifecycle chain

---

## Fixture Structure

| Option | Description | Selected |
|--------|-------------|----------|
| JSON fixture files | Static JSON in tests/fixtures/, version-control friendly | ✓ |
| Factory functions | Python factories generating data at runtime | |
| Both: JSON for golden, factories for property | Best of both | |

**User's choice:** JSON fixture files

---

## Scoring Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Run actual scoring with MockProvider | Full pipeline E2E, no AI costs | ✓ |
| Pre-computed expected values only | Data comparison, doesn't exercise pipeline | |

**User's choice:** Run actual scoring with MockProvider

---

## CI Integration

| Option | Description | Selected |
|--------|-------------|----------|
| Golden in PR, rest nightly | Golden fast with MockProvider, property+fuzz in Phase 4 nightly | ✓ |
| All in PR | Maximum safety, slower CI | |
| All nightly only | Fastest PRs, regressions caught next day | |

**User's choice:** Golden in PR, rest nightly

---

## Failure Strictness

| Option | Description | Selected |
|--------|-------------|----------|
| Any band-range violation fails | One failure = blocked PR | ✓ |
| Threshold: allow N failures | Tolerant of rubric tuning | |
| Warning only, never block | Defeats purpose | |

**User's choice:** Any band-range violation fails

---

## Test Markers

| Option | Description | Selected |
|--------|-------------|----------|
| Excluded from default, opt-in | Advanced tests only when requested or in CI jobs | ✓ |
| Included in default run | All tests always run | |
| Only golden in default | Middle ground | |

**User's choice:** Excluded from default, opt-in

---

## Claude's Discretion

- Specific Hypothesis strategies
- Schemathesis CLI configuration
- Golden set JSON schema
- Server start/stop for fuzzing
- Exact case counts per family

## Deferred Ideas

None
