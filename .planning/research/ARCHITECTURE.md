# Architecture Patterns

**Domain:** Onboarding system for existing CLI + Web application (Kestrel)
**Researched:** 2026-04-19

## Recommended Architecture

### System Overview

The onboarding system is a cross-cutting concern that touches three boundaries: CLI (`kestrel init`), Web UI (welcome flow + interactive tour), and Backend API (onboarding state + CV parsing). It does NOT introduce a new service -- it integrates into existing layers.

```
                          +-----------------------+
                          |   Onboarding State    |
                          |  (Backend API + DB)   |
                          +----------+------------+
                                     |
                    +----------------+----------------+
                    |                                  |
          +---------+----------+          +-----------+-----------+
          |   CLI Wizard       |          |   Web Welcome Flow    |
          |  `kestrel init`    |          |  React Route Guard    |
          |   (Typer + Rich)   |          |  + Interactive Tour   |
          +--------------------+          +-----------+-----------+
                    |                                  |
                    |       +--------------------+     |
                    +------>| CV Parser Service  |<----+
                            | (Local, no cloud)  |
                            +--------------------+
                                     |
                            +--------+---------+
                            | Profile API      |
                            | (existing PATCH) |
                            +------------------+
```

### Component Responsibilities

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| **Onboarding State (API)** | Track onboarding progress (steps completed, skipped, completed-at). Single source of truth. | DB (SQLAlchemy), CLI, Web UI |
| **CLI Wizard (`kestrel init`)** | Interactive terminal-based profile setup. CV import prompt, guided questions, demo data seeding. | Onboarding API, CV Parser, Profile API, Demo Seeder |
| **Web Welcome Flow** | Route guard + multi-step welcome UI. CV upload, profile review, interactive tour trigger. | Onboarding API, CV Parser, Profile API, Tour Engine |
| **CV Parser Service** | Extract structured data (name, roles, skills, location) from PDF/DOCX resume files. Runs locally, never sends data externally. | Called by CLI and Web, writes to Profile + Skills models |
| **Interactive Tour Engine** | Tooltip/popover overlays highlighting UI elements in sequence. Contextual, not modal. | Web UI only (frontend-only, no backend calls) |
| **Demo Data Seeder** | Load pre-baked sample jobs with pre-computed scores for instant first-run experience. No API key required. | DB directly (via service layer), triggered by CLI and Web onboarding |
| **Feedback Channel** | Persistent feedback button in web UI + end-of-onboarding prompt. Creates GitHub Issues via API. | GitHub Issues API (external), Web UI |
| **Existing Profile API** | Already handles PATCH profile updates. Onboarding populates profile through this. | DB, used by onboarding components |

## Recommended Project Structure

### Backend additions

```
src/career_os/
  api/
    onboarding.py          # New router: GET/PATCH /api/onboarding/status
  services/
    onboarding.py           # Onboarding business logic, state machine
    cv_parser.py            # CV parsing (PDF/DOCX -> structured data)
    demo_seeder.py          # Pre-baked demo data loading
  models/
    onboarding.py           # OnboardingState model
  schemas/
    onboarding.py           # Pydantic schemas for onboarding endpoints
  cli/
    init.py                 # `kestrel init` wizard command
  data/
    demo/
      sample_jobs.json      # Pre-computed scored jobs for demo
      sample_scores.json    # Pre-computed score breakdowns
```

### Frontend additions

```
frontend/src/
  components/
    onboarding/
      WelcomeFlow.tsx       # Multi-step welcome wizard container
      StepProfile.tsx       # Profile review/edit step
      StepCVUpload.tsx      # CV upload + parse step
      StepTour.tsx          # Tour trigger step
      StepComplete.tsx      # Completion + feedback prompt
      OnboardingGuard.tsx   # Route guard wrapper (checks onboarding state)
    tour/
      TourProvider.tsx      # Context provider for tour state
      TourStep.tsx          # Individual tooltip/popover component
      tourSteps.ts          # Tour step definitions (element selectors, copy)
    FeedbackButton.tsx      # Persistent feedback button (always visible)
  hooks/
    useOnboarding.ts        # TanStack Query hook for onboarding state
    useTour.ts              # Tour progression hook
  pages/
    Welcome.tsx             # Welcome/onboarding page (shown when guard triggers)
```

### CLI addition

```
# In cli/main.py, add:
from career_os.cli.init import init_app
app.add_typer(init_app, name="init")

# OR as a direct command (simpler):
@app.command("init")
def init_wizard(): ...
```

## Architectural Patterns

### Pattern 1: Onboarding State Machine

**What:** A lightweight state model that tracks which onboarding steps are complete. Not a full FSM -- just a checklist with timestamps.

**Why:** Both CLI and Web need to know "has the user completed onboarding?" without coupling to each other. The backend is the single source of truth.

**Model:**

```python
class OnboardingState(Base):
    __tablename__ = "onboarding_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("profiles.id"), unique=True, nullable=False
    )

    # Step completion timestamps (NULL = not done)
    profile_completed_at: Mapped[datetime | None]
    cv_imported_at: Mapped[datetime | None]
    demo_viewed_at: Mapped[datetime | None]
    tour_completed_at: Mapped[datetime | None]

    # Meta
    skipped_at: Mapped[datetime | None]  # User chose "skip all"
    completed_at: Mapped[datetime | None]  # All steps done or skipped
    source: Mapped[str | None]  # "cli" or "web" -- where they onboarded

    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

**Why timestamps over booleans:** Timestamps tell you WHEN each step was done, which is valuable for analytics ("how long does onboarding take?") and debugging ("user got stuck at step 3 for 20 minutes"). Booleans lose that information.

**Why per-profile:** The existing app scopes everything by `profile_id`. Onboarding state follows the same pattern. One profile = one onboarding record.

### Pattern 2: Route Guard for Web Welcome Flow

**What:** A React component wrapping the Layout that checks onboarding status and redirects to the welcome flow if incomplete.

**Why:** The user should never see an empty dashboard with no context. If onboarding is incomplete, they see the welcome flow instead.

```typescript
// OnboardingGuard.tsx
function OnboardingGuard({ children }: { children: ReactNode }) {
  const { data: status, isLoading } = useOnboardingStatus();

  if (isLoading) return <LoadingSpinner />;
  if (!status?.completed_at && !status?.skipped_at) {
    return <Navigate to="/welcome" replace />;
  }
  return <>{children}</>;
}

// In App.tsx:
<Route element={<OnboardingGuard><Layout /></OnboardingGuard>}>
  {/* existing routes */}
</Route>
<Route path="/welcome" element={<WelcomeFlow />} />
```

**Why a guard, not a context provider:** A guard is simpler and has one job: redirect if not onboarded. A context provider would add complexity for something that's checked once and then never again. The guard pattern also means the welcome flow is a separate route, not a modal overlay, which is better for back-button behavior and deep linking.

**Why NOT a feature flag:** Feature flags are for gradual rollouts. Onboarding is binary: you either have or haven't done it. The onboarding state model IS the flag.

### Pattern 3: CLI Wizard as Typer Subcommand

**What:** `kestrel init` as a new command registered in the existing Typer app. NOT a separate entry point.

**Why:** The existing CLI has `kestrel start`, `kestrel discover`, `kestrel score`, etc. Adding `kestrel init` is consistent with user expectations. A separate binary would fragment the CLI surface.

```python
# cli/init.py
@app.command("init")
def init_wizard(
    cv: Path | None = typer.Option(None, "--cv", help="Path to your CV/resume (PDF or DOCX)"),
    skip: bool = typer.Option(False, "--skip", help="Skip wizard, use defaults"),
) -> None:
    """Set up your Kestrel profile interactively."""
```

**Why Typer, not Click directly:** The existing CLI is 100% Typer. Consistency trumps preferences.

**Why `--cv` as an option, not an argument:** Most users will run `kestrel init` without a CV first time. The CV is an enhancement, not required. Making it an argument would imply it's required.

### Pattern 4: Local CV Parsing (No Cloud)

**What:** PDF/DOCX parsing using local libraries only. No data leaves the machine.

**Why:** Privacy constraint from PROJECT.md: "CV parsing must happen locally, never sent to external services." This is non-negotiable for a self-hosted tool.

**Approach:**

```python
# services/cv_parser.py
class CVParserService:
    def parse(self, file_path: Path) -> ParsedCV:
        """Extract structured data from a CV file."""
        text = self._extract_text(file_path)
        return self._structure_data(text)

    def _extract_text(self, path: Path) -> str:
        if path.suffix.lower() == ".pdf":
            return self._parse_pdf(path)
        elif path.suffix.lower() in (".docx", ".doc"):
            return self._parse_docx(path)
        raise UnsupportedFormatError(f"Unsupported: {path.suffix}")

    def _structure_data(self, text: str) -> ParsedCV:
        """Use regex/heuristic extraction for v1.
        Pattern-match sections: Experience, Education, Skills, Contact.
        """
```

**v1: Heuristic/regex extraction.** No LLM. Reasons:
1. No API key available during onboarding (constraint)
2. Fast and deterministic
3. Privacy-safe
4. "Good enough" for names, emails, skills lists, job titles

**v2 (future):** Optional local LLM enhancement (Ollama) for better extraction. Gated behind feature flag.

### Pattern 5: Pre-Baked Demo Data

**What:** JSON fixtures of sample jobs with pre-computed scores, shipped with the package. Loaded into DB on demand.

**Why:** The user needs to see scored results immediately. Without an API key, live scoring is impossible. Pre-baked data gives an instant, deterministic "aha moment."

```python
# services/demo_seeder.py
DEMO_DATA_DIR = Path(__file__).parent.parent / "data" / "demo"

class DemoSeeder:
    def seed(self, db: Session, profile_id: int) -> int:
        """Load demo jobs + scores. Idempotent."""
        if self._already_seeded(db, profile_id):
            return 0
        jobs = json.loads((DEMO_DATA_DIR / "sample_jobs.json").read_text())
        # ... create DiscoveredJob + Application records with source="demo"
```

**Why JSON fixtures, not SQL dumps:** JSON is portable, human-readable, and easy to update. SQL dumps are brittle across schema versions.

**Why embedded in package, not downloadable:** One fewer network dependency during onboarding. The demo data is small (< 100KB). Ship it.

### Pattern 6: Persistent Feedback Button

**What:** A fixed-position button in the web UI that opens a feedback form. Always visible, not just during onboarding.

**Why:** PROJECT.md explicitly requires "persistent feedback channel." The button creates a GitHub Issue via the API.

```typescript
// FeedbackButton.tsx - positioned fixed bottom-right
function FeedbackButton() {
  return (
    <button
      onClick={() => window.open(GITHUB_NEW_ISSUE_URL, '_blank')}
      className="fixed bottom-4 right-4 ..."
    >
      Feedback
    </button>
  );
}
```

**v1: Simple link to pre-filled GitHub Issue URL.** No custom backend endpoint needed. GitHub's issue template system handles the form structure.

**Why NOT a custom feedback API:** Adding a backend feedback service, storage, and admin UI is overengineering for v1. GitHub Issues is the existing issue tracker. Go direct.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Onboarding as a Modal Overlay
**What:** Showing onboarding as a modal/drawer on top of the existing dashboard.
**Why bad:** Modals are dismissible, lose state on refresh, and fight with the underlying page. The welcome flow should OWN the screen, not float on top of it.
**Instead:** Separate `/welcome` route with the route guard pattern.

### Anti-Pattern 2: Coupling CLI and Web Onboarding Steps
**What:** Making the CLI wizard call the same step-by-step sequence as the web flow.
**Why bad:** CLI and web have fundamentally different interaction models. CLI is sequential, blocking, text-based. Web is visual, non-blocking, can show previews.
**Instead:** Both share the same onboarding state model and CV parser, but have independent UI flows. The state model is the integration point, not the flow.

### Anti-Pattern 3: Storing Onboarding State in LocalStorage
**What:** Putting onboarding progress in browser storage instead of the backend.
**Why bad:** Doesn't sync between CLI and web. Cleared when user clears browser data. Can't query it server-side.
**Instead:** Backend DB via the onboarding state model. Both CLI and web read/write through the API.

### Anti-Pattern 4: Using the LLM for CV Parsing During Onboarding
**What:** Requiring an AI provider to extract CV data.
**Why bad:** No API key is available during onboarding (explicit constraint). Would add latency, cost, and a failure mode to the first-run experience.
**Instead:** Heuristic/regex extraction for v1. Good enough for structured CVs. Flag for future LLM enhancement.

### Anti-Pattern 5: Replacing `setup.sh` with `kestrel init`
**What:** Making the CLI wizard replace the existing Docker setup script.
**Why bad:** `setup.sh` handles Docker pre-flight checks (disk space, ports, internet). `kestrel init` handles profile setup. Different concerns, different users (Docker users vs pip users).
**Instead:** `setup.sh` handles infrastructure. `kestrel init` handles personalization. For Docker users, `setup.sh` could CALL `kestrel init` at the end as an optional step.

## Data Flow

### Flow 1: CLI Onboarding (`kestrel init`)

```
User runs `kestrel init`
    |
    v
[1] Check DB: onboarding state for profile_id=1
    |-- Already completed? Print "Already set up. Run with --reset to redo."
    |-- Not started? Continue.
    v
[2] CV prompt: "Do you have a resume file? (path or Enter to skip)"
    |-- Yes: Parse CV -> extract name, email, location, skills, roles
    |       Show extracted data for confirmation
    |       Write to Profile (PATCH) + Skills (POST)
    |-- No: Fall through to guided questions
    v
[3] Guided questions (max 7, skip any with Enter):
    - Name (pre-filled if CV extracted)
    - Email (pre-filled if CV extracted)
    - Location (pre-filled if CV extracted)
    - Target job family (with examples)
    - Dream companies (comma-separated)
    - Salary range (min-max)
    - Values (what matters to you?)
    |
    v
[4] Write profile data to DB via service layer (not HTTP)
    |
    v
[5] Seed demo data: load sample_jobs.json into DiscoveredJob table
    Print: "Loaded 10 sample jobs with pre-computed scores."
    |
    v
[6] Mark onboarding complete in onboarding_state table
    |
    v
[7] Print summary + next steps:
    "Your profile is set up! Run `kestrel start` to open the dashboard."
    "Run `kestrel discover` to find real jobs."
```

### Flow 2: Web UI Onboarding

```
User opens http://localhost:8101
    |
    v
[1] OnboardingGuard checks GET /api/onboarding/status
    |-- completed_at or skipped_at set? -> Show normal dashboard
    |-- Not set? -> Redirect to /welcome
    v
[2] Welcome page: "Welcome to Kestrel" + brief pitch
    Button: "Get Started" / "Skip Setup"
    |
    v
[3] Step 1 - CV Upload (optional):
    Drag-and-drop zone or file picker
    POST /api/onboarding/cv -> parse and show extracted data
    User confirms/edits extracted fields
    |
    v
[4] Step 2 - Profile Review:
    Pre-filled form (from CV or defaults)
    Name, email, location, job family, dream companies
    PATCH /api/profiles/{id}
    |
    v
[5] Step 3 - Demo Results:
    Show pre-baked scored jobs in a mini-pipeline view
    "These are sample results. Run Discovery to find real jobs."
    POST /api/onboarding/seed-demo
    |
    v
[6] Step 4 - Interactive Tour (optional):
    Tooltip-driven walkthrough of Pipeline, Discovery, Score pages
    Highlight nav items, key buttons, score breakdowns
    |
    v
[7] Completion screen:
    "You're all set!" + next steps
    Feedback prompt + GitHub issue link
    PATCH /api/onboarding/status { completed_at: now }
    |
    v
[8] Redirect to Pipeline (normal dashboard)
```

### Flow 3: CV Parsing (shared by CLI and Web)

```
Input: file path (CLI) or uploaded file (Web)
    |
    v
[1] Detect format: PDF or DOCX
    |
    v
[2] Extract raw text:
    PDF: pdfplumber or PyMuPDF
    DOCX: python-docx
    |
    v
[3] Section detection (heuristic):
    - Find headers: "Experience", "Education", "Skills", "Contact"
    - Split text into sections
    |
    v
[4] Field extraction (regex + patterns):
    - Name: first non-empty line or "Name:" field
    - Email: email regex
    - Phone: phone regex
    - Location: after "Location:" or city/country patterns
    - Skills: bullet points under "Skills" section
    - Roles: job titles from "Experience" section
    |
    v
[5] Return ParsedCV:
    {
      name, email, phone, location,
      skills: [str],
      roles: [{title, company, dates}],
      education: [{degree, institution}],
      raw_text: str  # for future LLM re-parse
    }
    |
    v
[6] Caller (CLI/Web) presents data for confirmation
```

## Integration Points with Existing Kestrel Codebase

### 1. Profile Model (existing, no changes needed)

The Profile model already has: `name`, `email`, `location`, `job_family`, `dream_companies`. Onboarding populates these through the existing `ProfileUpdate` schema and PATCH endpoint. No model changes needed.

### 2. Skills Model (existing, no changes needed)

The onboarding CV parser extracts skills and writes them through the existing skills service (`services/skills.py`). No new skill-related models needed.

### 3. CLI Entry Point (existing `app` in cli/main.py)

Add `kestrel init` as a new command to the existing Typer app. Follows the same pattern as `kestrel start`, `kestrel discover`, etc. The `_get_session()` and `_get_default_profile()` helpers are already available.

### 4. Seed System (existing pattern in migration/seed.py)

Demo data seeding follows the same idempotent pattern as `seed_default_profile()` and `seed_ghost_detection_records()`. Check for existing demo records before inserting.

### 5. Frontend Routing (existing App.tsx)

Add `/welcome` route outside the `<Layout />` wrapper (welcome flow has its own layout). Add `OnboardingGuard` around the `<Layout />` route group.

### 6. API Router Registration (existing main.py pattern)

New `onboarding_router` registered in `main.py` alongside the other 25+ routers. Follows the same `APIRouter(prefix="/api/onboarding")` pattern.

### 7. Database Migration

One new Alembic migration for the `onboarding_state` table. Auto-migration on startup handles deployment (existing `_auto_migrate()` in main.py).

### 8. `setup.sh` Integration (optional, minimal)

At the end of the existing `setup.sh` success block, add a hint:
```
echo "  Run 'kestrel init' to set up your profile interactively"
```
Do NOT make `setup.sh` call `kestrel init` automatically -- that would require the Docker container to be interactive.

## Build Order (Dependencies)

The following order respects component dependencies:

```
Phase 1: Foundation
  [1] OnboardingState model + migration
  [2] Onboarding API (GET/PATCH status)
  [3] Onboarding service layer
  -- Dependency: everything else reads/writes onboarding state

Phase 2: CV Parser
  [4] CV text extraction (PDF + DOCX)
  [5] Heuristic field extraction
  [6] ParsedCV schema + confirmation flow helpers
  -- Dependency: both CLI and Web consume this

Phase 3: CLI Wizard
  [7] `kestrel init` command
  [8] CV import integration
  [9] Guided questions fallback
  -- Dependency: needs onboarding state + CV parser

Phase 4: Demo Data
  [10] Sample jobs fixture creation
  [11] Demo seeder service
  [12] CLI + API trigger for seeding
  -- Dependency: needs existing DiscoveredJob model; consumed by CLI and Web

Phase 5: Web Welcome Flow
  [13] OnboardingGuard component
  [14] Welcome page + step components
  [15] CV upload UI + API integration
  [16] Demo results display
  -- Dependency: needs onboarding API + CV parser + demo seeder

Phase 6: Interactive Tour
  [17] Tour provider + step engine
  [18] Tour step definitions
  [19] Integration with welcome flow completion
  -- Dependency: needs existing pages rendered to attach tooltips to

Phase 7: Feedback Channel
  [20] Persistent feedback button
  [21] GitHub Issue URL builder
  [22] End-of-onboarding feedback prompt
  -- Dependency: minimal, can ship in parallel with Phase 5/6
```

## Scalability Considerations

| Concern | At 1 user (self-hosted) | At 100 users (future SaaS) | Notes |
|---------|-------------------------|----------------------------|-------|
| Onboarding state | One row per profile, trivial | 100 rows, trivial | Indexed by profile_id |
| CV parsing | Synchronous, sub-second | Queue-based, async | v1 sync is fine for self-hosted |
| Demo data | ~10 sample jobs, < 100KB | Same fixtures for all users | Demo data is read-only template |
| Tour state | Frontend-only, no persistence | Could persist for analytics | v1: localStorage is fine for tour progress |

## Sources

- Kestrel codebase analysis (direct code reading) -- HIGH confidence
- Existing patterns: Typer CLI (`cli/main.py`), FastAPI routers (`api/profiles.py`), SQLAlchemy models (`models/models.py`), seed system (`migration/seed.py`)
- PROJECT.md constraints: local CV parsing, no API keys during onboarding, < 10 minute completion
- CV parsing libraries: pdfplumber (MIT, maintained), python-docx (MIT, maintained) -- standard Python PDF/DOCX extraction
