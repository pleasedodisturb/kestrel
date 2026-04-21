/**
 * Tests for OnboardingGuard route wrapper.
 *
 * Covers:
 * - WEB-01: Redirects to /welcome when welcome_completed_at is null
 * - WEB-01: Passes through to Layout when welcome_completed_at is set
 * - Fail-open on API error (D-09)
 * - Blank screen during loading (UI-SPEC)
 *
 * Mocking strategy: API-level mocks on @/api/onboarding (D-04).
 * Real React Query hooks execute — only the fetch boundary is faked.
 */

import { screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { render } from "@testing-library/react";
import { OnboardingGuard } from "@/components/OnboardingGuard";
import { renderWithProviders } from "@/test-utils";
import type { OnboardingStatus } from "@/api/onboarding";

// ---- API-level mocks (D-04) ----

const mockFetchOnboardingStatus = vi.fn();
const mockPatchOnboardingStep = vi.fn();
const mockResetOnboarding = vi.fn();

vi.mock("@/api/onboarding", () => ({
  fetchOnboardingStatus: (...args: unknown[]) =>
    mockFetchOnboardingStatus(...(args as [])),
  patchOnboardingStep: (...args: unknown[]) =>
    mockPatchOnboardingStep(...(args as [])),
  resetOnboarding: (...args: unknown[]) =>
    mockResetOnboarding(...(args as [])),
  DEFAULT_PROFILE_ID: 1,
}));

// ---- helpers ----

function makeStatus(
  overrides: Partial<OnboardingStatus> = {},
): OnboardingStatus {
  return {
    profile_id: 1,
    current_step: null,
    next_step: null,
    is_complete: false,
    progress_pct: 0,
    profile_started_at: null,
    profile_completed_at: null,
    demo_seeded_at: null,
    welcome_completed_at: null,
    tour_completed_at: null,
    feedback_prompted_at: null,
    completed_at: null,
    profile_started_via: null,
    profile_completed_via: null,
    demo_seeded_via: null,
    welcome_completed_via: null,
    tour_completed_via: null,
    feedback_prompted_via: null,
    completed_via: null,
    created_at: null,
    updated_at: null,
    ...overrides,
  };
}

const guardRoutes = (
  <Routes>
    <Route
      path="/welcome"
      element={<div data-testid="welcome-redirect">Welcome</div>}
    />
    <Route element={<OnboardingGuard />}>
      <Route
        path="/"
        element={<div data-testid="pipeline">Pipeline</div>}
      />
    </Route>
  </Routes>
);

function renderGuard(route = "/") {
  return renderWithProviders(guardRoutes, { route });
}

// ---- tests ----

describe("OnboardingGuard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPatchOnboardingStep.mockResolvedValue({});
    mockResetOnboarding.mockResolvedValue({});
  });

  it("redirects to /welcome when welcome_completed_at is null (WEB-01)", async () => {
    mockFetchOnboardingStatus.mockResolvedValue(
      makeStatus({ welcome_completed_at: null }),
    );

    renderGuard("/");

    expect(await screen.findByTestId("welcome-redirect")).toBeInTheDocument();
    expect(screen.queryByTestId("pipeline")).not.toBeInTheDocument();
  });

  it("renders Layout children when welcome_completed_at is set (WEB-01)", async () => {
    mockFetchOnboardingStatus.mockResolvedValue(
      makeStatus({
        current_step: "welcome_completed",
        next_step: "tour_completed",
        progress_pct: 57,
        welcome_completed_at: "2026-04-20T10:00:00Z",
        profile_started_at: "2026-04-20T09:00:00Z",
        profile_completed_at: "2026-04-20T09:30:00Z",
        demo_seeded_at: "2026-04-20T09:31:00Z",
        profile_started_via: "web",
        profile_completed_via: "web",
        demo_seeded_via: "web",
        welcome_completed_via: "web",
        created_at: "2026-04-20T09:00:00Z",
        updated_at: "2026-04-20T10:00:00Z",
      }),
    );

    renderGuard("/");

    expect(await screen.findByTestId("pipeline")).toBeInTheDocument();
    expect(screen.queryByTestId("welcome-redirect")).not.toBeInTheDocument();
  });

  it("fails open on API error -- renders Layout, not redirect (D-09)", async () => {
    // When OnboardingGuard sees isError, it renders <Layout /> which contains
    // TourProvider (also calls useOnboardingStatus). If both query observers
    // trigger retries, the component re-mount loop prevents settling. To test
    // fail-open behavior, we pre-seed the query cache with an error state and
    // disable refetching so no re-fetch cycle occurs.
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0 },
        mutations: { retry: false },
      },
    });

    // Pre-seed the cache with an errored query for the onboarding status key
    // used by useOnboardingStatus (queryKey: ["onboarding-status", 1])
    queryClient.getQueryCache().build(queryClient, {
      queryKey: ["onboarding-status", 1],
      retry: false,
    }).setState({
      status: "error",
      error: new Error("API down"),
      data: undefined,
      dataUpdatedAt: 0,
      fetchStatus: "idle",
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/"]}>
          {guardRoutes}
        </MemoryRouter>
      </QueryClientProvider>,
    );

    // Fail-open: OnboardingGuard sees isError=true and renders Layout
    // Layout's Outlet renders the matched "/" route showing pipeline
    expect(await screen.findByTestId("pipeline")).toBeInTheDocument();
    expect(screen.queryByTestId("welcome-redirect")).not.toBeInTheDocument();
  });

  it("shows nothing during loading -- blank screen (UI-SPEC)", () => {
    // Never resolves = perpetual loading state
    mockFetchOnboardingStatus.mockReturnValue(new Promise(() => {}));

    renderGuard("/");

    // Component returns null during loading
    expect(screen.queryByTestId("welcome-redirect")).not.toBeInTheDocument();
    expect(screen.queryByTestId("pipeline")).not.toBeInTheDocument();
  });
});
