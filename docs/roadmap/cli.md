# CLI

*Part of the [Kestrel roadmap](../../ROADMAP.md).*

## Goal

Access your pipeline and scores from the terminal when you prefer working that way.

## What This Delivers

The `kestrel` command gives you terminal access to the same data and operations available in the web interface. You can manage your pipeline, review skills, set goals, prepare for interviews, and manage contacts without opening a browser.

Five subcommand groups organize the functionality: `pipeline` for application management, `skills` for skill tracking and analysis, `goals` for career goal management, `interview-prep` for rehearsal and preparation, and `contacts` for professional network management. Output is formatted with color and structure using Rich, so tables and lists are readable even in a dense terminal session.

The CLI connects directly to the same database and service layer as the web frontend. Changes you make in the terminal appear immediately in the browser, and vice versa. There is no synchronization step or separate data store.

For users who run Kestrel on a server or inside Docker, the CLI provides an alternative interface when a browser is not convenient. It also works well for scripting and automation, since each command returns structured output that can be piped to other tools.

## How It Works

The CLI is built on Typer, which generates help text and argument parsing from Python type annotations. Each subcommand group maps to a domain in the service layer. When you run `kestrel pipeline list`, the CLI calls the same `list_applications()` function that the web API calls. The database session is created directly rather than going through the HTTP layer.

Two entry points are registered in `pyproject.toml`: `kestrel` (primary) and `career` (alias). Both point to the same Typer application.

## Current Status

*Shipped in [v0.3.0](../../CHANGELOG.md#030-2026-04-13)*

All five subcommand groups are functional. The CLI shares the full service layer with the API, so every backend feature is accessible from the terminal. The main CLI file (`main.py`) is 2,272 lines, with only the contacts subcommand split into its own module so far.

## Related Milestones

- **[Application Pipeline](application-pipeline.md)** -- Terminal access to pipeline operations
- **[Scoring Engine](scoring-engine.md)** -- CLI can trigger scoring and display results in the terminal

---

*For Contributors*

## Architecture

The CLI lives in `src/career_os/cli/` with the following structure:

- `src/career_os/cli/main.py` (2,272 lines) -- Main Typer application with all subcommand groups except contacts. This is a known decomposition target (similar to the scoring service monolith).
- `src/career_os/cli/contacts.py` (443 lines) -- Contacts subcommand group, split out as the first extraction.
- `src/career_os/cli/warn.py` -- WARN Act data lookup subcommand (optional, requires `warn-scraper` extra).

Entry points in `pyproject.toml`:
```
[project.scripts]
kestrel = "career_os.cli.main:app"
career = "career_os.cli.main:app"
```

The CLI uses Typer for argument parsing and Rich for output formatting. It creates its own database session via `SessionLocal()` rather than using FastAPI's dependency injection, since it runs outside the web server context.

## Research & Decisions

Annotated links to research and reference documents:

- [M1 Validation Contract](../reference/M1-validation-contract.md) -- CLI validation assertions for pipeline commands and expected output formats
- [Technical Reference](../reference/REFERENCE.md) -- Technical reference including CLI command documentation and API endpoint specifications
- [Deployment Guide](../reference/DEPLOY.md) -- Deployment options including CLI-based server management and Docker entry points

## BMAD Integration

**PRD Status:** Not started

A PRD would define the command taxonomy and naming conventions, output format standards for scripting, shell completion generation, and the CLI-to-API parity matrix.

To start a PRD: `/bmad-create-prd` in Claude Code.
See the [planning hierarchy](inventory.md#how-planning-works) for how PRDs connect to implementation.
