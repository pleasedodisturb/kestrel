---
created: 2026-04-30
source: phase-05-uat
priority: medium
type: verification
---

# Retest Codespace auto-start after nohup fix

The fix in commit `df84ca9` replaced `bash -c '...&...&'` with `nohup` + log redirection in `.devcontainer/devcontainer.json:13`. UAT identified that the original wrapper exited and child processes received SIGHUP.

## Why

Phase 5 UAT Test 1 caught the bug. Fix is applied but not verified — only inspection (JSON valid) and reasoning (nohup is conventional) confirm it works. We need a real fresh Codespace start to confirm both servers persist.

## How to verify

1. Open a fresh Codespace from `G-540/mistral-huggingface-providers` branch
2. Wait 1-2 minutes for `postCreateCommand` (deps install)
3. Without typing anything, check `ps aux | grep -E "uvicorn|vite"` — both should be running
4. Check Ports panel — 8100 and 8101 both forwarded with correct labels
5. Open frontend in browser → should load without 502/connection refused
6. If logs are needed: `cat /tmp/kestrel-backend.log` and `/tmp/kestrel-frontend.log`

## Stop conditions

- DONE when ps aux shows both processes after a fresh Codespace start
- DONE when frontend loads in browser without manual server starts
- If still broken: investigate `nohup` permissions, Codespaces lifecycle quirks, or fall back to a `.vscode/tasks.json` approach

## Linked artifacts

- `.planning/phases/05-contributor-experience/05-HUMAN-UAT.md` (Test 1, Gaps section)
- Commit `df84ca9` — applied fix
- Commit `0f41c17` — UAT recording
