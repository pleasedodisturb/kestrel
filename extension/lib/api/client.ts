/**
 * The ONLY module that talks to the Kestrel backend (locked "golden rule": all
 * extension→backend calls originate in the background service worker, which
 * calls exclusively through here).
 *
 * Every request is cookie-less (`credentials: "omit"` — the token travels in an
 * `Authorization: Bearer` header, never cookies, matching the backend's
 * credential-less CORS) and wrapped in a short `AbortController` timeout so a
 * dead backend maps to a distinct "network" outcome the worker reports as
 * `backend-down`.
 */

import type { CapturePayload, InstanceInfo } from "@/lib/api/messages";
import { getBackendUrl, getToken } from "@/lib/storage";

const TIMEOUT_MS = 1500;

type FetchResult = { kind: "response"; response: Response } | { kind: "network" };

export type PairOutcome =
  | { ok: true; token: string; instance: InstanceInfo }
  | { ok: false; error: string };

export type CaptureOutcome =
  | {
      ok: true;
      jobId: string;
      discoveredJobId?: number;
      fitScore?: number;
      letterGrade?: string;
      scoreBreakdown?: unknown[];
      gap?: string;
    }
  | { ok: false; error: string };

export type PromoteOutcome =
  | { ok: true; applicationId?: number; status?: string }
  | { ok: false; error: string };

export type StatusOutcome =
  | { ok: true; instance: InstanceInfo }
  | { ok: false; status: number | null; error: string };

export interface HealthOutcome {
  ok: boolean;
}

async function request(url: string, init: RequestInit): Promise<FetchResult> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(url, {
      ...init,
      credentials: "omit",
      signal: controller.signal,
    });
    return { kind: "response", response };
  } catch {
    return { kind: "network" };
  } finally {
    clearTimeout(timer);
  }
}

export async function pair(pairingCode: string): Promise<PairOutcome> {
  const base = await getBackendUrl();
  const result = await request(`${base}/api/extension/pair`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pairing_code: pairingCode }),
  });
  if (result.kind === "network") {
    return { ok: false, error: "backend-unreachable" };
  }
  if (!result.response.ok) {
    return { ok: false, error: "Invalid or expired pairing code" };
  }
  const data = (await result.response.json()) as { token: string; instance: InstanceInfo };
  return { ok: true, token: data.token, instance: data.instance };
}

export async function capture(payload: CapturePayload): Promise<CaptureOutcome> {
  const base = await getBackendUrl();
  const token = await getToken();
  const result = await request(`${base}/api/extension/capture`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token ?? ""}`,
    },
    body: JSON.stringify(payload),
  });
  if (result.kind === "network") {
    return { ok: false, error: "backend-unreachable" };
  }
  if (result.response.status === 401) {
    return { ok: false, error: "bad-key" };
  }
  if (!result.response.ok) {
    return { ok: false, error: "capture-failed" };
  }
  const data = (await result.response.json()) as {
    job_id: string;
    discovered_job_id?: number;
    fit_score?: number;
    letter_grade?: string;
    score_breakdown?: unknown[] | null;
    gap?: string;
  };
  return {
    ok: true,
    jobId: data.job_id,
    discoveredJobId: data.discovered_job_id,
    fitScore: data.fit_score,
    letterGrade: data.letter_grade,
    // score_breakdown may be null when the provider returns none (01-02) —
    // normalize to undefined so the panel can treat "missing" uniformly.
    scoreBreakdown: data.score_breakdown ?? undefined,
    gap: data.gap,
  };
}

export async function promote(discoveredJobId: number): Promise<PromoteOutcome> {
  const base = await getBackendUrl();
  const token = await getToken();
  const result = await request(`${base}/api/extension/promote`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token ?? ""}`,
    },
    body: JSON.stringify({ discovered_job_id: discoveredJobId }),
  });
  if (result.kind === "network") {
    return { ok: false, error: "backend-unreachable" };
  }
  if (result.response.status === 401) {
    return { ok: false, error: "bad-key" };
  }
  if (!result.response.ok) {
    return { ok: false, error: "promote-failed" };
  }
  const data = (await result.response.json()) as {
    application_id?: number;
    status?: string;
  };
  return { ok: true, applicationId: data.application_id, status: data.status };
}

export async function status(): Promise<StatusOutcome> {
  const base = await getBackendUrl();
  const token = await getToken();
  const result = await request(`${base}/api/extension/status`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token ?? ""}` },
  });
  if (result.kind === "network") {
    return { ok: false, status: null, error: "backend-unreachable" };
  }
  if (result.response.status === 401) {
    return { ok: false, status: 401, error: "bad-key" };
  }
  if (!result.response.ok) {
    return { ok: false, status: result.response.status, error: "status-failed" };
  }
  const data = (await result.response.json()) as { instance: InstanceInfo };
  return { ok: true, instance: data.instance };
}

export async function health(): Promise<HealthOutcome> {
  const base = await getBackendUrl();
  const result = await request(`${base}/health`, { method: "GET" });
  if (result.kind === "network") {
    return { ok: false };
  }
  return { ok: result.response.ok };
}
