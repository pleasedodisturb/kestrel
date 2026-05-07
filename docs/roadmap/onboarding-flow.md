# Onboarding Flow

*Part of the [Kestrel roadmap](../../ROADMAP.md).*

## Goal

Get new users from installation to their first scored job in minutes.

## What This Delivers

When you open Kestrel for the first time, a six-step wizard walks you through setup. You create your profile, set your job preferences, pick an AI provider (or stay in free demo mode), configure your search parameters, and trigger your first discovery run. By the end, you have scored jobs in your pipeline and a clear picture of how Kestrel works.

The wizard is not a wall between you and the application. Each step explains what it does and why, so you understand the choices you are making. If you want to skip a step and come back to it later, you can. Nothing is locked behind completing the full flow.

Demo mode is the default starting point. No API key needed. The mock provider returns realistic-looking scores generated locally so you can explore the entire pipeline without any setup beyond the basic profile. When you are ready for real AI scoring, you add a provider key in settings and everything switches over.

The onboarding flow was designed around a specific goal: two minutes from opening the app to seeing your first scored job. Whether you reach that target depends on how much you customize during setup, but the critical path is short enough that most users see results quickly.

## How It Works

The onboarding wizard is a frontend component that checks whether the current profile has completed setup. If not, it presents the steps in sequence. Each step collects the minimum information needed to proceed, stores it via the backend API, and advances to the next. The backend onboarding service tracks which steps have been completed so the wizard can resume where you left off if you close the browser.

On the backend, the onboarding state is tied to the profile. First-run data seeding creates a default profile on startup, and the wizard fills in the details.

## Current Status

*Shipped in [v0.11.0](../../CHANGELOG.md#0110-2026-04-21)*

The six-step wizard is fully functional. Demo mode provides a complete experience without any API key. The onboarding was shipped as part of a larger epic (G-392) covering six development phases with 361 tests.

## Related Milestones

- **[Web Frontend](web-frontend.md)** -- Onboarding is the first experience in the web interface
- **[AI Provider System](ai-provider-system.md)** -- Onboarding includes provider setup and demo mode

---

*For Contributors*

## Architecture

The onboarding flow spans frontend and backend:

- `frontend/src/components/OnboardingWizard.tsx` -- React component implementing the step-by-step wizard. Checks profile completion status and renders the appropriate step.
- `frontend/src/pages/` -- The wizard integrates with the main application layout. Users can navigate away from onboarding and return to it.

Backend support:

- `src/career_os/services/` -- Onboarding-related service functions handle profile creation, preference storage, provider configuration, and search profile setup.
- `src/career_os/migration/seed.py` -- Default profile seeding on first startup, providing the base record that onboarding fills in.
- `src/career_os/api/` -- Profile and settings endpoints that the wizard calls during each step.

The onboarding state is implicit in the profile data. If required fields (preferences, search parameters) are not set, the frontend shows the wizard. Once everything is filled in, the wizard does not appear again unless the user resets their profile.

## Research & Decisions

Annotated links to research and reference documents:

- [UX Persona Testing](../research/ux-persona-testing.md) -- Persona testing of the onboarding experience for non-technical users, identifying where setup friction occurs
- [M1 Validation Contract](../reference/M1-validation-contract.md) -- Validation contract covering first-run experience, profile creation, and initial discovery trigger
- [Deployment Guide](../reference/DEPLOY.md) -- Deployment options affecting the onboarding experience (Docker, pip install, development setup)

## BMAD Integration

**PRD Status:** Not started

A PRD would specify the step-by-step UX flows with wireframes, progressive disclosure rules, skip and revisit patterns, and success metrics for first-run completion rate.

To start a PRD: `/bmad-create-prd` in Claude Code.
See the [planning hierarchy](inventory.md#how-planning-works) for how PRDs connect to implementation.
