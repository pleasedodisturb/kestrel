/**
 * API client functions for onboarding status.
 */

/** Default profile ID (single-user self-hosted model). */
export const DEFAULT_PROFILE_ID = 1;

export interface OnboardingStatus {
  profile_id: number;
  current_step: string | null;
  next_step: string | null;
  is_complete: boolean;
  progress_pct: number;
  profile_started_at: string | null;
  profile_completed_at: string | null;
  demo_seeded_at: string | null;
  welcome_completed_at: string | null;
  tour_completed_at: string | null;
  feedback_prompted_at: string | null;
  completed_at: string | null;
  profile_started_via: string | null;
  profile_completed_via: string | null;
  demo_seeded_via: string | null;
  welcome_completed_via: string | null;
  tour_completed_via: string | null;
  feedback_prompted_via: string | null;
  completed_via: string | null;
  created_at: string | null;
  updated_at: string | null;
}

const API_BASE = "/api/onboarding";

/** Fetch onboarding status for a profile. */
export async function fetchOnboardingStatus(
  profileId: number,
): Promise<OnboardingStatus> {
  const res = await fetch(`${API_BASE}/status?profile_id=${profileId}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch onboarding status: ${res.status}`);
  }
  return res.json() as Promise<OnboardingStatus>;
}

/** Mark an onboarding step complete. */
export async function patchOnboardingStep(
  profileId: number,
  step: string,
): Promise<OnboardingStatus> {
  const res = await fetch(`${API_BASE}/status?profile_id=${profileId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ step, via: "web" }),
  });
  if (!res.ok) {
    throw new Error(`Failed to update onboarding step: ${res.status}`);
  }
  return res.json() as Promise<OnboardingStatus>;
}

/** Reset the onboarding flow (keeps profile data, restarts welcome/tour). */
export async function resetOnboarding(
  profileId: number,
): Promise<OnboardingStatus> {
  const res = await fetch(`${API_BASE}/reset?profile_id=${profileId}`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error(`Failed to reset onboarding: ${res.status}`);
  }
  return res.json() as Promise<OnboardingStatus>;
}
