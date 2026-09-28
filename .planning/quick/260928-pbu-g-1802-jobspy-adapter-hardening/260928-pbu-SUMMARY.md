---
phase: quick
plan: 260928-pbu
subsystem: discovery-scraping
tags: [jobspy, discovery, tools, hardening, G-1802]
requirements: [G-1802]
dependency-graph:
  requires:
    - src/career_os/discovery/adapters.py (JobSpyAdapter, pre-existing)
    - src/career_os/services/discovery.py (_scrape_all_adapters, pre-existing)
    - tools/scraper.py (scrape_all/main, pre-existing)
    - tools/scrape_resilient.py (scrape_with_browser/scrape_jobspy, pre-existing)
    - tools/source_registry.py (module, pre-existing)
  provides:
    - JobSpyAdapter.SITES = ("indeed",) with per-site asyncio.wait_for calls
    - Settings.jobspy_timeout_seconds (JOBSPY_TIMEOUT_SECONDS)
    - tools/scraper.py UNSUPPORTED_SITES + validate_sites
    - tools/source_registry.BROWSER_DISABLED_HOSTS + browser_disabled_reason
  affects:
    - discovery sweep resilience (in-app scheduler)
    - tools/scrape_resilient.py Indeed browser fallback and jobspy site validation
tech-stack:
  added: []
  patterns:
    - "Per-board scrape_jobs calls with asyncio.wait_for timeout, isolated failure capture"
    - "Reason-recording denylist (source_registry.BROWSER_DISABLED_HOSTS) instead of a bare boolean block"
key-files:
  created:
    - tests/test_jobspy_adapter.py
    - tests/test_specific_hunt.py
    - tests/test_source_registry.py
  modified:
    - src/career_os/discovery/adapters.py
    - src/career_os/config.py
    - .env.example
    - tools/scraper.py
    - tools/specific_hunt.py
    - tools/README.md
    - tools/scrape_resilient.py
    - tools/source_registry.py
    - tests/test_scraper.py
    - tests/test_scrape_resilient.py
decisions:
  - "JobSpyAdapter.SITES is a class attribute (not a constructor param) — ADAPTER_REGISTRY builds adapters with cls(), tests monkeypatch the class attribute."
  - "Partial per-site failures are logged only, not added to run.warnings; an all-sites-failed scrape raises RuntimeError which _scrape_all_adapters does put into run.warnings. Wiring partial failures into run.warnings would require editing services/discovery.py, which the ticket's stop condition forbids."
  - "tools/scraper.py DEFAULT_SITES drops Glassdoor too (not just google) — verified same silent-zero failure mode; still accepted when requested explicitly."
  - "specific_hunt.py: documented the blank-LinkedIn-description behavior (AC6 option B) instead of flipping on linkedin_fetch_description, to avoid the extra guest-request/429 risk."
  - "AC5: no manual CHANGELOG.md edit — release-please has no Unreleased-section precedent in this repo's history; the changelog line comes from the fix(G-1802) squash-merge PR title. See 'AC5 / CHANGELOG' section below for the PR title the orchestrator should use."
metrics:
  duration: "~50 minutes"
  completed: "2026-09-28"
actuals:
  tokens: 10138
  tasks: 3
  commits: 3
status: complete
---

# G-1802: JobSpy Adapter Hardening Summary

Hardened the in-app python-jobspy integration (`JobSpyAdapter`) and the three standalone `tools/` scripts that also call python-jobspy, against three verified-live production failure modes: Glassdoor/Google silently returning zero rows, one board's failure wiping every other board's rows in the same sweep, and an unbounded executor call that could stall the discovery scheduler.

## Execution environment note

This agent ran in worktree branch `worktree-agent-ab424cad4339b58ca`, forked from `main` at `0cde483` — one commit *behind* the sibling branch `G-1802/jobspy-hardening` (`b1880f9`, the commit that added `260928-pbu-PLAN.md`). The plan content was read via `git show b1880f9:<path>` (read-only, no merge/checkout) and executed in full on this worktree's own branch, per the execution contract (`do NOT switch branches, do NOT merge, do NOT push`). All three task commits and this SUMMARY landed on `worktree-agent-ab424cad4339b58ca`, not on `G-1802/jobspy-hardening`.

## What Changed

**Task 1 — `JobSpyAdapter` (src/career_os/discovery/adapters.py, src/career_os/config.py, .env.example):**
`JobSpyAdapter.SITES` is now `("indeed",)` — Glassdoor and Google are gone. Each board in `SITES` gets its own `scrape_jobs` call wrapped in `asyncio.wait_for(..., timeout=settings.jobspy_timeout_seconds)` (new `Settings.jobspy_timeout_seconds`, default 60, env `JOBSPY_TIMEOUT_SECONDS`, `gt=0`). A board raising or timing out is logged at WARNING and skipped, not re-raised, so the other boards' rows survive; if every call in a scrape fails, `scrape()` raises one `RuntimeError` that `_scrape_all_adapters` records as a sweep warning.

**Task 2 — `tools/scraper.py`, `tools/specific_hunt.py`, `tools/README.md`:**
`tools/scraper.py` gained `UNSUPPORTED_SITES = {"google": "..."}` and `validate_sites()`, called from both `scrape_all()` (raises `ValueError`) and `main()` (turns that into `parser.error()`, exit code 2). `DEFAULT_SITES` is now `["linkedin", "indeed"]`. `tools/specific_hunt.py` gained its first module docstring, documenting that LinkedIn descriptions come back blank by default (upstream issue #374) and what opting into `linkedin_fetch_description=True` costs. `tools/README.md` states Kestrel never scrapes LinkedIn from an authenticated session.

**Task 3 — `tools/source_registry.py`, `tools/scrape_resilient.py`:**
`tools/source_registry.py` gained `BROWSER_DISABLED_HOSTS` and `browser_disabled_reason(url)` (label-based, case-insensitive, fail-closed on scheme-less input). `tools/scrape_resilient.scrape_with_browser` now refuses every URL whose host matches `BROWSER_DISABLED_HOSTS` **before** importing Playwright, returning an error entry (`"disabled: <reason>"`) for each. `scrape_jobspy` now calls `scraper.validate_sites(sites)` before `_retry_with_backoff`, so a deterministic rejection (e.g. `google`) is logged once at ERROR instead of being retried 3 times with backoff sleeps.

## RED Failure Lines (per task, recorded before GREEN)

**Task 1** — `tests/test_jobspy_adapter.py` did not exist yet; first run against old `adapters.py`:
```
9 failed, 1 passed, 4 warnings in 0.24s
```
(The 1 pass was `TestJobSpyMissingDependency` — the jobspy-absent RuntimeError already existed unchanged.)

**Task 2** — `tests/test_scraper.py` (updated) + `tests/test_specific_hunt.py` (new):
```
tests/test_scraper.py: ImportError: cannot import name 'validate_sites' from 'scraper'
  (1 collection error — whole file could not run)
tests/test_specific_hunt.py: 1 failed, 2 passed in 0.19s
  (failed: test_docstring_mentions_linkedin_fetch_description_and_blank_and_374 — no docstring yet)
```

**Task 3** — `tests/test_source_registry.py` (new) + `tests/test_scrape_resilient.py` (extended):
```
tests/test_source_registry.py: ImportError: cannot import name 'BROWSER_DISABLED_HOSTS' from 'source_registry'
  (1 collection error — whole file could not run)
tests/test_scrape_resilient.py: 3 failed, 27 passed in 12.63s
  (2 browser-refusal tests errored calling into real Playwright-import codepath;
   test_rejected_site_is_not_retried observed scrape_resilient.time.sleep called
   3 times — the old code retried the deterministic google rejection with backoff)
```

## Verification (plan `<verification>` block, run after all three tasks)

1. `pytest tests/ -k jobspy -v` → **14 passed, 3 skipped**, 0 failed.
2. `pytest tests/ -m "not eval" -q --tb=short` (full CI-equivalent suite) → **4430 passed, 23 skipped, 27 deselected**, 0 failed, exit code 0 (126.09s).
3. `ruff check src/ tests/` → All checks passed. `ruff format --check src/ tests/` → 380 files already formatted.
4. Tools lint gate (`ruff check tools/scraper.py tools/specific_hunt.py tools/scrape_resilient.py tools/source_registry.py --output-format json`) → exactly the 14 pre-existing findings, unchanged: `scraper.py F821 ×1`; `scrape_resilient.py E501 ×5, B023 ×1, F401 ×7`. `source_registry.py` and `specific_hunt.py`: 0.
5. Ticket's grep checks:
   - `grep -n 'glassdoor' src/career_os/discovery/adapters.py` → **no output** (exit 1).
   - `grep -n 'wait_for' src/career_os/discovery/adapters.py` → `507:        jobs_df = await asyncio.wait_for(`
   - `grep -n 'google' tools/scraper.py` → 4 hits, all in the docstring / `UNSUPPORTED_SITES` comment block (no `DEFAULT_SITES` passthrough).
   - `grep -rn 'indeed' tools/scrape_resilient.py` (case-sensitive, as literally specified) → **no output** — every mention in this file is capitalized `Indeed` (comments + the `IMPORTANT:` docstring line), so the lowercase-exact grep is empty. `grep -rni 'indeed'` (case-insensitive) confirms 5 hits, all comments/docstring/section-header prose referencing the refusal path — no Playwright call site can reach Indeed (refusal happens before the `from playwright.sync_api import sync_playwright` line).
6. `git diff --name-only main...HEAD` → exactly the 13 files listed in the plan's `files_modified`; `CHANGELOG.md` and `README.md` (repo-root) are absent from the diff.
7. `git diff main...HEAD -- src/career_os/discovery/adapters.py` → two hunks, `@@ -387,29 +387,59 @@` and `@@ -424,24 +454,70 @@`, both entirely inside `class JobSpyAdapter` (starts at source line 389); no import-block (lines 10-20) or `ArbeitsagenturAdapter` change — keeps the concurrent G-1717 branch's edits to the same file mergeable.
8. `git log --format='%s%n%b' main..HEAD` → 3 commits, each titled `fix(G-1802): ...` with a non-empty body (see Commits below).

## AC5 / CHANGELOG (finding, for the orchestrator)

Per the plan's objective: no manual `CHANGELOG.md` edit was made. `CHANGELOG.md` is release-please-generated (`release-please-config.json`, no `Unreleased` section; the only two non-release commits in its history trimmed/rewrote generated blocks, never hand-added an entry pre-release). **The changelog line for this work comes from the PR's squash-merge title**, which `fix` maps to "Bug Fixes" — so the orchestrator should title the PR/squash commit a single user-readable `fix(G-1802): ...` sentence (e.g. `fix(G-1802): harden JobSpy discovery sweep and standalone scraper tools`). `README.md` (repo root) was also left untouched, per the plan — the discovery-claim doc update is out of scope, routed to the sibling docs-truth-pass ticket.

## Flag: tools/source_registry.py had no tests before this change

`tools/source_registry.py` (130+ lines, `FLOOR_SOURCES`, `JOBSPY_BOARDS`, `classify`/`check`/`status_table`/`suggest_floors`) had **zero** test coverage before this plan. `tests/test_source_registry.py` (new, 12 tests) covers only the new `browser_disabled_reason` / `BROWSER_DISABLED_HOSTS` surface this ticket adds. The rest of the module (the floor/status-classification logic) remains untested — a pre-existing gap, flagged per the plan's Claude's-discretion note, not fixed here (out of this ticket's scope).

## Deviations from Plan

None — plan executed as written, including the "Claude's discretion" choices documented in the plan's `<objective>` block (SITES as a class attribute, partial-failure logging vs. run.warnings wiring, DEFAULT_SITES dropping Glassdoor too, specific_hunt.py documentation-only fix, source_registry.py test-gap flagged not fixed).

One process deviation, not a plan deviation: this agent's worktree was forked from `main` one commit before the sibling branch that carries `260928-pbu-PLAN.md` (see "Execution environment note" above). The plan content was read via `git show` rather than being present in this worktree's checkout; all code changes and this SUMMARY were still produced by literally following that plan text task-by-task, with every verify command re-run and passing.

## Commits

1. `fix(G-1802): Indeed-only JobSpy sweep with per-site calls and a hard timeout`
2. `fix(G-1802): reject google in tools/scraper.py and document LinkedIn behaviour`
3. `fix(G-1802): hard-disable the Indeed Playwright fallback and record why`

## Self-Check: PASSED

- `src/career_os/discovery/adapters.py` — FOUND, contains `asyncio.wait_for` and `SITES = ("indeed",)`.
- `src/career_os/config.py` — FOUND, contains `jobspy_timeout_seconds`.
- `.env.example` — FOUND, contains `JOBSPY_TIMEOUT_SECONDS=60`.
- `tests/test_jobspy_adapter.py` — FOUND, 10 tests, all passing.
- `tools/scraper.py` — FOUND, contains `UNSUPPORTED_SITES` and `validate_sites`.
- `tools/specific_hunt.py` — FOUND, module docstring present.
- `tools/README.md` — FOUND, contains the no-authenticated-session line.
- `tests/test_specific_hunt.py` — FOUND, 3 tests, all passing.
- `tools/source_registry.py` — FOUND, contains `BROWSER_DISABLED_HOSTS` and `browser_disabled_reason`.
- `tools/scrape_resilient.py` — FOUND, contains `browser_disabled_reason` and `validate_sites` call sites.
- `tests/test_source_registry.py` — FOUND, 12 tests, all passing.
- All 3 commit hashes verified present via `git log --oneline --all`.
