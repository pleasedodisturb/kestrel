---
title: "Testing Strategy — What We Built and Why We Stopped"
description: "The full testing infrastructure for Kestrel: what shipped, what was trimmed, and the rationale behind both decisions"
---

# Testing Strategy

## Overview

Kestrel's test infrastructure was built across a 6-phase milestone (Test Infrastructure Maturity, G-305). Phases 1 through 3.3 shipped. Phases 3.2, 4, 4.1, and 5 were trimmed after an honest assessment of what a solo self-hosted project actually needs.

This document captures the full picture: what was built, how it works together, and why we deliberately stopped before reaching "enterprise-grade."

## What Shipped

### Phase 1: CI Optimization (PR #233, #234)

**What it does:** Makes CI fast and targeted so tests aren't a bottleneck.

- **Pytest markers** — Auto-classifies tests as `unit` or `integration` via conftest.py hooks. Run `pytest -m unit` for fast feedback, `pytest -m integration` for full validation.
- **Path filtering** — PRs that only change frontend files skip the backend test job entirely (and vice versa). Saves ~2 minutes per docs-only PR.
- **Venv caching** — CI caches the Python virtualenv keyed on `pyproject.toml` hash. No `pip install` on cache hit.
- **JUnit XML + PR comments** — Test results posted directly on the PR as a GitHub comment. No clicking into logs.

### Phase 2: Agent-Aware Enforcement (PR #255)

**What it does:** Mechanically prevents weak tests from being committed — by humans or AI agents.

- **TESTING.md** — Dual-audience test standards doc. Humans read the guidelines, agents follow the rules.
- **Pre-commit hook** (`check-trivial-assertions.py`) — Blocks commits containing `assert True`, `assert False`, or `assert result is not None` as the sole assertion. These pass every test but prove nothing.
- **Claude Code Stop hook** (`check-test-assertions.py`) — Enforces minimum 2 assertions per test function. Catches tests that only check "it didn't crash" without verifying the result.
- **diff-cover CI gate** — PRs must have ≥80% coverage on changed lines. You can't add code without testing it.
- **CLAUDE.md testing rules** — Agent-enforceable rules that Claude Code reads before writing tests. Covers marker requirements, mocking boundaries, assertion quality.

**Why this matters for AI-assisted development:** AI writes code that looks perfectly reasonable and is subtly wrong. It compiles, the happy path works, but edge cases fail silently. These enforcement gates ensure AI-written tests actually verify behavior, not just existence.

### Phase 3: Advanced Testing (PR #256)

**What it does:** Catches bugs that unit tests structurally cannot find.

- **Golden set regression tests** — 6 job families (TPM, finance, design, healthcare, legal, product) with 20 hand-labeled jobs each. Every scoring change is checked against known-good bands. If a "dream match" suddenly scores as mediocre, the test fails.
- **Hypothesis property-based tests** — Proves scoring output is always 0-100 and deterministic (same input → same output). Uses random inputs to find edge cases humans wouldn't think of.
- **RuleBasedStateMachine tests** — Exercises application state transitions (discovered → applied → interviewing → etc.) with random sequences. Proves you can't reach an invalid state regardless of the order of operations.
- **Schemathesis API fuzzing** — Generates random payloads conforming to the OpenAPI spec for every endpoint. Asserts zero 500 errors on valid-schema inputs. Found 4 real bugs during Phase 3.1.

### Phase 3.1: Input Validation Hardening (PR #251)

**What it does:** Closes the gap between "valid per OpenAPI" and "safe for SQLite."

- **INT64/INT32 bounds** — Every integer field in every Pydantic schema and every API query/path parameter now has explicit `ge=`/`le=` constraints. Schemathesis can't generate overflow values that crash SQLite.
- **Hard-failure fuzz mode** — Fuzz tests use `assert response.status_code < 500` instead of `warnings.warn`. No silent failures.
- **4 bugs found and fixed** — ASGI transport overflow, pushover missing profile check, ghost threshold timedelta overflow, ApplicationUpdate type guard. All discovered by fuzzing, not manual testing.

### Phase 3.3: Datetime RFC 3339 Compliance (PR #258)

**What it does:** Ensures all API datetime responses include timezone suffixes.

- **`_ensure_utc` validators** — Added to 7 schema files that were missing UTC enforcement. Naive datetimes from SQLite get UTC attached before JSON serialization.
- **96 total `_ensure_utc` occurrences** across all schema files — complete coverage.

## What Was Trimmed (and Why)

### Phase 3.2: Trigger-Based Testing Rules — TRIMMED

**What it would have done:** CLAUDE.md rules like "when you add a new endpoint, also add a fuzz test" and "when you add a Pydantic int field, also add INT64 bounds."

**Why we cut it:** Phase 2's enforcement hooks already cover the core need (no weak assertions, coverage on changed lines). Adding rules-about-rules has diminishing returns. The INT64 bounds and fuzz survival requirements are better enforced by reviewing PRs than by maintaining a growing list of trigger conditions that need updating every time the codebase evolves.

### Phase 4: Scheduled Deep Testing — TRIMMED

**What it would have done:** Nightly CI running full test suite + fuzzing. Weekly CI running Bandit SAST, OWASP ZAP, mutation testing with mutmut. Gremlins.js monkey testing. Playwright visual regression.

**Why we cut it:** This is enterprise-grade QA for a solo self-hosted project. The cost isn't the $0 tooling — it's the maintenance burden:
- Mutation testing generates hundreds of "survived mutants" that need triaging. Most are in dead code paths or semantically equivalent. The signal-to-noise ratio is terrible for a solo maintainer.
- OWASP ZAP scans produce false positives that need suppression lists maintained.
- Visual regression screenshots break on every intentional UI change and need manual baseline updates.
- Nightly/weekly pipelines that nobody monitors are just CI minutes burned for inbox notifications nobody reads.

The PR-level checks (phases 1-3) catch the bugs that matter. Scheduled pipelines would catch theoretical bugs at the cost of real maintenance time.

### Phase 4.1: Test Data Factories — TRIMMED

**What it would have done:** Replace manual `dict(name="test", ...)` construction with `factory_boy` declarative factories.

**Why we cut it:** It's a refactor, not a risk mitigation. Manual dict construction works at ~1500 tests. The pain point doesn't exist yet. Revisit when test data setup becomes a measurable bottleneck (>30% of test code is data construction).

### Phase 5: Documentation Publication — TRIMMED → Phase 3.4

**What it would have done:** Publish the testing methodology as a research paper. Create a cross-project playbook for extracting and reusing the CI/testing patterns.

**Why we cut it:** Writing about testing instead of building features. The methodology is documented here. If a future project needs it, this doc and the actual configs are the playbook.

## The Testing Pyramid Today

```
                    ┌──────────────┐
                    │  Fuzz Tests  │  140 endpoints × 50 examples
                    │  (Phase 3+)  │  Schemathesis + hard assertions
                    ├──────────────┤
                    │   Property   │  Scoring invariants, state machine
                    │  (Phase 3)   │  Hypothesis random inputs
                    ├──────────────┤
                    │  Golden Set  │  6 job families × 20 jobs
                    │  (Phase 3)   │  Band drift detection
                ┌───┴──────────────┴───┐
                │   Integration Tests  │  API routes, DB operations
                │    (existing)        │  Full request/response cycles
            ┌───┴──────────────────────┴───┐
            │       Unit Tests             │  3000+ individual checks
            │       (existing)             │  Functions, components, utils
        ┌───┴──────────────────────────────┴───┐
        │         Enforcement Layer            │  Pre-commit hooks, Stop hooks
        │         (Phase 2)                    │  Blocks weak tests at commit time
    ┌───┴──────────────────────────────────────┴───┐
    │              CI Infrastructure               │  Path filtering, caching, PR comments
    │              (Phase 1)                        │  diff-cover gate (80% on changed lines)
    └──────────────────────────────────────────────┘
```

## The Numbers

| Metric | Count |
|--------|-------|
| Backend test functions | 3,000+ |
| Frontend test files | 22 |
| Golden set job profiles | 6 career domains, 120 labeled jobs |
| Fuzz-tested endpoints | 140 |
| Property-based test functions | 8 |
| Pre-commit enforcement hooks | 2 |
| CI checks per PR | 8+ parallel jobs |
| Time to full CI pass | ~3-4 minutes |
| Phases shipped | 6 (1, 2, 3, 3.1, 3.3, 3.4) |
| Phases trimmed | 4 (3.2, 4, 4.1, 5) |
| Monthly cost | $0 |

## Tools Used

All open source, all free:

| Tool | Purpose | Phase |
|------|---------|-------|
| pytest | Backend testing | All |
| Vitest | Frontend testing | 1 |
| Ruff | Python lint + format | All |
| Hypothesis | Property-based testing | 3 |
| Schemathesis | API fuzz testing | 3, 3.1 |
| diff-cover | Coverage on changed lines | 2 |
| GitHub Actions | CI/CD | 1 |
| SonarCloud | Static analysis | Existing |

## Decision Philosophy

We didn't chase coverage percentages or testing buzzwords. Each phase was evaluated by: **what's the costliest bug this catches, and is the maintenance cost worth it?**

- Phases 1-2 (CI + enforcement): Low maintenance, high value. Set up once, prevents classes of mistakes forever.
- Phase 3 (golden set, property, fuzz): Medium maintenance (fixtures need occasional recalibration), high value for scoring correctness and API stability.
- Phase 3.1 (INT64 bounds): One-time setup, prevents an entire class of overflow bugs permanently.
- Phase 3.3 (datetime): One-time fix, ensures API contract compliance.
- Phases 4-5 (nightly, mutation, publication): High ongoing maintenance, marginal incremental value over what's already in place.

The line was drawn where the marginal cost of maintaining the next tool exceeded the marginal benefit of the bugs it would catch. For a solo self-hosted project, that line is after Phase 3.3.
