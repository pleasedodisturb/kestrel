# CI/CD Patterns for Agentic AI-Assisted Development

**Researched:** 2026-04-16
**Context:** Kestrel project — solo developer using Claude Code, multiple sessions/machines, git worktrees, conventional commits, Linear task tracking, GitHub hosting
**Overall confidence:** HIGH (most patterns verified against GitHub docs and official tooling)

---

## 1. High-Frequency Commit Handling

AI agents commit after every logical change. Without mitigation, this causes CI overload on busy days (20+ pushes).

### Concurrency Groups (Already Partially Implemented)

Kestrel already has the right foundation:

```yaml
concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}
```

This cancels in-progress runs on feature branches when new commits push — exactly right for agentic workflows where the latest commit supersedes the previous one. Main branch runs are never cancelled (correct: every main commit should be validated).

**Confidence:** HIGH — verified against [GitHub concurrency docs](https://docs.github.com/en/actions/using-jobs/using-concurrency)

### Path Filtering with `dorny/paths-filter`

Kestrel is a monorepo (backend + frontend + mobile). Currently, ALL jobs run on every push. Add path-based filtering so backend-only changes skip frontend tests and vice versa:

```yaml
jobs:
  changes:
    runs-on: ubuntu-latest
    outputs:
      backend: ${{ steps.filter.outputs.backend }}
      frontend: ${{ steps.filter.outputs.frontend }}
      mobile: ${{ steps.filter.outputs.mobile }}
      ci: ${{ steps.filter.outputs.ci }}
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
            frontend:
              - 'frontend/**'
            mobile:
              - 'mobile/**'
            ci:
              - '.github/**'

  backend:
    needs: changes
    if: needs.changes.outputs.backend == 'true' || needs.changes.outputs.ci == 'true'
    # ... existing backend job

  frontend:
    needs: changes
    if: needs.changes.outputs.frontend == 'true' || needs.changes.outputs.ci == 'true'
    # ... existing frontend job
```

**Impact estimate:** 40-60% reduction in CI minutes on agent branches that touch only one component.

**Caveat:** GitHub required status checks remain "Pending" when path-filtered jobs are skipped, blocking merges. Solutions:
1. Use `dorny/paths-filter` with a "report success" fallback job that always passes
2. Use GitHub's native `paths` filter at workflow level (but loses per-job granularity)
3. Use the `actions/github-script` pattern to create a "skip" check status

**Confidence:** HIGH — [dorny/paths-filter](https://github.com/dorny/paths-filter) is the standard solution, 5k+ stars, actively maintained.

### Skip CI Patterns

GitHub Actions natively supports skip keywords in commit messages:
- `[skip ci]`, `[ci skip]`, `[no ci]`, `[skip actions]`, `[actions skip]`

For agentic workflows, agents should use `[skip ci]` on WIP/checkpoint commits and let CI run on the final push. This is configurable in Claude Code's commit behavior.

**Recommendation for Kestrel:** Train agents to use `[skip ci]` on intermediate commits. Final commit before PR creation/update should always trigger CI.

**Confidence:** HIGH — [GitHub docs](https://docs.github.com/actions/managing-workflow-runs/skipping-workflow-runs)

### Commit Batching for CI

For branches where an agent is doing rapid-fire commits (e.g., fixing lint errors across many files), consider a "debounce" pattern:

```yaml
on:
  push:
    branches-ignore:
      - 'wip/**'  # WIP branches don't trigger CI
```

Agents work on `wip/G-XXX/description`, then when ready, rename/push to `G-XXX/description` to trigger CI. However, this adds workflow complexity — the simpler approach is concurrency groups + `[skip ci]`.

**Recommendation:** Stick with concurrency groups + `[skip ci]`. Don't over-engineer branch naming schemes.

---

## 2. Branch Protection for Agentic Workflows

### Recommended Branch Protection Rules for `main`

```
Required:
- Require pull request before merging (no direct pushes)
- Require status checks to pass: backend, frontend, actionlint
- Require branches to be up to date before merging: OFF
  (use merge queue instead, or skip for solo dev)
- Require conversation resolution before merging: OFF
  (solo dev — would just slow you down)

Optional:
- Require signed commits: ON (SSH signing already configured)
- Require linear history: ON (keeps git log clean)
```

### Merge Queue vs Auto-Merge for Solo Dev

**Merge queue** is designed for high-throughput teams where multiple PRs land on main simultaneously. For a solo developer (even with AI agents), merge queue adds overhead without much benefit — you're unlikely to have merge conflicts between concurrent PRs because you're the only author.

**Auto-merge** is the better fit:
- Enable "Allow auto-merge" in repo settings
- When a PR passes all checks, it merges automatically
- Agent workflow: create PR -> CI runs -> auto-merge if green

```bash
# Agent can enable auto-merge when creating PR
gh pr create --title "feat(G-XXX): ..." --body "..."
gh pr merge --auto --squash
```

**Recommendation:** Use auto-merge, skip merge queue. Revisit if you add contributors.

**Confidence:** MEDIUM — merge queue benefits are [well-documented](https://github.blog/news-insights/product-news/github-merge-queue-is-generally-available/) but advice for solo dev is based on reasoning, not direct source.

---

## 3. PR Automation

### Auto-Labeling from Conventional Commits

Use [bcoe/conventional-release-labels](https://github.com/marketplace/actions/assign-labels-from-conventional-commits) or similar:

```yaml
name: Label PRs
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  label:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 0
      - uses: bcoe/conventional-release-labels@v1
        with:
          type_labels: |
            {
              "feat": "feature",
              "fix": "bug",
              "chore": "chore",
              "docs": "documentation",
              "ci": "ci",
              "test": "testing",
              "refactor": "refactor",
              "perf": "performance"
            }
```

Kestrel already uses conventional commits (`feat(G-XXX):`, `fix(G-XXX):`) and has `commitlint.yml` — adding auto-labels is a natural extension.

### PR Size Warnings

```yaml
- uses: CodelyTV/pr-size-labeler@v1
  with:
    xs_max_size: 10
    s_max_size: 100
    m_max_size: 500
    l_max_size: 1000
    fail_if_xl: false
    message_if_xl: >
      This PR has over 1000 lines changed. Consider splitting into
      stacked PRs for easier review.
```

AI agents can generate large PRs. Size warnings serve as a reminder to the human reviewer.

### Stale PR Cleanup

```yaml
name: Stale PRs
on:
  schedule:
    - cron: '0 9 * * 1'  # Weekly Monday 9am
jobs:
  stale:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/stale@v9
        with:
          days-before-stale: 14
          days-before-close: 7
          stale-pr-message: >
            This PR has been inactive for 14 days. It will be closed in 7 days
            unless updated. If the work is still needed, rebase and push.
```

Agents create branches that sometimes get abandoned. Automated cleanup prevents branch sprawl.

**Confidence:** HIGH — all actions are well-established GitHub Marketplace offerings.

---

## 4. Quality Gates for AI-Generated Code

### What Catches Real Issues (Keep)

| Check | Why It Matters for AI Code | Tool |
|-------|---------------------------|------|
| **Linting** | AI agents produce consistent style but miss project-specific conventions | Ruff (Python), ESLint (TS) — already in CI |
| **Type checking** | AI sometimes generates incorrect types or loses type safety | `tsc --noEmit` (currently disabled in Kestrel — fix this) |
| **Security scanning** | AI can introduce vulnerable patterns (eval, SQL injection, hardcoded secrets) | pip-audit, npm audit, SonarCloud — already in CI |
| **Test execution** | AI-written tests can be shallow or test implementation rather than behavior | pytest, Vitest — already in CI |
| **Coverage on new code** | AI tends to skip edge cases | SonarCloud quality gate (new code coverage) |
| **Migration validation** | AI can create conflicting Alembic migrations | Already in CI (heads check + roundtrip) |
| **Dead code detection** | AI generates unused imports and helper functions | Ruff (F401 unused imports) — already caught. Add vulture for Python dead code |
| **PII detection** | AI may hallucinate real-looking data | Already in CI |

### What's Pure Friction (Remove or Make Non-Blocking)

| Check | Why It's Friction | Recommendation |
|-------|-------------------|----------------|
| **Strict formatting on every push** | Agent already formats; CI just re-checks | Keep but make fast (already is with Ruff) |
| **Full SonarCloud on every PR** | Slow, often redundant with linting | Keep non-blocking (already `continue-on-error: true`) |
| **CodeQL on every PR** | Very slow (5-10 min), catches rare issues | Run on main only or weekly schedule |

### AI-Specific Quality Gates to Add

1. **Semgrep with custom rules** — encode project-specific anti-patterns:
   ```yaml
   - name: Semgrep scan
     uses: semgrep/semgrep-action@v1
     with:
       config: >-
         p/python
         p/typescript
         .semgrep/  # custom rules
   ```
   Custom rules for Kestrel might include:
   - Raw SQL string concatenation (use SQLAlchemy)
   - Direct `os.environ` access (use config.py)
   - Synchronous DB calls in async handlers

2. **Test quality check** — verify tests actually assert something meaningful:
   ```bash
   # Flag tests with no assertions
   grep -rn "def test_" tests/ | while read line; do
     file=$(echo $line | cut -d: -f1)
     func=$(echo $line | grep -oP 'def \K\w+')
     # Check if function body contains assert
     if ! python -c "import ast; ..."; then
       echo "Warning: $func in $file may lack assertions"
     fi
   done
   ```

3. **Import validation** — verify all imports resolve:
   ```bash
   python -c "import py_compile; py_compile.compile('file.py', doraise=True)"
   ```
   Ruff's F821 (undefined names) partially covers this.

**Confidence:** HIGH for existing tools, MEDIUM for Semgrep custom rules (requires project-specific tuning).

**Key source:** [Semgrep in CI docs](https://semgrep.dev/docs/deployment/oss-deployment), [Frank Neff on quality gates](https://www.frankneff.com/blog/2026-02-19-quality-gates-against-ai-slop/)

---

## 5. Multi-Session Development

### The Problem

Multiple Claude Code sessions (or worktree agents) work on different branches simultaneously. Risks:
- Two agents modify the same file on different branches (merge conflict)
- An agent's branch falls behind main, creating integration issues
- Alembic migration conflicts (already documented in Kestrel feedback memories)

### Mitigation Strategies

1. **Linear ticket ownership** — only one agent works on a ticket at a time. Linear status acts as a lock.

2. **Branch-level CI isolation** — current concurrency groups already handle this. Each branch gets its own CI group.

3. **Integration testing on main** — run a nightly or post-merge integration test that validates the full stack after merges:
   ```yaml
   name: Integration
   on:
     push:
       branches: [main]
     schedule:
       - cron: '0 6 * * *'  # Daily 6am
   jobs:
     integration:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v6
         - name: Full stack smoke test
           run: docker compose up -d && ./scripts/integration-test.sh
   ```

4. **Alembic conflict detection** — already in CI (heads count check). This is critical for Kestrel given the parallel agent pattern.

5. **PR conflict detection** — use GitHub's auto-update branch feature or a bot:
   ```yaml
   - uses: adRise/update-pr-branch@v0.7.4
     with:
       token: ${{ secrets.GITHUB_TOKEN }}
       base: main
       required_approval_count: 0  # solo dev
   ```

**Confidence:** HIGH — these are established patterns, not novel.

---

## 6. Claude Code + GitHub Actions Integration

### `anthropics/claude-code-action` — The Official Integration

Anthropic provides an official GitHub Action for Claude Code integration. Key capabilities:
- **PR review**: Analyzes diffs, posts inline comments
- **Issue triage**: Auto-labels, prioritizes, detects duplicates
- **Code implementation**: Can make changes and push commits
- **Interactive**: Responds to `@claude` mentions in PR comments

**Setup:**
```yaml
name: Claude
on:
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]
  issues:
    types: [opened, assigned]
  pull_request:
    types: [opened, synchronize]

permissions:
  contents: read
  pull-requests: write
  issues: write

jobs:
  claude:
    if: |
      (github.event_name == 'issue_comment' && contains(github.event.comment.body, '@claude')) ||
      (github.event_name == 'pull_request_review_comment' && contains(github.event.comment.body, '@claude')) ||
      (github.event_name == 'issues' && contains(github.event.issue.body, '@claude')) ||
      github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          model: claude-sonnet-4-20250514
          # For automatic PR review on every PR:
          direct_prompt: |
            Review this PR. Focus on:
            - Logic errors and edge cases
            - Security vulnerabilities
            - Consistency with project patterns in CLAUDE.md
            - Test coverage for new code
          # Limit cost:
          max_turns: 3
```

**Cost estimate:** Claude Sonnet 4 at $3/$15 per MTok input/output. A typical 400-line diff review costs ~$0.05. At 5 PRs/day = ~$0.25/day = ~$7.50/month.

**Security model:** The action receives a scoped GitHub token. For PR review, it only needs `contents: read` and `pull-requests: write`. It cannot merge, delete branches, or access secrets beyond what you explicitly pass.

**Recommendation for Kestrel:** Add claude-code-action for PR review. Since the developer already uses Claude Code locally, having Claude review the PR catches issues that the local session might have been blind to (fresh-eyes effect). Use `claude-sonnet-4` (not Opus) for cost control.

**Confidence:** HIGH — [official Anthropic action](https://github.com/anthropics/claude-code-action), [official docs](https://code.claude.com/docs/en/github-actions)

### Security Review Variant

Anthropic also provides `anthropics/claude-code-security-review` for focused security analysis:

```yaml
- uses: anthropics/claude-code-security-review@v1
  with:
    anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
```

This runs a fleet of specialized security agents examining changes against OWASP Top 10.

---

## 7. Worktree-Aware CI

### The Pattern

Agents working in git worktrees create branches, commit, and push. The CI itself doesn't need to be "worktree-aware" — branches pushed from worktrees are identical to branches pushed from the main checkout. The challenges are operational, not CI-level:

1. **Branch cleanup** — worktree branches can accumulate. Add a scheduled cleanup:
   ```yaml
   name: Branch Cleanup
   on:
     schedule:
       - cron: '0 10 * * 0'  # Weekly Sunday
   jobs:
     cleanup:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v6
         - name: Delete merged branches
           run: |
             git fetch --prune
             for branch in $(git branch -r --merged origin/main | grep -v main); do
               branch_name=${branch#origin/}
               echo "Deleting merged branch: $branch_name"
               gh api -X DELETE repos/${{ github.repository }}/git/refs/heads/$branch_name || true
             done
           env:
             GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
   ```

2. **Worktree agent commits** — agents in worktrees must commit before the worktree is cleaned up (already in Kestrel feedback memory). CI handles these commits normally.

3. **Orphaned PR detection** — if an agent's worktree was cleaned up but the PR is still open:
   ```yaml
   # Stale PR workflow (from section 3) handles this
   ```

**Confidence:** HIGH — worktree branches are just branches from CI's perspective.

---

## 8. Trust-but-Verify Patterns

AI agents are productive but can introduce subtle issues that humans wouldn't. These CI checks specifically target AI-generated code patterns:

### Tier 1: Automated (Run in CI)

| Check | What It Catches | Tool | Blocking? |
|-------|-----------------|------|-----------|
| Unused imports | AI adds imports it doesn't use | Ruff F401 | Yes |
| Undefined names | AI references nonexistent variables | Ruff F821 | Yes |
| Dead code | AI generates unused functions/classes | vulture (Python) | Warning only |
| Inconsistent naming | AI mixes camelCase/snake_case | Ruff N8xx rules | Yes |
| TODO/FIXME audit | AI leaves placeholder comments | Custom grep | Warning only |
| Hardcoded values | AI hardcodes URLs, ports, credentials | Semgrep custom | Yes |
| Test assertion count | AI writes tests that don't assert | Custom check | Warning only |
| Duplicate code | AI regenerates similar functions | SonarCloud (already configured) | Warning only |
| Type safety | AI loses type information | tsc --noEmit (enable this) | Yes |

### Tier 2: AI-Assisted Review (Run on PR)

| Check | What It Catches | Tool |
|-------|-----------------|------|
| Logic review | Subtle bugs, wrong assumptions | claude-code-action |
| Security patterns | OWASP Top 10 violations | claude-code-security-review |
| Architecture drift | New code that violates patterns | Claude reviewing against CLAUDE.md |

### Tier 3: Periodic (Run on Schedule)

| Check | What It Catches | Tool |
|-------|-----------------|------|
| Dependency health | Outdated/vulnerable deps | Dependabot + pip-audit |
| Code complexity trends | Growing complexity over time | SonarCloud trends |
| Test coverage trends | Declining coverage | SonarCloud trends |
| Dead code accumulation | Gradual buildup of unused code | vulture full scan |

### Recommended Additions for Kestrel

```yaml
# Add to backend job:
- name: Check for dead code
  run: |
    pip install vulture
    vulture src/career_os/ --min-confidence 80 --exclude "*/migrations/*" || true
  # Warning only — don't block

- name: Check for TODO/FIXME
  run: |
    count=$(grep -rn "TODO\|FIXME\|HACK\|XXX" src/ tests/ --include="*.py" | wc -l)
    echo "Found $count TODO/FIXME comments"
    if [ "$count" -gt 50 ]; then
      echo "::warning::High number of TODO/FIXME comments ($count). Consider creating tickets."
    fi
```

**Confidence:** HIGH — these are well-established static analysis patterns applied to the AI context.

---

## 9. Cost Management for Agentic CI

### Current Cost Profile (Estimate)

With 20+ commits/day on feature branches:
- Concurrency groups cancel most intermediate runs (saves ~60%)
- Effective runs: ~8-10/day (PR opens, updates, merges to main)
- Each full run: ~5 minutes backend + ~3 minutes frontend = ~8 minutes
- GitHub-hosted runner cost: $0.008/min (Linux) = ~$0.064/run
- Monthly estimate: 10 runs/day x 30 days x $0.064 = **~$19/month**

With path filtering added:
- ~50% of runs only trigger one component = ~4 min average
- Monthly estimate: **~$12/month**

With claude-code-action on PRs:
- ~5 PRs/day x $0.05/review = **~$7.50/month**

**Total estimated monthly CI cost: ~$20-30/month** (very manageable for solo dev)

### Cost Optimization Strategies (Ranked by Impact)

1. **Concurrency groups with cancel-in-progress** — Already implemented. Single biggest cost saver.

2. **Path filtering** — Not yet implemented. Easy win for monorepo. **Priority: add this.**

3. **`[skip ci]` on WIP commits** — Free, reduces unnecessary runs by ~30%. **Priority: train agents.**

4. **Artifact caching** — Already using pip and npm caches. Could add more aggressive caching:
   ```yaml
   - uses: actions/cache@v4
     with:
       path: ~/.cache/pip
       key: ${{ runner.os }}-pip-${{ hashFiles('**/pyproject.toml') }}
   ```

5. **Schedule expensive checks** — CodeQL, full SonarCloud, security audits don't need to run on every push:
   ```yaml
   # Move CodeQL to daily schedule instead of every PR
   on:
     schedule:
       - cron: '0 4 * * *'
     push:
       branches: [main]
   ```

6. **Self-hosted runner** — Only worth considering if CI costs exceed ~$100/month. At current volume, GitHub-hosted is cheaper when you factor in maintenance time.

**Confidence:** HIGH — pricing from [GitHub Actions pricing changes](https://github.com/resources/insights/2026-pricing-changes-for-github-actions)

---

## 10. Emerging Patterns

### GitHub Agentic Workflows (Technical Preview — Feb 2026)

GitHub's "Continuous AI" concept augments CI/CD with AI agents that run as GitHub Actions. Key principles:
- **Augment, don't replace** — agents handle judgment-heavy tasks (triage, review, docs); deterministic CI handles builds/tests
- **Markdown-to-YAML compilation** — describe workflows in natural language, compile to Actions YAML with `gh aw compile`
- **Safe Outputs architecture** — agents get read-only tokens, produce structured artifacts; a separate gated job applies changes with scoped write permissions
- **Agent operates in sandbox** — cannot merge, delete, or access secrets it isn't given

**Relevance for Kestrel:** Worth monitoring but not adopting yet. The `claude-code-action` is more mature and directly useful today.

**Confidence:** MEDIUM — [GitHub Agentic Workflows](https://github.github.com/gh-aw/) is in technical preview, not GA. API may change.

### Intelligent Test Selection

Rather than running the full test suite on every commit, Test Impact Analysis (TIA) determines which tests are affected by code changes:
- **Launchable** — ML-based test selection, integrates with pytest and Jest
- **Microsoft Test Impact** — uses code coverage data to select relevant tests
- **pytest-testmon** — monitors file changes and runs only affected tests

For Kestrel's current test suite size (~100 tests, runs in <30 seconds), this is premature optimization. Worth revisiting when test suite exceeds 5 minutes.

**Confidence:** MEDIUM — tools exist but ROI is low for small test suites.

### AI-Powered Test Generation in CI

Tools like Qodo (formerly CodiumAI) and Codegen can generate tests for new code as part of CI:

```yaml
# Hypothetical — not recommended yet
- name: Generate missing tests
  uses: qodo-ai/qodo-cover@v1
  with:
    target: src/career_os/
    test-dir: tests/
    min-coverage: 80
```

**Recommendation:** Don't add to CI yet. AI test generation is better done during development (Claude Code already does this). CI should validate tests, not generate them.

**Confidence:** LOW — rapidly evolving space, tools may change significantly.

### Stacked PRs

GitHub is previewing native Stacked PRs support. For agentic workflows, this enables:
- Agent creates a chain of dependent PRs
- Each PR is small and reviewable
- When the base PR merges, dependents auto-rebase

Tools: [Graphite](https://graphite.dev), [Aviator](https://www.aviator.co), GitHub native (private preview).

**Recommendation:** Not needed for current Kestrel workflow. Solo dev with Claude Code typically creates focused PRs. Worth adopting if PR sizes grow.

**Confidence:** MEDIUM — tools are mature but [GitHub native stacked PRs](https://www.agent-wars.com/news/2026-04-13-github-stacked-prs) is still in preview.

---

## Recommended Implementation Roadmap

### Phase 1: Quick Wins (1-2 hours)

1. **Add `dorny/paths-filter`** to skip irrelevant jobs
2. **Enable auto-merge** in repo settings
3. **Train agents to use `[skip ci]`** on WIP commits
4. **Move CodeQL to daily schedule** instead of every PR

### Phase 2: AI Review Integration (2-4 hours)

5. **Add `anthropics/claude-code-action`** for PR review
6. **Add conventional commit auto-labeling**
7. **Add PR size labeler**

### Phase 3: Trust-but-Verify (4-8 hours)

8. **Enable TypeScript type checking** in frontend CI (fix ~20 type errors first)
9. **Add vulture dead code detection** (warning only)
10. **Add Semgrep with custom rules** for project-specific anti-patterns
11. **Add TODO/FIXME audit**

### Phase 4: Housekeeping Automation (2-4 hours)

12. **Add branch cleanup workflow** (weekly)
13. **Add stale PR workflow** (weekly)
14. **Add integration test on main** (daily)

---

## Sources

### Official Documentation
- [GitHub Actions Concurrency](https://docs.github.com/en/actions/using-jobs/using-concurrency)
- [GitHub Merge Queue](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)
- [GitHub Skip CI](https://docs.github.com/actions/managing-workflow-runs/skipping-workflow-runs)
- [GitHub Branch Protection](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [GitHub Actions Pricing Changes 2026](https://github.com/resources/insights/2026-pricing-changes-for-github-actions)

### Anthropic / Claude Code
- [claude-code-action](https://github.com/anthropics/claude-code-action) — official GitHub Action
- [Claude Code GitHub Actions docs](https://code.claude.com/docs/en/github-actions)
- [claude-code-security-review](https://github.com/anthropics/claude-code-security-review)
- [Solutions examples](https://github.com/anthropics/claude-code-action/blob/main/docs/solutions.md)

### GitHub Agentic Workflows
- [GitHub Agentic Workflows](https://github.github.com/gh-aw/)
- [Continuous AI in Practice](https://github.blog/ai-and-ml/generative-ai/continuous-ai-in-practice-what-developers-can-automate-today-with-agentic-ci/)
- [GitHub Agentic Workflows Technical Preview](https://github.blog/changelog/2026-02-13-github-agentic-workflows-are-now-in-technical-preview/)
- [InfoQ overview](https://www.infoq.com/news/2026/02/github-agentic-workflows/)

### Quality Gates and AI Code
- [Frank Neff: Quality Gates for AI-Generated Code](https://www.frankneff.com/blog/2026-02-19-quality-gates-against-ai-slop/)
- [Semgrep Custom Workflows](https://semgrep.dev/blog/2026/introducing-semgrep-custom-workflows/)
- [Semgrep in CI](https://semgrep.dev/docs/deployment/oss-deployment)
- [Semaphore: Quality Checks on AI-Generated Code](https://semaphore.io/how-do-i-enforce-quality-checks-on-ai-generated-code-in-ci-cd)

### Tools and Patterns
- [dorny/paths-filter](https://github.com/dorny/paths-filter) — conditional job execution
- [Aviator Merge Queue & Stacked PRs](https://www.aviator.co/blog/stacked-prs-code-changes-as-narrative/)
- [Graphite Merge Queue](https://graphite.dev/guides/optimizing-code-reviews-automated-merge-queues)
- [Blacksmith: Concurrency in GitHub Actions](https://www.blacksmith.sh/blog/protect-prod-cut-costs-concurrency-in-github-actions)
- [Aviator: Parallel & Batch CI](https://www.aviator.co/blog/parallel-batch-ci/)
