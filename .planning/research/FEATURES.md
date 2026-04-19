# Feature Landscape: Kestrel Onboarding Experience

**Domain:** Self-hosted developer tool onboarding (CLI + Web UI)
**Researched:** 2026-04-19
**Overall confidence:** MEDIUM-HIGH (patterns well-documented across reference products; CV parsing complexity is the main uncertainty)

## Table Stakes

Features users expect. Missing = users abandon before seeing value.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| CLI setup wizard (`kestrel init`) | Every modern CLI tool (gh, vercel, railway, supabase) has an interactive init. Users who `pip install` and get nothing actionable leave immediately. | Medium | Typer already supports prompts. Must detect TTY and support `--no-input` flag per clig.dev guidelines. Use questionary for rich prompts. |
| Post-install next-steps message | Homebrew, gh CLI, and pip itself print "next steps" after install. The gap between `pip install kestrel-app` and "now what?" is where 80% of self-hosted tool users drop off. | Low | Print on first `kestrel` invocation: what to run, where docs are, what will happen. |
| CV/resume file upload (PDF, DOCX) | Primary data loading mechanism per project requirements. Users expect to hand over their resume and have data extracted. | Medium | pdfplumber for PDF, python-docx for DOCX. Must handle common formatting variations. |
| Auto-extract contact info from CV | Name, email, phone, location. Users expect smart import to handle the basics. Recruiter tools (RChilli, Sensible) have set this expectation. | Medium | Regex tier handles email/phone/URL reliably. spaCy NER for name/location. |
| Auto-extract skills from CV | Core value of smart import. Without skills extraction, the profile is incomplete and scoring quality suffers. | High | Needs skill taxonomy + fuzzy matching (rapidfuzz). Most CVs list skills in varied formats. |
| Confirmation step before saving | Users must verify extracted data before it becomes their profile. Trust-building step. Every import flow (LinkedIn, Notion, etc.) does this. | Low | questionary confirm + Rich table display (CLI). Review card (web). |
| Error messages as solutions | clig.dev: "catch errors and rewrite for humans." Stack traces during onboarding kill non-dev users. Every error must include what happened, why, and what to do next. | Medium | Wrap all onboarding code paths in user-friendly error handling. Reserve tracebacks for `--verbose`. |
| Empty state coaching | Notion, Linear, Figma all turn empty dashboards into onboarding surfaces. Carbon Design System and NN/g both document this as essential UX. An empty Pipeline page with no context is hostile. | Medium | Each major page (Pipeline, Discovery, Contacts, Skills) needs: what this page does, how to populate it, and a CTA. |
| Skip option for power users | Every wizard must be skippable. Vercel CLI lets you pass all config as flags. Forced flows without escape create resentment. | Low | CLI: all wizard answers available as flags + `kestrel init --skip`. Web: "Skip tour" visible on every step. |
| Progress indicator during setup | Users need to know how far along they are. Both CLI and web. | Low | CLI: step counter "Step 2/5" via Rich. Web: stepper component. |
| Web welcome screen (first visit) | Empty dashboard on first visit is disorienting. Nextcloud, Linear, and Notion all have first-visit detection. | Low | Conditional render based on onboarding completion flag. API-backed status check. |
| Pre-baked demo data | Instant proof the tool works without any API key or external service. The "aha moment." | Medium | Ship 5-10 sample jobs with pre-computed scores as fixtures. Must feel real (actual job titles, plausible scores), not dummy data. |

## Differentiators

Features that set Kestrel's onboarding apart. Not expected in self-hosted tools, but create competitive advantage.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Smart CV import as primary onboarding path | Most self-hosted tools make users fill forms manually or edit YAML. Kestrel parses your resume and builds your profile. This is the killer feature -- users see their own data reflected back instantly. | High | Two-tier parsing: regex (contact info, URLs) + spaCy NER (name, orgs, dates) + fuzzy skill matching. All local, no API calls. Fallback to guided questions if extraction is poor. |
| Guided fallback with max 7 questions | When CV parsing extracts insufficient data, dynamically ask only the missing fields. Not a full form -- just the gaps. Max 7 questions with skip on each. | Medium | Dynamic question list based on extraction gaps. Questions ordered by impact on scoring quality. Shared question set between CLI and web. |
| Interactive UI tour (Shepherd.js) | Tooltip-attached-to-element walkthrough of Pipeline, Discovery, Scoring. Figma pioneered this pattern: bite-sized tooltips, user explores while learning. No other self-hosted job tool does this. | Medium | **Use Shepherd.js** (MIT, actively maintained through March 2026, CSS-based theming, Tailwind-compatible). NOT React Joyride (unmaintained 9+ months, React 19 incompatible). NOT Intro.js (commercial license required). |
| Pre-baked offline scoring demo | See scored results before configuring any API key. Proves the product works in under 60 seconds. Combined with CV import, users see their profile scored against real-looking jobs. | Medium | Bundle fixture data in the pip package. Load during onboarding. Pre-compute scores with real rubric. Deterministic -- same input always produces same output. |
| "Do it later" signposting | When users skip a step, they know WHERE to do it later. Figma and Notion leave breadcrumbs. Without this, skipped steps become permanently abandoned. | Low | After each skippable step: "You can do this later in Settings > Profile" with exact navigation path. |
| Persistent feedback channel | Always-visible feedback button in web UI (not just during onboarding). Sentry's feedback widget pattern -- contextual, minimal friction. For self-hosted tool, this is the lifeline. | Low | Floating button bottom-right. Opens to: GitHub issue template pre-filled with system info (OS, Python version, Kestrel version). No third-party feedback SaaS. |
| End-of-onboarding summary | Completion screen showing: what was configured, what was skipped (with links), what to explore next. Clear "you're all set" moment. | Low | Both CLI (Rich-formatted summary) and web UI (completion card with next-step CTAs). |
| Suggested next commands (CLI) | After each CLI action, suggest what to run next. clig.dev documents this. gh CLI does it excellently: after `gh repo clone`, it suggests `cd repo && gh issue list`. | Low | After `kestrel init`: "Try `kestrel pipeline` to see your scored jobs". After import: "Run `kestrel discover` to find new opportunities". |
| Health check (`kestrel doctor`) | Homebrew's `brew doctor` pattern. After setup, confirm everything works. Confidence-building moment. | Low | Check: DB exists, config valid, sample data loaded, Python version compatible. CLI command + web UI health badge. |
| Non-developer terminal guidance | For true non-devs: explain what the terminal is, how to open it. Not inline (clutters for devs) but via expandable "New to the terminal?" sections or linked guide. | Low | Docs page "Getting Started for Non-Developers" + CLI `--explain` flag for verbose step explanations. |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| AI provider setup during onboarding | Requires API key, blocks progress, adds complexity. Most first-time users don't have a key ready. | Pre-baked demo scores prove value without any AI. Defer provider setup to Settings, post-onboarding. |
| Video/GIF walkthrough | Heavy assets, go stale with every UI change, not interactive. Figma proved tooltips beat videos. | Interactive tour with Shepherd.js. Static screenshots in docs only if needed. |
| Account creation / signup flow | Self-hosted = no accounts to create. Auth is optional admin config, not user onboarding. | Profile setup (name, preferences) only. Auth is a post-onboarding configuration concern. |
| Animated onboarding carousel / slideshow | "Swipe through 5 marketing screens" is a mobile SaaS anti-pattern. Kestrel users already installed -- they need setup, not selling. | Get to product immediately. Explanation via in-context tooltips and empty states, not upfront slides. |
| Mandatory wizard (no escape) | Forced flows create resentment. Every modern CLI tool (Vercel, gh) lets you skip via flags. | Every step skippable. `kestrel init --skip` bypasses wizard. Web: "Skip" always visible. |
| External service calls during onboarding | CV parsing must stay local (privacy constraint). No OAuth, no cloud APIs, no "sign in with" flows. | All processing local: pdfplumber, python-docx, spaCy. No data leaves the machine. |
| Multi-page web wizard (Next/Back navigation) | Heavy enterprise SaaS feel. Wrong for a dev tool. | Single welcome page with checklist or collapsible sections (Notion pattern). Tour is overlay, not page-based. |
| Gamification (points, badges, streaks) | Inappropriate for a professional job search tool. | Simple progress stepper. No rewards. "You're all set" is sufficient celebration. |
| OCR for scanned PDF resumes | Adds tesseract dependency (~500MB), rare use case, unreliable results. | Detect scanned PDFs, show clear message: "Please use a digital PDF (not a scan)." |
| Multi-language CV parsing | English-only for v1. Huge complexity multiplier (different NER models per language). | Detect non-English content, explain limitation clearly. |
| Onboarding analytics / telemetry | Privacy-first product. No phoning home. | Local-only completion tracking via onboarding status flags in the database. |

## Feature Dependencies

```
Post-install next-steps message
    |
    v
CLI Setup Wizard (`kestrel init`)
    |
    +---> CV file upload --> Text extraction (pdfplumber/python-docx)
    |         |
    |         +---> Regex parsing (email, phone, URLs)
    |         +---> spaCy NER (name, orgs, dates, locations)
    |         +---> Skill matching (rapidfuzz against taxonomy)
    |         |
    |         v
    |     Confirmation step (Rich table display)
    |         |
    |         v
    |     Guided fallback (dynamic questions for gaps)
    |
    +---> Pre-baked demo data loading (requires: fixture data in package)
    |
    v
Health check (`kestrel doctor`)
    |
    v
Web UI Welcome Flow
    |
    +---> Empty state coaching (requires: content for each page)
    |
    +---> Interactive tour / Shepherd.js (requires: tour step definitions per page)
    |
    +---> End-of-onboarding summary (requires: tracking what was completed/skipped)
    |
    v
Persistent feedback channel (independent -- can ship anytime)

Key parallel track:
- "Do it later" signposting: requires settings pages to exist as link targets
- Suggested next commands: requires CLI commands to exist as targets
- Non-dev guidance: docs only, no code dependencies
```

**Critical path:** Post-install message --> CLI wizard --> CV parsing pipeline --> Demo data --> Web welcome --> Tour

**Independent items (no blockers):** Feedback channel, health check, error handling improvements, non-dev docs

## MVP Recommendation

**Phase 1 -- "Zero to Scored Results" (highest impact, lowest risk):**

1. Post-install next-steps message -- trivial, massive first-impression impact
2. `kestrel init` wizard with questionary prompts -- the primary entry point
3. CV upload + regex-tier extraction (email, phone, skills keyword matching) -- basic smart import
4. Pre-baked demo data + scoring fixtures -- the "aha moment"
5. `kestrel doctor` health check -- confidence builder
6. Error messages as solutions -- wrap all onboarding paths
7. Skip option -- must ship with wizard, not added later

**Phase 2 -- "Smart Data + Web UI" (differentiators):**

8. spaCy NER tier (name, org, date, location extraction) -- completes smart import
9. Guided fallback questions for extraction gaps -- safety net
10. Web welcome screen + empty state coaching for all pages
11. Interactive tour with Shepherd.js -- tooltip walkthrough

**Phase 3 -- "Polish + Feedback Loop":**

12. Persistent feedback channel -- floating button + GitHub issue template
13. End-of-onboarding summary -- completion state with next steps
14. "Do it later" signposting -- breadcrumbs for skipped steps
15. Suggested next commands -- post-action CLI hints
16. Non-developer terminal guidance -- docs page + `--explain` flag
17. Confirmation step refinement -- editable fields, not just accept/reject

## Competitor Feature Analysis

| Feature | Homebrew | gh CLI | Vercel CLI | Linear | Notion | Figma | Nextcloud |
|---------|----------|--------|------------|--------|--------|-------|-----------|
| Post-install message | Yes (PATH) | Yes (auth prompt) | Yes (login) | N/A | N/A | N/A | Yes (admin) |
| Interactive wizard | No | Yes (`gh auth login`) | Yes (`vercel init`) | No | No | No | Yes (first-run) |
| Skip / flag config | Yes (env vars) | Yes (flags) | Yes (flags + json) | N/A | N/A | N/A | Config file |
| Empty state coaching | N/A | N/A | N/A | Yes (templates) | Yes (template pages) | Yes (starter files) | Yes (app suggestions) |
| Interactive tour | N/A | N/A | N/A | Minimal | Yes (tooltips) | Yes (animated tooltips) | Yes (first-run wizard) |
| Demo/sample data | N/A | N/A | Templates | Yes (sample project) | Yes (templates) | Yes (starter design) | No |
| Error quality | Good | Excellent | Good | N/A | N/A | N/A | Moderate |
| Health check | `brew doctor` | `gh auth status` | `vercel whoami` | N/A | N/A | N/A | Status page |
| Data import | N/A | N/A | N/A | CSV | CSV/Notion | Sketch/Figma | File upload |
| Feedback channel | GitHub | `gh issue create` | Support | In-app | In-app | In-app | Forum |
| Suggested next steps | No | Yes | Yes | Yes | Yes | Yes | Yes |
| Non-dev accessible | Low | Low | Low | High | High | High | Medium |

### Key Takeaways

1. **CLI tools excel at:** post-install messages, flag-based skip, error quality, health checks. Kestrel must match these baseline patterns.
2. **SaaS tools excel at:** empty states, interactive tours, sample data, progressive disclosure. Kestrel's web UI should adapt these for self-hosted context (no accounts, no telemetry).
3. **Market gap:** No self-hosted tool combines CLI wizard + smart data import + interactive web tour + demo data. Kestrel can own this intersection.
4. **Nextcloud's first-run wizard** is the closest self-hosted precedent but focuses on admin config, not user experience. Kestrel should be user-oriented.

## Tour Library Decision

**Use Shepherd.js** for the interactive web UI tour.

| Criterion | Shepherd.js | React Joyride | Intro.js | Driver.js |
|-----------|------------|---------------|----------|-----------|
| Maintained | Yes (March 2026, 170+ releases, 100+ contributors) | No (9+ months stale) | Maintenance-only | Yes |
| React 19 | Yes (wrapper) | Broken (unstable next) | Not React-native | Not React-native |
| License | MIT | MIT | Commercial required | MIT |
| Theming | CSS classes (Tailwind-compatible) | Inline styles only (friction with Tailwind) | CSS classes | CSS classes |
| Bundle | ~20kb | ~15kb | ~12kb | ~5kb |
| Downloads/week | ~130K | ~400K (legacy installs) | N/A | N/A |
| Focus/overlay | Built-in modal overlay | Yes | Yes | Highlight only |

Shepherd.js wins: active maintenance, React 19 support, CSS-class theming for Tailwind, MIT license, built-in focus overlay. Bundle size difference is negligible for self-hosted.

## Sources

- [Command Line Interface Guidelines (clig.dev)](https://clig.dev/) -- authoritative CLI design reference (HIGH confidence)
- [5 Best React Onboarding Libraries 2026 (OnboardJS)](https://onboardjs.com/blog/5-best-react-onboarding-libraries-in-2025-compared) -- library comparison (MEDIUM confidence, vendor blog but data verified)
- [7 User Onboarding Best Practices 2026 (Formbricks)](https://formbricks.com/blog/user-onboarding-best-practices) -- progressive disclosure patterns (MEDIUM confidence)
- [Empty States Pattern (Carbon Design System)](https://carbondesignsystem.com/patterns/empty-states-pattern/) -- IBM design system guidelines (HIGH confidence)
- [Designing Empty States (NN/g)](https://www.nngroup.com/articles/empty-state-interface-design/) -- research-backed UX guidelines (HIGH confidence)
- [Figma's Onboarding Flow (Appcues GoodUX)](https://goodux.appcues.com/blog/figmas-animated-onboarding-flow) -- tooltip onboarding analysis (MEDIUM confidence)
- [Building Accessible GitHub CLI (GitHub Blog)](https://github.blog/engineering/user-experience/building-a-more-accessible-github-cli/) -- CLI accessibility patterns (HIGH confidence)
- [Nextcloud First Run Wizard (GitHub)](https://github.com/nextcloud/firstrunwizard) -- self-hosted onboarding precedent (HIGH confidence)
- [Best Open-Source Product Tour Libraries 2026 (Userorbit)](https://userorbit.com/blog/best-open-source-product-tour-libraries) -- tour library landscape (MEDIUM confidence)
- [Sentry User Feedback Widget](https://blog.sentry.io/user-feedback-widget-for-mobile-apps/) -- feedback collection pattern (HIGH confidence)
- [In-App Feedback Tools (Userback)](https://userback.io/blog/in-app-feedback-tools-for-saas-applications/) -- feedback widget patterns (MEDIUM confidence)
