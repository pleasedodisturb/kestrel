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
export default defineConfig({
  modules: ["@wxt-dev/module-react"],
  manifest: {
    name: "Kestrel",
    description:
      "Companion for your self-hosted Kestrel job search. Captures job posts to your own paired instance. No telemetry and no broad host access.",
    // Nothing beyond activeTab + storage. Recognized job hosts are reached via
    // the content-script `matches` allowlist, never a wildcard host permission.
    permissions: ["activeTab", "storage"],
    // The paired Kestrel backend only. Remote hosts are added in later phases as
    // explicit entries; Phase 0/1 talk to localhost exclusively.
    host_permissions: ["http://localhost/*", "http://127.0.0.1/*"],
  },
});
