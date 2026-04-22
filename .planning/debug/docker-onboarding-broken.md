---
status: awaiting_human_verify
trigger: "Docker onboarding broken on first screen — save fails with connection error. Frontend (port 8101) cannot reach backend API (port 8100) in Docker compose."
created: 2026-04-22T00:00:00Z
updated: 2026-04-22T00:02:00Z
---

## Current Focus
<!-- OVERWRITE on each update - reflects NOW -->

hypothesis: confirmed — Vite proxy defaulted to localhost:8100 inside Docker; fixed by setting VITE_API_URL=http://backend:8100 in docker-compose.yml frontend environment
fix_applied: docker-compose.yml — added VITE_API_URL=http://backend:8100 to frontend service environment block
next_action: await human verification that docker compose up → onboarding step 1 now works

## Symptoms
<!-- Written during gathering, then IMMUTABLE -->

expected: docker compose up results in working onboarding flow. First-time user can complete all 6 onboarding steps without errors.
actual: First screen (Step 1/6: "What's your name?") fails immediately after typing a name. Error: "Couldn't save your answer. Check your connection and try again."
errors: "Couldn't save your answer. Check your connection and try again." — frontend error message from a failed API call
reproduction: docker compose up → open localhost:8101/welcome → type name → click next → error appears
started: First real user (Viktor) tried Docker deployment and hit this on first contact

## Eliminated
<!-- APPEND only - prevents re-investigating -->

## Evidence
<!-- APPEND only - facts discovered -->

- timestamp: 2026-04-22T00:01:00Z
  checked: frontend/vite.config.ts proxy configuration
  found: target is `process.env.VITE_API_URL || "http://localhost:8100"` — VITE_API_URL is the escape hatch but was never set in docker-compose.yml
  implication: Inside Docker, localhost:8100 resolves to the frontend container itself (not the backend), so every proxied /api/* request gets a connection refused

- timestamp: 2026-04-22T00:01:00Z
  checked: docker-compose.yml frontend service environment block
  found: Only NODE_ENV=development was set; no VITE_API_URL entry existed
  implication: Confirms the escape hatch was always falling through to the broken default

- timestamp: 2026-04-22T00:01:00Z
  checked: docker-compose.yml backend service name
  found: Backend service is named "backend" — Docker's internal DNS resolves "backend" to the backend container IP
  implication: VITE_API_URL=http://backend:8100 is the correct Docker-network target

- timestamp: 2026-04-22T00:01:00Z
  checked: frontend/src/api/profiles.ts and onboarding.ts
  found: All fetch calls use relative paths (/api/profiles, /api/onboarding) — they rely 100% on the Vite proxy to reach the backend
  implication: No fallback; proxy misconfiguration = total failure for all API calls

## Resolution
<!-- OVERWRITE as understanding evolves -->

root_cause: Vite dev proxy in vite.config.ts defaulted to http://localhost:8100 when VITE_API_URL was unset. Inside Docker, localhost refers to the frontend container itself — not the backend container — so all proxied /api/* requests failed with a connection error before reaching the backend.
fix: Added `VITE_API_URL=http://backend:8100` to the frontend service environment block in docker-compose.yml. Docker's internal DNS resolves the service name "backend" to the backend container, so the proxy now routes correctly.
verification: awaiting human verification
files_changed:
  - docker-compose.yml
