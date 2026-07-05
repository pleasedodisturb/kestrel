---
phase: quick-260705-kil
plan: 01
subsystem: infra
tags: [github-actions, dependabot, docker, ci-cd, automerge, security-patches]

# Dependency graph
requires: []
provides:
  - Dependabot auto-merge workflow (patch/minor via GitHub App token)
  - Dependabot docker package-ecosystem coverage
  - Weekly scheduled Docker image rebuild for OS security patches
  - Removal of dead renovate.json config
affects: [ci-cd, release-pipeline, dependency-management]

# Tech tracking
tech-stack:
  added: [dependabot/fetch-metadata@v2.5.0]
  patterns:
    - "GitHub App token minted via actions/create-github-app-token for any workflow step whose result must trigger downstream workflows (merge pushes made with default GITHUB_TOKEN do not re-trigger Actions)"
    - "env: indirection for PR_URL/GH_TOKEN in run: blocks to avoid raw github-context template interpolation (zizmor template-injection rule)"

key-files:
  created:
    - .github/workflows/dependabot-automerge.yml
  modified:
    - .github/dependabot.yml
    - .github/workflows/docker-publish.yml
  deleted:
    - renovate.json

key-decisions:
  - "Keep Dependabot, drop Renovate — Renovate app was never installed on the repo (zero PRs ever produced), so renovate.json was dead config"
  - "Auto-merge only patch/minor Dependabot PRs; major bumps stay manual (no automerge) since they're most likely to carry breaking changes"
  - "No approval-count gating in the automerge workflow — repo has no required reviews configured"
  - "Weekly docker-publish rebuild reuses the existing push trigger's build/push job unchanged — schedule events resolve github.ref to main, so existing metadata-action tag rules (type=ref,event=branch, type=sha) keep working without modification"

patterns-established:
  - "App-token-for-downstream-triggers: any automation that needs its result (merge, push, release) to cascade into other workflows must mint a scoped GitHub App token rather than rely on the default GITHUB_TOKEN"

requirements-completed: [G-1277]

# Metrics
duration: ~20min
completed: 2026-07-05
---

# Phase quick-260705-kil Plan 01: Automate Security Fix Inclusion Summary

**Dependabot patch/minor PRs now auto-merge via a minted GitHub App token, Dependabot covers Docker base-image bumps, and the published image rebuilds weekly to pick up OS security patches — closing the gap where fixes sat in an 8-PR manual-merge backlog.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-07-05T12:54:00Z
- **Tasks:** 2 (both auto)
- **Files modified:** 4 (1 created, 2 modified, 1 deleted)

## Accomplishments
- New `.github/workflows/dependabot-automerge.yml`: gates on `github.actor == 'dependabot[bot]'`, mints an app token (same pattern as `release-please.yml`), reads `dependabot/fetch-metadata` for update type, and runs `gh pr merge --auto --squash` only for `semver-patch`/`semver-minor` updates. Majors stay manual.
- Deleted `renovate.json` — the Renovate GitHub App was never installed, so the config had produced zero PRs since it was added.
- Added a `docker` package-ecosystem entry to `.github/dependabot.yml` (weekly, `deps` commit prefix) so Dependabot now opens PRs for Dockerfile base-image updates, alongside the existing pip/npm/github-actions entries (all left untouched).
- Added a `schedule: cron: '0 5 * * 1'` trigger to `.github/workflows/docker-publish.yml` alongside the existing `push` trigger, so the published image rebuilds every Monday at 05:00 UTC and re-runs the Dockerfile's `apt-get upgrade` layer even in weeks with no app release.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Dependabot auto-merge workflow and delete dead Renovate config** - `9821062` (feat)
2. **Task 2: Add Docker ecosystem to Dependabot and weekly image rebuild schedule** - `2e10efa` (chore)

_Plan-level docs (SUMMARY.md, STATE.md) are intentionally NOT committed per this quick task's constraints — no final metadata commit was made._

## Files Created/Modified
- `.github/workflows/dependabot-automerge.yml` - New workflow: app-token mint, fetch-metadata read, conditional `gh pr merge --auto --squash` for patch/minor only
- `.github/dependabot.yml` - Added `docker` package-ecosystem entry (weekly, `deps` prefix); pip/npm/github-actions entries untouched
- `.github/workflows/docker-publish.yml` - Added `schedule: cron: '0 5 * * 1'` trigger alongside existing `push` trigger; metadata-action tags block untouched
- `renovate.json` - Deleted (dead config, Renovate app never installed)

## Decisions Made
- Used the exact `actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1 # v3.2.0` pin and `RELEASE_APP_ID`/`RELEASE_APP_KEY` secrets already established by `release-please.yml`, rather than introducing a new secret pair, since the same app permissions (contents: write, pull-requests: write) satisfy both use cases.
- Pinned `dependabot/fetch-metadata@21025c705c08248db411dc16f3619e6b5f9ea21a # v2.5.0` per plan spec (no prior usage in repo to cross-reference, so pin was taken as-given and verified as a 40-char SHA).
- No changes to `docker/metadata-action` tag rules in `docker-publish.yml` — confirmed a `schedule` event yields `github.ref` == `main`, so `type=ref,event=branch` and `type=sha` tags continue to resolve correctly; semver tags simply no-op off-tag (expected, harmless).

## Deviations from Plan

None - plan executed exactly as written. Both tasks matched their `<action>` blocks precisely; all automated `<verify>` checks passed on first attempt.

## Issues Encountered

**PyYAML not on system Python.** The plan's verification commands invoke `python3 -c "import yaml, ..."`, but the system `python3` (Homebrew) has no `pyyaml` installed. Used the project's `.venv/bin/python` (which already has PyYAML as a transitive pytest/tooling dependency) to run the identical verification commands instead of installing a new package — no scope change, same checks, same pass/fail semantics. Not logged as a deviation since no plan file was modified and no new dependency was added.

## User Setup Required

None - no external service configuration required. `RELEASE_APP_ID` and `RELEASE_APP_KEY` secrets already exist in the repo (used by `release-please.yml`); the new workflow reuses them.

## Next Phase Readiness
- Both commits are on branch `G-1277/auto-fix-inclusion`, ready for PR review and CI (actionlint + zizmor run automatically via `workflow-lint.yml` on any push touching `.github/workflows/**`).
- No blockers. The 8-PR Dependabot backlog will need one manual merge cycle to establish a clean baseline once this workflow is live; going forward, patch/minor PRs merge unattended.

---
*Phase: quick-260705-kil*
*Completed: 2026-07-05*

## Self-Check: PASSED

- FOUND: `.github/workflows/dependabot-automerge.yml`
- CONFIRMED DELETED: `renovate.json`
- FOUND: `docker` package-ecosystem entry in `.github/dependabot.yml`
- FOUND: `cron:` schedule trigger in `.github/workflows/docker-publish.yml`
- FOUND commit: `9821062` (Task 1)
- FOUND commit: `2e10efa` (Task 2)
