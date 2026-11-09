---
phase: 11-map
plan: 03
subsystem: testing
tags: [pytest, alembic, sqlite, yaml, strict-xfail, privacy-boundary, script-ledger]

requires:
  - phase: 11-map
    provides: "plan 11-01 MANIFEST layout (classes.gate_verdicts.status and golden) that the armed gate-verdict check reads"
provides:
  - "MAP-05 protective golden: an ai_providers key survives alembic upgrade head and is read back through the real factory"
  - "MAP-01 script ledger (49 rows over 73 files) with a filesystem-derived honesty test and guard cases"
  - "Boundary validators (verdict list, arrival counts, anonymised private ledger rows, forbidden_hits) plus a CLI"
  - "MAP-09 citation checker with strict-xfail enforcement for the Cut A and Retire cut lists"
  - "Real-file checks for every crossing artefact, armed as strict xfails for plan 11-05"
affects: [11-05, 11-06, 12-foundation, 13-cut-a, 22-retire]

plan_head_before: 8d5756472950391facd55907f012c847dc3d2025
plan_head_after: b0e94e235b410bc6b1a6fc5f127417e51fdfc221

actuals:
  tokens: 25000
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "filesystem-derived ledger sweep with an in-memory guard-the-guard fixture"
    - "strict xfail keyed on a dedicated exception (ArtifactMissing, CutListMissing) so an invalid present file fails loudly"
    - "forbidden-content scan reports label and count only, never the matched text"

key-files:
  created:
    - tests/test_ai_providers_golden.py
    - tests/ports/__init__.py
    - tests/ports/PORT_LEDGER.yaml
    - tests/ports/test_script_ledger.py
    - tests/ports/boundary.py
    - tests/ports/test_boundary_gates.py
    - tests/ports/test_map_artifacts.py
  modified: []

key-decisions:
  - "The ledger sweep drops git-ignored files (read-only git check-ignore) so a worktree, the main checkout and CI give the same answer; tracked files are never dropped"
  - "Where REQUIREMENTS.md overrides ARCHITECTURE.md section 10, the row reason names REQUIREMENTS.md as the winner, and a test pins 18 such rows"
  - "uncited_items returns one (0, 'cut list has no items', []) entry for an empty list so emptiness can never pass"
  - "find_cut_list raises ValueError (not CutListMissing) when more than one cut list matches, so ambiguity fails loudly"

patterns-established:
  - "Cut-list format: one line per item, '- {item} | verdict: {ID}' or '- {item} | verdicts: {ID}, {ID}', in .planning/phases/NN-slug/NN-CUT-LIST.md"
  - "A phase that writes a cut list removes the matching strict-xfail marker in the same PR"

requirements-completed: [MAP-01, MAP-05, MAP-08, MAP-09]

coverage:
  - id: D1
    description: "MAP-05 golden: seeded ai_providers key readable through factory._read_credential_from_db and get_ai_provider('openrouter') after upgrade head; timingsapp row gone, five other names survive"
    requirement: MAP-05
    verification:
      - kind: integration
        ref: "tests/test_ai_providers_golden.py (5 tests; mutation probe recorded below)"
        status: pass
    human_judgment: false
  - id: D2
    description: "MAP-01 ledger covers every tools/ and glue file exactly once with D-06 values, and the honesty test proves missing, phantom, collision, enum, sort, test-link, empty and anchor failure modes"
    requirement: MAP-01
    verification:
      - kind: unit
        ref: "tests/ports/test_script_ledger.py (23 tests; mutation probe recorded below)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Ledger dispositions (port, keep_until_retire, delete) and the candidate-delete proposals are maintainer decisions, not test-proven facts"
    requirement: MAP-01
    verification: []
    human_judgment: true
    rationale: "Dispositions are proposals from RESEARCH.md that the maintainer confirms; the test proves only that every file has a well-formed row"
  - id: D4
    description: "Boundary validators (verdict list, counts, private rows, forbidden_hits, cut-list citations) with single-mutation guard cases for every MAP-07, MAP-08 and MAP-09 probe, plus a CLI exiting 0, 1 or 2"
    requirement: MAP-08
    verification:
      - kind: unit
        ref: "tests/ports/test_boundary_gates.py (87 passed, 2 xfailed)"
        status: pass
    human_judgment: false
  - id: D5
    description: "MAP-09 and crossing checks armed as strict xfails (2 cut-list checks, 4 real-file checks)"
    requirement: MAP-09
    verification:
      - kind: unit
        ref: "pytest tests/ports -q -rxX reports 6 xfailed; probes show FAILED on an uncited item and XPASS(strict) on a cited one"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-11-09
status: complete
---

# Phase 11 Plan 03: Ledger, MAP-05 golden and boundary validators Summary

**A seeded AI key is proven to survive the full alembic chain through the real factory read, every tools/ and glue file has exactly one ledger row guarded by a filesystem-derived honesty test, and the verdict-list, counts and private-row crossing artefacts have validators with proven failure modes and strict-xfail real-file checks waiting for plan 11-05.**

## Performance

- **Duration:** about 25 min (start time was not recorded at spawn; estimated from the first commit)
- **Completed:** 2026-11-09
- **Tasks:** 3
- **Files created:** 7 (no existing file modified; nothing under `src/` or `frontend/`)

## Accomplishments

- MAP-05: `tests/test_ai_providers_golden.py` migrates a temp SQLite file to `f7a8b9c0d1e2`, seeds six `integration_configs` rows by raw SQL, upgrades to head, and asserts the key value and exactly one `ai_providers` row through the real reader and `get_ai_provider("openrouter")`. The real reader is captured at import and restored, so the autouse `hermetic_db_credentials` stub cannot make it vacuous.
- MAP-01: `tests/ports/PORT_LEDGER.yaml` has 49 rows covering 73 swept files. By disposition: 22 keep_until_retire, 15 port, 12 delete. By run status: 30 by_hand, 14 scheduled, 5 dead.
- `tests/ports/test_script_ledger.py` (23 tests) sweeps `tools/`, `automation/` and non-CI workflows that mention `tools/`, with in-memory guard cases for each failure mode.
- `tests/ports/boundary.py` holds the verdict-list, arrival-counts, private-row and cut-list contracts, `forbidden_hits()` (built on `scrub_patterns()`), and a CLI for plan 11-05.
- `tests/ports/test_boundary_gates.py` has 87 passing guard cases plus the two MAP-09 strict xfails; `tests/ports/test_map_artifacts.py` has the four crossing checks as strict xfails.

## Task Commits

1. **Task 1: MAP-05 protective golden** - `f0d5f06c` (test)
2. **Task 2: script ledger and honesty test** - `29a64f86` (docs, PORT_LEDGER.yaml) and `04f74e3f` (test, honesty test)
3. **Task 3: boundary validators and armed checks** - `b0e94e23` (test)

**Plan metadata:** the SUMMARY commit follows (`docs(G-2039): complete phase 11 plan 03 ...`).

## Mutation probes (mutation, red result, restore, green result)

1. **MAP-05.** Deleted the line `monkeypatch.setattr(factory, "_read_credential_from_db", REAL_READ)` (line 88; `git diff --stat` showed 1 deletion, proving the mutation applied). Result: 2 failed (`test_ai_providers_key_survives_upgrade_head`, `test_factory_builds_openrouter_with_the_seeded_key`), 3 passed. Restored with `git checkout -- <file>`; `git diff --exit-code` printed nothing; result: 5 passed.
2. **Ledger.** Deleted the 11-line `tools/normalize.py` row (`git diff --stat`: 11 deletions). Result: `test_ledger_has_no_problems` and `test_sweep_contains_the_anchors` failed, with `missing: tools/normalize.py matches no ledger row` in the output; 21 passed. Restored; `git diff --exit-code` printed nothing; result: 23 passed.
3. **MAP-09.** Created a temporary `.planning/phases/13-cut-a/13-CUT-LIST.md` containing `- drop the thing` (no verdict clause). As specified in the plan, `test_cut_a_cut_list_cites_a_verdict_for_every_item` reported FAILED, not XFAIL (the retire test stayed XFAIL). That failure came from `ArtifactMissing` because `11-VERDICTS.md` does not exist yet, so a supplementary probe wrote a temporary valid verdict list at `VERDICTS_PATH` as well: the test then failed on `assert [(1, 'drop the thing', [])] == []`, which is the citation assertion itself. Changing the item to `- drop the thing | verdict: X-01` made the test report `[XPASS(strict)]` and FAILED, proving the marker-removal forcing works; with the temporary verdict list present, `test_verdict_list_is_valid_and_complete` also XPASSed strictly, proving the validator accepts a valid list. Both temporary files were then removed; `git status --porcelain -- .planning` printed nothing and `pytest tests/ports` returned to 110 passed, 6 xfailed.

## Verification results

- `pytest tests/test_ai_providers_golden.py tests/ports -q -p no:cacheprovider -rxX`: 115 passed, 6 xfailed, no skips, no xpass.
- `pytest tests/ -q -m "not eval"`: 4863 passed, 24 skipped (pre-existing, none in the new files), 27 deselected, 6 xfailed.
- `pytest tests/test_no_import_masking_skips.py`: 232 passed (sweeps `tests/`, so it covers the new files).
- Idempotency: `git status --porcelain` before and after two runs of the ledger test is identical.
- `python -m tests.ports.boundary --verdicts tests/ports/__init__.py` exits 1.
- `ruff check` and `ruff format --check` over the new files exit 0; `.claude/hooks/check-test-assertions.py` and `check-trivial-assertions.py` exit 0 with the files staged.
- `gitleaks dir --redact --no-banner tests/ports tests/test_ai_providers_golden.py`: no leaks. `scrub_patterns()` over all seven new files: no hits.
- `git diff --stat origin/main...HEAD -- src/ frontend/`: empty.

## Cut-list format later phases must follow

A cut list is `.planning/phases/NN-slug/NN-CUT-LIST.md`, where the folder matches `*-cut-a` (Cut A) or `*-retire` (Retire). Every item is one line starting `- `, ending with a verdict clause naming ids that exist in `11-VERDICTS.md`: `- {item} | verdict: X-03` or `- {item} | verdicts: X-03, F-02`. An item with no clause, or an unknown id, fails. A list with no items fails. The phase that adds the file must remove the matching `xfail` marker in `tests/ports/test_boundary_gates.py` in the same PR. Plan 11-05 does the same for the four checks in `tests/ports/test_map_artifacts.py` when it crosses the files; the gate-verdict check stays XFAIL while `classes.gate_verdicts.status` is `awaiting_private_run`.

## Decisions Made

- Sweep drops git-ignored files and keeps tracked ones (see deviation 1).
- `local_scorer.py` is keep_until_retire (not a delete candidate) because plan 11-01 freezes it as a scoring golden producer, as the plan specified; `spike_batch_quality.py` has no listed tests because `tests/test_batch_quality_spike.py` does not mention that script (RESEARCH A7 warned the grep mapping was approximate).
- Porting targets in the ledger are provisional ("TBD:Phase 14" to "TBD:Phase 20", GSD numbering from RESEARCH).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Ledger sweep ignores git-ignored files**
- **Found during:** Task 2, from the orchestrator note that the sweep must give one answer in this worktree, the main checkout and CI.
- **Issue:** a bare `rglob` over `tools/` and `automation/` would count an ignored scratch file present only in one checkout, so the honesty test could pass in CI and fail locally (or the reverse).
- **Fix:** `sweep_files` filters its result through `git check-ignore -z --stdin` (read-only, empty set if git cannot answer). Tracked files are never reported ignored, so the plan's covered set (tracked `tools/` and glue files) is unchanged: 73 files here, equal to `git ls-files` for those roots. Two tests prove it (noise exclusion and ignored-versus-tracked-but-matching in a temporary repository).
- **Files modified:** tests/ports/test_script_ledger.py
- **Commit:** `04f74e3f`

**2. [Rule 3 - Blocking] Assertion-count hook rejected one MAP-05 test**
- **Found during:** Task 1 verification.
- **Issue:** `test_missing_ai_providers_row_reads_empty` had one `assert` plus `pytest.raises`, and `.claude/hooks/check-test-assertions.py` counts only `assert` statements.
- **Fix:** added `assert "ai_providers" not in _names(migrated_db)` before the reader call, which also proves the delete applied.
- **Files modified:** tests/test_ai_providers_golden.py
- **Commit:** `f0d5f06c`

**3. [Rule 1 - Bug] `require()` crashed on paths outside the repository**
- **Found during:** Task 3, writing the tmp_path test for `ArtifactMissing`.
- **Issue:** `path.relative_to(REPO_ROOT)` raised ValueError for a non-repo path instead of `ArtifactMissing`.
- **Fix:** show the repo-relative path only when `is_relative_to(REPO_ROOT)`.
- **Files modified:** tests/ports/boundary.py
- **Commit:** `b0e94e23`

### Other departures, none changing a plan deliverable

- The MAP-09 mutation probe as written fails through `ArtifactMissing` (no verdict list yet), so a supplementary probe proves the citation assertion; see the probes section.
- The ledger data and the honesty test are two commits (`docs` for `PORT_LEDGER.yaml`, `test` for the test), following the plan's commit-type rules.
- The idempotency check wrote its before and after snapshots to the session scratchpad instead of `$TMPDIR`, because the shell tool refused the chained git form.
- The environment is Python 3.11 (CI parity), not the 3.14 used in RESEARCH.

**Total deviations:** 3 auto-fixed (1 Rule 1, 1 Rule 2, 1 Rule 3).
**Impact on plan:** no scope change; all three fixes are inside files this plan owns.

## Issues Encountered

- The `PORT_LEDGER.yaml` header says private rows live in `tests/ports/PORT_LEDGER_PRIVATE.yaml`; that file does not exist until plan 11-05, and `test_private_ledger_rows_are_anonymous` is the armed check for it.
- `tests/ports/test_map_artifacts.py::test_gate_verdict_golden_is_frozen` reads `classes.gate_verdicts.status` and `golden` from plan 11-01's MANIFEST layout (taken from the 11-01 plan text); `tests/replay/golden/MANIFEST.json` was not in this worktree, so the awaiting path was verified only through the missing-file branch. Whoever merges the two plans should run `pytest tests/ports -rxX` once to confirm the check reports XFAIL against the real manifest.
- No stubs, no skipped tests and no unrun `<verify>` entries; nothing was appended to the broken-windows ledger.

## Threat Flags

None. The only new process-spawning code is a read-only `git check-ignore` in the ledger test and a temporary-directory `git init` in one test; neither touches the network or any trust boundary.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 11-05 can run `python -m tests.ports.boundary --verdicts ... --counts ... --private-rows ...` over the private export before anything crosses, then remove the four xfail markers in `test_map_artifacts.py` in the crossing commit.
- Plan 11-06's `tests/ports/test_ledger_manifest_link.py` can rely on `PORT_LEDGER.yaml` rows: every MANIFEST producer under `tools/` has a row, and `local_scorer.py` carries keep_until_retire as required.
- The orchestrator still needs to land these four commits on `G-2039/map`, run `review-push`, and push (not done here, per the dispatch notes).

---
*Phase: 11-map*
*Completed: 2026-11-09*

## Self-Check: PASSED
