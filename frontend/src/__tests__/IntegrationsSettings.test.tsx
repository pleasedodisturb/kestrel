/**
 * Tests for the Integrations section of SettingsPage.
 *
 * Covers:
 * - VAL-PUSH-006: All integrations have settings section with credential fields,
 *                  on/off toggle, status indicator
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { SettingsPage } from "@/pages/SettingsPage";
import type {
  IntegrationListResponse,
  IntegrationConfigResponse,
  IntegrationTestResponse,
} from "@/api/integrations";

// ---- mocks ----

const mockFetchIntegrations =
  vi.fn<() => Promise<IntegrationListResponse>>();
const mockUpdateIntegration =
  vi.fn<() => Promise<IntegrationConfigResponse>>();
const mockTestIntegration =
  vi.fn<() => Promise<IntegrationTestResponse>>();

vi.mock("@/api/integrations", () => ({
  fetchIntegrations: (...args: unknown[]) =>
    mockFetchIntegrations(...(args as [])),
  updateIntegration: (...args: unknown[]) =>
    mockUpdateIntegration(...(args as [])),
  testIntegration: (...args: unknown[]) =>
    mockTestIntegration(...(args as [])),
}));

// Mock profiles API (not tested here, but loaded by the component)
vi.mock("@/api/profiles", () => ({
  fetchProfiles: vi.fn().mockResolvedValue({ profiles: [], count: 0 }),
  createProfile: vi.fn(),
  updateProfile: vi.fn(),
  deleteProfile: vi.fn(),
}));

vi.mock("@/api/followUps", () => ({
  fetchOverdueCount: vi.fn().mockResolvedValue({ count: 0 }),
}));

// ---- helpers ----

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

function renderSettings() {
  const qc = createQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const SAMPLE_PUSHOVER: IntegrationConfigResponse = {
  name: "pushover",
  display_name: "Pushover",
  description: "Push notifications for follow-ups, ghost alerts, and discoveries",
  enabled: false,
  credential_fields: [
    {
      key: "user_key",
      label: "User Key",
      field_type: "password",
      placeholder: "Pushover user key",
      required: true,
    },
    {
      key: "app_token",
      label: "App Token",
      field_type: "password",
      placeholder: "Pushover application token",
      required: true,
    },
  ],
  credentials_set: { user_key: false, app_token: false },
  status: "not_configured",
  status_message: null,
  last_tested_at: null,
  created_at: null,
  updated_at: null,
};

const SAMPLE_TICKTICK: IntegrationConfigResponse = {
  name: "ticktick",
  display_name: "TickTick",
  description: "Bidirectional task sync with TickTick",
  enabled: true,
  credential_fields: [
    {
      key: "api_token",
      label: "API Token",
      field_type: "password",
      placeholder: "Your TickTick API token",
      required: true,
    },
    {
      key: "project_id",
      label: "Project ID",
      field_type: "text",
      placeholder: "TickTick project ID",
      required: false,
    },
  ],
  credentials_set: { api_token: true, project_id: false },
  status: "connected",
  status_message: "Connection test passed.",
  last_tested_at: "2026-03-14T06:00:00Z",
  created_at: "2026-03-14T05:00:00Z",
  updated_at: "2026-03-14T06:00:00Z",
};

const ALL_INTEGRATIONS: IntegrationListResponse = {
  integrations: [
    SAMPLE_TICKTICK,
    { ...SAMPLE_PUSHOVER, name: "calendar", display_name: "Calendar", description: "Calendar integration", credential_fields: [], credentials_set: {} },
    SAMPLE_PUSHOVER,
    { ...SAMPLE_PUSHOVER, name: "voice", display_name: "Voice Mode", description: "Voice interaction", credential_fields: [], credentials_set: {} },
    { ...SAMPLE_PUSHOVER, name: "ai_providers", display_name: "AI Providers", description: "AI config", credential_fields: [], credentials_set: {} },
  ],
  count: 5,
};

// ---- tests ----

describe("IntegrationsSettings", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("shows loading state while fetching", () => {
    mockFetchIntegrations.mockReturnValue(new Promise(() => {}));
    renderSettings();
    expect(screen.getByTestId("integrations-loading")).toBeInTheDocument();
  });

  it("shows error on fetch failure", async () => {
    mockFetchIntegrations.mockRejectedValue(new Error("Network error"));
    renderSettings();
    await waitFor(() => {
      expect(screen.getByTestId("integrations-error")).toBeInTheDocument();
    });
  });

  it("renders all integration panels", async () => {
    mockFetchIntegrations.mockResolvedValue(ALL_INTEGRATIONS);
    renderSettings();
    await waitFor(() => {
      expect(
        screen.getByTestId("integration-panel-ticktick"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("integration-panel-pushover"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("integration-panel-calendar"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("integration-panel-voice"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("integration-panel-ai_providers"),
      ).toBeInTheDocument();
    });
  });

  it("shows display name for each integration", async () => {
    mockFetchIntegrations.mockResolvedValue(ALL_INTEGRATIONS);
    renderSettings();
    await waitFor(() => {
      expect(
        screen.getByTestId("integration-name-ticktick"),
      ).toHaveTextContent("TickTick");
      expect(
        screen.getByTestId("integration-name-pushover"),
      ).toHaveTextContent("Pushover");
    });
  });

  it("shows toggle switches", async () => {
    mockFetchIntegrations.mockResolvedValue(ALL_INTEGRATIONS);
    renderSettings();
    await waitFor(() => {
      const ticktickToggle = screen.getByTestId("integration-toggle-ticktick");
      expect(ticktickToggle).toBeInTheDocument();
      expect(ticktickToggle).toHaveAttribute("aria-checked", "true");

      const pushoverToggle = screen.getByTestId(
        "integration-toggle-pushover",
      );
      expect(pushoverToggle).toHaveAttribute("aria-checked", "false");
    });
  });

  it("shows status indicators", async () => {
    mockFetchIntegrations.mockResolvedValue(ALL_INTEGRATIONS);
    renderSettings();
    await waitFor(() => {
      // TickTick has status "connected"
      const panel = screen.getByTestId("integration-panel-ticktick");
      expect(panel.querySelector('[data-testid="status-connected"]')).toBeInTheDocument();
    });
  });

  it("expands panel to show credential fields", async () => {
    mockFetchIntegrations.mockResolvedValue({
      integrations: [SAMPLE_PUSHOVER],
      count: 1,
    });
    renderSettings();

    await waitFor(() => {
      expect(
        screen.getByTestId("integration-panel-pushover"),
      ).toBeInTheDocument();
    });

    // Click expand
    fireEvent.click(screen.getByTestId("integration-expand-pushover"));

    await waitFor(() => {
      expect(
        screen.getByTestId("integration-config-pushover"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("credential-pushover-user_key"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("credential-pushover-app_token"),
      ).toBeInTheDocument();
    });
  });

  it("shows save and test buttons in expanded panel", async () => {
    mockFetchIntegrations.mockResolvedValue({
      integrations: [SAMPLE_PUSHOVER],
      count: 1,
    });
    renderSettings();

    await waitFor(() => {
      expect(
        screen.getByTestId("integration-panel-pushover"),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("integration-expand-pushover"));

    await waitFor(() => {
      expect(
        screen.getByTestId("save-credentials-pushover"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("test-connection-pushover"),
      ).toBeInTheDocument();
    });
  });

  it("has integrations tab active by default", async () => {
    mockFetchIntegrations.mockResolvedValue(ALL_INTEGRATIONS);
    renderSettings();
    const tabButton = screen.getByTestId("tab-integrations");
    expect(tabButton).toHaveClass("border-gray-900");
  });

  it("switches to profiles tab", async () => {
    mockFetchIntegrations.mockResolvedValue(ALL_INTEGRATIONS);
    renderSettings();

    fireEvent.click(screen.getByTestId("tab-profiles"));
    const profilesTab = screen.getByTestId("tab-profiles");
    expect(profilesTab).toHaveClass("border-gray-900");
  });

  it("toggle calls update API", async () => {
    const updatedPushover = { ...SAMPLE_PUSHOVER, enabled: true };
    mockFetchIntegrations.mockResolvedValue({
      integrations: [SAMPLE_PUSHOVER],
      count: 1,
    });
    mockUpdateIntegration.mockResolvedValue(updatedPushover);
    renderSettings();

    await waitFor(() => {
      expect(
        screen.getByTestId("integration-toggle-pushover"),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("integration-toggle-pushover"));

    await waitFor(() => {
      expect(mockUpdateIntegration).toHaveBeenCalled();
    });
  });
});
