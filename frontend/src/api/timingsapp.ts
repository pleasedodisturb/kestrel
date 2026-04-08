/**
 * API client functions for TimingsApp integration.
 */

import { DEFAULT_PROFILE_ID } from "./applications";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface TimeSession {
  id: number;
  profile_id: number;
  activity_name: string;
  category: string;
  notes: string | null;
  started_at: string;
  stopped_at: string | null;
  duration_seconds: number | null;
  timingsapp_entry_id: string | null;
  timingsapp_project: string | null;
  created_at: string;
  updated_at: string;
}

export interface TimeSessionListResponse {
  sessions: TimeSession[];
  total: number;
}

export interface CategoryBreakdown {
  category: string;
  total_hours: number;
  percentage: number;
  session_count: number;
}

export interface WeeklyTrend {
  week: string;
  total_hours: number;
  category_hours: Record<string, number>;
}

export interface TimeAnalyticsData {
  total_hours: number;
  total_sessions: number;
  category_breakdown: CategoryBreakdown[];
  weekly_trend: WeeklyTrend[];
  avg_daily_hours: number;
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

/**
 * Fetch time analytics for the default profile.
 */
export async function fetchTimeAnalytics(
  weeks = 4,
): Promise<TimeAnalyticsData> {
  const res = await fetch(
    `/api/timingsapp/analytics?profile_id=${DEFAULT_PROFILE_ID}&weeks=${weeks}`,
  );
  if (!res.ok) {
    throw new Error(`Failed to fetch time analytics: ${res.status}`);
  }
  return res.json() as Promise<TimeAnalyticsData>;
}

/**
 * Start a new tracked time session.
 */
export async function startTimeSession(data: {
  activity_name: string;
  category?: string;
  notes?: string;
}): Promise<TimeSession> {
  const res = await fetch("/api/timingsapp/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      profile_id: DEFAULT_PROFILE_ID,
      ...data,
    }),
  });
  if (!res.ok) {
    throw new Error(`Failed to start session: ${res.status}`);
  }
  return res.json() as Promise<TimeSession>;
}

/**
 * Stop a tracked time session.
 */
export async function stopTimeSession(
  sessionId: number,
  notes?: string,
): Promise<TimeSession> {
  const res = await fetch(
    `/api/timingsapp/sessions/${sessionId}/stop?profile_id=${DEFAULT_PROFILE_ID}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notes: notes || null }),
    },
  );
  if (!res.ok) {
    throw new Error(`Failed to stop session: ${res.status}`);
  }
  return res.json() as Promise<TimeSession>;
}

/**
 * Get the currently running session (or null).
 */
export async function fetchRunningSession(): Promise<TimeSession | null> {
  const res = await fetch(
    `/api/timingsapp/sessions/running?profile_id=${DEFAULT_PROFILE_ID}`,
  );
  if (!res.ok) {
    throw new Error(`Failed to fetch running session: ${res.status}`);
  }
  return res.json() as Promise<TimeSession | null>;
}

/**
 * List tracked time sessions.
 */
export async function fetchTimeSessions(params?: {
  category?: string;
  limit?: number;
  offset?: number;
}): Promise<TimeSessionListResponse> {
  const query = new URLSearchParams({
    profile_id: String(DEFAULT_PROFILE_ID),
  });
  if (params?.category) query.set("category", params.category);
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.offset) query.set("offset", String(params.offset));

  const res = await fetch(`/api/timingsapp/sessions?${query}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch sessions: ${res.status}`);
  }
  return res.json() as Promise<TimeSessionListResponse>;
}
