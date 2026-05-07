# Desktop App

*Part of the [Kestrel roadmap](../../ROADMAP.md).*

## Goal

Make Kestrel installable without a terminal. This is the most important step from developer tool to real product.

## What This Delivers

Right now, running Kestrel means cloning a repository, configuring environment variables, or setting up Docker. All of those assume comfort with a terminal. The Desktop App milestone changes that entirely. You will download an installer, double-click it, and start scoring jobs. No terminal, no Docker, no configuration files.

The path to get there has two stages. First, a Progressive Web App (PWA) version of the existing web frontend that you can install from your browser and pin to your dock or taskbar. This works today with the existing codebase and gives you an app-like experience while the native version is being built. Second, a full native application with signed installers for macOS and Windows. The native app packages the web frontend with an embedded backend, so everything runs locally from a single application. Your data stays on your machine, just like it does today.

Signed installers matter. On macOS, unsigned applications trigger security warnings that scare users away. An Apple Developer Certificate enables proper code signing and notarization so the installer behaves like any other app you download. Windows code signing serves the same purpose. Auto-updates keep the app current without manual intervention.

## Design Considerations

The biggest decision is which native framework to use. Electron wraps Chromium and has a mature ecosystem (VS Code, Obsidian, Discord all use it), but produces larger binaries (100MB+). Tauri uses the system's built-in web renderer and produces much smaller binaries (10-20MB), but has a younger ecosystem. Both can embed a Python backend process. The choice affects installer size, startup time, system resource usage, and the complexity of packaging Python alongside the frontend.

Embedding the Python backend is the key technical challenge. The native app needs to start a local API server and connect the frontend to it, all invisibly. Users should never see a terminal window or a log file. Data migration from an existing CLI or Docker installation to the desktop app needs a clear, safe path so nobody loses their pipeline or scores.

## Current Status

*Status: Planned -- not yet started*

No implementation exists yet. The BMAD product planning tool is installed and ready to begin the formal product requirements process for this milestone.

## Related Milestones

- **[Web Frontend](web-frontend.md)** -- The desktop app packages the existing web frontend
- **[Hosted Version](hosted-version.md)** -- An alternative deployment path for users who prefer cloud over local
- **[Mobile App](mobile-app.md)** -- Another form factor for accessing Kestrel

---

*For Contributors*

## Open Questions

- Which native framework: Electron (mature ecosystem, larger binary) or Tauri (smaller binary, younger tooling)?
- How should the Python backend be packaged inside the native app? PyInstaller, conda-pack, or a custom approach?
- What is the target installer size? Electron apps typically run 100MB+, Tauri apps 10-20MB. How much does this matter for adoption?
- Auto-update mechanism: Electron has `electron-updater`, Tauri has a built-in updater. What UX should the update flow have (silent, notify, manual)?
- Apple Developer Certificate logistics: annual renewal, notarization pipeline, CI integration for signing builds
- Data migration path: how does a user who installed via pip or Docker move their database and settings to the desktop app?
- Should the PWA interim step be a separate release or bundled into the web frontend as a feature flag?

## Research Needed

No dedicated research documents exist for the desktop app yet. The following existing docs provide relevant context:

- [UX Persona Testing](../research/ux-persona-testing.md) -- Identifies friction points for non-technical users, which directly motivates the desktop app milestone
- [Deployment Guide](../reference/DEPLOY.md) -- Documents current deployment paths (pip, Docker, development server) that the desktop app will replace for end users

The BMAD product planning tool is installed and the output directory is configured at `_bmad-output/planning-artifacts/`. No PRD artifacts have been generated yet. This is the highest-priority PRD to create because the desktop app is the single most important step toward mainstream adoption.

## BMAD Integration

**PRD Status:** Not started (BMAD installed, ready to begin)

A PRD would specify the installation experience from download to first launch, the auto-update mechanism, the platform support matrix (macOS and Windows at minimum, Linux as stretch), the embedded backend packaging strategy, code signing requirements for both platforms, and the data migration path from existing installations. This is the highest-priority PRD to create.

To start a PRD: `/bmad-create-prd` in Claude Code.
See the [planning hierarchy](inventory.md#how-planning-works) for how PRDs connect to implementation.
