# Milestone 1 — Validation Contract: Core Platform & Pipeline Management

> **Version:** 1.0  
> **Date:** 2026-03-13  
> **Scope:** Project scaffold, data model, CSV/YAML migration, AI provider abstraction, application lifecycle, Kanban UI, follow-up engine, activity log, analytics dashboard, CLI pipeline commands.  
> **Pass criteria:** All assertions below must pass. Any failure blocks M1 sign-off.

---

## Infrastructure & Setup (VAL-INFRA)

### VAL-INFRA-001: FastAPI backend starts on port 8100
`docker compose up` (or local `uvicorn`) starts the FastAPI backend and it responds to `GET /health` on `http://localhost:8100` with a 200 OK JSON payload including `{"status": "ok"}`.  
**Evidence:** `curl -s http://localhost:8100/health | jq .status` returns `"ok"`. No error logs in container stdout.

### VAL-INFRA-002: React frontend starts on port 8101
`docker compose up` (or local `npm start`) serves the React app on `http://localhost:8101`. The root page loads without a blank screen and renders the main navigation shell (sidebar or top-nav with at least "Pipeline", "Analytics", "Settings" links).  
**Evidence:** Open `http://localhost:8101` in a browser; screenshot shows rendered UI shell. DevTools console has zero uncaught errors.

### VAL-INFRA-003: SQLite database is created and accessible
On first startup, the backend creates (or migrates) a SQLite database file at the configured path (e.g., `data/career_os.db`). The file exists and can be opened with `sqlite3` showing the expected tables: `profiles`, `applications`, `activity_log`, `follow_ups` (at minimum).  
**Evidence:** `sqlite3 data/career_os.db ".tables"` lists all expected tables. No migration errors in backend logs.

### VAL-INFRA-004: Typer CLI is installable and responds to --help
Running `career --help` (or `python -m career_os --help`) prints the top-level command group with subcommands including `pipeline`, and exits 0.  
**Evidence:** Terminal output shows help text with `pipeline` subcommand listed. Exit code is 0.

### VAL-INFRA-005: Docker Compose orchestrates full stack
`docker compose up --build` brings up backend, frontend, and any supporting services. All containers reach healthy status within 60 seconds. Frontend can reach backend API (no CORS or network errors in browser console).  
**Evidence:** `docker compose ps` shows all services in "running"/"healthy" state. Frontend makes at least one successful API call (visible in Network tab, 200 response).

### VAL-INFRA-006: Profile (multi-user) data model exists
The database schema supports a `profiles` table with at least: `id`, `name`, `email`, `location`, `created_at`. A default profile is seeded on first run. The API exposes `GET /api/profiles` returning at least the default profile.  
**Evidence:** `curl http://localhost:8100/api/profiles` returns a JSON array with ≥1 profile object containing `id`, `name`, `email` fields.

### VAL-INFRA-007: AI provider abstraction layer responds with mock provider
With `AI_PROVIDER=mock` (or default), calling an AI-powered endpoint (e.g., `POST /api/ai/complete` with a test prompt) returns a deterministic mock response (not an error). Switching to an unconfigured provider returns a clear error message, not a crash.  
**Evidence:** `curl -X POST http://localhost:8100/api/ai/complete -d '{"prompt":"test"}' -H 'Content-Type: application/json'` with mock provider returns 200 with a body containing `"response"` key. With `AI_PROVIDER=nonexistent`, returns 4xx/5xx with an error message mentioning the unsupported provider.

---

## Pipeline Management — Web UI (VAL-PIPE)

### VAL-PIPE-001: Create a new application via web UI
From the Pipeline view, the user clicks "Add Application" (or equivalent). A form appears with fields: company, role, URL, source, salary range, notes, fit score. Submitting the form with valid data creates the application and it appears on the Kanban board in the "Discovered" column.  
**Evidence:** Screenshot of the form pre-submit and post-submit. New card visible in "Discovered" column. Network tab shows POST to `/api/applications` returning 201.

### VAL-PIPE-002: View application detail page
Clicking an application card on the Kanban board opens a detail page (or modal) showing all fields: company, role, URL, source, status, salary range, notes, fit score, created date, last updated date, and the activity log for that application.  
**Evidence:** Screenshot of the detail page with all fields populated. URL includes application ID (e.g., `/applications/42`).

### VAL-PIPE-003: Update application fields
On the detail page, the user edits the salary range and notes fields and saves. The changes persist on page reload. An activity log entry is automatically created recording the field change with timestamp.  
**Evidence:** Edit fields → save → refresh page → fields retain new values. Activity log section shows "salary_range updated" and "notes updated" entries with timestamps.

### VAL-PIPE-004: Move application through status workflow via drag-and-drop
On the Kanban board, the user drags an application card from "Discovered" to "Interested", then from "Interested" to "Applied". After each move, the card appears in the correct column. The backend persists the new status (verified by page reload).  
**Evidence:** Screenshots showing the card in each column after drag. Network tab shows PATCH/PUT to `/api/applications/{id}` with status field. Page reload confirms positions.

### VAL-PIPE-005: Status workflow enforces valid transitions
The allowed status transitions are: `discovered → interested → applied → interviewing → offer → accepted/rejected` and any status can transition to `ghosted`. Attempting an invalid transition (e.g., `discovered → offer` directly) is either prevented in the UI (drag target not available) or returns a 422 validation error from the API.  
**Evidence:** Attempt to drag from "Discovered" directly to "Offer" — either the drop is rejected in the UI, or the API returns a 422 with a message about invalid transition. No silent data corruption.

### VAL-PIPE-006: Delete (archive) an application
The user can archive/delete an application from the detail page. After deletion, the card is no longer visible on the Kanban board. The API confirms deletion. If soft-delete is implemented, the application can be recovered.  
**Evidence:** Click delete/archive → confirm → card disappears from board. `GET /api/applications/{id}` returns 404 (hard delete) or the record with `archived: true` (soft delete).

### VAL-PIPE-007: Kanban board renders all status columns
The Kanban board displays columns for all lifecycle statuses: Discovered, Interested, Applied, Interviewing, Offer, Accepted, Rejected, Ghosted. Empty columns are visible with a placeholder (not hidden). The total card count across all columns matches the total application count.  
**Evidence:** Screenshot of the full board showing all 8 columns. At least one column is empty and shows placeholder text. API `GET /api/applications` count matches sum of visible cards.

### VAL-PIPE-008: Kanban board loads with migrated data
After data migration (VAL-PIPE-015), the Kanban board loads and displays the migrated applications distributed across the correct status columns based on their original CSV status values.  
**Evidence:** Board shows cards in "Interested", "Applied", "Discovery" (mapped to Discovered), and "Outreach" (mapped to the correct column) columns matching the CSV data distribution.

### VAL-PIPE-009: Follow-up reminder creation
On the application detail page, the user can create a follow-up reminder with: due date, reminder type (e.g., "follow-up email", "check status"), and optional notes. The follow-up appears in the application's detail view and in the global follow-ups list.  
**Evidence:** Create follow-up → detail page shows it in a "Follow-ups" section. `GET /api/follow-ups` includes the new entry with `application_id`, `due_date`, `type`, `notes`.

### VAL-PIPE-010: Follow-up due items are surfaced
When a follow-up's due date is today or in the past (and not completed), it appears in a "Due Follow-ups" section/banner on the dashboard or pipeline view. The count of overdue items is visible.  
**Evidence:** Create a follow-up with `due_date` = yesterday. Reload the pipeline view. A banner/badge shows "1 overdue follow-up" (or similar). The follow-up is linked to its application.

### VAL-PIPE-011: Ghost detection alerts
Applications in "Applied" or "Interviewing" status that have had no activity for a configurable number of days (default: 14 for Applied, 7 for Interviewing) are flagged as "possibly ghosted". A visual indicator appears on the Kanban card and/or a ghost detection alert section exists.  
**Evidence:** Insert an application with status "Applied" and `last_activity` = 15 days ago. The Kanban card shows a ghost indicator (icon, border color, or badge). `GET /api/applications?ghost_alert=true` returns it. The configurable threshold is documented or exposed in settings.

### VAL-PIPE-012: Activity log records all state changes
Every status transition, field edit, follow-up creation, and note addition creates an entry in the activity log with: `application_id`, `action`, `old_value`, `new_value`, `timestamp`, `source` (web/cli/migration). The log is visible on the application detail page in reverse chronological order.  
**Evidence:** Perform 3 actions (status change, field edit, note add) on one application. Detail page shows 3 activity log entries in newest-first order with all fields populated.

### VAL-PIPE-013: Application list supports filtering and sorting
The pipeline view (or a list view) supports: filtering by status, filtering by company name (search), sorting by fit score, sorting by date applied, sorting by last updated. At minimum 2 filter and 2 sort options work.  
**Evidence:** Apply status filter "Applied" → only applied applications shown. Sort by fit score descending → highest score first. URL query params or UI controls reflect the active filters.

### VAL-PIPE-014: Empty state handling
When no applications exist (fresh install, before migration), the Kanban board shows a friendly empty state message (e.g., "No applications yet. Add your first one!") with a call-to-action button, not a blank page or error.  
**Evidence:** Screenshot of the board with zero applications showing the empty state message and CTA button. No console errors.

### VAL-PIPE-015: CSV data migration — 42 positions imported correctly
Running the migration command/script imports all rows from `tracking/applications.csv` into the SQLite database. The count of imported applications matches the source CSV row count (42+). Field mapping preserves: company, role, URL, source, status, salary_range, notes, fit_score, date_applied.  
**Evidence:** `sqlite3 data/career_os.db "SELECT COUNT(*) FROM applications"` returns ≥42. Spot-check 3 records (Mistral AI Deployment Strategist fit_score=8.5, Plain Senior Product Engineer fit_score=9.5, Shopware TPM fit_score=8.5) — all fields match CSV values.

### VAL-PIPE-016: YAML application packages migration
If application package data exists in `cv/applications/` (YAML/directory structure for 14 packages), the migration links these to the corresponding application records. Each linked package is accessible from the application detail page.  
**Evidence:** For an application with a package (e.g., `mistral-ai-deployment-strategist`), the detail page shows a "Package" or "Materials" section with the linked cover letter and tailored CV reference. `GET /api/applications/{id}` includes a `package` or `materials` field.

### VAL-PIPE-017: Profile creation and management
The user can create a new profile via the web UI (Settings or Profile page) with name, email, location, and optional fields. The profile can be edited after creation. All applications are associated with a profile ID.  
**Evidence:** Create profile → edit profile → verify changes persist. `GET /api/applications` results include `profile_id` matching the active profile.

### VAL-PIPE-018: Validation errors on invalid input
Submitting a new application with missing required fields (e.g., empty company name) returns a validation error displayed in the UI (inline error message or toast). The form is not submitted. The API returns 422 with field-level error details.  
**Evidence:** Submit form with empty "Company" field → red error message appears on the field or as a toast. Network tab shows 422 response with `{"detail": [{"field": "company", "message": "..."}]}` structure.

---

## Analytics (VAL-ANALYTICS)

### VAL-ANALYTICS-001: Conversion funnel visualization
The Analytics dashboard displays a funnel chart (or equivalent) showing the count of applications at each stage: Discovered → Interested → Applied → Interviewing → Offer → Accepted. The numbers are correct based on current data. Percentages between stages are displayed.  
**Evidence:** Screenshot of funnel chart. With migrated data: verify Discovered count + Interested count + Applied count matches the CSV data distribution. Conversion percentage (e.g., "Applied / Interested = X%") is shown.

### VAL-ANALYTICS-002: Response rate metric
The analytics page shows a "Response Rate" metric: the percentage of applications in "Applied" status (or later) that progressed to "Interviewing" or beyond. The calculation is: `(count(interviewing+offer+accepted) / count(applied+interviewing+offer+accepted+rejected+ghosted)) * 100`. With zero applied applications, shows "N/A" or "0%" (not NaN or error).  
**Evidence:** Metric is visible on the dashboard. Manual calculation from the database matches displayed value. With empty data: shows graceful fallback, no NaN/Infinity.

### VAL-ANALYTICS-003: Time-in-stage metrics
The analytics page shows average time spent in each status stage (in days). Calculated from activity log timestamps for status transitions. Stages with no data show "—" or "No data" (not 0 or error).  
**Evidence:** Dashboard shows time-in-stage for at least Applied and Interviewing stages. If data exists, the value is a positive number of days. If no transitions exist for a stage, it shows a graceful fallback.

### VAL-ANALYTICS-004: Applications over time chart
A time-series chart shows the number of new applications added per week (or day/month, selectable). The X-axis is time, Y-axis is count. The chart renders correctly with migrated data and updates when new applications are added.  
**Evidence:** Screenshot of time-series chart. With migrated data (most entries dated 2026-02-23 and 2026-03-03), the chart shows two spikes at those dates. Adding a new application shifts the current period bar/point up by 1.

### VAL-ANALYTICS-005: Fit score distribution
The analytics page shows a histogram or distribution chart of fit scores across all applications. Scores cluster around 6-9 based on the existing data. The chart handles applications with no fit score gracefully (excluded or shown as "unscored").  
**Evidence:** Screenshot of score distribution chart. The distribution shape matches the CSV data (peak around 7-8.5). Hover/tooltip shows the count per score bucket.

### VAL-ANALYTICS-006: Analytics with empty data
Loading the analytics page with zero applications shows placeholder messages or empty-state charts (e.g., "Add applications to see analytics") instead of broken charts, NaN values, or JavaScript errors.  
**Evidence:** Clear all applications (or use fresh DB). Load analytics page. Screenshot shows friendly empty states. Browser console has zero errors.

---

## CLI Pipeline Commands (VAL-CLI-PIPE)

### VAL-CLI-PIPE-001: `career pipeline list` shows all applications
Running `career pipeline list` prints a table of all applications with columns: ID, Company, Role, Status, Fit Score, Date Applied. The output is sorted by date (newest first) by default. With migrated data, shows 42+ rows.  
**Evidence:** Terminal output showing the table. Row count matches database. Columns are aligned and readable.

### VAL-CLI-PIPE-002: `career pipeline list --status applied` filters by status
Running `career pipeline list --status applied` shows only applications with status "applied". The count matches the number of applied applications in the database.  
**Evidence:** Terminal output filtered to "applied" only. Cross-check with `sqlite3 data/career_os.db "SELECT COUNT(*) FROM applications WHERE status='applied'"`.

### VAL-CLI-PIPE-003: `career pipeline add` creates a new application
Running `career pipeline add --company "TestCorp" --role "Engineer" --url "https://example.com" --source "manual"` creates a new application in "discovered" status. The CLI confirms creation with the new application ID. The application appears in the web UI Kanban board.  
**Evidence:** CLI output shows "Application created: ID=XX". `career pipeline list` shows the new entry. Web UI Kanban board shows the card in "Discovered" column after refresh.

### VAL-CLI-PIPE-004: `career pipeline update` changes application fields
Running `career pipeline update <id> --status interested --notes "Great fit"` updates the application's status and notes. The change is reflected in both `career pipeline list` and the web UI.  
**Evidence:** CLI output confirms update. `career pipeline list` shows new status. Web UI detail page shows updated notes and status. Activity log records the CLI-initiated change with `source=cli`.

### VAL-CLI-PIPE-005: `career pipeline stats` shows summary statistics
Running `career pipeline stats` prints a summary including: total applications, count per status, average fit score, top companies by application count, and date range of applications.  
**Evidence:** Terminal output showing all summary fields. Numbers match database aggregates.

### VAL-CLI-PIPE-006: `career pipeline follow-ups` lists due follow-ups
Running `career pipeline follow-ups` (or `career follow-ups`) lists all follow-ups due today or overdue, with: application company/role, due date, type, and days overdue. With no due follow-ups, prints "No follow-ups due. You're all caught up!".  
**Evidence:** With an overdue follow-up in the system, the CLI output shows it with correct days-overdue count. With none due, shows the friendly message.

### VAL-CLI-PIPE-007: CLI error handling for invalid input
Running `career pipeline add` without required arguments prints a clear usage error message with the required fields listed (not a Python traceback). Running `career pipeline update 99999 --status applied` with a nonexistent ID prints "Application not found" (not a crash).  
**Evidence:** Terminal output for both error cases shows user-friendly messages. Exit codes are non-zero. No Python tracebacks visible.

### VAL-CLI-PIPE-008: CLI and web UI share the same database
An application created via CLI (`career pipeline add`) is immediately visible in the web UI (after page refresh). An application created via web UI is immediately visible via CLI (`career pipeline list`). Both use the same SQLite database file.  
**Evidence:** Create via CLI → verify in web UI. Create via web UI → verify in CLI. Both reference the same `data/career_os.db` file.

---

## Cross-Cutting Concerns

### VAL-PIPE-019: Timestamps use consistent timezone handling
All timestamps in the database, API responses, and UI display use UTC internally. The UI can display in the user's local timezone (Europe/Berlin for the primary user). Activity log entries created seconds apart show correct chronological ordering.  
**Evidence:** Create two activity log entries in rapid succession. `sqlite3` query shows UTC timestamps. API returns ISO 8601 format with `Z` or `+00:00` suffix. UI displays in local time if timezone setting exists.

### VAL-PIPE-020: API documentation is auto-generated
The FastAPI backend serves Swagger/OpenAPI docs at `/docs` (or `/api/docs`). All application CRUD endpoints, follow-up endpoints, analytics endpoints, and profile endpoints are documented with request/response schemas.  
**Evidence:** Open `http://localhost:8100/docs` in browser. Screenshot shows all endpoint groups. At least `GET/POST/PATCH/DELETE /api/applications` are listed with schemas.

---

*Total assertions: 34*  
*Breakdown: VAL-INFRA: 7 | VAL-PIPE: 20 | VAL-ANALYTICS: 6 | VAL-CLI-PIPE: 8*
