# Infrastructure

*Part of the [Kestrel roadmap](../../ROADMAP.md).*

## Goal

Keep the codebase healthy so new features ship without breaking existing ones.

## What This Delivers

Kestrel has a full CI/CD pipeline running on GitHub Actions. Every pull request triggers linting, testing, security scanning, and a smoke test. Over 300 tests across backend and frontend catch regressions before code reaches the main branch. Nightly workflows run discovery scans and additional security checks on a schedule.

The release process is automated through release-please, which manages version bumping and changelog generation from conventional commit messages. When a release is tagged, separate workflows publish the Python package to PyPI, the Docker image to GitHub Container Registry, and the npm wrapper package. A release gate checks that required quality criteria are met before a release goes out.

PII scanning runs on every commit to prevent personal data from leaking into the repository. CodeQL performs security analysis. Dependency auditing checks both Python (pip-audit) and JavaScript (npm audit with signature verification) for known vulnerabilities. The OpenSSF Scorecard provides an external measure of the project's security practices.

For developers, the project supports Docker Compose for local development (backend and frontend in separate containers with hot-reload) and a production Docker configuration that serves everything from a single container on port 8100.

## How It Works

The CI pipeline runs in parallel jobs: one for the Python backend (lint, migrate, test, audit, smoke) and one for the React frontend (lint, build, test, audit). SonarCloud analyzes code quality and posts results as PR comments. The pipeline is designed so that a green build means the code is safe to merge.

Alembic database migrations run automatically on application startup, so deploying a new version handles schema changes without manual intervention. A roundtrip migration check in CI verifies that migrations can be applied and rolled back cleanly.

## Current Status

*Shipped in [v0.12.0](../../CHANGELOG.md#0120-2026-04-23)*

The full CI/CD pipeline is active with linting, testing, smoke tests, nightly scans, release automation, and multi-platform publishing. PII scanning, CodeQL, and dependency auditing run on every pull request. Release-please manages versioning and changelogs. Docker images are published to GHCR on release.

## Related Milestones

- **[Scoring Engine](scoring-engine.md)** -- Test suite validates scoring behavior across provider changes
- **[AI Provider System](ai-provider-system.md)** -- CI includes test isolation guard to block real AI HTTP calls
- **[PII Safety Boundary](pii-safety-boundary.md)** -- PII scanning prevents sensitive data from entering the repository

---

*For Contributors*

## Architecture

CI/CD workflows live in `.github/workflows/`:

- `ci.yml` -- Main CI: Python lint (Ruff) + test (pytest with coverage) + Alembic migration roundtrip + API smoke test. Frontend lint (ESLint) + test (Vitest with coverage). Security: pip-audit, npm audit with signature verification, PII leak scan.
- `release-please.yml` -- Automated changelog and version bumping from conventional commits.
- `publish.yml` -- PyPI publishing on release tag. Package name: `kestrel-app`.
- `docker-publish.yml` -- Docker image publishing to GHCR.
- `publish-npm.yml` -- npm package publishing for the wrapper package.
- `codeql.yml` -- CodeQL security scanning.
- `commitlint.yml` -- Conventional commit format enforcement.
- `daily-scan.yml` -- Scheduled discovery sweep.
- `secret-scan.yml` -- Secret leak detection.
- `scorecard.yml` -- OpenSSF Scorecard.
- `workflow-lint.yml` -- GitHub Actions workflow YAML validation.
- `release-checks.yml` -- Pre-release validation (release gate).

Testing infrastructure:

- Backend: pytest (108 test files, ~51,886 lines) with pytest-asyncio, pytest-cov, and pytest-timeout (30s default). In-memory SQLite with foreign key enforcement for test isolation.
- Frontend: Vitest (22 test files, ~5,706 lines) with Testing Library (React + DOM + jest-dom) and jsdom environment.
- Test isolation guard blocks real AI provider HTTP calls in the test suite.

Docker:

- `Dockerfile` -- Multi-stage: `node:22-alpine` for frontend build, `python:3.11-slim` for runtime. Single container serves API + static frontend.
- `docker-compose.yml` -- Dev mode with hot-reload and volume mounts.
- `docker-compose.prod.yml` -- Production mode on port 8100.

## Research & Decisions

Annotated links to research and reference documents:

- [CI/CD Research](../research/cicd-research.md) -- CI/CD research: from tested code to production reality, 4-phase implementation roadmap
- [CI/CD Dev Review](../research/cicd-dev-review.md) -- CI/CD implementation review and developer-focused synthesis of research findings
- [CI/CD Raw Research](../research/cicd-raw-research.md) -- Raw CI/CD research data covering GitHub Actions patterns, deployment strategies, and cost analysis
- [Testing Research](../research/testing-research.md) -- Testing research: strategies, tools, and what level of testing a solo project needs
- [Testing Raw Research](../research/testing-raw-research.md) -- Raw testing research data behind the testing strategy decisions
- [Testing Standards](../reference/TESTING.md) -- Machine-readable testing standards: rules, mocking boundaries, and test structure conventions
- [Testing Strategy](../reference/testing-strategy.md) -- What shipped, what was trimmed, and the rationale for stopping before enterprise-grade coverage
- [Release Pipeline](../reference/release-pipeline.md) -- Release pipeline documentation: commit to release flow, two-tier status system, and workflow descriptions

## BMAD Integration

**PRD Status:** Not started

A PRD would cover CI pipeline stage definitions, test coverage floor targets, release cadence policy, and the criteria for promoting nightly builds to stable.

To start a PRD: `/bmad-create-prd` in Claude Code.
See the [planning hierarchy](inventory.md#how-planning-works) for how PRDs connect to implementation.
