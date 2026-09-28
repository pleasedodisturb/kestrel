# Roadmap: Kestrel

## Milestones

- ✅ **roadmap-m1 (Public Roadmap)** - Phases 1-5 (shipped 2026-05-07) - see [archive](milestones/roadmap-m1-ROADMAP.md)
- 🚧 **v1.1 (Geo gate to production)** - Phases 6-10 (in progress) - Linear epic G-1790

## Phases

<details>
<summary>✅ roadmap-m1 (Public Roadmap) (Phases 1-5) - SHIPPED 2026-05-07</summary>

- [ ] Phase 1: Feature Inventory (0/1 plans, deferred; intent absorbed into Phase 4 deep dives, INV-01..08 remain deferred)
- [x] Phase 2: Roadmap Foundation (2/2 plans, completed 2026-04-25)
- [x] Phase 3: Forward Vision (2/2 plans, completed 2026-04-26)
- [x] Phase 4: Milestone Deep Dives (2/2 plans, completed 2026-04-27)
- [x] Phase 5: Contributor Experience (2/2 plans, completed 2026-05-07)

Full archive: `.planning/milestones/roadmap-m1-ROADMAP.md`
Audit: `.planning/milestones/roadmap-m1-MILESTONE-AUDIT.md`

</details>

### 🚧 v1.1 Geo gate to production (In Progress)

**Milestone goal:** Make the shipped geo engine actually decide something in production, with one classifier, honest tests and provider failures that are told apart. Linear epic G-1790 (children G-1382, G-1383, G-1483, G-1496, G-1484, G-1485, G-1440).

Phase numbering continues from roadmap-m1 (ended at Phase 5). Every phase below ships as its own PR on a `<ticket>/<slug>` branch: commits use conventional-commit format scoped to the ticket, `review-push run` then `review-push sign` before push, one PR per phase, merge only on green CI.

- [ ] **Phase 6: Test honesty** - No test masks an ImportError behind a module-level skip; one ruff version governs dev and CI
- [ ] **Phase 7: Wire the geo gate** - `SearchProfile.filters` enables the gate; `geo_class` is persisted and visible in discovery results; defaults unchanged
- [ ] **Phase 8: Over-admission rule** - Multi-office postings stop passing the gate on one eligible desk; the rule is chosen by measurement on the 277-item blind set
- [ ] **Phase 9: Single authority** - `tools/batch_probe.py` delegates to the package geo engine; the blind-set fixture is trimmed with a behaviour-neutrality proof
- [ ] **Phase 10: Provider preflight** - Providers tell "no credits" apart from "rate limited"; a preflight tool reports provider readiness before any scan

## Phase Details

### Phase 6: Test honesty
**Goal**: The test suite tells the truth: no test silently vanishes behind a masked import error, and the formatter used locally cannot disagree with the one CI enforces.
**Depends on**: Phase 5 (roadmap-m1, shipped)
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04
**Linear tickets**: G-1382, G-1383
**Success Criteria** (what must be TRUE):
  1. `pytest -rs tests/` reports zero module-level skips caused by ImportError-masking `pytest.skip(allow_module_level=True)` calls
  2. `tests/test_parse_scoring_response.py` either exercises a real, importable parser or has been deleted along with its dead subject; `pytest --collect-only` shows no collection error and no skip for that path
  3. A guard test or CI step fails on demand when an import-masking module-level skip is reintroduced (proven by a deliberate reintroduction in a scratch check)
  4. `ruff format --check src/ tests/` (the CI invocation) and the local pre-commit `ruff-format` hook agree on every file, because one ruff version is pinned in both `.pre-commit-config.yaml` and `pyproject.toml`; the `_alembic` exclude is preserved
  5. A test or CI step fails when the pre-commit ruff rev and the pyproject ruff pin are made to drift apart (proven by a deliberate drift in a scratch check)
**Plans**: TBD
**Git delivery**: Branch `G-1382/test-honesty` off main; commits scoped per ticket (`test(G-1382): ...`, `chore(G-1383): ...`); `review-push run` then `review-push sign` before push; one PR for the phase; merge only when CI is green.

### Phase 7: Wire the geo gate
**Goal**: A user can turn geo-eligibility filtering on per search profile and see the verdict on every surviving job, with zero change in behaviour for profiles that leave it off.
**Depends on**: Phase 6
**Requirements**: GEO-01, GEO-02, GEO-03, GEO-04
**Linear tickets**: G-1483
**Success Criteria** (what must be TRUE):
  1. Setting the documented geo keys on `SearchProfile.filters` builds a `GeoProfile` that reaches `PrefilterConfig.geo_profile` (an integration test constructs a profile from filters and asserts the resulting `GeoProfile`)
  2. With the gate enabled, `DiscoveredJob.geo_class` is persisted for each surviving job and present in the discovery API response body
  3. With no geo keys set on a profile, prefilter output and discovery API results are byte-identical to pre-Phase-7 behaviour, proven by a regression test comparing fixture output before and after
  4. A user reading discovery results, via the API response (documented) and via the frontend results view if one exists, can see each job's `geo_class`
**Plans**: TBD
**Git delivery**: Branch `G-1483/wire-geo-gate` off main; conventional commits scoped `feat(G-1483): ...`; `review-push run` then `review-push sign` before push; one PR; merge only when CI is green.
**UI hint**: yes

### Phase 8: Over-admission rule
**Goal**: A multi-office global company no longer passes the gate on the strength of one eligible desk when the role's own location is ineligible, and the choice of rule is backed by measurement, not guesswork.
**Depends on**: Phase 7
**Requirements**: RULE-01, RULE-02, RULE-03, RULE-04
**Linear tickets**: G-1496
**Planning note**: Run `/gsd-discuss-phase 8` before `/gsd-plan-phase 8`. The over-admission rule is a design decision that must be re-measured against the 277-item blind set (RULE-03, RULE-04) before an approach is committed to; do not skip straight to planning.
**Success Criteria** (what must be TRUE):
  1. A multi-office job posting whose own role location is ineligible no longer passes the gate solely because another listed office is eligible, proven by a regression test on a crafted multi-office fixture
  2. The secondary-location rescue case (primary "All France", secondary Germany-remote) still passes after the rule change
  3. Precision on the 277-item blind set with authoritative offices improves over the 51.5% baseline while recall stays at or above 79.1%, recorded in the eval log with a differential table
  4. The committed benchmark run measures the exact configuration that ships (offices supplied), so the published numbers match production behaviour
  5. The chosen rule and its rationale are documented in `.claude/rules/geo-gate.md` or the engine docs, readable by the next contributor
**Plans**: TBD
**Git delivery**: Branch `G-1496/over-admission-rule` off main; conventional commits scoped `feat(G-1496): ...`; `review-push run` then `review-push sign` before push; one PR; merge only when CI is green.

### Phase 9: Single authority
**Goal**: There is exactly one geo classifier in the codebase; the legacy `tools/batch_probe.py` duplicate delegates to the package engine, and the blind-set fixture is trimmed to the engine's real input window without changing a single reference verdict.
**Depends on**: Phase 8
**Requirements**: UNIF-01, UNIF-02, UNIF-03, UNIF-04, UNIF-05
**Linear tickets**: G-1485, G-1484
**Success Criteria** (what must be TRUE):
  1. `tools/batch_probe.py`'s `geo_classify` and `geo_ok` call into `career_os.services.geo` via a profile built from `config/geo.yaml`; the old duplicated token vocabularies are gone or reduced to thin re-exports
  2. A differential test pins old-vs-new `geo_classify` verdicts across a fixed location corpus, with any intended divergence captured in an explicit allow-list, and passes in CI
  3. `build_profile` rejects or documents pathological user regexes, and `_compile_tokens` skips punctuation-only tokens, both covered by unit tests
  4. Every item in `tests/eval/geo/fixtures/blind_items.json` has `desc` capped at the 2500-character engine window, HTML-stripped, with tracking markers and outbound URLs removed
  5. `pytest tests/eval/geo` is green with `reference_assignments.json` regenerated and all 277 reference verdicts unchanged from before the trim, recorded in `GENERATION_LOG.md`
**Plans**: TBD
**Git delivery**: Branch `G-1485/single-geo-authority` off main; conventional commits scoped per ticket (`refactor(G-1485): ...`, `chore(G-1484): ...`); `review-push run` then `review-push sign` before push; one PR for the phase; merge only when CI is green.

### Phase 10: Provider preflight
**Goal**: Provider failures are told apart before they burn budget or silently degrade discovery: "no credits" is distinguished from "rate limited," and a preflight check reports readiness before any scan runs.
**Depends on**: Phase 9
**Requirements**: PROV-01, PROV-02, PROV-03
**Linear tickets**: G-1440
**Success Criteria** (what must be TRUE):
  1. Each AI provider in `src/career_os/ai/` raises a distinct error type for HTTP 402 (no credits) versus 429 (rate limited), each with its own retry and fallback behaviour, covered by unit tests per provider
  2. `tools/preflight_providers.py` checks every configured provider's readiness (key present, endpoint reachable, credits or quota status) without scoring a single job, and prints a readiness table
  3. The preflight tool exits 0 only when every required provider is ready, and non-zero otherwise, proven by a test with a mocked not-ready provider
  4. The scan workflow docs reference the preflight tool and explain the 402-vs-429 semantics to a reader; the pre-push scrub confirms no personal data entered the port
**Plans**: TBD
**Git delivery**: Branch `G-1440/provider-preflight` off main; conventional commits scoped `feat(G-1440): ...`; `review-push run` then `review-push sign` before push; one PR; merge only when CI is green.

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|-----------------|--------|-----------|
| 1. Feature Inventory | roadmap-m1 | 0/1 | Deferred to v1.1 | - |
| 2. Roadmap Foundation | roadmap-m1 | 2/2 | Complete | 2026-04-25 |
| 3. Forward Vision | roadmap-m1 | 2/2 | Complete | 2026-04-26 |
| 4. Milestone Deep Dives | roadmap-m1 | 2/2 | Complete | 2026-04-27 |
| 5. Contributor Experience | roadmap-m1 | 2/2 | Complete | 2026-05-07 |
| 6. Test honesty | v1.1 | 0/TBD | Not started | - |
| 7. Wire the geo gate | v1.1 | 0/TBD | Not started | - |
| 8. Over-admission rule | v1.1 | 0/TBD | Not started | - |
| 9. Single authority | v1.1 | 0/TBD | Not started | - |
| 10. Provider preflight | v1.1 | 0/TBD | Not started | - |
