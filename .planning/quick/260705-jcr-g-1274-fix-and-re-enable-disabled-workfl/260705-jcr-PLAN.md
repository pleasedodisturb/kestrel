---
phase: quick
plan: 260705-jcr
type: execute
wave: 1
depends_on: []
files_modified:
  - .github/workflows/scorecard.yml
  - .github/workflows/daily-scan.yml
  - .github/workflows/release-checks.yml
  - frontend/package.json
  - Dockerfile
autonomous: true
requirements: [G-1274]

must_haves:
  truths:
    - "scorecard.yml pins ossf/scorecard-action to a resolvable ref (v2.4.3 SHA)"
    - "daily-scan.yml scheduled runs are skipped unless explicitly enabled via DAILY_SCAN_ENABLED"
    - "release-checks size-limit step passes because frontend/package.json declares the size-limit config + devDeps"
    - "Docker image has no fixable CRITICAL/HIGH Trivy findings (libssh2, wheel, jaraco.context upgraded)"
  artifacts:
    - path: .github/workflows/scorecard.yml
      provides: "pinned scorecard-action"
      contains: "99c09fe975337306107572b4fdf4db224cf8e2f2"
    - path: frontend/package.json
      provides: "size-limit config + devDeps"
      contains: "size-limit"
    - path: Dockerfile
      provides: "hardened runtime stage"
      contains: "apt-get upgrade"
  key_links:
    - from: .github/workflows/release-checks.yml
      to: frontend/package.json
      via: "npx size-limit reads size-limit config"
      pattern: "size-limit"
---

<objective>
Fix the three disabled Kestrel GitHub workflows (G-1274) so they can be re-enabled green: pin `ossf/scorecard-action`, guard `daily-scan.yml` scheduled runs, and repair `release-checks.yml` (size-limit config + Dockerfile Trivy vulnerabilities).

Purpose: The three workflows currently fail on every run (scorecard: bad tag in 5s; daily-scan: 429s + failure-rate gate every weekday; release-checks: size-limit crash + 6 fixable Trivy CVEs). Re-enabling them green restores CI signal and improves the OpenSSF Scorecard.
Output: Corrected workflow YAML, frontend size-limit config, and hardened Dockerfile — all changes local; verified locally where tooling allows.

Scope note: Re-enabling workflows on GitHub (`gh workflow enable`) and confirming green runs is OUT OF SCOPE — that happens after PR review + merge. This plan covers local changes + local verification only.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@./CLAUDE.md

Verified facts (do not re-verify — plan from these):
- scorecard-action latest release v2.4.3, SHA `99c09fe975337306107572b4fdf4db224cf8e2f2`. OpenSSF style = full SHA pin with `# v2.4.3` comment (improves Pinned-Dependencies score).
- daily-scan job name is `daily-scan` (line 77). Header comment block already documents secrets/vars — add DAILY_SCAN_ENABLED there.
- Current frontend bundle: `dist/assets/index-*.js` = 982.00 kB (273.73 kB gzip); `index-*.css` = 44.08 kB (8.67 kB gzip). @size-limit/file budgets are gzip by default.
- Trivy findings (severity CRITICAL,HIGH; ignore-unfixed:true; all fixable):
  - `libssh2-1t64` 1.11.1-1 → 1.11.1-1+deb13u1 (CVE-2026-55200 CRITICAL, CVE-2026-55199 HIGH, CVE-2026-7598 HIGH)
  - `wheel` 0.45.1 → 0.46.2 (CVE-2026-24049 HIGH) — site-packages + vendored in setuptools/_vendor
  - `jaraco.context` 5.3.0 → 6.1.0 (CVE-2026-23949 HIGH) — vendored in setuptools/_vendor
- Local tooling: `docker` available; `trivy` and `actionlint` NOT installed. Install trivy via `brew install trivy` for local verify, or defer Trivy verification to CI.
- Branch `G-1274/fix-workflows` already checked out. Conventional commits with body, scope `G-1274`.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Pin scorecard-action and guard daily-scan scheduled runs</name>
  <files>.github/workflows/scorecard.yml, .github/workflows/daily-scan.yml</files>
  <action>
In scorecard.yml, change the `Run analysis` step (line 28) from `uses: ossf/scorecard-action@v2` to `uses: ossf/scorecard-action@99c09fe975337306107572b4fdf4db224cf8e2f2 # v2.4.3` — full SHA pin with version comment per OpenSSF Pinned-Dependencies guidance. Leave all other pins (they already use tag pins per repo convention) untouched.

In daily-scan.yml, add a job-level guard to the `daily-scan` job (line 77) so scheduled runs only proceed where explicitly enabled: add `if: github.event_name == 'workflow_dispatch' || vars.DAILY_SCAN_ENABLED == 'true'` between the `daily-scan:` key and `runs-on:` (before line 78). This keeps manual `workflow_dispatch` always working while skipping the cron run in clones/upstream where the repo variable is unset (avoids the 429/failure-rate failures). Then document the new variable in the header comment block under "Optional variables" (near line 34-38): add a line `#   DAILY_SCAN_ENABLED      - Set to "true" to enable the scheduled cron run.` matching the existing comment style.

Commit: `fix(G-1274): pin scorecard-action to v2.4.3 and guard daily-scan cron`.
  </action>
  <verify>
    <automated>command -v actionlint >/dev/null 2>&1 &amp;&amp; actionlint .github/workflows/scorecard.yml .github/workflows/daily-scan.yml || python3 -c "import yaml,sys; [yaml.safe_load(open(f)) for f in ['.github/workflows/scorecard.yml','.github/workflows/daily-scan.yml']]; print('yaml-ok')"</automated>
  </verify>
  <done>scorecard.yml pins the v2.4.3 SHA with comment; daily-scan job has the `if:` guard and DAILY_SCAN_ENABLED is documented in the header; both files parse as valid YAML (or pass actionlint if installed).</done>
</task>

<task type="auto">
  <name>Task 2: Add size-limit config to frontend and simplify the release-checks step</name>
  <files>frontend/package.json, .github/workflows/release-checks.yml</files>
  <action>
In frontend/package.json, add `size-limit` and `@size-limit/file` to `devDependencies` (use current stable versions; a `size` script already references size-limit). Add a top-level `"size-limit"` config array with realistic gzip budgets that have headroom over current sizes (JS is 273.73 kB gzip, CSS 8.67 kB gzip): one entry `{ "path": "dist/assets/index-*.js", "limit": "350 kB" }` and one `{ "path": "dist/assets/index-*.css", "limit": "15 kB" }`. @size-limit/file measures gzip by default, so these are gzip budgets. Run `cd frontend && npm install --save-dev --legacy-peer-deps size-limit @size-limit/file` to update package-lock.json, then per the npm supply-chain rule run `npm audit signatures`.

In release-checks.yml, simplify the `Bundle size check` step (lines 68-71) to just `run: npx size-limit` — remove the `npm install --no-save ... size-limit @size-limit/file` line, since the deps now install via `npm ci` (line 63) and size-limit rejects --no-save installs.

Commit: `fix(G-1274): add size-limit config so release-checks bundle gate passes`.
  </action>
  <verify>
    <automated>cd frontend &amp;&amp; npm ci --legacy-peer-deps &amp;&amp; npm run build &amp;&amp; npx size-limit</automated>
  </verify>
  <done>frontend/package.json has size-limit + @size-limit/file devDeps and a size-limit config with 350 kB JS / 15 kB CSS gzip budgets; package-lock.json updated; `npx size-limit` passes locally under budget; release-checks step is `npx size-limit` only; `npm audit signatures` clean.</done>
</task>

<task type="auto">
  <name>Task 3: Harden Dockerfile runtime stage against fixable Trivy CVEs</name>
  <files>Dockerfile</files>
  <action>
In the runtime stage (stage 2, `python:3.11-slim`), fix all 6 fixable CRITICAL/HIGH Trivy findings. Do NOT weaken the Trivy gate in release-checks.yml (keep exit-code 1, severity CRITICAL,HIGH, ignore-unfixed) and do NOT add .trivyignore entries.

1. libssh2 (Debian base): in the existing `apt-get` block (lines 35-37), add `apt-get upgrade -y` after `apt-get update` (targeted `--only-upgrade libssh2-1t64` also acceptable) so `libssh2-1t64` moves to 1.11.1-1+deb13u1, keeping the `rm -rf /var/lib/apt/lists/*` cleanup at the end.
2. Python build tooling (wheel 0.45.1 → 0.46.2, jaraco.context 5.3.0 → 6.1.0 vendored in setuptools/_vendor): before or as part of the pip install (line 44), upgrade the tooling — `pip install --no-cache-dir -U pip setuptools wheel` — so the runtime image ships the fixed `wheel` and a setuptools that vendors fixed `jaraco.context`. Upgrade (not uninstall) is the safe default; do not remove setuptools/wheel unless verified nothing at runtime imports pkg_resources.

Commit: `fix(G-1274): upgrade Docker base + build tooling to clear Trivy CVEs`.
  </action>
  <verify>
    <automated>docker build -t kestrel:ci . &amp;&amp; { command -v trivy >/dev/null 2>&1 &amp;&amp; trivy image --severity CRITICAL,HIGH --ignore-unfixed --exit-code 1 kestrel:ci || echo "TRIVY NOT INSTALLED — verify in CI (brew install trivy to check locally)"; }</automated>
  </verify>
  <done>Docker image builds; if trivy is installed, `trivy image --severity CRITICAL,HIGH --ignore-unfixed --exit-code 1 kestrel:ci` exits 0 (no fixable findings). If trivy is unavailable locally, image builds cleanly and Trivy verification is deferred to the CI run. Trivy gate in release-checks.yml unchanged; no .trivyignore added.</done>
</task>

</tasks>

<verification>
- `python3 -c` YAML parse (or actionlint) passes for all three workflow files.
- `cd frontend && npm ci --legacy-peer-deps && npm run build && npx size-limit` passes under budget.
- `docker build -t kestrel:ci .` succeeds; Trivy scan (local if installed, else CI) shows zero fixable CRITICAL/HIGH findings.
- No unit-test surface: workflow YAML and package.json changes are config-only. Validation is via actionlint/YAML parse + local builds, per the stated constraint.
</verification>

<success_criteria>
- scorecard.yml pins ossf/scorecard-action@99c09fe... # v2.4.3.
- daily-scan.yml `daily-scan` job guarded by DAILY_SCAN_ENABLED (documented in header).
- frontend/package.json has size-limit config + devDeps; release-checks bundle step is `npx size-limit`; passes under budget.
- Dockerfile upgraded (apt upgrade for libssh2; pip -U setuptools wheel) so Trivy finds no fixable CRITICAL/HIGH.
- All commits on branch G-1274/fix-workflows, conventional format with bodies. GitHub re-enable/green-run verification left for post-merge (out of scope).
</success_criteria>

<output>
Create `.planning/quick/260705-jcr-g-1274-fix-and-re-enable-disabled-workfl/260705-jcr-SUMMARY.md` when done.
</output>
