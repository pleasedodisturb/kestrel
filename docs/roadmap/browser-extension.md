# Browser Extension

*Part of the [Kestrel roadmap](../../ROADMAP.md).*

## Goal

Add any job from any website to your scoring queue with one click.

## What This Delivers

Kestrel's built-in discovery engine scans major job boards automatically, but it cannot reach every posting. Some jobs appear on company career pages, niche boards, or platforms the scrapers do not cover. The browser extension fills that gap. When you find a job posting anywhere on the web, you click a button and it goes straight into your Kestrel pipeline for scoring.

The extension targets Chrome and Firefox (Manifest V3, built with WXT + React 19). It reads the page you are on, extracts the relevant job details (title, company, description, location), and sends them to your local Kestrel instance. You keep browsing. Behind the scenes, the job enters your scoring queue and gets evaluated like any other discovered position.

## Design Considerations

Chrome's Manifest V3 standard defines how modern extensions work, and it places restrictions on background processing that affect how the extension communicates with a local server. The extension needs to parse job posting content from pages with wildly different HTML structures. Some sites use structured markup that makes extraction straightforward. Others render everything dynamically, requiring content scripts that wait for the page to finish loading before attempting extraction.

The extension communicates with a Kestrel instance running on your machine. This raises authentication questions: how does the extension prove it is talking to your Kestrel and not someone else's? A locally generated token exchanged during setup is the likely approach, but the details need design work. For times when Kestrel is not running (laptop closed, server stopped), the extension should queue saved jobs and sync them when the connection is restored.

## Current Status

*Status: Built and tested in-repo (`extension/`) -- not yet published to the Chrome Web Store / Firefox Add-ons.*

The extension is implemented with WXT + React 19 on Manifest V3. Shipped entrypoints: a background service worker, page content scripts, an auto-log content script, a popup, a side panel, and an options page. Authentication is handled by a pairing flow (`PairingForm`) that exchanges a locally generated token with your Kestrel instance, and a `HealthBadge` surfaces backend connectivity. A `ScorePanel` shows the fit/desire score inline. The suite runs under Vitest (`extension/__tests__/`: extraction, autolog, background, options, score panel).

What remains before a public release: store submission (Chrome Web Store + Firefox Add-ons review), and the offline queue-and-sync behavior for when Kestrel is not running.

## Related Milestones

- **[Discovery Engine](discovery-engine.md)** -- The extension extends job discovery beyond the built-in scrapers
- **[Desktop App](desktop-app.md)** -- The extension communicates with a local Kestrel instance, which the desktop app makes easier to run

---

*For Contributors*

Resolved during implementation:

- **Authentication** -- a locally generated token exchanged during setup (`PairingForm`), as anticipated. Backend connectivity is surfaced by `HealthBadge`.
- **Quick preview** -- the extension shows the fit/desire score inline (`ScorePanel`), not just a one-click save.

Still open:

- How should the extension detect job posting content on pages with no standard markup? Heuristic-based extraction versus site-specific parsers remains a live trade-off as coverage grows
- How should offline queuing work when Kestrel is not running? Local storage with automatic sync on reconnect (not yet built)
- Chrome Web Store and Firefox Add-ons have different review processes and content policies. What submission requirements need to be met before publishing?
- Should the extension support multiple Kestrel instances (e.g., work laptop and personal desktop)?

## Research Needed

- [Job Search Tools](../research/job-search-tools.md) -- Survey of scrapers, MCP servers, and discovery sources. Useful context for understanding what the built-in discovery covers and where the extension fills gaps

No dedicated extension research exists yet. Research areas include: Manifest V3 background service worker limitations, content script injection patterns for dynamic pages, local server communication from browser extensions, and Chrome Web Store review timelines.

## BMAD Integration

**PRD Status:** Superseded by implementation for the core flow (extraction, pairing, scoring). A focused PRD would still help for the remaining pre-release scope: the supported-site list and extraction rules as coverage expands, store submission requirements, and the offline job-queuing strategy.

To start a PRD: `/bmad-create-prd` in Claude Code.
See the [planning hierarchy](inventory.md#how-planning-works) for how PRDs connect to implementation.
