# CI/CD Research: From Tested Code to Production Reality

**Researched:** 2026-04-16
**Status:** Research complete — pending decision & implementation
**Scope:** Kestrel-first, but designed to be reusable across all repos

---

## Philosophy: Human-First, Data-Driven

This document follows a deliberate research philosophy: we do deep, thorough research to understand the full landscape, but research findings **inform** decisions — they don't make them.

Every recommendation here weighs:

- **Developer wellbeing** — mental load, emotional cost, maintenance burden for a solo developer
- **Sustainability** — will this still be manageable in 6 months? In 2 years?
- **Real-world consequences** — for the developer, for users, for the project's future
- **Balance** — across competing concerns, not optimizing for a single metric

"Recommended" doesn't mean "optimal." It means: sane, balanced, and reflective of what we actually care about. We research deeply so we *can* make informed trade-offs. Then we make the human decision.

This is the same approach we took with testing research (G-268) and scoring benchmarks (G-286). CI/CD is the third stage: **the tested stuff going into reality**.

---

## Context: What We Already Have

Kestrel's CI/CD is surprisingly mature — 12 GitHub Actions workflows covering:

| Category | What's In Place | Status |
|----------|----------------|--------|
| **Code Quality** | Ruff lint/format, ESLint, commitlint (conventional commits) | Solid |
| **Testing** | pytest + coverage, Vitest + coverage, API smoke test | Solid |
| **Database** | Alembic migration roundtrip validation (upgrade + downgrade) | Solid |
| **Security** | pip-audit, npm audit + signatures, gitleaks, CodeQL, PII detection | Strong |
| **Supply Chain** | OpenSSF Scorecard, Dependabot (pip/npm/actions), zizmor workflow lint | Strong |
| **Code Analysis** | SonarCloud (coverage, quality, duplication) | Active but non-blocking |
| **Release** | release-please (conventional commits → Release PR → tag) | Configured |
| **Publishing** | PyPI (OIDC), npm, Docker multi-arch (GHCR) | Automated on tags |
| **Daily Ops** | Job discovery pipeline (Mon-Fri, notifications, Google Sheets) | Running |

**Key gaps identified:**
- Frontend TypeScript checking disabled (~20 pre-existing errors, tracked in #103)
- SonarCloud quality gate is informational only (not blocking)
- No path filtering — backend changes trigger frontend CI and vice versa
- Docker image signing/provenance disabled
- No mobile CI at all (zero test files)
- No E2E testing
- No deployment automation (manual Docker Compose pull)

---

## Research Synthesis: Six Streams

### Stream 1: GitHub Actions Optimization

**The data says:** Path filtering with `dorny/paths-filter` is the single highest-ROI improvement. It reduces CI time 70-90% on single-component PRs by skipping irrelevant jobs. Requires migrating from legacy branch protection to GitHub Rulesets ("Required when present" for status checks).

**The trade-off:** Path filtering adds a "detect changes" job (~15s overhead) but saves 3-5 minutes on most PRs. The Rulesets migration is a one-time configuration change.

**Our recommendation:** Add path filtering. It's the rare optimization that's both technically sound and reduces cognitive load — fewer CI notifications, faster feedback, less waiting.

**Other findings:**
- Public repo = free unlimited GitHub-hosted runners. Self-hosted runners add maintenance burden for zero cost savings.
- SHA-pin all actions (some currently use mutable `@v6` tags — supply chain risk)
- Dependabot auto-merge for minor/patch updates saves review cycles
- pytest-xdist for parallel tests — defer until test suite exceeds 2 minutes
- Composite action for backend setup (DRY across workflows) — nice to have, not urgent

### Stream 2: Release Strategy

**The data says:** release-please (already configured) is the right tool. Feature-based releases suit self-hosted software better than time-based cadences. Trunk-based development (already practiced) is correct for solo/agentic dev.

**The trade-off:** Feature-based releases mean no fixed shipping schedule (reduces pressure to ship incomplete work), but require discipline to not let the release PR accumulate indefinitely.

**Our recommendation:** Keep current approach. release-please accumulates conventional commits into a Release PR. Merge when a meaningful milestone ships. No forced cadences.

**Key decisions already made right:**
- SemVer with backend as platform version (0.x.y)
- Frontend version inherited from Docker container
- Mobile gets independent version (app store requirements)
- Trunk-based development, no release branches
- Multi-level Docker tags: `v0.4.0`, `v0.4`, `sha-abc1234`, `latest`

**What to add:**
- Docker build validation in release gates
- Trivy image scanning before publishing
- Rollback documentation for self-hosted users

### Stream 3: Deployment Strategy

**The data says:** Kamal 2 (from Basecamp) provides zero-downtime Docker deploys with zero server-side overhead. Coolify had 11 critical CVEs (CVSS 10.0) in January 2026 — its web dashboard is an attack surface. Hetzner CX22 at ~$5.50/mo is 2-3x cheaper than DigitalOcean.

**The trade-off:** Kamal requires Ruby locally (minor friction for Python/Node developer) and a Docker registry (GHCR is free for public repos). The simpler path is Docker Compose + Caddy (what we effectively have today) — Kamal adds zero-downtime deploys and rollback capabilities.

**Our recommendation:** Start with Docker Compose + Caddy on Hetzner (Phase 1, ~$5.50/mo). Graduate to Kamal 2 when zero-downtime matters (Phase 2). This isn't about the "best" tool — it's about the right tool for the current stage.

**MVP deployment stack ($5.50/mo total):**

| Component | Tool | Cost |
|-----------|------|------|
| Hosting | Hetzner CX22 (2 vCPU, 4 GB RAM) | $5.50 |
| Reverse proxy | Caddy (automatic HTTPS) | $0 |
| SQLite backup | Litestream → Cloudflare R2 | $0 |
| Uptime monitoring | Uptime Kuma (self-hosted) | $0 |
| Error tracking | Sentry free tier (5K errors/mo) | $0 |
| CDN/DDoS | Cloudflare free plan | $0 |

**Database:** SQLite with WAL mode is production-ready for single-server, single-user self-hosted apps. Litestream provides continuous backup to S3-compatible storage at effectively $0/month. LiteFS is deprecated/pre-1.0 — skip it. Migrate to Postgres only if multiple servers need simultaneous writes or DB exceeds 10 GB.

### Stream 4: Agentic CI/CD Patterns

**The data says:** High-frequency agent commits (20+/day) are already handled by concurrency groups with `cancel-in-progress`. The official `anthropics/claude-code-action` provides AI PR review at ~$0.05/review. Auto-merge (not merge queue) is the right pattern for solo dev. Total estimated CI cost: ~$20-30/month.

**The trade-off:** AI PR review adds cost (~$7.50/month) but provides a "fresh eyes" second pass that catches issues the authoring session was blind to. This is particularly valuable when AI agents write the code — a different AI instance reviewing catches pattern drift and subtle bugs.

**Our recommendation:** Add `claude-code-action` for PR review. Train agents to use `[skip ci]` on WIP commits. Enable auto-merge for Dependabot minor/patch updates. Skip merge queue (overkill for solo dev).

**Trust-but-verify checks specifically for AI-generated code:**

| Check | Tool | Blocking? | Why |
|-------|------|-----------|-----|
| Dead code detection | vulture | Warning only | AI generates unused functions |
| Type safety | tsc --noEmit | Yes (once enabled) | AI loses type information |
| Unused imports | Ruff F401 | Yes (already active) | AI adds imports it doesn't use |
| Custom anti-patterns | Semgrep | Yes | Encode project-specific rules |
| TODO/FIXME audit | Custom grep | Warning only | AI leaves placeholder comments |
| PR review | claude-code-action | Non-blocking | Fresh-eyes catch for subtle bugs |

### Stream 5: Testing Strategy for CI

**The data says:** Kestrel has 102 backend test files and 20+ frontend test files — a solid base. The quick wins are pytest-xdist (2-3x faster backend tests), making SonarCloud quality gate blocking (already configured, just flip the switch), and Semgrep for fast SAST (10-second scans vs CodeQL's minutes).

**The trade-off:** Making SonarCloud blocking means PRs can fail on code quality — this is friction. But the default gate (70% coverage on new code, no new bugs/vulnerabilities) is reasonable and prevents quality erosion over time.

**Our recommendation:** Make SonarCloud blocking. Add pytest-xdist when test suite exceeds 2 minutes. Add Semgrep as a fast security gate. Defer E2E testing (Playwright for web, Maestro for mobile) until those frontends stabilize.

**What NOT to add:**
- 100% coverage gates (leads to garbage tests — 70% on new code is the sweet spot)
- Visual regression testing (solo dev, no design team to review diffs)
- Device farm services (simulator testing catches 95% of issues)
- Test impact analysis tools (Nx/Turborepo — designed for massive monorepos)
- E2E on every PR (save it for nightly runs)

### Stream 6: Current State Audit (Gaps)

**Critical gaps to fix:**
1. Frontend TypeScript checking disabled — ~20 pre-existing errors. Fix these and re-enable `tsc` in CI.
2. Alembic migration check missing from publish pipeline — broken migrations could ship via manual tags.
3. Docker image provenance disabled (`provenance: false`) — enable OCI attestations.

**Medium gaps:**
4. SonarCloud quality gate non-blocking — flip to blocking
5. Frontend coverage not in release gates — add Vitest coverage check
6. Actionlint runs redundantly in ci.yml AND workflow-lint.yml — deduplicate
7. npm deps not pinned in publish pipeline — frontend built during PyPI publish could diverge

**Low-priority gaps:**
8. No CONTRIBUTING.md for CI/CD setup
9. Daily scan secrets not documented (Google Sheets, Pushover, Mailgun)
10. Version sync window in npm publish (uses pyproject.toml, should use git tag)

---

## Implementation Roadmap

### Phase 1: Quick Wins (2-3 hours total)

These deliver immediate value with minimal risk:

| # | Change | Effort | Impact |
|---|--------|--------|--------|
| 1 | Add `dorny/paths-filter` to ci.yml | 30 min | 70-90% CI time reduction on single-component PRs |
| 2 | Migrate to GitHub Rulesets ("Required when present") | 15 min | Prerequisite for path filtering |
| 3 | Make SonarCloud quality gate blocking | 15 min | Enforces 70% coverage on new code |
| 4 | SHA-pin all GitHub Actions | 30 min | Supply chain hardening |
| 5 | Add Dependabot auto-merge workflow | 15 min | Minor/patch deps auto-merge after CI passes |
| 6 | Add `size-limit` bundle size check (frontend) | 30 min | Catch frontend bloat on PRs |
| 7 | Enable auto-merge in repo settings | 5 min | PRs merge when checks pass |

### Phase 2: Quality & Security Hardening (4-6 hours)

| # | Change | Effort | Impact |
|---|--------|--------|--------|
| 8 | Fix ~20 TypeScript errors & re-enable tsc in CI | 2 hours | Catch type regressions |
| 9 | Add Semgrep SAST (fast, blocking) | 30 min | 10-second security scan on every PR |
| 10 | Add `claude-code-action` for AI PR review | 30 min | Fresh-eyes review at ~$0.05/PR |
| 11 | Add vulture dead code detection (warning only) | 15 min | Catch AI-generated dead code |
| 12 | Add `pytest-rerunfailures` | 15 min | Flaky test detection + auto-retry |
| 13 | Add migration check to publish.yml | 15 min | Prevent broken migrations from shipping |
| 14 | Enable Docker image provenance/attestations | 15 min | Supply chain trust |
| 15 | Add PR auto-labeling (conventional commits) | 15 min | Automatic feature/bug/chore labels |
| 16 | Add branch cleanup workflow (weekly) | 15 min | Clean up merged worktree branches |

### Phase 3: Deployment Pipeline (4-8 hours)

| # | Change | Effort | Impact |
|---|--------|--------|--------|
| 17 | Set up Hetzner CX22 server | 30 min | Production hosting at $5.50/mo |
| 18 | Configure Caddy reverse proxy | 30 min | Automatic HTTPS |
| 19 | Set up Litestream → Cloudflare R2 backup | 1 hour | Continuous SQLite backup at $0/mo |
| 20 | Set up Uptime Kuma monitoring | 15 min | Uptime monitoring + status page |
| 21 | Set up Sentry free tier (Python + React) | 30 min | Error tracking |
| 22 | Add Cloudflare DNS + CDN | 15 min | DDoS protection, static asset caching |
| 23 | Create deploy script/workflow | 1 hour | `docker compose pull && up -d` automated |
| 24 | Write RUNBOOK.md (disaster recovery) | 1 hour | Recovery procedure documentation |

### Phase 4: Advanced (deferred, conditional)

| # | Change | When to Add | Effort |
|---|--------|-------------|--------|
| 25 | Migrate to Kamal 2 | When zero-downtime matters | 2-4 hours |
| 26 | Add Playwright E2E (nightly) | After web frontend stabilizes | 2 hours |
| 27 | Add mobile Jest CI job | When mobile test files exist | 30 min |
| 28 | Add Maestro mobile E2E | After mobile v1 ships | 4 hours |
| 29 | Add pytest-xdist parallel tests | When test suite exceeds 2 min | 1 hour |
| 30 | Add Hypothesis property-based tests | For scoring logic validation | 2 hours |
| 31 | Add Lighthouse CI (nightly) | When web performance matters | 1 hour |
| 32 | Add Trivy container scanning (nightly) | On release branches | 30 min |
| 33 | Mobile EAS Build + Submit workflows | When app is in stores | 2 hours |
| 34 | Mobile OTA update workflow | When app has users | 1 hour |

---

## Decision Matrix

Key decisions across all streams, with the reasoning:

| Decision | Choice | Runner-Up | Why This Choice |
|----------|--------|-----------|-----------------|
| CI optimization | Path filtering (dorny) | Nx/Turborepo | Simpler, sufficient for 3 components |
| Action pinning | SHA-pin all | Mutable tags | Supply chain security, immutable actions coming 2026 |
| Release trigger | Feature-based | Time-based (2-week sprints) | Solo dev shouldn't force cadences on themselves |
| Release tooling | release-please | semantic-release | Human-in-the-loop for self-hosted software |
| Versioning | SemVer (backend-driven) | CalVer | API contracts matter |
| Branching | Trunk-based + tags | GitFlow | Solo dev, high commit frequency |
| Deployment tool (Phase 1) | Docker Compose + Caddy | Kamal 2 | Simplest viable production setup |
| Deployment tool (Phase 2) | Kamal 2 | Coolify | Zero server-side attack surface, zero-downtime |
| Hosting | Hetzner CX22 | DigitalOcean | 2-3x cheaper at equivalent specs |
| SQLite backup | Litestream → R2 | Manual cron + rsync | Continuous, near-zero RPO, effectively $0 |
| SAST (fast) | Semgrep | CodeQL-only | 10-second scans, complements existing CodeQL |
| SAST (deep) | CodeQL (keep) | SonarCloud SAST | Free, GitHub-native, good for scheduled deep scans |
| AI PR review | claude-code-action | GitHub Copilot | Already use Claude; fresh-eyes effect at $0.05/PR |
| Merge strategy | Auto-merge | Merge queue | Merge queue is overkill for solo dev |
| Coverage gate | 70% on new code | 80% or 100% | Realistic, prevents gaming, allows pragmatic skips |
| E2E web | Playwright (nightly) | Cypress | Faster, lighter, no paid dashboard upsell |
| E2E mobile | Maestro (deferred) | Detox | YAML-based, Expo-native, simpler |
| Monitoring | Uptime Kuma + Sentry free | Grafana + PagerDuty | Solo dev doesn't need enterprise observability |
| Feature flags | Environment variables | Unleash/GrowthBook | Skip the infrastructure; graduate when needed |
| Docker registry | GHCR | Docker Hub | Free for public repos, native GitHub integration |
| Container scanning | Trivy | Grype | Most popular, free, SARIF output |

---

## Cost Summary

### CI/CD Running Costs (Monthly)

| Item | Cost | Notes |
|------|------|-------|
| GitHub Actions | $0 | Public repo = unlimited free minutes |
| claude-code-action PR reviews | ~$7.50 | ~5 PRs/day × $0.05 |
| SonarCloud | $0 | Free for public repos |
| Semgrep | $0 | Free for <10 contributors |
| **CI subtotal** | **~$7.50/mo** | |

### Production Infrastructure (Monthly)

| Item | Cost | Notes |
|------|------|-------|
| Hetzner CX22 | $5.50 | 2 vCPU, 4 GB RAM, 40 GB NVMe |
| Cloudflare | $0 | Free plan: CDN + DDoS |
| Litestream backup | $0 | Cloudflare R2 free tier (10 GB) |
| Uptime Kuma | $0 | Self-hosted on same server |
| Sentry | $0 | Free tier (5K errors/mo) |
| Domain | ~$1 | Assumed existing |
| **Infra subtotal** | **~$6.50/mo** | |

### Mobile (When Applicable)

| Item | Cost | Notes |
|------|------|-------|
| EAS Build (free tier) | $0 | Low-priority builds |
| EAS Build (Starter) | $19 | When faster builds needed |
| Apple Developer Program | $99/year (~$8.25/mo) | Required for iOS |
| Google Play Console | $25 one-time | Required for Android |

### Total

| Phase | Monthly Cost |
|-------|-------------|
| Phase 1-2 (CI + deploy) | ~$14/mo |
| Phase 3 (+ mobile free tier) | ~$14/mo |
| Phase 3 (+ mobile paid) | ~$41/mo |

---

## What We Explicitly Chose NOT to Do

These came up in research but were rejected for good reasons:

| Rejected Approach | Why |
|-------------------|-----|
| Self-hosted runners | Public repo is free. Maintenance burden > cost savings |
| Nx/Turborepo | Only 3 components. Path filtering is simpler |
| GitFlow / release branches | Solo dev, single supported version |
| Time-based release cadence | Creates pressure to ship incomplete work |
| Merge queue | Overkill for solo dev (no concurrent mergers) |
| 100% coverage gates | Leads to garbage tests written to hit a number |
| Cypress | Playwright is faster, lighter, no paid upsell |
| Detox (mobile E2E) | Requires native builds. Maestro is simpler for Expo |
| Visual regression SaaS | Chromatic/Percy at $150-400/mo for a solo project — no |
| Device farm services | Simulator catches 95% of issues |
| Terraform/Pulumi | Single server. RUNBOOK.md is our IaC |
| Unleash/GrowthBook | Feature flags via env vars until we need percentage rollouts |
| Coolify | 11 critical CVEs (Jan 2026). Web dashboard = attack surface |
| LiteFS | Pre-1.0, deprioritized by Fly.io. Litestream is proven |
| Dedicated staging environment | Solo dev overhead. Local Docker testing + CI is sufficient |

---

## Detailed Research Files

The raw research from each stream is preserved in `.planning/research/`:

| File | Stream | Content |
|------|--------|---------|
| `cicd_github_actions.md` | GitHub Actions optimization | Caching, path filtering, security, cost, agentic patterns |
| `cicd_release_strategy.md` | Release strategy | SemVer, release-please, changelog, mobile releases, rollbacks |
| `cicd_deployment.md` | Deployment infrastructure | Kamal vs Coolify, hosting comparison, SQLite backup, monitoring |
| `cicd_agentic_patterns.md` | Agentic development CI/CD | High-frequency commits, PR automation, trust-but-verify, cost |
| `cicd_testing_strategy.md` | Testing in CI | Test pyramid, speed, E2E, flaky tests, coverage gates, security |

---

## Next Steps

1. **Review this document** — flag anything that feels wrong or doesn't match your priorities
2. **Linear epic created** — individual tickets for each actionable item, ordered by phase
3. **Start with Phase 1 quick wins** — 2-3 hours of work for immediate, tangible improvement
4. **Phase 2-3 as separate sprints** — each phase is a natural stopping point

This research is designed to be reusable. When we set up CI/CD for other repos, we start from these decisions and adapt only where the project differs.

---

*Research conducted 2026-04-16 across 6 parallel research streams. Raw data in `.planning/research/cicd_*.md`. Philosophy: human-first, data-driven.*
