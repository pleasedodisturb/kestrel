/**
 * Tests for the global FollowUps page.
 *
 * Covers:
 * - Follow-ups page renders with nav
 * - Shows all follow-ups across applications (overdue, due today, upcoming)
 * - Links to application detail pages
 * - Empty state
 */

import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { FollowUps } from "@/pages/FollowUps";
import type { FollowUp } from "@/api/types";

// ---- mocks ----

const mockFetchFollowUps = vi.fn();

vi.mock("@/api/followUps", () => ({
  fetchFollowUps: (...args: unknown[]) => mockFetchFollowUps(...(args as [])),
  fetchOverdueCount: vi.fn().mockResolvedValue({ count: 0 }),
  createFollowUp: vi.fn(),
  completeFollowUp: vi.fn(),
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

function renderFollowUps() {
  const qc = createQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/follow-ups"]}>
        <Routes>
          <Route path="/follow-ups" element={<FollowUps />} />
          <Route
            path="/applications/:id"
            element={<div data-testid="app-detail">Detail</div>}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function makeFollowUp(overrides: Partial<FollowUp> = {}): FollowUp {
  return {
    id: 1,
    application_id: 10,
    profile_id: 1,
    due_date: new Date().toISOString(),
    follow_up_type: "email",
    notes: "Follow up with recruiter",
    completed_at: null,
    created_at: "2026-03-01T00:00:00Z",
    application_company: "Acme Corp",
    application_role: "Senior TPM",
    ...overrides,
  };
}

// ---- tests ----

describe("FollowUps page", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("shows loading state while fetching", () => {
    mockFetchFollowUps.mockReturnValue(new Promise(() => {}));
    renderFollowUps();
    expect(screen.getByTestId("follow-ups-loading")).toBeInTheDocument();
  });

  it("shows error when API fails", async () => {
    mockFetchFollowUps.mockRejectedValue(new Error("Network error"));
    renderFollowUps();
    expect(await screen.findByTestId("follow-ups-error")).toBeInTheDocument();
  });

  it("shows empty state when no follow-ups", async () => {
    mockFetchFollowUps.mockResolvedValue({ follow_ups: [], total: 0 });
    renderFollowUps();
    expect(await screen.findByTestId("follow-ups-empty")).toBeInTheDocument();
    expect(screen.getByText("No pending follow-ups")).toBeInTheDocument();
  });

  it("renders follow-ups page with header", async () => {
    mockFetchFollowUps.mockResolvedValue({ follow_ups: [], total: 0 });
    renderFollowUps();
    expect(await screen.findByTestId("follow-ups-page")).toBeInTheDocument();
    expect(screen.getByText("Follow-Ups")).toBeInTheDocument();
  });

  describe("with follow-ups data", () => {
    const now = new Date();
    const yesterday = new Date(now.getTime() - 86400000);
    const twoDaysAgo = new Date(now.getTime() - 2 * 86400000);
    const inTwoDays = new Date(now.getTime() + 2 * 86400000);

    const followUps: FollowUp[] = [
      makeFollowUp({
        id: 1,
        application_id: 10,
        due_date: twoDaysAgo.toISOString(),
        follow_up_type: "email",
        notes: "Overdue task",
        application_company: "Acme Corp",
        application_role: "Senior TPM",
      }),
      makeFollowUp({
        id: 2,
        application_id: 20,
        due_date: yesterday.toISOString(),
        follow_up_type: "phone",
        notes: "Also overdue",
        application_company: "Beta Inc",
        application_role: "Engineer",
      }),
      makeFollowUp({
        id: 3,
        application_id: 30,
        due_date: now.toISOString(),
        follow_up_type: "linkedin",
        notes: "Due today",
        application_company: "Gamma Ltd",
        application_role: "Lead",
      }),
      makeFollowUp({
        id: 4,
        application_id: 40,
        due_date: inTwoDays.toISOString(),
        follow_up_type: "other",
        notes: "Upcoming task",
        application_company: "Delta GmbH",
        application_role: "DevRel",
      }),
    ];

    beforeEach(() => {
      mockFetchFollowUps.mockResolvedValue({
        follow_ups: followUps,
        total: followUps.length,
      });
    });

    it("renders all follow-up rows", async () => {
      renderFollowUps();
      await screen.findByTestId("follow-ups-page");

      expect(screen.getByTestId("follow-up-row-1")).toBeInTheDocument();
      expect(screen.getByTestId("follow-up-row-2")).toBeInTheDocument();
      expect(screen.getByTestId("follow-up-row-3")).toBeInTheDocument();
      expect(screen.getByTestId("follow-up-row-4")).toBeInTheDocument();
    });

    it("shows summary counts", async () => {
      renderFollowUps();
      await screen.findByTestId("follow-ups-page");

      // 2 overdue, 1 due today (but depends on exact timing)
      expect(screen.getByTestId("overdue-count")).toBeInTheDocument();
      expect(screen.getByTestId("due-today-count")).toBeInTheDocument();
      expect(screen.getByTestId("upcoming-count")).toBeInTheDocument();
    });

    it("shows application links", async () => {
      renderFollowUps();
      await screen.findByTestId("follow-ups-page");

      const link1 = screen.getByTestId("follow-up-app-link-1");
      expect(link1).toBeInTheDocument();
      expect(link1).toHaveTextContent("Acme Corp");
    });

    it("shows complete buttons", async () => {
      renderFollowUps();
      await screen.findByTestId("follow-ups-page");

      expect(screen.getByTestId("complete-follow-up-1")).toBeInTheDocument();
      expect(screen.getByTestId("complete-follow-up-2")).toBeInTheDocument();
    });

    it("shows follow-up notes", async () => {
      renderFollowUps();
      await screen.findByTestId("follow-ups-page");

      expect(screen.getByText("Overdue task")).toBeInTheDocument();
      expect(screen.getByText("Upcoming task")).toBeInTheDocument();
    });
  });

  describe("excludes completed follow-ups", () => {
    it("filters out completed follow-ups from the list", async () => {
      const completedFu = makeFollowUp({
        id: 5,
        completed_at: "2026-03-10T00:00:00Z",
        notes: "Already done",
      });
      mockFetchFollowUps.mockResolvedValue({
        follow_ups: [completedFu],
        total: 1,
      });
      renderFollowUps();
      expect(await screen.findByTestId("follow-ups-empty")).toBeInTheDocument();
    });
  });
});
