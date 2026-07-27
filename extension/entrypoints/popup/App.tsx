import { useEffect, useState } from "react";
import type {
  CaptureResponse,
  ExtResponse,
  HealthResponse,
  HealthState,
} from "@/lib/api/messages";

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

/** Result line for a capture attempt; the panel surface (01-04) renders detail. */
function captureLabel(res: CaptureResponse): string {
  if (!res.ok) {
    if (res.error === "unsupported-page") {
      return "Open a supported job posting (LinkedIn / Greenhouse / Lever / Ashby) to capture.";
    }
    if (res.error === "not-paired") {
      return "Not paired — open Options to pair first.";
    }
    return "Capture failed. Try again.";
  }
  if (res.fitScore != null && res.letterGrade) {
    return `Captured ✓ — fit ${res.letterGrade} (${res.fitScore}). Added to Kestrel.`;
  }
  return "Captured ✓ — added to Kestrel.";
}

/**
 * Capture the active tab WITHOUT any broad host access: we use `activeTab` (the
 * click on the toolbar action grants it) to message the content script running
 * on the viewed page, which extracts + captures through the worker. The popup
 * never fetches the backend directly.
 */
async function captureActiveTab(): Promise<CaptureResponse> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) {
    return { ok: false, error: "unsupported-page" };
  }
  try {
    return (await chrome.tabs.sendMessage(tab.id, { type: "CAPTURE_ACTIVE_TAB" })) as CaptureResponse;
  } catch {
    // No content script here → not a recognized job page.
    return { ok: false, error: "unsupported-page" };
  }
}

export function App() {
  const [status, setStatus] = useState<string>("Checking connection…");
  const [capturing, setCapturing] = useState(false);
  const [captureResult, setCaptureResult] = useState<string>("");

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

  async function onCapture() {
    setCapturing(true);
    setCaptureResult("");
    try {
      const res = await captureActiveTab();
      setCaptureResult(captureLabel(res));
    } catch {
      setCaptureResult("Capture failed. Try again.");
    } finally {
      setCapturing(false);
    }
  }

  return (
    <main style={{ width: 280, padding: 16, fontFamily: "system-ui, sans-serif" }}>
      <h1 style={{ fontSize: 16, margin: "0 0 8px" }}>Kestrel</h1>
      <p style={{ fontSize: 13, margin: "0 0 12px", color: "#444" }}>{status}</p>
      <button
        type="button"
        onClick={onCapture}
        disabled={capturing}
        style={{
          width: "100%",
          padding: "9px 12px",
          fontSize: 13,
          fontWeight: 600,
          border: 0,
          borderRadius: 8,
          background: capturing ? "#9ca3af" : "#1f2937",
          color: "#fff",
          cursor: capturing ? "default" : "pointer",
        }}
      >
        {capturing ? "Capturing…" : "Capture this job"}
      </button>
      {captureResult && (
        <p style={{ fontSize: 12, margin: "10px 0 0", color: "#374151" }}>{captureResult}</p>
      )}
    </main>
  );
}
