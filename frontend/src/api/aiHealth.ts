/**
 * API client functions for AI provider health dashboard.
 */

export interface ProviderCredits {
  remaining: number | null;
  total: number | null;
  unit: string;
}

export interface ProviderRateLimit {
  requests_per_minute: number | null;
  tokens_per_minute: number | null;
}

export interface ProviderHealthStatus {
  name: string;
  display_name: string;
  status: "reachable" | "unreachable" | "not_configured" | "error";
  is_default: boolean;
  error_message: string | null;
  credits: ProviderCredits | null;
  rate_limit: ProviderRateLimit | null;
  response_time_ms: number | null;
}

export interface AIHealthResponse {
  providers: ProviderHealthStatus[];
  default_provider: string;
}

const API_BASE = "/api/ai";

/**
 * Record a credits-exhausted / rate-limited response so the UI banner
 * (CreditsExhaustedBanner) can surface it. Called from any endpoint that
 * could trip OpenRouter's 402/429.
 */
function markCreditsIssue(status: number): void {
  if (status === 402 || status === 429) {
    sessionStorage.setItem("credits_exhausted", "true");
  }
}

/** Fetch health status for all AI providers. */
export async function fetchAIHealth(): Promise<AIHealthResponse> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) {
    markCreditsIssue(res.status);
    throw new Error(`Failed to fetch AI health: ${res.status}`);
  }
  return res.json() as Promise<AIHealthResponse>;
}

/** Fetch health status for a single provider. */
export async function fetchProviderHealth(
  provider: string,
): Promise<ProviderHealthStatus> {
  const res = await fetch(`${API_BASE}/health/check?provider=${encodeURIComponent(provider)}`);
  if (!res.ok) {
    markCreditsIssue(res.status);
    throw new Error(`Failed to check provider health: ${res.status}`);
  }
  return res.json() as Promise<ProviderHealthStatus>;
}
