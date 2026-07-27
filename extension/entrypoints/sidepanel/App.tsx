import { useEffect, useState } from "react";
import { ScorePanel } from "@/components/ScorePanel";
import type { CaptureResponse, PromoteResponse } from "@/lib/api/messages";
import { getLastCapture, onLastCaptureChanged } from "@/lib/storage";

/**
 * sidePanel host — the PRIMARY score/gap surface (01-04 LOCKED decision). It
 * reads the latest capture result from `chrome.storage.session` on mount,
 * subscribes to changes (MV3 worker-restart safe), and mounts the surface-
 * agnostic `ScorePanel`. Add-to-pipeline routes a PROMOTE message through the
 * background worker (the sole backend caller) — the panel never fetches.
 */
export function App() {
  const [result, setResult] = useState<CaptureResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const last = await getLastCapture();
      if (!cancelled && last) {
        setResult(last);
      }
    })();
    const unsubscribe = onLastCaptureChanged((next) => setResult(next));
    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, []);

  async function onPromote(discoveredJobId: number): Promise<void> {
    const res = (await chrome.runtime.sendMessage({
      type: "PROMOTE",
      discoveredJobId,
    })) as PromoteResponse;
    if (!res.ok) {
      throw new Error(res.error ?? "promote-failed");
    }
  }

  if (!result) {
    return (
      <main style={{ padding: 16, fontFamily: "system-ui, sans-serif", color: "#4b5563" }}>
        <h1 style={{ fontSize: 15, margin: "0 0 8px" }}>Kestrel</h1>
        <p style={{ fontSize: 13, margin: 0 }}>
          Capture a job posting to see its Kestrel fit score and gap here.
        </p>
      </main>
    );
  }

  return <ScorePanel result={result} onPromote={onPromote} />;
}
