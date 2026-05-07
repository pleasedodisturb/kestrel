# Browser Extension

*Part of the [Kestrel roadmap](../../ROADMAP.md).*

## Goal

Add any job from any website to your scoring queue with one click.

## What This Delivers

Kestrel's built-in discovery engine scans major job boards automatically, but it cannot reach every posting. Some jobs appear on company career pages, niche boards, or platforms the scrapers do not cover. The browser extension fills that gap. When you find a job posting anywhere on the web, you click a button and it goes straight into your Kestrel pipeline for scoring.

The extension will be available for Chrome and Firefox. It reads the page you are on, extracts the relevant job details (title, company, description, location), and sends them to your local Kestrel instance. You keep browsing. Behind the scenes, the job enters your scoring queue and gets evaluated like any other discovered position.

## Design Considerations

Chrome's Manifest V3 standard defines how modern extensions work, and it places restrictions on background processing that affect how the extension communicates with a local server. The extension needs to parse job posting content from pages with wildly different HTML structures. Some sites use structured markup that makes extraction straightforward. Others render everything dynamically, requiring content scripts that wait for the page to finish loading before attempting extraction.

The extension communicates with a Kestrel instance running on your machine. This raises authentication questions: how does the extension prove it is talking to your Kestrel and not someone else's? A locally generated token exchanged during setup is the likely approach, but the details need design work. For times when Kestrel is not running (laptop closed, server stopped), the extension should queue saved jobs and sync them when the connection is restored.

## Current Status

*Status: Planned -- not yet started*

No implementation exists. The extension depends on a stable API surface from the backend, which is available today.

## Related Milestones

- **[Discovery Engine](discovery-engine.md)** -- The extension extends job discovery beyond the built-in scrapers
- **[Desktop App](desktop-app.md)** -- The extension communicates with a local Kestrel instance, which the desktop app makes easier to run

---

*For Contributors*

## Open Questions

- How should the extension detect job posting content on pages with no standard markup? Heuristic-based extraction versus site-specific parsers is a core design choice
- What authentication mechanism should the extension use to connect to the local Kestrel backend? A shared secret generated during setup, or something more formal?
- Should the extension support a "quick preview" of the score before adding to the pipeline, or just a one-click save?
- How should offline queuing work when Kestrel is not running? Local storage with automatic sync on reconnect?
- Chrome Web Store and Firefox Add-ons have different review processes and content policies. What submission requirements need to be met?
- Should the extension support multiple Kestrel instances (e.g., work laptop and personal desktop)?

## Research Needed

- [Job Search Tools](../research/job-search-tools.md) -- Survey of scrapers, MCP servers, and discovery sources. Useful context for understanding what the built-in discovery covers and where the extension fills gaps

No dedicated extension research exists yet. Research areas include: Manifest V3 background service worker limitations, content script injection patterns for dynamic pages, local server communication from browser extensions, and Chrome Web Store review timelines.

## BMAD Integration

**PRD Status:** Not started

A PRD would define the supported site list and content extraction rules, the extension-to-backend communication protocol, Chrome Web Store and Firefox Add-ons submission requirements, and the offline job queuing strategy.

To start a PRD: `/bmad-create-prd` in Claude Code.
See the [planning hierarchy](inventory.md#how-planning-works) for how PRDs connect to implementation.
