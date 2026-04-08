/**
 * API client functions for follow-ups.
 */

import type {
  FollowUp,
  FollowUpCreate,
  FollowUpListResponse,
  OverdueCountResponse,
} from "./types";

import { DEFAULT_PROFILE_ID } from "./applications";

const API_BASE = "/api/follow-ups";

/**
 * Create a new follow-up.
 */
export async function createFollowUp(data: Omit<FollowUpCreate, "profile_id">): Promise<FollowUp> {
  const res = await fetch(API_BASE, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...data, profile_id: DEFAULT_PROFILE_ID }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Failed to create follow-up: ${res.status}`,
    );
  }
  return res.json() as Promise<FollowUp>;
}

/**
 * Fetch all follow-ups for the default profile.
 * Optionally filter to overdue only.
 */
export async function fetchFollowUps(params?: {
  overdue?: boolean;
}): Promise<FollowUpListResponse> {
  const searchParams = new URLSearchParams({
    profile_id: String(DEFAULT_PROFILE_ID),
  });
  if (params?.overdue) searchParams.set("overdue", "true");

  const res = await fetch(`${API_BASE}?${searchParams.toString()}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch follow-ups: ${res.status}`);
  }
  return res.json() as Promise<FollowUpListResponse>;
}

/**
 * Complete a follow-up.
 */
export async function completeFollowUp(id: number): Promise<FollowUp> {
  const res = await fetch(
    `${API_BASE}/${id}?profile_id=${DEFAULT_PROFILE_ID}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ completed: true }),
    },
  );
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Failed to complete follow-up: ${res.status}`,
    );
  }
  return res.json() as Promise<FollowUp>;
}

/**
 * Get the count of overdue follow-ups.
 */
export async function fetchOverdueCount(): Promise<OverdueCountResponse> {
  const res = await fetch(
    `${API_BASE}/overdue-count?profile_id=${DEFAULT_PROFILE_ID}`,
  );
  if (!res.ok) {
    throw new Error(`Failed to fetch overdue count: ${res.status}`);
  }
  return res.json() as Promise<OverdueCountResponse>;
}
