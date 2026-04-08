/**
 * Tests for the ApplicationDetail page.
 *
 * Covers:
 * - VAL-PIPE-002: Detail page shows all fields
 * - VAL-PIPE-003: Edit and save persists, activity log entry
 * - VAL-PIPE-006: Archive removes from board
 * - VAL-PIPE-012: Activity log in reverse chronological order
 */

import { render, screen, within, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ApplicationDetail } from "@/pages/ApplicationDetail";
import type { ApplicationDetailResponse } from "@/api/types";

// ---- mocks ----

const mockFetchDetail = vi.fn<() => Promise<ApplicationDetailResponse>>();
const mockUpdateApplication = vi.fn();
const mockArchiveApplication = vi.fn();
const mockFetchApplications = vi.fn();

vi.mock("@/api/applications", () => ({
  fetchApplicationDetail: (...args: unknown[]) => mockFetchDetail(...(args as [])),
  updateApplication: (...args: unknown[]) => mockUpdateApplication(...(args as [])),
  archiveApplication: (...args: unknown[]) => mockArchiveApplication(...(args as [])),
  fetchApplications: (...args: unknown[]) => mockFetchApplications(...(args as [])),
  createApplication: vi.fn(),
}));

vi.mock("@/api/followUps", () => ({
  fetchOverdueCount: vi.fn().mockResolvedValue({ count: 0 }),
  fetchFollowUps: vi.fn().mockResolvedValue({ follow_ups: [], total: 0 }),
  createFollowUp: vi.fn(),
  completeFollowUp: vi.fn(),
}));

vi.mock("@/api/calendar", () => ({
  fetchCalendarEvents: vi.fn().mockResolvedValue({ events: [], total: 0 }),
  createCalendarEvent: vi.fn(),
  getICalExportUrl: vi.fn().mockReturnValue("/api/calendar/events/1/ical?profile_id=1"),
  fetchGoogleCalendarUrl: vi.fn().mockResolvedValue({ url: "https://calendar.google.com", event_id: 1 }),
  deleteCalendarEvent: vi.fn(),
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

function renderDetail(id = "42") {
  const qc = createQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/applications/${id}`]}>
        <Routes>
          <Route path="/applications/:id" element={<ApplicationDetail />} />
          <Route path="/" element={<div data-testid="pipeline-page">Pipeline</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const SAMPLE_DETAIL: ApplicationDetailResponse = {
  id: 42,
  profile_id: 1,
  company: "Mistral AI",
  role: "TPM DACH",
  url: "https://jobs.mistral.ai/tpm-dach",
  source: "LinkedIn",
  status: "applied",
  salary_range: "120-140k EUR",
  contact: "Jane Smith",
  next_step: "Schedule interview",
  notes: "Great AI company, strong fit",
  fit_score: 8.5,
  date_applied: "2026-03-05T10:00:00Z",
  created_at: "2026-03-01T08:00:00Z",
  updated_at: "2026-03-10T14:30:00Z",
  archived_at: null,
  is_ghost: false,
  follow_ups: [],
  activity_log: [
    {
      id: 3,
      action: "updated",
      details: "Updated fields: notes",
      source: "api",
      created_at: "2026-03-10T14:30:00Z",
    },
    {
      id: 2,
      action: "status_changed",
      details: "Status changed from 'interested' to 'applied'",
      source: "api",
      created_at: "2026-03-05T10:00:00Z",
    },
    {
      id: 1,
      action: "created",
      details: "Created application for Mistral AI — TPM DACH",
      source: "api",
      created_at: "2026-03-01T08:00:00Z",
    },
  ],
};

// ---- tests ----

describe("ApplicationDetail", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("shows loading state while fetching", () => {
    mockFetchDetail.mockReturnValue(new Promise(() => {}));
    renderDetail();
    expect(screen.getByTestId("detail-loading")).toBeInTheDocument();
  });

  it("shows error when application not found", async () => {
    mockFetchDetail.mockRejectedValue(new Error("Application not found"));
    renderDetail();
    expect(await screen.findByTestId("detail-error")).toBeInTheDocument();
    // Should show archived/removed state for 404
    expect(screen.getByTestId("detail-removed")).toBeInTheDocument();
    expect(
      screen.getByText("This application has been archived or removed."),
    ).toBeInTheDocument();
  });

  describe("detail page with data", () => {
    beforeEach(() => {
      mockFetchDetail.mockResolvedValue(SAMPLE_DETAIL);
    });

    it("renders the detail page container", async () => {
      renderDetail();
      expect(
        await screen.findByTestId("application-detail"),
      ).toBeInTheDocument();
    });

    it("shows company and role in header", async () => {
      renderDetail();
      await screen.findByTestId("application-detail");
      expect(screen.getByText("Mistral AI — TPM DACH")).toBeInTheDocument();
    });

    it("shows status badge", async () => {
      renderDetail();
      const badge = await screen.findByTestId("detail-status-badge");
      expect(badge).toHaveTextContent("Applied");
    });

    it("shows all application fields", async () => {
      renderDetail();
      await screen.findByTestId("application-detail");

      expect(screen.getByTestId("field-company")).toHaveTextContent("Mistral AI");
      expect(screen.getByTestId("field-role")).toHaveTextContent("TPM DACH");
      expect(screen.getByTestId("field-source")).toHaveTextContent("LinkedIn");
      expect(screen.getByTestId("field-salary")).toHaveTextContent("120-140k EUR");
      expect(screen.getByTestId("field-contact")).toHaveTextContent("Jane Smith");
      expect(screen.getByTestId("field-score")).toHaveTextContent("8.5");
      expect(screen.getByTestId("field-notes")).toHaveTextContent(
        "Great AI company, strong fit",
      );
      expect(screen.getByTestId("field-next-step")).toHaveTextContent(
        "Schedule interview",
      );
    });

    it("shows URL as a link", async () => {
      renderDetail();
      await screen.findByTestId("application-detail");
      const urlField = screen.getByTestId("field-url");
      const link = within(urlField).getByRole("link");
      expect(link).toHaveAttribute("href", "https://jobs.mistral.ai/tpm-dach");
    });

    it("shows date fields", async () => {
      renderDetail();
      await screen.findByTestId("application-detail");
      expect(screen.getByTestId("field-created-at")).not.toHaveTextContent("—");
      expect(screen.getByTestId("field-updated-at")).not.toHaveTextContent("—");
      expect(screen.getByTestId("field-date-applied")).not.toHaveTextContent("—");
    });

    it("shows activity log in reverse chronological order", async () => {
      renderDetail();
      await screen.findByTestId("application-detail");

      const log = screen.getByTestId("activity-log");
      const entries = within(log).getAllByTestId(/^activity-entry-/);
      expect(entries).toHaveLength(3);

      // First entry should be the most recent (id=3)
      expect(entries[0]).toHaveAttribute("data-testid", "activity-entry-3");
      // Last entry should be the oldest (id=1)
      expect(entries[2]).toHaveAttribute("data-testid", "activity-entry-1");
    });

    it("activity log entries show action and details", async () => {
      renderDetail();
      await screen.findByTestId("application-detail");

      const entry = screen.getByTestId("activity-entry-2");
      expect(entry).toHaveTextContent("status changed");
      expect(entry).toHaveTextContent(
        "Status changed from 'interested' to 'applied'",
      );
    });

    it("has back to pipeline link", async () => {
      renderDetail();
      await screen.findByTestId("application-detail");
      expect(screen.getByTestId("back-to-pipeline")).toBeInTheDocument();
    });

    it("has edit button", async () => {
      renderDetail();
      await screen.findByTestId("application-detail");
      expect(screen.getByTestId("edit-button")).toBeInTheDocument();
    });

    it("has archive button", async () => {
      renderDetail();
      await screen.findByTestId("application-detail");
      expect(screen.getByTestId("archive-button")).toBeInTheDocument();
    });
  });

  describe("edit mode", () => {
    beforeEach(() => {
      mockFetchDetail.mockResolvedValue(SAMPLE_DETAIL);
    });

    it("shows editable fields after clicking edit", async () => {
      renderDetail();
      await screen.findByTestId("application-detail");

      fireEvent.click(screen.getByTestId("edit-button"));

      expect(screen.getByTestId("field-salary-input")).toBeInTheDocument();
      expect(screen.getByTestId("field-notes-input")).toBeInTheDocument();
      expect(screen.getByTestId("field-company-input")).toBeInTheDocument();
    });

    it("shows save and cancel buttons in edit mode", async () => {
      renderDetail();
      await screen.findByTestId("application-detail");

      fireEvent.click(screen.getByTestId("edit-button"));

      expect(screen.getByTestId("save-button")).toBeInTheDocument();
      expect(screen.getByTestId("cancel-edit-button")).toBeInTheDocument();
    });

    it("cancel restores original values", async () => {
      renderDetail();
      await screen.findByTestId("application-detail");

      fireEvent.click(screen.getByTestId("edit-button"));

      const salaryInput = screen.getByTestId("field-salary-input");
      fireEvent.change(salaryInput, { target: { value: "200k EUR" } });

      fireEvent.click(screen.getByTestId("cancel-edit-button"));

      expect(screen.getByTestId("field-salary")).toHaveTextContent(
        "120-140k EUR",
      );
    });

    it("save calls update API with changed fields", async () => {
      mockUpdateApplication.mockResolvedValue({
        ...SAMPLE_DETAIL,
        salary_range: "200k EUR",
      });

      renderDetail();
      await screen.findByTestId("application-detail");

      fireEvent.click(screen.getByTestId("edit-button"));

      const salaryInput = screen.getByTestId("field-salary-input");
      fireEvent.change(salaryInput, { target: { value: "200k EUR" } });

      fireEvent.click(screen.getByTestId("save-button"));

      await waitFor(() => {
        expect(mockUpdateApplication).toHaveBeenCalledWith(42, {
          salary_range: "200k EUR",
        });
      });
    });
  });

  describe("archive", () => {
    beforeEach(() => {
      mockFetchDetail.mockResolvedValue(SAMPLE_DETAIL);
    });

    it("archive navigates back to pipeline on success", async () => {
      mockArchiveApplication.mockResolvedValue({
        ...SAMPLE_DETAIL,
        archived_at: "2026-03-10T15:00:00Z",
      });

      renderDetail();
      await screen.findByTestId("application-detail");

      fireEvent.click(screen.getByTestId("archive-button"));

      await waitFor(() => {
        expect(mockArchiveApplication).toHaveBeenCalledWith(42);
      });

      // After archive, should navigate to pipeline
      await waitFor(() => {
        expect(screen.getByTestId("pipeline-page")).toBeInTheDocument();
      });
    });
  });

  describe("empty activity log", () => {
    it("shows empty message when no activity", async () => {
      mockFetchDetail.mockResolvedValue({
        ...SAMPLE_DETAIL,
        activity_log: [],
      });
      renderDetail();
      await screen.findByTestId("application-detail");
      expect(screen.getByTestId("activity-log-empty")).toBeInTheDocument();
    });
  });

  describe("calendar section", () => {
    it("renders calendar section on detail page", async () => {
      mockFetchDetail.mockResolvedValue(SAMPLE_DETAIL);
      renderDetail();
      await screen.findByTestId("application-detail");
      expect(screen.getByTestId("calendar-section")).toBeInTheDocument();
    });

    it("shows add to calendar button", async () => {
      mockFetchDetail.mockResolvedValue(SAMPLE_DETAIL);
      renderDetail();
      await screen.findByTestId("application-detail");
      expect(screen.getByTestId("add-calendar-event-button")).toBeInTheDocument();
    });

    it("shows empty state when no events", async () => {
      mockFetchDetail.mockResolvedValue(SAMPLE_DETAIL);
      renderDetail();
      await screen.findByTestId("application-detail");
      await waitFor(() => {
        expect(screen.getByTestId("calendar-events-empty")).toBeInTheDocument();
      });
    });
  });
});
