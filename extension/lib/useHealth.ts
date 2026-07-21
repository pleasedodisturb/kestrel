import { useCallback, useEffect, useState } from "react";
import type { ExtResponse, HealthResponse, HealthState } from "@/lib/api/messages";

/**
 * React hook that surfaces the background worker's connection health.
 *
 * It sends `{ type: "HEALTH" }` through `chrome.runtime.sendMessage` on mount and
 * exposes a `refresh()` callback so callers (e.g. after a successful pair) can
 * re-run the check on demand. The hook itself NEVER fetches the backend — the
 * worker owns every network call (locked golden rule).
 */

function isHealthResponse(res: ExtResponse): res is HealthResponse {
  return "state" in res;
}

export interface UseHealthResult {
  /** Latest health state, or `null` while the first check is in flight. */
  readonly state: HealthState | null;
  /** True while a health check is running. */
  readonly loading: boolean;
  /** Re-run the health check on demand. */
  readonly refresh: () => Promise<void>;
}

export function useHealth(): UseHealthResult {
  const [state, setState] = useState<HealthState | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const res = (await chrome.runtime.sendMessage({ type: "HEALTH" })) as ExtResponse;
      setState(isHealthResponse(res) ? res.state : "backend-down");
    } catch {
      setState("backend-down");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { state, loading, refresh };
}
