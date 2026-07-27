import { defineConfig } from "wxt";

// WXT + React 19, Manifest V3 (WXT's default target).
// Locked Phase-0/1 decisions: narrow permissions only, and NEVER a broad-host or
// wildcard permission. The background service worker is the sole backend caller;
// the paired backend is reachable via localhost host_permissions only. No
// telemetry ships here.
//
// The in-page floating trigger runs from the content script (entrypoints/content.ts),
// whose EXPLICIT ATS `matches` allowlist (LinkedIn jobs / Greenhouse / Lever /
// Ashby) WXT auto-registers into manifest content_scripts — no host_permissions
// widening needed. The popup "Capture this job" path uses `activeTab` (granted by
// the toolbar click) to message that content script; it never fetches the backend.
//
// The score/gap surface is the MV3 `sidePanel` (01-04): WXT auto-detects the
// `entrypoints/sidepanel/` entrypoint and registers `side_panel.default_path`.
// `sidePanel` is the ONLY new permission — it grants a companion panel, NOT any
// host access. A `chrome.sidePanel.open()` from a user-gesture message opens it.
// The auto-log content script (entrypoints/autolog.content.ts) adds its own
// EXPLICIT ATS application-host `matches` allowlist — again, no wildcard host.
export default defineConfig({
  modules: ["@wxt-dev/module-react"],
  manifest: {
    name: "Kestrel",
    description:
      "Companion for your self-hosted Kestrel job search. Captures job posts to your own paired instance. No telemetry and no broad host access.",
    // activeTab + storage + sidePanel only. Recognized job hosts are reached via
    // the content-script `matches` allowlist, never a wildcard host permission;
    // sidePanel is a companion-UI grant, not host access.
    permissions: ["activeTab", "storage", "sidePanel"],
    // The paired Kestrel backend only. Remote hosts are added in later phases as
    // explicit entries; Phase 0/1 talk to localhost exclusively.
    host_permissions: ["http://localhost/*", "http://127.0.0.1/*"],
  },
});
