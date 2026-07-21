import { useEffect } from "react";
import type { HealthState } from "@/lib/api/messages";
import { useHealth } from "@/lib/useHealth";

/**
 * Connection-health badge. It is driven by `useHealth()`, which sends a
 * `{ type: "HEALTH" }` message to the background worker — the badge never touches
 * the backend directly. Each `HealthState` maps to a human label + color. When
 * `pairNonce` changes (a successful pair bumps it), the badge re-runs the HEALTH
 * check so it flips to `connected`.
 */

interface Descriptor {
  readonly label: string;
  readonly color: string;
  readonly background: string;
}

const STATE_DESCRIPTOR: Record<HealthState, Descriptor> = {
  connected: {
    label: "Connected to Kestrel",
    color: "#0f5132",
    background: "#d1e7dd",
  },
  unpaired: {
    label: "Not paired yet",
    color: "#41464b",
    background: "#e2e3e5",
  },
  "backend-down": {
    label: "Kestrel not running — start it with `uvicorn career_os.main:app --port 8100`",
    color: "#842029",
    background: "#f8d7da",
  },
  "bad-key": {
    label: "Pairing expired — pair again",
    color: "#664d03",
    background: "#fff3cd",
  },
};

export interface HealthBadgeProps {
  /** Bumped by the parent after a successful pair to force a re-check. */
  readonly pairNonce: number;
}

export function HealthBadge({ pairNonce }: HealthBadgeProps) {
  const { state, loading, refresh } = useHealth();

  useEffect(() => {
    if (pairNonce > 0) {
      void refresh();
    }
  }, [pairNonce, refresh]);

  const descriptor = state ? STATE_DESCRIPTOR[state] : null;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <span
        role="status"
        style={{
          display: "inline-block",
          padding: "4px 10px",
          borderRadius: 6,
          fontSize: 13,
          color: descriptor?.color ?? "#41464b",
          background: descriptor?.background ?? "#e2e3e5",
        }}
      >
        {descriptor ? descriptor.label : "Checking connection…"}
      </span>
      <button
        type="button"
        onClick={() => {
          void refresh();
        }}
        disabled={loading}
        style={{ fontSize: 12, padding: "2px 8px", cursor: loading ? "default" : "pointer" }}
      >
        Recheck
      </button>
    </div>
  );
}
