/**
 * Tests for the Kanban pipeline board.
 *
 * Covers:
 * - 8 status columns rendered (VAL-PIPE-007)
 * - Empty columns show placeholder
 * - Empty board (zero apps) shows CTA (VAL-PIPE-014)
 * - Cards show company, role, score
 * - Card count matches total applications
 * - Migrated data in correct columns (VAL-PIPE-008)
 * - Loading and error states
 * - Cross-column drag triggers PATCH (VAL-PIPE-004)
 * - Same-column drop is a no-op
 * - Dropping card on itself is a no-op
 */

import { render, screen, within, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { KanbanBoard } from "@/components/KanbanBoard";
import type { Application, ApplicationListResponse, ApplicationStatus } from "@/api/types";

// ---- capture DndContext callbacks ----

// We capture the onDragStart, onDragOver, onDragEnd callbacks passed to
// DndContext so we can invoke them programmatically in tests.
let capturedOnDragStart: ((...args: unknown[]) => void) | undefined;
let capturedOnDragOver: ((...args: unknown[]) => void) | undefined;
let capturedOnDragEnd: ((...args: unknown[]) => void) | undefined;

vi.mock("@dnd-kit/core", async () => {
  const actual = await vi.importActual<typeof import("@dnd-kit/core")>("@dnd-kit/core");
  return {
    ...actual,
    DndContext: ({ children, onDragStart, onDragOver, onDragEnd, ...rest }: Record<string, unknown>) => {
      capturedOnDragStart = onDragStart as typeof capturedOnDragStart;
      capturedOnDragOver = onDragOver as typeof capturedOnDragOver;
      capturedOnDragEnd = onDragEnd as typeof capturedOnDragEnd;
      // Render a wrapper that still renders children (columns / cards)
      return <div data-testid="dnd-context-mock" {...rest}>{children as React.ReactNode}</div>;
    },
    DragOverlay: ({ children }: Record<string, unknown>) => <div>{children as React.ReactNode}</div>,
  };
});

// ---- mocks ----

const mockFetchApplications = vi.fn<() => Promise<ApplicationListResponse>>();
const mockUpdateApplication = vi.fn();

vi.mock("@/api/applications", () => ({
  fetchApplications: (...args: unknown[]) => mockFetchApplications(...(args as [])),
  updateApplication: (...args: unknown[]) => mockUpdateApplication(...(args as [])),
  createApplication: vi.fn(),
  archiveApplication: vi.fn(),
  fetchApplicationDetail: vi.fn(),
}));

vi.mock("@/api/followUps", () => ({
  fetchOverdueCount: vi.fn().mockResolvedValue({ count: 0 }),
  fetchFollowUps: vi.fn().mockResolvedValue({ follow_ups: [], total: 0 }),
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

function renderBoard() {
  const qc = createQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <KanbanBoard />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function makeApp(
  overrides: Partial<{
    id: number;
    company: string;
    role: string;
    status: ApplicationStatus;
    fit_score: number | null;
    is_ghost: boolean;
  }> = {},
): Application {
  return {
    id: overrides.id ?? 1,
    profile_id: 1,
    company: overrides.company ?? "Acme Corp",
    role: overrides.role ?? "Senior Engineer",
    url: null,
    source: null,
    status: overrides.status ?? "discovered",
    salary_range: null,
    contact: null,
    next_step: null,
    notes: null,
    fit_score: overrides.fit_score ?? null,
    date_applied: null,
    created_at: "2026-03-01T00:00:00Z",
    updated_at: "2026-03-01T00:00:00Z",
    archived_at: null,
    is_ghost: overrides.is_ghost ?? false,
  };
}

// ---- tests ----

describe("KanbanBoard", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("shows loading state while fetching", () => {
    // Return a promise that never resolves
    mockFetchApplications.mockReturnValue(new Promise(() => {}));
    renderBoard();
    expect(screen.getByTestId("kanban-loading")).toBeInTheDocument();
  });

  it("shows error state when fetch fails", async () => {
    mockFetchApplications.mockRejectedValue(new Error("Network error"));
    renderBoard();
    expect(await screen.findByTestId("kanban-error")).toBeInTheDocument();
    expect(screen.getByText("Network error")).toBeInTheDocument();
  });

  describe("empty board (zero applications)", () => {
    beforeEach(() => {
      mockFetchApplications.mockResolvedValue({
        applications: [],
        total: 0,
      });
    });

    it("shows empty state CTA", async () => {
      renderBoard();
      expect(await screen.findByTestId("kanban-empty")).toBeInTheDocument();
    });

    it("shows friendly message", async () => {
      renderBoard();
      expect(
        await screen.findByText("No applications yet"),
      ).toBeInTheDocument();
    });

    it("shows Add Application button", async () => {
      renderBoard();
      expect(
        await screen.findByTestId("kanban-add-cta"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Add Application"),
      ).toBeInTheDocument();
    });
  });

  describe("board with applications", () => {
    const apps = [
      makeApp({ id: 1, company: "Mistral AI", role: "TPM DACH", status: "applied", fit_score: 8.5 }),
      makeApp({ id: 2, company: "Plain", role: "Product Engineer", status: "applied", fit_score: 9.5 }),
      makeApp({ id: 3, company: "Shopware", role: "TPM", status: "interested", fit_score: 8.5 }),
      makeApp({ id: 4, company: "DataDog", role: "SRE", status: "discovered", fit_score: 7.0 }),
      makeApp({ id: 5, company: "Ghost Inc", role: "DevRel", status: "ghosted", fit_score: null }),
    ];

    beforeEach(() => {
      mockFetchApplications.mockResolvedValue({
        applications: apps,
        total: apps.length,
      });
    });

    it("renders all 8 status columns", async () => {
      renderBoard();
      await screen.findByTestId("kanban-board");
      const statuses = [
        "discovered",
        "interested",
        "applied",
        "interviewing",
        "offer",
        "accepted",
        "rejected",
        "ghosted",
      ];
      for (const s of statuses) {
        expect(screen.getByTestId(`kanban-column-${s}`)).toBeInTheDocument();
      }
    });

    it("shows correct column headers", async () => {
      renderBoard();
      const board = await screen.findByTestId("kanban-board");
      expect(within(board).getByText("Discovered")).toBeInTheDocument();
      expect(within(board).getByText("Interested")).toBeInTheDocument();
      expect(within(board).getByText("Applied")).toBeInTheDocument();
      expect(within(board).getByText("Interviewing")).toBeInTheDocument();
      expect(within(board).getByText("Offer")).toBeInTheDocument();
      expect(within(board).getByText("Accepted")).toBeInTheDocument();
      expect(within(board).getByText("Rejected")).toBeInTheDocument();
      expect(within(board).getByText("Ghosted")).toBeInTheDocument();
    });

    it("empty columns show placeholder text", async () => {
      renderBoard();
      await screen.findByTestId("kanban-board");
      // Interviewing, Offer, Accepted, Rejected should be empty
      expect(
        screen.getByTestId("column-empty-interviewing"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("column-empty-offer"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("column-empty-accepted"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("column-empty-rejected"),
      ).toBeInTheDocument();
    });

    it("cards appear in correct columns matching status", async () => {
      renderBoard();
      await screen.findByTestId("kanban-board");

      // Discovered column should contain DataDog
      const discoveredCol = screen.getByTestId("kanban-column-discovered");
      expect(within(discoveredCol).getByText("DataDog")).toBeInTheDocument();

      // Interested column should contain Shopware
      const interestedCol = screen.getByTestId("kanban-column-interested");
      expect(within(interestedCol).getByText("Shopware")).toBeInTheDocument();

      // Applied column should contain Mistral and Plain
      const appliedCol = screen.getByTestId("kanban-column-applied");
      expect(within(appliedCol).getByText("Mistral AI")).toBeInTheDocument();
      expect(within(appliedCol).getByText("Plain")).toBeInTheDocument();

      // Ghosted column should contain Ghost Inc
      const ghostedCol = screen.getByTestId("kanban-column-ghosted");
      expect(within(ghostedCol).getByText("Ghost Inc")).toBeInTheDocument();
    });

    it("cards show company name", async () => {
      renderBoard();
      await screen.findByTestId("kanban-board");
      expect(screen.getByText("Mistral AI")).toBeInTheDocument();
    });

    it("cards show role", async () => {
      renderBoard();
      await screen.findByTestId("kanban-board");
      expect(screen.getByText("TPM DACH")).toBeInTheDocument();
    });

    it("cards show fit score when available", async () => {
      renderBoard();
      await screen.findByTestId("kanban-board");
      expect(screen.getByTestId("score-badge-1")).toHaveTextContent("8.5");
      expect(screen.getByTestId("score-badge-2")).toHaveTextContent("9.5");
    });

    it("cards without score don't show score badge", async () => {
      renderBoard();
      await screen.findByTestId("kanban-board");
      expect(screen.queryByTestId("score-badge-5")).not.toBeInTheDocument();
    });

    it("total card count matches application count", async () => {
      renderBoard();
      const totalBadge = await screen.findByTestId("kanban-total-count");
      expect(totalBadge).toHaveTextContent("5 applications");
    });

    it("column counts are correct", async () => {
      renderBoard();
      await screen.findByTestId("kanban-board");
      expect(screen.getByTestId("column-count-discovered")).toHaveTextContent("1");
      expect(screen.getByTestId("column-count-interested")).toHaveTextContent("1");
      expect(screen.getByTestId("column-count-applied")).toHaveTextContent("2");
      expect(screen.getByTestId("column-count-interviewing")).toHaveTextContent("0");
      expect(screen.getByTestId("column-count-offer")).toHaveTextContent("0");
      expect(screen.getByTestId("column-count-accepted")).toHaveTextContent("0");
      expect(screen.getByTestId("column-count-rejected")).toHaveTextContent("0");
      expect(screen.getByTestId("column-count-ghosted")).toHaveTextContent("1");
    });
  });

  describe("grade badge colors", () => {
    // Score-to-grade mapping lives in ``lib/gradeUtils.ts``:
    //   A/A-  -> green, B+/B -> emerald, C+/C -> yellow, D -> orange, F -> red
    it("A grade (≥9) shows green badge", async () => {
      mockFetchApplications.mockResolvedValue({
        applications: [makeApp({ id: 1, fit_score: 9.0 })],
        total: 1,
      });
      renderBoard();
      const badge = await screen.findByTestId("score-badge-1");
      expect(badge.className).toContain("bg-green-100");
      expect(badge.textContent).toContain("A");
    });

    it("B grade (6-6.9) shows emerald badge", async () => {
      mockFetchApplications.mockResolvedValue({
        applications: [makeApp({ id: 1, fit_score: 6.5 })],
        total: 1,
      });
      renderBoard();
      const badge = await screen.findByTestId("score-badge-1");
      expect(badge.className).toContain("bg-emerald-100");
      expect(badge.textContent).toContain("B");
    });

    it("D grade (3-3.9) shows orange badge", async () => {
      mockFetchApplications.mockResolvedValue({
        applications: [makeApp({ id: 1, fit_score: 3.0 })],
        total: 1,
      });
      renderBoard();
      const badge = await screen.findByTestId("score-badge-1");
      expect(badge.className).toContain("bg-orange-100");
      expect(badge.textContent).toContain("D");
    });

    it("F grade (<3) shows red badge", async () => {
      mockFetchApplications.mockResolvedValue({
        applications: [makeApp({ id: 1, fit_score: 2.0 })],
        total: 1,
      });
      renderBoard();
      const badge = await screen.findByTestId("score-badge-1");
      expect(badge.className).toContain("bg-red-100");
      expect(badge.textContent).toContain("F");
    });
  });

  describe("singular/plural label", () => {
    it("shows 'application' (singular) for 1 app", async () => {
      mockFetchApplications.mockResolvedValue({
        applications: [makeApp({ id: 1 })],
        total: 1,
      });
      renderBoard();
      const totalBadge = await screen.findByTestId("kanban-total-count");
      expect(totalBadge).toHaveTextContent("1 application");
      expect(totalBadge.textContent).not.toContain("applications");
    });
  });

  describe("drag-and-drop status transitions (VAL-PIPE-004)", () => {
    const dndApps = [
      makeApp({ id: 10, company: "SourceCo", role: "SWE", status: "discovered" }),
      makeApp({ id: 20, company: "TargetCo", role: "PM", status: "interested" }),
    ];

    beforeEach(() => {
      mockFetchApplications.mockResolvedValue({
        applications: dndApps,
        total: dndApps.length,
      });
      mockUpdateApplication.mockResolvedValue(dndApps[0]);
    });

    it("cross-column drag via column droppable triggers PATCH with new status", async () => {
      renderBoard();
      await screen.findByTestId("kanban-board");

      // Simulate: drag card 10 (discovered) → drop on "interested" column
      act(() => {
        capturedOnDragStart?.({ active: { id: 10 } } as never);
      });
      act(() => {
        capturedOnDragOver?.({ active: { id: 10 }, over: { id: "interested" } } as never);
      });
      act(() => {
        capturedOnDragEnd?.({ active: { id: 10 }, over: { id: "interested" } } as never);
      });

      await waitFor(() => {
        expect(mockUpdateApplication).toHaveBeenCalledWith(
          10,
          { status: "interested" },
        );
      });
    });

    it("cross-column drag landing on a card in another column triggers PATCH via tracked column", async () => {
      renderBoard();
      await screen.findByTestId("kanban-board");

      // Simulate: drag card 10 (discovered), hover over "interested" column,
      // but closestCorners resolves over.id to card 20 (in interested column)
      act(() => {
        capturedOnDragStart?.({ active: { id: 10 } } as never);
      });
      act(() => {
        capturedOnDragOver?.({ active: { id: 10 }, over: { id: 20 } } as never);
      });
      act(() => {
        // over.id is card 20 (not a status string) — handler must use tracked column
        capturedOnDragEnd?.({ active: { id: 10 }, over: { id: 20 } } as never);
      });

      await waitFor(() => {
        expect(mockUpdateApplication).toHaveBeenCalledWith(
          10,
          { status: "interested" },
        );
      });
    });

    it("dropping card on same column is a no-op", async () => {
      renderBoard();
      await screen.findByTestId("kanban-board");

      // Drag card 10 (discovered) and drop on "discovered" column
      act(() => {
        capturedOnDragStart?.({ active: { id: 10 } } as never);
      });
      act(() => {
        capturedOnDragOver?.({ active: { id: 10 }, over: { id: "discovered" } } as never);
      });
      act(() => {
        capturedOnDragEnd?.({ active: { id: 10 }, over: { id: "discovered" } } as never);
      });

      expect(mockUpdateApplication).not.toHaveBeenCalled();
    });

    it("dropping card on itself is a no-op", async () => {
      renderBoard();
      await screen.findByTestId("kanban-board");

      act(() => {
        capturedOnDragStart?.({ active: { id: 10 } } as never);
      });
      act(() => {
        capturedOnDragEnd?.({ active: { id: 10 }, over: { id: 10 } } as never);
      });

      expect(mockUpdateApplication).not.toHaveBeenCalled();
    });

    it("dropping with no over target is a no-op", async () => {
      renderBoard();
      await screen.findByTestId("kanban-board");

      act(() => {
        capturedOnDragStart?.({ active: { id: 10 } } as never);
      });
      act(() => {
        capturedOnDragEnd?.({ active: { id: 10 }, over: null } as never);
      });

      expect(mockUpdateApplication).not.toHaveBeenCalled();
    });
  });
});
