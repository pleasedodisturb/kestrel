# Release Pipeline

How Kestrel gets from code to release. Every step is automated.

## Overview

```
commit → CI (lint/test) → smoke tests → release-please PR → release gate → auto-merge → publish
```

## Tiers

Kestrel uses a two-tier status system. The distinction matters: nightly can be broken (it's work in progress), but a published release must always work.

| Tier | Badge | Broken = | Response |
|------|-------|----------|----------|
| Nightly | `nightly: passing/failing` | Acceptable | Informational. If red >48h, a stability ticket is created. |
| Release | `release: passing/failing` | Unacceptable | Auto-creates GitHub Issue, alerts maintainer. |

## Workflows

### CI (`ci.yml`)

Runs on every push to `main` and every PR.

- **Backend:** ruff lint, pytest (3200+ tests), pip-audit, PII scan
- **Frontend:** eslint, vitest, npm audit, signature verification
- **Actionlint:** validates all workflow YAML files

Backend is currently advisory (pre-existing failures). Frontend and actionlint are hard gates.

### Smoke Tests (`smoke.yml`)

Runs on PRs that touch backend, frontend, Docker, or setup files. Four parallel jobs:

| Job | What it proves |
|-----|---------------|
| `docker-prod` | Production Docker image builds, starts, `/health` returns 200, `/api/profiles` returns JSON |
| `docker-dev` | Dev compose starts both containers, Vite proxy on :8101 reaches backend on :8100 |
| `pypi-wheel` | Wheel builds, installs in clean venv, uvicorn starts, `/health` returns 200 |
| `setup-script` | `bash setup.sh --dry-run` exits 0 (Docker installed, ports free, disk OK) |

These catch what unit tests miss: the product actually starts and serves requests through real install paths.

### Nightly (`nightly.yml`)

Runs daily at 2am UTC. Calls the full smoke test suite via `workflow_call`. Shows current health of `main`. Not a merge gate.

### Release Verification (`release-verify.yml`)

Runs daily at 6am UTC and on every new release. Checks out the latest tagged release and runs the production Docker smoke test against it. If the released version is broken:

1. Creates a GitHub Issue labeled `bug,release-broken,priority:urgent`
2. If an issue already exists, appends a comment with the latest failure

### Release Gate (`release-gate.yml`)

Evaluates release-please PRs against 5 conditions. All must pass for auto-merge:

1. **CI + smoke tests pass** — all required checks green
2. **No blocker issues** — no open issues labeled `priority:urgent` or `release-broken`
3. **Qualifying commits** — at least one `feat:` or `fix:` commit (skips chore-only releases)
4. **Cool-down period** — PR has been open for at least 1 hour
5. **No release-broken issues** — previous release isn't known-broken

**When all pass:** auto-merges with a comment listing all conditions.

**When checks fail:** closes the PR with explanation, links to failed run. Release-please recreates the PR on the next qualifying push.

**When blocked:** comments that blocker issues are preventing release.

### Release Please (`release-please.yml`)

Creates version bump PRs automatically from conventional commits. Generates changelogs. On merge, publishes to PyPI and creates a GitHub Release.

## Bug Sync

### GitHub → Linear (`bug-sync.yml`)

When a GitHub Issue is opened with the `bug` label:
- Creates a Linear ticket (team G) with the issue content
- Maps GitHub priority labels to Linear priority levels
- Adds `synced-to-linear` label to prevent duplicate syncs
- Comments on the GitHub Issue with the Linear ticket link

### @claude Comment Handler (`claude-comment.yml`)

When a comment mentions `@claude` in any issue or PR:
- `@claude bug: ...` → creates a Linear ticket (priority: high)
- `@claude todo: ...` → creates a Linear ticket (backlog)
- `@claude question: ...` → responds with docs links
- `@claude review` → flags for maintainer review

Requires `LINEAR_API_KEY` and `OPENROUTER_API_KEY` as GitHub Actions secrets.

## Badges

The README displays at-a-glance status:

```
[build] [smoke tests] [nightly] [release] [pypi] [open bugs] [license]
```

## Secrets Required

| Secret | Used by | Source |
|--------|---------|--------|
| `LINEAR_API_KEY` | bug-sync, claude-comment, release-gate | Linear API settings |
| `OPENROUTER_API_KEY` | claude-comment (future AI classification) | OpenRouter dashboard |
| `SONAR_TOKEN` | CI (SonarCloud analysis) | SonarCloud settings |
| `RELEASE_APP_ID` | release-please | GitHub App settings |
| `RELEASE_APP_KEY` | release-please | GitHub App settings |

## Install Paths

Five documented install paths, all tested by smoke tests:

| Path | Command | Smoke tested |
|------|---------|-------------|
| Setup script | `bash setup.sh` | `setup-script` job |
| Dev Docker | `docker compose up --build` | `docker-dev` job |
| Prod Docker | `docker compose -f docker-compose.prod.yml up --build` | `docker-prod` job |
| PyPI | `pip install kestrel-app` | `pypi-wheel` job |
| Local dev | `pip install -e ".[dev]" && npm run dev` | Covered by CI |

## History

This pipeline was built in response to G-488 (2026-04-22), where a real user hit 100% failure on first contact — all Docker install paths were broken, and 3200 passing tests didn't catch it. The smoke tests, release gate, and two-tier status system were designed to prevent this class of failure from recurring.
