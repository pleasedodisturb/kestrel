---
phase: 00-wxt-skeleton-pairing-backend-endpoints
plan: 03
subsystem: ui
tags: [wxt, react, mv3, chrome-extension, pairing, health-check, vitest]

# Dependency graph
requires:
  - phase: 00-02
    provides: "background worker message API (PAIR/HEALTH/STATUS/CAPTURE), storage helpers (getBackendUrl/setBackendUrl guard/getToken/setToken), typed message contracts"
  - phase: 00-01
    provides: "backend POST /api/extension/pair mint/validate + `kestrel extension pair` CLI code source"
provides:
  - "Extension options/pairing page (WXT React entrypoint): backend-URL field, pairing form, health badge"
  - "useHealth() React hook routing HEALTH through the background worker"
  - "vitest coverage for storage guard + pairing outcomes + all four health states"
affects: [phase-1-capture, extension-popup, autofill]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Options page is a pure presentation/message layer — never fetches the backend; all network via chrome.runtime.sendMessage to the worker"
    - "useHealth() hook owns the HEALTH round-trip; badge re-checks via a pairNonce trigger after a successful pair"
    - "Tests mock chrome.runtime.sendMessage + storage at the module boundary; real assertValidBackendUrl kept to exercise the URL guard"

key-files:
  created:
    - extension/entrypoints/options/index.html
    - extension/entrypoints/options/main.tsx
    - extension/entrypoints/options/App.tsx
    - extension/entrypoints/options/PairingForm.tsx
    - extension/entrypoints/options/HealthBadge.tsx
    - extension/lib/useHealth.ts
    - extension/__tests__/options.test.tsx
  modified: []

key-decisions:
  - "Health hook lives in HealthBadge (driven by useHealth); App bumps a pairNonce prop to force a re-check after pairing, keeping the HEALTH round-trip inside the badge"
  - "Options page delegates ALL token persistence to the worker (setToken is called in the worker on a successful pair); the page never writes the token itself"
  - "Backend-URL guard error surfaced inline by keeping the real assertValidBackendUrl in the setBackendUrl helper (from 00-02)"

patterns-established:
  - "renderOptions() test helper mirrors the frontend render* convention"
  - "it.each over the four HealthState values asserts every badge label"

requirements-completed: [G-1390]

# Metrics
duration: ~15min
completed: 2026-07-21
---

# Phase 0 Plan 03: Extension Options / Pairing Page + Health Badge Summary

**A WXT React options page that stores the backend URL + pairs (minting the token via the background worker) and shows a live connected / unpaired / backend-down / bad-key health badge — completing the Phase 0 first-run onboarding loop with zero direct backend calls.**

## Performance

- **Duration:** ~15 min
- **Tasks:** 2 completed
- **Files created:** 7

## Accomplishments
- Built the `options` WXT entrypoint: backend-URL field (with the non-localhost `http://` guard surfaced inline), a 6-digit pairing form, and a health badge.
- Pairing and health both flow exclusively through `chrome.runtime.sendMessage` — the page never touches the backend (locked golden rule; `grep fetch( extension/entrypoints/options/` is empty).
- `useHealth()` hook maps each `HealthState` to a label + color; the badge re-runs the HEALTH check after a successful pair (via `pairNonce`) so it flips to "Connected to Kestrel".
- Full vitest coverage: both pairing outcomes, all four health states, and the URL guard rejection — 8 new tests, all green (19 total in the extension suite).

## Task Commits

1. **Task 1: Options page — backend URL + pairing form + health badge** — `8869aaf` (feat)
2. **Task 2: Options page tests (storage + pairing + health states)** — `5a3e2a2` (test)

_Task 2's commit also included an accessible `<label>` for the backend-URL input (queried by the tests via `getByLabelText`), added after Task 1._

## Files Created
- `extension/entrypoints/options/index.html` — options entrypoint HTML shell.
- `extension/entrypoints/options/main.tsx` — React root mount (StrictMode).
- `extension/entrypoints/options/App.tsx` — composes URL field + pairing form + health badge; owns the `pairNonce` trigger and URL-save/guard-error state.
- `extension/entrypoints/options/PairingForm.tsx` — 6-digit code entry; sends `{ type: "PAIR", pairingCode }`; shows instance name/version on success, error on failure.
- `extension/entrypoints/options/HealthBadge.tsx` — badge driven by `useHealth()`; maps the four states to labels/colors; re-checks on `pairNonce` bump.
- `extension/lib/useHealth.ts` — hook sending `{ type: "HEALTH" }` on mount + on-demand `refresh()`.
- `extension/__tests__/options.test.tsx` — vitest coverage.

## Verification

- `cd extension && npm run build` → `✔ Built extension` including `.output/chrome-mv3/options.html` (410 B). ✓
- `cd extension && npm run compile` (`tsc --noEmit`) → clean, no type errors. ✓
- `cd extension && npm run test` → **19 passed (2 files)** — 11 background + 8 options. ✓
- `grep -rn "fetch(" extension/entrypoints/options/` → empty (page never calls the backend directly). ✓
- `grep -rn "all_urls" extension/` → empty. ✓

## Deviations from Plan

None — plan executed as written. The plan's `<verify>` blocks hardcode `/Users/pleasedodisturb/Projects/apps/kestrel/extension`; commands were run against the worktree path `/Users/pleasedodisturb/.claude/worktrees/kestrel/G-1389-browser-extension/extension` as instructed. One minor, in-scope addition: an accessible `<label>` for the backend-URL input (needed for `getByLabelText` and better a11y).

## ROADMAP Phase 0 Success Criteria — end-to-end status

1. `npm run build` → loadable MV3 unpacked extension, zero `<all_urls>` — **met** (00-02 skeleton + this plan's options page; build clean, `all_urls` grep empty).
2. Options/pairing page stores URL + token in `chrome.storage`; health check shows connected / backend-down / bad-key — **met** (this plan: URL via `setBackendUrl`, token minted+stored by the worker on pair, badge shows all four states).
3. All backend calls via the background service worker — **met** (options page has no `fetch`; PAIR/HEALTH/STATUS/CAPTURE all go through `chrome.runtime.sendMessage`).
4. `POST /api/extension/pair` mints/validates, `/capture` stub returns 200 + id, CORS regex credential-less, tested — **met** (00-01, `pytest -k extension`).
5. No default telemetry; `grep -r all_urls extension/` empty; `pytest -k extension` + `cd extension && npm run test` green — **met** (no telemetry anywhere; grep empty; extension vitest 19/19 green).

## Known Stubs

None introduced by this plan. (The backend `/api/extension/capture` remains a Phase-0 stub by design — owned by 00-01, wired to `score_job` in Phase 1.)

## Self-Check: PASSED
