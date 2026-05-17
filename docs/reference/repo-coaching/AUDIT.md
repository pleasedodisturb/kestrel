# Audit — Kestrel repo against the masterlist

Snapshot date: 2026-05-02. Branch: `claude/github-best-practices-guide-tLSuf`.

## Executive summary

Kestrel scores **strong on Layer 1 (technical)** — most security, supply-chain, release, and CI hygiene is in place. **Layer 2 (operational)** is light because the project is solo/early; this is appropriate. **Layer 3 (marketing)** is mid: the README hero is good, the install paths are excellent, but discovery, comparison, social proof, and launch choreography are largely absent.

If the goal is to broaden contributor reach, **Layer 3 is the highest-leverage place to invest next.** Layer 1 has only minor gaps (community-health files, FUNDING.yml, CITATION.cff, .gitattributes).

## Layer 1 — Technical: 32 of 40 default-yes items present

### Wins (already in place)

- README, LICENSE (AGPL-3.0), CONTRIBUTING, SECURITY, CHANGELOG, CODEOWNERS
- `.github/` is well-furnished: dependabot.yml, ISSUE_TEMPLATE/{bug, feature, config}, pull_request_template.md, zizmor.yml (workflow security linter), pii-patterns.txt
- Workflows: `ci`, `codeql`, `commitlint`, `daily-scan`, `docker-publish`, `publish-npm`, `publish`, `release-checks`, `release-please`, `scorecard`, `secret-scan`, `workflow-lint`. That's a serious CI surface.
- Pre-commit (`.pre-commit-config.yaml`), gitleaks (`.gitleaks.toml`), pip-audit ignore, socket policy (`.socket.yml`), sonar config
- Conventional Commits enforced (`commitlint.config.js`)
- Release-please configured (`release-please-config.json`, `.release-please-manifest.json`)
- Renovate configured (`renovate.json`)
- Devcontainer present (`.devcontainer/`)
- Docker (Dockerfile + Dockerfile.frontend + 3 compose files)
- Logo set in `assets/` (icon, badge, full, dark variants)
- `docs/` is structured (guides, reference, research, archive, internal, images)
- `.env.example` present
- README hero shows a logo + tagline + Codespaces button + 3 install options + 3 product screenshots — well above median.

### Gaps (default-yes items missing)

| # | Item | Action |
|---|---|---|
| 1 | `CODE_OF_CONDUCT.md` | Add Contributor Covenant 2.1 with a real reporting email. ~5 min. |
| 2 | `.github/FUNDING.yml` | Add even if just one channel (GitHub Sponsors, Buy Me a Coffee, Ko-fi). Adds a Sponsor button. ~2 min. |
| 3 | `CITATION.cff` | Useful given the AI/data flavor — academics may cite it. ~5 min. |
| 4 | `.gitattributes` | At minimum: `* text=auto` + linguist overrides for `assets/`, `docs/images/`. ~3 min. |
| 5 | `SUPPORT.md` | Optional but cheap — points users at Discussions/issues vs questions. ~3 min. |
| 6 | Private vulnerability reporting | Verify it's enabled in Settings → Security. SECURITY.md should state it. |
| 7 | OpenSSF Best Practices badge | Fill questionnaire at [bestpractices.dev](https://www.bestpractices.dev/). 30 min for "passing." |
| 8 | SBOM in releases | Confirm `release-please` flow attaches SBOM (and SLSA provenance) to GH releases. |

### Verify-don't-assume (need to look at workflow internals)

- [ ] Are GitHub Actions pinned by full SHA, or only by tag (`@v4`)? **Audit recommendation: open every workflow in `.github/workflows/` and check.**
- [ ] Is `permissions: {}` set at workflow root in every file?
- [ ] Are `concurrency:` groups set on PR-triggered workflows?
- [ ] Are `timeout-minutes:` set on every job?
- [ ] Branch protection on `main`: required checks, required reviews, signed commits, linear history.
- [ ] Are signed commits/tags enforced? (Repo has commitlint but signing is separate.)
- [ ] Coverage reporting visible (codecov badge in README)?

These are quick command-line checks; consider a follow-up GSD task `/gsd-quick — audit workflows for SHA pinning + permissions`.

## Layer 2 — Operational: minimum viable, appropriate for solo

### Present
- CODEOWNERS exists (catches review routing).
- Issue forms (`bug_report.yml`, `feature_request.yml`) are in place.
- `config.yml` for issue templates routes blank issues elsewhere.
- PR template present.
- Conventional Commits + commitlint.
- CLAUDE.md and CONTRIBUTING.md document workflow rules and triage expectations implicitly via Linear.

### Gaps relative to the masterlist (most are nice-to-have for a solo project)

| Item | Recommendation |
|---|---|
| Public label taxonomy | Document the `type/*`, `area/*`, `priority/*`, `status/*` schema in CONTRIBUTING. Otherwise contributors guess. |
| `good first issue` / `help wanted` curation | Maintain at least 3 labelled at all times once the project takes external contributions. |
| Stale-bot policy (or explicit non-policy) | Decide; document. |
| Discussions vs Issues split | Consider enabling Discussions to absorb questions. |
| Public roadmap link | If Linear is private, expose a public mirror in the README ("public roadmap"). |
| Review SLA | Even an honest "I look at PRs on weekends" beats silent backlog. |
| all-contributors / first-interaction bot | Cheap, friendly. |
| Decision-making doc | One short paragraph in CONTRIBUTING ("BDFL with lazy consensus") suffices. |

The CLAUDE.md notes `<!-- maintainer-specific -->` which signals you've separated personal infra from project infra — good. Operational debt is low because expectations are clear.

## Layer 3 — Marketing/branding: highest-leverage place to invest

### Present (above median)

- Logo set with light/dark variants, hero illustration in README
- 4 install paths (curl, npx, brew, Codespaces) covering the major audiences
- 3 product screenshots — preview pipeline / discovery / settings
- Clear one-liner: "A job search system that runs on your computer."
- AGPL-3.0 license publicly badged
- PyPI publishing via workflow
- Homebrew formula
- npm wrapper (`npm-package/`)
- Devcontainer + Codespaces button in hero

### Gaps (highest-leverage)

| Priority | Item | Why it matters | Effort |
|---|---|---|---|
| **P0** | **Comparison table** (Kestrel vs Teal / Huntr / Simplify / spreadsheet) | Top-of-funnel converters need to know "why this, not that." | 30 min |
| **P0** | **Social preview image** | Posts on HN/Reddit/X/LinkedIn unfurl ugly without it. 1280×640, logo + tagline. | 30 min |
| **P0** | **Wedge / 10× framing** | Current pitch is descriptive ("a job search system") not differentiated. Try: "Job search, but yours" / "Self-hosted job-tracker your data never leaves" / "Stop letting Indeed score you. Score the jobs." | 15 min copy work |
| **P1** | **GitHub topics audit** | Are `self-hosted`, `llm`, `ai-agent`, `job-search`, `python`, `fastapi`, `kanban`, `react`, `local-first` all set? Each one is a discovery surface. | 5 min |
| **P1** | **External list inclusion** | `awesome-selfhosted`, `awesome-llm-apps`, `awesome-fastapi`, `awesome-job-search` if it exists. | 1–2 hr/week of PRs |
| **P1** | **Demo GIF or asciinema cast in hero** | Static screenshots underdeliver vs a 5-second motion clip. [vhs](https://github.com/charmbracelet/vhs) renders deterministic terminal GIFs. | 1–2 hrs |
| **P1** | **Star-history chart in README** | Once at >300 ⭐, embed [star-history.com](https://star-history.com/) graph. | 2 min |
| **P1** | **Architecture diagram** in README or docs | One Mermaid diagram. The CLAUDE.md has the architecture in prose. | 30 min |
| **P2** | **`docs/` site on a domain** (kestrel.dev / kestrel-app.dev) | README is great but doesn't compound for SEO; a real docs site does. Astro Starlight or mkdocs-material in 1 day. | 1 day |
| **P2** | **`llms.txt` + `llms-full.txt`** at docs root | LLM-agent discoverability, near-zero cost. | 30 min |
| **P2** | **Launch post** ("I built a self-hosted alternative to Teal/Huntr") | Show HN, r/selfhosted, dev.to, Hashnode. Coordinate window. | 1 day prep + launch day |
| **P2** | **"Used by" or testimonial** section | Even one quote and one logo. Solicit from early users. | ongoing |
| **P3** | **Engineering blog** | One deep-dive post on "how we do AI provider abstraction with 9 providers" → category-leading content piece. | 1 week |
| **P3** | **Newsletter pitch** | Console.dev, TLDR, Hacker Newsletter — short blurb pitches. | 2 hrs |

### Anti-patterns currently absent (good)

- Badge soup: 4 badges, all meaningful. ✓
- TOC for short README: none. ✓
- Missing install: install is _the second section_. ✓
- Jargon-dense first paragraph: pitch is plain English. ✓
- "Production-ready" / "blazingly fast" without proof: not present. ✓

## Cross-cutting

- **AGPL-3.0** is a strong signal-of-intent for a self-hosted, privacy-flavored project, but it _will_ deter some commercial adoption. Document the rationale in `LICENSE-RATIONALE.md` or in the FAQ — this defuses 80% of "why AGPL?" questions.
- **Solo signal honesty**: somewhere in CONTRIBUTING or README, name that this is a solo project and what response times look like. This _grows_ trust rather than reducing it.
- **The "private/" and `.planning/` dirs** are gitignored — confirm they don't leak. The `.gitignore` and `.gitattributes` audit covers this.

## Top 10 next moves (prioritized)

1. **Add `CODE_OF_CONDUCT.md` + `.github/FUNDING.yml`** — 10 minutes, closes Layer 1 gaps.
2. **Generate a social preview image** — 30 minutes, biggest unforced error to fix.
3. **Add a "vs alternatives" comparison table** to README — 30 minutes, single biggest conversion lift.
4. **Audit GitHub Actions for SHA pinning + minimum permissions** — security hygiene, 1 hour.
5. **Sharpen the wedge** in the README hero — copy work, 30 minutes.
6. **Audit + add GitHub topics** — 5 minutes, discovery lift.
7. **Add a 5-second demo GIF / vhs cast** to the README hero — 1–2 hours, large credibility jump.
8. **OpenSSF Best Practices "passing" badge** — 30 min questionnaire, free signal.
9. **Stand up `kestrel.dev` docs site** with Starlight or mkdocs-material — 1 day, SEO compound.
10. **Plan a coordinated launch post** (Show HN + r/selfhosted) once 1–9 are done — 1 day.
