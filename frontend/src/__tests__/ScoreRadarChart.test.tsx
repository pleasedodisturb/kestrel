/**
 * Tests for ScoreRadarChart component (#76).
 *
 * Uses a lightweight recharts mock (same pattern as Analytics.test.tsx) so
 * the chart library doesn't need to actually render axes in jsdom.
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ScoreRadarChart } from "@/components/ScoreRadarChart";
import type { DimensionalScores } from "@/api/types";

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "responsive-container" }, children),
  RadarChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "radar-chart" }, children),
  BarChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "bar-chart" }, children),
  Radar: () => null,
  Bar: ({ children }: { children?: React.ReactNode }) =>
    React.createElement("div", null, children),
  Cell: () => null,
  PolarGrid: () => null,
  PolarAngleAxis: () => null,
  PolarRadiusAxis: () => null,
  CartesianGrid: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
}));

const sampleScores: DimensionalScores = {
  technical_fit: 8.5,
  seniority_alignment: 7.0,
  compensation_fit: 6.0,
  location_fit: 9.0,
  career_trajectory: 7.5,
  company_fit: 5.5,
};

function stubMatchMedia(matches: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  );
}

describe("ScoreRadarChart", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders nothing when scores are null", () => {
    const { container } = render(<ScoreRadarChart scores={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when scores are undefined", () => {
    const { container } = render(<ScoreRadarChart scores={undefined} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders the radar chart on wide viewports", () => {
    stubMatchMedia(false); // not narrow → radar
    render(<ScoreRadarChart scores={sampleScores} />);
    const chart = screen.getByTestId("score-radar-chart");
    expect(chart).toBeInTheDocument();
    expect(chart.getAttribute("data-mode")).toBe("radar");
    expect(screen.getByTestId("radar-chart")).toBeInTheDocument();
  });

  it("falls back to bar chart on narrow viewports", () => {
    stubMatchMedia(true); // narrow → bars
    render(<ScoreRadarChart scores={sampleScores} />);
    const chart = screen.getByTestId("score-radar-chart");
    expect(chart).toBeInTheDocument();
    expect(chart.getAttribute("data-mode")).toBe("bars");
    expect(screen.getByTestId("bar-chart")).toBeInTheDocument();
  });
});
