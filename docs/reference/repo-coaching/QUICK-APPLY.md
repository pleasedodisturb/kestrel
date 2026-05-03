# Quick-Apply Playbook

A time-budgeted plan to apply the masterlist to any repo. Phases are independent — pick what matches your hour budget today.

| Phase | Time | What you get |
|---|---|---|
| 0. Foundation | 15 min | License + README hero + .gitignore sanity |
| 1. Community health | 30 min | CoC, FUNDING, CITATION, SUPPORT, .gitattributes |
| 2. `.github/` plumbing | 1 hr | Issue forms, PR template, dependabot, CODEOWNERS |
| 3. CI security | 2 hr | SHA-pinned actions, least-priv permissions, actionlint, zizmor |
| 4. Supply-chain | 1 hr | Scorecard, secret scanning, private vuln reporting, signed commits |
| 5. Releases | 1 hr | Conventional Commits, release-please, signed artifacts |
| 6. Marketing hero | 2 hr | Social preview, comparison table, demo GIF, badges |
| 7. Discovery | 2 hr | Topics, awesome-list submissions, llms.txt |
| 8. Launch prep | 1 day | Blog post, social handles, HN/Reddit/PH choreography |

All snippet files referenced live under [`./snippets/`](./snippets/). Edit the placeholders (`OWNER`, `REPO`, `SHA`, `email@example.com`) before committing.

---

## Phase 0 — Foundation (15 min)

**Goal:** the floor. Anyone landing on the repo today should not bounce.

```bash
# 1. Verify license is detected by GitHub
gh repo view --json licenseInfo
# If null: pick one at https://choosealicense.com/ and commit a real LICENSE file.
# Do not edit the license body — even whitespace breaks GitHub's licensee detection.

# 2. Confirm .gitignore is comprehensive
# Use: https://github.com/github/gitignore as a base
curl -fsSL https://raw.githubusercontent.com/github/gitignore/main/Python.gitignore > .gitignore  # adapt language
```

**README hero check** (open the rendered README on GitHub):
- [ ] Logo or wordmark visible above the fold
- [ ] One-sentence pitch in `<strong>` tags directly under
- [ ] A copy-pasteable install/run command in the first viewport
- [ ] License + version + CI badges (max 5)

If any of these are missing, copy from [`snippets/README-template.md`](./snippets/README-template.md) and adapt.

**Commit:** `chore: tighten readme hero and license detection`

---

## Phase 1 — Community health (30 min)

**Goal:** GitHub's "Community profile" page (Insights → Community Standards) shows a full green checklist.

```bash
# Run from repo root.

# CODE_OF_CONDUCT.md — Contributor Covenant 2.1
cp docs/reference/repo-coaching/snippets/CODE_OF_CONDUCT.md ./CODE_OF_CONDUCT.md
# Edit: replace conduct@example.com with a real address.

# .github/FUNDING.yml — adds Sponsor button
mkdir -p .github
cp docs/reference/repo-coaching/snippets/FUNDING.yml ./.github/FUNDING.yml
# Edit: uncomment the lines that match your funding channels.

# CITATION.cff — only if academics may cite (delete if not)
cp docs/reference/repo-coaching/snippets/CITATION.cff ./CITATION.cff
# Edit: title, authors, repository-code, abstract.

# SUPPORT.md — diverts "help me" issues to the right channel
cp docs/reference/repo-coaching/snippets/SUPPORT.md ./SUPPORT.md
# Edit: replace OWNER/REPO and Discord invite.

# .gitattributes — line endings + linguist overrides
cp docs/reference/repo-coaching/snippets/.gitattributes ./.gitattributes
# Edit: add language-specific rules if your language stats are wrong.
```

**Verify:**
- Open `https://github.com/OWNER/REPO/community` — every item green.
- Open repo header — "Sponsor" button is now visible.

**Commit:** `chore: add community health files (CoC, FUNDING, SUPPORT, CITATION, gitattributes)`

---

## Phase 2 — `.github/` plumbing (1 hr)

**Goal:** every new issue and PR enters a structured pipeline.

```bash
mkdir -p .github/ISSUE_TEMPLATE

# Issue forms (YAML — not markdown)
cp docs/reference/repo-coaching/snippets/bug_report.yml      .github/ISSUE_TEMPLATE/bug_report.yml
cp docs/reference/repo-coaching/snippets/feature_request.yml .github/ISSUE_TEMPLATE/feature_request.yml
cp docs/reference/repo-coaching/snippets/issue-config.yml    .github/ISSUE_TEMPLATE/config.yml
# Edit: replace OWNER/REPO and Discord invite in config.yml.

# PR template
cp docs/reference/repo-coaching/snippets/pull_request_template.md .github/pull_request_template.md

# Dependabot
cp docs/reference/repo-coaching/snippets/dependabot.yml .github/dependabot.yml
# Edit: keep only the package-ecosystem blocks you actually use.

# CODEOWNERS
cp docs/reference/repo-coaching/snippets/CODEOWNERS .github/CODEOWNERS
# Edit: replace @OWNER with your handle/team. Add area-specific lines.

# Auto-categorized release notes
cp docs/reference/repo-coaching/snippets/release.yml .github/release.yml

# SECURITY.md — disclosure policy
cp docs/reference/repo-coaching/snippets/SECURITY.md ./SECURITY.md
# Edit: replace OWNER/REPO and security@example.com.
```

**Then in the GitHub UI** (one-time, no PR):

1. **Settings → Security → Private vulnerability reporting → Enable.**
2. **Apply the label taxonomy** with `gh label clone` or [EndBug/label-sync](https://github.com/EndBug/label-sync) using [`snippets/labels.yml`](./snippets/labels.yml):
   ```bash
   gh label create "type/bug" --color "e11d48" --description "Something broken"
   # …repeat for each label in snippets/labels.yml, or use label-sync to apply in one shot
   ```
3. **Settings → General → Discussions → Enable** (then update `config.yml` Discussions link).

**Commit:** `chore(github): add issue forms, PR template, dependabot, CODEOWNERS, SECURITY policy`

---

## Phase 3 — CI security (2 hr)

**Goal:** every workflow follows the 2026 hardening baseline. This is the highest-leverage security work.

### 3a. Audit current workflows (10 min)

```bash
# What action references exist?
grep -rh "uses:" .github/workflows/ | sort -u

# Are any pinned by tag (@v4) instead of SHA? Those are the unsafe ones.
grep -rE "uses:.*@(v[0-9]|main|master)\b" .github/workflows/ || echo "all pinned by SHA"

# Permissions audit — every workflow should have permissions: {} at root
grep -L "^permissions:" .github/workflows/*.yml
```

### 3b. Pin every action by SHA (30–60 min)

For each `uses: org/repo@vN` in your workflows, look up the SHA at `https://github.com/org/repo/releases/tag/vN` and replace:

```yaml
# before
- uses: actions/checkout@v4

# after
- uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11  # v4.1.1
```

Tools: [`pin-github-action`](https://github.com/mheap/pin-github-action) automates this:

```bash
npx pin-github-action .github/workflows/ci.yml
```

### 3c. Add the standard CI hygiene block (15 min)

Open every workflow and ensure the top has:

```yaml
permissions: {}

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

Per job:
- `runs-on: ubuntu-24.04` (not `ubuntu-latest`)
- `timeout-minutes: 10` or appropriate
- `permissions:` block granting only what's needed (e.g. `contents: read`)

If you don't have a CI workflow yet: copy [`snippets/ci.yml`](./snippets/ci.yml) to `.github/workflows/ci.yml`.

### 3d. Add workflow linters (15 min)

```bash
cp docs/reference/repo-coaching/snippets/workflow-lint.yml .github/workflows/workflow-lint.yml
```

This adds `actionlint` (syntax + shell injection) and `zizmor` (security misconfig) to every PR touching `.github/workflows/`.

### 3e. Branch protection (5 min, GitHub UI)

**Settings → Branches → Add rule for `main`:**
- ✅ Require a pull request before merging (1+ reviewer, dismiss stale, require code-owner)
- ✅ Require status checks before merging — pick your CI jobs
- ✅ Require branches to be up to date
- ✅ Require signed commits (optional but recommended)
- ✅ Require linear history (if you squash-merge)
- ❌ Do not allow bypassing the above settings (uncheck admin bypass)

**Commit:** `chore(ci): pin actions by SHA, add least-priv permissions, add workflow linters`

---

## Phase 4 — Supply-chain (1 hr)

**Goal:** OpenSSF Scorecard ≥ 7, signed commits, private vulnerability reporting.

### 4a. Scorecard (15 min)

```bash
cp docs/reference/repo-coaching/snippets/scorecard.yml .github/workflows/scorecard.yml
# Then push, let it run, and add the badge to README:
```

```markdown
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/OWNER/REPO/badge)](https://scorecard.dev/viewer/?uri=github.com/OWNER/REPO)
```

### 4b. Secret scanning + push protection (5 min, GitHub UI)

**Settings → Code security → Secret scanning:** enable scanning + push protection. Free for public repos.

### 4c. Signed commits (10 min, local)

The lowest-friction option in 2026 is SSH-key signing:

```bash
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_ed25519.pub
git config --global commit.gpgsign true

# Tell GitHub the key is also a signing key:
# Settings → SSH and GPG keys → New SSH key → Key type: Signing.
```

For keyless signing via Sigstore: use [`gitsign`](https://github.com/sigstore/gitsign).

### 4d. Private vulnerability reporting (1 min)

**Settings → Security → Private vulnerability reporting → Enable.** Done.

### 4e. SBOM in releases (10 min)

Add to your release workflow:

```yaml
- name: Generate SBOM
  uses: anchore/sbom-action@v0
  with:
    format: cyclonedx-json
    output-file: sbom.cdx.json

- uses: actions/attest-build-provenance@v2
  with:
    subject-path: 'dist/*'
```

Or rely on GitHub's auto-SBOM: `Insights → Dependency graph → Export SBOM`.

**Commit:** `chore(security): add Scorecard, signed commits, SBOM, private vuln reporting`

---

## Phase 5 — Releases (1 hr)

**Goal:** every merge produces a clean changelog and tagged release without human glue.

### 5a. Conventional Commits + commitlint (15 min)

```bash
npm install --save-dev @commitlint/cli @commitlint/config-conventional husky
npx husky init
echo 'npx --no -- commitlint --edit "$1"' > .husky/commit-msg
chmod +x .husky/commit-msg

cat > commitlint.config.js <<'EOF'
module.exports = { extends: ['@commitlint/config-conventional'] };
EOF
```

(Python projects: skip Husky, use [pre-commit](https://pre-commit.com/) with [`commitlint`](https://github.com/alessandrojcm/commitlint-pre-commit-hook).)

### 5b. Release automation — pick one

**Polyglot or non-JS:** [release-please](https://github.com/googleapis/release-please)

```bash
mkdir -p .github/workflows
cat > .github/workflows/release-please.yml <<'EOF'
name: release-please
on:
  push:
    branches: [main]
permissions: {}
jobs:
  release-please:
    runs-on: ubuntu-24.04
    permissions:
      contents: write
      pull-requests: write
    steps:
      - uses: googleapis/release-please-action@v4
        with:
          release-type: python   # or node, go, rust, simple, etc.
EOF
```

**JS monorepo:** [changesets](https://github.com/changesets/changesets).
**Single npm package:** [semantic-release](https://semantic-release.gitbook.io/).
**Rust:** [cargo-release](https://github.com/crate-ci/cargo-release).

### 5c. Auto-categorized release notes

Already covered in Phase 2 via `.github/release.yml`. Confirm your PR labels match the categories.

**Commit:** `chore(release): add commitlint and release-please`

---

## Phase 6 — Marketing hero (2 hr)

**Goal:** the README and social preview are the brand.

### 6a. Social preview image (30 min)

- Size: **1280×640 PNG**, ≤1 MB.
- Logo + tagline. Tagline text ≥ 24px so it survives Slack/Twitter thumbnail rendering.
- Tools: Figma, [og-image.vercel.app](https://og-image.vercel.app/), Canva.
- Upload via **Settings → General → Social preview → Edit**.

### 6b. Comparison table (15 min)

In your README, after the quickstart:

```markdown
## Why ProjectName

| | ProjectName | Alt A | Alt B |
|---|---|---|---|
| Self-hosted | ✅ | ❌ | ✅ |
| Zero-config start | ✅ | ❌ | ❌ |
| <Your wedge> | ✅ | ❌ | ❌ |
```

Honest checkmarks only — dishonest ones invite HN dunk threads.

### 6c. Demo GIF or asciinema cast (45 min)

For terminal: [`charmbracelet/vhs`](https://github.com/charmbracelet/vhs).

```bash
# install
brew install vhs

# create a tape
cat > demo.tape <<'EOF'
Output demo.gif
Set FontSize 18
Set Width 1200
Set Height 700
Type "your-cli init"
Enter
Sleep 2s
EOF

vhs demo.tape    # produces demo.gif (≤2 MB target)
```

For UI: Loom / Tella / CleanShot. Trim to ≤30 seconds. Save under `docs/hero.gif`.

Embed in README hero:

```html
<p align="center">
  <img src="docs/hero.gif" alt="30-second demo" width="800">
</p>
```

### 6d. Badges audit (10 min)

Pick **3–5 max**:
- CI status (shields.io/github/actions)
- Latest version (npm / pypi / cargo)
- License
- OpenSSF Scorecard
- Discord member count (if active community)

**Remove:** "made with love", framework logos, redundant counters. See full pattern in [`snippets/README-template.md`](./snippets/README-template.md).

### 6e. Logo light/dark variants (20 min)

If you only have one logo, the dark-theme view of GitHub looks broken for half your visitors:

```html
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/logo-dark.svg">
  <img alt="ProjectName" src="docs/logo-light.svg" width="280">
</picture>
```

**Commit:** `docs(readme): add social preview, comparison, demo GIF, light/dark logo`

---

## Phase 7 — Discovery (2 hr)

**Goal:** people who would love your project actually find it.

### 7a. GitHub topics audit (5 min)

GitHub UI → click the gear next to "About" → Topics. Pick **up to 20** from the popular slugs at [github.com/topics](https://github.com/topics). Reference list: [`snippets/topics.txt`](./snippets/topics.txt).

### 7b. Repo description (5 min)

Same panel. Write **≤120 chars**, keyword-dense, ends with link to docs.

```
Self-hosted, AI-powered job-search platform. Discover jobs, score them, track your pipeline. https://yourproject.dev
```

### 7c. Awesome-list submissions (45 min)

Find candidates:

```bash
# Search github.com/topics for awesome-* lists in your category:
# https://github.com/topics/awesome-list
# https://github.com/sindresorhus/awesome
# Niche-specific: awesome-selfhosted, awesome-llm-apps, awesome-fastapi, etc.
```

For each, open a PR adding **one alphabetized line**:

```markdown
- [Project Name](https://github.com/OWNER/REPO) - One-sentence description ending with a period.
```

Read each list's `CONTRIBUTING.md` first — many auto-close PRs that violate sort/format.

### 7d. `llms.txt` for docs (15 min)

If you have a docs site, serve at `/llms.txt`:

```
# ProjectName

> One-paragraph project summary.

## Docs
- [Quickstart](https://yourproject.dev/quickstart): How to install and run in 60 seconds.
- [API reference](https://yourproject.dev/api): Full REST + SDK docs.
- [Architecture](https://yourproject.dev/architecture): System design and data flow.

## Optional
- [Blog](https://yourproject.dev/blog): Engineering deep-dives.
```

And `/llms-full.txt` = concatenated docs corpus. Wire to your docs build so they don't go stale. ([spec](https://llmstxt.org/))

### 7e. Pinned repos & org profile (10 min)

Personal profile: pin this repo. Org profile: create a `.github` repo with `profile/README.md` describing the org.

**Commit:** _(no code change — these are GitHub UI / external PRs)_

---

## Phase 8 — Launch prep (1 day)

Only do this once Phases 0–7 are clean. A great launch on a half-built repo wastes the launch.

### 8a. Pre-launch (T−14 to T−1)

- **Day -14:** Email/DM 5–10 friendly users for beta feedback. Fix issues they hit.
- **Day -7:** Draft Show HN title + first comment. Title format: `Show HN: ProjectName – plain claim of what it does`. No marketing fluff.
- **Day -7:** Pitch newsletters (TLDR, console.dev, bytes.dev, [your language]'s This Week newsletter). Editors want exclusivity windows; pitch ≥1 week ahead.
- **Day -3:** Pre-write the launch blog post: problem → why existing tools fail → solution → demo GIF → architecture → CTA. Aim 1500 words.
- **Day -1:** Recruit 3 launch buddies who'll genuinely upvote/comment within the first hour.

### 8b. Launch day (T+0)

Coordinate within 2 hours, ideally **Tue/Wed/Thu, 8–10 am ET**:

1. Post Show HN. Be present in comments for the next 4 hours — it's where ranking happens.
2. Post on relevant subreddits (read each sub's rules first; have prior karma).
3. Post X / Bluesky / Mastodon thread linking to the blog post.
4. Send the launch newsletter to your waitlist.
5. Notify your community channel.

If SaaS-flavored: also Product Hunt, queued for 12:01 am PT same day. ([playbook](https://dev.to/iris1031/product-hunt-launch-playbook-the-definitive-guide-30x-1-winner-1pbh))

### 8c. Post-launch (T+1 to T+30)

- **Week 1:** Reply to every comment, every issue, every email. Ship a visible improvement.
- **Week 2:** Publish "what we learned" follow-up with traffic + ⭐ numbers and the most-asked question's answer.
- **Week 3–4:** First weekly changelog post. Set the cadence.

### 8d. What NOT to do

- ❌ Buy stars. Vendors are detected; GitHub purges; trust evaporates. ([case study](https://dev.to/iris1031/how-to-get-more-github-stars-the-definitive-guide-33k-stars-case-study-2kjo))
- ❌ Astroturf comment threads.
- ❌ Use clickbait titles ("This 10× faster than X" without proof).
- ❌ Disappear from comments.
- ❌ Promise features in launch posts you can't ship.

---

## Done — what to keep doing

- **Weekly**: triage issues, reply to PRs within your stated SLA, ship one visible thing.
- **Monthly**: changelog post. Even short.
- **Quarterly**: refresh badges, audit Action SHA pins (Dependabot helps), review the masterlist for new gaps.
- **Yearly**: re-run the full audit, update `CITATION.cff` version, refresh social preview if branding changed.

---

## When you're stuck

- Item from masterlist looks unclear → see the deep-dive in [`./research/`](./research/) for citations.
- Action snippet placeholder confusing → see [`./snippets/`](./snippets/) for the ready file with comments.
- Strategic choice (license / governance / launch timing) → see [`./LANDSCAPE.md`](./LANDSCAPE.md) and [`./FORM-FACTOR.md`](./FORM-FACTOR.md) for context.
- For a working example of a real audit applied to one repo → [`./AUDIT.md`](./AUDIT.md) (Kestrel).
