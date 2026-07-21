import { useEffect, useState } from "react";
import { getBackendUrl, setBackendUrl } from "@/lib/storage";
import { HealthBadge } from "./HealthBadge";
import { PairingForm } from "./PairingForm";

/**
 * Kestrel extension options page. Composes three pieces:
 *   1. A backend-URL field (persisted via storage; surfaces the non-localhost
 *      `http://` guard error inline).
 *   2. A pairing form that mints + stores the token via the background worker.
 *   3. A health badge reflecting connected / unpaired / backend-down / bad-key.
 * Nothing here fetches the backend directly — all of that flows through the
 * background service worker (locked golden rule).
 */

export function App() {
  const [url, setUrl] = useState<string>("http://localhost:8100");
  const [saved, setSaved] = useState<boolean>(false);
  const [urlError, setUrlError] = useState<string | null>(null);
  const [pairNonce, setPairNonce] = useState<number>(0);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const stored = await getBackendUrl();
      if (!cancelled) {
        setUrl(stored);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSaveUrl(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setSaved(false);
    setUrlError(null);
    try {
      await setBackendUrl(url.trim());
      setSaved(true);
    } catch (err) {
      setUrlError(err instanceof Error ? err.message : "Invalid backend URL.");
    }
  }

  return (
    <main
      style={{
        maxWidth: 520,
        margin: "0 auto",
        padding: 24,
        fontFamily: "system-ui, sans-serif",
        color: "#222",
      }}
    >
      <h1 style={{ fontSize: 20, marginBottom: 4 }}>Kestrel extension</h1>
      <p style={{ fontSize: 13, color: "#666", marginTop: 0 }}>
        Connect this extension to your own self-hosted Kestrel instance.
      </p>

      <section style={{ marginTop: 24 }}>
        <h2 style={{ fontSize: 15, marginBottom: 8 }}>Backend URL</h2>
        <form onSubmit={handleSaveUrl} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ display: "flex", gap: 8 }}>
            <input
              id="backend-url"
              name="backend-url"
              type="text"
              value={url}
              onChange={(event) => {
                setUrl(event.target.value);
                setSaved(false);
              }}
              placeholder="http://localhost:8100"
              style={{ fontSize: 14, padding: "6px 8px", flex: 1 }}
            />
            <button type="submit" style={{ fontSize: 14, padding: "6px 12px" }}>
              Save
            </button>
          </div>
          {saved && (
            <p role="status" style={{ fontSize: 13, color: "#0f5132", margin: 0 }}>
              Backend URL saved.
            </p>
          )}
          {urlError && (
            <p role="alert" style={{ fontSize: 13, color: "#842029", margin: 0 }}>
              {urlError}
            </p>
          )}
        </form>
      </section>

      <section style={{ marginTop: 24 }}>
        <h2 style={{ fontSize: 15, marginBottom: 8 }}>Pair</h2>
        <PairingForm onPaired={() => setPairNonce((n) => n + 1)} />
      </section>

      <section style={{ marginTop: 24 }}>
        <h2 style={{ fontSize: 15, marginBottom: 8 }}>Status</h2>
        <HealthBadge pairNonce={pairNonce} />
      </section>
    </main>
  );
}
