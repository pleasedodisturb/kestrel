/**
 * API client functions for the analytics dashboard.
 */

import { DEFAULT_PROFILE_ID } from "./applications";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface FunnelStage {
  stage: string;
  count: number;
  percentage: number;
}

export interface TimeInStage {
  stage: string;
  avg_days: number | null;
}

export interface WeeklyCount {
  week: string;
  count: number;
}

export interface ScoreBucket {
  range: string;
  count: number;
}

export interface PrepMetrics {
  total_sessions: number;
  completed_sessions: number;
  completion_rate: number | null;
  total_items: number;
  completed_items: number;
}

export interface NotificationMetrics {
  total_sent: number;
  total_failed: number;
  total_queued: number;
  by_category: Record<string, number>;
}

export interface AnalyticsData {
  conversion_funnel: FunnelStage[];
  response_rate: number | null;
  time_in_stage: TimeInStage[];
  applications_over_time: WeeklyCount[];
  score_distribution: ScoreBucket[];
  prep_metrics?: PrepMetrics;
  notification_metrics?: NotificationMetrics;
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

/**
 * Fetch analytics data for the default profile.
 */
export async function fetchAnalytics(): Promise<AnalyticsData> {
  const res = await fetch(
    `/api/analytics?profile_id=${DEFAULT_PROFILE_ID}`,
  );
  if (!res.ok) {
    throw new Error(`Failed to fetch analytics: ${res.status}`);
  }
  return res.json() as Promise<AnalyticsData>;
}
