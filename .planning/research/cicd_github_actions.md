# CI/CD GitHub Actions Research: Kestrel

**Domain:** GitHub Actions CI/CD for solo agentic development
**Researched:** 2026-04-16
**Overall confidence:** HIGH (most findings from official GitHub docs and changelogs)

---

## Table of Contents

1. [Current State Assessment](#current-state-assessment)
2. [Workflow Optimization](#workflow-optimization)
3. [Cost Optimization](#cost-optimization)
4. [Monorepo CI Patterns](#monorepo-ci-patterns)
5. [Security in CI](#security-in-ci)
6. [Speed Optimization](#speed-optimization)
7. [Agentic Development Patterns](#agentic-development-patterns)
8. [Emerging Best Practices 2025-2026](#emerging-best-practices-2025-2026)
9. [Recommended Improvements](#recommended-improvements)

---

## Current State Assessment

Kestrel already has a mature CI setup across 12 workflow files:

| Workflow | Trigger | What It Does | Assessment |
|----------|---------|--------------|------------|
| `ci.yml` | push/PR to main | Backend lint+test+audit, Frontend lint+test+audit, SonarCloud, actionlint | **Good** -- core pipeline |
| `codeql.yml` | push/PR/weekly | CodeQL for Python + JS/TS | **Good** -- standard SAST |
| `commitlint.yml` | PR to main | Conventional commits enforcement | **Good** -- essential for agentic dev |
| `daily-scan.yml` | cron Mon-Fri 07:00 | Job discovery + AI scoring | **Good** -- product feature |
| `docker-publish.yml` | ? | Docker image publishing | Not reviewed in detail |
| `publish-npm.yml` | ? | NPM package publishing | Not reviewed in detail |
| `publish.yml` | ? | PyPI publishing | Not reviewed in detail |
| `release-please.yml` | push to main | Automated releases via Release Please | **Good** -- uses GitHub App token |
| `scorecard.yml` | push to main/weekly | OpenSSF Scorecard | **Good** -- supply chain security |
| `secret-scan.yml` | push/PR/weekly | Gitleaks secret detection | **Good** -- defense in depth |
| `workflow-lint.yml` | push/PR (workflow paths only) | actionlint + zizmor | **Excellent** -- already path-filtered |

**What's already done well:**
- Concurrency with `cancel-in-progress` on non-main branches
- Pip caching via `setup-python` cache option
- npm caching via `setup-node` cache option
- SHA-pinned critical actions (checkout, release-please, SonarCloud)
- `npm audit signatures` (supply chain verification)
- `pip-audit` with ignore file
- Artifact retention set to 1 day (cost-conscious)
- Separate workflow-lint with path filtering

**Gaps to address:**
- No path filtering on main CI -- backend changes trigger frontend tests and vice versa
- No parallel test execution (pytest-xdist)
- No reusable workflows or composite actions (some duplication between ci.yml and workflow-lint.yml for actionlint)
- No auto-merge for Dependabot
- No OIDC for any cloud deploys (not needed yet, but worth noting)
- SonarCloud job always runs even when coverage artifacts are missing

---

## Workflow Optimization

### Caching Strategies

**Current state:** Basic dependency caching via setup-python and setup-node built-in cache options. This is fine for now.

**Advanced caching patterns when needed:**

```yaml
# Cache pip wheels separately from venv for faster restores
- uses: actions/cache@v4
  with:
    path: |
      ~/.cache/pip
      .venv
    key: pip-${{ runner.os }}-${{ hashFiles('pyproject.toml') }}
    restore-keys: |
      pip-${{ runner.os }}-
```

**When to upgrade:** Only if install times exceed 60s. Current setup-python cache is sufficient for Kestrel's dependency count.

**Cache limits:** 10 GB per repository, entries evicted after 7 days of no access. Kestrel's 1-day artifact retention is already cost-conscious. The cache backend was rewritten in Feb 2025 for better performance ([source](https://github.com/actions/cache)).

### Reusable Workflows vs Composite Actions

**Key distinction:**
- **Reusable workflows** = entire pipelines (multiple jobs). Called with `uses: ./.github/workflows/reusable.yml`
- **Composite actions** = shared step sequences within a job. Called with `uses: ./.github/actions/my-action`

**Recommendation for Kestrel:** Don't over-abstract. Solo developer with 12 workflows -- the overhead of maintaining reusable workflow interfaces exceeds the DRY benefit. The only worthwhile extraction is if the same steps appear in 3+ workflows.

One useful composite action: a "setup-python-with-deps" action that combines setup-python + pip install + config copy:

```yaml
# .github/actions/setup-backend/action.yml
name: Setup Backend
description: Install Python deps and prepare test config
inputs:
  python-version:
    default: "3.11"
runs:
  using: composite
  steps:
    - uses: actions/setup-python@v6
      with:
        python-version: ${{ inputs.python-version }}
        cache: pip
    - run: |
        python -m pip install --upgrade 'pip>=26.0'
        pip install -e ".[dev]"
      shell: bash
    - run: |
        mkdir -p config data
        cp config/personal.yaml.example config/personal.yaml
      shell: bash
```

**Important:** Every `run` step in a composite action MUST specify `shell:` -- composite actions don't inherit the workflow's default shell ([source](https://docs.github.com/en/actions/concepts/workflows-and-actions/reusing-workflow-configurations)).

### Concurrency Controls

**Current state:** Already good.

```yaml
concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}
```

This cancels superseded runs on feature branches while letting main runs complete. No changes needed.

**Known gotcha with Dependabot:** When Dependabot opens a PR and adds labels simultaneously, it can trigger multiple runs. Combined with `cancel-in-progress: true`, the wrong run can be cancelled, leaving status checks stuck ([source](https://github.com/dependabot/dependabot-core/issues/10074)). If adding Dependabot auto-merge, use a separate concurrency group keyed on `github.head_ref`.

---

## Cost Optimization

### Free Tier Limits (as of 2026)

| Plan | Free Minutes/Month | Storage | Public Repos |
|------|-------------------|---------|--------------|
| GitHub Free | 2,000 min | 500 MB | **Unlimited free** |
| GitHub Pro | 3,000 min | 1 GB | **Unlimited free** |

**Critical fact for Kestrel:** Since Kestrel is a public repository, all standard GitHub-hosted runner usage is **free and unlimited**. The 2,000 minute limit only applies to private repositories.

Sources: [GitHub Billing Docs](https://docs.github.com/en/actions/concepts/billing-and-usage), [2026 Pricing Changes](https://resources.github.com/actions/2026-pricing-changes-for-github-actions/)

### 2026 Pricing Changes

- **January 1, 2026:** GitHub-hosted runner prices dropped ~39% across all sizes
- **Self-hosted runner fee ($0.002/min):** Originally planned for March 2026, now **on hold indefinitely** after community backlash. GitHub says they're "re-evaluating" but haven't cancelled the idea
- **Public repos remain free** for both GitHub-hosted and self-hosted runners

Source: [GitHub Changelog](https://github.blog/changelog/2025-12-16-coming-soon-simpler-pricing-and-a-better-experience-for-github-actions/)

### Cost Recommendations for Kestrel

1. **Stay on GitHub-hosted runners.** Public repo = free. Self-hosted runners add maintenance burden and the pricing uncertainty.
2. **Keep artifact retention at 1 day** (already done). Coverage XMLs are consumed by SonarCloud in the same workflow run.
3. **Add path filtering** (see Monorepo section). This is the single biggest cost/time saver -- avoids running ~50% of CI on irrelevant changes.
4. **Don't use larger runners** unless a specific job consistently exceeds 10 minutes. The 2-core `ubuntu-latest` is free; larger runners cost money even on public repos.

### When to Consider Self-Hosted Runners

Only if:
- Build times consistently exceed 15+ minutes (not Kestrel's case)
- You need GPU access for ML workloads
- You need persistent caches that survive across runs (Docker layer caches)
- You need access to private network resources

**Verdict:** Not needed for Kestrel. Stay GitHub-hosted.

---

## Monorepo CI Patterns

### The Problem

Kestrel's `ci.yml` runs backend, frontend, and actionlint jobs on every push/PR to main regardless of what changed. A README edit triggers pytest. A Python-only change triggers `npm ci` + Vitest.

### Solution: dorny/paths-filter

The standard approach is a "detect changes" job that sets outputs consumed by downstream jobs:

```yaml
jobs:
  changes:
    name: Detect changes
    runs-on: ubuntu-latest
    outputs:
      backend: ${{ steps.filter.outputs.backend }}
      frontend: ${{ steps.filter.outputs.frontend }}
      workflows: ${{ steps.filter.outputs.workflows }}
    steps:
      - uses: actions/checkout@v6
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            backend:
              - 'src/**'
              - 'tests/**'
              - 'pyproject.toml'
              - 'alembic/**'
              - 'alembic.ini'
              - 'config/**'
            frontend:
              - 'frontend/**'
            workflows:
              - '.github/**'

  backend:
    name: Backend (Python 3.11)
    needs: changes
    if: ${{ needs.changes.outputs.backend == 'true' || github.ref == 'refs/heads/main' }}
    runs-on: ubuntu-latest
    # ... existing steps ...

  frontend:
    name: Frontend (React)
    needs: changes
    if: ${{ needs.changes.outputs.frontend == 'true' || github.ref == 'refs/heads/main' }}
    runs-on: ubuntu-latest
    # ... existing steps ...
```

Source: [dorny/paths-filter](https://github.com/dorny/paths-filter)

**Why `|| github.ref == 'refs/heads/main'`:** Always run everything on main merges as a safety net. Path filtering is for PR feedback speed.

**Important caveat with required status checks:** If "Backend" is a required check and the job is skipped (because only frontend changed), the PR will be blocked. Solutions:

1. **Use `paths-ignore` at workflow level** instead (simpler but less granular)
2. **Always run the job but skip expensive steps** (the job still "passes")
3. **Use a merge queue** (`merge_group` event, which Kestrel already triggers on)
4. **Configure required checks as "Required when present"** -- this is available in branch rulesets (not legacy branch protection)

**Recommendation:** Use approach 4 (rulesets with "Required when present") + dorny/paths-filter. This gives clean path filtering without blocking PRs.

Source: [GitHub Community Discussion](https://github.com/orgs/community/discussions/26251)

### Estimated Impact

Well-configured path filtering reduces CI time by 70-90% for PRs that only touch one component. For Kestrel:
- Backend-only PR: skips ~3 min of frontend CI
- Frontend-only PR: skips ~2-3 min of backend CI + migration checks
- Docs-only PR: skips everything except linting

---

## Security in CI

### What Kestrel Already Has (Good)

| Security Layer | Implementation | Status |
|---------------|----------------|--------|
| Secret scanning | Gitleaks (`secret-scan.yml`) | Active |
| SAST | CodeQL for Python + JS/TS | Active |
| Dependency audit (Python) | pip-audit with ignore file | Active |
| Dependency audit (JS) | npm audit + npm audit signatures | Active |
| Supply chain scoring | OpenSSF Scorecard | Active |
| PII leak detection | Custom grep patterns | Active |
| Workflow linting | actionlint + zizmor | Active |
| Commit signing | SSH key signing (per global config) | Active |
| Action pinning | SHA-pinned for critical actions | Partial |

### What to Add

#### 1. Pin ALL Actions to SHA (not just critical ones)

Currently mixed -- some use `@v6` (mutable tag), some use SHA pins. Mutable tags can be force-pushed by compromised action maintainers.

```yaml
# BAD: mutable tag
- uses: actions/setup-python@v6

# GOOD: SHA pin with version comment
- uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v6.0.0
```

**Tool to automate this:** [pin-github-action](https://github.com/mheap/pin-github-action) or [StepSecurity's secure-repo](https://github.com/step-security/secure-repo).

GitHub's new **Immutable Actions** feature (coming 2026) will make this less critical over time, but SHA pinning is the standard until then.

#### 2. Add `permissions` to All Workflows

Kestrel already has `permissions: contents: read` on most workflows. Ensure every workflow has explicit permissions (principle of least privilege). The `ci.yml` top-level `permissions` is good.

#### 3. Artifact Attestations (for releases)

When publishing Docker images or Python packages, add build provenance:

```yaml
- uses: actions/attest-build-provenance@v2
  with:
    subject-path: dist/*.whl
```

This provides SLSA Build Level 2 automatically. Combined with a reusable workflow, it achieves Level 3.

Source: [GitHub Artifact Attestations Docs](https://docs.github.com/en/actions/concepts/security/artifact-attestations)

#### 4. OIDC for Cloud Deploys (future)

Not needed now (Kestrel is self-hosted), but when deploying to cloud:

```yaml
permissions:
  id-token: write  # Required for OIDC

steps:
  - uses: aws-actions/configure-aws-credentials@v4
    with:
      role-to-arn: arn:aws:iam::123456789:role/github-actions
      aws-region: us-east-1
```

**No long-lived secrets needed.** The OIDC token is scoped to the specific workflow run.

Source: [GitHub OIDC Docs](https://docs.github.com/en/actions/concepts/security/openid-connect)

### GitHub Actions 2026 Security Roadmap

Three major features coming ([source](https://github.blog/news-insights/product-news/whats-coming-to-our-github-actions-2026-security-roadmap/)):

1. **Deterministic Dependency Locking:** A `dependencies:` section in workflow YAML that locks all direct and transitive action dependencies with commit SHAs. Changes appear as PR diffs. Public preview in 3-6 months.

2. **Policy-Driven Execution Controls:** Workflow protections built into GitHub's ruleset framework. Actor rules (who can trigger), event rules (which events allowed). Centralized policy instead of per-workflow config.

3. **Immutable Publishing Standards:** Actions move from mutable tags to immutable releases. Once published, assets and Git tags can't be changed or deleted. Includes release attestations.

**Action for Kestrel:** No immediate action needed. Keep SHA-pinning as the bridge strategy until immutable actions GA.

---

## Speed Optimization

### Current Bottlenecks (estimated)

| Step | Estimated Time | Optimization |
|------|---------------|-------------|
| Backend: pip install | ~45-60s | Already cached. Could pre-build venv. |
| Backend: pytest | ~30-60s | pytest-xdist if grows past 2 min |
| Backend: Alembic roundtrip | ~10-15s | Unavoidable (validates migrations) |
| Backend: API smoke test | ~10-15s | Unavoidable (validates startup) |
| Backend: pip-audit | ~15-20s | Could cache audit DB |
| Frontend: npm ci | ~30-45s | Already cached |
| Frontend: vitest | ~20-30s | Fine for now |
| Frontend: npm audit | ~5-10s | Fine |
| SonarCloud | ~2-3 min | Runs after backend+frontend, could be made optional |

**Total estimated wall-clock:** ~5-7 min for full pipeline (backend + frontend parallel, then SonarCloud serial).

### pytest-xdist for Python

Not needed yet (test suite likely < 2 minutes), but when it grows:

```bash
# In pyproject.toml [project.optional-dependencies] dev section:
# "pytest-xdist>=3.5.0"

# In CI:
pytest tests/ -v -n auto --tb=short --cov=src/career_os --cov-report=xml
```

The `-n auto` flag detects available cores (2 on `ubuntu-latest`) and distributes tests. Achieves ~1.5-2x speedup on 2-core runners.

**Caveat:** Tests must not share state (DB, files). Kestrel's tests use fresh SQLite DBs, so this should work. Integration tests that start uvicorn need isolation.

Source: [pytest-xdist](https://github.com/pytest-dev/pytest-xdist)

### Vitest Parallelism

Vitest already runs tests in parallel by default (worker threads). No changes needed unless the frontend test suite grows significantly.

### SonarCloud Optimization

SonarCloud is the longest single job (~2-3 min) and runs serially after backend+frontend. Options:

1. **Make it non-blocking:** Already using `continue-on-error: true` on the scan. Could skip entirely on draft PRs.
2. **Skip on certain paths:** Only run when `src/` or `frontend/src/` changed.
3. **Skip on merge_group:** Already does this (`if: github.event_name != 'merge_group'`).

### Matrix Builds (not recommended)

Matrix builds (e.g., testing Python 3.11 + 3.12) add minutes for marginal benefit for a solo developer shipping on a single Python version. Only add when:
- Kestrel supports multiple Python versions
- You want to test against multiple Node.js versions

---

## Agentic Development Patterns

### The Challenge

AI-assisted development (Claude Code, Copilot, Codex) produces high-frequency commits -- often 5-15 commits per feature branch session. This creates CI patterns that differ from traditional human dev:

- **Rapid succession pushes:** Agent commits after every logical unit, triggering CI on each
- **Multiple parallel branches:** Agent worktrees create concurrent PRs
- **Automated PR creation:** Agents open PRs programmatically
- **High commit volume:** More granular commits than human developers

### Concurrency: Already Handled

Kestrel's existing concurrency config handles rapid pushes well:

```yaml
concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}
```

When an agent pushes 3 commits in quick succession, only the last one's CI run completes. This is the correct behavior.

### Branch Protection That Works with Automation

**Problem:** Agents need to push to branches and create PRs, but branch protection can block `github-actions[bot]` from pushing to protected branches.

**Solution for Kestrel (solo developer):**

1. **Protect only `main`** with:
   - Require PR before merging (no direct pushes)
   - Require status checks to pass
   - Do NOT require reviews (solo developer -- you ARE the reviewer)
   - Allow force pushes: disabled
   - Allow deletions: disabled

2. **Use GitHub Rulesets** instead of legacy branch protection:
   - Rulesets support "Required when present" for status checks (fixes the path-filter skip problem)
   - Rulesets can exempt GitHub Apps (for Release Please bot)

3. **For agent-created PRs:** Agents push to feature branches (not protected), create PR via `gh pr create`. Human reviews and merges.

Source: [GitHub Branch Protection Docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)

### Auto-Merge Patterns

**For Dependabot PRs:**

```yaml
# .github/workflows/dependabot-auto-merge.yml
name: Dependabot auto-merge

on: pull_request

permissions:
  contents: write
  pull-requests: write

jobs:
  auto-merge:
    runs-on: ubuntu-latest
    if: github.actor == 'dependabot[bot]'
    steps:
      - name: Dependabot metadata
        id: metadata
        uses: dependabot/fetch-metadata@v2
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}

      - name: Enable auto-merge for minor/patch updates
        if: steps.metadata.outputs.update-type != 'version-update:semver-major'
        run: gh pr merge --auto --squash "$PR_URL"
        env:
          PR_URL: ${{ github.event.pull_request.html_url }}
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

This auto-merges minor/patch dependency updates after CI passes. Major version bumps still require manual review.

Source: [GitHub Docs: Automating Dependabot](https://docs.github.com/en/code-security/tutorials/secure-your-dependencies/automating-dependabot-with-github-actions)

**For agent PRs:** Do NOT auto-merge agent PRs. Agents open PRs; human reviews and merges. This is a deliberate human-in-the-loop gate.

### GitHub Agentic Workflows (Technical Preview, Feb 2026)

GitHub launched "Agentic Workflows" -- AI agents that run inside GitHub Actions, triggered by issues/PRs/schedules. Key facts:

- **Supported agents:** Copilot CLI, Claude Code, OpenAI Codex
- **Security model:** Read-only defaults, explicit permissions, sandboxed execution, network isolation, human review gates
- **Agents open PRs, they don't auto-merge** -- by design
- **Use cases:** Continuous triage, documentation updates, test improvement, CI failure analysis

**Production results from GitHub's own usage:**
- Documentation agents: 85-100% merge rate across 6 specialized agents
- Runs on GitHub Actions infrastructure (free for public repos)

**Relevance to Kestrel:** Worth exploring for automated tasks like:
- Auto-updating `types.generated.ts` when backend schemas change
- Auto-fixing lint issues on PRs
- Triaging GitHub Issues (if ever used)

Source: [GitHub Agentic Workflows Announcement](https://github.blog/changelog/2026-02-13-github-agentic-workflows-are-now-in-technical-preview/)

---

## Emerging Best Practices 2025-2026

### 1. Immutable Actions (Coming 2026)

Actions will support immutable releases where assets and Git tags can't be changed or deleted post-publish. Includes release attestations for verifiable integrity.

**Current bridge strategy:** SHA-pin all actions. When immutable actions GA, the ecosystem will gradually shift.

Source: [GitHub Actions 2026 Security Roadmap](https://github.blog/news-insights/product-news/whats-coming-to-our-github-actions-2026-security-roadmap/)

### 2. Workflow Dependency Locking

A new `dependencies:` section in workflow YAML will lock all direct and transitive dependencies with commit SHAs. Changes become visible as PR diffs. Public preview expected in 3-6 months.

### 3. Deployment Protection Rules

Custom deployment protection rules (GA) allow integrating external approval systems, compliance checks, or security gates before deployments proceed. Kestrel doesn't need these yet (self-hosted), but relevant for future SaaS mode.

### 4. Deprecations to Watch

From [GitHub Changelog Feb 2026](https://github.blog/changelog/2026-02-05-notice-of-upcoming-deprecations-and-breaking-changes-for-github-actions/):
- **actions/cache v1-v2:** Deprecated. Use v4+.
- **ubuntu-20.04 runner:** Fully deprecated.
- **Check run status modification:** Can no longer modify conclusion/status of Actions-created check runs via GITHUB_TOKEN.
- **Network allow list:** Self-hosted runners must allow `pkg.actions.githubusercontent.com` and `ghcr.io` for immutable actions.

### 5. GitHub Actions Policy Controls

SHA-pinning enforcement at org level (August 2025). Organizations can now block actions that aren't SHA-pinned. Solo developers on personal accounts can't enforce this via policy, but it's a best practice anyway.

Source: [GitHub Changelog Aug 2025](https://github.blog/changelog/2025-08-15-github-actions-policy-now-supports-blocking-and-sha-pinning-actions/)

---

## Recommended Improvements

### Priority 1: Path Filtering (High Impact, Low Effort)

Add `dorny/paths-filter` to `ci.yml`. Skip backend jobs when only frontend changes, and vice versa. Expected 70-90% time savings on single-component PRs.

**Prerequisite:** Switch from legacy branch protection to GitHub Rulesets with "Required when present" for status checks.

### Priority 2: SHA-Pin All Actions (Security, Low Effort)

Run `pin-github-action` across all workflow files to replace `@v6` tags with SHA pins. Add a comment with the version for readability.

### Priority 3: Dependabot Auto-Merge (Time Savings, Low Effort)

Add a workflow that auto-merges minor/patch Dependabot PRs after CI passes. Major version bumps stay manual.

### Priority 4: Composite Action for Backend Setup (DRY, Low Effort)

Extract the Python setup + dep install + config copy into `.github/actions/setup-backend/action.yml`. Reuse in ci.yml and any future workflows.

### Priority 5: pytest-xdist (When Test Suite Grows)

Add `pytest-xdist` to dev dependencies and use `-n auto` in CI. Wait until test suite exceeds 2 minutes before adding.

### Priority 6: SonarCloud Conditional Run (Minor Optimization)

Only run SonarCloud when `src/` or `frontend/src/` files change. Skip on docs-only PRs.

### Not Recommended (Overkill for Solo Dev)

| Feature | Why Skip |
|---------|----------|
| Self-hosted runners | Public repo = free GitHub-hosted. Maintenance overhead not worth it. |
| Nx/Turborepo | Only 2 frontend workspaces. dorny/paths-filter is simpler. |
| Matrix builds (multi-Python) | Single Python version target. Add when supporting 3.12+. |
| OIDC for cloud deploys | Not deploying to cloud yet. Add when needed. |
| Artifact attestations | Add to publish workflows when Docker/PyPI releases mature. |
| GitHub Agentic Workflows | Interesting but technical preview. Monitor, don't adopt yet. |

---

## Sources

- [GitHub Actions Billing and Usage](https://docs.github.com/en/actions/concepts/billing-and-usage)
- [2026 Pricing Changes](https://resources.github.com/actions/2026-pricing-changes-for-github-actions/)
- [GitHub Actions Pricing Changelog (Dec 2025)](https://github.blog/changelog/2025-12-16-coming-soon-simpler-pricing-and-a-better-experience-for-github-actions/)
- [actions/cache Repository](https://github.com/actions/cache)
- [dorny/paths-filter](https://github.com/dorny/paths-filter)
- [Monorepo Path Filters in GitHub Actions](https://oneuptime.com/blog/post/2025-12-20-monorepo-path-filters-github-actions/view)
- [GitHub Community: Required Checks in Monorepo](https://github.com/orgs/community/discussions/26251)
- [GitHub OIDC Docs](https://docs.github.com/en/actions/concepts/security/openid-connect)
- [GitHub Artifact Attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations)
- [actions/attest-build-provenance](https://github.com/actions/attest-build-provenance)
- [GitHub Actions 2026 Security Roadmap](https://github.blog/news-insights/product-news/whats-coming-to-our-github-actions-2026-security-roadmap/)
- [GitHub Actions Deprecations (Feb 2026)](https://github.blog/changelog/2026-02-05-notice-of-upcoming-deprecations-and-breaking-changes-for-github-actions/)
- [GitHub Actions SHA Pinning Policy (Aug 2025)](https://github.blog/changelog/2025-08-15-github-actions-policy-now-supports-blocking-and-sha-pinning-actions/)
- [pytest-xdist](https://github.com/pytest-dev/pytest-xdist)
- [Reusable Workflow Configurations](https://docs.github.com/en/actions/concepts/workflows-and-actions/reusing-workflow-configurations)
- [Composite Actions vs Reusable Workflows](https://dev.to/n3wt0n/composite-actions-vs-reusable-workflows-what-is-the-difference-github-actions-11kd)
- [Automating Dependabot with GitHub Actions](https://docs.github.com/en/code-security/tutorials/secure-your-dependencies/automating-dependabot-with-github-actions)
- [Dependabot cancel-in-progress issue](https://github.com/dependabot/dependabot-core/issues/10074)
- [GitHub Agentic Workflows (Feb 2026)](https://github.blog/changelog/2026-02-13-github-agentic-workflows-are-now-in-technical-preview/)
- [GitHub Branch Protection Docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [GitHub Self-Hosted Runner Pricing Concerns](https://northflank.com/blog/github-pricing-change-self-hosted-alternatives-github-actions)
- [Concurrency in GitHub Actions (Blacksmith)](https://www.blacksmith.sh/blog/protect-prod-cut-costs-concurrency-in-github-actions)
