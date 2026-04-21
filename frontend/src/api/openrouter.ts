/**
 * API client for OpenRouter OAuth onboarding.
 *
 * Uses the existing /api/auth/openrouter/* endpoints which implement
 * PKCE with server-side state management and rate limiting.
 */

export interface OAuthStartResponse {
  auth_url: string;
  state: string;
}

export interface OAuthStatusResponse {
  connected: boolean;
  provider: string;
}

export interface CreditsResponse {
  total_credits: number;
  total_usage: number;
  balance: number;
  needs_deposit: boolean;
}

/** Start the OAuth PKCE flow — returns auth URL and state token. */
export async function startOAuth(): Promise<OAuthStartResponse> {
  const res = await fetch("/api/auth/openrouter/start");
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `OAuth start failed: ${res.status}`,
    );
  }
  return res.json() as Promise<OAuthStartResponse>;
}

/** Check OpenRouter connection status. */
export async function fetchStatus(): Promise<OAuthStatusResponse> {
  const res = await fetch("/api/auth/openrouter/status");
  if (!res.ok) {
    return { connected: false, provider: "openrouter" };
  }
  return res.json() as Promise<OAuthStatusResponse>;
}

/** Check OpenRouter credit balance. */
export async function fetchCredits(): Promise<CreditsResponse> {
  const res = await fetch("/api/auth/openrouter/credits");
  if (!res.ok) {
    if (res.status === 404)
      return {
        total_credits: 0,
        total_usage: 0,
        balance: 0,
        needs_deposit: true,
      };
    throw new Error(`Credits check failed: ${res.status}`);
  }
  return res.json() as Promise<CreditsResponse>;
}
