import { defineBackground } from "#imports";
import * as client from "@/lib/api/client";
import type { ExtMessage, ExtResponse, HealthState } from "@/lib/api/messages";
import { getToken, setLastCapture, setToken } from "@/lib/storage";

/**
 * Background service worker: the extension's networking spine. It owns the typed
 * `chrome.runtime` message API (PAIR / CAPTURE / STATUS / HEALTH) and is the ONLY
 * place backend calls happen — always via `lib/api/client` (never `fetch` here).
 *
 * The worker is STATELESS: MV3 kills it after ~30s idle, so every handler reads
 * fresh from `chrome.storage` rather than caching anything at module scope.
 */

/** Compute the connection health state per the <interfaces> contract. */
async function computeHealth(): Promise<HealthState> {
  const backend = await client.health();
  if (!backend.ok) {
    return "backend-down";
  }
  const token = await getToken();
  if (!token) {
    return "unpaired";
  }
  const result = await client.status();
  if (result.ok) {
    return "connected";
  }
  if (result.status === 401) {
    return "bad-key";
  }
  // Backend answered /health but /status is unreachable — treat as down.
  return "backend-down";
}

/**
 * Route a single message to its handler. Exported (separate from the listener
 * registration) so it is unit-testable without the WXT/MV3 runtime.
 */
export async function handleMessage(message: ExtMessage): Promise<ExtResponse> {
  switch (message.type) {
    case "PAIR": {
      const result = await client.pair(message.pairingCode);
      if (!result.ok) {
        return { ok: false, error: result.error };
      }
      await setToken(result.token);
      return { ok: true, token: result.token, instance: result.instance };
    }
    case "CAPTURE": {
      // Require a stored token BEFORE any network call (never leak an
      // unauthenticated capture attempt to the backend).
      const token = await getToken();
      if (!token) {
        return { ok: false, error: "not-paired" };
      }
      const result = await client.capture(message.payload);
      if (!result.ok) {
        return { ok: false, error: result.error };
      }
      // Pass the score fields through to the caller (popup / content script →
      // the 01-04 panel surface renders them).
      const response: ExtResponse = {
        ok: true,
        jobId: result.jobId,
        // Echo the captured job identity so the auto-log banner can name it
        // (MED-02). The backend response carries no title/company, so take them
        // from the payload the user just captured.
        title: message.payload.title || undefined,
        company: message.payload.company || undefined,
        discoveredJobId: result.discoveredJobId,
        fitScore: result.fitScore,
        letterGrade: result.letterGrade,
        scoreBreakdown: result.scoreBreakdown,
        gap: result.gap,
      };
      // Stash the score in ephemeral session storage so the sidePanel renders it
      // on open (and live-updates via its onChanged subscription). The panel is
      // opened from the user gesture in the listener below, not here.
      await setLastCapture(response);
      return response;
    }
    case "PROMOTE": {
      // Add-to-pipeline: token required before any network call.
      const token = await getToken();
      if (!token) {
        return { ok: false, error: "not-paired" };
      }
      const result = await client.promote(message.discoveredJobId);
      if (!result.ok) {
        return { ok: false, error: result.error };
      }
      return { ok: true, applicationId: result.applicationId, status: result.status };
    }
    case "STATUS": {
      const result = await client.status();
      if (!result.ok) {
        return { ok: false, error: result.error };
      }
      return { ok: true, instance: result.instance };
    }
    case "HEALTH": {
      const state = await computeHealth();
      return { ok: state === "connected", state };
    }
  }
}

/**
 * Open the sidePanel for the tab a CAPTURE originated from. This MUST run
 * SYNCHRONOUSLY at the top of the message listener, BEFORE any `await`: the user
 * gesture that fired the capture (the floating button click) propagates across
 * `sendMessage`, but only if `chrome.sidePanel.open` is called before the event
 * loop yields — otherwise the gesture is consumed and the call throws. If
 * sidePanel is unavailable (older Chrome), we swallow the error; the in-page
 * overlay/inline acknowledgement remains the documented fallback surface.
 */
function openSidePanelForCapture(message: ExtMessage, sender: chrome.runtime.MessageSender): void {
  if (message.type !== "CAPTURE") {
    return;
  }
  const tabId = sender.tab?.id;
  const opener = (chrome as { sidePanel?: { open?: (opts: { tabId: number }) => unknown } })
    .sidePanel?.open;
  if (typeof tabId !== "number" || typeof opener !== "function") {
    return;
  }
  try {
    // Fire-and-forget: opening is best-effort and gesture-tied; the score itself
    // is delivered via chrome.storage.session, read by the panel on load.
    void Promise.resolve(opener({ tabId })).catch(() => {});
  } catch {
    // Gesture already consumed or API unavailable — fall back silently.
  }
}

export default defineBackground(() => {
  chrome.runtime.onMessage.addListener(
    (
      message: ExtMessage,
      sender: chrome.runtime.MessageSender,
      sendResponse: (response: ExtResponse) => void,
    ) => {
      // Gesture-tied side-panel open happens FIRST, synchronously.
      openSidePanelForCapture(message, sender);
      handleMessage(message)
        .then(sendResponse)
        .catch(() => sendResponse({ ok: false, error: "internal-error" }));
      // Keep the message channel open for the async response.
      return true;
    },
  );
});
