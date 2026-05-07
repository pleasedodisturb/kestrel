# Web Frontend

*Part of the [Kestrel roadmap](../../ROADMAP.md).*

## Goal

See and manage your entire job search from a browser.

## What This Delivers

Kestrel's web interface gives you eleven pages covering every part of your job search. The pipeline page shows your Kanban board with drag-and-drop cards. Discovery lets you browse and filter newly found jobs. Analytics shows scoring distributions, application velocity, and pipeline health. Contacts tracks the people you are talking to. Skills maps your professional profile. Interview prep helps you rehearse. Settings configures your providers, presets, and integrations.

The interface is responsive and works on screens of different sizes. Data loads efficiently through a caching layer that keeps things fast even when your pipeline has hundreds of entries. When you update something, the interface refreshes the affected data automatically without reloading the page.

The onboarding wizard guides new users through initial setup on their first visit. Once you have completed setup, the pipeline page becomes your home base. Every page connects back to the same underlying data, so a job you discover on the Discovery page appears on your Kanban board after you mark it as Interesting.

## How It Works

The frontend is a single-page application built with React 19. React Router handles navigation between pages. TanStack React Query manages all data fetching and caching with a five-minute stale time and automatic cache invalidation on mutations. The backend serves a REST API, and the frontend consumes it through typed API client functions that wrap `fetch()` calls.

In development, Vite proxies API requests to the backend on port 8100. In production, the backend serves both the API and the compiled frontend as static files from a single port.

## Current Status

*Shipped in [v0.11.0](../../CHANGELOG.md#0110-2026-04-21)*

All eleven pages are functional: Pipeline, Application Detail, Analytics, Discovery, Contacts, Skills, Goals, Interview Prep, Star Stories, Settings, and Onboarding. The frontend has 22 test files covering components and API clients. Some pre-existing TypeScript type errors remain (tracked separately), and the type-check step is disabled in CI pending resolution.

## Related Milestones

- **[Application Pipeline](application-pipeline.md)** -- Kanban board visualizes the pipeline
- **[Desktop App](desktop-app.md)** -- Desktop app packages the web frontend
- **[Mobile App](mobile-app.md)** -- Mobile app provides the same interface on phones

---

*For Contributors*

## Architecture

The frontend lives in `frontend/src/` with the following structure:

- `frontend/src/pages/` -- Eleven page components, one per route. Each page is a self-contained view using hooks and API clients.
- `frontend/src/api/` -- Sixteen typed API client modules. Each exports async functions for one domain (applications, scoring, discovery, contacts, etc.). Functions return typed Promises.
- `frontend/src/components/` -- Twenty-plus reusable components including `KanbanBoard.tsx`, `Layout.tsx` (app shell with navigation), `OnboardingWizard.tsx`, dialogs, badges, and charts.
- `frontend/src/hooks/` -- Custom React hooks wrapping TanStack Query for domain-specific data fetching.
- `frontend/src/lib/` -- Utility functions (grade calculation, formatting, styling helpers).
- `frontend/src/__tests__/` -- Twenty-two Vitest test files for components and API clients.

Key technology choices: React 19 for the UI framework, Vite 8 for bundling and dev server, Tailwind CSS 4.2 for styling (via `@tailwindcss/vite` plugin), TanStack React Query 5.90 for data fetching, React Router DOM 7.13 for navigation, Recharts 3.8 for data visualization, and `@dnd-kit` for drag-and-drop on the Kanban board.

The `@/*` path alias maps to `frontend/src/` in both TypeScript config and Vite config for clean imports.

## Research & Decisions

Annotated links to research and reference documents:

- [UX Persona Testing](../research/ux-persona-testing.md) -- Persona-based UX testing identifying friction points across all eleven pages for non-technical users
- [Mobile UX Findings](../research/mobile-ux-findings.md) -- UX findings from mobile exploration that inform responsive web design decisions
- [M1 Validation Contract](../reference/M1-validation-contract.md) -- Validation contract covering Kanban UI, analytics dashboard, and frontend component assertions

## BMAD Integration

**PRD Status:** Not started

A PRD would specify page-level UX interaction flows, accessibility requirements (WCAG 2.1 targets), responsive breakpoint behavior, and component design system rules.

To start a PRD: `/bmad-create-prd` in Claude Code.
See the [planning hierarchy](inventory.md#how-planning-works) for how PRDs connect to implementation.
