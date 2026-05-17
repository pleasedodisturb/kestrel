# Supply-Chain Security & Release Engineering (2026)

Format: WHY / HOW / PITFALL per item.

## Security Hardening

**Secret scanning + push protection** — WHY: blocks credential leaks at `git push`. HOW: Settings → Code security → enable both (free for public repos, GHAS for private). PITFALL: only catches partner-recognized patterns; add custom regex for internal tokens. https://docs.github.com/en/code-security/secret-scanning

**CodeQL / SAST** — WHY: semantic dataflow finds injection/auth bugs lint cannot. HOW: `Security → Set up code scanning → CodeQL`, runs on PR + weekly cron. PITFALL: tune `paths-ignore` and queries-suite or PR latency balloons. https://docs.github.com/en/code-security/code-scanning

**dependency-review-action** — WHY: blocks PRs introducing known-vuln or bad-license deps. HOW: add `actions/dependency-review-action@v4` to PR workflow with `fail-on-severity: high`. PITFALL: only inspects the diff; pair with Dependabot for stock issues. https://github.com/actions/dependency-review-action

**Dependabot** (pick this) — WHY: native, free, auto-grouped PRs, security advisories integrated. HOW: `.github/dependabot.yml` with `groups:` per ecosystem. PITFALL: weaker monorepo support than Renovate; cap `open-pull-requests-limit`. https://docs.github.com/en/code-security/dependabot

**Private vulnerability reporting** — WHY: gives reporters a private channel; produces draft GHSA. HOW: Settings → Security → enable PVR; triage in Security tab. PITFALL: not enabled by default on forks/older repos. https://docs.github.com/en/code-security/security-advisories

**Coordinated disclosure / CVE via GHSA** — WHY: GitHub is a CNA — request CVE inside the draft advisory. HOW: draft GHSA → "Request CVE" → publish on patch release. PITFALL: publish only after fix lands; embargo broken if commits leak the fix early. https://docs.github.com/en/code-security/security-advisories/repository-security-advisories

## Identity & Provenance

**Signed commits + tags** — WHY: proves authorship; "Verified" badge. HOW: SSH signing (`git config gpg.format ssh`) is simplest; Sigstore `gitsign` for keyless OIDC. PITFALL: enforce via branch protection "Require signed commits" or it's cosmetic. https://docs.sigstore.dev/cosign/signing/gitsign/

**OpenSSF Scorecard** — WHY: 18+ automated checks scored 0–10 (Branch-Protection, Token-Permissions, Pinned-Dependencies, Signed-Releases, SAST). HOW: `ossf/scorecard-action` weekly cron + on push to main, publish badge. PITFALL: needs `id-token: write` and a `SCORECARD_TOKEN` PAT for private metadata. https://scorecard.dev/

**OpenSSF Best Practices badge** — WHY: passing/silver/gold self-attestation reviewed by humans. HOW: register at bestpractices.coreinfrastructure.org, answer the criteria. PITFALL: silver/gold demand 2-person review and crypto-hygiene most small projects skip. https://www.bestpractices.dev/

**SBOM (SPDX/CycloneDX)** — WHY: regulatory (EO 14028, EU CRA) + dep visibility. HOW: GitHub auto-SBOM via dependency graph "Export SBOM" (SPDX JSON) or `gh sbom -c` for CycloneDX. PITFALL: dependency-graph SBOM omits OS/system packages — generate at build with Syft for full coverage. https://github.blog/2023-03-28-introducing-self-service-sboms/

**SLSA provenance** — WHY: tamper-evident link from source → artifact (SLSA L3). HOW: `slsa-framework/slsa-github-generator` emits `*.intoto.jsonl` attached to the release; verify with `slsa-verifier`. PITFALL: must call as a reusable workflow (not local job) to keep L3 isolation. https://slsa.dev/

**Build attestations** — WHY: lighter Sigstore-signed provenance for any artifact. HOW: `actions/attest-build-provenance@v2` with `id-token: write`, `attestations: write`. PITFALL: distinct from SLSA generator — pick one path, don't double-sign. https://github.com/actions/attest-build-provenance

## Release Engineering

**SemVer** — WHY: consumers reason about breakage from version alone. HOW: MAJOR.MINOR.PATCH; pre-1.0 minor = breaking. PITFALL: `0.x` does not exempt you from changelog discipline. https://semver.org/

**Conventional Commits + commitlint** — WHY: machine-parseable history drives version bumps + changelogs. HOW: `@commitlint/config-conventional` in Husky `commit-msg` hook. PITFALL: squash-merge must preserve the conventional title or release tooling miscomputes bumps. https://www.conventionalcommits.org/

**Release automation (pick one)** —
- **release-please** (Google) — best for polyglot/multi-language; "Release PR" model. https://github.com/googleapis/release-please
- **semantic-release** — fully automatic on merge; single-package npm-centric. https://semantic-release.gitbook.io/
- **changesets** — explicit `.changeset/*.md` files; superior for JS monorepos. https://github.com/changesets/changesets
- **cargo-release** — Rust crates with workspace support.
PITFALL: switching mid-project rewrites tag history — choose once.

**Signed release artifacts** — WHY: downloaders verify integrity offline. HOW: `sigstore/gh-action-sigstore-python` or `cosign sign-blob`; publish `SHA256SUMS` + `.sig`. PITFALL: GPG keys expire/rotate — Sigstore keyless avoids long-lived secrets. https://docs.sigstore.dev/

**.github/release.yml** — WHY: auto-categorizes PRs into release notes by label. HOW: define `categories:` (Features/Fixes/Breaking) keyed on labels. PITFALL: requires PR labels to be applied at merge time — automate with labeler.

**Pre-release channels** — WHY: ship `next`/`canary`/`beta` without poisoning `latest`. HOW: tag `v1.2.0-beta.1`, npm `--tag next`, GitHub "pre-release" checkbox. PITFALL: SemVer pre-release ordering is alpha < beta < rc; mixing names breaks resolvers.

**Deprecation policy** — WHY: predictable removal windows. HOW: doc minimum 1 minor cycle warning, runtime `DeprecationWarning`, `npm deprecate`. PITFALL: silent removal in patch is the #1 trust-killer.

**Container scanning + base images** — WHY: most CVEs live in OS layer. HOW: Trivy or Grype in CI fail-on HIGH; switch FROM to `gcr.io/distroless/*` or Chainguard Images. PITFALL: distroless lacks shell — debug with `:debug` tag, not by reverting to Alpine. https://github.com/aquasecurity/trivy

---

## Summary (≤50 words)

Enable secret scanning + push protection, CodeQL, dependency-review, and Dependabot. Sign commits (gitsign) and releases (Sigstore). Publish SBOMs and SLSA provenance via attest-build-provenance. Adopt Conventional Commits with release-please (polyglot) or changesets (JS monorepo). Run Scorecard weekly; scan containers with Trivy on distroless bases.
