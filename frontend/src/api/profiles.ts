/**
 * API client functions for profile management.
 */

export interface ProfileResponse {
  id: number;
  name: string;
  email: string | null;
  location: string | null;
  job_family: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProfileListResponse {
  profiles: ProfileResponse[];
  count: number;
}

export interface ProfileCreate {
  name: string;
  email?: string;
  location?: string;
  job_family?: string;
}

export interface ProfileUpdate {
  name?: string;
  email?: string;
  location?: string;
  job_family?: string;
}

const API_BASE = "/api/profiles";

/** Fetch all profiles. */
export async function fetchProfiles(): Promise<ProfileListResponse> {
  const res = await fetch(API_BASE);
  if (!res.ok) {
    throw new Error(`Failed to fetch profiles: ${res.status}`);
  }
  return res.json() as Promise<ProfileListResponse>;
}

/** Fetch a single profile by ID. */
export async function fetchProfile(id: number): Promise<ProfileResponse> {
  const res = await fetch(`${API_BASE}/${id}`);
  if (!res.ok) {
    if (res.status === 404) throw new Error("Profile not found");
    throw new Error(`Failed to fetch profile: ${res.status}`);
  }
  return res.json() as Promise<ProfileResponse>;
}

/** Create a new profile. */
export async function createProfile(
  data: ProfileCreate,
): Promise<ProfileResponse> {
  const res = await fetch(API_BASE, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Failed to create profile: ${res.status}`,
    );
  }
  return res.json() as Promise<ProfileResponse>;
}

/** Update an existing profile (partial). */
export async function updateProfile(
  id: number,
  data: ProfileUpdate,
): Promise<ProfileResponse> {
  const res = await fetch(`${API_BASE}/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Failed to update profile: ${res.status}`,
    );
  }
  return res.json() as Promise<ProfileResponse>;
}

/** Delete a profile. */
export async function deleteProfile(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Failed to delete profile: ${res.status}`,
    );
  }
}
