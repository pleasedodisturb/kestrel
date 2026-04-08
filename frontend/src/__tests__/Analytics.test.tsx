/**
 * Tests for the Analytics dashboard page.
 *
 * Covers:
 * - VAL-ANALYTICS-001: Conversion funnel
 * - VAL-ANALYTICS-002: Response rate
 * - VAL-ANALYTICS-003: Time-in-stage
 * - VAL-ANALYTICS-004: Applications over time
 * - VAL-ANALYTICS-005: Score distribution
 * - VAL-ANALYTICS-006: Empty state handling
 */

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { Analytics } from "@/pages/Analytics";
import type { AnalyticsData } from "@/api/analytics";

// ---- Recharts mock (renders text content only in jsdom) ----

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "responsive-container" }, children),
  BarChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "bar-chart" }, children),
  AreaChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "area-chart" }, children),
  Bar: () => null,
  Area: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  Cell: () => null,
}));

// ---- API mock ----

const mockFetchAnalytics = vi.fn<() => Promise<AnalyticsData>>();

vi.mock("@/api/analytics", () => ({
  fetchAnalytics: (...args: unknown[]) => mockFetchAnalytics(...(args as [])),
}));

vi.mock("@/api/timingsapp", () => ({
  fetchTimeAnalytics: vi.fn().mockResolvedValue({
    total_hours: 0,
    total_sessions: 0,
    category_breakdown: [],
    weekly_trend: [],
    avg_daily_hours: 0,
  }),
  fetchRunningSession: vi.fn().mockResolvedValue(null),
  startTimeSession: vi.fn(),
  stopTimeSession: vi.fn(),
  fetchTimeSessions: vi.fn().mockResolvedValue({ sessions: [], total: 0 }),
}));

// ---- Helpers ----

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  });
}

function renderAnalytics() {
  const qc = createQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Analytics />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const EMPTY_DATA: AnalyticsData = {
  conversion_funnel: [
    { stage: "discovered", count: 0, percentage: 0 },
    { stage: "interested", count: 0, percentage: 0 },
    { stage: "applied", count: 0, percentage: 0 },
    { stage: "interviewing", count: 0, percentage: 0 },
    { stage: "offer", count: 0, percentage: 0 },
    { stage: "accepted", count: 0, percentage: 0 },
    { stage: "rejected", count: 0, percentage: 0 },
    { stage: "ghosted", count: 0, percentage: 0 },
  ],
  response_rate: null,
  time_in_stage: [
    { stage: "discovered", avg_days: null },
    { stage: "interested", avg_days: null },
    { stage: "applied", avg_days: null },
    { stage: "interviewing", avg_days: null },
    { stage: "offer", avg_days: null },
    { stage: "accepted", avg_days: null },
    { stage: "rejected", avg_days: null },
    { stage: "ghosted", avg_days: null },
  ],
  applications_over_time: [],
  score_distribution: [
    { range: "0-2", count: 0 },
    { range: "2-4", count: 0 },
    { range: "4-6", count: 0 },
    { range: "6-8", count: 0 },
    { range: "8-10", count: 0 },
  ],
};

const POPULATED_DATA: AnalyticsData = {
  conversion_funnel: [
    { stage: "discovered", count: 10, percentage: 40 },    // 10/25 * 100
    { stage: "interested", count: 5, percentage: 50 },     // 5/10 (interested/discovered)
    { stage: "applied", count: 4, percentage: 80 },        // 4/5 (applied/interested)
    { stage: "interviewing", count: 3, percentage: 75 },   // 3/4 (interviewing/applied)
    { stage: "offer", count: 1, percentage: 33.3 },        // 1/3 (offer/interviewing)
    { stage: "accepted", count: 1, percentage: 100 },      // 1/1 (accepted/offer)
    { stage: "rejected", count: 1, percentage: 100 },      // 1/1 (rejected/offer)
    { stage: "ghosted", count: 0, percentage: 0 },
  ],
  response_rate: 40.0,
  time_in_stage: [
    { stage: "discovered", avg_days: 5.2 },
    { stage: "interested", avg_days: 3.1 },
    { stage: "applied", avg_days: 12.5 },
    { stage: "interviewing", avg_days: 8.0 },
    { stage: "offer", avg_days: 2.0 },
    { stage: "accepted", avg_days: 1.0 },
    { stage: "rejected", avg_days: null },
    { stage: "ghosted", avg_days: null },
  ],
  applications_over_time: [
    { week: "2026-03-02", count: 5 },
    { week: "2026-03-09", count: 8 },
  ],
  score_distribution: [
    { range: "0-2", count: 0 },
    { range: "2-4", count: 1 },
    { range: "4-6", count: 3 },
    { range: "6-8", count: 8 },
    { range: "8-10", count: 5 },
  ],
};

// ---- Tests ----

describe("Analytics", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  describe("loading state", () => {
    it("shows loading indicator while fetching", () => {
      mockFetchAnalytics.mockReturnValue(new Promise(() => {})); // never resolves
      renderAnalytics();
      expect(screen.getByText("Loading analytics…")).toBeInTheDocument();
    });
  });

  describe("error state", () => {
    it("shows error message on fetch failure", async () => {
      mockFetchAnalytics.mockRejectedValue(new Error("Network error"));
      renderAnalytics();
      expect(
        await screen.findByText("Failed to load analytics. Please try again."),
      ).toBeInTheDocument();
    });
  });

  describe("VAL-ANALYTICS-006: empty state", () => {
    it("shows friendly empty state when zero applications", async () => {
      mockFetchAnalytics.mockResolvedValue(EMPTY_DATA);
      renderAnalytics();
      expect(
        await screen.findByText("No applications yet"),
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          "Start adding applications to your pipeline to see analytics here.",
        ),
      ).toBeInTheDocument();
    });

    it("does not render charts when data is empty", async () => {
      mockFetchAnalytics.mockResolvedValue(EMPTY_DATA);
      renderAnalytics();
      await screen.findByText("No applications yet");
      expect(screen.queryByTestId("conversion-funnel")).not.toBeInTheDocument();
      expect(screen.queryByTestId("response-rate")).not.toBeInTheDocument();
    });
  });

  describe("VAL-ANALYTICS-001: conversion funnel", () => {
    it("renders the conversion funnel section", async () => {
      mockFetchAnalytics.mockResolvedValue(POPULATED_DATA);
      renderAnalytics();
      expect(
        await screen.findByTestId("conversion-funnel"),
      ).toBeInTheDocument();
      expect(screen.getByText("Conversion Funnel")).toBeInTheDocument();
    });

    it("shows counts and stage-to-stage percentages per stage", async () => {
      mockFetchAnalytics.mockResolvedValue(POPULATED_DATA);
      renderAnalytics();
      await screen.findByTestId("conversion-funnel");
      // Summary table shows counts with stage-to-stage conversion percentages
      expect(screen.getByText(/10 \(40%\)/)).toBeInTheDocument();
      expect(screen.getByText(/5 \(50%\)/)).toBeInTheDocument();
    });
  });

  describe("VAL-ANALYTICS-002: response rate", () => {
    it("renders response rate value", async () => {
      mockFetchAnalytics.mockResolvedValue(POPULATED_DATA);
      renderAnalytics();
      expect(await screen.findByTestId("response-rate")).toBeInTheDocument();
      expect(screen.getByTestId("response-rate-value")).toHaveTextContent(
        "40.0%",
      );
    });

    it("shows N/A when response rate is null", async () => {
      mockFetchAnalytics.mockResolvedValue({
        ...POPULATED_DATA,
        conversion_funnel: [
          { stage: "discovered", count: 5, percentage: 100 },
          ...POPULATED_DATA.conversion_funnel.slice(1).map((s) => ({
            ...s,
            count: 0,
            percentage: 0,
          })),
        ],
        response_rate: null,
      });
      renderAnalytics();
      expect(await screen.findByTestId("response-rate-value")).toHaveTextContent(
        "N/A",
      );
    });
  });

  describe("VAL-ANALYTICS-003: time-in-stage", () => {
    it("renders time-in-stage section", async () => {
      mockFetchAnalytics.mockResolvedValue(POPULATED_DATA);
      renderAnalytics();
      expect(
        await screen.findByTestId("time-in-stage"),
      ).toBeInTheDocument();
      expect(screen.getByText("Time in Stage")).toBeInTheDocument();
    });

    it("shows 'No data' for stages without data", async () => {
      mockFetchAnalytics.mockResolvedValue(POPULATED_DATA);
      renderAnalytics();
      await screen.findByTestId("time-in-stage");
      // Rejected and ghosted have null avg_days
      const noDataBadges = screen.getAllByText("No data");
      expect(noDataBadges.length).toBeGreaterThanOrEqual(2);
    });

    it("shows days for stages with data", async () => {
      mockFetchAnalytics.mockResolvedValue(POPULATED_DATA);
      renderAnalytics();
      await screen.findByTestId("time-in-stage");
      expect(screen.getByText("5.2d")).toBeInTheDocument();
      expect(screen.getByText("12.5d")).toBeInTheDocument();
    });
  });

  describe("VAL-ANALYTICS-004: applications over time", () => {
    it("renders applications over time chart", async () => {
      mockFetchAnalytics.mockResolvedValue(POPULATED_DATA);
      renderAnalytics();
      expect(
        await screen.findByTestId("applications-over-time"),
      ).toBeInTheDocument();
      expect(screen.getByText("Applications Over Time")).toBeInTheDocument();
    });
  });

  describe("VAL-ANALYTICS-005: score distribution", () => {
    it("renders score distribution histogram", async () => {
      mockFetchAnalytics.mockResolvedValue(POPULATED_DATA);
      renderAnalytics();
      expect(
        await screen.findByTestId("score-distribution"),
      ).toBeInTheDocument();
      expect(screen.getByText("Score Distribution")).toBeInTheDocument();
    });
  });

  describe("all 5 chart sections present with data", () => {
    it("renders all chart sections when data is available", async () => {
      mockFetchAnalytics.mockResolvedValue(POPULATED_DATA);
      renderAnalytics();
      await screen.findByText("Analytics");
      expect(screen.getByTestId("conversion-funnel")).toBeInTheDocument();
      expect(screen.getByTestId("response-rate")).toBeInTheDocument();
      expect(screen.getByTestId("time-in-stage")).toBeInTheDocument();
      expect(screen.getByTestId("applications-over-time")).toBeInTheDocument();
      expect(screen.getByTestId("score-distribution")).toBeInTheDocument();
    });
  });

  describe("time tracker controls in header", () => {
    it("renders time tracker controls", async () => {
      mockFetchAnalytics.mockResolvedValue(POPULATED_DATA);
      renderAnalytics();
      await waitFor(() => {
        expect(screen.getByTestId("time-tracker-controls")).toBeInTheDocument();
      });
    });

    it("shows start tracking button when no session running", async () => {
      mockFetchAnalytics.mockResolvedValue(POPULATED_DATA);
      renderAnalytics();
      await waitFor(() => {
        expect(screen.getByTestId("start-session-button")).toBeInTheDocument();
        expect(screen.getByText("Start Tracking")).toBeInTheDocument();
      });
    });
  });
});
