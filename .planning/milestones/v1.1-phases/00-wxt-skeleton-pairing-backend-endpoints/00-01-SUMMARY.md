---
phase: 00-wxt-skeleton-pairing-backend-endpoints
plan: 01
subsystem: api
tags: [fastapi, hmac, cors, auth, browser-extension, typer, pydantic]

# Dependency graph
requires: []
provides:
  - "POST /api/extension/pair — validates a time-windowed pairing code and mints a dedicated stateless HMAC token"
  - "POST /api/extension/capture — STUB accepting a normalized job payload, returns job_id + scored:false (no scoring, no DB write)"
  - "GET /api/extension/status — token-gated instance identity check"
  - "services.extension_pairing — pairing-code + token mint/verify with auto-persisted secret"
  - "Auth-middleware bypass (_PUBLIC_PREFIXES) + additive chrome-extension CORS regex"
  - "kestrel extension pair CLI surfacing the current pairing code"
affects: [00-02-extension-skeleton, 00-03-extension-pairing-ui, phase-1-capture-scoring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Dedicated stateless HMAC token space, separate from AUTH_API_KEY, secret persisted to {data_dir}/.extension_secret"
    - "Prefix-based middleware bypass with per-route token dependency governing the bypassed routes"
    - "Additive allow_origin_regex on CORSMiddleware (never widens the credentialed-wildcard allow_origins list)"

key-files:
  created:
    - src/career_os/services/extension_pairing.py
    - src/career_os/api/extension.py
    - src/career_os/schemas/extension.py
    - src/career_os/cli/extension.py
    - tests/test_extension_api.py
  modified:
    - src/career_os/config.py
    - src/career_os/middleware.py
    - src/career_os/main.py
    - src/career_os/cli/main.py

key-decisions:
  - "Bootstrap via a 6-digit, secret-derived, time-windowed pairing code (works regardless of AUTH_ENABLED); mint a distinct stateless HMAC token — no DB table, no Alembic migration"
  - "Secret auto-generated once and persisted 0600 so minted tokens survive a backend restart"
  - "Surface brand name 'Kestrel' (not internal 'Career OS') in pair/status responses; never echo AUTH_API_KEY or the token secret"
  - "CORS regex ADDS concrete chrome-extension:// origins; existing frontend allow_origins/credentials untouched"

patterns-established:
  - "Extension token verification is timing-safe (hmac.compare_digest) and rejects malformed/tampered/empty input"
  - "capture is a scoring-free stub; the scoring service is never imported (structural test guard)"

requirements-completed: [G-1390]

# Metrics
duration: ~35min
completed: 2026-07-21
---

# Phase 0 Plan 01: Backend Extension Endpoints Summary

**Dedicated stateless-HMAC pairing/token auth (`/pair` mint, `/capture` stub, `/status`), an auth-middleware bypass with per-route token enforcement, an additive chrome-extension CORS regex, and a `kestrel extension pair` CLI — all with zero scoring/product logic.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-07-21 (worktree venv bootstrap + 3 TDD tasks)
- **Completed:** 2026-07-21
- **Tasks:** 3
- **Files modified:** 9 (5 created, 4 modified)

## Accomplishments
- Stateless HMAC pairing service: 6-digit time-windowed code (current + previous window accepted), separate token space, secret auto-generated and persisted to `{data_dir}/.extension_secret` (0600) so tokens survive restarts.
- Three contract-exact routes: `POST /pair` (code-gated, mints token), `POST /capture` (token-gated STUB — uuid4 job_id, `scored:false`, no DB, no scoring import), `GET /status` (token-gated instance info).
- Middleware bypass (`_PUBLIC_PREFIXES = ("/api/extension/",)`) that skips ONLY the global AUTH_API_KEY check; capture/status stay gated by the per-route extension token, verified with AUTH_ENABLED=true.
- Additive `allow_origin_regex` (`^chrome-extension://[a-p]{32}$`) on the existing CORSMiddleware — the flagged credentialed-wildcard frontend CORS is not widened.
- `kestrel extension pair` CLI printing the current pairing code in a Rich panel.
- 23 tests (pairing/token unit, routes, bypass, CORS preflight, no-score guard, CLI) all green.

## Task Commits

Each task was committed atomically (one signed `feat(G-1390)` commit per task, per orchestrator instruction; TDD tests written alongside implementation):

1. **Task 1: Pairing + token service (stateless HMAC) + config + unit tests** — `63fbc21` (feat)
2. **Task 2: Router (pair/capture-stub/status) + middleware bypass + CORS + wiring** — `0a90ff9` (feat)
3. **Task 3: `kestrel extension pair` CLI** — `bfa7df2` (feat)

## Files Created/Modified
- `src/career_os/services/extension_pairing.py` — pairing-code + token mint/verify, secret persistence
- `src/career_os/api/extension.py` — `/api/extension` router + `require_extension_token` dependency
- `src/career_os/schemas/extension.py` — Pydantic v2 models for the wire contract
- `src/career_os/cli/extension.py` — `extension pair` Typer command
- `tests/test_extension_api.py` — TestExtensionPairing / TestExtensionRoutes / TestExtensionCli
- `src/career_os/config.py` — `extension_token_secret`, `extension_pairing_window_seconds`, `extension_cors_regex`
- `src/career_os/middleware.py` — `_PUBLIC_PREFIXES` bypass for `/api/extension/`
- `src/career_os/main.py` — include extension router + add `allow_origin_regex`
- `src/career_os/cli/main.py` — register `extension_app`

## Decisions Made
- Followed the plan's `<design_decision>` exactly: CLI/instance-surfaced short-lived pairing code + distinct stateless HMAC token; no token table / no migration.
- Read `EXTENSION_TOKEN_SECRET` directly from `os.environ` (in addition to the settings field) so tests can monkeypatch it deterministically after the settings singleton is constructed; added a `reset_secret_cache()` test helper.

## Deviations from Plan

None — plan executed as written. Two minor, in-scope implementation choices worth noting (not deviations):
- Reworded the capture module's docstring/comments to avoid the literal token `score_job`, because the plan's structural guard is a substring check (`"score_job" not in extension.py`). The scoring service is still referenced by description.
- Added `reset_secret_cache()` and read env directly (see Decisions) for test determinism.

## Issues Encountered
- Pre-commit ruff-format reflowed two long lines in the test file on the first Task 2 commit attempt, aborting it. Re-ran `ruff format`, re-staged, and re-committed cleanly. Subsequent tasks were `ruff format`-ed before committing to avoid a repeat.
- FastAPI 0.139 / Starlette 1.3 does not surface the mounted route `path` via `app.routes` enumeration in this environment, so a `path`-based route count reads 0 — but the routes are fully reachable (TestClient `POST /api/extension/pair` → 200). Wiring is correct; only the introspection shortcut was misleading.

## Verification
- `.venv/bin/pytest tests/test_extension_api.py -q` → **23 passed**
- Broader `.venv/bin/pytest -k "extension or middleware or auth or cors"` → **72 passed, 5 skipped** (no regressions to existing auth/CORS tests)
- `.venv/bin/ruff check` on all touched source + test files → clean
- `grep -rn score_job src/career_os/api/extension.py` → empty
- No new file under `src/career_os/_alembic/versions/`
- `kestrel extension pair` prints a 6-digit code that `verify_pairing_code` accepts

## User Setup Required
None for this plan. Optional: set `EXTENSION_TOKEN_SECRET` in `.env` to pin the token secret across machines; otherwise it is auto-generated at `{data_dir}/.extension_secret` on first use.

## Next Phase Readiness
- The wire contract is live and tested; 00-02 (WXT extension skeleton) can build its background service worker against `POST /api/extension/pair` → `{token, instance}`, then send `Authorization: Bearer <token>` to `/capture` and `/status`.
- Extension IDs must match `^chrome-extension://[a-p]{32}$` for CORS to allow the origin (standard Chrome unpacked/store IDs qualify).
- Phase 1 must wire `/capture` to the scoring service (currently a stub returning `scored:false`); the structural no-score guard test in `tests/test_extension_api.py` will need updating when that happens.
- Token revocation in Phase 0 = rotate `EXTENSION_TOKEN_SECRET` (or delete `.extension_secret`). A persisted per-device revocable token store remains a clean later-phase upgrade.

## Self-Check: PASSED

All 5 created source/test files exist on disk; all 3 task commits (`63fbc21`, `0a90ff9`, `bfa7df2`) are present in git history.

---
*Phase: 00-wxt-skeleton-pairing-backend-endpoints*
*Completed: 2026-07-21*
