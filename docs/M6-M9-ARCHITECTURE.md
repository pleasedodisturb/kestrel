# Career OS — Phase 2 Architecture & Milestone Specs (M6–M9)

> Phase 1 (M1–M5): Core platform, discovery, scoring, skills, integrations, voice.
> Phase 2 (M6–M9): Networking CRM, CV pipeline, ATS scanning, auto-apply.

---

## 1. Architecture Principles

### 1.1 CLI-Web Parity

Every feature MUST be fully usable from both CLI and Web UI. The CLI is the primary orchestration interface (Claude Code as operator), the Web UI is the visual dashboard (user as viewer/actor).

**Pattern:**
```
Service (business logic)
  ├── API route (FastAPI) → Web UI consumes
  └── CLI command (Typer) → Claude Code consumes
```

Both API and CLI call the same service functions. No logic in routes or CLI handlers — they are thin wrappers.

**Checklist for every new feature:**
- [ ] Service function exists with full business logic
- [ ] API route exposes it via REST
- [ ] CLI command exposes it via terminal
- [ ] Web UI page/component consumes the API
- [ ] All three produce identical outcomes for the same operation

### 1.2 Debug & Observability System

Every operation should be traceable. When something goes wrong, the user or Claude Code should be able to answer: "what happened, when, and why?"

#### 1.2.1 Structured Activity Log (existing, extend)

The `ActivityLog` model already tracks actions per application. Extend it to be the universal audit trail:

```python
class ActivityLog(Base):
    # Existing fields
    profile_id: int
    application_id: int | None    # nullable — not all actions are app-scoped
    action: str                    # e.g., "contact_created", "cv_rendered", "auto_apply_submitted"
    details: str | None            # human-readable summary
    source: str                    # "api", "cli", "scheduler", "auto_apply"

    # New fields (Phase 2)
    entity_type: str | None        # "application", "contact", "cv_package", "submission"
    entity_id: int | None          # ID of the affected entity
    duration_ms: int | None        # how long the operation took
    error: str | None              # error message if failed
    metadata: str | None           # JSON blob for structured debug data
```

#### 1.2.2 Debug CLI

```bash
career-os debug log                        # last 20 activity log entries
career-os debug log --entity contact       # filter by entity type
career-os debug log --action auto_apply*   # filter by action pattern
career-os debug log --errors               # only failed operations
career-os debug log --since 2h             # last 2 hours
career-os debug status                     # system health: DB size, record counts, integration status
career-os debug inspect <entity> <id>      # full dump of an entity + related records
```

#### 1.2.3 Debug API

```
GET /api/debug/log?entity_type=contact&limit=20&errors_only=true
GET /api/debug/status
GET /api/debug/inspect/{entity_type}/{entity_id}
```

#### 1.2.4 Debug UI

- Settings page → "Debug Log" tab showing recent operations
- Each entity detail page shows its activity log inline (already done for applications, extend to contacts)
- Toast notifications on errors with "View Details" link to debug log

### 1.3 Data Model Conventions

All new models follow these conventions:

```python
class NewModel(Base):
    id: Mapped[int]                          # auto-increment PK
    profile_id: Mapped[int]                  # FK to profiles, always scoped
    created_at: Mapped[datetime]             # UTC, auto-set
    updated_at: Mapped[datetime]             # UTC, auto-set on update
    archived_at: Mapped[datetime | None]     # soft delete, nullable

    # All JSON fields use Text + json.loads/dumps (consistent with existing pattern)
    # All string fields use explicit max lengths
    # All FKs include ondelete behavior (CASCADE or SET NULL)
```

### 1.4 Testing Strategy

Each milestone produces:
- **Unit tests** — service functions with mocked dependencies
- **API tests** — route handlers via TestClient
- **CLI tests** — command execution via CliRunner
- **Integration tests** — cross-feature flows (e.g., "create contact → link to application → referral shows on app detail")
- **Validation contract** — scrutiny reviews + user-testing flows (`.factory/validation/`)

Test naming: `tests/test_{feature}.py` for unit+API, `tests/test_cli_{feature}.py` for CLI, `tests/test_{feature}_integration.py` for cross-feature flows.

### 1.5 Migration Strategy

Each milestone creates one Alembic migration. Migration includes:
- `upgrade()` with new tables/columns
- `downgrade()` that cleanly reverses
- No data migrations in the same file as schema migrations (separate migration if needed)

---

## 2. Shared Infrastructure (pre-M6)

Before starting M6, implement these shared pieces:

### 2.1 Extended ActivityLog

Add `entity_type`, `entity_id`, `duration_ms`, `error`, `metadata` columns to `activity_log` table.

Update the `_log_activity()` helper in services to accept the new fields.

### 2.2 Debug CLI Module

Create `src/career_os/cli/debug.py` with the debug commands. Wire into main CLI app via `app.add_typer()`.

### 2.3 Debug API Router

Create `src/career_os/api/debug.py` with log/status/inspect endpoints.

### 2.4 CLI Module Split (Issue #15)

Split `cli/main.py` (2151 lines) into sub-modules before adding more commands:
```
cli/
  __init__.py
  main.py            # app setup + top-level commands
  pipeline.py        # pipeline CRUD
  discovery.py       # discover + search profiles
  skills.py          # skills + goals
  prep.py            # interview prep + research
  debug.py           # debug commands (new)
  contacts.py        # networking CRM (M6)
  cv.py              # CV pipeline (M7)
  apply.py           # auto-apply (M9)
```

### 2.5 Shared Test Fixtures

Extend `tests/conftest.py` with reusable fixtures:
- `profile` — seeded profile
- `application` — seeded application linked to profile
- `contact` — seeded contact (M6+)
- `authenticated_client` — TestClient with auth header set

---

## 3. M6 — Networking CRM (Issue #23)

### 3.1 Overview

Track contacts, referrals, and interactions linked to companies and applications. The highest-impact feature: referrals convert at 10x the rate of cold applications.

### 3.2 Data Model

```python
class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int]
    profile_id: Mapped[int]                      # FK profiles.id
    name: Mapped[str]                            # max 255
    company: Mapped[str | None]                  # max 255, nullable (freelancers, etc.)
    role: Mapped[str | None]                     # max 255, their role
    email: Mapped[str | None]                    # max 255
    linkedin_url: Mapped[str | None]             # max 500
    phone: Mapped[str | None]                    # max 50
    relationship_type: Mapped[str]               # enum: referral, recruiter, hiring_manager, peer, mentor, other
    referral_status: Mapped[str | None]          # enum: none, contacted, cv_sent, submitted, feedback_received
    warmth: Mapped[str]                          # enum: cold, warm, hot — how strong the connection is
    notes: Mapped[str | None]                    # free text
    tags: Mapped[str | None]                     # JSON array as text (e.g., ["ai", "tpm", "berlin"])
    source: Mapped[str | None]                   # max 100: "linkedin", "conference", "intro", "cold_outreach"
    last_contacted_at: Mapped[datetime | None]   # UTC
    next_follow_up: Mapped[datetime | None]      # UTC — when to ping them next
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    archived_at: Mapped[datetime | None]

class ContactInteraction(Base):
    __tablename__ = "contact_interactions"

    id: Mapped[int]
    contact_id: Mapped[int]                      # FK contacts.id, ondelete CASCADE
    profile_id: Mapped[int]                      # FK profiles.id
    interaction_type: Mapped[str]                # enum: email, call, coffee, linkedin_message, intro, referral_submission
    direction: Mapped[str]                       # enum: inbound, outbound
    subject: Mapped[str | None]                  # max 500
    notes: Mapped[str | None]                    # free text
    occurred_at: Mapped[datetime]                # when the interaction happened
    created_at: Mapped[datetime]

class ContactApplication(Base):
    """Link table: which contacts are associated with which applications."""
    __tablename__ = "contact_applications"

    id: Mapped[int]
    contact_id: Mapped[int]                      # FK contacts.id, ondelete CASCADE
    application_id: Mapped[int]                  # FK applications.id, ondelete CASCADE
    role: Mapped[str]                            # what role this contact plays for this app:
                                                 # "referrer", "recruiter", "hiring_manager", "interviewer", "insider"
    notes: Mapped[str | None]
    created_at: Mapped[datetime]
```

### 3.3 API Endpoints

```
# Contact CRUD
POST   /api/contacts                              → ContactResponse (201)
GET    /api/contacts?profile_id=1                  → ContactListResponse
GET    /api/contacts/{id}?profile_id=1             → ContactResponse
PATCH  /api/contacts/{id}?profile_id=1             → ContactResponse
DELETE /api/contacts/{id}?profile_id=1             → 204

# Filtering & search
GET    /api/contacts?company=Mistral               → filter by company
GET    /api/contacts?relationship_type=referral     → filter by type
GET    /api/contacts?warmth=hot                     → filter by warmth
GET    /api/contacts?needs_follow_up=true           → overdue follow-ups
GET    /api/contacts?search=<text>                  → full-text search on name/company/notes

# Interactions
POST   /api/contacts/{id}/interactions             → InteractionResponse (201)
GET    /api/contacts/{id}/interactions              → InteractionListResponse

# Contact-Application linking
POST   /api/contacts/{id}/applications             → link contact to application
GET    /api/contacts/{id}/applications              → list linked applications
DELETE /api/contacts/{id}/applications/{app_id}     → unlink

# Reverse lookup: "who do I know at this company?"
GET    /api/applications/{id}/contacts              → contacts linked to this application
GET    /api/contacts/by-company/{company}            → all contacts at a company
```

### 3.4 CLI Commands

```bash
# CRUD
career-os contacts add --name "Jane Doe" --company "Mistral" --type referral --warmth hot
career-os contacts list
career-os contacts list --company Mistral
career-os contacts list --type referral
career-os contacts list --needs-follow-up
career-os contacts show <id>
career-os contacts update <id> --referral-status cv_sent
career-os contacts archive <id>

# Interactions
career-os contacts log <id> --type email --direction outbound --notes "Sent CV for TPM role"
career-os contacts log <id> --type intro --direction inbound --notes "Intro'd by mutual friend"
career-os contacts history <id>

# Linking
career-os contacts link <contact_id> <application_id> --role referrer
career-os contacts unlink <contact_id> <application_id>

# Company view
career-os contacts at <company>         # "who do I know at Mistral?"

# Follow-up reminders
career-os contacts follow-ups           # all overdue contact follow-ups
```

### 3.5 Web UI

#### Pages
- `/contacts` — main contacts page with list/grid view, filters, search
- Contact detail modal or inline expand (not a separate page — contacts are lightweight)

#### Components
- `ContactsPage.tsx` — list + filters + add dialog
- `ContactCard.tsx` — compact card in list
- `ContactDetail.tsx` — expanded view with interactions timeline
- `AddContactDialog.tsx` — form for new contact
- `LogInteractionDialog.tsx` — form for logging interaction
- `LinkContactDialog.tsx` — link contact to application (from app detail page)

#### Integration with existing pages
- `ApplicationDetail.tsx` → new "Contacts" section showing linked contacts + "Link Contact" button
- `KanbanCard.tsx` → referral badge if any linked contact has `relationship_type=referral`
- `Layout.tsx` → new nav item "Contacts" (between Follow-ups and Skills)

### 3.6 Test Matrix

#### Unit Tests (`tests/test_contacts.py`)

| # | Test | Assert |
|---|------|--------|
| 1 | create_contact with all fields | returns Contact with correct data |
| 2 | create_contact minimal fields | name + profile_id sufficient |
| 3 | list_contacts filters by profile_id | only own contacts returned |
| 4 | list_contacts filters by company | case-insensitive substring match |
| 5 | list_contacts filters by relationship_type | exact match |
| 6 | list_contacts filters by warmth | exact match |
| 7 | list_contacts needs_follow_up | returns contacts with next_follow_up < now |
| 8 | list_contacts search | matches on name, company, notes |
| 9 | update_contact changes fields | only specified fields updated |
| 10 | update_contact referral_status | validates enum value |
| 11 | archive_contact | sets archived_at, excluded from list |
| 12 | create_interaction | linked to contact, updates last_contacted_at |
| 13 | list_interactions | ordered by occurred_at desc |
| 14 | link_contact_to_application | creates ContactApplication record |
| 15 | link_contact_duplicate | returns 409 or ignores |
| 16 | unlink_contact | removes ContactApplication record |
| 17 | contacts_by_company | returns all contacts at a company name |
| 18 | contacts_for_application | returns linked contacts via join |
| 19 | contact_not_found | raises ContactNotFoundError |
| 20 | profile_scoping | contact from profile 2 not visible to profile 1 |

#### API Tests (`tests/test_contacts_api.py`)

| # | Test | Assert |
|---|------|--------|
| 1 | POST /api/contacts — valid | 201 + response body |
| 2 | POST /api/contacts — missing name | 422 |
| 3 | GET /api/contacts — empty | 200, empty list |
| 4 | GET /api/contacts — with data | 200, correct count |
| 5 | GET /api/contacts?company=X | filtered results |
| 6 | GET /api/contacts/{id} — exists | 200 |
| 7 | GET /api/contacts/{id} — not found | 404 |
| 8 | PATCH /api/contacts/{id} | 200, updated fields |
| 9 | DELETE /api/contacts/{id} | 204 |
| 10 | POST /api/contacts/{id}/interactions | 201 |
| 11 | GET /api/contacts/{id}/interactions | 200, ordered |
| 12 | POST /api/contacts/{id}/applications | link created |
| 13 | GET /api/applications/{id}/contacts | reverse lookup |
| 14 | GET /api/contacts/by-company/Mistral | company lookup |
| 15 | GET /api/contacts?needs_follow_up=true | overdue contacts |

#### CLI Tests (`tests/test_cli_contacts.py`)

| # | Test | Assert |
|---|------|--------|
| 1 | contacts add — full flags | contact created, output shows ID |
| 2 | contacts list — empty | "No contacts found" message |
| 3 | contacts list — with data | table output with contacts |
| 4 | contacts list --company X | filtered output |
| 5 | contacts list --type referral | filtered output |
| 6 | contacts show <id> | detail output |
| 7 | contacts update <id> --referral-status cv_sent | updated |
| 8 | contacts log <id> --type email | interaction created |
| 9 | contacts history <id> | interactions listed |
| 10 | contacts link <c_id> <a_id> | linked |
| 11 | contacts at <company> | company contacts listed |
| 12 | contacts follow-ups | overdue listed |

#### Integration Tests (`tests/test_contacts_integration.py`)

| # | Test | Assert |
|---|------|--------|
| 1 | create contact → link to app → app detail shows contact | full flow |
| 2 | create contact → log interaction → last_contacted_at updates | timestamp propagation |
| 3 | archive application → linked contacts still exist | contacts independent of app lifecycle |
| 4 | archive contact → excluded from app detail contacts | soft delete respected |
| 5 | referral contact linked → application shows referral badge data | badge data in response |
| 6 | contact follow-up overdue → appears in follow-up list | cross-feature flow |

#### Frontend Tests (`frontend/src/__tests__/Contacts.test.tsx`)

| # | Test | Assert |
|---|------|--------|
| 1 | renders contact list | shows contacts |
| 2 | add contact dialog | form fields present |
| 3 | filter by company | filtered results |
| 4 | filter by type | filtered results |
| 5 | contact detail expands | shows interactions |
| 6 | log interaction | interaction appears in timeline |
| 7 | link contact from app detail | contact linked |
| 8 | empty state | shows "No contacts yet" CTA |
| 9 | error state | shows error message |
| 10 | loading state | shows spinner |

### 3.7 Validation Contract

#### Scrutiny (code review before user-testing)
- Data model review: FK constraints, indexes, cascade behavior
- API review: auth scoping, input validation, error responses
- CLI review: output formatting, error handling, help text
- Frontend review: state management, optimistic updates, error boundaries

#### User-Testing Flows
1. **API Core** — CRUD contacts, interactions, linking (15-20 steps)
2. **CLI Core** — same operations via CLI (12-15 steps)
3. **Web Core** — contacts page, add/edit/filter, link from app detail (15-20 steps)
4. **Cross-System** — create via CLI → verify in Web, create in Web → verify via CLI (10 steps)
5. **Edge Cases** — duplicate links, archived contacts, orphan cleanup (8-10 steps)

### 3.8 Definition of Done

- [ ] Alembic migration for contacts, contact_interactions, contact_applications tables
- [ ] Service layer with full CRUD + linking + filtering + search
- [ ] API routes with profile scoping and input validation
- [ ] CLI commands with rich table output
- [ ] Web UI: contacts page + integration in application detail
- [ ] ActivityLog entries for all contact operations
- [ ] Unit tests: 20 cases
- [ ] API tests: 15 cases
- [ ] CLI tests: 12 cases
- [ ] Integration tests: 6 cases
- [ ] Frontend tests: 10 cases
- [ ] Scrutiny review passed
- [ ] User-testing flows passed (5 flows)
- [ ] All existing tests still pass

---

## 4. M7 — CV Tailoring Pipeline (Issue #26)

### 4.1 Overview

Integrate `render_tailored_cvs.py` and `md_to_pdf_cover_letter.py` into the platform. Generate tailored CVs and cover letter PDFs from the API/CLI, linked to applications as packages.

### 4.2 Data Model

No new tables — uses existing `ApplicationPackage` model. New fields:

```python
# Extend ApplicationPackage (already exists)
class ApplicationPackage(Base):
    # Existing fields: id, profile_id, application_id, package_dir, cv_path, cover_letter_path, created_at

    # New fields
    cv_variant: Mapped[str | None]           # max 50: "tpm", "pm", "devrel", "ai_engineer", etc.
    generation_method: Mapped[str | None]    # "manual", "auto_rendered", "auto_tailored"
    ats_score: Mapped[float | None]          # ATS match score (filled by M8)
    metadata: Mapped[str | None]             # JSON: render config, template used, etc.
```

### 4.3 API Endpoints

```
# CV rendering
POST   /api/applications/{id}/render-cv            → triggers CV render, returns PackageResponse
POST   /api/applications/{id}/render-cover-letter   → triggers cover letter render
GET    /api/applications/{id}/packages              → list all packages (existing)
GET    /api/cv/variants                             → list available CV variants

# Bulk operations
POST   /api/cv/render-batch                         → render CVs for multiple applications
```

### 4.4 CLI Commands

```bash
career-os cv render <application_id>                # render best-fit CV variant
career-os cv render <application_id> --variant tpm  # render specific variant
career-os cv render --all                           # render for all applied/interested apps
career-os cv variants                               # list available variants
career-os cv cover-letter <application_id>          # render cover letter from voice brainstorm or notes
career-os cv cover-letter <application_id> --from-file draft.md  # from markdown file
career-os cv packages <application_id>              # list generated packages
```

### 4.5 Service Layer

```python
# src/career_os/services/cv_pipeline.py

def select_best_variant(db, application_id) -> str:
    """Select the best CV variant based on role type, company, and job requirements."""

def render_cv(db, application_id, *, variant: str | None = None) -> ApplicationPackage:
    """Render a tailored CV for an application. Uses RenderCV."""

def render_cover_letter(db, application_id, *, source: str = "voice") -> ApplicationPackage:
    """Render a cover letter PDF. Source: voice session transcript, notes, or file."""

def render_batch(db, profile_id, *, application_ids: list[int]) -> list[ApplicationPackage]:
    """Batch render CVs for multiple applications."""
```

### 4.6 Test Matrix

| # | Category | Test | Assert |
|---|----------|------|--------|
| 1 | Unit | select_best_variant for TPM role | returns "tpm" variant |
| 2 | Unit | select_best_variant for DevRel role | returns "devrel" variant |
| 3 | Unit | select_best_variant unknown role | returns "general" fallback |
| 4 | Unit | render_cv creates package | ApplicationPackage with cv_path set |
| 5 | Unit | render_cv with explicit variant | uses specified variant |
| 6 | Unit | render_cover_letter from voice | extracts from voice session |
| 7 | Unit | render_cover_letter from notes | uses application notes |
| 8 | Unit | render_batch multiple apps | correct count of packages |
| 9 | API | POST /render-cv | 201 + package response |
| 10 | API | POST /render-cv app not found | 404 |
| 11 | API | GET /cv/variants | list of available variants |
| 12 | CLI | cv render <id> | package created, path printed |
| 13 | CLI | cv variants | table of variants |
| 14 | CLI | cv cover-letter <id> | cover letter generated |
| 15 | Integration | render CV → verify file exists | file on disk |
| 16 | Integration | render CV → ATS score updates (M8) | score populated |

### 4.7 Definition of Done

- [ ] Alembic migration for ApplicationPackage new columns
- [ ] Service: select_best_variant, render_cv, render_cover_letter, render_batch
- [ ] API routes for rendering + listing variants
- [ ] CLI commands for cv render/variants/cover-letter/packages
- [ ] Web UI: "Generate CV" button on application detail
- [ ] ActivityLog for all render operations
- [ ] 16 tests (unit + API + CLI + integration)
- [ ] Scrutiny + user-testing passed

---

## 5. M8 — ATS Resume Scanner (Issue #24)

### 5.1 Overview

Score how well a CV matches a job description. Uses the AI provider to extract keywords from JD, compare against CV content, and return a match percentage with specific gaps.

### 5.2 Data Model

```python
class ATSScan(Base):
    __tablename__ = "ats_scans"

    id: Mapped[int]
    profile_id: Mapped[int]
    application_id: Mapped[int]                  # FK applications.id
    package_id: Mapped[int | None]               # FK application_packages.id — which CV was scanned
    match_score: Mapped[float]                   # 0-100 percentage
    matched_keywords: Mapped[str]                # JSON list of matched keywords
    missing_keywords: Mapped[str]                # JSON list of missing keywords
    suggestions: Mapped[str | None]              # JSON list of improvement suggestions
    jd_hash: Mapped[str]                         # hash of job description (detect changes)
    cv_hash: Mapped[str]                         # hash of CV content (detect changes)
    created_at: Mapped[datetime]
```

### 5.3 API Endpoints

```
POST   /api/applications/{id}/ats-scan             → run scan, return ATSScanResponse
GET    /api/applications/{id}/ats-scan              → get latest scan result
GET    /api/applications/{id}/ats-scan/history       → all scan results for this app
```

### 5.4 CLI Commands

```bash
career-os ats scan <application_id>                  # scan CV against JD
career-os ats scan <application_id> --jd "paste..."  # scan against custom JD text
career-os ats scan <application_id> --variant tpm    # scan a specific CV variant
career-os ats report <application_id>                # detailed report with suggestions
career-os ats batch                                  # scan all applied apps without recent scan
```

### 5.5 AI Provider Extension

```python
# New AIFeature enum value
class AIFeature(StrEnum):
    ats_scan = "ats_scan"

# Mock provider handler
def _handle_ats_scan(prompt, context) -> AIResponse:
    """Return deterministic ATS scan result."""
    return AIResponse(
        structured=ATSScanResult(
            match_score=72.0,
            matched_keywords=["stakeholder management", "agile", "cross-functional"],
            missing_keywords=["kubernetes", "terraform", "CI/CD"],
            suggestions=["Add cloud infrastructure keywords", "Mention specific CI/CD tools"],
        ),
        ...
    )
```

### 5.6 Test Matrix

| # | Category | Test | Assert |
|---|----------|------|--------|
| 1 | Unit | scan_cv with mock provider | returns ATSScan with score |
| 2 | Unit | scan_cv extracts keywords | matched + missing lists populated |
| 3 | Unit | scan_cv no JD available | raises error |
| 4 | Unit | scan_cv caches by hash | same JD+CV returns existing scan |
| 5 | Unit | scan_cv detects JD change | new scan if JD hash differs |
| 6 | API | POST /ats-scan | 201 + scan response |
| 7 | API | GET /ats-scan | latest scan |
| 8 | API | GET /ats-scan/history | all scans ordered |
| 9 | CLI | ats scan <id> | score printed with keywords |
| 10 | CLI | ats report <id> | detailed report |
| 11 | Integration | render CV → scan → suggestions | end-to-end pipeline |
| 12 | Integration | scan → update ApplicationPackage.ats_score | score propagates |

### 5.7 Definition of Done

- [ ] Alembic migration for ats_scans table
- [ ] Service: scan_cv, get_latest_scan, scan_batch
- [ ] AI provider: ats_scan feature in mock + openrouter
- [ ] API routes
- [ ] CLI commands
- [ ] Web UI: ATS score badge on application detail + scan button
- [ ] 12 tests
- [ ] Scrutiny + user-testing passed

---

## 6. M9 — Auto-Apply Pipeline (Issue #25)

### 6.1 Overview

Integrate `tools/auto_apply.py` into the platform. Queue-based submission system with dry-run default, safety confirmations, and result tracking.

### 6.2 Data Model

```python
class SubmissionAttempt(Base):
    __tablename__ = "submission_attempts"

    id: Mapped[int]
    profile_id: Mapped[int]
    application_id: Mapped[int]                  # FK applications.id
    package_id: Mapped[int | None]               # FK application_packages.id — which CV/CL was used
    platform: Mapped[str]                        # "lever", "greenhouse", "ashby", "workable", "manual"
    status: Mapped[str]                          # "queued", "dry_run", "pending_confirm", "submitted", "failed", "rejected"
    dry_run: Mapped[bool]                        # was this a dry run?
    submit_url: Mapped[str | None]               # the actual submission URL
    screenshot_path: Mapped[str | None]          # path to pre-submit screenshot
    response_data: Mapped[str | None]            # JSON: API response or error details
    error: Mapped[str | None]                    # error message if failed
    submitted_at: Mapped[datetime | None]        # when actually submitted (null if dry_run)
    created_at: Mapped[datetime]
```

### 6.3 API Endpoints

```
# Submission queue
POST   /api/applications/{id}/submit               → queue submission (dry_run=true default)
POST   /api/applications/{id}/submit/confirm        → confirm and execute a pending submission
GET    /api/submissions                             → list all submission attempts
GET    /api/submissions/{id}                        → submission detail with screenshot

# Batch
POST   /api/submissions/batch                       → queue multiple submissions
```

### 6.4 CLI Commands

```bash
career-os apply <application_id>                     # dry-run (default)
career-os apply <application_id> --confirm           # actually submit
career-os apply <application_id> --platform lever    # force specific platform
career-os apply --batch --dry-run                    # dry-run all queued apps
career-os apply --batch --confirm                    # submit all queued (with per-app confirmation)
career-os apply list                                 # list submission history
career-os apply show <submission_id>                 # show submission detail
```

### 6.5 Safety Rules (from .claude/rules/auto-apply.md)

- ALWAYS dry-run first before any real submission
- ALWAYS require user confirmation before submitting
- Screenshots saved to `screenshots/` before each submit
- Rate limiting: max 10 submissions per hour
- Activity log entry for every attempt (including dry runs)

### 6.6 Service Layer

```python
# src/career_os/services/auto_apply.py

async def prepare_submission(db, application_id, *, platform: str | None = None) -> SubmissionAttempt:
    """Prepare a submission (dry run). Detects platform, validates package, takes screenshot."""

async def confirm_submission(db, submission_id) -> SubmissionAttempt:
    """Execute a pending submission. Updates application status to 'applied' on success."""

async def batch_prepare(db, profile_id, *, application_ids: list[int]) -> list[SubmissionAttempt]:
    """Prepare multiple submissions."""

def detect_platform(url: str) -> str:
    """Detect submission platform from URL (lever, greenhouse, ashby, workable)."""
```

### 6.7 Test Matrix

| # | Category | Test | Assert |
|---|----------|------|--------|
| 1 | Unit | detect_platform lever URL | returns "lever" |
| 2 | Unit | detect_platform greenhouse URL | returns "greenhouse" |
| 3 | Unit | detect_platform unknown URL | returns "manual" |
| 4 | Unit | prepare_submission dry_run | status="dry_run", no actual submit |
| 5 | Unit | prepare_submission no package | raises error |
| 6 | Unit | confirm_submission | status="submitted", app status="applied" |
| 7 | Unit | confirm_submission already submitted | raises error |
| 8 | Unit | rate_limit exceeded | raises RateLimitError |
| 9 | API | POST /submit (dry_run) | 201 + dry_run response |
| 10 | API | POST /submit/confirm | 200 + submitted |
| 11 | API | GET /submissions | list of attempts |
| 12 | CLI | apply <id> | dry-run output |
| 13 | CLI | apply <id> --confirm | submission output |
| 14 | CLI | apply list | table of submissions |
| 15 | Integration | prepare → confirm → app status changes | end-to-end |
| 16 | Integration | submit → activity log entry | audit trail |
| 17 | Safety | batch without --confirm | all dry-run |
| 18 | Safety | rate limit 11th submission | blocked |

### 6.8 Definition of Done

- [ ] Alembic migration for submission_attempts table
- [ ] Service: prepare_submission, confirm_submission, batch_prepare, detect_platform
- [ ] API routes with safety defaults
- [ ] CLI commands with confirmation prompts
- [ ] Web UI: "Submit Application" button on app detail (with confirmation dialog)
- [ ] Rate limiting (10/hour)
- [ ] Screenshot capture before submission
- [ ] ActivityLog for all submission attempts
- [ ] 18 tests
- [ ] Scrutiny + user-testing passed

---

## 7. Implementation Timeline

```
Pre-M6:  Shared infrastructure (ActivityLog extension, debug CLI, CLI split)
M6:      Networking CRM (contacts, referrals, interactions)
M7:      CV Tailoring Pipeline (RenderCV + cover letter integration)
M8:      ATS Resume Scanner (keyword matching + scoring)
M9:      Auto-Apply Pipeline (queue + submission + tracking)
```

Each milestone follows the factory process:
1. Build (Ralph loop with spec as prompt)
2. Scrutiny review (code review + security review)
3. Fix scrutiny findings
4. User-testing (5 flows per milestone)
5. Fix user-testing findings
6. Synthesis (quality report)
7. Merge (separate PR per milestone)

---

## 8. Cross-Feature Integration Points

These integrations connect the milestones into a cohesive pipeline:

```
Discovery → Score → [M8: ATS Scan] → [M7: Render CV] → [M9: Auto-Apply]
                ↑                           ↑
          [M6: Referral contact]    [M6: Contact as reference]
```

### Key integration flows:
1. **Referral-boosted discovery**: Contact with referral → linked application gets priority in pipeline
2. **CV → Scan → Improve loop**: Render CV (M7) → ATS scan (M8) → see gaps → re-render with tweaks
3. **Prep-to-apply pipeline**: Research + prep + render CV + cover letter → auto-submit (M9)
4. **Contact-driven follow-up**: Interaction logged → next_follow_up set → appears in follow-ups page

---

*Spec version: 1.0 — March 14, 2026*
*Author: Claude Code*
