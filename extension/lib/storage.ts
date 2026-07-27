/**
 * Thin, testable typed wrapper over `chrome.storage` for the values the
 * extension persists: the backend URL + paired token (durable `local`), and the
 * latest capture result (ephemeral `session`, so the sidePanel survives an MV3
 * worker restart and reads the score on mount).
 *
 * Security (T-00-10): reject a non-localhost `http://` backend URL. `http://` is
 * permitted ONLY for localhost/127.0.0.1; every other host must be `https://`.
 */

import type { CaptureResponse } from "@/lib/api/messages";

const KEY_BACKEND_URL = "backendUrl";
const KEY_TOKEN = "extensionToken";
const KEY_LAST_CAPTURE = "lastCapture";
const DEFAULT_BACKEND_URL = "http://localhost:8100";

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

/** Throw if `url` is not a safe backend origin. */
export function assertValidBackendUrl(url: string): void {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    throw new Error(`Invalid backend URL: ${url}`);
  }
  if (parsed.protocol === "https:") {
    return;
  }
  if (parsed.protocol === "http:" && LOCAL_HOSTS.has(parsed.hostname)) {
    return;
  }
  throw new Error(
    `Insecure backend URL: ${url} — http:// is only allowed for localhost, use https:// for remote hosts`,
  );
}

export async function getBackendUrl(): Promise<string> {
  const result = await chrome.storage.local.get(KEY_BACKEND_URL);
  const value = result[KEY_BACKEND_URL] as string | undefined;
  return value ?? DEFAULT_BACKEND_URL;
}

export async function setBackendUrl(url: string): Promise<void> {
  assertValidBackendUrl(url);
  await chrome.storage.local.set({ [KEY_BACKEND_URL]: url });
}

export async function getToken(): Promise<string | null> {
  const result = await chrome.storage.local.get(KEY_TOKEN);
  const value = result[KEY_TOKEN] as string | null | undefined;
  return value ?? null;
}

export async function setToken(token: string | null): Promise<void> {
  await chrome.storage.local.set({ [KEY_TOKEN]: token });
}

// ---------------------------------------------------------------------------
// Latest capture result — ephemeral session storage (cleared when the browser
// closes). The background CAPTURE handler writes it; the sidePanel reads it on
// mount and subscribes to changes so a fresh capture updates the panel live and
// an MV3 worker restart never loses the last score.
// ---------------------------------------------------------------------------

export async function getLastCapture(): Promise<CaptureResponse | null> {
  const result = await chrome.storage.session.get(KEY_LAST_CAPTURE);
  return (result[KEY_LAST_CAPTURE] as CaptureResponse | undefined) ?? null;
}

export async function setLastCapture(result: CaptureResponse): Promise<void> {
  await chrome.storage.session.set({ [KEY_LAST_CAPTURE]: result });
}

/** Read the last captured `discoveredJobId` (used by auto-log's promote path). */
export async function getLastDiscoveredJobId(): Promise<number | undefined> {
  const last = await getLastCapture();
  return typeof last?.discoveredJobId === "number" ? last.discoveredJobId : undefined;
}

/**
 * Subscribe to session `lastCapture` changes; returns an unsubscribe fn. Guarded
 * so it is a no-op when `chrome.storage.session.onChanged` is unavailable.
 */
export function onLastCaptureChanged(callback: (result: CaptureResponse) => void): () => void {
  const events = chrome.storage.session.onChanged;
  if (!events) {
    return () => {};
  }
  const listener = (changes: Record<string, chrome.storage.StorageChange>): void => {
    const change = changes[KEY_LAST_CAPTURE];
    if (change && change.newValue !== undefined) {
      callback(change.newValue as CaptureResponse);
    }
  };
  events.addListener(listener);
  return () => events.removeListener(listener);
}
