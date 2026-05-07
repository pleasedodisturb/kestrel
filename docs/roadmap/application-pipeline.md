# Application Pipeline

*Part of the [Kestrel roadmap](../../ROADMAP.md).*

## Goal

Track every application from first discovery to final outcome in one place.

## What This Delivers

Your job search pipeline is a Kanban board. Jobs move through stages: Discovered, Interested, Applied, Interviewing, Offer, Accepted, Rejected, and Ghosted. You drag a card from one column to the next as your application progresses. The board shows you where everything stands at a glance, replacing the spreadsheet most job seekers end up maintaining.

Status transitions are enforced. You cannot jump from Discovered straight to Offer. The pipeline only allows moves that make sense, so your data stays clean even when you are moving fast. If you try an invalid transition, Kestrel tells you why and suggests the correct path.

Follow-up reminders keep you from losing track of applications. When you mark a job as Applied, you can set a follow-up date. Kestrel reminds you when it is time to check in. Activity logging records every status change, note, and interaction so you have a full history when you need to remember what happened with a particular application.

Each application links back to the scored job that started it. You can always see the original scoring breakdown, the red flags that were flagged, and the job description that caught your attention. The pipeline is the central place where discovery, scoring, and your own decisions come together.

## How It Works

The pipeline is a state machine defined in the schema layer. A dictionary of valid transitions maps each status to the statuses it can move to. When you update an application's status, the service layer checks this dictionary before allowing the change. Invalid transitions raise an error that the API translates to an HTTP 422 response.

Activity logging creates a record for every status change. Follow-ups are stored with due dates and linked to the application they belong to. The Kanban board on the frontend reads all applications and groups them by status for the column layout.

## Current Status

*Shipped in [v0.2.0](../../CHANGELOG.md#020-2026-04-12)*

The pipeline is fully functional with Kanban board, status enforcement, follow-up reminders, and activity logging. The state machine handles all standard job search workflows. The Application Pipeline was the first major feature shipped and has been stable since v0.2.

## Related Milestones

- **[Scoring Engine](scoring-engine.md)** -- Scored jobs become pipeline applications
- **[Web Frontend](web-frontend.md)** -- Kanban board is the primary pipeline interface

---

*For Contributors*

## Architecture

The pipeline follows the standard layered pattern:

- `src/career_os/schemas/applications.py` -- `ApplicationStatus` enum (StrEnum) and `VALID_TRANSITIONS` dictionary. This is where the state machine lives. Business rules for what moves are legal are defined here, not in the service layer.
- `src/career_os/services/applications.py` -- CRUD operations plus state transition enforcement. Functions accept `db: Session` and raise `ApplicationNotFoundError` or `InvalidStatusTransitionError` for invalid operations.
- `src/career_os/models/models.py` -- `Application`, `FollowUp`, and `ActivityLog` ORM models. Applications have a `profile_id` foreign key for multi-profile isolation.
- `src/career_os/api/applications.py` -- REST endpoints for pipeline CRUD, status updates, follow-up management. Catches domain exceptions and maps to HTTP status codes.

The frontend Kanban board lives in `frontend/src/components/KanbanBoard.tsx` with drag-and-drop powered by `@dnd-kit`. The pipeline page at `frontend/src/pages/Pipeline.tsx` wraps the board with filtering and sorting controls.

The `_get_active_application()` helper in the service layer uses keyword-only arguments for clarity, including an optional `profile_id` parameter for cross-profile access control.

## Research & Decisions

Annotated links to research and reference documents:

- [M1 Validation Contract](../reference/M1-validation-contract.md) -- Milestone 1 validation contract covering core platform, pipeline management, Kanban UI, and follow-up engine
- [UX Persona Testing](../research/ux-persona-testing.md) -- Persona-based journey analysis identifying friction points in pipeline workflows
- [Technical Reference](../reference/REFERENCE.md) -- Technical reference including API documentation and pipeline endpoint specifications

## BMAD Integration

**PRD Status:** Not started

A PRD would cover pipeline analytics requirements, status transition validation rules, notification trigger configuration, and the follow-up scheduling algorithm.

To start a PRD: `/bmad-create-prd` in Claude Code.
See the [planning hierarchy](inventory.md#how-planning-works) for how PRDs connect to implementation.
