# Domain Pitfalls

**Domain:** CLI + Web onboarding for self-hosted job search platform (non-dev target users)
**Researched:** 2026-04-19
**Overall confidence:** MEDIUM-HIGH (multiple sources corroborate; some areas are domain-specific extrapolation)

---

## Critical Pitfalls

Mistakes that cause rewrites, user abandonment, or fundamental design failures.

### Pitfall 1: CV Parsing Silently Returns Garbage

**What goes wrong:** The parser extracts text from a PDF but produces mangled output -- columns merged, text box content orphaned to wrong sections, encoding corrupted (e.g. "Jose" rendered with broken UTF-8), or entire sections missing because they were image-based. The onboarding flow reports "CV imported successfully!" while the extracted data is nonsense. The user trusts the import, skips manual review, and ends up with a broken profile.

**Why it happens:** PDFs are a presentation format, not a data format. Text extraction order is undefined -- two-column layouts merge randomly, floating text boxes appear at arbitrary positions in the extracted stream, and headers/footers contaminate body text. Design-tool PDFs (Canva, Figma exports) may render text as vector paths, making them invisible to text extractors. Non-Latin scripts, smart quotes, em-dashes, and ligatures cause encoding failures with naive UTF-8 handling.

**Consequences:**
- User sees garbled skills/roles in confirmation step and loses trust immediately
- If no confirmation step exists, the profile is silently wrong and scoring is meaningless
- Users with creative/designed resumes (common among non-devs) are disproportionately affected

**Prevention:**
- Always show a human-readable confirmation screen after parsing -- never auto-accept
- Use PyMuPDF (fitz) as primary extractor (best balance of speed, layout awareness, and markdown output) with pdfplumber as fallback for table-heavy CVs
- Detect image-only PDFs (zero extractable text) and tell the user explicitly: "This PDF contains images, not text. Please use a different version or enter details manually."
- Normalize encoding aggressively: strip smart quotes, normalize Unicode (NFC), handle BOM markers
- Test with at least 20 real-world resumes across formats: single-column, two-column, Canva-designed, LaTeX-generated, Word-exported, Google Docs-exported, non-English
- Set a confidence threshold: if extracted text is under ~50 characters or contains >30% non-printable characters, treat as parse failure and route to manual entry
- Design the flow so guided fallback (manual questions) is an equal-quality path, not a degraded experience

**Detection (warning signs):**
- No resume test corpus exists in the test suite
- Parser tests only use clean, single-column, English PDFs
- No confirmation screen in the onboarding wireframes
- Zero handling for the "nothing extracted" case

**Phase relevance:** CV Import phase (must be addressed before any user testing)

---

### Pitfall 2: CLI Wizard Crashes in Non-TTY / Docker / Piped Environments

**What goes wrong:** The `kestrel init` wizard uses interactive prompts (Rich, prompt-toolkit, Typer prompts, or questionary) that assume a TTY is attached. When run inside Docker without `-it`, piped through another command, run from a GUI launcher, or executed in CI/CD, the wizard crashes with "input device is not a TTY" or hangs waiting for input that will never come.

**Why it happens:** Interactive Python CLI libraries call `isatty()` on stdin. When stdin is a pipe or /dev/null, they either crash, hang, or display garbled output (escape codes printed raw). Docker containers don't allocate a TTY by default. Non-dev users may run commands from GUI tools, IDEs, or copy-paste into non-standard terminals.

**Consequences:**
- Docker users (a primary install path) hit a wall on first run
- Users following copy-paste instructions from a web page may pipe commands unexpectedly
- CI/CD or scripted setups become impossible
- Error message is cryptic and terrifying for non-developers

**Prevention:**
- Check `sys.stdin.isatty()` at wizard entry point. If not a TTY, print a clear message: "This command needs an interactive terminal. Run it directly (not piped)." and exit with code 1
- Provide a `--non-interactive` flag that accepts all config via command-line arguments or a config file
- For Docker: document `docker run -it` clearly, but also support `docker run -e KESTREL_INIT_CONFIG=/path/to/config.yaml` for non-interactive setup
- Test the wizard explicitly in: bare terminal, Docker without -it, Docker with -it, piped input, VS Code integrated terminal, WSL2

**Detection (warning signs):**
- No `isatty()` check anywhere in the wizard code
- Docker quick-start instructions don't include `-it` flag
- No `--non-interactive` flag exists
- Zero Docker-based testing of the wizard

**Phase relevance:** CLI Wizard phase (foundational -- must be addressed before release)

---

### Pitfall 3: Onboarding State Lost on Browser Close / Tab Switch

**What goes wrong:** User is halfway through the web onboarding flow (step 3 of 5), closes the browser tab accidentally or intentionally ("I'll finish later"), returns, and is dumped back to step 1 with no data preserved. Alternatively, they're shown the onboarding again after already completing it, or worse, shown a half-completed state that is neither fresh nor resumable.

**Why it happens:** Onboarding state stored only in React component state or context (memory). No persistence to localStorage, sessionStorage, or backend. Developers assume the flow is short enough that users will complete it in one sitting.

**Consequences:**
- Users who got interrupted abandon entirely rather than redo steps
- Users who already entered CV data are furious at losing it
- "Did I already do this?" confusion when onboarding re-shows

**Prevention:**
- Persist onboarding progress to the backend (not just localStorage) after each step completion. The backend already has a profile concept -- add an `onboarding_state` JSON column
- Store: current step, completed steps, any user-entered data not yet committed to the profile
- On app load: check onboarding state. If incomplete, resume from last completed step. If complete, never show again
- Cache onboarding-complete flag in localStorage as fallback for API errors (defensive: if uncertain, don't show onboarding again to returning users)
- For the CLI wizard: save partial progress to a temp file (`~/.kestrel/.onboarding-state.json`) so `kestrel init` can resume with "Resume from step 3?" or "Start over?"
- Implement a "Start Over" button for users who want to redo onboarding intentionally

**Detection (warning signs):**
- Onboarding state lives only in React useState/useContext
- No database migration adds onboarding tracking fields
- No test for "close browser mid-flow, reopen" scenario
- Opening the app in a second tab shows onboarding again
- Kill the CLI process mid-wizard; verify state recovery

**Phase relevance:** Both CLI Wizard and Web Welcome Flow phases

---

### Pitfall 4: Non-Dev Users Cannot Navigate the CLI At All

**What goes wrong:** The target user has never opened a terminal. They don't know what "run a command" means, can't find Terminal.app, don't understand `cd`, are confused by `$` prompts in documentation, and panic at any error output. The CLI wizard itself may be polished, but the user never reaches it.

**Why it happens:** Developer-authored documentation assumes baseline terminal literacy: "Open your terminal and run `pip install kestrel-app`" presumes the user knows what a terminal is, where to find it, and what `pip` does. Self-hosted tools almost universally fail this population.

**Consequences:**
- Entire user segment is effectively locked out despite the tool being "free and open source"
- Support burden shifts to GitHub issues full of "how do I open terminal" questions
- Non-dev users are the exact population most likely to benefit from job search tooling

**Prevention:**
- Write a "Before You Begin" page with platform-specific screenshots: "On macOS, press Cmd+Space, type Terminal, press Enter" / "On Ubuntu, press Ctrl+Alt+T" / "On Windows, install WSL2 first (link to guide)"
- Never show raw `$` in documentation (users type it literally)
- Provide exact copy-pasteable commands with a clipboard button in docs
- When CLI errors occur during onboarding, catch them and print human-readable messages: "Something went wrong. Here is what to do: [specific fix]" -- never show Python tracebacks
- Consider: the web UI should be the primary onboarding path for non-devs. The CLI wizard is for users who are already in a terminal. Don't force CLI-first onboarding
- Add a `--verbose` flag for debugging but keep default output minimal and friendly

**Detection (warning signs):**
- Install docs start with "Run `pip install ...`" without any preamble
- Error handling in CLI uses `raise` without `try/except` user-facing wrappers
- No platform-specific "getting started" content exists
- Usability testing only includes developers

**Phase relevance:** Documentation and Install Experience phase (before CLI Wizard)

---

### Pitfall 5: Demo Data Reveals Itself as Fake, Breaking Trust

**What goes wrong:** Pre-baked demo jobs use obviously fake companies ("Acme Corp"), unrealistic salaries, expired dates ("Posted: January 2024"), US-only locations for a non-US user, or tech-only roles for a user in marketing. The user sees through the demo instantly, concludes the tool doesn't work for their situation, and leaves. Additionally, demo data IDs may collide with real discovered jobs, or users can't distinguish demo from real results.

**Why it happens:** Demo data is written once by a developer and never updated. It reflects the developer's own job search context (tech, US, senior-level). Dates are hardcoded. Data is inserted into the same tables as real data without clear separation.

**Consequences:**
- "This isn't for people like me" -- immediate abandonment
- Users don't understand that real results will be different
- Demo scores on fake data don't prove the scoring system works for their profile
- Data integrity issues if demo jobs collide with real discovery results
- Users accidentally interact with demo jobs as if they were real

**Prevention:**
- Use realistic but anonymized job data based on actual scraped results (sanitized)
- Include multiple job families: tech, finance, healthcare, creative, operations -- at least 3 categories
- Use relative dates ("Posted 2 days ago") not absolute dates, computed at display time
- Make demo jobs locale-aware: detect user's timezone/locale and show geographically plausible locations, or show "Remote" roles
- Include a clear banner: "These are sample results to show how Kestrel works. Connect your preferences to see real jobs."
- Ship demo data as a versioned fixture that gets updated with each release
- Flag all demo data with `is_demo=True`, display demo badge in UI, provide "Clear demo data" action
- Use UUID-based IDs that cannot collide with discovery results
- Demo scores should respond to the user's actual extracted profile (even if jobs are pre-baked, re-score against the user's skills)

**Detection (warning signs):**
- Demo data JSON hasn't been modified since initial commit
- All demo jobs are in one city/country or one industry
- Dates in demo data are absolute and in the past
- No banner distinguishes demo from real results
- No `is_demo` flag in the data model
- Run a full discovery cycle after onboarding and verify no conflicts

**Phase relevance:** Demo Data and First-Run phase

---

### Pitfall 6: spaCy / Heavy NLP Dependencies Break User Setup

**What goes wrong:** spaCy + model download adds 200MB+ and requires compilation of C extensions. On some systems (older pip, missing build tools, ARM Linux), installation fails with cryptic errors. The user's very first experience with Kestrel is a failed `pip install`.

**Why it happens:** spaCy has binary wheels for common platforms but not all. Model download requires internet access during install. Build-from-source paths need compilers that non-dev users won't have installed.

**Consequences:**
- Devastating first impression for non-dev target audience
- Support burden of "pip install failed" issues across diverse environments
- ARM Linux (Raspberry Pi, some cloud instances) particularly affected

**Prevention:**
- Make spaCy optional: `pip install kestrel-app[cv]`. Core onboarding works with regex-only Tier 1 parsing
- Detect missing spaCy gracefully at runtime and explain what the user gains by installing it
- Consider lighter alternatives for basic NER (rule-based extraction, pre-trained small models)
- Test install on clean Python 3.11 environments across macOS, Ubuntu 22, WSL2 before every release

**Detection (warning signs):**
- spaCy is in core `install_requires`, not an optional extra
- No graceful fallback when spaCy import fails
- Install tested only on developer machines with full build toolchains

**Phase relevance:** CV Import phase (dependency strategy)

---

## Moderate Pitfalls

### Pitfall 7: Accessibility of Product Tour is an Afterthought

**What goes wrong:** The interactive tooltip tour (highlighting UI elements, walking through the pipeline) is built with visual-only cues: overlay darkening, animated arrows, pulsing highlights. Screen reader users hear nothing. Keyboard-only users can't advance through tour steps. Focus is trapped in the tooltip while the highlighted element is unreachable, or focus is never moved to the tooltip at all.

**Prevention:**
- Use `aria-live="polite"` regions to announce tour step content
- Move keyboard focus to each tooltip when it appears; restore focus to the previously-focused element when the tour ends
- Ensure all tour controls (Next, Skip, Back) are keyboard-accessible with visible focus indicators
- Test with VoiceOver (macOS), NVDA (Windows), and keyboard-only navigation
- Don't use overlay-based tours that trap focus outside the tooltip -- use inline highlight + popover pattern
- Provide a non-tour alternative: a checklist-style "Getting Started" card that links to each feature area

**Detection (warning signs):**
- Tour library chosen without checking its accessibility support
- No `aria-*` attributes in tour component code
- No keyboard navigation tests for the tour
- Tour uses z-index overlays without focus management

**Phase relevance:** Web Welcome Flow / Interactive Tour phase

---

### Pitfall 8: Wizard Asks Too Many Questions (or Wrong Questions)

**What goes wrong:** The project spec says "max 7 questions if smart import fails." But the questions asked are wrong: they ask for information the system doesn't actually need yet (job board preferences, notification settings, AI provider config), or they ask in developer-speak ("What's your target tech stack?"), or they don't have sensible defaults.

**Prevention:**
- Every wizard question must map to a profile field that directly affects first-run scoring. If it doesn't affect scoring, defer it
- Provide smart defaults for every question (location: from system locale, salary: median for detected role, experience: inferred from CV dates)
- Use plain language: "What kind of work are you looking for?" not "Target role taxonomy"
- Allow "Skip" on every question with a clear explanation of what skipping means
- The ideal fallback path: 3 questions (role, location, experience level) + "Good enough to start! You can refine later."

**Detection (warning signs):**
- Wizard asks about AI provider, notification preferences, or integrations
- Any question lacks a default value
- Questions use jargon or assume domain knowledge
- No "skip all" path exists

**Phase relevance:** CLI Wizard and Web Welcome Flow phases

---

### Pitfall 9: DOCX/ODT/RTF Resume Formats Silently Ignored

**What goes wrong:** The CV parser only handles PDF. User uploads a .docx (the most common resume format for non-tech users) and gets an unhelpful error or, worse, the parser attempts to read it as text and extracts XML tags and gibberish. Legacy .doc files or renamed PDFs with .docx extension cause additional confusion.

**Prevention:**
- Support at minimum: PDF, DOCX, plain text. These three cover >95% of resumes
- For DOCX: use `python-docx` to extract text and structure
- For plain text: accept .txt and .md files with simple section-header detection
- Check file magic bytes, not just extension. python-docx raises `BadZipFile` for non-DOCX -- catch this and provide actionable error ("This looks like an older Word format. Please save as .docx first.")
- Reject unsupported formats explicitly: "Kestrel supports PDF, DOCX, and TXT files. Your file appears to be [format]. Please save it as PDF or DOCX and try again."
- Never silently fail -- always tell the user what happened and what to do

**Detection (warning signs):**
- Parser code only imports PDF libraries
- File extension check is absent or only checks for `.pdf`
- No test cases for DOCX or TXT input
- No magic-byte validation
- Error message for wrong format says "Parse error" without mentioning format

**Phase relevance:** CV Import phase

---

### Pitfall 10: Cross-Platform Terminal Rendering Breaks on WSL2 / Older Terminals

**What goes wrong:** Rich-library colored output, progress bars, spinners, and Unicode box-drawing characters render as garbage in Windows Terminal (older versions), WSL2 with default settings, PuTTY, or basic SSH sessions. Users see raw ANSI escape codes or mojibake instead of the polished CLI experience.

**Prevention:**
- Detect terminal capabilities: check `TERM`, `COLORTERM`, `WT_SESSION` (Windows Terminal) environment variables
- Use Rich's built-in `Console(force_terminal=True)` only when capabilities are confirmed; fall back to plain text otherwise
- Test explicitly in: macOS Terminal.app, iTerm2, Ubuntu GNOME Terminal, WSL2 default, Windows Terminal, VS Code integrated terminal
- Avoid Unicode box-drawing characters for essential information -- use ASCII fallbacks
- Spinner animations should degrade gracefully to static "Processing..." text in dumb terminals

**Detection (warning signs):**
- CLI code uses Rich without any terminal capability detection
- No ASCII fallback mode exists
- Testing only done in developer's preferred terminal (iTerm2/Ghostty)
- No `TERM=dumb` test case

**Phase relevance:** CLI Wizard phase

---

### Pitfall 11: "Error Messages as Solutions" Not Actually Implemented

**What goes wrong:** The project spec requires "every error during onboarding includes resolution steps, not stack traces." In practice, developers write the happy path first, add `try/except` later (or never), and error messages remain generic Python exceptions or HTTP 500 responses. The non-dev user sees `ConnectionRefusedError: [Errno 111]` and has no idea what to do.

**Prevention:**
- Create an `OnboardingError` exception hierarchy with mandatory `user_message` and `resolution` fields
- Wrap every external operation (file read, network call, database write) in onboarding-specific error handlers
- Map common errors to plain-English messages:
  - `FileNotFoundError` -> "We couldn't find that file. Please check the path and try again."
  - `ConnectionRefusedError` -> "Can't reach the Kestrel server. Make sure it's running (check the terminal where you started it)."
  - `PermissionError` -> "Kestrel doesn't have permission to read that file. Try moving it to your home folder."
- Add a catch-all that wraps unknown exceptions: "Something unexpected went wrong. Details have been saved to ~/.kestrel/logs/. Please share this with us: [link to issue template]"
- Write tests that deliberately trigger each error path and verify the user-facing message

**Detection (warning signs):**
- No custom exception classes for onboarding
- `except Exception as e: print(e)` patterns in code
- Error messages contain Python class names or tracebacks
- No error-path tests exist

**Phase relevance:** All phases (must be a cross-cutting concern from the start)

---

### Pitfall 12: Skill Matching False Positives During CV Import

**What goes wrong:** Fuzzy matching "Java" to "JavaScript", "C" to "C++", "Go" to "Google". User's profile ends up with skills they don't have, producing misleading scores.

**Prevention:**
- Use high similarity threshold (>= 85). Maintain explicit exclusion pairs for known confusable skills
- Prefer exact match over fuzzy for short skill names (< 4 chars)
- Always show extracted skills for user confirmation before committing to profile
- Kestrel already has 288 job family presets with fuzzy matching -- leverage the existing exclusion logic

**Detection (warning signs):**
- No exclusion pairs defined for common confusable skills
- Confirmation screen shows skills without edit capability
- No tests for known confusable pairs

**Phase relevance:** CV Import phase

---

### Pitfall 13: react-joyride Tour Targets Missing Elements

**What goes wrong:** Tour targets `[data-tour="pipeline"]` but the element isn't rendered yet (loading state, empty state, or user navigated away). Tour step points at nothing, floats in wrong position, or crashes.

**Prevention:**
- Use joyride's `disableScrolling` option for above-fold elements
- Add `isReady` checks before starting tour
- Handle missing targets gracefully (skip step, don't crash)
- Ensure tour only starts on the correct page/route
- Pre-populate the dashboard with demo data before the tour starts so elements have content to show

**Detection (warning signs):**
- Tour starts before data is loaded (no loading-state guard)
- No error boundary around tour component
- Tour tested only with pre-populated data, never with empty state

**Phase relevance:** Web Welcome Flow / Interactive Tour phase

---

## Minor Pitfalls

### Pitfall 14: Feedback Channel is a Dead End

**What goes wrong:** The end-of-onboarding "Give us feedback" link points to GitHub issue creation. Non-dev users don't have GitHub accounts, don't understand issue templates, and are intimidated by the interface. The persistent feedback button links to the same place. Result: zero feedback from the exact users who need the most help.

**Prevention:**
- Provide multiple feedback channels: simple email link, embedded form (even a Google Form is better than GitHub for non-devs), AND GitHub issues for technical users
- Pre-fill as much context as possible: OS, Kestrel version, onboarding completion status
- The persistent feedback button should open an in-app form, not navigate away

**Phase relevance:** Feedback Channel phase

---

### Pitfall 15: "Skip for Power Users" Breaks Onboarding State

**What goes wrong:** Power user clicks "Skip onboarding" but the system doesn't properly mark onboarding as complete. On next login, onboarding shows again. Or worse: skipping doesn't create required default profile data, so the app crashes on the dashboard because it expects profile fields that onboarding would have created.

**Prevention:**
- "Skip" must: (1) mark onboarding as complete, (2) create a default profile with sensible defaults for all required fields, (3) never show onboarding again
- Test the skip path as thoroughly as the complete path
- The dashboard must handle empty/default profile gracefully (empty states, not crashes)

**Phase relevance:** Web Welcome Flow phase

---

### Pitfall 16: Time-to-Value Exceeds the 10-Minute Budget Silently

**What goes wrong:** Each individual step feels reasonable, but the cumulative time exceeds 10 minutes. Nobody measures end-to-end time. Steps that are fast for developers (reading prompts, understanding terminology) take 3x longer for non-dev users.

**Prevention:**
- Time the full flow with a non-developer. Literally. Sit them in front of the tool and use a stopwatch
- Set time budgets per step: install (3 min), CV import + confirmation (3 min), tour (2 min), see results (2 min)
- If any step consistently exceeds its budget in testing, cut scope from that step -- don't add "helpful" explanatory text (which makes it longer)
- Automate timing in integration tests: if the happy-path flow takes >N seconds of wall time, flag it

**Phase relevance:** All phases (integration testing concern)

---

### Pitfall 17: Onboarding API Endpoint Abuse

**What goes wrong:** Onboarding endpoints that create profiles or load demo data are unprotected, allowing repeated calls that create duplicate data or consume resources.

**Prevention:**
- Rate-limit onboarding endpoints
- The onboarding-complete endpoint should be idempotent
- Demo data loading should check if already loaded before inserting

**Phase relevance:** Backend API phase

---

## "Looks Done But Isn't" Checklist

These are conditions where onboarding appears complete to developers but is broken for real users.

| Condition | What's Actually Wrong | How to Verify |
|-----------|----------------------|---------------|
| CV parsed "successfully" | Extracted text is garbled or incomplete | Show parsed output to 5 non-devs, ask "Is this your resume?" |
| Onboarding flow completes | Profile has empty required fields from skipped optional questions | Query DB after onboarding: any NULL fields that scoring needs? |
| Demo scores displayed | Scores are identical regardless of user profile (not personalized) | Import two different resumes, verify scores differ |
| Tour completes | User can't find any feature without the tour 5 minutes later | Ask user to "show me how to add a job" after tour ends |
| Wizard works on dev machine | Crashes in Docker, WSL2, or non-TTY environment | Run in CI with `docker run` (no -it), capture exit code |
| Error messages are "friendly" | Only happy-path errors handled; edge cases show tracebacks | Deliberately: unplug network, pass binary file as CV, fill disk |
| Skip works | Dashboard crashes because profile is incomplete | Click Skip, immediately try every dashboard action |
| Feedback button exists | Links to GitHub (non-devs can't use it) | Ask a non-dev to "tell us what you think" using only the button |
| Onboarding "never shows again" | Shows again in incognito, different browser, or after clearing cache | Check: is completion state in backend DB or only localStorage? |
| Progress bar shows 100% | User doesn't know what to do next -- no graduation/redirect | Watch 3 users finish onboarding, see where they click next |
| Tour is "accessible" | Screen reader announces nothing; keyboard can't advance steps | Test with VoiceOver on, eyes closed, keyboard only |
| Install "just works" | spaCy C extension compilation fails on ARM/minimal systems | Test `pip install` on clean Ubuntu minimal Docker image |

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| CV Import | Silent parse failure on designed PDFs (Canva, etc.) | Image-only PDF detection + explicit error message |
| CV Import | DOCX not supported, alienating non-tech users | Support PDF + DOCX + TXT from day one |
| CV Import | Encoding corruption on non-English names | Unicode NFC normalization, explicit encoding detection |
| CV Import | spaCy install failure on user machines | Make optional extra, test on all target platforms |
| CV Import | Skill matching false positives (Java/JavaScript) | High threshold, exclusion pairs, user confirmation |
| CLI Wizard | Non-TTY crash in Docker | `isatty()` check + `--non-interactive` flag |
| CLI Wizard | Terminal rendering garbage on WSL2/older terminals | Rich capability detection + ASCII fallback |
| CLI Wizard | Asking questions that don't affect first-run value | Map every question to a scoring-relevant field |
| Web Welcome Flow | State lost on browser close | Backend persistence of onboarding progress |
| Web Welcome Flow | Skip creates incomplete profile | Skip path creates full default profile |
| Web Welcome Flow | Welcome screen re-shows on API error | localStorage fallback, defensive defaults |
| Interactive Tour | Inaccessible to screen readers / keyboard | aria-live, focus management, non-tour alternative |
| Interactive Tour | Overlay traps focus incorrectly | Inline highlight pattern, not overlay-based |
| Interactive Tour | Tour targets missing elements (loading/empty state) | isReady guards, missing-target handlers |
| Demo Data | Fake-looking data breaks trust | Realistic anonymized data, relative dates, multi-locale |
| Demo Data | US/tech-only bias in sample jobs | Include 3+ job families and generic/remote locations |
| Demo Data | ID conflicts with real discovered jobs | `is_demo` flag, UUID IDs, explicit cleanup action |
| Error Handling | Stack traces shown to non-dev users | OnboardingError hierarchy with user_message + resolution |
| Feedback | GitHub-only channel excludes non-devs | In-app form + email as primary, GitHub as secondary |
| Install Docs | Assumes terminal literacy | Platform-specific screenshots, no raw `$` prompts |
| All Phases | Total time exceeds 10-minute budget | Per-step time budgets, measured with real non-dev users |

---

## Sources

- [Resume Parsing: How It Works, Why It Fails (CareerBldr)](https://careerbldr.com/blog/resume-parsing-how-it-works/) - MEDIUM confidence
- [5 Critical ATS Resume Formatting Mistakes 2026 (Jobscan)](https://www.jobscan.co/blog/ats-formatting-mistakes/) - MEDIUM confidence
- [7 Python PDF Extractors Tested 2025 Edition](https://dev.to/onlyoneaman/i-tested-7-python-pdf-extractors-so-you-dont-have-to-2025-edition-akm) - MEDIUM confidence
- [Wizard UI Pattern: When to Use It (Eleken)](https://www.eleken.co/blog-posts/wizard-ui-pattern-explained) - MEDIUM confidence
- [Onboarding Wizard Falls Short (UserPilot)](https://userpilot.com/blog/onboarding-wizard/) - MEDIUM confidence
- [Focus Trap Accessibility (UXPin)](https://www.uxpin.com/studio/blog/how-to-build-accessible-modals-with-focus-traps/) - MEDIUM confidence
- [Screen Reader Accessibility Best Practices (Equally AI)](https://blog.equally.ai/web-accessibility/screen-reader-accessibility/) - MEDIUM confidence
- [Feature Tours Prevent Focus Change - Google Site Kit issue 6638](https://github.com/google/site-kit-wp/issues/6638) - HIGH confidence (real bug report)
- [OnboardJS: State Persistence for Onboarding](https://onboardjs.com/blog/supabase-onboarding-persistence-onboardjs) - MEDIUM confidence
- [Empty States and Hidden UX Moments (Raw.Studio)](https://raw.studio/blog/empty-states-error-states-onboarding-the-hidden-ux-moments-users-notice/) - MEDIUM confidence
- [Every Onboarding Mistake (ProductLed / FullStory)](https://productled.com/blog/every-onboarding-mistake-i-made-so-you-dont-have-to) - MEDIUM confidence
- Understanding the "input device is not a TTY" Error (Harold Finch, Medium) - HIGH confidence
- [Mozilla Bugzilla 1707575: Onboarding Slides Not Screen-Reader Accessible](https://bugzilla.mozilla.org/show_bug.cgi?id=1707575) - HIGH confidence (real bug report)
- [7 User Onboarding Retention Mistakes (Appcues)](https://www.appcues.com/blog/your-retention-problem-starts-with-these-7-user-onboarding-mistakes) - MEDIUM confidence
- [pdfplumber known limitations (GitHub)](https://github.com/jsvine/pdfplumber/issues) - HIGH confidence
- [react-joyride v3 docs](https://react-joyride.com/docs/new-in-v3) - HIGH confidence
- [spaCy installation troubleshooting](https://spacy.io/usage) - HIGH confidence
- [Demo Content 101 (UserPilot)](https://userpilot.com/blog/demo-content/) - MEDIUM confidence
