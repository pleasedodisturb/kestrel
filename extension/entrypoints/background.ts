import { defineBackground } from "#imports";
import * as client from "@/lib/api/client";
import type { ExtMessage, ExtResponse, HealthState } from "@/lib/api/messages";
import { getToken, setToken } from "@/lib/storage";

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
      return {
        ok: true,
        jobId: result.jobId,
        discoveredJobId: result.discoveredJobId,
        fitScore: result.fitScore,
        letterGrade: result.letterGrade,
        scoreBreakdown: result.scoreBreakdown,
        gap: result.gap,
      };
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

export default defineBackground(() => {
  chrome.runtime.onMessage.addListener(
    (message: ExtMessage, _sender, sendResponse: (response: ExtResponse) => void) => {
      handleMessage(message)
        .then(sendResponse)
        .catch(() => sendResponse({ ok: false, error: "internal-error" }));
      // Keep the message channel open for the async response.
      return true;
    },
  );
});
