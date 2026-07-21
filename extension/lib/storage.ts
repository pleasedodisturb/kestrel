/**
 * Thin, testable typed wrapper over `chrome.storage.local` for the two values
 * the extension persists: the backend URL and the paired extension token.
 *
 * Security (T-00-10): reject a non-localhost `http://` backend URL. `http://` is
 * permitted ONLY for localhost/127.0.0.1; every other host must be `https://`.
 */

const KEY_BACKEND_URL = "backendUrl";
const KEY_TOKEN = "extensionToken";
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
