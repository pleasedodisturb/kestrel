# CI/CD Research: Raw Findings & Sources

**Researched:** 2026-04-16
**Method:** 6 parallel research agents covering GitHub Actions, release strategy, deployment, agentic CI/CD, testing strategy, and current state audit
**Audience:** Developers, contributors, researchers evaluating Kestrel's CI/CD decisions

This document presents findings without editorial filtering. For interpreted recommendations, see `cicd-research.md`. For a user-friendly explanation, see `../how-cicd-works.md`.

---

## 1. Current State: What Kestrel Already Has

### 12 GitHub Actions Workflows

| Workflow | File | Trigger | What It Does |
|----------|------|---------|--------------|
| CI | `ci.yml` | push/PR to main, merge_group | Backend lint+test+audit, frontend lint+test+audit, SonarCloud, actionlint |
| CodeQL | `codeql.yml` | push/PR to main, weekly schedule | SAST for Python + JS/TS |
| Commitlint | `commitlint.yml` | PR to main | Conventional commit format enforcement |
| Daily Scan | `daily-scan.yml` | Mon-Fri 07:00 UTC, manual | Job discovery + AI scoring pipeline |
| Docker Publish | `docker-publish.yml` | push to main, v* tags | Multi-arch Docker image to GHCR |
| npm Publish | `publish-npm.yml` | v* tags | npm package publication |
| PyPI Publish | `publish.yml` | v* tags | Python wheel to PyPI via OIDC |
| Release Please | `release-please.yml` | push to main | Automated release PR from conventional commits |
| Release Checks | `release-checks.yml` | push to main, v* tags, manual | Container build + Trivy scan, frontend extras |
| OpenSSF Scorecard | `scorecard.yml` | push to main, weekly, manual | Supply chain security scoring |
| Secret Scan | `secret-scan.yml` | push/PR to main, weekly | Gitleaks secret detection |
| Workflow Lint | `workflow-lint.yml` | workflow file changes | actionlint + zizmor security lint |

### Security Posture

| Layer | Tool | Status |
|-------|------|--------|
| Secret scanning | Gitleaks (pre-commit + CI + weekly) | Active |
| SAST | CodeQL (Python + JS/TS) | Active |
| Dependency audit (Python) | pip-audit with .pip-audit-ignore | Active |
| Dependency audit (JS) | npm audit + npm audit signatures | Active |
| Supply chain scoring | OpenSSF Scorecard | Active |
| PII leak detection | Custom grep (.github/pii-patterns.txt) | Active |
| Workflow security | actionlint + zizmor | Active |
| Action pinning | SHA-pinned for critical actions | Partial (some mutable tags remain) |
| Container scanning | Trivy (CRITICAL/HIGH fail) | Active on release-checks |
| Code quality | SonarCloud | Active but non-blocking |

### Known Gaps

| Gap | Severity | Details |
|-----|----------|---------|
| Frontend TypeScript checking disabled | Critical | ~20 pre-existing errors (Recharts, test fixtures, nullable guards). Tracked in #103. |
| SonarCloud quality gate non-blocking | Medium | `continue-on-error: true` on quality gate step |
| No path filtering | Medium | All jobs run on every push regardless of changed files |
| Docker provenance disabled | Medium | `provenance: false` in docker-publish.yml |
| Migration check missing from publish | Medium | Broken migrations could ship via manual tags |
| Frontend coverage not in release gates | Low | Only backend coverage checked at release time |
| Actionlint runs redundantly | Low | Both ci.yml and workflow-lint.yml run it |
| No mobile CI | Low | Zero test files exist yet |

---

## 2. GitHub Actions Optimization

### Path Filtering

**Tool:** `dorny/paths-filter@v3` (5k+ stars, actively maintained)
**Impact:** 70-90% CI time reduction on single-component PRs
**Prerequisite:** Migrate from legacy branch protection to GitHub Rulesets with "Required when present"

```yaml
jobs:
  changes:
    runs-on: ubuntu-latest
    outputs:
      backend: ${{ steps.filter.outputs.backend }}
      frontend: ${{ steps.filter.outputs.frontend }}
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
```

**Sources:**
- [dorny/paths-filter](https://github.com/dorny/paths-filter)
- [GitHub Community: Required Checks in Monorepo](https://github.com/orgs/community/discussions/26251)
- [Monorepo Path Filters](https://oneuptime.com/blog/post/2025-12-20-monorepo-path-filters-github-actions/view)

### Cost Profile

| Fact | Data |
|------|------|
| Public repo runner cost | $0 (unlimited free minutes) |
| Private repo free tier | 2,000 min/month |
| Self-hosted runner fee | $0.002/min (announced, "on hold indefinitely" since March 2026) |
| Estimated runs/day | 8-10 effective (concurrency cancels the rest) |
| Estimated monthly cost (current) | ~$19 (if private; $0 since public) |
| With path filtering | ~$12 (if private) |
| With claude-code-action reviews | +$7.50/mo |

**Sources:**
- [GitHub Actions Billing](https://docs.github.com/en/actions/concepts/billing-and-usage)
- [2026 Pricing Changes](https://resources.github.com/actions/2026-pricing-changes-for-github-actions/)
- [GitHub Changelog Dec 2025](https://github.blog/changelog/2025-12-16-coming-soon-simpler-pricing-and-a-better-experience-for-github-actions/)

### Action Security

| Finding | Details |
|---------|---------|
| SHA-pinning | Some actions use mutable `@v6` tags. Tool: [pin-github-action](https://github.com/mheap/pin-github-action) |
| Immutable Actions | Coming 2026, not GA yet. SHA-pin as bridge strategy |
| Dependency locking | New `dependencies:` YAML section in public preview (3-6 months) |
| Artifact attestations | `actions/attest-build-provenance@v2` provides SLSA Build Level 2 |

**Sources:**
- [GitHub Actions 2026 Security Roadmap](https://github.blog/news-insights/product-news/whats-coming-to-our-github-actions-2026-security-roadmap/)
- [GitHub Actions Deprecations Feb 2026](https://github.blog/changelog/2026-02-05-notice-of-upcoming-deprecations-and-breaking-changes-for-github-actions/)
- [SHA Pinning Policy Aug 2025](https://github.blog/changelog/2025-08-15-github-actions-policy-now-supports-blocking-and-sha-pinning-actions/)

---

## 3. Release Strategy

### Tool Comparison

| Tool | Approach | Monorepo | Python | Solo-Dev Fit | Status |
|------|----------|----------|--------|-------------|--------|
| **release-please** | Release PR from conventional commits; human merges | Yes (manifest) | Yes (pyproject.toml) | Excellent | Active (Google) |
| **semantic-release** | Fully automated on merge to main | Yes (plugins) | Via python-semantic-release | Overkill for self-hosted | Active |
| **changesets** | Manual changeset files per PR | Yes (native) | No native support | Too much ceremony | Declining (20/100 score) |
| **release-it** | Interactive CLI | Limited | Via plugins | Good for manual | Active |

**Sources:**
- [release-please](https://github.com/googleapis/release-please)
- [NPM Release Automation Comparison](https://oleksiipopov.com/blog/npm-release-automation/)
- [release-please vs semantic-release](https://www.hamzak.xyz/blog-posts/release-please-vs-semantic-release)

### Versioning Data

| Scheme | Format | Used By |
|--------|--------|---------|
| SemVer | MAJOR.MINOR.PATCH | Most libraries, APIs, self-hosted apps |
| CalVer | YYYY.MM.PATCH | Ubuntu, pip, SaaS with no API contracts |

### Release Trigger Patterns

| Model | Trigger | Best For |
|-------|---------|----------|
| Continuous delivery | Every merge to main | SaaS (vendor controls deployment) |
| Feature-based | When features ship | Self-hosted (users choose when to upgrade) |
| Time-based | Fixed schedule (e.g., bi-weekly) | Teams with coordination needs |
| Mobile OTA | JS-only changes | Bypasses app store review |
| Mobile native | SDK/permission changes | Requires app store review (1-3 days) |

### Branching Model Data

| Model | Use Case | Fit for Solo Dev |
|-------|----------|-----------------|
| Trunk-based + tags | Single version, fast iteration | Yes (already in use) |
| Release branches | Multiple supported versions | No |
| GitFlow | Large team coordination | No |

**Sources:**
- [Trunk Based Development](https://trunkbaseddevelopment.com/)
- [Atlassian: Trunk-Based Development](https://www.atlassian.com/continuous-delivery/continuous-integration/trunk-based-development)

---

## 4. Deployment Platform Comparison

### Self-Hosted Deployment Tools

| Platform | Stars | Setup | Maintenance | Dashboard | Zero-Downtime | Security Notes |
|----------|-------|-------|-------------|-----------|---------------|----------------|
| **Kamal 2** | ~15K | 30 min | Minimal | No (CLI) | Yes (built-in) | Zero server-side components |
| **Coolify** | ~52K | 15 min | Medium | Yes (web) | Yes | **11 critical CVEs Jan 2026** (CVSS 10.0) |
| **Dokku** | ~28K | 20 min | Low | No (CLI) | Plugin-based | Single-server only |
| **CapRover** | ~13K | 20 min | Medium | Yes (web) | Yes | Web dashboard attack surface |
| **Portainer** | ~31K | 10 min | Low | Yes (web) | No | Management, not deployment |

**Coolify CVEs (January 2026):**
- CVE-2025-66209: Command injection via database backup (container escape, full server compromise)
- CVE-2025-64420: Private key disclosure (SSH root access)
- CVE-2025-64419: Command injection via docker-compose.yaml (root execution)
- 8 additional critical/high vulnerabilities

**Sources:**
- [Self-Hosted Tools Compared 2026](https://haloy.dev/blog/self-hosted-deployment-tools-compared)
- [Coolify Security Disclosure](https://thehackernews.com/2026/01/coolify-discloses-11-critical-flaws.html)
- [Kamal Deploy](https://kamal-deploy.org/)
- [Deploying FastAPI with Kamal on Hetzner](https://www.ianwootten.co.uk/2024/10/13/deploying-a-fastapi-app-to-hetzner-with-kamal/)

### Hosting Provider Comparison (Post-April 2026 Pricing)

| Provider | Smallest Plan | 2 vCPU / 4 GB | Bandwidth | SQLite-Friendly |
|----------|--------------|---------------|-----------|-----------------|
| **Hetzner** | CX22 @ EUR 4.49 (~$5.50) | CX32 @ EUR 7.99 (~$9.50) | 20 TB/mo | Yes |
| **DigitalOcean** | $4/mo (512 MB) | $24/mo | 4 TB/mo | Yes |
| **Fly.io** | ~$2-5 (usage) | ~$15/mo | Pay per GB | Tricky (ephemeral VMs) |
| **Railway** | $5/mo | ~$10-15/mo | Included | No (ephemeral) |
| **Render** | $7/mo | ~$25/mo | Included | No (ephemeral) |

**Sources:**
- [Hetzner Price Adjustment April 2026](https://www.hetzner.com/pressroom/statement-price-adjustment/)
- [DigitalOcean vs Hetzner 2026](https://betterstack.com/community/guides/web-servers/digitalocean-vs-hetzner/)

### SQLite Production Data

| Tool | Purpose | Status | Notes |
|------|---------|--------|-------|
| **Litestream** | Continuous WAL replication to S3/R2 | Stable, recommended | Near-zero RPO, $0/mo on R2 free tier |
| **LiteFS** | Distributed SQLite via FUSE | Pre-1.0, deprioritized | LiteFS Cloud sunset Oct 2024. Skip. |
| **SQLite WAL mode** | Concurrent read/write | Already configured in Kestrel | ~1000 TPS write throughput |

**Sources:**
- [Litestream](https://litestream.io/)
- [SQLite Renaissance 2026](https://dev.to/pockit_tools/the-sqlite-renaissance-why-the-worlds-most-deployed-database-is-taking-over-production-in-2026-3jcc)

### Monitoring Tools

| Tool | Purpose | Cost | Setup |
|------|---------|------|-------|
| **Uptime Kuma** | Uptime monitoring, status page | Free (self-hosted) | 10 min |
| **Sentry Free** | Error tracking (Python + React) | Free (5K errors/mo) | 20 min |
| **GlitchTip** | Sentry alternative (self-hosted) | Free | 4 containers, 2 GB VPS |
| **Grafana Cloud Free** | Metrics + Loki logs | Free (10K series, 50 GB logs) | 30 min |

**Sources:**
- [Uptime Kuma](https://uptimekuma.org/)
- [Sentry Alternatives 2026](https://dev.to/david-ssojet/best-sentry-alternatives-for-error-tracking-and-monitoring-2026-44op)

---

## 5. Agentic CI/CD Patterns

### High-Frequency Commit Handling

| Strategy | Effect | Status in Kestrel |
|----------|--------|-------------------|
| Concurrency groups with cancel-in-progress | Only latest push's CI completes per branch | Already implemented |
| `[skip ci]` on WIP commits | Skips CI entirely | Not yet adopted |
| Path filtering | Skips irrelevant jobs | Not yet implemented |
| WIP branch namespacing | `wip/**` branches skip CI | Not recommended (over-engineering) |

### AI PR Review

| Tool | Cost | Maturity | Notes |
|------|------|----------|-------|
| **anthropics/claude-code-action@v1** | ~$0.05/review (Sonnet 4) | GA, official | Reviews diffs, responds to @claude, posts inline comments |
| **anthropics/claude-code-security-review** | Similar | GA, official | Focused security analysis (OWASP Top 10) |
| **GitHub Copilot code review** | Included with Copilot plan | GA | Requires Copilot subscription |
| **GitHub Agentic Workflows** | Free for public repos | Technical preview (Feb 2026) | Too early to adopt |

**Sources:**
- [claude-code-action](https://github.com/anthropics/claude-code-action)
- [Claude Code GitHub Actions docs](https://code.claude.com/docs/en/github-actions)
- [GitHub Agentic Workflows](https://github.blog/changelog/2026-02-13-github-agentic-workflows-are-now-in-technical-preview/)

### Trust-but-Verify Checks

| Check | What It Catches | Tool | AI-Specific? |
|-------|-----------------|------|-------------|
| Unused imports | AI adds unused imports | Ruff F401 | Partially |
| Undefined names | AI references nonexistent variables | Ruff F821 | Partially |
| Dead code | AI generates unused functions | vulture | Yes |
| Type safety | AI loses type information | tsc --noEmit | Partially |
| Custom anti-patterns | Project-specific rule violations | Semgrep | Yes |
| TODO/FIXME accumulation | AI leaves placeholder comments | grep audit | Yes |
| Duplicate code | AI regenerates similar logic | SonarCloud | Partially |

**Sources:**
- [Frank Neff: Quality Gates for AI-Generated Code](https://www.frankneff.com/blog/2026-02-19-quality-gates-against-ai-slop/)
- [Semgrep Custom Workflows](https://semgrep.dev/blog/2026/introducing-semgrep-custom-workflows/)

---

## 6. Testing Strategy

### Test Speed Data

| Component | Test Count | Current Time (est.) | With Optimization |
|-----------|-----------|---------------------|-------------------|
| Backend (pytest) | 102 files, ~50K lines | ~60-90s | ~30-45s (xdist -n auto) |
| Frontend (Vitest) | 20+ files | ~20-30s | Already parallel by default |
| Mobile (Jest) | 0 files | N/A | N/A |

### Tool Comparison: E2E Testing

| Tool | Type | Setup | CI Cost | Maintenance | Best For |
|------|------|-------|---------|-------------|----------|
| **Playwright** | Web E2E | Low | ~3 min/run | Low (5-10 tests) | Web frontend |
| **Cypress** | Web E2E | Low | ~5 min/run | Medium | Not recommended (paid dashboard upsell) |
| **Maestro** | Mobile E2E | Low | Varies | Low (YAML-based) | Expo/React Native |
| **Detox** | Mobile E2E | High | ~10 min/run | High (native builds) | Not recommended for solo dev |

### SAST Tool Comparison

| Tool | Speed | Cost | Custom Rules | Integration |
|------|-------|------|-------------|-------------|
| **Semgrep** | ~10 seconds | Free (<10 contributors) | YAML-based, easy | GitHub Action, PR comments |
| **CodeQL** | ~5-10 minutes | Free (public repos) | QL language (complex) | GitHub native, SARIF |
| **SonarCloud** | ~2-3 minutes | Free (public repos) | Limited | Dashboard, PR decoration |

**Sources:**
- [Semgrep vs CodeQL 2026](https://konvu.com/compare/semgrep-vs-codeql)
- [pytest-xdist](https://github.com/pytest-dev/pytest-xdist)
- [PyPI test suite 81% faster with xdist](https://blog.trailofbits.com/2025/05/01/making-pypis-test-suite-81-faster/)

### Property-Based Testing

| Tool | Language | Use Case | Evidence |
|------|----------|----------|----------|
| **Hypothesis** | Python | Scoring logic, API validation | OOPSLA 2025: finds ~50x more bugs than unit tests |
| **fast-check** | TypeScript | Frontend validation | Vitest-compatible |

**Sources:**
- [Hypothesis docs](https://hypothesis.readthedocs.io/)
- [OOPSLA 2025: Property-Based Testing Evaluation](https://2025.splashcon.org/details/OOPSLA/102/An-Empirical-Evaluation-of-Property-Based-Testing-in-Python)

---

## 7. Mobile CI/CD

### Expo EAS Pricing (Current)

| Service | Free Tier | Starter ($19/mo) | Notes |
|---------|-----------|-------------------|-------|
| EAS Build | Low-priority (15-30 min) | Priority (~5 min iOS) | 30 builds/mo free |
| EAS Submit | Included | Included | Auto-submit to TestFlight/Play Store |
| EAS Update (OTA) | 1,000 MAU | 3,000 MAU | Push JS updates without app store review |

### App Store Requirements

| Platform | One-Time Cost | Annual Cost | First Submission |
|----------|--------------|-------------|------------------|
| iOS (Apple Developer) | $0 | $99/year | Manual enrollment required |
| Android (Google Play) | $25 | $0 | Manual first APK upload required |

**Sources:**
- [EAS Pricing](https://expo.dev/pricing)
- [EAS Update docs](https://docs.expo.dev/eas-update/introduction/)
- [EAS Workflows with Maestro](https://docs.expo.dev/eas/workflows/examples/e2e-tests/)

---

## 8. Cost Summary (All Data Points)

### CI/CD Monthly Costs

| Item | Cost | Condition |
|------|------|-----------|
| GitHub Actions runners | $0 | Public repo (unlimited) |
| GitHub Actions runners | ~$19 | If repo were private (2K free min) |
| claude-code-action reviews | ~$7.50 | 5 PRs/day x $0.05 |
| SonarCloud | $0 | Public repo |
| Semgrep | $0 | <10 contributors |
| CodeQL | $0 | Public repo |

### Infrastructure Monthly Costs

| Item | Cost | Notes |
|------|------|-------|
| Hetzner CX22 | $5.50 | 2 vCPU, 4 GB RAM, 40 GB NVMe, 20 TB bandwidth |
| Hetzner CX32 | $9.50 | Upgrade: 2 dedicated vCPU, 8 GB RAM |
| Cloudflare free | $0 | CDN, DDoS, DNS |
| Cloudflare R2 (10 GB) | $0 | Litestream backup target |
| Sentry free | $0 | 5K errors, 10K perf events/mo |
| Uptime Kuma | $0 | Self-hosted |
| Domain | ~$1/mo | Assumed existing |
| EAS free tier | $0 | Low-priority builds |
| EAS Starter | $19/mo | When faster builds needed |
| Apple Developer | $8.25/mo | $99/year |

---

## Complete Source Index

### Official Documentation
- [GitHub Actions Billing](https://docs.github.com/en/actions/concepts/billing-and-usage)
- [GitHub Actions Concurrency](https://docs.github.com/en/actions/using-jobs/using-concurrency)
- [GitHub Skip CI](https://docs.github.com/actions/managing-workflow-runs/skipping-workflow-runs)
- [GitHub Branch Protection](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [GitHub OIDC](https://docs.github.com/en/actions/concepts/security/openid-connect)
- [GitHub Artifact Attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations)
- [GitHub Merge Queue](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)

### GitHub Changelogs & Roadmaps
- [2026 Pricing Changes](https://resources.github.com/actions/2026-pricing-changes-for-github-actions/)
- [Pricing Changelog Dec 2025](https://github.blog/changelog/2025-12-16-coming-soon-simpler-pricing-and-a-better-experience-for-github-actions/)
- [Actions 2026 Security Roadmap](https://github.blog/news-insights/product-news/whats-coming-to-our-github-actions-2026-security-roadmap/)
- [Actions Deprecations Feb 2026](https://github.blog/changelog/2026-02-05-notice-of-upcoming-deprecations-and-breaking-changes-for-github-actions/)
- [SHA Pinning Policy Aug 2025](https://github.blog/changelog/2025-08-15-github-actions-policy-now-supports-blocking-and-sha-pinning-actions/)
- [Agentic Workflows Feb 2026](https://github.blog/changelog/2026-02-13-github-agentic-workflows-are-now-in-technical-preview/)

### Tools & Actions
- [dorny/paths-filter](https://github.com/dorny/paths-filter)
- [release-please](https://github.com/googleapis/release-please)
- [claude-code-action](https://github.com/anthropics/claude-code-action)
- [claude-code-security-review](https://github.com/anthropics/claude-code-security-review)
- [pin-github-action](https://github.com/mheap/pin-github-action)
- [pytest-xdist](https://github.com/pytest-dev/pytest-xdist)
- [Semgrep](https://semgrep.dev/docs/deployment/oss-deployment)
- [Trivy](https://github.com/aquasecurity/trivy-action)
- [Litestream](https://litestream.io/)
- [docker-rollout](https://github.com/wowu/docker-rollout)
- [Kamal Deploy](https://kamal-deploy.org/)
- [Uptime Kuma](https://uptimekuma.org/)

### Comparisons & Analysis
- [NPM Release Automation Comparison](https://oleksiipopov.com/blog/npm-release-automation/)
- [release-please vs semantic-release](https://www.hamzak.xyz/blog-posts/release-please-vs-semantic-release)
- [Self-Hosted Tools Compared 2026](https://haloy.dev/blog/self-hosted-deployment-tools-compared)
- [Coolify Security Disclosure](https://thehackernews.com/2026/01/coolify-discloses-11-critical-flaws.html)
- [Hetzner Price Adjustment](https://www.hetzner.com/pressroom/statement-price-adjustment/)
- [DigitalOcean vs Hetzner 2026](https://betterstack.com/community/guides/web-servers/digitalocean-vs-hetzner/)
- [Semgrep vs CodeQL 2026](https://konvu.com/compare/semgrep-vs-codeql)
- [Quality Gates for AI Code](https://www.frankneff.com/blog/2026-02-19-quality-gates-against-ai-slop/)
- [Sentry Alternatives 2026](https://dev.to/david-ssojet/best-sentry-alternatives-for-error-tracking-and-monitoring-2026-44op)
- [SQLite Renaissance 2026](https://dev.to/pockit_tools/the-sqlite-renaissance-why-the-worlds-most-deployed-database-is-taking-over-production-in-2026-3jcc)

### Testing
- [PyPI test suite 81% faster with xdist](https://blog.trailofbits.com/2025/05/01/making-pypis-test-suite-81-faster/)
- [OOPSLA 2025: Property-Based Testing](https://2025.splashcon.org/details/OOPSLA/102/An-Empirical-Evaluation-of-Property-Based-Testing-in-Python)
- [Flaky Test Benchmark 2026](https://testdino.com/blog/flaky-test-benchmark/)
- [Playwright CI](https://playwright.dev/docs/ci-intro)
- [Maestro React Native](https://docs.maestro.dev/get-started/supported-platform/react-native)

### Deployment & Infrastructure
- [Deploying FastAPI with Kamal on Hetzner](https://www.ianwootten.co.uk/2024/10/13/deploying-a-fastapi-app-to-hetzner-with-kamal/)
- [Kamal 2 Multi-App](https://www.honeybadger.io/blog/new-in-kamal-2/)
- [Trunk Based Development](https://trunkbaseddevelopment.com/)
- [EAS Update](https://docs.expo.dev/eas-update/introduction/)
- [EAS Workflows](https://docs.expo.dev/eas/workflows/examples/e2e-tests/)
- [Caddy Reverse Proxy Guide](https://1vps.com/caddy-reverse-proxy-guide)
- [Cloudflare Free Plan](https://www.cloudflare.com/plans/free/)

---

*Raw research data from 6 parallel agents, 2026-04-16. No editorial filtering applied.*
