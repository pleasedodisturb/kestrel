# Repo Hygiene: Root Files & `.github/`

Scope: technical hygiene only. Excludes CI workflows and releases.

## Documentation

**README.md** — First impression and quickstart. Structure: hero (1-line pitch + badges + screenshot), quickstart (install/run in <5 commands), body (features, config, links). Pitfall: burying the install command under marketing copy; keep it above the fold.

**CONTRIBUTING.md** — Sets contributor expectations and unblocks PRs. Include: dev setup, test/lint commands, branch/commit conventions, PR checklist, DCO/CLA stance. Pitfall: linking only — GitHub surfaces a "Contributing" banner on new-PR pages only when the file is present at root, `docs/`, or `.github/` ([docs](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/setting-guidelines-for-repository-contributors)).

**CODE_OF_CONDUCT.md** — Signals safe community. Use Contributor Covenant 2.1 verbatim with your enforcement email substituted ([contributor-covenant.org](https://www.contributor-covenant.org/version/2/1/code_of_conduct/)). Pitfall: leaving the `[INSERT CONTACT METHOD]` placeholder unfilled.

**SECURITY.md** — Tells researchers where to send vulns. Enable GitHub Private Vulnerability Reporting (Settings → Security) and link to it; list supported versions and disclosure SLO. Pitfall: directing reporters to public issues — that burns the embargo ([docs](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)).

**SUPPORT.md** — Diverts "help me" issues to the right channel (Discussions, Stack Overflow, paid support). One screen of links. Pitfall: omitting it; users open issues for support questions and clog the tracker.

**CHANGELOG.md** — Human-readable history. Follow [Keep a Changelog 1.1](https://keepachangelog.com/en/1.1.0/) (sections: Added/Changed/Deprecated/Removed/Fixed/Security; reverse-chronological; SemVer-tagged). Pitfall: relying on auto-generated GitHub release notes — fine for ops, hostile for end-users.

**CITATION.cff** — Only if your repo is cited in academic work; GitHub renders a "Cite this repository" button when present ([citation-file-format.github.io](https://citation-file-format.github.io/)). Skip for typical SaaS apps.

## Licensing

**LICENSE** — Picks who can use what. Decision: **MIT** for max adoption (4-line, no patent grant); **Apache-2.0** when you need an explicit patent grant + NOTICE handling; **AGPL-3.0** when you ship a SaaS competitor moat (network use triggers source disclosure); **BUSL-1.1** when you want source-available with a 4-year delayed-OSS conversion (HashiCorp/MariaDB pattern — *not* OSI-approved). GitHub auto-detects via [licensee](https://github.com/licensee/licensee) and matches against SPDX text. Pitfall: editing the license text (even whitespace/trailing copyright lines) breaks detection — keep LICENSE pristine and put project notices elsewhere ([docs](https://docs.github.com/articles/licensing-a-repository)).

## Repo Configuration

**CODEOWNERS** — Auto-requests reviewers and gates protected branches. Lookup order: `.github/` → root → `docs/` (first wins). Pitfall: stale owners block every PR; pair with a team handle, not individual users ([docs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)).

**.gitignore** — Use a per-language template from [github/gitignore](https://github.com/github/gitignore); commit lockfiles, ignore venvs/`node_modules`/build dirs. Pitfall: committing `.env` then trying to `.gitignore` it later — already in history.

**.gitattributes** — Normalizes line endings (`* text=auto`) and overrides Linguist stats. Mark generated/vendored paths: `dist/* linguist-generated`, `vendor/* linguist-vendored` ([linguist overrides](https://github.com/github-linguist/linguist/blob/main/docs/overrides.md)). Pitfall: repo language shows as "HTML" because a built docs dir wasn't excluded.

**.editorconfig** — Cross-editor indent/EOL/charset agreement; most IDEs honor it natively ([editorconfig.org](https://editorconfig.org/)). Pitfall: contradicting your formatter (Prettier/Ruff) — keep settings aligned.

**.env.example** — Documents required env vars without leaking values. Commit it; gitignore real `.env`. Pitfall: drifting from actual code — add a startup check that fails loudly on missing keys.

**Toolchain pins** — `.python-version` (pyenv), `.nvmrc` (nvm), `.tool-versions` (asdf/[mise](https://mise.jdx.dev/)). Pick one based on team tooling; `.tool-versions` is the most portable. Pitfall: pinning patch versions you never bump.

## `.github/` directory

**ISSUE_TEMPLATE/*.yml** — Use [YAML issue forms](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms) (`type: textarea/dropdown/input/checkboxes`) for structured triage. Pitfall: YAML form file extension must be `.yml`, not `.yaml`.

**ISSUE_TEMPLATE/config.yml** — `blank_issues_enabled: false` plus `contact_links:` (Discussions, Discord, security advisory). Pitfall: forgetting this routes lazy users back to free-form issues.

**pull_request_template.md** — Single template at `.github/pull_request_template.md`; rendered into PR body. Multiple templates require `?template=` query param (rarely worth it).

**dependabot.yml** — Lives at `.github/dependabot.yml`. Always include the `github-actions` ecosystem (directory `/`) — it's the easiest CVE vector. Use `groups:` to bundle minor/patch updates into one PR per ecosystem ([reference](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference)). Pitfall: ungrouped updates flood reviewers and burn CI minutes.

**FUNDING.yml** — Adds the "Sponsor" button. Keys: `github:`, `custom:`, `open_collective:`, etc. Skip on company-owned repos.

## Repo metadata (Settings → General)

Description (160 chars), homepage URL, topics (max 20, lowercase, hyphenated), social preview image (1280x640 PNG/JPG <1MB). Pitfall: missing topics — kills SEO and the GitHub topic-explore surface.
