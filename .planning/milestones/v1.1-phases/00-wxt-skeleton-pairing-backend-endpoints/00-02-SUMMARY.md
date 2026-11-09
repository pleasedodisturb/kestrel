---
phase: 00-wxt-skeleton-pairing-backend-endpoints
plan: 02
subsystem: browser-extension
tags: [extension, wxt, mv3, react, service-worker, typescript]
requires:
  - "00-01 backend extension endpoints (POST /api/extension/pair, /capture, /status, /health)"
provides:
  - "extension/ WXT + React 19 MV3 skeleton (buildable, narrow perms, zero broad-host)"
  - "background service worker: sole backend caller + typed chrome.runtime message router"
  - "lib/api/messages.ts contract: ExtMessage, ExtResponse, HealthState, CapturePayload, InstanceInfo"
  - "lib/storage.ts typed chrome.storage.local wrapper with URL guard"
  - "lib/api/client.ts cookie-less bearer backend client"
affects:
  - "00-03 options page (imports lib/api/messages.ts types + lib/storage.ts)"
tech-stack:
  added:
    - "wxt@0.20.27 (build tool)"
    - "@wxt-dev/module-react@1.2.2"
    - "react@19.2.7 / react-dom@19.2.7"
    - "typescript@5.9.3"
    - "vitest@3.2.7 + jsdom + @testing-library/react + @testing-library/jest-dom"
  patterns:
    - "background service worker is the ONLY module that calls fetch (golden rule)"
    - "cookie-less requests (credentials: omit), token in Authorization: Bearer header"
    - "stateless MV3 worker — reads chrome.storage fresh on every message"
key-files:
  created:
    - extension/package.json
    - extension/wxt.config.ts
    - extension/tsconfig.json
    - extension/vitest.config.ts
    - extension/.gitignore
    - extension/entrypoints/popup/index.html
    - extension/entrypoints/popup/main.tsx
    - extension/entrypoints/popup/App.tsx
    - extension/entrypoints/background.ts
    - extension/lib/api/messages.ts
    - extension/lib/api/client.ts
    - extension/lib/storage.ts
    - extension/__tests__/background.test.ts
    - extension/test/imports-stub.ts
    - extension/test/setup.ts
decisions:
  - "Committed package-lock.json for reproducible/pinnable dependency tree (supply-chain)"
  - "Moved lib/api/messages.ts (types-only) into Task 1 commit because the popup App.tsx imports it — keeps each commit type-checking"
  - "vitest aliases WXT's #imports virtual module to a tiny local stub so background.ts unit-tests without the full WXT runtime"
metrics:
  duration: "~25 min"
  completed: "2026-07-21"
  tasks: 2
  files: 15
---

# Phase 0 Plan 02: WXT + React 19 MV3 Extension Skeleton + Background Service Worker Summary

Stood up the standalone `extension/` package — a WXT + React 19 + TS-strict MV3 skeleton whose background service worker owns every backend call, exposes a typed `chrome.runtime` message API (pair / capture / health / status), and builds to a loadable unpacked extension with narrow permissions and zero broad-host access. Foundation only: no content scripts, no capture extraction, no overlay.

## What Was Built

### Task 1 — WXT + React MV3 skeleton (commit 9c5c02e)
- Hand-written config (no interactive scaffolder): `package.json` (kestrel-extension, WXT + React 19 + vitest scripts, `postinstall: wxt prepare`, `compile: tsc --noEmit`), `wxt.config.ts` (MV3 manifest), `tsconfig.json` (extends generated `.wxt/tsconfig.json`, `strict` + `verbatimModuleSyntax`), `vitest.config.ts` (jsdom + jest-dom, `@/` alias, `#imports` stub).
- Manifest: `permissions: ["activeTab", "storage"]` only; `host_permissions: ["http://localhost/*", "http://127.0.0.1/*"]` only; no wildcard/broad host anywhere.
- Minimal React popup that round-trips a HEALTH message to the worker and shows a one-line connection status — no backend request, no pairing UI (that is 00-03).
- `lib/api/messages.ts` type contract.

### Task 2 — Background service worker (commit 213e999)
- `lib/storage.ts`: typed `chrome.storage.local` wrapper. Keys `backendUrl` (default `http://localhost:8100`) and `extensionToken`. URL guard (T-00-10) rejects non-localhost `http://`, requires `https://` for remote hosts.
- `lib/api/client.ts`: the ONLY backend caller. `pair` / `capture` / `status` / `health`, all cookie-less (`credentials: "omit"`, Bearer token in `Authorization` header) wrapped in a 1.5 s `AbortController` timeout that maps network failure/timeout to a distinct outcome so the worker can report `backend-down`.
- `entrypoints/background.ts`: typed `chrome.runtime.onMessage` router. PAIR stores the minted token; CAPTURE requires a stored token before any network call; STATUS proxies `/api/extension/status`; HEALTH computes `connected` / `unpaired` / `backend-down` / `bad-key`. Stateless — no module-level mutable state. No `fetch(` here (delegates to client).
- `__tests__/background.test.ts` (+ `test/` helpers): 11 vitest cases covering token storage, the no-token capture guard, cookie-less bearer capture, all four health states, and the storage URL guard.

## Wire contract (built against 00-01, verified live)
`POST /api/extension/pair` body `{pairing_code}` → `{token, instance:{name:"Kestrel",version}}` | 401; `POST /capture` + `GET /status` require `Authorization: Bearer`; `GET /health` unauth → `{status, database}`. Confirmed against `src/career_os/api/extension.py` + `schemas/extension.py`.

## Supply-chain / `npm audit signatures`
Blocking-human checkpoint was pre-approved by the orchestrator (wxt@0.20.27 and @wxt-dev/module-react@1.2.2 verified as genuine `_aklinker1` / wxt-dev packages). After `npm install`:

```
461 packages have verified registry signatures
79 packages have verified attestations
```

Zero unsigned / failed-verification packages — proceeded as instructed.

Note (out of scope): `npm install` also printed `11 vulnerabilities (1 low, 2 moderate, 5 high, 3 critical)` from the standard CVE `npm audit` (dev-tooling transitive deps, e.g. esbuild dev-server advisory). These are known-CVE advisories, NOT signature/forgery failures, and do not block a dev-only build tool. Logged for later tightening, not fixed here.

## Verification (worktree paths)
| Check | Result |
|-------|--------|
| `npm run build` | PASS — `.output/chrome-mv3/manifest.json` (426 B) produced |
| `npm run compile` (tsc --noEmit) | PASS — clean |
| `npm run test` (vitest) | PASS — 11/11 green |
| `grep -rq all_urls .output/` | none (PASS) |
| `grep -rn all_urls extension/` source | none (PASS) |
| `fetch(` in `entrypoints/background.ts` | none — delegates to client (PASS) |
| `Authorization` in `lib/api/client.ts` | present (PASS) |
| `npm audit signatures` | all verified (PASS) |

Built manifest:
```json
{"manifest_version":3,"name":"Kestrel","permissions":["activeTab","storage"],
 "host_permissions":["http://localhost/*","http://127.0.0.1/*"],
 "background":{"service_worker":"background.js"},
 "action":{"default_title":"Kestrel","default_popup":"popup.html"}}
```

## Deviations from Plan

### Reordering / structural (Rule 3 — blocking issue)
**1. [Rule 3] `lib/api/messages.ts` committed in Task 1, not Task 2.** The Task 1 popup `App.tsx` imports `HealthState`/`ExtResponse`/`HealthResponse` from `lib/api/messages.ts`. To keep each commit type-checking, the types-only contract (zero backend calls) moved into the Task 1 commit. All required exports (`CapturePayload`, `ExtMessage`, `ExtResponse`, `HealthState`, plus `InstanceInfo` and the per-message response interfaces) are present.
**2. [Rule 3] `#imports` stub + vitest alias.** `background.ts` imports `defineBackground` from WXT's `#imports` virtual module, which does not resolve under plain vitest. Added `test/imports-stub.ts` (identity `defineBackground`) and aliased `#imports` to it in `vitest.config.ts` so the worker's router is unit-testable without the WXT runtime. The registered listener callback is not invoked in tests — `handleMessage` is exercised directly.
**3. [Rule 2] Committed `package-lock.json`.** Not in the plan file list, but pinning the resolved dependency tree is a supply-chain/reproducibility requirement for a package introducing new npm deps.
**4. [Rule 3] tsconfig `jsx` + inherited include.** The generated `.wxt/tsconfig.json` does not set `jsx`, and my initial custom `include` excluded `.wxt/wxt.d.ts` (which declares `#imports`). Fixed by adding `"jsx": "react-jsx"` and dropping the `include` override so it inherits WXT's (`../**/*` + `./wxt.d.ts`).

### Wording (build-gate compliance)
**5. [Rule 1] Removed the literal string `all_urls` from the manifest description and `wxt.config.ts` comments.** The privacy blurb originally read "No telemetry, no `<all_urls>`", which put the literal `all_urls` into the built manifest and tripped the `! grep -rq all_urls .output/` gate. Reworded to "No telemetry and no broad host access" / "never a wildcard host".

No authentication gates occurred (all backend contract work was against the already-committed 00-01 endpoints; no live server needed for the build/test verification).

## Known Stubs
None that block this plan's goal. The popup shows a placeholder connection status by design; the pairing UI is deliberately deferred to 00-03. `/capture` wiring to scoring is Phase 1 (backend already returns a stub id).

## For plan 00-03 (options page)
- **Types contract is ready.** Import from `@/lib/api/messages`: `ExtMessage`, `ExtResponse`, `HealthState`, `CapturePayload`, `InstanceInfo`, and the per-message response interfaces (`PairResponse`, `HealthResponse`, `CaptureResponse`, `StatusResponse`). All exported and confirmed compiling.
- **Storage helpers ready.** Import from `@/lib/storage`: `getBackendUrl`, `setBackendUrl` (throws on non-localhost `http://`), `getToken`, `setToken`, `assertValidBackendUrl`.
- **Do NOT call the backend from the options page.** Send messages to the worker: `chrome.runtime.sendMessage({ type: "PAIR", pairingCode })`, `{ type: "HEALTH" }`, `{ type: "STATUS" }`. The worker owns all fetches and token persistence.
- **Health states** returned by `{ type: "HEALTH" }` → `HealthResponse.state`: `connected` | `unpaired` | `backend-down` | `bad-key` — map these to the connected / backend-down / bad-key UX in the options page.
- **PAIR persistence:** the worker calls `setToken` on a successful pair — the options page does NOT need to store the token itself; it just sends `{ type: "PAIR", pairingCode }` and reads the `{ ok, token?, instance?, error? }` response.
- Add the options entrypoint under `extension/entrypoints/options/` (WXT auto-detects it). The `@/` alias and TS-strict posture are already configured.

## Environment note
Node **v26.5.0** is installed; the project targets Node 22. WXT 0.20.27 / Vite 8 / vitest 3 all built, type-checked, and tested cleanly on v26 with no warnings attributable to the version gap. Flagging the mismatch for awareness — no action needed for this plan.

## Self-Check: PASSED
- All 15 created files exist on disk (verified via build + compile + test reading them).
- Commit 9c5c02e (Task 1) and 213e999 (Task 2) present on `G-1389/browser-extension`.
- `.output/chrome-mv3/manifest.json` generated; all verification gates green.
