---
phase: 11-map
plan: 01
subsystem: testing
tags: [golden-replay, provenance, pytest, jsonl, pii-scan, pinned-config]

requires:
  - phase: 11-map
    provides: "11-CONTEXT decisions D-03, D-05, D-07, D-13 and the A1 two-family reading of D-07"
provides:
  - "tests/replay package: pinned() harness, HARNESS registry, canonical JSONL encoding, manifest checker, PII scan, one-shot generator"
  - "five frozen Family A goldens (dedup_verdicts, eligibility_verdicts, scoring, scan_arrivals, digest) replayed over synthetic inputs at pinned producer blobs"
  - "Kestrel-authored synthetic gate inputs (gate_drafts.jsonl, gate_fact_sheet.json) awaiting the private gate run"
  - "six awaiting registrations (gate_verdicts plus the five Family B classes) with private_golden_problems, gate_verdict_problems and the --register-private paths plan 11-05 uses"
affects: [phase-11-04, phase-11-05, phase-11-06, phase-14-find, phase-15-filter, phase-16-scan, phase-17-score, phase-22-retire]

actuals:
  tokens: 58500
  tasks: 3
  commits: 3
plan_head_before: 8d5756472950391facd55907f012c847dc3d2025
plan_head_after: 4bd77dd90c84842c33b05040155da5bd2d6759d0

tech-stack:
  added: []
  patterns:
    - "golden = JSONL of {id, input, output} replayed through HARNESS[class] inside pinned(), compared exactly"
    - "MANIFEST.json per class: sha256, producer git blobs, producer_commit, python, month-granularity generated, pins; test fails on a changed golden byte or producer file"
    - "guard-the-guard: every validator rule is paired with a test that makes it fire (23 single mutations for the Family B validator)"
    - "lifecycle-tolerant manifest tests, so plan 11-05 freezes private classes without editing the test module"

key-files:
  created:
    - tests/replay/__init__.py
    - tests/replay/_support.py
    - tests/replay/generate_golden.py
    - tests/replay/test_golden.py
    - tests/replay/golden/README.md
    - tests/replay/golden/MANIFEST.json
    - tests/replay/golden/dedup_verdicts.jsonl
    - tests/replay/golden/eligibility_verdicts.jsonl
    - tests/replay/golden/scoring.jsonl
    - tests/replay/golden/scan_arrivals.jsonl
    - tests/replay/golden/digest.jsonl
    - tests/replay/golden/gate_drafts.jsonl
    - tests/replay/golden/gate_fact_sheet.json
  modified: []

key-decisions:
  - "pinned() fixes batch_probe._CONFIG, job_scorer._GEO_PROFILE, the blocklist floor, the tier0 clock and PIPELINE_*/GITHUB_STEP_SUMMARY; every pin is recorded per class in MANIFEST"
  - "Synthetic inputs may not name a real company (D-03), so job_scorer.BLOCKED_COMPANIES and local_scorer.DREAM_COMPANIES/STRONG_COMPANIES are pinned to fictional members for the replay"
  - "Family B classes have no HARNESS entry; Kestrel validates them by schema, invariants, sha256 and PII only, and replay modes are exact (dedup, eligibility), shape (scan arrivals), reference (scoring, digest)"
  - "gate_verdicts and Family B registration requires the file to already sit in golden/ for a real (non dry-run) registration"

patterns-established:
  - "Standalone generator and pytest share one implementation through tests/replay/_support.py (REPO_ROOT and tools/ put on sys.path there)"
  - "A replay harness that would write to a repo folder (daily_pipeline._fallback_score writes tracking/) redirects the write into a temp dir and a test asserts the folder is untouched"

requirements-completed: [MAP-02]

coverage:
  - id: D1
    description: "dedup_verdicts golden: 36 synthetic cases (suffixes, (m/f/d) noise, casing, slug drift, exact-equal merge, one-char-apart stays two, None and empty inputs, deduplicate([]), five-job list) replayed exactly under two hash seeds"
    requirement: MAP-02
    verification:
      - kind: unit
        ref: "tests/replay/test_golden.py#test_replay_reproduces_golden[dedup_verdicts::*]"
        status: pass
      - kind: unit
        ref: "tests/replay/test_golden.py#test_dedup_adjacency_pairs_merge_and_stay_apart"
        status: pass
    human_judgment: false
  - id: D2
    description: "eligibility_verdicts, scoring and scan_arrivals goldens (49, 65 and 17 cases) replayed under explicit config, blocklist, clock, env and transport pins; no op reaches an AI provider and the transport refuses every unregistered URL"
    requirement: MAP-02
    verification:
      - kind: unit
        ref: "tests/replay/test_golden.py#test_replay_reproduces_golden[eligibility_verdicts::*,scoring::*,scan_arrivals::*]"
        status: pass
      - kind: unit
        ref: "tests/replay/test_golden.py#test_scan_transport_refuses_unknown_urls"
        status: pass
      - kind: unit
        ref: "tests/replay/test_golden.py#test_pins_are_restored_after_use"
        status: pass
    human_judgment: false
  - id: D3
    description: "digest golden (4 cases, Markdown stored as a JSON string, file_matches_return true) and the gate drafts and fact sheet, registered in MANIFEST with status awaiting_private_run until plan 11-05"
    requirement: MAP-02
    verification:
      - kind: unit
        ref: "tests/replay/test_golden.py#test_gate_inputs_are_registered"
        status: pass
      - kind: unit
        ref: "tests/replay/test_golden.py#test_digest_golden_stores_markdown_as_json_and_matches_the_written_file"
        status: pass
    human_judgment: false
  - id: D4
    description: "manifest integrity: a flipped golden byte, an unlisted file, a changed producer blob, a wrong replay mode, awaiting for a synthetic class and an unlisted Family B class are each reported; --check --all exits 0 on the committed state"
    requirement: MAP-02
    verification:
      - kind: unit
        ref: "tests/replay/test_golden.py#test_manifest_has_no_problems"
        status: pass
      - kind: integration
        ref: "python tests/replay/generate_golden.py --check --all"
        status: pass
    human_judgment: false
  - id: D5
    description: "Family B validator private_golden_problems enforces the record contract; 23 single mutations are each reported, the five lifecycle tests hold before and after plan 11-05 freezes a class"
    requirement: MAP-02
    verification:
      - kind: unit
        ref: "tests/replay/test_golden.py#test_private_golden_validator_rejects_each_defect"
        status: pass
      - kind: unit
        ref: "tests/replay/test_golden.py#test_register_private_family_b_refuses_bad_input"
        status: pass
    human_judgment: false
  - id: D6
    description: "synthetic gate drafts and fact sheet are fictional and do not resemble the maintainer's real profile (whether the planted defects are the right ones for the private gates to catch)"
    requirement: MAP-02
    verification: []
    human_judgment: true
    rationale: "Whether the eight planted defect classes exercise the private gates well can only be judged by running them in plan 11-05; no Kestrel test can assert it"

duration: 40min
completed: 2026-11-09
status: complete
---

# Phase 11 Plan 01: Golden replay with provenance (MAP-02, Track A) Summary

**Five Family A goldens (167 synthetic cases over tools/ at pinned git blobs) replayed exactly under two hash seeds, a MANIFEST that fails on a changed golden byte or producer file, and six awaiting registrations (gate verdicts plus five Family B classes) with a validator whose 23 rules each fire on a single mutation.**

## Performance

- **Duration:** about 40 min
- **Started:** 2026-11-09 (about 15:00Z; the start time was not captured by script)
- **Completed:** 2026-11-09T15:41Z
- **Tasks:** 3
- **Files modified:** 13 created, 0 modified (all under tests/replay/)

## Accomplishments

- **Family A goldens.** Frozen with Python 3.11.15, `PYTHONHASHSEED=0` and `4242` both giving 260 passed:

| Class | Cases | Producers (git blob at generation) |
|-------|-------|------------------------------------|
| dedup_verdicts | 36 | tools/normalize.py `b92a08e9c3ca6175b41981aa22c9d8ef80d1f381`; tools/scrape_resilient.py `190f711eb3da59c0e3a1ceb2219d9f5597bc9f83` |
| eligibility_verdicts | 49 | tools/batch_probe.py `abf760c099c174922f3e67af58cdaafde6a6d65c`; tools/blocklist.py `e54047e9a4bc77726f7a077138c09e5526e92aae`; tools/job_scorer.py `2db48aef685dfecd2d05a529ceaddd79a58a7b0e` |
| scoring | 65 | tools/daily_pipeline.py `c92dcdcf2e14325b692fa86fc28b2dc535f3ec95`; tools/job_scorer.py `2db48aef685dfecd2d05a529ceaddd79a58a7b0e`; tools/local_scorer.py `2764b656a24fe80a78818a60a6fe50042bbc8432` |
| scan_arrivals | 17 | tools/tier0_ats_poller.py `d23f1f49e722b1ea3a91801ba25877c148834112`; tools/germany_jobs.py `e2ab1710790e26fd5ce4f986b0642847248ca9b5` |
| digest | 4 | tools/daily_pipeline.py `c92dcdcf2e14325b692fa86fc28b2dc535f3ec95` |

- **Six awaiting classes** (all `status: awaiting_private_run`, `golden` null, producer `{"the private pipeline": null}`): `gate_verdicts` (inputs synthetic; drafts and fact sheet hashed in `input_files`) and the five Family B classes with `inputs: scrubbed`, `profile_scope: maintainer`, `producer_row: null` and replay `private_dedup_verdicts` exact, `private_eligibility_verdicts` exact, `private_scan_arrivals` shape, `private_scoring` reference, `private_digest` reference. None has a HARNESS entry; `generate_golden.py --class private_scoring` exits 2 and changes nothing.
- **Defect ids the validator guard tests proved** (each a single mutation of a clean sample, the mutated copy reported with the named rule): day_date, at_sign, url_query, raw_company, too_many_rows (201), too_few_rows (19), single_month, duplicate_input_output, single_tier, dream_tier_true, floored_true, missing_scrubbed, wrong_profile_scope, unknown_key (all on private_scoring); too_few_digest_runs (2 runs), digest_markdown_key, digest_footer_text (private_digest); one_sided_dedup (private_dedup_verdicts); single_geo_class, home_location_verbatim, blocked_true, soft_flag_true, config_reason_code (private_eligibility_verdicts). That is 23.
- **Gate verdict validator.** `gate_verdict_problems` is proven against unknown draft_id, bad verdict, duplicate pair, missing pair, bad reason code, empty file, a voice record while `--gates fact`, and an email-shaped string (assembled from fragments at runtime); a narrowed `--gates fact` registration freezes and records `gates` in MANIFEST.
- **Guards that prove they fire:** two mutation probes run against the real files, both with the mutation asserted as applied and the original restored with `cmp`: one flipped golden output byte (5 tests failed: manifest, flipped-byte guard, the replay item, check mode, regeneration), one producer edit (`DREAM_TIER_FLOOR = 8` to `9` in tools/job_scorer.py: 6 failed, including the two floors replay items and the producer-blob check).

## Task Commits

1. **Task 1: Dedup verdicts golden end to end (tracer)** - `0a8e1801` (test)
2. **Task 2: Eligibility, scoring and scan-arrival goldens under pins** - `ae52182d` (test)
3. **Task 3: Digest golden, gate inputs, six awaiting registrations and the Family B validator** - `4bd77dd9` (test)

**Plan metadata:** the `docs(G-2039): complete phase 11 plan 01` commit that carries this file.

The tracer gate: Task 1's `<verify>` is automated only and `HUMAN_VERIFY_MODE` is the default `end-of-phase`, so it was re-run after the commit (tests, both hash seeds, `--check --all`) and passed; expansion proceeded.

## Files Created/Modified

- `tests/replay/_support.py` - `pinned()`, `HARNESS`/`CLASS_PRODUCERS`/`CLASS_PINS`, JSONL and hash helpers, `pii_hits`, `manifest_problems`, `manifest_pending`, `gate_verdict_problems`, `private_golden_problems`, `FAMILY_B_*`, `awaiting_entry`
- `tests/replay/generate_golden.py` - one-shot generator (`--class`, `--all`, `--check`, `--register-awaiting`, `--register-private`, `--producer-row`, `--ledger`, `--dry-run`); not run by CI
- `tests/replay/test_golden.py` - 260 tests: replay (167 items), manifest integrity, PII, pins and transport, generator behaviour, gate and Family B lifecycle, validator guards
- `tests/replay/golden/` - README (two-family contract), MANIFEST.json, five Family A goldens, gate inputs

## Decisions Made

- `pinned()` also pins `batch_probe._CONFIG` from Task 1 (see deviation 1).
- Fictional member lists replace the real ones in three producer modules for the replay only (deviation 2); the producer blob still covers the real lists.
- `producer_commit` differs per class because it records the HEAD at that class's generation; it is recorded, never checked in CI.
- A non-dry-run `--register-private` requires the file to already sit at `golden/{class}.jsonl` for gate_verdicts as well as the Family B classes (the plan stated it for Family B and the 11-05 plan's command already uses that form for the gate).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Geo-config pin needed in Task 1, not Task 2**
- **Found during:** Task 1
- **Issue:** the plan said Task 1 needs no module pins, but `normalize.normalize_title` classifies parenthesised locations through `batch_probe._classify_token`, which reads the maintainer's gitignored `config/geo.yaml` at import. An unpinned dedup golden could differ between a maintainer machine and CI.
- **Fix:** `pinned()` fixes `batch_probe._CONFIG` from the first commit; it is recorded in the dedup class's `pins`.
- **Files modified:** tests/replay/_support.py
- **Committed in:** 0a8e1801

**2. [Rule 2 - Missing critical] Pins beyond the plan sketch so no real company name enters a fixture (D-03)**
- **Found during:** Task 2
- **Issue:** `job_scorer.BLOCKED_COMPANIES` (a tracked literal) and `local_scorer.DREAM_COMPANIES`/`STRONG_COMPANIES` hold real company names; a case can only reach the block, dream and strong branches by naming a member, which would put a real company in a golden.
- **Fix:** `pinned()` replaces those three lists with fictional members for the replay and records two extra pin strings. Consequence: the real list values are covered only by the producer blob, not by an output; the branch logic is exercised.
- **Files modified:** tests/replay/_support.py
- **Committed in:** ae52182d

**3. [Rule 1 - Bug] `daily_pipeline._fallback_score` writes into the repository's tracking folder**
- **Found during:** Task 2
- **Issue:** the function writes `tracking/scraped_scored_<date>.json` on every call, so a replay would write into maintainer data and a CI checkout.
- **Fix:** the harness swaps `PipelineConfig` for a subclass whose `scored_path` is in a temp dir; `test_scoring_replay_never_writes_into_the_tracking_folder` asserts the folder's names and mtimes are unchanged.
- **Files modified:** tests/replay/_support.py, tests/replay/test_golden.py
- **Committed in:** ae52182d

**4. [Rule 3 - Blocking] "A malformed Arbeitsagentur row that is skipped" is not reachable through `_parse_arbeitsagentur_rows`**
- **Found during:** Task 2
- **Issue:** every field read in that function is type-guarded and a non-dict row crashes its own except handler; the skipping of null and scalar rows happens in `_dict_rows` on the fetch path.
- **Fix:** added a second op `parse_arbeitsagentur_page` that runs `_raw_rows` then `_dict_rows` then the parse, the same row handling `fetch_arbeitsagentur` applies to one served page; cases cover null and scalar rows, an absent list and a null body.
- **Files modified:** tests/replay/_support.py, tests/replay/golden/scan_arrivals.jsonl
- **Committed in:** ae52182d

**5. [Rule 1 - Bug] The plan's pin-restore test could not assert "differs inside" for the blocklist regex**
- **Found during:** Task 2
- **Issue:** `re.compile` caches by pattern, so when the loaded blocklist equals the floor (as in CI) the rebuilt regex is the same object.
- **Fix:** `test_pins_are_restored_after_use` sets sentinel values for `_CONFIG`, `_BLOCKED_RE`, `_GEO_PROFILE` and `_utcnow_iso` first, asserts the pinned values inside and the sentinels again after exit (plus an exception-path test).
- **Files modified:** tests/replay/test_golden.py
- **Committed in:** ae52182d

**6. [Rule 2 - Missing critical] Small additions the plan implied but did not name**
- `--register-awaiting` (adds the six awaiting entries without resetting a frozen class), `--golden-dir` (hidden; lets tests run every write path on a tmp copy), `awaiting_entry`, `ledger_row_ids`; `load_jsonl` splits on `"\n"` only because `str.splitlines()` would split inside a JSON string holding U+2028.
- **Committed in:** 0a8e1801, 4bd77dd9

---

**Total deviations:** 6 documented (3 Rule 2, 2 Rule 1 bug, 1 Rule 3 blocking; item 6 groups small Rule 2 additions)
**Impact on plan:** none changes a contract the later plans rely on; every name in the plan's artifact table exists with the stated behaviour.

## Issues Encountered

- A producer-built URL in the scan outputs: for a row with a `referenznummer`, `_parse_arbeitsagentur_rows` emits `https://www.arbeitsagentur.de/jobsuche/jobdetail/{ref}`. That host is the public job agency, not an employer, and the references are synthetic (`SYN-0001`), so no real posting is named; it is the one non-example host in Family A and is flagged here for the 11-05 review rather than rewritten, because rewriting the producer's output would defeat the golden.
- Unrelated: `tools/blocklist.py` prints a `falling back to embedded floor` warning to stderr at import when `config/blocklist.yaml` is absent (as in CI); it is harmless and pre-existing.
- The sandbox refuses some command shapes (chained git, heredocs with long content); commands were split instead. No effect on results.

## Known Stubs

None. No placeholder text, hardcoded empty value flowing to UI, or unwired data source in the files this plan created. Nothing was appended to `.planning/WINDOWS.md`.

## Authentication Gates

None.

## Threat Flags

None. The plan adds tests, goldens and a developer script only; no network endpoint, auth path or schema at a trust boundary. T-11-01 to T-11-04 mitigations are in place: placement first (synthetic only), `pii_hits` on every generation and on every CI run, gitleaks clean (`no leaks found` on `tests/replay` and on all three task commits), pins over gitignored config, `MockTransport` refusing unknown URLs, `block_real_ai_calls` untouched and no op reaching a provider.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 11-05 can freeze each crossed class with `python tests/replay/generate_golden.py --register-private CLASS --file tests/replay/golden/CLASS.jsonl --private-commit SHA [--producer-row P-NN --ledger PATH | --gates ...]`; the lifecycle tests hold in both states, so `tests/replay/test_golden.py` does not need editing. Until `tests/ports/PORT_LEDGER_PRIVATE.yaml` exists, `manifest_pending()` reports a frozen class's `producer_row` as pending and `manifest_problems()` stays clean.
- Plan 11-04 can dry-run its Family B drafts with `--register-private ... --dry-run` now that the validator exists.
- Verification evidence: `pytest tests/replay` 260 passed under both hash seeds, no skips or xfails; `-k "private_golden or register_private_family_b"` 37 passed; `generate_golden.py --check --all` exits 0; full `pytest tests/ -m "not eval"` 5008 passed (24 skipped, all pre-existing, none in tests/replay); `ruff check` and `ruff format --check` clean; both assertion hooks exit 0; `git diff --stat origin/main...HEAD -- src/ frontend/` prints nothing. Not pushed and `review-push` not run (orchestrator owns both).

## Self-Check: PASSED

- All 13 created files exist on disk.
- Commits `0a8e1801`, `ae52182d`, `4bd77dd9` are ancestors of HEAD.
- Measured `commits: 3` from `git rev-list --count 8d5756472950391facd55907f012c847dc3d2025..HEAD` before this file was written.

---
*Phase: 11-map*
*Completed: 2026-11-09*
