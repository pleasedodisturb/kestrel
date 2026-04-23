# Session: CI Failure Sweep
**Date:** 2026-04-23
**Branch:** Multiple worktree branches, all merged to main
**Tickets:** G-495, G-496, G-497, G-498, G-499

## What was done
- Audited last 15 PRs for CI failures — identified 38 failing tests across 6 root causes
- Created 5 Linear tickets (G-495 through G-499) via direct GraphQL (linearis CLI broken)
- Launched 5 parallel worktree agents to fix all issues simultaneously
- Reviewed all 5 PRs (4 PASS, 1 BLOCK — fixed the BLOCK finding)
- Fixed pre-existing lint blocker on main (unformatted test_ai_isolation_guard.py from PR #310)
- Fixed xAI privacy warning tests (caplog vs mock, Python 3.11 CI incompatibility)
- Merged all 6 PRs: #317, #318, #319, #320, #321, #322
- Closed all 5 Linear tickets

## Key fixes
- **G-495 (22 failures):** DiscoveryWarning schema mismatch in prod code + broken scraper mocks + CLI banner on stdout
- **G-496 (4 failures):** Wired update_current_span from observability into cache.py and pii_masking.py
- **G-497 (3 failures):** Implemented _build_fallback_chain() in factory.py (FallbackProvider existed but wasn't wired)
- **G-498 (2 failures):** Updated X-Title assertion and batch prompt assertion to match current code
- **G-499 (2+2 failures):** Fixed doc paths for reorganized docs/, xAI caplog replaced with mock

## Production bugs found
- discovery.py prefilter/batch warnings used wrong fields — would crash at runtime
- CLI onboarding banner printed to stdout, breaking --output json

## Decisions made
- Use mock instead of caplog for logger assertions (cross-Python-version reliability)
- Implement missing features (observability spans, fallback chain) rather than deleting tests
- Added rule to global CLAUDE.md: paste-friendly commands with semicolons and line continuations
- Updated worktree rule: ALL work must use worktrees, not just feature branches

## Open items
- linearis CLI broken (Fetch failed) — using linear-cli.sh as workaround
- gh CLI intermittent TLS errors — resolved by using REST API fallback

## Commits (all squash-merged to main)
- `fix(G-412): format test_ai_isolation_guard.py for ruff` (#322)
- `fix(G-495): fix discovery test mock/schema breakage` (#317)
- `fix(G-496): wire observability spans into cache and PII masking layers` (#318)
- `fix(G-497): add _build_fallback_chain to factory` (#319)
- `fix(G-498): fix stale test assertions for X-Title and batch payload` (#320)
- `fix(G-499): fix doc link tests + xAI privacy warning mock` (#321)
