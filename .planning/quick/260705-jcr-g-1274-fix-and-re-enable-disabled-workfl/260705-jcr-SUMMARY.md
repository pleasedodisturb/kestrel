---
phase: quick
plan: 260705-jcr
subsystem: infra
tags: [github-actions, ci, trivy, size-limit, docker, ossf-scorecard]

# Dependency graph
requires: []
provides:
  - scorecard.yml pinned to a resolvable ossf/scorecard-action SHA (v2.4.3)
  - daily-scan.yml cron gated behind DAILY_SCAN_ENABLED repo variable
  - frontend size-limit config + devDeps wired into release-checks.yml
  - Dockerfile runtime stage upgraded to clear 6 fixable Trivy CRITICAL/HIGH CVEs
affects: [ci, release-checks, scorecard, daily-scan]

# Tech tracking
tech-stack:
  added: [size-limit@11.2.0, "@size-limit/file@11.2.0"]
  patterns: []

key-files:
  created: []
  modified:
    - .github/workflows/scorecard.yml
    - .github/workflows/daily-scan.yml
    - .github/workflows/release-checks.yml
    - frontend/package.json
    - frontend/package-lock.json
    - Dockerfile

key-decisions:
  - "Pinned scorecard-action to full SHA 99c09fe975337306107572b4fdf4db224cf8e2f2 with # v2.4.3 comment per OpenSSF Pinned-Dependencies guidance"
  - "daily-scan cron guarded by vars.DAILY_SCAN_ENABLED (default unset/false) rather than deleting the schedule, so workflow_dispatch always works"
  - "size-limit budgets set with headroom (350 kB JS / 15 kB CSS) over current output rather than tight to current size"
  - "Dockerfile: upgrade (not remove) pip/setuptools/wheel to keep pkg_resources available at runtime"

patterns-established: []

requirements-completed: [G-1274]

# Metrics
duration: 8min
completed: 2026-07-05
---

# Phase quick: G-1274 Fix and Re-enable Disabled Workflows Summary

**Pinned scorecard-action to a resolvable SHA, gated daily-scan's cron behind a repo variable, wired size-limit into release-checks, and hardened the Dockerfile runtime stage to clear 6 fixable Trivy CVEs.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-07-05T14:00:10+02:00 (branch base commit)
- **Completed:** 2026-07-05T14:05:57+02:00 (last task commit)
- **Tasks:** 3/3 completed
- **Files modified:** 6

## Accomplishments
- `scorecard.yml` no longer fails in 5s on every run — `ossf/scorecard-action@v2` (unresolvable tag) replaced with the full SHA for v2.4.3
- `daily-scan.yml`'s Mon-Fri cron no longer fires (and fails on 429s/failure-rate) in clones without provider API keys configured — gated behind `vars.DAILY_SCAN_ENABLED`, with manual `workflow_dispatch` unaffected
- `release-checks.yml`'s bundle-size step no longer crashes — `frontend/package.json` now has a `size-limit` config + devDeps, verified passing locally under budget
- `Dockerfile` runtime stage upgraded (`apt-get upgrade`, `pip install -U pip setuptools wheel`) to address libssh2, wheel, and jaraco.context CVEs that Trivy was flagging

## Task Commits

Each task was committed atomically:

1. **Task 1: Pin scorecard-action and guard daily-scan scheduled runs** - `7c89e3d` (fix)
2. **Task 2: Add size-limit config to frontend and simplify the release-checks step** - `b218b5c` (fix)
3. **Task 3: Harden Dockerfile runtime stage against fixable Trivy CVEs** - `efd1d0a` (fix)

_No TDD tasks — config-only changes, no unit-test surface (per plan's stated constraint)._

## Files Created/Modified
- `.github/workflows/scorecard.yml` - Pinned `ossf/scorecard-action` to SHA `99c09fe975337306107572b4fdf4db224cf8e2f2` (`# v2.4.3` comment)
- `.github/workflows/daily-scan.yml` - Added `if: github.event_name == 'workflow_dispatch' || vars.DAILY_SCAN_ENABLED == 'true'` guard on the `daily-scan` job; documented `DAILY_SCAN_ENABLED` in the header comment block
- `.github/workflows/release-checks.yml` - Simplified "Bundle size check" step to `npx size-limit` (removed the conflicting `npm install --no-save` line)
- `frontend/package.json` - Added `size-limit` and `@size-limit/file` (^11.2.0) to devDependencies; added top-level `size-limit` config (350 kB JS / 15 kB CSS)
- `frontend/package-lock.json` - Updated via `npm install --save-dev --legacy-peer-deps size-limit @size-limit/file`
- `Dockerfile` - Added `apt-get upgrade -y` to the runtime-stage apt block; added `pip install --no-cache-dir -U pip setuptools wheel` before the package install

## Decisions Made
- Pin format: full SHA + `# vX.Y.Z` comment (matches existing repo convention for other actions, improves OpenSSF Pinned-Dependencies score) rather than a shorter partial SHA.
- daily-scan: chose a job-level `if:` guard over deleting the `schedule:` trigger entirely, so the cron infrastructure stays intact for users who opt in via the repo variable, while forks/clones don't get failing scheduled runs by default.
- size-limit budgets: set at 350 kB (JS) / 15 kB (CSS) — roughly 1.3x current measured size — to absorb normal growth without needing this ticket revisited on every dependency bump.
- Dockerfile: upgraded rather than removed `setuptools`/`wheel` per plan guidance, since `pkg_resources` (vendored in setuptools) may still be imported by transitive runtime dependencies.

## Deviations from Plan

### Auto-fixed Issues

None — no Rule 1/2/3 auto-fixes were needed. All three tasks matched the plan's exact instructions.

### Verification Environment Limitations (not code deviations)

**1. size-limit reports brotli size, not gzip, as originally assumed**
- **Found during:** Task 2 verification (`npx size-limit`)
- **Detail:** The plan's context stated "@size-limit/file measures gzip by default." The installed `@size-limit/file@11.2.0` actually reports brotli-compressed size by default. This doesn't change the outcome — brotli output is smaller than gzip (224.05 kB vs. the 273.73 kB gzip figure used to size the budget), so the 350 kB / 15 kB budgets still hold with even more headroom than planned. No code change was needed; documenting for accuracy only.
- **Files modified:** None (informational only)

**2. Docker/Trivy verification deferred entirely to CI — local Docker daemon unavailable**
- **Found during:** Task 3 verification (`docker build -t kestrel:ci .`)
- **Issue:** This worktree sandbox has no reachable Docker daemon. `docker info` shows the OrbStack context, but the daemon socket (`~/.orbstack/run/docker.sock`) doesn't exist, and `orb start` times out waiting for the VM to start (no virtualization access in this sandboxed environment). `trivy` was also confirmed not installed (per plan's pre-verified facts).
- **Impact:** Could not run `docker build` or the Trivy scan locally at all — a step beyond what the plan anticipated (the plan only flagged Trivy itself as possibly missing, assuming Docker would be available). The Dockerfile changes were reviewed manually against the plan's exact spec (apt-get upgrade placement, pip -U pip setuptools wheel placement, no .trivyignore, Trivy gate in release-checks.yml unchanged) and match precisely.
- **Resolution:** Deferred to the CI `release-checks.yml` container job, which runs `docker/build-push-action` + `aquasecurity/trivy-action` with the exact gate (`exit-code: "1"`, `severity: CRITICAL,HIGH`, `ignore-unfixed: true`) already in place and unmodified.
- **Files modified:** None (environment limitation, not a code issue)

---

**Total deviations:** 0 code auto-fixes. 2 verification-environment notes (informational, no code impact).
**Impact on plan:** None on scope or correctness. Task 3's Docker/Trivy check is the only plan verification step not run locally; it is deferred to CI per the plan's own stated fallback path, extended to cover Docker itself.

## Issues Encountered
- OrbStack (Docker daemon) unreachable in this sandboxed worktree — see Deviations above. No workaround attempted beyond a single `orb start` (timed out); did not force further attempts to avoid destabilizing the sandbox.

## User Setup Required

None - no external service configuration required. Note for repo maintainer: to actually enable the `daily-scan.yml` scheduled cron after this PR merges, set the `DAILY_SCAN_ENABLED` repository variable (Settings > Variables > Actions) to `"true"`. Leaving it unset keeps the cron dormant while `workflow_dispatch` continues to work.

## Next Phase Readiness
- All three disabled workflows have local-verifiable fixes in place; branch `G-1274/fix-workflows` ready for PR review.
- Post-merge, out-of-scope follow-up (per plan): confirm green runs on GitHub and run `gh workflow enable` for all three workflows — explicitly deferred to after PR review + merge.
- Recommend the PR description note that Docker/Trivy verification for Task 3 was not run locally (sandbox limitation) and should be confirmed via the CI `release-checks` run on the PR itself before merge.

---
*Phase: quick*
*Completed: 2026-07-05*

## Self-Check: PASSED

All 6 claimed modified files exist on disk; all 3 claimed commit hashes (`7c89e3d`, `b218b5c`, `efd1d0a`) verified present in git log.
