---
phase: 06-test-honesty
plan: 01
subsystem: testing
tags: [ruff, pre-commit, toolchain, ci, pytest]

requires: []
provides:
  - "One exact ruff version (0.16.9) governing pyproject.toml's dev extra and .pre-commit-config.yaml's astral-sh/ruff-pre-commit rev"
  - "force-exclude = true under [tool.ruff], closing the _alembic exclude gap for explicit-path invocations (pre-commit, editor integrations)"
  - "tests/test_toolchain_pins.py: get_pyproject_ruff_pin, get_precommit_ruff_rev, a real-file drift guard, an _alembic-exclude regression test, and 14 parser self-tests"
affects: ["06-02 (wave 2, shares the pinned ruff formatting every new test file must satisfy)"]

actuals:
  tokens: 3947
  tasks: 2
  commits: 2
  plan_head_before: c5f4856c359d2f4a9593565ae25090c4e757707e
  plan_head_after: 7d4185f90332656659f7cec8e46fe7f8b73b67af

tech-stack:
  added: []
  patterns:
    - "Sweep + guard-the-guard style test (tests/test_provider_contract.py analog) applied to a two-config-file drift guard instead of a module sweep"
    - "tomllib + packaging.requirements.Requirement for exact-pin TOML parsing (no new dependency)"
    - "Deterministic line-scan regex parser for a scoped YAML block, avoiding a new pyyaml declaration (DEC-02)"

key-files:
  created:
    - tests/test_toolchain_pins.py
  modified:
    - pyproject.toml
    - .pre-commit-config.yaml

key-decisions:
  - "DEC-05 executed: pin value (0.16.9) resolved at execution time from the newest green main CI run (36580634314, headSha 2a065a2), not copied from RESEARCH.md's 0.16.9 observation — independently re-verified and happened to match."
  - "Ruff 0.16.9's `ruff format --check` default output format is per-file concise diagnostics (`path:line:col: unformatted: ...`), not the older `Would reformat: <path>` line the plan's verify-command-5 sed pattern assumed. Fixed inline by using `--output-format concise` and `cut -d: -f1` for the ad-hoc shell extraction (Rule 3 — the verify script itself, not committed test/production code)."
  - "Both Task 2 self-tests and the scratch drift proofs passed against Task 1's parsers with zero required changes — documented honestly rather than staged as if a fix occurred."

requirements-completed: [TEST-03, TEST-04]

coverage:
  - id: D1
    description: "One exact ruff version (0.16.9) pinned in pyproject.toml's dev extra and .pre-commit-config.yaml's astral-sh/ruff-pre-commit rev, resolved from the newest green CI run"
    requirement: "TEST-03"
    verification:
      - kind: unit
        ref: "tests/test_toolchain_pins.py#test_ruff_pin_matches_precommit_rev"
        status: pass
      - kind: integration
        ref: "ruff check src/ tests/ && ruff format --check src/ tests/ (CI's exact Lint step)"
        status: pass
    human_judgment: false
  - id: D2
    description: "force-exclude = true keeps the _alembic exclude intact for explicit-path invocations (pre-commit's actual invocation shape)"
    requirement: "TEST-03"
    verification:
      - kind: unit
        ref: "tests/test_toolchain_pins.py#test_ruff_exclude_keeps_alembic_out"
        status: pass
      - kind: integration
        ref: "ruff check/format --check src/career_os/_alembic/ -> All checks passed!"
        status: pass
      - kind: integration
        ref: "pre-commit run ruff-format/ruff --files <alembic file> -> file left untouched (ALEMBIC-HOOK-EXCLUDE-OK)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Drift guard fails the moment the two pins disagree, proven in both directions with reverted scratch edits"
    requirement: "TEST-04"
    verification:
      - kind: unit
        ref: "tests/test_toolchain_pins.py (14 parser self-tests: drift, agreement, quoting, missing/duplicate blocks, frozen SHA rejection, non-exact specifiers, canonical-name matching)"
        status: pass
      - kind: manual_procedural
        ref: "Scratch drift proof, both directions, reverted via git checkout (DRIFT-PROOF-PRECOMMIT-OK / DRIFT-PROOF-PYPROJECT-OK)"
        status: pass
    human_judgment: false

duration: 42min
completed: 2026-09-30
status: complete
---

# Phase 6 Plan 1: Pin ruff, close the _alembic force-exclude gap, prove drift detection Summary

**One exact ruff version (0.16.9), resolved from the newest green CI run, now governs both pyproject.toml and .pre-commit-config.yaml, with `force-exclude = true` closing a previously-undiscovered gap where pre-commit's explicit-path invocation bypassed the `_alembic` exclude, and 16 tests (2 real-file + 14 self-tests) proving the guard actually detects drift.**

## Performance

- **Duration:** 42 min
- **Started:** 2026-09-30T09:47:00Z (approx, session start)
- **Completed:** 2026-09-30T10:29:00Z (approx)
- **Tasks:** 2
- **Files modified:** 3 (2 modified, 1 created)

## Version Resolution (DEC-05)

- Newest green CI run on `main`: **36580634314**, headSha `2a065a2` (`2a065a2a1c02a00614d53c9602859f569f968ee6`), conclusion `success`, created 2026-09-29T14:10:16Z.
- `gh run view 36580634314 --log | grep -oE 'ruff-[0-9]+\.[0-9]+\.[0-9]+' | sort -u` printed exactly one version: **`ruff-0.16.9`** (X_ci = 0.16.9).
- `pip index versions ruff` PyPI-latest: **0.16.9** (matches X_ci exactly).
- `git ls-remote --exit-code --tags https://github.com/astral-sh/ruff-pre-commit refs/tags/v0.16.9` → `a56c0b927e6465d37cae3e97d35d4d18ab2b96cd refs/tags/v0.16.9` (tag exists, exit 0).
- **Chosen pin: X.Y.Z = 0.16.9** — matches X_ci and PyPI-latest, no lower fallback version was needed.

## Accomplishments

- `pyproject.toml`'s `dev` extra pins `ruff==0.16.9` (was `ruff>=0.11.0`), with a comment explaining the exact-pin requirement and the Dependabot one-sided-bump caveat.
- `[tool.ruff]` gained `force-exclude = true`, with the header comment rewritten to state the accurate rationale (the research's original claim that pre-commit bypasses the exclude entirely was wrong — pre-commit's hooks already pass `--force-exclude` themselves per the cached `.pre-commit-hooks.yaml` manifest; `force-exclude` in pyproject closes the gap for bare explicit-path `ruff check <file>` invocations and editor integrations).
- `.pre-commit-config.yaml`'s `astral-sh/ruff-pre-commit` rev bumped `v0.11.0` → `v0.16.9`, header comment rewritten to name the enforcing test.
- `tests/test_toolchain_pins.py` created: `get_pyproject_ruff_pin`, `get_precommit_ruff_rev` (stdlib `tomllib` + `packaging`, and a deterministic line-scan regex for the YAML block — no new `pyyaml` dependency per DEC-02/DEC-03), `test_ruff_pin_matches_precommit_rev`, `test_ruff_exclude_keeps_alembic_out`, and 14 self-tests proving the parsers themselves are correct against constructed fixtures (drift detection, agreement, quoting/comment tolerance, wrong-block rejection, duplicate-block rejection, frozen-SHA rejection, non-exact-specifier rejection, canonical-name matching).
- The shared `.venv` (used by every worktree in this milestone) now has ruff 0.16.9 installed, matching the pin.

## Task Commits

Each task was committed atomically:

1. **Task 1 (tracer): resolve ruff pin from CI, pin in both files, prove CI/pre-commit shape parity** — `7a4245a` (chore)
2. **Task 2: parser self-tests, drift in both directions, real pre-commit parity** — `7d4185f` (test)

Both commits are on the executor branch (`worktree-agent-ad19f326a353b467e`); this plan does not push, open a PR, or run review-push, per the plan's own success criteria.

## Tracer Feedback Gate

`workflow.human_verify_mode` is unset (default `end-of-phase`) and the run is interactive (`workflow._auto_chain_active`/`workflow.auto_advance` both `false`), and Task 1's `<verify>` block carries only `<automated>` entries (no `<human-check>`). Per checkpoints.md row 3, the tracer's full `<verify>` (all 5 automated checks) was re-run end-to-end after the Task 1 commit and all passed — no checkpoint synthesized, expansion into Task 2 proceeded directly (`⚡ Tracer verified end-to-end — expanding`).

## RED-first note (Task 2 self-tests)

Per the plan's TDD instruction, the self-tests were run against Task 1's already-committed parsers before any parser modification was considered. **All 16 tests (2 real-file + 14 new self-tests) passed on the first run — no parser bug surfaced, and no changes were made to `get_pyproject_ruff_pin` or `get_precommit_ruff_rev` in Task 2.** This is reported honestly rather than staging an artificial fix: the parsers were written carefully enough in Task 1 (informed directly by the self-test requirements already specified in the plan) that the "RED" phase found nothing to fix.

## Scratch Drift Proofs (both directions, TEST-04)

**Direction 1 — mutate `.pre-commit-config.yaml`'s rev to `v0.0.0`:**
```
E       AssertionError: ruff drift: pyproject.toml dev extra pins ruff==0.16.9 but .pre-commit-config.yaml astral-sh/ruff-pre-commit rev is v0.0.0; bump both together (G-1383)
```
File restored via `git checkout -- .pre-commit-config.yaml`; full suite re-ran green (16 passed); `git status --short -- .pre-commit-config.yaml` empty afterward.
**DRIFT-PROOF-PRECOMMIT-OK**

**Direction 2 — mutate `pyproject.toml`'s pin to `ruff==0.0.0`:**
```
E       AssertionError: ruff drift: pyproject.toml dev extra pins ruff==0.0.0 but .pre-commit-config.yaml astral-sh/ruff-pre-commit rev is v0.16.9; bump both together (G-1383)
```
File restored via `git checkout -- pyproject.toml`; full suite re-ran green (16 passed); `git status --short -- pyproject.toml` empty afterward.
**DRIFT-PROOF-PYPROJECT-OK**

## Real Pre-commit Parity (TEST-03)

Run after the Task 2 commit (the verify script's own precondition requires a clean `git status --short -- src tests`, which only held once `tests/test_toolchain_pins.py` was committed):

- `pre-commit run ruff --all-files` → installed the v0.16.9 hook environment, `ruff (legacy alias)......Passed`.
- `pre-commit run ruff-format --all-files` → `ruff format..............Passed`.
- `git status --short -- src tests` empty after both hooks ran.
**PRECOMMIT-PARITY-OK**

- Picked `src/career_os/_alembic/versions/07cca291f71f_add_saved_searches_table.py` — confirmed via `ruff format --check --no-force-exclude` that it would be reformatted (19 files in `_alembic/` would be reformatted without the exclude, proving the proof is not vacuous).
- `pre-commit run ruff-format --files <that file>` → Passed. `pre-commit run ruff --files <that file>` → Passed.
- `git status --short -- src/career_os/_alembic` empty afterward — the file was left untouched.
**ALEMBIC-HOOK-EXCLUDE-OK src/career_os/_alembic/versions/07cca291f71f_add_saved_searches_table.py**

## Files Created/Modified

- `pyproject.toml` — `ruff==0.16.9` exact pin (dev extra), `force-exclude = true` under `[tool.ruff]`, rewritten comments
- `.pre-commit-config.yaml` — `rev: v0.16.9` for astral-sh/ruff-pre-commit, rewritten header comment
- `tests/test_toolchain_pins.py` (new) — 147 then 175 lines added across the two commits; `_REPO_ROOT`, `RUFF_PRECOMMIT_URL`, `get_pyproject_ruff_pin`, `get_precommit_ruff_rev`, `_write`, and 16 test functions (2 real-file + 14 self-tests, 4 of which are parametrized variants of `test_precommit_rev_tolerates_quotes_and_trailing_comment` and 3 of `test_pyproject_pin_rejects_non_exact_specifiers`)

## Decisions Made

- DEC-05 executed as written: the pin (0.16.9) came from the newest green CI run at execution time, independently re-verified against PyPI-latest and the ruff-pre-commit tag — not copied from RESEARCH.md, even though it happened to match RESEARCH.md's own same-day observation.
- Ruff 0.16.9 changed `ruff format --check`'s default output format from the `Would reformat: <path>` line the plan's verify-command-5 shell one-liner assumed to per-file concise diagnostics (`path:line:col: unformatted: ...`). Fixed the ad-hoc shell extraction with `--output-format concise` + `cut -d: -f1` (a Rule 3 blocking-issue fix to the verify script itself — no test or production code was touched).
- Both Task 2 self-tests and the scratch drift proofs passed against Task 1's parsers on the first run with zero parser changes required — reported as-is rather than manufacturing an artificial RED.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Adapted the _alembic-file-extraction shell command to ruff 0.16.9's changed `format --check` output format**
- **Found during:** Task 2, real pre-commit parity verification (verify command 5)
- **Issue:** The plan's `sed -n 's/^Would reformat: //p'` pattern matches an older ruff CLI output format. Ruff 0.16.9's default `--check` output is per-file concise diagnostics with no `Would reformat: ` prefix line, so the pattern always matched zero lines and the extracted file variable would be empty.
- **Fix:** Used `ruff format --check --no-force-exclude --output-format concise src/career_os/_alembic/ | head -1 | cut -d: -f1` to extract the first offending file path from the `path:line:col: unformatted: ...` line shape.
- **Files modified:** none (ad-hoc verification shell command only, not committed)
- **Verification:** Extracted `src/career_os/_alembic/versions/07cca291f71f_add_saved_searches_table.py`; confirmed non-empty before proceeding to the pre-commit hook-scoped run.
- **Commit:** N/A (verification-only change, not part of either commit)

---

**Total deviations:** 1 auto-fixed (1 blocking, verify-script-only)
**Impact on plan:** No production or test code was affected. The underlying `_alembic` force-exclude behavior was proven exactly as the plan required, using an equivalent (non-vacuous) file-selection mechanism.

## Out-of-scope discovery (logged, not fixed)

The plan-level full-suite `<verification>` (`pytest tests/ -m "not eval"`) surfaced 3 pre-existing failures unrelated to this plan's scope: `tests/test_dep_security.py::test_npm_audit_no_high_or_critical` for `[frontend]`, `[worker]`, `[extension]` — an npm advisory (`GHSA-6j4f-fj2g-mc7p`, brace-expansion DoS) in those three lockfiles. This plan touches no npm package files. Logged to `.planning/phases/06-test-honesty/deferred-items.md`; the project's `WINDOWS.md` ledger append (`gsd-tools query windows append`) was attempted but the `windows` subcommand does not exist in this GSD-tools install (`Unknown command: windows`) — per the executor contract this is best-effort/optional, so this is noted here instead and execution continued.

## Issues Encountered

None beyond the two items already documented above (ruff CLI output-format adaptation; pre-existing npm audit failures out of scope).

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Both Task 1 and Task 2 commits (`7a4245a`, `7d4185f`) are on `worktree-agent-ad19f326a353b467e`, ready for the orchestrator to merge.
- The shared `.venv` now has ruff 0.16.9 installed, which plan 06-02 (wave 2) depends on per DEC-06 — any new test files 06-02 creates must be formatted by this pinned ruff.
- `git status --short -- pyproject.toml .pre-commit-config.yaml src tests` is empty; the working tree is clean modulo the gitignored `config/personal.yaml` and `data/` created for the full-suite run (both confirmed gitignored via `git check-ignore -v`).
- No blockers for 06-02.

## Self-Check: PASSED

- `tests/test_toolchain_pins.py` exists: FOUND.
- Commit `7a4245a` exists: FOUND (`git log --oneline --all | grep 7a4245a`).
- Commit `7d4185f` exists: FOUND (`git log --oneline --all | grep 7d4185f`).
- `git show --stat 7a4245a` lists exactly `pyproject.toml`, `.pre-commit-config.yaml`, `tests/test_toolchain_pins.py`: confirmed.
- `git show --stat 7d4185f` lists exactly `tests/test_toolchain_pins.py`: confirmed.
- Plan-level `<verification>` re-run: `pytest tests/test_toolchain_pins.py -v` → 16 passed, 0 skipped; `ruff check src/ tests/ && ruff format --check src/ tests/` → exit 0; full suite → 4499 passed, 25 skipped, 27 deselected, 3 failed (pre-existing, out of scope, documented above); `git status --short -- pyproject.toml .pre-commit-config.yaml src tests` → empty.

---
*Phase: 06-test-honesty*
*Plan: 01*
*Completed: 2026-09-30*
