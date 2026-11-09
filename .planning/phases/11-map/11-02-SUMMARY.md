---
phase: 11-map
plan: 02
subsystem: testing
tags: [pytest, strict-xfail, mapping-tables, yaml, v2-pending, map-03]

requires:
  - phase: 11-map
    provides: "CONTEXT D-08 (strict-xfail mapping tables), RESEARCH Pattern 1, research SUMMARY/FEATURES target behaviours"
provides:
  - "v2_pending pytest marker (the only edit outside tests/, docs/, .planning/)"
  - "tests/targets/ package: NotBuilt, load_target, load_tables, build_params, project, observe_row, table_problems"
  - "Eight provisional mapping tables (Phases 14 to 21), 95 rows, each collected today as a strict xfail"
  - "Single data-driven engine test and an inventory meta-test with EXPECTED_ROWS pins and guard-the-guard cases"
affects: [phase-14-find, phase-15-filter, phase-16-scan, phase-17-score, phase-18-track, phase-19-write, phase-20-connect, phase-21-apply, 11-06]

actuals:
  tokens: 17863
  tasks: 3
  commits: 3
plan_head_before: 8d5756472950391facd55907f012c847dc3d2025
plan_head_after: da280e9c592160999a5b26d5c7483a374446eaec

tech-stack:
  added: []
  patterns:
    - "Mapping tables as YAML data; one parametrized engine; pending flag drives v2_pending + xfail(strict=True, raises=NotBuilt)"
    - "A phase turns its rows green by setting pending: false in its own table"
    - "Inventory meta-test pins row counts per file and inspects every param's marks"

key-files:
  created:
    - tests/targets/__init__.py
    - tests/targets/_support.py
    - tests/targets/test_mapping_tables.py
    - tests/targets/test_target_inventory.py
    - tests/targets/tables/phase_14_find.yaml
    - tests/targets/tables/phase_15_filter.yaml
    - tests/targets/tables/phase_16_scan.yaml
    - tests/targets/tables/phase_17_score.yaml
    - tests/targets/tables/phase_18_track.yaml
    - tests/targets/tables/phase_19_write.yaml
    - tests/targets/tables/phase_20_connect.yaml
    - tests/targets/tables/phase_21_apply.yaml
  modified:
    - pyproject.toml

key-decisions:
  - "Tables are pure YAML; the engine applies the marks from each table's pending flag, so D-08's 'remove the marker' becomes 'set pending: false in your own table'"
  - "Scan encodes only exit codes 0 and 3; codes 1, 2, 4 and 75 stay under pending_decision (OQ-4)"
  - "Phases 12 and 13 are not encoded (OQ-5); phase numbers 14 to 21 are provisional"
  - "assess() is called with a third keyword, context (seen_urls), because the seen set is run context, not search profile"

patterns-established:
  - "load_target raises NotBuilt only for a missing target module or attribute; every other import failure propagates"
  - "Table checker rejects non-string YAML keys (an unquoted on/off/yes/no key silently becomes a boolean)"

requirements-completed: [MAP-03]

coverage:
  - id: D1
    description: "v2_pending marker registered; it is the only configuration edit and nothing under src/ or frontend/ changed"
    requirement: MAP-03
    verification:
      - kind: other
        ref: "git diff origin/main -- pyproject.toml shows one added line; git diff --stat origin/main...HEAD -- src/ frontend/ prints nothing"
        status: pass
    human_judgment: false
  - id: D2
    description: "Eight provisional mapping tables (95 rows) collected by CI as strict xfails, none passing, none erroring"
    requirement: MAP-03
    verification:
      - kind: unit
        ref: "python -m pytest tests/ -m 'not eval' (4780 passed, 24 skipped, 95 xfailed)"
        status: pass
      - kind: unit
        ref: "tests/targets/test_mapping_tables.py#test_mapping_row"
        status: pass
    human_judgment: false
  - id: D3
    description: "Inventory meta-test guards structure, row-count pins, marks, ordering, and proves its checker with bad tables"
    requirement: MAP-03
    verification:
      - kind: unit
        ref: "tests/targets/test_target_inventory.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "Row contents (provisional target names, reason codes, key formats) are the right behaviour for each later phase"
    requirement: MAP-03
    verification: []
    human_judgment: true
    rationale: "Rows encode research, not decisions; each later phase's review owns and may rewrite them"

duration: ~25min
completed: 2026-11-09
status: complete
---

# Phase 11 Plan 02: Mapping tables (MAP-03) Summary

**95 provisional input-to-output rows for Phases 14 to 21, encoded as YAML and collected today by one data-driven engine as `v2_pending` strict xfails pinned to `NotBuilt`, with an inventory meta-test that fails on any lost row, weakened mark or malformed table.**

## Performance

- **Duration:** about 25 min (start time was not captured at spawn; estimate from commit timestamps)
- **Completed:** 2026-11-09
- **Tasks:** 3 (1 tracer, 2 auto)
- **Files:** 13 (12 created, 1 modified)
- **Verification run:** `python -m pytest tests/ -m "not eval"` reports 4780 passed, 24 skipped, 27 deselected, 95 xfailed, exit 0, no xpassed, no errors

## Accomplishments

- Registered one pytest marker, `v2_pending`, in `pyproject.toml`. It is the only edit outside `tests/`, `docs/` and `.planning/`; `git diff --stat origin/main...HEAD -- src/ frontend/` prints nothing.
- Built `tests/targets/_support.py`. `load_target` raises `NotBuilt` only when the target module or attribute is missing; a `ModuleNotFoundError` from inside an existing module and every other `ImportError` propagate. `build_params` yields one `pytest.param` per row, ids `phase_NN_name::table::row-id`, in YAML order, with `v2_pending` and `xfail(strict=True, raises=NotBuilt, reason="v2.0 Phase N")` while a table is `pending: true` and no marks once it is `pending: false`.
- One engine test, `test_mapping_row`, covers every row. `python -m pytest tests/targets -m v2_pending` reports 95 xfailed and nothing else; `--collect-only` selects the same 95.
- Inventory meta-test (32 tests in `tests/targets/`, 95 rows pinned) fails on: a lost or added unpinned row, an unpinned or missing table file, a row without `id`/`input`/`expect`, a phase number that disagrees with the filename, a malformed or non-`career_os` target, duplicate row ids, identical input with different expect, zero rows, an empty expect, non-string YAML keys, and any pending param whose xfail loses `strict=True`, `raises=NotBuilt` or the exact reason.

### Tables, provisional targets and row counts

All inputs are synthetic (fictional candidates and companies, the shipped example geo config, `example.com` URLs).

| Phase | File | Rows | Tables and provisional target |
|-------|------|------|-------------------------------|
| 14 Find | `phase_14_find.yaml` | 34 | `url_normalize` -> `career_os.services.dedup:normalize_url` (7); `identity_key` -> `dedup:identity_key` (5); `seen_classification` -> `dedup:classify_against_seen` (4); `liveness` -> `career_os.discovery.ats:liveness_state` (7); `source_canary` -> `discovery.ats:canary_verdict` (8); `arrival_filter` -> `discovery.ats:is_arrival` (3) |
| 15 Filter | `phase_15_filter.yaml` | 12 | `assess_decision` -> `career_os.services.assess:assess` (12) |
| 16 Scan | `phase_16_scan.yaml` | 8 | `exit_code` -> `career_os.services.scan:exit_code_for` (3); `run_settings` -> `scan:check_run_settings` (3); `dry_run` -> `scan:dry_run_plan` (2) |
| 17 Score | `phase_17_score.yaml` | 9 | `digest_summary` -> `career_os.services.triage:build_digest_summary` (3); `audit_sample` -> `career_os.services.audit:draw_sample` (3); `overturn_fixture` -> `audit:overturn_fixture` (2); `review_card` -> `audit:review_card_field_order` (1) |
| 18 Track | `phase_18_track.yaml` | 10 | `submission_state` -> `career_os.services.outcomes:next_submission_state` (5); `outcome_ledger` -> `outcomes:replay_outcome_ledger` (2); `confirmation_prompt` -> `outcomes:needs_confirmation_prompt` (3) |
| 19 Write | `phase_19_write.yaml` | 10 | `fact_gate` -> `career_os.services.gates:fact_gate` (6); `voice_gate` -> `gates:voice_gate` (3); `draft_producers` -> `career_os.services.drafting:draft_producers` (1) |
| 20 Connect | `phase_20_connect.yaml` | 6 | `tool_manifest` -> `career_os.mcp_server:tool_manifest_summary` (3); `untrusted_text` -> `mcp_server:render_untrusted_text` (2); `cli_twin` -> `mcp_server:cli_twin_for` (1) |
| 21 Apply | `phase_21_apply.yaml` | 6 | `prefill_plan` -> `career_os.services.prefill:plan_prefill` (6) |
| | | **95** | EXPECTED_ROWS pins each file; the sum is 95 against the plan floor of 85 |

### Scan pending_decision entries (OQ-4)

`phase_16_scan.yaml` records these four conflicts and encodes none of them; the `exit_code` table has rows only for 0 and 3, and `test_scan_encodes_only_the_agreed_exit_codes` fails if a row ever expects 1, 2, 4 or 75:

- `1: partial (SUMMARY Phase 5) vs fatal (ARCHITECTURE line 180)`
- `2: spend halted (SUMMARY) vs partial (ARCHITECTURE)`
- `4: spend halt (ARCHITECTURE only)`
- `75: lease held (SUMMARY only)`

## Task Commits

1. **Task 1: marker, engine and the Filter assess() table end to end (tracer)** - `d4612cf9` (test)
2. **Task 2: Find, Scan, Score and Track tables** - `2bfa415c` (test)
3. **Task 3: Write, Connect and Apply tables plus the eight-phase pin** - `da280e9c` (test)

Plan metadata (this SUMMARY): committed as `docs(G-2039): complete phase 11 plan 02 (mapping tables)`; its hash is not in this file (a commit cannot contain its own hash) and is in the executor's return message.

Tracer gate: Task 1's `<verify>` was automated-only and ran green end to end (29 passed, 12 xfailed) before expansion, so expansion proceeded.

## Files Created/Modified

- `pyproject.toml` - one added marker line, `v2_pending`
- `tests/targets/_support.py` - `NotBuilt`, `TableError`, `load_target`, `Table`, `read_table`, `load_tables`, `build_params`, `project`, `observe_row`, `table_problems`
- `tests/targets/test_mapping_tables.py` - the single parametrized engine test
- `tests/targets/test_target_inventory.py` - `EXPECTED_ROWS` pins and the guard-the-guard cases
- `tests/targets/tables/phase_14_find.yaml` to `phase_21_apply.yaml` - the eight tables

## Decisions Made

- Kept the plan's design: pure YAML data, one engine, marks derived from `pending`. A phase turns its rows green by flipping its own table to `pending: false`, which drops both marks for that phase only (verified by `test_pending_false_drops_marks_for_that_phase_only`).
- `assess()` rows pass a third keyword, `context` (`seen_urls`), alongside `job` and `profile`. The plan described only `job` and `profile`, but the seen set is run context rather than search profile, and FEATURES 2a gives `assess(posting, search_profile, context)`. The Filter review may fold it back; it is a one-line change per row group.
- The engine calls a small `observe_row` helper in `_support.py` (load target, call with `**input`, project the expected keys) and keeps the two asserts in the test body. This lets the inventory prove the engine path is not vacuous against a real built target (`test_engine_observation_is_not_vacuous_against_a_built_target`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Table checker rejects non-string YAML keys**
- **Found during:** Task 2 (Track table)
- **Issue:** PyYAML 1.1 reads an unquoted `on:` key as boolean `True`. The outcome-ledger rows used `on:` for an event date, which made `json.dumps(sort_keys=True)` raise `TypeError` at collection and, worse, would have silently changed the row's meaning had it not crashed.
- **Fix:** Renamed the key to `occurred_on` in `phase_18_track.yaml`, and added `_non_string_keys` to `table_problems` plus an inventory case (`yaml-boolean-key`) so the trap is caught for every future table.
- **Files modified:** `tests/targets/_support.py`, `tests/targets/test_target_inventory.py`, `tests/targets/tables/phase_18_track.yaml`
- **Verification:** `python -m pytest tests/targets` green; the new case fails if the check is removed
- **Committed in:** `2bfa415c`

**2. [Rule 1 - Bug] Two inventory tests had fewer than 2 assertions**
- **Found during:** Task 1 (`.claude/hooks/check-test-assertions.py` on the staged files)
- **Issue:** `test_load_tables_rejects_a_malformed_directory` had 1 assert and `test_load_target_rejects_a_spec_without_an_attribute` had 0.
- **Fix:** Added assertions on the error text. Hook exit 0 afterwards.
- **Committed in:** `d4612cf9`

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 bug). **Impact on plan:** both strengthen the guard; no scope change.

## Issues Encountered

- The task 1 acceptance command `python -m pytest tests/targets --collect-only -q -m eval | tail -1` could not be run: the executor sandbox refuses any command containing the word `eval`. Equivalent evidence instead: no file under `tests/targets/` mentions an `eval` marker or `pytestmark` (grep count 0), and the 95 rows are all selected by `-m v2_pending` alone.
- The repository's own `scrub_patterns()` set (from `tests/eval/geo/replay.py`) reports one hit across `tests/targets/`: the `tracking:url-query` pattern on `phase_14_find.yaml`. That is inherent to the URL-normalisation rows, whose subject is query strings with `utm_*` and `gh_src`; they sit on `example.com` and carry no identity. The set is applied only to the geo fixtures in this repo. The gate-file patterns from `.github/pii-patterns.txt` and the generic email pattern report no hits. The CI PII step itself was not run here.
- `pytest --version` in the fresh worktree venv resolved pytest 9.2.0 (plan text referenced 9.0.3 from RESEARCH); the plan's floor was 8.3 or newer.

## Known Stubs

None. The tables are intentionally pending, not stubs: every row is a strict xfail that fails CI if it passes early. Nothing was appended to `.planning/WINDOWS.md`.

## Threat Flags

None. No network endpoint, auth path, file access or schema change was added. T-11-05 and T-11-06 mitigations are in place (`raises=NotBuilt` plus the narrow `ModuleNotFoundError` check; inventory inspects every param's marks and pins row counts; `yaml.safe_load` only; `table_problems` rejects unknown shapes before any row runs).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Each later phase starts by reconciling its table with its closed review, then flips `pending: false` and updates its `EXPECTED_ROWS` pin and, if it renumbers, the `phase:` field, filename and pin.
- Phase numbers 14 to 21 are provisional until each `/gsd-phase add`.
- Plan 11-06's full accounting can cite MAP-03 as done.
- Delivery: nothing was pushed and `review-push` was not run (orchestrator owns Git delivery step 5). The three task commits and the SUMMARY commit sit on the worktree branch forked from `G-2039/map` at `8d575647`.

## Self-Check: PASSED

- Created files exist: all 12 under `tests/targets/` found on disk.
- Task commits `d4612cf9`, `2bfa415c`, `da280e9c` are ancestors of HEAD.
- `git status --short` was empty before this SUMMARY was written.

---
*Phase: 11-map*
*Completed: 2026-11-09*
