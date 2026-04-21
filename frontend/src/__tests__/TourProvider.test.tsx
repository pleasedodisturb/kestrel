/**
 * Tests for TourProvider, TourTooltip, and TourOverlay.
 *
 * Covers:
 * - useTour context (default inactive state outside provider)
 * - Auto-launch after onboarding completion (D-01)
 * - Step progression via next()
 * - Cross-page navigation on step change (D-02)
 * - Tour completion persists via patchOnboardingStep (D-06)
 * - Skip ends tour and persists
 * - Tour does not auto-launch when already completed
 * - Tour does not auto-launch before welcome completion
 * - TourOverlay renders when active
 * - TourTooltip renders step content and navigation buttons
 * - TourTooltip shows "Done" on last step
 * - Accessibility: tooltip has role=dialog and aria-label (D-05)
 * - Accessibility: Escape key skips tour
 * - TOUR_STEPS has expected structure
 *
 * Mock strategy (D-04): Mock only @/api/onboarding (external boundary).
 * Real hooks (useOnboardingStatus, usePatchOnboardingStep) run via React Query.
 * Minimal useNavigate spy for imperative navigation assertions only.
 */

import {
  render,
  screen,
  act,
  fireEvent,
  waitFor,
} from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { renderWithProviders } from "@/test-utils";
import type { OnboardingStatus } from "@/api/onboarding";
import { TourProvider, useTour, TOUR_STEPS } from "@/components/TourProvider";

/* ---------- API-level mocks (D-04: mock external boundary only) ---------- */

const mockFetchOnboardingStatus = vi.fn();
const mockPatchOnboardingStep = vi.fn();
const mockResetOnboarding = vi.fn();

vi.mock("@/api/onboarding", () => ({
  fetchOnboardingStatus: (...args: unknown[]) =>
    mockFetchOnboardingStatus(...(args as [])),
  patchOnboardingStep: (...args: unknown[]) =>
    mockPatchOnboardingStep(...(args as [])),
  resetOnboarding: (...args: unknown[]) => mockResetOnboarding(...(args as [])),
  DEFAULT_PROFILE_ID: 1,
}));

/* ---------- Minimal navigate spy (Open Question #1 fallback for imperative nav) ---------- */

const mockNavigate = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual =
    await vi.importActual<typeof import("react-router-dom")>(
      "react-router-dom",
    );
  return { ...actual, useNavigate: () => mockNavigate };
});

/* ---------- Helpers ---------- */

/** Onboarding status where welcome is done but tour is not. */
function welcomeCompletedStatus(): OnboardingStatus {
  return {
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
  };
}

/** Onboarding status where tour is already completed. */
function tourCompletedStatus(): OnboardingStatus {
  return {
    ...welcomeCompletedStatus(),
    tour_completed_at: "2026-04-20T11:00:00Z",
    tour_completed_via: "web",
  };
}

/** Onboarding status where welcome is NOT yet done. */
function welcomeNotCompletedStatus(): OnboardingStatus {
  return {
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
  };
}

/** Consumer component that exposes tour context for assertions. */
function TourConsumer() {
  const tour = useTour();
  return (
    <div data-testid="tour-consumer">
      <span data-testid="is-active">{String(tour.isActive)}</span>
      <span data-testid="current-step">{tour.currentStep}</span>
      <span data-testid="total-steps">{tour.totalSteps}</span>
      <span data-testid="step-heading">
        {tour.currentStepData?.heading ?? "none"}
      </span>
      <button data-testid="call-next" onClick={tour.next}>
        Next
      </button>
      <button data-testid="call-skip" onClick={tour.skip}>
        Skip
      </button>
    </div>
  );
}

function renderTour(initialRoute = "/", children?: React.ReactNode) {
  return renderWithProviders(
    <TourProvider>{children ?? <TourConsumer />}</TourProvider>,
    { route: initialRoute },
  );
}

/* ---------- Setup ---------- */

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  mockFetchOnboardingStatus.mockResolvedValue(welcomeNotCompletedStatus());
  mockPatchOnboardingStep.mockResolvedValue(welcomeCompletedStatus());
  mockResetOnboarding.mockResolvedValue({});
});

afterEach(() => {
  vi.useRealTimers();
});

/* ---------- Tests ---------- */

describe("TOUR_STEPS", () => {
  it("has at least 5 steps with required fields", () => {
    expect(TOUR_STEPS.length).toBeGreaterThanOrEqual(5);
    for (const step of TOUR_STEPS) {
      expect(step.page).toBeTruthy();
      expect(step.targetSelector).toBeTruthy();
      expect(step.heading).toBeTruthy();
      expect(step.body).toBeTruthy();
    }
  });
});

describe("useTour outside provider", () => {
  it("returns inactive default context without crashing", () => {
    function Standalone() {
      const tour = useTour();
      return (
        <div>
          <span data-testid="standalone-active">{String(tour.isActive)}</span>
          <span data-testid="standalone-steps">{tour.totalSteps}</span>
        </div>
      );
    }

    render(
      <MemoryRouter>
        <Standalone />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("standalone-active")).toHaveTextContent("false");
    expect(screen.getByTestId("standalone-steps")).toHaveTextContent(
      String(TOUR_STEPS.length),
    );
  });
});

describe("TourProvider", () => {
  it("starts inactive when onboarding status is loading", () => {
    // Default mock returns a never-resolving promise to simulate loading
    mockFetchOnboardingStatus.mockReturnValue(new Promise(() => {}));
    renderTour();
    expect(screen.getByTestId("is-active")).toHaveTextContent("false");
  });

  it("auto-launches tour when welcome completed but tour not completed (D-01)", async () => {
    mockFetchOnboardingStatus.mockResolvedValue(welcomeCompletedStatus());
    renderTour();

    // Wait for React Query to resolve, then advance past AUTO_LAUNCH_DELAY
    await waitFor(() => {
      expect(screen.getByTestId("is-active")).toHaveTextContent("false");
    });

    act(() => {
      vi.advanceTimersByTime(600);
    });

    await waitFor(() => {
      expect(screen.getByTestId("is-active")).toHaveTextContent("true");
    });
    expect(screen.getByTestId("current-step")).toHaveTextContent("0");
    expect(screen.getByTestId("step-heading")).toHaveTextContent(
      TOUR_STEPS[0].heading,
    );
  });

  it("does NOT auto-launch when tour already completed", async () => {
    mockFetchOnboardingStatus.mockResolvedValue(tourCompletedStatus());
    renderTour();

    await waitFor(() => {
      // Data loaded (not loading), but tour should stay inactive
      expect(screen.getByTestId("is-active")).toHaveTextContent("false");
    });

    act(() => {
      vi.advanceTimersByTime(600);
    });

    expect(screen.getByTestId("is-active")).toHaveTextContent("false");
  });

  it("does NOT auto-launch when welcome not yet completed", async () => {
    mockFetchOnboardingStatus.mockResolvedValue(welcomeNotCompletedStatus());
    renderTour();

    await waitFor(() => {
      expect(screen.getByTestId("is-active")).toHaveTextContent("false");
    });

    act(() => {
      vi.advanceTimersByTime(600);
    });

    expect(screen.getByTestId("is-active")).toHaveTextContent("false");
  });

  it("advances step on next() and stays active mid-tour", async () => {
    mockFetchOnboardingStatus.mockResolvedValue(welcomeCompletedStatus());
    renderTour();

    act(() => {
      vi.advanceTimersByTime(600);
    });

    await waitFor(() => {
      expect(screen.getByTestId("is-active")).toHaveTextContent("true");
    });

    expect(screen.getByTestId("current-step")).toHaveTextContent("0");

    act(() => {
      fireEvent.click(screen.getByTestId("call-next"));
    });

    expect(screen.getByTestId("current-step")).toHaveTextContent("1");
    expect(screen.getByTestId("is-active")).toHaveTextContent("true");
  });

  it("navigates to next step page when page differs (D-02)", async () => {
    mockFetchOnboardingStatus.mockResolvedValue(welcomeCompletedStatus());
    renderTour();

    act(() => {
      vi.advanceTimersByTime(600);
    });

    await waitFor(() => {
      expect(screen.getByTestId("is-active")).toHaveTextContent("true");
    });

    // Steps 0,1 are on "/", step 2 is on "/discovery"
    // Advance to step 2 which requires navigation
    act(() => {
      fireEvent.click(screen.getByTestId("call-next")); // 0 -> 1
    });
    act(() => {
      fireEvent.click(screen.getByTestId("call-next")); // 1 -> 2
    });

    expect(mockNavigate).toHaveBeenCalledWith("/discovery");
  });

  it("completes tour on next() past last step and persists (D-06)", async () => {
    mockFetchOnboardingStatus.mockResolvedValue(welcomeCompletedStatus());
    renderTour();

    act(() => {
      vi.advanceTimersByTime(600);
    });

    await waitFor(() => {
      expect(screen.getByTestId("is-active")).toHaveTextContent("true");
    });

    // Advance through all steps
    for (let i = 0; i < TOUR_STEPS.length; i++) {
      act(() => {
        fireEvent.click(screen.getByTestId("call-next"));
      });
    }

    expect(screen.getByTestId("is-active")).toHaveTextContent("false");
    await waitFor(() => {
      expect(mockPatchOnboardingStep).toHaveBeenCalledWith(1, "tour_completed");
    });
  });

  it("skip() ends tour and persists completion (D-06)", async () => {
    mockFetchOnboardingStatus.mockResolvedValue(welcomeCompletedStatus());
    renderTour();

    act(() => {
      vi.advanceTimersByTime(600);
    });

    await waitFor(() => {
      expect(screen.getByTestId("is-active")).toHaveTextContent("true");
    });

    act(() => {
      fireEvent.click(screen.getByTestId("call-skip"));
    });

    expect(screen.getByTestId("is-active")).toHaveTextContent("false");
    await waitFor(() => {
      expect(mockPatchOnboardingStep).toHaveBeenCalledWith(1, "tour_completed");
    });
  });

  it("resets currentStep to 0 after completion", async () => {
    mockFetchOnboardingStatus.mockResolvedValue(welcomeCompletedStatus());
    renderTour();

    act(() => {
      vi.advanceTimersByTime(600);
    });

    await waitFor(() => {
      expect(screen.getByTestId("is-active")).toHaveTextContent("true");
    });

    // Advance a couple steps then skip
    act(() => {
      fireEvent.click(screen.getByTestId("call-next"));
    });
    expect(screen.getByTestId("current-step")).toHaveTextContent("1");

    act(() => {
      fireEvent.click(screen.getByTestId("call-skip"));
    });

    expect(screen.getByTestId("current-step")).toHaveTextContent("0");
  });
});

describe("TourOverlay", () => {
  it("renders overlay element when tour is active", async () => {
    mockFetchOnboardingStatus.mockResolvedValue(welcomeCompletedStatus());
    renderTour("/", <TourConsumer />);

    act(() => {
      vi.advanceTimersByTime(600);
    });

    await waitFor(() => {
      expect(screen.getByTestId("is-active")).toHaveTextContent("true");
    });

    // TourOverlay and TourTooltip render inside the provider
    const overlay = document.querySelector("[data-testid='tour-overlay']");
    expect(overlay).toBeInTheDocument();
  });

  it("does NOT render overlay when tour is inactive", async () => {
    mockFetchOnboardingStatus.mockResolvedValue(tourCompletedStatus());
    renderTour();

    act(() => {
      vi.advanceTimersByTime(600);
    });

    await waitFor(() => {
      expect(screen.getByTestId("is-active")).toHaveTextContent("false");
    });

    const overlay = document.querySelector("[data-testid='tour-overlay']");
    expect(overlay).not.toBeInTheDocument();
  });
});

describe("TourTooltip", () => {
  it("renders tooltip with step heading and body when active", async () => {
    mockFetchOnboardingStatus.mockResolvedValue(welcomeCompletedStatus());
    renderTour();

    act(() => {
      vi.advanceTimersByTime(600);
    });

    await waitFor(() => {
      expect(screen.getByTestId("is-active")).toHaveTextContent("true");
    });

    const tooltip = document.querySelector("[data-testid='tour-tooltip']");
    expect(tooltip).toBeInTheDocument();
    expect(tooltip).toHaveAttribute("role", "dialog");
    expect(tooltip).toHaveAttribute("aria-label", TOUR_STEPS[0].heading);
  });

  it("has Skip tour and Next buttons", async () => {
    mockFetchOnboardingStatus.mockResolvedValue(welcomeCompletedStatus());
    renderTour();

    act(() => {
      vi.advanceTimersByTime(600);
    });

    await waitFor(() => {
      expect(screen.getByTestId("is-active")).toHaveTextContent("true");
    });

    const skipBtn = document.querySelector("[data-testid='tour-skip']");
    const nextBtn = document.querySelector("[data-testid='tour-next']");
    expect(skipBtn).toBeInTheDocument();
    expect(nextBtn).toBeInTheDocument();
    expect(nextBtn).toHaveTextContent("Next");
  });

  it("shows Done on last step instead of Next", async () => {
    mockFetchOnboardingStatus.mockResolvedValue(welcomeCompletedStatus());
    renderTour();

    act(() => {
      vi.advanceTimersByTime(600);
    });

    await waitFor(() => {
      expect(screen.getByTestId("is-active")).toHaveTextContent("true");
    });

    // Navigate to last step
    for (let i = 0; i < TOUR_STEPS.length - 1; i++) {
      act(() => {
        fireEvent.click(screen.getByTestId("call-next"));
      });
    }

    const nextBtn = document.querySelector("[data-testid='tour-next']");
    expect(nextBtn).toHaveTextContent("Done");
  });

  it("displays step counter (e.g. 1 of 5)", async () => {
    mockFetchOnboardingStatus.mockResolvedValue(welcomeCompletedStatus());
    renderTour();

    act(() => {
      vi.advanceTimersByTime(600);
    });

    await waitFor(() => {
      expect(screen.getByTestId("is-active")).toHaveTextContent("true");
    });

    const tooltip = document.querySelector("[data-testid='tour-tooltip']");
    expect(tooltip?.textContent).toContain(`1 of ${TOUR_STEPS.length}`);
  });

  it("Escape key skips the tour (D-05 accessibility)", async () => {
    mockFetchOnboardingStatus.mockResolvedValue(welcomeCompletedStatus());
    renderTour();

    act(() => {
      vi.advanceTimersByTime(600);
    });

    await waitFor(() => {
      expect(screen.getByTestId("is-active")).toHaveTextContent("true");
    });

    act(() => {
      fireEvent.keyDown(document, { key: "Escape" });
    });

    expect(screen.getByTestId("is-active")).toHaveTextContent("false");
    await waitFor(() => {
      expect(mockPatchOnboardingStep).toHaveBeenCalledWith(1, "tour_completed");
    });
  });
});
