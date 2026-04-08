/**
 * API client functions for the applications pipeline.
 */

import type {
  Application,
  ApplicationCreate,
  ApplicationDetailResponse,
  ApplicationListResponse,
  ApplicationUpdate,
} from "./types";

const API_BASE = "/api/applications";

/** Default profile ID used for all requests. */
export const DEFAULT_PROFILE_ID = 1;

/**
 * Fetch all (non-archived) applications for the default profile.
 * Supports optional filter/sort params.
 */
export async function fetchApplications(params?: {
  status?: string;
  search?: string;
  sort?: string;
  order?: string;
}): Promise<ApplicationListResponse> {
  const searchParams = new URLSearchParams({
    profile_id: String(DEFAULT_PROFILE_ID),
  });
  if (params?.status) searchParams.set("status", params.status);
  if (params?.search) searchParams.set("search", params.search);
  if (params?.sort) searchParams.set("sort", params.sort);
  if (params?.order) searchParams.set("order", params.order);

  const url = `${API_BASE}?${searchParams.toString()}`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to fetch applications: ${res.status}`);
  }
  return res.json() as Promise<ApplicationListResponse>;
}

/**
 * Fetch a single application detail (including activity log).
 */
export async function fetchApplicationDetail(
  id: number,
): Promise<ApplicationDetailResponse> {
  const res = await fetch(
    `${API_BASE}/${id}?profile_id=${DEFAULT_PROFILE_ID}`,
  );
  if (!res.ok) {
    if (res.status === 404) {
      throw new Error("Application not found");
    }
    throw new Error(`Failed to fetch application: ${res.status}`);
  }
  return res.json() as Promise<ApplicationDetailResponse>;
}

/**
 * Create a new application.
 */
export async function createApplication(
  data: ApplicationCreate,
): Promise<Application> {
  const res = await fetch(API_BASE, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...data, profile_id: DEFAULT_PROFILE_ID }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Failed to create application: ${res.status}`,
    );
  }
  return res.json() as Promise<Application>;
}

/**
 * Update an application (partial update via PATCH).
 */
export async function updateApplication(
  id: number,
  data: ApplicationUpdate,
): Promise<Application> {
  const res = await fetch(
    `${API_BASE}/${id}?profile_id=${DEFAULT_PROFILE_ID}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Failed to update application: ${res.status}`,
    );
  }
  return res.json() as Promise<Application>;
}

/**
 * Archive (soft-delete) an application.
 */
export async function archiveApplication(id: number): Promise<Application> {
  const res = await fetch(
    `${API_BASE}/${id}?profile_id=${DEFAULT_PROFILE_ID}`,
    {
      method: "DELETE",
    },
  );
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Failed to archive application: ${res.status}`,
    );
  }
  return res.json() as Promise<Application>;
}
