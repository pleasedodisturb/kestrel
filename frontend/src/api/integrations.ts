/**
 * API client functions for integration configuration.
 */

export interface IntegrationFieldDef {
  key: string;
  label: string;
  field_type: "password" | "text" | "url";
  placeholder: string;
  required: boolean;
}

export interface IntegrationConfigResponse {
  name: string;
  display_name: string;
  description: string;
  enabled: boolean;
  credential_fields: IntegrationFieldDef[];
  credentials_set: Record<string, boolean>;
  status: "not_configured" | "connected" | "error" | "disabled";
  status_message: string | null;
  last_tested_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface IntegrationListResponse {
  integrations: IntegrationConfigResponse[];
  count: number;
}

export interface IntegrationConfigUpdate {
  enabled?: boolean;
  credentials?: Record<string, string>;
}

export interface IntegrationTestResponse {
  name: string;
  success: boolean;
  message: string;
  tested_at: string;
}

const API_BASE = "/api/integrations";

/** Fetch all integrations with their configuration. */
export async function fetchIntegrations(): Promise<IntegrationListResponse> {
  const res = await fetch(API_BASE);
  if (!res.ok) {
    throw new Error(`Failed to fetch integrations: ${res.status}`);
  }
  return res.json() as Promise<IntegrationListResponse>;
}

/** Fetch a single integration's configuration. */
export async function fetchIntegration(
  name: string,
): Promise<IntegrationConfigResponse> {
  const res = await fetch(`${API_BASE}/${name}/config`);
  if (!res.ok) {
    if (res.status === 404) throw new Error(`Unknown integration: ${name}`);
    throw new Error(`Failed to fetch integration: ${res.status}`);
  }
  return res.json() as Promise<IntegrationConfigResponse>;
}

/** Update an integration's configuration. */
export async function updateIntegration(
  name: string,
  data: IntegrationConfigUpdate,
): Promise<IntegrationConfigResponse> {
  const res = await fetch(`${API_BASE}/${name}/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Failed to update integration: ${res.status}`,
    );
  }
  return res.json() as Promise<IntegrationConfigResponse>;
}

/** Test an integration's connection. */
export async function testIntegration(
  name: string,
): Promise<IntegrationTestResponse> {
  const res = await fetch(`${API_BASE}/${name}/test`, {
    method: "POST",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Failed to test integration: ${res.status}`,
    );
  }
  return res.json() as Promise<IntegrationTestResponse>;
}
