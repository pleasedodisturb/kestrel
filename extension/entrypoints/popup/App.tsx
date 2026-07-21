import { useEffect, useState } from "react";
import type { ExtResponse, HealthResponse, HealthState } from "@/lib/api/messages";

// One-line, human-readable label per health state. The popup proves the
// React+WXT build and the background message round-trip only — it issues NO
// backend request itself and hosts NO pairing UI (that lives on the options
// page in 00-03).
const STATE_LABEL: Record<HealthState, string> = {
  connected: "Connected to your Kestrel instance.",
  unpaired: "Not paired yet — open Options to pair.",
  "backend-down": "Kestrel instance unreachable.",
  "bad-key": "Pairing expired — re-pair in Options.",
};

function isHealthResponse(res: ExtResponse): res is HealthResponse {
  return "state" in res;
}

export function App() {
  const [status, setStatus] = useState<string>("Checking connection…");

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = (await chrome.runtime.sendMessage({ type: "HEALTH" })) as ExtResponse;
        if (cancelled) {
          return;
        }
        setStatus(isHealthResponse(res) ? STATE_LABEL[res.state] : "Unknown status.");
      } catch {
        if (!cancelled) {
          setStatus("Extension worker unavailable.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main style={{ width: 280, padding: 16, fontFamily: "system-ui, sans-serif" }}>
      <h1 style={{ fontSize: 16, margin: "0 0 8px" }}>Kestrel</h1>
      <p style={{ fontSize: 13, margin: 0, color: "#444" }}>{status}</p>
    </main>
  );
}
