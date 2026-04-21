/**
 * Tests for OnboardingGuard route wrapper.
 *
 * Covers:
 * - WEB-01: Redirects to /welcome when welcome_completed_at is null
 * - WEB-01: Passes through to Layout when welcome_completed_at is set
 * - Fail-open on API error (D-09)
 * - Blank screen during loading (UI-SPEC)
 */

import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { OnboardingGuard } from "@/components/OnboardingGuard";
import type { UseQueryResult } from "@tanstack/react-query";
import type { OnboardingStatus } from "@/api/onboarding";

// Mock the hook that OnboardingGuard uses
const mockUseOnboardingStatus =
  vi.fn<() => Partial<UseQueryResult<OnboardingStatus>>>();

vi.mock("@/hooks/useOnboarding", () => ({
  useOnboardingStatus: (...args: unknown[]) =>
    mockUseOnboardingStatus(...(args as [])),
}));

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  });
}

function renderGuard(route = "/") {
  const qc = createQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[route]}>
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
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("OnboardingGuard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("redirects to /welcome when welcome_completed_at is null (WEB-01)", () => {
    mockUseOnboardingStatus.mockReturnValue({
      data: {
        profile_id: 1,
        current_step: null,
        next_step: "profile_started",
        is_complete: false,
        progress_pct: 0,
        welcome_completed_at: null,
        profile_started_at: null,
        profile_completed_at: null,
        demo_seeded_at: null,
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
      },
      isLoading: false,
      isError: false,
    });

    renderGuard("/");
    expect(screen.getByTestId("welcome-redirect")).toBeInTheDocument();
    expect(screen.queryByTestId("pipeline")).not.toBeInTheDocument();
  });

  it("renders Layout children when welcome_completed_at is set (WEB-01)", () => {
    mockUseOnboardingStatus.mockReturnValue({
      data: {
        profile_id: 1,
        current_step: "welcome_completed",
        next_step: "tour_completed",
        is_complete: false,
        progress_pct: 57,
        welcome_completed_at: "2026-04-20T10:00:00Z",
        profile_started_at: "2026-04-20T09:00:00Z",
        profile_completed_at: "2026-04-20T09:30:00Z",
        demo_seeded_at: "2026-04-20T09:31:00Z",
        tour_completed_at: null,
        feedback_prompted_at: null,
        completed_at: null,
        profile_started_via: "web",
        profile_completed_via: "web",
        demo_seeded_via: "web",
        welcome_completed_via: "web",
        tour_completed_via: null,
        feedback_prompted_via: null,
        completed_via: null,
        created_at: "2026-04-20T09:00:00Z",
        updated_at: "2026-04-20T10:00:00Z",
      },
      isLoading: false,
      isError: false,
    });

    renderGuard("/");
    expect(screen.getByTestId("pipeline")).toBeInTheDocument();
    expect(screen.queryByTestId("welcome-redirect")).not.toBeInTheDocument();
  });

  it("fails open on API error -- renders Layout, not redirect (D-09)", () => {
    mockUseOnboardingStatus.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    });

    renderGuard("/");
    // Fail-open: Layout renders its Outlet, so pipeline should be visible
    expect(screen.getByTestId("pipeline")).toBeInTheDocument();
    expect(screen.queryByTestId("welcome-redirect")).not.toBeInTheDocument();
  });

  it("shows nothing during loading -- blank screen (UI-SPEC)", () => {
    mockUseOnboardingStatus.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });

    renderGuard("/");
    // Component returns null during loading
    expect(screen.queryByTestId("welcome-redirect")).not.toBeInTheDocument();
    expect(screen.queryByTestId("pipeline")).not.toBeInTheDocument();
  });
});
