import { defineConfig } from "wxt";

// WXT + React 19, Manifest V3 (WXT's default target).
// Locked Phase-0 decisions: narrow permissions only, and NEVER a broad-host /
// wildcard permission. The background service worker is the sole backend caller;
// the paired backend is reachable via localhost host_permissions only. No
// telemetry ships here.
export default defineConfig({
  modules: ["@wxt-dev/module-react"],
  manifest: {
    name: "Kestrel",
    description:
      "Companion for your self-hosted Kestrel job search. Captures job posts to your own paired instance. No telemetry and no broad host access.",
    // Nothing beyond activeTab + storage. Later phases add EXPLICIT ATS domains,
    // never a wildcard host.
    permissions: ["activeTab", "storage"],
    // The paired Kestrel backend only. Remote hosts are added in later phases as
    // explicit entries; Phase 0 talks to localhost exclusively.
    host_permissions: ["http://localhost/*", "http://127.0.0.1/*"],
  },
});
