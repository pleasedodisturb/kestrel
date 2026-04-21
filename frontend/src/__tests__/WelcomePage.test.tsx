/**
 * Tests for the WelcomePage component.
 *
 * Covers:
 * - WEB-02: Welcome screen with Get Started CTA
 * - WEB-04: Resume from last step
 * - WEB-07: Summary screen with completed/skipped checklist
 * - WEB-08: Skipped steps show Settings path
 * - WEB-09: AI provider nudge card on summary
 * - PROF-04: Same 6 questions as CLI wizard
 *
 * Mocking strategy: API-level mocks on @/api/* (D-04).
 * No useNavigate mock — navigation tested via Routes rendering.
 */

import { screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { Routes, Route } from "react-router-dom";
import { WelcomePage } from "@/pages/WelcomePage";
import { renderWithProviders } from "@/test-utils";
import type { OnboardingStatus } from "@/api/onboarding";

// ---- API-level mocks (D-04) ----

const mockFetchOnboardingStatus = vi.fn<() => Promise<OnboardingStatus>>();
const mockPatchOnboardingStep = vi.fn<() => Promise<OnboardingStatus>>();

vi.mock("@/api/onboarding", () => ({
  DEFAULT_PROFILE_ID: 1,
  fetchOnboardingStatus: (...args: unknown[]) =>
    mockFetchOnboardingStatus(...(args as [])),
  patchOnboardingStep: (...args: unknown[]) =>
    mockPatchOnboardingStep(...(args as [])),
}));

const mockUpdateProfile = vi.fn<() => Promise<unknown>>();
const mockFetchProfile = vi.fn<() => Promise<unknown>>();
vi.mock("@/api/profiles", () => ({
  updateProfile: (...args: unknown[]) => mockUpdateProfile(...(args as [])),
  fetchProfile: (...args: unknown[]) => mockFetchProfile(...(args as [])),
}));

const mockCreateSkill = vi.fn<() => Promise<unknown>>();
vi.mock("@/api/skills", () => ({
  createSkill: (...args: unknown[]) => mockCreateSkill(...(args as [])),
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

function makeProfile(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    name: "Default",
    email: null,
    location: null,
    job_family: null,
    salary_range: null,
    experience_level: null,
    created_at: "2026-04-21T00:00:00Z",
    updated_at: "2026-04-21T00:00:00Z",
    ...overrides,
  };
}

function renderWelcomePage(statusOverrides: Partial<OnboardingStatus> = {}) {
  mockFetchOnboardingStatus.mockResolvedValue(makeStatus(statusOverrides));
  return renderWithProviders(
    <Routes>
      <Route path="/welcome" element={<WelcomePage />} />
      <Route
        path="/"
        element={<div data-testid="pipeline-redirect">Pipeline</div>}
      />
    </Routes>,
    { route: "/welcome" },
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockUpdateProfile.mockResolvedValue({});
  mockFetchProfile.mockResolvedValue(makeProfile());
  mockCreateSkill.mockResolvedValue({ id: 1 });
  mockPatchOnboardingStep.mockResolvedValue(makeStatus());
});

// ---- tests ----

describe("WelcomePage", () => {
  describe("Welcome screen (WEB-02)", () => {
    it("renders the welcome heading and CTA", () => {
      renderWelcomePage();

      expect(screen.getByText("Welcome to Kestrel")).toBeInTheDocument();
      expect(screen.getByText("Get Started")).toBeInTheDocument();
    });

    it("shows setup description text", () => {
      renderWelcomePage();

      expect(screen.getByText(/score jobs that match you/)).toBeInTheDocument();
    });

    it("has a welcome-page test id", () => {
      renderWelcomePage();

      expect(screen.getByTestId("welcome-page")).toBeInTheDocument();
    });
  });

  describe("Step flow (PROF-04)", () => {
    it("shows the first question after clicking Get Started", async () => {
      renderWelcomePage();

      fireEvent.click(screen.getByText("Get Started"));

      await waitFor(() => {
        expect(screen.getByText("What's your name?")).toBeInTheDocument();
      });
    });

    it("shows all 6 step questions in sequence", async () => {
      renderWelcomePage();

      fireEvent.click(screen.getByText("Get Started"));

      const questions = [
        "What's your name?",
        "Where are you based?",
        "What roles are you targeting?",
        "What's your target salary range?",
        "What are your key skills?",
        "What's your experience level?",
      ];

      for (const question of questions) {
        await waitFor(() => {
          expect(screen.getByText(question)).toBeInTheDocument();
        });
        // Skip to advance to next question
        fireEvent.click(screen.getByText("Skip"));
      }
    });

    it("shows Back, Skip, and Next buttons on step screens", async () => {
      renderWelcomePage();

      fireEvent.click(screen.getByText("Get Started"));

      await waitFor(() => {
        expect(screen.getByText("Back")).toBeInTheDocument();
        expect(screen.getByText("Skip")).toBeInTheDocument();
        expect(screen.getByText("Next")).toBeInTheDocument();
      });
    });

    it("disables Back button on the first step", async () => {
      renderWelcomePage();

      fireEvent.click(screen.getByText("Get Started"));

      await waitFor(() => {
        expect(screen.getByText("Back")).toBeDisabled();
      });
    });

    it("shows the progress bar during steps", async () => {
      renderWelcomePage();

      fireEvent.click(screen.getByText("Get Started"));

      await waitFor(() => {
        expect(screen.getByTestId("step-progress")).toBeInTheDocument();
        expect(screen.getByText("Step 1 of 6")).toBeInTheDocument();
      });
    });
  });

  describe("Summary screen (WEB-07, WEB-08, WEB-09)", () => {
    it("shows summary after completing all steps by skipping", async () => {
      renderWelcomePage();

      fireEvent.click(screen.getByText("Get Started"));

      // Skip all 6 steps
      for (let i = 0; i < 6; i++) {
        await waitFor(() => {
          expect(screen.getByText("Skip")).toBeInTheDocument();
        });
        fireEvent.click(screen.getByText("Skip"));
      }

      await waitFor(() => {
        expect(screen.getByText(/all set/i)).toBeInTheDocument();
      });
    });

    it("shows summary checklist with test id", async () => {
      renderWelcomePage();

      fireEvent.click(screen.getByText("Get Started"));

      for (let i = 0; i < 6; i++) {
        await waitFor(() => {
          expect(screen.getByText("Skip")).toBeInTheDocument();
        });
        fireEvent.click(screen.getByText("Skip"));
      }

      await waitFor(() => {
        expect(screen.getByTestId("summary-checklist")).toBeInTheDocument();
      });
    });

    it("shows AI provider nudge card (WEB-09)", async () => {
      renderWelcomePage();

      fireEvent.click(screen.getByText("Get Started"));

      for (let i = 0; i < 6; i++) {
        await waitFor(() => {
          expect(screen.getByText("Skip")).toBeInTheDocument();
        });
        fireEvent.click(screen.getByText("Skip"));
      }

      await waitFor(() => {
        expect(screen.getByTestId("ai-provider-nudge")).toBeInTheDocument();
        expect(screen.getByText("Unlock full AI scoring")).toBeInTheDocument();
        expect(screen.getByText("Configure in Settings")).toBeInTheDocument();
      });
    });

    it("shows See your scored results CTA (D-08)", async () => {
      renderWelcomePage();

      fireEvent.click(screen.getByText("Get Started"));

      for (let i = 0; i < 6; i++) {
        await waitFor(() => {
          expect(screen.getByText("Skip")).toBeInTheDocument();
        });
        fireEvent.click(screen.getByText("Skip"));
      }

      await waitFor(() => {
        expect(screen.getByTestId("see-results-cta")).toBeInTheDocument();
        expect(screen.getByText("See your scored results")).toBeInTheDocument();
      });
    });

    it("skipped steps show Settings > Profile path (WEB-08)", async () => {
      renderWelcomePage();

      fireEvent.click(screen.getByText("Get Started"));

      for (let i = 0; i < 6; i++) {
        await waitFor(() => {
          expect(screen.getByText("Skip")).toBeInTheDocument();
        });
        fireEvent.click(screen.getByText("Skip"));
      }

      await waitFor(() => {
        expect(
          screen.getByText(/update anything later in Settings/),
        ).toBeInTheDocument();
      });
    });

    it("navigates to Pipeline when CTA is clicked", async () => {
      renderWelcomePage();

      fireEvent.click(screen.getByText("Get Started"));

      for (let i = 0; i < 6; i++) {
        await waitFor(() => {
          expect(screen.getByText("Skip")).toBeInTheDocument();
        });
        fireEvent.click(screen.getByText("Skip"));
      }

      await waitFor(() => {
        expect(screen.getByTestId("see-results-cta")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId("see-results-cta"));

      // Navigation verified via Routes — clicking CTA calls navigate("/")
      // which renders the "/" route showing the pipeline-redirect element
      expect(
        await screen.findByTestId("pipeline-redirect"),
      ).toBeInTheDocument();
    });
  });

  describe("Resume logic (WEB-04)", () => {
    it("shows step screen when profile_started_at is set", async () => {
      // All profile fields empty — resume at step 1
      mockFetchProfile.mockResolvedValue(
        makeProfile({ name: "", location: null }),
      );

      renderWelcomePage({
        profile_started_at: "2026-04-21T00:00:00Z",
      });

      await waitFor(() => {
        expect(screen.getByText("What's your name?")).toBeInTheDocument();
      });
    });

    it("resumes at first empty profile field, not step 1", async () => {
      // User filled name and location, then closed browser
      mockFetchProfile.mockResolvedValue(
        makeProfile({ name: "Alice", location: "Berlin", job_family: null }),
      );

      renderWelcomePage({
        profile_started_at: "2026-04-21T00:00:00Z",
      });

      // Should resume at step 3 (job_family), skipping filled name & location
      await waitFor(() => {
        expect(
          screen.getByText("What roles are you targeting?"),
        ).toBeInTheDocument();
      });
      expect(screen.getByText("Step 3 of 6")).toBeInTheDocument();
    });

    it("shows summary screen when welcome_completed_at is set", async () => {
      renderWelcomePage({
        welcome_completed_at: "2026-04-21T00:00:00Z",
      });

      await waitFor(() => {
        expect(screen.getByText(/all set/i)).toBeInTheDocument();
      });
    });
  });

  describe("Save behavior", () => {
    it("calls updateProfile on Next with field value", async () => {
      renderWelcomePage();

      fireEvent.click(screen.getByText("Get Started"));

      await waitFor(() => {
        expect(screen.getByText("What's your name?")).toBeInTheDocument();
      });

      const input = screen.getByRole("textbox");
      fireEvent.change(input, { target: { value: "Alice" } });
      fireEvent.click(screen.getByText("Next"));

      await waitFor(() => {
        expect(mockUpdateProfile).toHaveBeenCalledWith(1, { name: "Alice" });
      });
    });

    it("calls createSkill for skills step", async () => {
      renderWelcomePage();

      fireEvent.click(screen.getByText("Get Started"));

      // Skip to skills step (step index 4)
      for (let i = 0; i < 4; i++) {
        await waitFor(() => {
          expect(screen.getByText("Skip")).toBeInTheDocument();
        });
        fireEvent.click(screen.getByText("Skip"));
      }

      await waitFor(() => {
        expect(
          screen.getByText("What are your key skills?"),
        ).toBeInTheDocument();
      });

      const input = screen.getByRole("textbox");
      fireEvent.change(input, { target: { value: "TypeScript, React" } });
      fireEvent.click(screen.getByText("Next"));

      await waitFor(() => {
        expect(mockCreateSkill).toHaveBeenCalledWith({
          profile_id: 1,
          name: "TypeScript",
          category: "technical",
          evidence_source: "onboarding",
        });
        expect(mockCreateSkill).toHaveBeenCalledWith({
          profile_id: 1,
          name: "React",
          category: "technical",
          evidence_source: "onboarding",
        });
      });
    });

    it("treats empty Next as skip (no API call)", async () => {
      renderWelcomePage();

      fireEvent.click(screen.getByText("Get Started"));

      await waitFor(() => {
        expect(screen.getByText("What's your name?")).toBeInTheDocument();
      });

      // Click Next with empty input
      fireEvent.click(screen.getByText("Next"));

      await waitFor(() => {
        // Should advance to step 2 without calling updateProfile
        expect(screen.getByText("Where are you based?")).toBeInTheDocument();
      });
      expect(mockUpdateProfile).not.toHaveBeenCalled();
    });
  });

  describe("Error handling", () => {
    it("shows error message when save fails", async () => {
      mockUpdateProfile.mockRejectedValueOnce(new Error("Network error"));
      renderWelcomePage();

      fireEvent.click(screen.getByText("Get Started"));

      await waitFor(() => {
        expect(screen.getByText("What's your name?")).toBeInTheDocument();
      });

      const input = screen.getByRole("textbox");
      fireEvent.change(input, { target: { value: "Test User" } });
      fireEvent.click(screen.getByText("Next"));

      await waitFor(() => {
        expect(
          screen.getByText(/Couldn't save your answer/),
        ).toBeInTheDocument();
      });
    });
  });
});
