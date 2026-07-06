# Release Strategy Research: Kestrel

**Domain:** Self-hosted monorepo (Python backend + React frontend + React Native mobile)
**Researched:** 2026-04-16
**Overall confidence:** HIGH (well-established tooling, multiple verified sources)

---

## Table of Contents

1. [When to Cut a Release](#1-when-to-cut-a-release)
2. [Versioning Strategy](#2-versioning-strategy)
3. [Automated Release Workflows](#3-automated-release-workflows)
4. [Changelog Generation](#4-changelog-generation)
5. [Release Validation Gates](#5-release-validation-gates)
6. [Mobile Release Specifics](#6-mobile-release-specifics)
7. [Docker Image Releases](#7-docker-image-releases)
8. [Branching Model](#8-branching-model)
9. [Rollback Strategies](#9-rollback-strategies)
10. [Recommended Implementation Plan](#10-recommended-implementation-plan)

---

## 1. When to Cut a Release

### Self-Hosted vs SaaS vs Mobile: Different Cadences

| Deployment Model | Release Trigger | Rationale |
|------------------|----------------|-----------|
| **SaaS** | Continuous (every merge to main) | Vendor controls deployment; users get updates automatically |
| **Self-hosted** | Feature-based milestones | Users choose when to upgrade; releases must be stable, well-documented |
| **Mobile (app stores)** | Feature-based + compliance | App store review adds 1-3 day latency; bundle releases for efficiency |
| **Mobile (OTA)** | Bug fixes + minor UI changes | Bypasses app store; fast iteration on JS-only changes |

### Recommendation for Kestrel: Feature-Based Releases

**Use feature-based releases, not time-based.** Rationale:

1. **Solo developer** -- time-based cadences (e.g., "release every 2 weeks") create pressure to ship incomplete work or ship empty releases.
2. **Self-hosted app** -- users pull releases manually. They want meaningful changelogs ("what's new?"), not "accumulated patches since last Tuesday."
3. **Current version is 0.3.1** -- pre-1.0 software should release when features land, not on a schedule.

**Release triggers:**
- A meaningful feature ships to main (e.g., new scoring engine, new provider)
- A security fix lands (immediate patch release)
- Accumulated bug fixes reach 5+ or a month passes since last release (whichever comes first)
- Mobile native dependency changes (requires new binary build)

**Do NOT release for:** docs-only changes, CI config changes, refactors that don't affect user behavior.

**Confidence:** HIGH -- this matches patterns from GitGuardian, Zitadel, and other self-hosted projects.

---

## 2. Versioning Strategy

### SemVer vs CalVer

| Scheme | Format | Best For | Example |
|--------|--------|----------|---------|
| **SemVer** | MAJOR.MINOR.PATCH | Libraries, APIs, self-hosted apps | 1.4.2 |
| **CalVer** | YYYY.MM.PATCH | SaaS, rapid iteration, no API contracts | 2026.04.1 |

**Use SemVer.** Kestrel has an API that external consumers (frontends, mobile app) depend on. SemVer communicates breaking changes. CalVer is for projects where "version" is just a timestamp (Ubuntu, pip). Kestrel already uses SemVer (0.3.1).

### Independent vs Lockstep Versioning

| Strategy | How It Works | When to Use |
|----------|-------------|-------------|
| **Lockstep** | All components share one version | Tightly coupled, always deployed together |
| **Independent** | Each component has its own version | Loosely coupled, different deploy cadences |
| **Hybrid** | One "platform version" + independent components | Mixed coupling |

**Use Hybrid: Backend drives the version, frontends follow loosely.**

Rationale:
- The backend API is the contract. Its version is the "Kestrel version."
- The web frontend deploys inside the same Docker container as backend -- it inherits the backend version implicitly.
- The mobile app has its own version because app stores require independent versioning (build numbers, native code changes).

**Concrete scheme:**
```
Backend (pyproject.toml):  0.4.0  -- this IS the Kestrel release version
Frontend (package.json):   0.0.0  -- not independently versioned (bundled in Docker)
Mobile (app.json):         1.0.0 (build 1)  -- independent, follows app store conventions
Docker image:              ghcr.io/pleasedodisturb/kestrel:0.4.0
```

**Pre-1.0 rules (current state):**
- MINOR bumps (0.3 -> 0.4) for new features, even if they break things
- PATCH bumps (0.3.1 -> 0.3.2) for bug fixes
- No MAJOR bumps until 1.0 launch

**Post-1.0 rules:**
- MAJOR: breaking API changes (removed endpoints, changed response shapes)
- MINOR: new features, new endpoints, non-breaking additions
- PATCH: bug fixes, performance improvements

**Confidence:** HIGH -- standard SemVer practice for API-driven projects.

---

## 3. Automated Release Workflows

### Tool Comparison

| Tool | Approach | Monorepo | Python Support | Solo-Dev Fit | Maintenance |
|------|----------|----------|----------------|-------------|-------------|
| **release-please** | Creates release PR from conventional commits; human merges to release | Yes (manifest config) | Yes (pyproject.toml) | Excellent -- review before release | Active (Google) |
| **semantic-release** | Fully automated: merge to main = release | Yes (plugins) | Via python-semantic-release | Overkill for self-hosted | Active |
| **changesets** | Manual changeset files per PR; bot aggregates | Yes (native) | No native support | Too much ceremony for solo | Declining maintenance (20/100 score) |
| **release-it** | Interactive CLI, configurable | Limited | Via plugins | Good for manual releases | Active |

### Recommendation: release-please

**Use release-please** because:

1. **Human-in-the-loop**: It creates a release PR that accumulates conventional commits. You merge when ready. Perfect for feature-based releases -- the PR sits open, accumulating changes, until you decide to ship.
2. **Zero ceremony**: No changeset files to create per PR (unlike changesets). Just write conventional commits, which Kestrel already does.
3. **Monorepo native**: Manifest config supports multiple components with different release types (Python for backend, Node for frontend if ever needed).
4. **Python support**: Bumps version in `pyproject.toml` automatically.
5. **GitHub-native**: Creates GitHub Releases with auto-generated changelogs. No external services.

**How release-please works:**
1. You merge PRs to main with conventional commits (`feat(G-123): add scoring engine`)
2. release-please bot opens/updates a "Release PR" that bumps version + updates CHANGELOG
3. When you're ready to release, merge the Release PR
4. GitHub Action triggers on the merge: creates GitHub Release, tags, triggers Docker build

### Configuration for Kestrel

**`release-please-config.json`:**
```json
{
  "$schema": "https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json",
  "release-type": "python",
  "packages": {
    ".": {
      "release-type": "python",
      "component": "kestrel",
      "changelog-path": "CHANGELOG.md",
      "bump-minor-pre-major": true,
      "bump-patch-for-minor-pre-major": false,
      "include-component-in-tag": false,
      "extra-files": [
        "src/career_os/__init__.py"
      ]
    }
  }
}
```

**`.release-please-manifest.json`:**
```json
{
  ".": "0.3.1"
}
```

**`.github/workflows/release.yml`:**
```yaml
name: Release

on:
  push:
    branches: [main]

permissions:
  contents: write
  pull-requests: write

jobs:
  release-please:
    runs-on: ubuntu-latest
    outputs:
      release_created: ${{ steps.release.outputs.release_created }}
      tag_name: ${{ steps.release.outputs.tag_name }}
      version: ${{ steps.release.outputs.version }}
    steps:
      - uses: googleapis/release-please-action@v4
        id: release
        with:
          config-file: release-please-config.json
          manifest-file: .release-please-manifest.json

  # Docker build triggers only when a release is created
  docker:
    needs: release-please
    if: ${{ needs.release-please.outputs.release_created }}
    # ... (see Docker section below)
```

**Confidence:** HIGH -- release-please is well-documented, actively maintained by Google, and widely used.

**Sources:**
- [release-please GitHub](https://github.com/googleapis/release-please)
- [release-please-action](https://github.com/googleapis/release-please-action)
- [Monorepo manifest docs](https://github.com/googleapis/release-please/blob/main/docs/manifest-releaser.md)
- [Monorepo example repo](https://github.com/amarjanica/release-please-monorepo-example)

---

## 4. Changelog Generation

### Automatic from Conventional Commits

release-please generates CHANGELOG.md entries from conventional commits:

```markdown
## [0.4.0](https://github.com/pleasedodisturb/kestrel/compare/v0.3.1...v0.4.0) (2026-04-20)

### Features

* **G-295:** expand golden set with finance and design categories ([4eed038](https://github.com/...))
* **G-300:** sync legacy features to Kestrel platform ([abc1234](https://github.com/...))

### Bug Fixes

* **G-295:** update golden set tests for profile-aware wrapper format ([9fc50f3](https://github.com/...))
```

### Linear Ticket References

Kestrel's commit format already includes Linear ticket IDs in the scope: `feat(G-295): description`. These appear in the changelog automatically because release-please preserves the full commit message.

**Enhancement:** Add a "Tickets" section to release notes via a post-processing step or GitHub Release template that links `G-XXX` patterns to Linear URLs. This is optional polish.

### GitHub Release Notes

GitHub's auto-generated release notes (the "Generate release notes" button) pull from PR titles and labels. release-please creates the GitHub Release automatically with the changelog content, which is better than GitHub's built-in generator because it's structured by commit type.

**Confidence:** HIGH -- this is release-please's core feature.

---

## 5. Release Validation Gates

### Current CI Gates (Already in Place)

Kestrel's CI already runs on every PR to main:

| Gate | Status | Component |
|------|--------|-----------|
| Ruff lint + format | Active | Backend |
| pytest with coverage | Active | Backend |
| Alembic migration check (up + down roundtrip) | Active | Backend |
| API smoke test (health endpoint) | Active | Backend |
| pip-audit (dependency vulnerabilities) | Active | Backend |
| PII leak scan | Active | Backend |
| ESLint | Active | Frontend |
| Vitest with coverage | Active | Frontend |
| npm audit + signature verification | Active | Frontend |
| SonarCloud analysis | Active (informational) | Both |
| actionlint | Active | CI config |

### Additional Gates for Release Workflow

Add these for the release workflow specifically (run after release-please merges):

| Gate | Priority | Rationale |
|------|----------|-----------|
| **Docker build succeeds** | Critical | If the Docker image doesn't build, the release is broken |
| **Docker smoke test** | High | Start the container, hit /health, verify it responds |
| **License check** | Medium | Ensure no GPL-incompatible deps sneak in (MIT project) |
| **Image vulnerability scan** | Medium | Trivy or Grype scan of the built Docker image |

### Pre-Release Checklist (Manual, for Major Releases)

For MINOR+ bumps, before merging the release PR:
- [ ] CHANGELOG.md looks correct
- [ ] Version number makes sense
- [ ] No WIP features accidentally included
- [ ] Migration roundtrip passes (already in CI)
- [ ] Docker image builds locally (`docker compose -f docker-compose.prod.yml build`)

**Confidence:** HIGH -- these are well-established patterns. The existing CI is already strong.

---

## 6. Mobile Release Specifics

### Expo EAS Build Pipeline

Kestrel's mobile app uses Expo (React Native). The release pipeline has two tracks:

| Track | Mechanism | When | App Store Review? |
|-------|-----------|------|-------------------|
| **Native build** | EAS Build | New native deps, SDK upgrades, permission changes | Yes (1-3 days) |
| **OTA update** | EAS Update | JS/styling/image changes | No (instant) |

### EAS Update (OTA) Concepts

- **Channels:** Named deployment targets (e.g., `production`, `staging`)
- **Branches:** Named update streams mapped to channels
- **Updates:** JS bundles + assets pushed to a branch
- **Rollback:** "Republish" a previous stable update on top of the broken one

### Recommended Setup

```
Channel: production  --> Branch: production  (stable releases)
Channel: preview     --> Branch: preview     (testing before release)
```

**Workflow:**
1. Develop on feature branch
2. Merge to main
3. Push OTA update to `preview` channel for testing: `eas update --channel preview --message "feat: new scoring UI"`
4. After validation, push to `production`: `eas update --channel production`
5. For native changes: `eas build --platform all --profile production` then `eas submit`

### When Mobile Diverges from Backend

The mobile app version is independent because:
- App stores require incrementing build numbers
- Native binary releases are slow (review process)
- OTA updates can ship faster than backend releases
- Users may be on old app versions talking to new backend

**Mobile version scheme:**
```
version: "1.0.0"       -- user-facing version (SemVer)
buildNumber: "1"        -- iOS build number (incrementing integer)
versionCode: 1          -- Android version code (incrementing integer)
```

**API compatibility:** The backend should maintain backward compatibility for at least N-2 mobile versions. Use API versioning (`/api/v1/`) or feature flags.

### GitHub Actions for Mobile

```yaml
# .github/workflows/mobile-ota.yml
name: Mobile OTA Update

on:
  workflow_dispatch:
    inputs:
      channel:
        description: 'Update channel'
        required: true
        default: 'preview'
        type: choice
        options: [preview, production]
      message:
        description: 'Update message'
        required: true

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-node@v6
        with:
          node-version: '22'
      - uses: expo/expo-github-action@v8
        with:
          eas-version: latest
          token: ${{ secrets.EXPO_TOKEN }}
      - run: cd mobile && npm ci
      - run: cd mobile && eas update --channel ${{ inputs.channel }} --message "${{ inputs.message }}" --non-interactive
```

### EAS Pricing Note

EAS Update is free for up to a limited number of monthly active users. For a self-hosted app with a small user base, this is likely sufficient. EAS Build has a free tier of ~30 builds/month on the free plan. Check current pricing at [expo.dev/pricing](https://expo.dev/pricing).

**Confidence:** MEDIUM-HIGH -- EAS is well-documented and actively developed. The specific pricing may change; verify before committing to paid features.

**Sources:**
- [EAS Update Introduction](https://docs.expo.dev/eas-update/introduction/)
- [EAS Update: How It Works](https://docs.expo.dev/eas-update/how-it-works/)
- [Production Playbook for OTA Updates](https://expo.dev/blog/the-production-playbook-for-ota-updates)
- [Mastering Expo EAS (Procedure Blog)](https://procedure.tech/blogs/mastering-expo-eas-submit-ota-updates-and-workflow-automation)

---

## 7. Docker Image Releases

### Tagging Strategy

Use multi-level SemVer tags + git SHA for traceability:

| Tag | Example | Mutable? | Purpose |
|-----|---------|----------|---------|
| `v{MAJOR}.{MINOR}.{PATCH}` | `v0.4.0` | Immutable | Pin exact version |
| `v{MAJOR}.{MINOR}` | `v0.4` | Mutable (floats) | "Latest patch in 0.4" |
| `v{MAJOR}` | `v0` | Mutable (floats) | "Latest in 0.x" (skip pre-1.0) |
| `sha-{short}` | `sha-4bf61b3` | Immutable | Trace image to exact commit |
| `latest` | `latest` | Mutable | Convenience only; NEVER use in production compose files |

**Pre-1.0:** Skip the `v{MAJOR}` tag (v0 is meaningless).

### Multi-Platform Builds

Build for `linux/amd64` and `linux/arm64` (covers x86 servers and Apple Silicon / ARM VPS).

The workflow uses standard GitHub Actions for Docker:
- `docker/setup-qemu-action@v3` for cross-platform emulation
- `docker/setup-buildx-action@v3` for Buildx builder
- `docker/login-action@v3` to authenticate with GHCR (uses the built-in GITHUB_TOKEN secret via secrets context)
- `docker/metadata-action@v5` to generate SemVer tags from the release version
- `docker/build-push-action@v6` to build and push for `linux/amd64,linux/arm64`
- GitHub Actions cache (`type=gha`) for layer caching

### Image Scanning

Use **Trivy** (Aqua Security, free, most popular) to scan for CVEs in the Docker image. Run post-build. Upload SARIF results to GitHub Security tab for visibility.

**Confidence:** HIGH -- docker/metadata-action + build-push-action is the standard GitHub Actions Docker workflow, used by Docker's own documentation.

**Sources:**
- [Docker metadata-action](https://github.com/docker/metadata-action)
- [Docker multi-platform builds](https://docs.docker.com/build/ci/github-actions/multi-platform/)
- [Docker tagging best practices (Container Registry)](https://container-registry.com/posts/container-image-versioning/)
- [Trivy GitHub Action](https://github.com/aquasecurity/trivy-action)

---

## 8. Branching Model

### Trunk-Based Development (Recommended)

Kestrel already practices a variant of trunk-based development:
- Feature branches (`G-295/golden-set-expansion`) merge to main via PR
- CI runs on every PR
- Main is always the latest stable state

**This is correct. Do not change it.**

### Why NOT Release Branches

| Approach | When to Use | Kestrel Fit |
|----------|-------------|-------------|
| **Release branches** | Multiple supported versions, enterprise customers, long stabilization | No -- solo dev, single supported version |
| **Trunk + tags** | Single version, fast iteration, small team | Yes |
| **GitFlow** | Large teams, complex release coordination | No -- too heavy for solo dev |

**Trunk-based with tags** means:
1. All development happens on feature branches off main
2. Features merge to main via PR
3. release-please creates a Release PR (a special branch that bumps version)
4. Merging the Release PR = cutting a release (tag + GitHub Release created)
5. No long-lived release branches. If a hotfix is needed for a released version, create a branch from the tag, fix, and release a patch.

### Hotfix Process

For the rare case where you need to patch a released version while main has moved forward:

```
main:  A -- B -- C -- D (v0.4.0) -- E -- F -- G (unreleased)
                                \
hotfix/v0.4.1:                   -- H (security fix)
                                    \
                                     v0.4.1 (tagged, released)
```

1. Branch from the release tag: `git checkout -b hotfix/v0.4.1 v0.4.0`
2. Apply fix, test
3. Manually bump version, update changelog
4. Tag and push: `git tag v0.4.1 && git push origin v0.4.1`
5. Cherry-pick the fix back to main

This is rare enough that it doesn't need automation.

**Confidence:** HIGH -- trunk-based development is well-established for solo/small team projects.

**Sources:**
- [Trunk Based Development](https://trunkbaseddevelopment.com/)
- [Branch for Release](https://trunkbaseddevelopment.com/branch-for-release/)
- [Atlassian: Trunk-Based Development](https://www.atlassian.com/continuous-delivery/continuous-integration/trunk-based-development)

---

## 9. Rollback Strategies

### Per-Component Rollback

| Component | Rollback Mechanism | Speed | Complexity |
|-----------|--------------------|-------|------------|
| **Backend + Web** (Docker) | Pull previous image version from GHCR | ~1 min | Low |
| **Backend** (bare metal) | `git checkout v0.3.1 && pip install -e .` then restart | ~2 min | Low |
| **Mobile (OTA)** | `eas update:republish` -- push previous JS bundle | ~1 min | Low |
| **Mobile (native)** | Submit previous binary to app stores (slow) | 1-3 days | High -- avoid |
| **Database** | Alembic downgrade: `alembic downgrade -1` | ~1 min | Medium -- data loss risk |

### Database Migration Rollback

This is the hardest part. Kestrel already tests migration roundtrips in CI (upgrade + downgrade + upgrade). Key rules:

1. **Never delete columns in the "upgrade" step.** Instead: add new column, migrate data, drop old column in a *later* migration (two-step).
2. **Backups before major releases:** `cp data/career_os.db data/career_os.db.backup-$(date +%Y%m%d)`
3. **Document breaking migrations** in the release notes.

### Docker Rollback Procedure

For self-hosted users, document this in release notes:

```bash
# Rollback to previous version
docker compose -f docker-compose.prod.yml down
# Edit docker-compose.prod.yml to pin the previous image tag
docker compose -f docker-compose.prod.yml up -d

# If database migration needs rollback:
docker exec -it <container> alembic downgrade -1
```

**Confidence:** HIGH -- standard rollback patterns for containerized applications.

---

## 10. Recommended Implementation Plan

### Phase 1: release-please Setup (Low Effort, High Impact)

1. Add `release-please-config.json` and `.release-please-manifest.json` to repo root
2. Add `.github/workflows/release.yml` with release-please action
3. Ensure `pyproject.toml` version is the source of truth
4. Merge to main -- release-please will start accumulating commits into a Release PR

### Phase 2: Docker Build Automation (Medium Effort)

1. Add Docker build + push job to the release workflow (triggers on release_created)
2. Configure GHCR authentication (uses built-in GITHUB_TOKEN, no extra secrets needed)
3. Add multi-platform build (amd64 + arm64)
4. Add Trivy image scanning
5. Test by merging the release-please PR

### Phase 3: Mobile CI/CD (Medium Effort)

1. Set up Expo project with `eas.json` configuration
2. Add `mobile-ota.yml` workflow for OTA updates (manual trigger)
3. Add `mobile-build.yml` for native builds (manual trigger initially)
4. Test OTA update flow end-to-end

### Phase 4: Polish (Low Effort)

1. Add Linear ticket links to release notes (regex post-processing)
2. Add upgrade guide template for MINOR+ releases
3. Document rollback procedures in user-facing docs

### What NOT to Build

- **Do not set up Changesets** -- too much ceremony for solo dev
- **Do not use semantic-release** -- fully automated releases are wrong for self-hosted (you want to review before shipping)
- **Do not create release branches** -- trunk + tags is sufficient
- **Do not automate app store submission yet** -- wait until the mobile app is actually in stores
- **Do not version the frontend independently** -- it ships inside the Docker container

---

## Decision Matrix Summary

| Decision | Choice | Runner-Up | Why |
|----------|--------|-----------|-----|
| Release trigger | Feature-based | Time-based | Solo dev, self-hosted, pre-1.0 |
| Versioning | SemVer (backend-driven) | CalVer | API contracts matter |
| Component versioning | Hybrid (backend = platform version) | Full independent | Frontend bundled in Docker |
| Release automation | release-please | semantic-release | Human-in-the-loop for self-hosted |
| Changelog | Auto from conventional commits | Manual | Already using conventional commits |
| Branching | Trunk-based + tags | GitFlow | Solo dev, high commit frequency |
| Docker registry | GHCR (ghcr.io) | Docker Hub | Free for public repos, native GitHub integration |
| Docker tagging | Multi-level SemVer + SHA | SHA only | Users need stable version pins |
| Mobile OTA | EAS Update | CodePush | Expo-native, maintained |
| Image scanning | Trivy | Grype | Most popular, free, SARIF output |

---

## Sources

### Release Tools
- [release-please (Google)](https://github.com/googleapis/release-please)
- [release-please-action](https://github.com/googleapis/release-please-action)
- [Monorepo manifest docs](https://github.com/googleapis/release-please/blob/main/docs/manifest-releaser.md)
- [Monorepo example repo](https://github.com/amarjanica/release-please-monorepo-example)
- [NPM Release Automation Comparison (Oleksii Popov)](https://oleksiipopov.com/blog/npm-release-automation/)
- [release-please vs semantic-release (Hamza K)](https://www.hamzak.xyz/blog-posts/release-please-vs-semantic-release)
- [NX monorepo release comparison (Hamza K)](https://www.hamzak.xyz/blog-posts/release-management-for-nx-monorepos-semantic-release-vs-changesets-vs-release-it-)

### Versioning
- [Monorepo Versioning (Microsoft ISE)](https://devblogs.microsoft.com/ise/streamlining-development-through-monorepo-with-independent-release-cycles/)
- [Monorepo Version/Tag/Release (Streamdal)](https://medium.com/streamdal/monorepos-version-tag-and-release-strategy-ce26a3fd5a03)
- [Release Management in Monorepos (Graphite)](https://www.graphite.com/guides/release-management-strategies-in-a-monorepo)

### Docker
- [Docker metadata-action](https://github.com/docker/metadata-action)
- [Docker multi-platform builds](https://docs.docker.com/build/ci/github-actions/multi-platform/)
- [Docker tagging best practices (Container Registry)](https://container-registry.com/posts/container-image-versioning/)
- [Trivy GitHub Action](https://github.com/aquasecurity/trivy-action)

### Mobile / Expo
- [EAS Update Introduction](https://docs.expo.dev/eas-update/introduction/)
- [EAS Update: How It Works](https://docs.expo.dev/eas-update/how-it-works/)
- [Production Playbook for OTA Updates](https://expo.dev/blog/the-production-playbook-for-ota-updates)
- [Mastering Expo EAS (Procedure Blog)](https://procedure.tech/blogs/mastering-expo-eas-submit-ota-updates-and-workflow-automation)

### Branching / Strategy
- [Trunk Based Development](https://trunkbaseddevelopment.com/)
- [Atlassian: Trunk-Based Development](https://www.atlassian.com/continuous-delivery/continuous-integration/trunk-based-development)
- [Self-Hosted vs SaaS Release Patterns (GitGuardian)](https://docs.gitguardian.com/self-hosting/saas-vs-self-hosted)
- [Building Self-Hostable Apps (FusionAuth)](https://fusionauth.io/blog/building-self-hostable-application)
