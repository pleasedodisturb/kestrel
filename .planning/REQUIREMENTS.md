# Requirements: Kestrel Onboarding Experience

**Defined:** 2026-04-19
**Core Value:** A user who has never seen Kestrel finishes onboarding understanding what it does, has their profile populated, has seen scored results, and knows where to go next — all in under 10 minutes.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### CLI & Setup

- [ ] **CLI-01**: User sees next-steps message on first `kestrel` invocation after install
- [ ] **CLI-02**: User can run `kestrel init` to start interactive profile wizard with questionary prompts
- [ ] **CLI-03**: Wizard detects non-TTY environment and exits with clear message + `--non-interactive` flag guidance
- [ ] **CLI-04**: User can skip entire wizard with `kestrel init --skip` (creates complete default profile)
- [ ] **CLI-05**: Wizard shows progress indicator ("Step 2/5") at each stage
- [ ] **CLI-06**: User can run `kestrel doctor` to verify setup is healthy (DB, config, sample data, Python version)
- [ ] **CLI-07**: Every error during onboarding includes what happened, why, and what to do next (no stack traces unless --verbose)
- [ ] **CLI-08**: After each CLI action, suggested next command is printed (e.g. "Try `kestrel pipeline` to see your scored jobs")

### Profile Data Loading

- [ ] **PROF-01**: Wizard asks 5-7 guided questions (name, location, target roles, salary range, skills, experience level) — all skippable
- [ ] **PROF-02**: Optional "paste your resume text" field with regex extraction for email, phone, URLs, skill keywords
- [ ] **PROF-03**: Extracted data shown for confirmation before saving to profile
- [x] **PROF-04**: Same question set available in web welcome flow

### Demo Data

- [ ] **DEMO-01**: Pre-baked sample jobs (10) with pre-computed scores ship as fixture data in the package
- [ ] **DEMO-02**: Demo jobs span 3+ job families (not just tech roles — include marketing, operations, finance)
- [ ] **DEMO-03**: Demo data uses relative dates computed at display time (never looks stale)
- [ ] **DEMO-04**: Demo records have `is_demo=True` flag and display "Sample Results" banner in UI
- [ ] **DEMO-05**: Demo seeder is idempotent (safe to run multiple times without duplicating data)

### Web UI

- [ ] **WEB-01**: First-time visitors redirected to `/welcome` via OnboardingGuard route wrapper
- [x] **WEB-02**: Welcome screen explains what Kestrel does and walks through setup steps
- [ ] **WEB-03**: Pipeline, Discovery, Contacts, and Skills pages show empty state coaching when no data exists
- [x] **WEB-04**: User can resume onboarding from last completed step after browser close
- [ ] **WEB-05**: Shepherd.js interactive tour walks through Pipeline, Discovery, Scoring pages with tooltips
- [ ] **WEB-06**: Tour is accessible (aria-live announcements, focus management, keyboard-navigable, skip button)
- [x] **WEB-07**: End-of-onboarding summary shows what was configured, what was skipped (with navigation links)
- [x] **WEB-08**: Skipped steps show "do it later" signposting with exact navigation path (e.g. "Settings > Profile")
- [x] **WEB-09**: After onboarding completes, show "Unlock full scoring" card with AI provider options (OpenRouter one-click OAuth connect via G-224/G-255, Together.ai, Ollama) and link to provider settings

### Feedback

- [ ] **FB-01**: Persistent feedback button visible in web UI (bottom-right, all pages)
- [ ] **FB-02**: Feedback button opens pre-filled GitHub issue URL with system info (OS, Python version, Kestrel version)
- [ ] **FB-03**: End-of-onboarding prompts for feedback with link to GitHub issues + contact info

### Infrastructure

- [x] **INF-01**: Onboarding state persisted in backend DB (per-profile, timestamps not booleans), shared between CLI and web
- [x] **INF-02**: `OnboardingError` exception hierarchy with `user_message` and `resolution` fields
- [x] **INF-03**: `GET/PATCH /api/onboarding/status` endpoints for state tracking
- [ ] **INF-04**: Non-developer terminal guidance docs page ("Getting Started for Non-Developers")

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Smart CV Import

- **CV-01**: User can upload PDF or DOCX resume file via CLI (`kestrel init --cv resume.pdf`)
- **CV-02**: pdfplumber extracts text from PDF, python-docx extracts from DOCX
- **CV-03**: Regex tier extracts contact info (email, phone, URLs) from document text
- **CV-04**: spaCy NER tier extracts name, organizations, locations, dates (optional `[cv]` extra)
- **CV-05**: rapidfuzz matches extracted skills against taxonomy
- **CV-06**: Image-only PDFs detected and user routed to manual entry with clear message
- **CV-07**: All CV parsing happens locally — no data leaves the machine
- **CV-08**: Web-side file upload UI for CV documents (`POST /api/onboarding/cv`)

### Enhanced Guidance

- **GUIDE-01**: `--explain` flag for verbose non-developer CLI step explanations
- **GUIDE-02**: LinkedIn URL import (fetch public profile data)
- **GUIDE-03**: Local LLM re-parse of pasted resume text via Ollama integration

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| AI provider setup during onboarding wizard | Blocks progress, adds friction. Post-onboarding nudge (WEB-09) handles this instead. |
| OCR for scanned PDF resumes | Adds tesseract ~500MB dependency, unreliable results, rare use case |
| Multi-language CV parsing | Huge complexity multiplier (different NER models per language). English-only for v1+v2. |
| Onboarding analytics / telemetry | Privacy-first product. No phoning home. Local-only state tracking via DB. |
| Animated carousel / slideshow | Mobile SaaS anti-pattern. Users already installed — they need setup, not selling. |
| Mandatory wizard (no escape) | Every step must be skippable. Forced flows create resentment. |
| Mobile app onboarding | Distant future. All React Native onboarding code parked. |
| Account creation / signup flow | Self-hosted = no accounts. Auth is optional admin config, not user onboarding. |
| Gamification (points, badges) | Inappropriate for professional job search tool. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CLI-01 | Phase 2 | Pending |
| CLI-02 | Phase 2 | Pending |
| CLI-03 | Phase 2 | Pending |
| CLI-04 | Phase 2 | Pending |
| CLI-05 | Phase 2 | Pending |
| CLI-06 | Phase 2 | Pending |
| CLI-07 | Phase 2 | Pending |
| CLI-08 | Phase 2 | Pending |
| PROF-01 | Phase 2 | Pending |
| PROF-02 | Phase 2 | Pending |
| PROF-03 | Phase 2 | Pending |
| PROF-04 | Phase 4 | Complete |
| DEMO-01 | Phase 3 | Pending |
| DEMO-02 | Phase 3 | Pending |
| DEMO-03 | Phase 3 | Pending |
| DEMO-04 | Phase 3 | Pending |
| DEMO-05 | Phase 3 | Pending |
| WEB-01 | Phase 4 | Pending |
| WEB-02 | Phase 4 | Complete |
| WEB-03 | Phase 5 | Pending |
| WEB-04 | Phase 4 | Complete |
| WEB-05 | Phase 5 | Pending |
| WEB-06 | Phase 5 | Pending |
| WEB-07 | Phase 4 | Complete |
| WEB-08 | Phase 4 | Complete |
| WEB-09 | Phase 4 | Complete |
| FB-01 | Phase 5 | Pending |
| FB-02 | Phase 5 | Pending |
| FB-03 | Phase 5 | Pending |
| INF-01 | Phase 1 | Complete |
| INF-02 | Phase 1 | Complete |
| INF-03 | Phase 1 | Complete |
| INF-04 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 33 total
- Mapped to phases: 33
- Unmapped: 0

---
*Requirements defined: 2026-04-19*
*Last updated: 2026-04-19 after roadmap creation*
