/**
 * Tests for the SettingsPage — Profiles tab.
 *
 * Covers:
 * - VAL-PIPE-017: Profile create/edit flow via web UI
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { SettingsPage } from "@/pages/SettingsPage";
import type { ProfileListResponse, ProfileResponse } from "@/api/profiles";

// ---- mocks ----

const mockFetchProfiles = vi.fn<() => Promise<ProfileListResponse>>();
const mockCreateProfile = vi.fn<() => Promise<ProfileResponse>>();
const mockUpdateProfile = vi.fn<() => Promise<ProfileResponse>>();
const mockDeleteProfile = vi.fn<() => Promise<void>>();

vi.mock("@/api/profiles", () => ({
  fetchProfiles: (...args: unknown[]) => mockFetchProfiles(...(args as [])),
  fetchProfile: vi.fn(),
  createProfile: (...args: unknown[]) => mockCreateProfile(...(args as [])),
  updateProfile: (...args: unknown[]) => mockUpdateProfile(...(args as [])),
  deleteProfile: (...args: unknown[]) => mockDeleteProfile(...(args as [])),
}));

// Mock integrations API (not tested here — see IntegrationsSettings.test.tsx)
vi.mock("@/api/integrations", () => ({
  fetchIntegrations: vi.fn().mockResolvedValue({ integrations: [], count: 0 }),
  updateIntegration: vi.fn(),
  testIntegration: vi.fn(),
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

/** Render settings page and switch to Profiles tab. */
async function renderSettingsProfilesTab() {
  const qc = createQueryClient();
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  // Switch to Profiles tab (Integrations is the default tab)
  const profilesTab = screen.getByTestId("tab-profiles");
  fireEvent.click(profilesTab);
}

const SAMPLE_PROFILE: ProfileResponse = {
  id: 1,
  name: "Kestrel User",
  email: "user@example.com",
  location: "Berlin, Germany",
  job_family: "Senior TPM",
  created_at: "2026-03-01T08:00:00Z",
  updated_at: "2026-03-10T14:30:00Z",
};

// ---- tests ----

describe("SettingsPage — Profiles tab", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders the settings page with tabs", () => {
    mockFetchProfiles.mockReturnValue(new Promise(() => {}));
    const qc = createQueryClient();
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <SettingsPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByTestId("settings-page")).toBeInTheDocument();
    expect(screen.getByTestId("tab-integrations")).toBeInTheDocument();
    expect(screen.getByTestId("tab-profiles")).toBeInTheDocument();
  });

  it("shows loading state while fetching profiles", async () => {
    mockFetchProfiles.mockReturnValue(new Promise(() => {}));
    await renderSettingsProfilesTab();
    expect(screen.getByTestId("settings-loading")).toBeInTheDocument();
  });

  it("shows error on fetch failure", async () => {
    mockFetchProfiles.mockRejectedValue(new Error("Network error"));
    await renderSettingsProfilesTab();
    expect(await screen.findByTestId("settings-error")).toBeInTheDocument();
  });

  describe("with profiles loaded", () => {
    beforeEach(() => {
      mockFetchProfiles.mockResolvedValue({
        profiles: [SAMPLE_PROFILE],
        count: 1,
      });
    });

    it("shows profile card with name", async () => {
      await renderSettingsProfilesTab();
      expect(
        await screen.findByTestId("profile-name-1"),
      ).toHaveTextContent("Kestrel User");
    });

    it("shows profile email", async () => {
      await renderSettingsProfilesTab();
      expect(
        await screen.findByTestId("profile-email-1"),
      ).toHaveTextContent("user@example.com");
    });

    it("shows profile location", async () => {
      await renderSettingsProfilesTab();
      expect(
        await screen.findByTestId("profile-location-1"),
      ).toHaveTextContent("Berlin, Germany");
    });

    it("shows profile job family", async () => {
      await renderSettingsProfilesTab();
      expect(
        await screen.findByTestId("profile-job-family-1"),
      ).toHaveTextContent("Senior TPM");
    });

    it("has create profile button", async () => {
      await renderSettingsProfilesTab();
      expect(
        await screen.findByTestId("create-profile-button"),
      ).toBeInTheDocument();
    });

    it("has edit button for profile", async () => {
      await renderSettingsProfilesTab();
      expect(
        await screen.findByTestId("edit-profile-1"),
      ).toBeInTheDocument();
    });

    it("has delete button for profile", async () => {
      await renderSettingsProfilesTab();
      expect(
        await screen.findByTestId("delete-profile-1"),
      ).toBeInTheDocument();
    });

    it("shows create form when clicking New Profile", async () => {
      await renderSettingsProfilesTab();
      const btn = await screen.findByTestId("create-profile-button");
      fireEvent.click(btn);
      expect(screen.getByTestId("profile-create-form")).toBeInTheDocument();
      expect(screen.getByTestId("create-name-input")).toBeInTheDocument();
      expect(screen.getByTestId("create-email-input")).toBeInTheDocument();
      expect(screen.getByTestId("create-location-input")).toBeInTheDocument();
      expect(screen.getByTestId("create-job-family-input")).toBeInTheDocument();
    });

    it("shows edit form when clicking Edit", async () => {
      await renderSettingsProfilesTab();
      const editBtn = await screen.findByTestId("edit-profile-1");
      fireEvent.click(editBtn);
      expect(
        screen.getByTestId("profile-edit-form-1"),
      ).toBeInTheDocument();
      expect(screen.getByTestId("edit-1-name-input")).toHaveValue(
        "Kestrel User",
      );
      expect(screen.getByTestId("edit-1-email-input")).toHaveValue(
        "user@example.com",
      );
    });

    it("calls create API on save", async () => {
      mockCreateProfile.mockResolvedValue({
        ...SAMPLE_PROFILE,
        id: 2,
        name: "New User",
      });

      await renderSettingsProfilesTab();
      const btn = await screen.findByTestId("create-profile-button");
      fireEvent.click(btn);

      const nameInput = screen.getByTestId("create-name-input");
      fireEvent.change(nameInput, { target: { value: "New User" } });

      const saveBtn = screen.getByTestId("create-save-button");
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(mockCreateProfile).toHaveBeenCalled();
      });
    });

    it("calls update API on edit save", async () => {
      mockUpdateProfile.mockResolvedValue({
        ...SAMPLE_PROFILE,
        location: "Munich",
      });

      await renderSettingsProfilesTab();
      const editBtn = await screen.findByTestId("edit-profile-1");
      fireEvent.click(editBtn);

      const locationInput = screen.getByTestId("edit-1-location-input");
      fireEvent.change(locationInput, { target: { value: "Munich" } });

      const saveBtn = screen.getByTestId("edit-1-save-button");
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(mockUpdateProfile).toHaveBeenCalled();
      });
    });
  });

  describe("empty profiles", () => {
    it("shows no-profiles empty state", async () => {
      mockFetchProfiles.mockResolvedValue({ profiles: [], count: 0 });
      await renderSettingsProfilesTab();
      expect(await screen.findByTestId("no-profiles")).toBeInTheDocument();
      expect(screen.getByTestId("create-profile-cta")).toBeInTheDocument();
    });
  });
});
