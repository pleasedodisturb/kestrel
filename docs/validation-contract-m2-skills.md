# Validation Contract — Milestone 2: Skills Intelligence, Goals & Coaching

> **Scope:** Dynamic skills inventory, gap analysis, learning paths, career goals, AI coaching, CLI commands.
> **Platform:** FastAPI + React + SQLite + Typer CLI
> **Data sources:** `cv/cv.yaml`, `profile/` docs (cliftonstrengths.md, personality-epp.md, workplace-insights.md, strengths-summary.md), job postings, user input.

---

## Skills Inventory

### VAL-SKILL-001: CV parsing populates skills inventory
When the system ingests `cv/cv.yaml`, it extracts skills from experience entries, the skills section, and summary — populating the skills inventory with correct categories (technical, domain, soft, tools) and evidence sources pointing back to specific CV sections.
**Evidence:** GET `/api/skills` returns ≥ 1 skill per category; each skill has `source: "cv.yaml"` and a non-empty `evidence` field referencing the originating CV section.

### VAL-SKILL-002: Psychometric assessment parsing
When CliftonStrengths, EPP, CCAT, and Workplace Insights documents are ingested, the system extracts soft skills and cognitive attributes (e.g., Communication from CliftonStrengths #1, 85th-percentile Extroversion from EPP) and adds them to the inventory with assessment-specific source tags.
**Evidence:** GET `/api/skills?category=soft` returns entries with `source` values including `"cliftonstrengths"`, `"epp"`, `"ccat"`, and `"workplace_insights"`; proficiency levels reflect assessment scores (e.g., Communication → expert-level based on #1 ranking).

### VAL-SKILL-003: Profile document skill extraction
When profile documents (`profile/README.md`, `profile/capability-digest.md`) are parsed, the system identifies domain and technical skills from narrative descriptions (e.g., "CRM migration" -> Salesforce, Pipedrive; "15+ Python scripts" -> Python automation) and adds them with evidence quotes.
**Evidence:** Skills extracted from profile docs have `source: "profile"` and `evidence` containing a snippet or reference to the originating document paragraph.

### VAL-SKILL-004: Skill categories are correctly assigned
Every skill in the inventory belongs to exactly one of: `technical`, `domain`, `soft`, `tools`. Technical = programming languages, frameworks, architectures. Domain = industry knowledge (e.g., IoT, e-commerce logistics). Soft = interpersonal and cognitive (e.g., Communication, Strategic Thinking). Tools = specific products (e.g., Jira, Confluence, Git).
**Evidence:** GET `/api/skills` returns skills where every entry has a `category` field matching one of the four valid values; no skill has `category: null` or an unrecognized value.

### VAL-SKILL-005: Proficiency levels with evidence
Each skill has a proficiency level (beginner, intermediate, advanced, expert) derived from evidence strength: expert requires multiple high-quality sources (e.g., production experience + years), beginner requires only mention without demonstrated application.
**Evidence:** A skill like "Python" sourced from cv.yaml (15+ scripts) + profile docs (automation suite) is rated `advanced` or `expert`; a skill mentioned once in a JD match with no CV evidence is `beginner`.

### VAL-SKILL-006: Manual skill addition
A user can add a skill via POST `/api/skills` with `name`, `category`, `proficiency`, and optional `evidence`. The skill appears immediately in the inventory and is tagged `source: "manual"`.
**Evidence:** POST `/api/skills` with `{"name": "Rust", "category": "technical", "proficiency": "beginner", "source": "manual"}` → 201; subsequent GET `/api/skills` includes the new entry.

### VAL-SKILL-007: Skill editing
A user can update any field of an existing skill via PUT `/api/skills/{id}`. Changes persist and the `updated_at` timestamp advances.
**Evidence:** PUT `/api/skills/42` with `{"proficiency": "advanced"}` → 200; GET `/api/skills/42` shows `proficiency: "advanced"` and `updated_at` > previous value.

### VAL-SKILL-008: Skills search and filter
GET `/api/skills` supports query parameters: `?q=python` (text search on name), `?category=technical`, `?source=cv.yaml`, `?proficiency=expert`. Filters compose with AND logic. Results are paginated.
**Evidence:** GET `/api/skills?category=technical&q=python` returns only technical skills matching "python"; response includes `total`, `page`, `per_page` fields.

### VAL-SKILL-009: Skills timeline tracking
When a skill's proficiency changes or new evidence is added, the system records a timestamped history entry. GET `/api/skills/{id}/history` returns the progression over time.
**Evidence:** After updating a skill's proficiency from "intermediate" to "advanced", GET `/api/skills/{id}/history` returns ≥ 2 entries with distinct timestamps and proficiency values.

### VAL-SKILL-010: Empty inventory state
When no CV or profile documents have been ingested and no manual skills exist, the skills inventory page shows an empty state with clear calls-to-action: "Import from CV", "Parse assessments", "Add manually".
**Evidence:** With a fresh database, GET `/api/skills` returns `{"items": [], "total": 0}`; the React UI renders the empty state component with three action buttons.

---

## Gap Analysis

### VAL-GAP-001: Per-job gap analysis
Given a job posting's parsed requirements and the user's current skills inventory, GET `/api/applications/{id}/gaps` returns a list of gaps — each with `skill_name`, `required_level`, `current_level` (or null if missing), and `severity` (critical / nice-to-have / bonus).
**Evidence:** For a job requiring "Kubernetes (expert)" where the user has no Kubernetes skill, the response includes `{"skill_name": "Kubernetes", "required_level": "expert", "current_level": null, "severity": "critical"}`.

### VAL-GAP-002: Gap severity classification
Critical gaps are "must-have" requirements the user doesn't meet. Nice-to-have gaps are "preferred" requirements partially met. Bonus gaps are "nice-to-have" requirements in the JD that the user exceeds or doesn't have. The classification derives from the JD's requirement language.
**Evidence:** A JD saying "Required: 5+ years Kubernetes" maps to severity `critical`; "Nice to have: Go experience" maps to `nice-to-have`; "Bonus: Rust" maps to `bonus`.

### VAL-GAP-003: Distance metric
Each gap includes a `distance` field quantifying how far the user is from the requirement: 0 (met), 1 (one proficiency level away), 2 (two levels away), 3 (skill entirely missing). The distance considers both existence and proficiency delta.
**Evidence:** User has Python at "advanced", job requires "expert" → distance 1. User has no Go skill, job requires "intermediate" → distance 3.

### VAL-GAP-004: Readiness score per application
Each application in the pipeline has a computed `readiness_score` (0-100) derived from gap analysis: percentage of required skills met at or above the required proficiency level, weighted by severity (critical gaps weigh 3x, nice-to-have 1x, bonus 0.5x).
**Evidence:** GET `/api/applications/{id}` includes `readiness_score: 72`; the pipeline dashboard UI displays this score as a badge/progress indicator next to the application.

### VAL-GAP-005: Readiness score in pipeline dashboard
The pipeline dashboard (applications list view) displays each application's readiness score inline, color-coded: green (≥ 80), yellow (50-79), red (< 50).
**Evidence:** The React pipeline component renders readiness scores for all applications with correct color coding; applications without gap analysis show a "Run analysis" prompt instead.

### VAL-GAP-006: Aggregate gap analysis
GET `/api/gaps/aggregate` returns a cross-application view: skills that appear as gaps in multiple applications, ranked by frequency and average severity. This identifies the highest-leverage skills to develop.
**Evidence:** If "Kubernetes" is a critical gap in 3 of 5 applications, the aggregate endpoint returns it with `frequency: 3`, `avg_severity: "critical"`, ranked at or near the top.

### VAL-GAP-007: Gap analysis with missing job requirements
When a job posting has been added but its requirements haven't been parsed yet, requesting gap analysis returns a 400 error with a clear message: "Job requirements not yet parsed. Run requirement extraction first."
**Evidence:** GET `/api/applications/{id}/gaps` for an application with no parsed requirements → 400 with `{"detail": "Job requirements not yet parsed..."}`.

---

## Learning Paths

### VAL-LEARN-001: Per-gap learning recommendations
For each identified gap, GET `/api/gaps/{gap_id}/recommendations` returns a list of learning resources categorized as: free courses, paid courses, hands-on projects. Each recommendation includes `title`, `url`, `type`, `estimated_hours`, and `provider`.
**Evidence:** For a "Kubernetes" gap, the response includes at least one free course (e.g., Kubernetes docs tutorial), one paid course (e.g., Udemy/Coursera), and one hands-on project suggestion.

### VAL-LEARN-002: Learning progress tracking
Each learning resource can be marked with a status: `not_started` → `in_progress` → `completed`. POST `/api/learning/{id}/status` with `{"status": "in_progress"}` updates the status and records the transition timestamp.
**Evidence:** After marking a resource as `in_progress`, GET `/api/learning/{id}` shows `status: "in_progress"` and `started_at` timestamp; marking `completed` adds `completed_at`.

### VAL-LEARN-003: Learning progress affects gap distance
When a user completes learning resources associated with a gap, the system recalculates the gap distance and readiness score. Completing a course alone doesn't close the gap, but may reduce distance by 1 level.
**Evidence:** After completing a Kubernetes course, re-running gap analysis shows the Kubernetes gap distance reduced (e.g., from 3 to 2) and the application readiness score increased.

### VAL-LEARN-004: Effort estimates on recommendations
Each learning recommendation includes an AI-generated effort estimate: hours to complete and a difficulty rating (beginner-friendly, intermediate, advanced). These help the user prioritize.
**Evidence:** GET `/api/gaps/{gap_id}/recommendations` returns entries with `estimated_hours: 20` and `difficulty: "intermediate"` fields populated.

### VAL-LEARN-005: Empty learning state
When a gap has no learning recommendations yet (e.g., for a very niche skill), the UI shows "No recommendations available. Add your own resource or request AI suggestions." with an "Add resource" button.
**Evidence:** For a gap on an obscure skill with no seeded recommendations, the UI renders the empty state with the manual-add action.

---

## Career Goals

### VAL-GOAL-001: Define career goals
POST `/api/goals` creates a goal with `title`, `description`, `type` (realistic | aspirational), `target_date`, and `status` (active | achieved | paused | abandoned). Both realistic and aspirational goals are supported.
**Evidence:** POST with `{"title": "Transition to AI Engineer", "type": "aspirational", "target_date": "2027-06-01"}` → 201; GET `/api/goals` includes the new goal.

### VAL-GOAL-002: Goal-to-reality mapping
Each goal has a computed `reality_map` accessible via GET `/api/goals/{id}/reality-map` showing: current state (skills, experience, applications), required state (target skills, experience, credentials), and the delta between them.
**Evidence:** For "Transition to AI Engineer", the reality map shows current Python/ML skills, identifies missing skills (e.g., PyTorch production experience), and lists concrete steps to close each gap.

### VAL-GOAL-003: Progress tracking across dimensions
Goal progress is tracked across three dimensions: applications (relevant roles applied to / interviewed at), learning (relevant courses completed), and portfolio (projects built). GET `/api/goals/{id}/progress` returns percentage progress per dimension.
**Evidence:** GET `/api/goals/{id}/progress` returns `{"applications": 40, "learning": 60, "portfolio": 20, "overall": 40}` with breakdowns showing which applications, courses, and projects contribute.

### VAL-GOAL-004: Goal recalibration
PUT `/api/goals/{id}/recalibrate` triggers an AI-powered reassessment that considers current market data (job posting volumes, salary trends, skill demand) and suggests adjustments to timeline or approach.
**Evidence:** After recalibration, the goal's response includes `recalibration_notes` with market-data-backed suggestions (e.g., "AI Engineer roles in Germany increased 30% — timeline achievable") and an optional suggested `adjusted_target_date`.

### VAL-GOAL-005: Alternative path analysis
GET `/api/goals/{id}/alternatives` returns at least three path options: full-time employment, bootstrap/freelance, and consulting/fractional — each with pros, cons, estimated timeline, and financial projection.
**Evidence:** For "Transition to AI Engineer", the response includes paths like `{"path": "employment", "timeline": "6-12 months", "estimated_comp": "100-140k EUR"}`, `{"path": "freelance", "timeline": "3-6 months", "estimated_comp": "800-1200 EUR/day"}`, and `{"path": "consulting", ...}`.

---

## Coaching

### VAL-COACH-001: AI coaching suggestions
GET `/api/coaching/suggestions` returns prioritized, actionable coaching recommendations based on the user's current skills inventory, active gaps, goal progress, and application pipeline status.
**Evidence:** With 3 applications having Kubernetes gaps and a goal of "AI Engineer transition", suggestions include "Focus on Kubernetes certification — it's blocking 3 applications" with a priority ranking.

### VAL-COACH-002: Coaching effort estimates
Each coaching suggestion includes an `effort_estimate` with `hours`, `weeks`, and `difficulty` fields, helping the user plan their time investment.
**Evidence:** A coaching suggestion like "Complete AWS Solutions Architect certification" includes `{"hours": 80, "weeks": 6, "difficulty": "intermediate"}`.

### VAL-COACH-003: Coaching adapts to progress
When a user completes learning items or achieves goals, the coaching suggestions update to reflect the new state — removing resolved recommendations and surfacing new priorities.
**Evidence:** After completing a Kubernetes course and marking the learning item as `completed`, GET `/api/coaching/suggestions` no longer includes "Learn Kubernetes basics" and instead suggests next-level actions (e.g., "Build a K8s side project for portfolio").

---

## CLI Commands

### VAL-CLI-SKILL-001: List skills via CLI
`career skills list` outputs the full skills inventory in a formatted table with columns: Name, Category, Proficiency, Source. Supports `--category technical` and `--source cv.yaml` filters.
**Evidence:** Running `career skills list --category technical` prints a table containing only technical skills; exit code 0.

### VAL-CLI-SKILL-002: Gap analysis via CLI
`career skills gaps --application <id>` outputs the gap report for a specific application: skill name, required level, current level, severity, distance. Supports `--severity critical` to filter.
**Evidence:** Running `career skills gaps --application 1 --severity critical` prints only critical gaps; exit code 0.

### VAL-CLI-SKILL-003: Career goals via CLI
`career goals` lists all active goals with title, type, target date, and overall progress percentage. `career goals show <id>` displays the full reality map for a specific goal.
**Evidence:** Running `career goals` prints a goals table; `career goals show 1` prints the reality map with current vs. required state; exit code 0.

### VAL-CLI-SKILL-004: Coaching via CLI
`career coach` outputs the top 5 coaching suggestions with effort estimates. `career coach --all` shows the full list.
**Evidence:** Running `career coach` prints 5 prioritized suggestions with effort hours; exit code 0.

### VAL-CLI-SKILL-005: Aggregate gaps via CLI
`career skills gaps --aggregate` outputs the cross-application gap summary: most common missing skills ranked by frequency and severity.
**Evidence:** Running `career skills gaps --aggregate` prints a ranked table of skills appearing as gaps across applications; exit code 0.

---

## Assertion Summary

| Prefix | Count | Coverage |
|--------|-------|----------|
| VAL-SKILL | 10 | Skills inventory: parsing, categories, proficiency, CRUD, search, timeline, empty state |
| VAL-GAP | 7 | Gap analysis: per-job, severity, distance, readiness score, pipeline display, aggregate, error state |
| VAL-LEARN | 5 | Learning: recommendations, progress tracking, score impact, effort estimates, empty state |
| VAL-GOAL | 5 | Goals: CRUD, reality mapping, progress tracking, recalibration, alternative paths |
| VAL-COACH | 3 | Coaching: suggestions, effort estimates, adaptive updates |
| VAL-CLI-SKILL | 5 | CLI: skills list, gaps, goals, coach, aggregate |
| **Total** | **35** | |
