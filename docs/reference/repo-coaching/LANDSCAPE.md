# Landscape — what already exists in repo coaching

Mapping of existing tools, lists, and bots in the "audit / score / coach a GitHub repo" space, plus a gap analysis to inform form-factor choice.

## A. Auditing & scoring tools

| Tool | What it does | Strength | Gap |
|---|---|---|---|
| [OpenSSF Scorecard](https://scorecard.dev/) | 18+ automated security checks (branch protection, signed releases, pinned deps, fuzzing, etc.). REST API for any public repo. | Industry standard, actionable, auto-runnable in CI. SLSA + Sigstore aware. | Security-only. Says nothing about README quality, marketing, community health. |
| [OpenSSF Best Practices Badge](https://www.bestpractices.dev/) | Self-assessed questionnaire → passing/silver/gold badge. | Broader than Scorecard — covers governance, change control, vulnerability management. | Self-assessed = honor system; UI is dated. |
| [GitHub Community Profile](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions) | Built-in checklist in Insights → Community Standards. | Free, embedded, zero-setup. | ~6 items only (README, license, CoC, contributing, issue/PR templates). Doesn't grade quality. |
| [repolinter](https://github.com/todogroup/repolinter) (Linux Foundation TODO Group) | Configurable rule engine (presence-of-file, regex-in-file). | Mature, plugin-able. | Last meaningful release 2022; presence-only — can't grade README content quality. |
| [Repo Doctor](https://dev.to/glaucia86/repo-doctor-ai-powered-github-repository-health-analyzer-136n) | AI-powered analyzer; 0–100 score across 6 categories with remediation hints. | LLM-based grading of qualitative aspects. | Newer tool; ecosystem unproven; coverage of marketing/branding unclear. |
| [Repo Health Check](https://repocheck.com/) | PR-effectiveness + issue-effectiveness scoring (0–10). | Operational metrics specifically. | Narrow scope (no security, no marketing). |
| [RepoAudit](https://repoaudit-home.github.io/) | LLM-agent for repository-level _bug_ auditing (code quality / security defects). | Deep code analysis. | Code-quality only; not repo-hygiene. |
| [Snyk Advisor](https://snyk.io/advisor/) | Per-package health: popularity, maintenance, security, community. | Useful for picking deps; widely cited. | Per-package, not per-repo. |
| [Socket.dev](https://socket.dev/) | Supply-chain security for packages — capability changes per release. | Best-in-class for npm/PyPI supply-chain risk. | Package focus; doesn't evaluate repo as a project. |
| [deps.dev](https://deps.dev/) | Google's dependency-graph + Scorecard scores for any package. | API for programmatic queries. | Same as Scorecard plus dep view. |
| [libraries.io / SourceRank](https://libraries.io/) | Composite popularity/quality score per package. | Simple, broad coverage. | Stale-ish; presence-of-file heuristics. |
| [OSPO Code Scanner](https://github.com/alliander-opensource/ospo-code-scanner) (Alliander) | Combines Scorecard + repolinter + custom OSPO rules. | Closer to "OSS hygiene" than Scorecard alone. | Internal tool, niche audience. |
| [DeepSource](https://deepsource.io/) / [Codacy](https://www.codacy.com/) / [SonarQube](https://www.sonarsource.com/) | Code-quality SaaS. | Static analysis + style at scale. | Code-only; nothing on community/marketing. |
| [CHAOSS metrics](https://chaoss.community/) | Open standard for community health metrics (bus factor, lottery factor, time-to-merge). | Rigorous, vendor-neutral. | Data-collection oriented; not a product. |
| [repostatus.org](https://www.repostatus.org/) | Simple lifecycle badge: Concept / WIP / Active / Inactive / Unsupported / Abandoned. | Sets contributor expectations. | One badge; not an audit. |
| [Tidelift](https://tidelift.com/) | Enterprise contracts for "promised maintenance" of OSS deps. | Funding model, audit by proxy. | Vendor-driven, not a public audit tool. |

**Net:** the **technical/security** layer is well-served (Scorecard + Best Practices + Snyk/Socket are mature). The **operational** layer is partially served (CHAOSS, repocheck.com). The **marketing/branding** layer has essentially no automated tooling beyond awesome-list inclusion.

## B. AI / PR-review bots (adjacent but not "repo coaching")

| Tool | What it does | Notes |
|---|---|---|
| [CodeRabbit](https://www.coderabbit.ai/) | Most-installed AI PR reviewer (2M+ repos, 13M+ PRs). | PR-level, not repo-level. ([source](https://www.devtoolsacademy.com/blog/state-of-ai-code-review-tools-2025/)) |
| [Greptile](https://www.greptile.com/) | AI PR reviewer with full-codebase indexing. 82% bug-catch in benchmark. | PR-level. |
| [Ellipsis.dev](https://www.ellipsis.dev/) | AI reviewer that also _fixes_ code. | PR-level. |
| [Qodo Merge / CodiumAI](https://www.qodo.ai/) | AI PR reviewer + test generation. | PR-level. |
| [Sweep AI](https://sweep.dev/) | Issue-to-PR agent. | Code-task automation. |
| [GitHub Copilot Workspace / Coding Agent](https://github.com/features/copilot) | Agentic dev assistant inside PRs. | PR/code-task scope. |

**Net:** every AI-bot in the repo space is **PR/code-level**. None coaches the _repo itself_ — README quality, marketing, community health, launch readiness.

## C. README & docs generators

| Tool | What it does |
|---|---|
| [readme.so](https://readme.so/) | Drag-and-drop README sections. Static templates. |
| [readme-ai](https://github.com/eli64s/readme-ai) | LLM-generated README from codebase scan. |
| [DeepWiki](https://deepwiki.com/) | LLM-summarized "wiki" of any GitHub repo. |
| [Mintlify](https://mintlify.com/) / [GitBook](https://www.gitbook.com/) / [readme.com](https://readme.com/) | Hosted docs SaaS. |
| [dosu.dev](https://dosu.dev/) | AI maintainer-bot answering issues. |

**Net:** generators exist for the README artifact and docs; **none coach** the wider hygiene, community, or marketing surface.

## D. "Awesome" lists in adjacent space

| List | Coverage |
|---|---|
| [matiassingers/awesome-readme](https://github.com/matiassingers/awesome-readme) | Curated list of well-crafted READMEs + tools. |
| [kylelobo/The-Documentation-Compendium](https://github.com/kylelobo/The-Documentation-Compendium) | README templates + writing patterns. |
| [sdras/awesome-actions](https://github.com/sdras/awesome-actions) | GitHub Actions catalog. |
| [phodal/awesome-github](https://github.com/phodal/awesome-github) | GitHub developer-experience tools. |
| [abhisheknaiidu/awesome-github-profile-readme](https://github.com/abhisheknaiidu/awesome-github-profile-readme) | Personal-profile READMEs. |
| [todogroup/awesome-ospo](https://github.com/todogroup/awesome-ospo) | OSS Program Office resources. |
| [marmelab/awesome-rest](https://github.com/marmelab/awesome-rest), [awesome-monorepo](https://github.com/korfuri/awesome-monorepo), countless `awesome-<lang>` | Topical, technical. |

**What's missing:** there is no `awesome-repo-coaching`, no `awesome-oss-launch-playbook`, no `awesome-repo-health` that ties together **technical + operational + marketing/branding** in one curated list.

`awesome-readme` covers ~20% of the surface (README only). `awesome-actions` covers automation. The cross-cutting "how do I take my repo from 'works' to 'thrives'" guide is not curated anywhere obvious.

## E. Manual playbooks & books

- [GitHub Open Source Guides](https://opensource.guide/) — the canonical English-language playbook. Excellent baseline; light on marketing tactics.
- [producingoss.com](https://producingoss.com/) (Karl Fogel) — definitive book on OSS governance/community. Pre-2010 worldview; updated 2022.
- Nadia Eghbal, _Working in Public_ (2020) — economics of solo maintainers. Mental model, not a checklist.
- [TODO Group guides](https://todogroup.org/resources/guides/) — corporate OSPO-flavored.
- [CNCF graduation criteria](https://github.com/cncf/toc/blob/main/process/graduation_criteria.md) — graduation-tier health bar. Useful as a "high-end" reference.
- Apache "[Maturity Model](https://community.apache.org/apache-way/apache-project-maturity-model.html)" — same spirit, ASF-flavored.

**Net:** great prose; nothing actionable as a checklist a maintainer can scan in 20 minutes.

## F. Gap analysis

Plotting coverage by layer:

| Layer | Existing coverage | Gap |
|---|---|---|
| Technical / security | **Strong** (Scorecard, Best Practices, Snyk, Socket, deps.dev) | Mostly solved. |
| Technical / hygiene (files, configs, CI structure) | Medium (repolinter, community profile) | Tools are presence-only or stale. No quality-grading. |
| Operational (triage, governance, community) | Weak (CHAOSS for metrics; opensource.guide for prose) | No tool that grades or coaches. |
| Marketing / branding / launch | **None** beyond awesome-readme | Wide-open gap. |
| AI-driven repo-level coaching | None | Wide-open gap. |
| Cross-cutting curated list | None | Wide-open gap. |

## G. Form-factor implications

Given the gaps, viable form factors:

1. **One-off audit report** for a specific repo. Cheapest. Highest signal for the host repo. Reusable as a template.
2. **`awesome-repo-coaching` public list** — fills the cross-cutting curated-list gap. Distribution via GitHub trending, awesome-mirrors. Ongoing maintenance burden.
3. **CLI / GitHub Action audit tool** — opinionated, modern repolinter. Open question: does the world need another lint-er? Differentiator would be marketing/branding rules (no one has these).
4. **AI bot / MCP server** — gives qualitative grading on README, social preview, positioning. Overlaps least with existing tools. Maintenance is cheap (LLM does the grading).
5. **GitHub App** — a "Repo Coach" that comments quarterly on the repo with prioritized recommendations. Highest user effort to install; highest distribution leverage if it lands.

`FORM-FACTOR.md` makes a concrete recommendation.

## Sources
- [scorecard.dev](https://scorecard.dev/) and [scorecard checks](https://github.com/ossf/scorecard/blob/main/docs/checks.md)
- [OpenSSF Best Practices](https://www.bestpractices.dev/)
- [GitHub community-profile docs](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file)
- [State of AI Code Review Tools 2025](https://www.devtoolsacademy.com/blog/state-of-ai-code-review-tools-2025/)
- [Repo Doctor (DEV)](https://dev.to/glaucia86/repo-doctor-ai-powered-github-repository-health-analyzer-136n)
- [OSPO Code Scanner (Alliander)](https://github.com/alliander-opensource/ospo-code-scanner)
- [matiassingers/awesome-readme](https://github.com/matiassingers/awesome-readme)
- [opensource.guide](https://opensource.guide/)
- [CNCF graduation criteria](https://github.com/cncf/toc/blob/main/process/graduation_criteria.md)
- [Apache Maturity Model](https://community.apache.org/apache-way/apache-project-maturity-model.html)
