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

/** Fetch health status for all AI providers. */
export async function fetchAIHealth(): Promise<AIHealthResponse> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) {
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
    throw new Error(`Failed to check provider health: ${res.status}`);
  }
  return res.json() as Promise<ProviderHealthStatus>;
}
