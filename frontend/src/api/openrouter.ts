/**
 * API client for OpenRouter OAuth onboarding.
 */

export interface OAuthStartResponse {
  auth_url: string;
  code_verifier: string;
}

export interface OAuthCallbackResponse {
  success: boolean;
  message: string;
  has_credits: boolean;
  balance: number;
}

export interface CreditsResponse {
  total_credits: number;
  total_usage: number;
  balance: number;
  needs_deposit: boolean;
}

/** Start the OAuth PKCE flow — returns auth URL and code verifier. */
export async function startOAuth(
  callbackUrl: string,
): Promise<OAuthStartResponse> {
  const res = await fetch("/api/openrouter/oauth/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ callback_url: callbackUrl }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `OAuth start failed: ${res.status}`,
    );
  }
  return res.json() as Promise<OAuthStartResponse>;
}

/** Exchange auth code for API key — stores key in backend. */
export async function completeOAuth(
  code: string,
  codeVerifier: string,
): Promise<OAuthCallbackResponse> {
  const res = await fetch("/api/openrouter/oauth/callback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code, code_verifier: codeVerifier }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `OAuth callback failed: ${res.status}`,
    );
  }
  return res.json() as Promise<OAuthCallbackResponse>;
}

/** Check OpenRouter credit balance. */
export async function fetchCredits(): Promise<CreditsResponse> {
  const res = await fetch("/api/openrouter/credits");
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
