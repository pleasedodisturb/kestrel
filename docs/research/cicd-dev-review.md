# CI/CD Deep Review: Architecture & Trade-offs

**Audience:** Developers evaluating or contributing to Kestrel's CI/CD pipeline
**Prerequisite:** Familiarity with GitHub Actions, Docker, and CI/CD concepts

This document explains *why* each decision was made, the trade-offs considered, and the architectural implications. For raw data and sources, see `cicd-raw-research.md`. For the user-friendly version, see `../how-cicd-works.md`.

---

## Architecture Overview

Kestrel's CI/CD has three distinct stages, each with different concerns:

```
Code Push  →  CI (validate)  →  Release (package)  →  Deploy (ship)
    │              │                   │                    │
    │         Lint, test,         Version bump,        Docker pull,
    │         security scan,      changelog,           health check,
    │         coverage gate       Docker build,        backup verify
    │                             PyPI/npm publish
    │
    └── Agentic: high-frequency commits,
        multiple branches, worktree agents
```

The key insight is that each stage serves a different audience:
- **CI** serves the developer (fast feedback, catch mistakes early)
- **Release** serves the project (clean versions, reproducible artifacts)
- **Deploy** serves the user (stable, recoverable, monitored)

---

## Why Path Filtering Is the #1 Priority

Kestrel is a monorepo with three components that rarely change together:

```
src/           → Backend (Python)
frontend/      → Web Frontend (React)
mobile/        → Mobile App (Expo)
```

Without path filtering, a one-line Python fix triggers:
1. Python lint + format check (~15s)
2. Python tests with coverage (~60s)
3. Alembic migration roundtrip (~15s)
4. API smoke test (~15s)
5. pip-audit security scan (~20s)
6. **Frontend npm install** (~45s) ← unnecessary
7. **Frontend ESLint** (~10s) ← unnecessary
8. **Frontend Vitest** (~30s) ← unnecessary
9. **Frontend npm audit** (~10s) ← unnecessary
10. SonarCloud analysis (~180s) ← runs both coverages
11. Actionlint (~5s)

That's ~6.5 minutes when ~2 minutes would suffice. With `dorny/paths-filter`, the backend job runs standalone in ~2 minutes for backend-only changes.

### The Required Checks Problem

GitHub's legacy branch protection has a frustrating limitation: if "Frontend" is a required status check and the job is *skipped* (because only backend changed), the PR shows "Pending" forever and can't merge.

**Solution:** GitHub Rulesets (the newer system) support "Required when present" — a check is only required if the job actually ran. This is the prerequisite for path filtering.

**Migration risk:** Low. Rulesets are a superset of branch protection. The migration is a one-time UI configuration change, not a code change.

### Why Not Nx or Turborepo?

These monorepo tools solve a harder problem: dependency-aware builds across dozens of packages. Kestrel has 3 components with no shared code. `dorny/paths-filter` with simple glob patterns is sufficient and adds zero build infrastructure.

---

## SonarCloud: From Informational to Blocking

Currently:
```yaml
- name: Wait for SonarCloud quality gate
  continue-on-error: true  # ← This makes it non-blocking
```

The quality gate checks:
- New code coverage >= 70%
- No new bugs (reliability)
- No new vulnerabilities (security)
- No new code smells beyond threshold (maintainability)
- Duplicated lines on new code <= 3%

### Why 70% Coverage on New Code?

**Not 80%:** AI-generated code includes boilerplate (models, schemas, config) that doesn't benefit from high coverage. 80% leads to writing test_model_has_field_name() garbage tests just to hit a number.

**Not 50%:** Too low to catch regressions. Business logic (scoring, state transitions, API validation) should be thoroughly tested.

**70% on new code (not overall):** This is the key distinction. SonarCloud evaluates new code separately. Old code with 40% coverage won't fail the gate — but any new code you write must meet the bar. This prevents quality erosion without requiring retroactive test writing.

### Why Make It Blocking?

Because non-blocking gates get ignored. The SonarCloud PR decoration says "Failed" but the merge button is green. Over time, developers (and especially AI agents) learn to ignore it. Making it blocking adds ~5 minutes of wait time but ensures every PR meets minimum quality standards.

---

## Release Strategy: Human-in-the-Loop

release-please (already configured) works like this:

```
feat(G-295): expand golden set     ──┐
fix(G-295): update tests            ├── Conventional commits
ci: trigger CI re-run              ──┘
         │
         ▼
┌─────────────────────────────────────┐
│  Release PR (auto-created)          │
│                                     │
│  ## [0.4.0] (2026-04-20)           │
│                                     │
│  ### Features                       │
│  * expand golden set (4eed038)      │
│                                     │
│  ### Bug Fixes                      │
│  * update tests (9fc50f3)           │
│                                     │
│  Bumps: pyproject.toml → 0.4.0      │
│         __init__.py → "0.4.0"       │
│         npm-package → 0.4.0         │
└─────────────────────────────────────┘
         │
         ▼ (human merges when ready)
         │
    v0.4.0 tag created
         │
         ├── docker-publish.yml → GHCR image
         ├── publish.yml → PyPI package
         └── publish-npm.yml → npm package
```

### Why Not Fully Automated (semantic-release)?

For SaaS: fully automated releases make sense. You control the deployment. Users get updates automatically.

For self-hosted: users choose when to upgrade. They read changelogs. A bad release means they're stuck until the next patch. The human review step (merging the Release PR) provides:

1. **Changelog review** — does it make sense to users?
2. **Scope check** — did any WIP features accidentally get included?
3. **Timing control** — is this the right moment to ship?
4. **Emotional safety** — the developer doesn't wake up to a release they didn't know about.

### Mobile Versioning Independence

The mobile app *must* have independent versions because:
- App stores require incrementing build numbers
- Native binary releases go through review (1-3 days)
- OTA updates ship JS changes instantly (no review)
- Users on old app versions still talk to the new backend

This means the mobile app version (1.0.0, build 7) has no relationship to the backend version (0.4.0). The API contract (`/api/v1/`) is what binds them.

---

## Deployment Architecture: Start Simple, Graduate

### Phase 1: Docker Compose + Caddy

```
┌─────────────────────────────────────────┐
│  Hetzner CX22 ($5.50/mo)               │
│                                         │
│  ┌──────────┐  ┌──────────────────────┐ │
│  │  Caddy   │──│  Kestrel Container   │ │
│  │  :443    │  │  FastAPI + React     │ │
│  │  auto-TLS│  │  :8100               │ │
│  └──────────┘  └──────────────────────┘ │
│                                         │
│  ┌──────────┐  ┌──────────────────────┐ │
│  │Litestream│──│  SQLite (WAL mode)   │ │
│  │  sidecar │  │  /data/career_os.db  │ │
│  └──────────┘  └──────────────────────┘ │
│       │                                 │
│       ▼                                 │
│  Cloudflare R2 (backup)                 │
│                                         │
│  ┌──────────────────────────────────┐   │
│  │  Uptime Kuma (:3001)             │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

This is the simplest production deployment that covers all bases:
- **Caddy** handles HTTPS automatically (ACME/Let's Encrypt) — zero TLS configuration
- **Litestream** continuously replicates SQLite WAL to Cloudflare R2 — near-zero data loss
- **Uptime Kuma** monitors /health and sends notifications — awareness without complexity

Deploy procedure:
```bash
ssh server "cd /opt/kestrel && docker compose pull && docker compose up -d"
```

That's it. There's downtime during the restart (~5-15 seconds). For a self-hosted single-user app, this is acceptable.

### Phase 2: Kamal 2 (When Zero-Downtime Matters)

Kamal deploys by:
1. Pulling the new image
2. Starting a new container alongside the old one
3. Waiting for the health check to pass
4. Switching the proxy to the new container
5. Stopping the old container

Zero downtime. Built-in rollback (`kamal rollback`). No server-side daemon to maintain — Kamal runs from your local machine via SSH.

**Why not Coolify?** Coolify runs a web dashboard on your deployment server. In January 2026, 11 critical CVEs were disclosed (including authentication bypass and container escape to root). That's the inherent risk of running a complex web application on the same machine as your production app. Kamal has zero server-side components — the attack surface is just your Docker container.

**Why not now?** Kamal requires Ruby installed locally (friction for Python/Node developers). The Docker Compose approach works fine for Phase 1. Graduate when users would notice 15 seconds of downtime.

---

## Agentic CI/CD: The Unique Challenge

Traditional CI/CD assumes humans commit a few times per day. Agentic development produces 20+ commits per day, sometimes 5 in 10 minutes on a single branch. This changes the calculus:

### What Already Works

```yaml
concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}
```

When an agent pushes commits A, B, C in quick succession:
- CI starts for A
- B arrives → A's CI is cancelled, B's starts
- C arrives → B's CI is cancelled, C's starts

Only C's CI runs to completion. This is correct — the latest commit is what matters.

### What to Add

**`[skip ci]` discipline:** Agents should use `[skip ci]` on checkpoint/WIP commits. The final commit before a PR update should trigger CI.

**claude-code-action for PR review:** This is the "fresh eyes" pattern. The same AI model that wrote the code can't catch its own blind spots. A different session (the GitHub Action) reviews the diff without the context of "I just wrote this, it must be right."

At ~$0.05 per review (Sonnet 4), this costs ~$7.50/month at 5 PRs/day. The value is catching:
- Pattern drift (code that works but doesn't follow project conventions)
- Subtle logic errors (the kind where the test passes because it tests the wrong thing)
- Security issues (the authoring session was focused on features, not attack vectors)

### Auto-Merge: Yes for Deps, No for Code

- **Dependabot minor/patch updates:** Auto-merge after CI passes. Low risk, high time savings.
- **Agent PRs:** Never auto-merge. The human reviews and merges. This is the deliberate gate where "trust but verify" happens.
- **Merge queue:** Overkill for solo dev. Merge queues solve the problem of multiple PRs racing to merge simultaneously. With one developer, this doesn't happen.

---

## Security Layers: Defense in Depth

```
Layer 1: Pre-commit hooks
├── Ruff (lint + format)
├── Prettier (frontend)
├── Gitleaks (secret scan)
└── Large file check

Layer 2: CI (every PR)
├── Ruff + ESLint (code quality)
├── pip-audit + npm audit (dependency vulns)
├── npm audit signatures (supply chain)
├── PII pattern scan (data leak prevention)
├── Commitlint (commit format)
├── SonarCloud (quality gate, coverage)
└── [TO ADD] Semgrep (fast SAST, 10 seconds)

Layer 3: CI (main branch + scheduled)
├── CodeQL (deep SAST, Python + JS/TS)
├── OpenSSF Scorecard (supply chain scoring)
├── Gitleaks (weekly full-repo scan)
└── Trivy (container vulnerability scan)

Layer 4: Release
├── Docker image build validation
├── Alembic migration roundtrip
├── [TO ADD] Build provenance attestation
└── [TO ADD] Image signing

Layer 5: Runtime
├── Health check endpoint (/health)
├── [TO ADD] Sentry error tracking
├── [TO ADD] Uptime Kuma monitoring
└── [TO ADD] Litestream backup verification
```

### Why Add Semgrep When We Have CodeQL?

They serve different purposes:

| | Semgrep | CodeQL |
|---|---------|--------|
| Speed | ~10 seconds | ~5-10 minutes |
| PR blocking | Yes (fast enough) | No (too slow for PR feedback) |
| Custom rules | YAML (easy to write) | QL language (complex) |
| Depth | Surface-level pattern matching | Deep dataflow analysis |
| Best for | Fast feedback, project-specific rules | Thorough weekly security audit |

Use Semgrep on every PR for fast feedback. Keep CodeQL on main + weekly schedule for deep analysis.

---

## Testing in CI: The Pyramid

```
                    ╱╲
                   ╱  ╲
                  ╱ E2E╲          ← Nightly only (Playwright)
                 ╱      ╲           5-10 critical paths
                ╱────────╲
               ╱          ╲
              ╱ Integration ╲     ← Every PR
             ╱    (API)      ╲      Route tests with real DB
            ╱────────────────╲
           ╱                  ╲
          ╱    Unit Tests       ╲  ← Every PR
         ╱  pytest + Vitest      ╲   Fast, isolated, comprehensive
        ╱────────────────────────╲
       ╱                          ╲
      ╱    Static Analysis          ╲ ← Every PR
     ╱  Ruff, ESLint, Semgrep, tsc   ╲  Fastest feedback
    ╱──────────────────────────────────╲
```

### Why Not E2E on Every PR?

E2E tests (Playwright) require:
1. Starting the backend (uvicorn)
2. Starting the frontend dev server
3. Installing Chromium
4. Running browser tests

This adds 3-5 minutes and a brittle dependency chain. For a solo developer, the feedback loop is: write code → push → wait 8+ minutes. That's demotivating.

Instead: E2E runs nightly. If it fails, you fix it the next morning. Unit + integration tests on every PR catch 95% of regressions. The remaining 5% (CSS layout, browser-specific behavior) are caught overnight.

### pytest-xdist: When to Add

Current test suite runs in ~60-90 seconds. pytest-xdist adds overhead (worker process startup) that only pays off when the suite exceeds ~2 minutes. With `--dist loadfile`, it keeps each test file on one worker (important for Kestrel's shared SQLite fixture pattern).

Add it when the test suite grows. Don't add it now — premature optimization adds complexity.

---

## Cost Breakdown

### CI Costs

| Item | Cost | Why |
|------|------|-----|
| GitHub Actions runners | **$0** | Public repo = unlimited free |
| SonarCloud | **$0** | Free for open source |
| Semgrep | **$0** | Free for <10 contributors |
| CodeQL | **$0** | Free for public repos |
| claude-code-action | **~$7.50/mo** | Sonnet 4 at ~$0.05/review, ~5 PRs/day |
| **CI total** | **~$7.50/mo** | Only non-zero cost is AI PR review |

### Infrastructure Costs

| Item | Cost | Why |
|------|------|-----|
| Hetzner CX22 | **$5.50/mo** | 2 vCPU, 4 GB RAM, 40 GB NVMe |
| Cloudflare | **$0** | Free plan: CDN + DDoS protection |
| Cloudflare R2 | **$0** | 10 GB free tier for SQLite backups |
| Sentry | **$0** | Free tier: 5K errors/mo |
| Uptime Kuma | **$0** | Self-hosted on same server |
| Domain | **~$1/mo** | Assumed existing |
| **Infra total** | **~$6.50/mo** | Hetzner + domain |

### What's Not Free

The **$7.50/mo for AI PR review** is the only CI cost because everything else is free for public open-source repos. If the repo ever goes private, GitHub Actions would add ~$12-19/month.

The **$5.50/mo for Hetzner** is the server. This is the minimum viable production hosting — anything cheaper (free tiers on Fly.io/Railway) doesn't support persistent SQLite well.

---

## Implementation Dependencies

```
G-307 (Path filtering) ──requires──→ GitHub Rulesets migration
                                          │
G-308 (SonarCloud blocking) ──────────────┤ (independent)
G-309 (SHA-pin actions) ──────────────────┤ (independent)
G-310 (Dependabot auto-merge) ────────────┤ (independent)
G-311 (Bundle size tracking) ─────────────┘ (independent)

G-313 (TypeScript errors) ──before──→ tsc in CI (same ticket)
G-314 (Semgrep) ──────────────────────┤ (independent)
G-315 (claude-code-action) ──requires─→ ANTHROPIC_API_KEY secret
G-318 (Docker provenance) ────────────┤ (independent)

G-320 (Hetzner setup) ──before──→ G-321 (Litestream)
                       ──before──→ G-322 (Monitoring)
                       ──before──→ G-323 (Deploy automation)
```

Most Phase 1 and Phase 2 tickets are independent and can be parallelized across agents. Phase 3 has a dependency chain: server must exist before you can set up backups or monitoring.

---

*Deep review written 2026-04-16. For the decisional synthesis, see `cicd-research.md`.*
