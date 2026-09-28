# Requirements: Kestrel v1.1 (Geo gate to production)

**Defined:** 2026-09-28
**Core Value:** Kestrel's direction stays visible and coherent; for this milestone: the shipped geo engine must actually decide something in production, with one classifier, honest tests and provider failures told apart.
**Linear epic:** G-1790

## v1.1 Requirements

Each requirement maps to exactly one roadmap phase. Phase numbering continues from roadmap-m1 (phases 6 to 10).

### Test honesty (TEST)

- [ ] **TEST-01**: No test file under `tests/` masks an ImportError with a module-level `pytest.skip(allow_module_level=True)`; `tests/test_parse_scoring_response.py` either runs against a relocated parser or is deleted with its dead subject (G-1382)
- [ ] **TEST-02**: A guard test or CI step fails when an import-masking module-level skip is reintroduced (G-1382)
- [ ] **TEST-03**: One ruff version governs pre-commit and CI; a file formatted locally cannot fail `ruff format --check` in CI; the `_alembic` exclude stays (G-1383)
- [ ] **TEST-04**: A test or CI step fails when the pre-commit ruff rev and the pyproject ruff pin drift apart (G-1383)

### Geo gate wiring (GEO)

- [ ] **GEO-01**: A user can enable the geo gate for discovery through `SearchProfile.filters` keys (documented names), which build a `GeoProfile` for `PrefilterConfig.geo_profile` (G-1483)
- [ ] **GEO-02**: When the gate is enabled, each surviving discovered job carries its geo verdict (`geo_class`) persisted on `DiscoveredJob` and returned by the discovery API (G-1483)
- [ ] **GEO-03**: With no geo keys set, prefilter output and discovery results are byte-identical to today, proven by a regression test (G-1483)
- [ ] **GEO-04**: The geo gate's effect is visible where a user reads discovery results (API response documented; frontend shows the class if a discovery results view exists) (G-1483)

### Over-admission rule (RULE)

- [ ] **RULE-01**: A multi-office posting no longer passes the gate on the strength of one eligible desk when the role's own location is ineligible; the chosen rule is documented with its rationale in `.claude/rules/geo-gate.md` or the engine docs (G-1496)
- [ ] **RULE-02**: The secondary-location rescue case (primary "All France", secondary Germany-remote) still passes (G-1496)
- [ ] **RULE-03**: Precision on the 277-item blind set with authoritative offices improves over the 51.5% baseline without recall dropping below 79.1%, recorded in the eval log with the differential table (G-1496)
- [ ] **RULE-04**: The committed benchmark measures the configuration that ships (offices supplied), so the reported numbers match production (G-1496)

### Single authority (UNIF)

- [ ] **UNIF-01**: `tools/batch_probe.py` `geo_classify` and `geo_ok` delegate to `career_os.services.geo` via the profile built from `config/geo.yaml`; the duplicated token vocabularies are deleted or reduced to thin re-exports (G-1485)
- [ ] **UNIF-02**: A differential test pins old-vs-new `geo_classify` verdicts over a fixed location corpus with an explicit allow-list of intended divergences (G-1485)
- [ ] **UNIF-03**: `build_profile` rejects or documents pathological user regexes and `_compile_tokens` skips punctuation-only tokens (G-1485 nits NT-03, NT-05)
- [ ] **UNIF-04**: Every item in `tests/eval/geo/fixtures/blind_items.json` has `desc` cut to the 2500-character engine window, HTML-stripped, with tracking markers and outbound URLs removed (G-1484)
- [ ] **UNIF-05**: Behaviour neutrality of the trim is proven: reference verdicts identical for all 277 items, recorded in `GENERATION_LOG.md`, `reference_assignments.json` regenerated, `pytest tests/eval/geo` green (G-1484)

### Provider preflight (PROV)

- [ ] **PROV-01**: `src/career_os/ai/` providers raise distinct errors for HTTP 402 (no credits) and 429 (rate limit), with distinct retry and fallback behaviour, covered by unit tests (G-1440)
- [ ] **PROV-02**: `tools/preflight_providers.py` checks each configured provider's readiness (key present, endpoint reachable, credits or quota status) without scoring anything, and reports a table with exit code 0 only when every required provider is ready (G-1440)
- [ ] **PROV-03**: The scan workflow docs reference the preflight tool and the 402/429 semantics; pre-push scrub confirms no personal data entered the port (G-1440)

## Future Requirements

Deferred, tracked in Linear, not in this roadmap.

- **REV-01**: Publish review-push records to the PR so CI can verify a review happened (G-1734)
- **GEO-05**: Wire `geo_class` into ranking and the frontend results view beyond display (follow-up after GEO-04 lands)
- **INV-01..08**: Unified feature inventory (deferred since roadmap-m1)

## Out of Scope

| Feature | Reason |
|---------|--------|
| PII purge of public history (G-1448) | Human decision on remediation path after GitHub Support declined |
| MacBook signing and gate install (G-1759) | Machine setup on another Mac, needs the owner at the keyboard |
| Finishing the PII gate fail-closed semantics (G-1449) | Deliberately left open by the owner; decision pending |
| Cross-repo review-record publishing (G-1734) | Review infrastructure, not product; touches terminal-craft |
| New AI providers or scoring changes | Milestone is about the gate and provider error semantics only |

## Traceability

Filled by the roadmapper.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TEST-01 | Phase 6 | Pending |
| TEST-02 | Phase 6 | Pending |
| TEST-03 | Phase 6 | Pending |
| TEST-04 | Phase 6 | Pending |
| GEO-01 | Phase 7 | Pending |
| GEO-02 | Phase 7 | Pending |
| GEO-03 | Phase 7 | Pending |
| GEO-04 | Phase 7 | Pending |
| RULE-01 | Phase 8 | Pending |
| RULE-02 | Phase 8 | Pending |
| RULE-03 | Phase 8 | Pending |
| RULE-04 | Phase 8 | Pending |
| UNIF-01 | Phase 9 | Pending |
| UNIF-02 | Phase 9 | Pending |
| UNIF-03 | Phase 9 | Pending |
| UNIF-04 | Phase 9 | Pending |
| UNIF-05 | Phase 9 | Pending |
| PROV-01 | Phase 10 | Pending |
| PROV-02 | Phase 10 | Pending |
| PROV-03 | Phase 10 | Pending |

**Coverage:**
- v1.1 requirements: 20 total
- Mapped to phases: 20
- Unmapped: 0 ✓

---
*Requirements defined: 2026-09-28*
*Last updated: 2026-09-28 after initial definition*
