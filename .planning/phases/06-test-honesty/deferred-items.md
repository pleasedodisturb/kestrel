# Deferred Items — Phase 06 Plan 01 (G-1383)

Out-of-scope discoveries logged per the executor scope-boundary rule. Not fixed
in this plan.

## npm audit: GHSA-6j4f-fj2g-mc7p (brace-expansion DoS) in frontend/worker/extension

**Found during:** Task 2, plan-level `<verification>` full backend suite run
(`pytest tests/ -q --tb=short -m "not eval"`).

**Symptom:** `tests/test_dep_security.py::test_npm_audit_no_high_or_critical`
fails for `[frontend]`, `[worker]`, `[extension]` — each reports the
`brace-expansion` package's `GHSA-6j4f-fj2g-mc7p` (uncontrolled recursion /
DoS via nested brace groups) as a high-severity finding.

**Why out of scope:** This plan (G-1383/TEST-03/TEST-04) touches only
`pyproject.toml`, `.pre-commit-config.yaml`, and
`tests/test_toolchain_pins.py` — Python toolchain governance. It does not
touch any `package.json`/`package-lock.json` under `frontend/`, `worker/`,
or `extension/`. This is a pre-existing npm-ecosystem advisory unrelated to
the ruff-pin work.

**Recommendation:** A separate Dependabot/npm-audit intake ticket should bump
`brace-expansion` (transitive dependency) across the three affected
lockfiles. Not filed here — follow the project's existing Dependabot intake
pattern.

**Filed 2026-09-30 as G-1856** (Todo, CareerOS Open Source): bump brace-expansion across the three lockfiles; also covers GHSA-qhr7-859c-m2p7 found in the same audit.
