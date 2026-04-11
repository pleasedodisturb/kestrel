/**
 * ScoreRadarChart — visualizes the six dimensional sub-scores returned by
 * the scoring engine. Uses a radar chart on desktop (≥640px) and falls back
 * to a horizontal bar chart on mobile where radar labels become unreadable.
 */

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DimensionalScores } from "@/api/types";

interface ScoreRadarChartProps {
  readonly scores: DimensionalScores | null | undefined;
}

interface Datum {
  readonly short: string;
  readonly full: string;
  readonly value: number;
}

const RADAR_FILL = "#22c55e"; // green-500

function buildData(scores: DimensionalScores): Datum[] {
  return [
    { short: "Technical", full: "Technical Fit", value: scores.technical_fit },
    { short: "Seniority", full: "Seniority Alignment", value: scores.seniority_alignment },
    { short: "Salary", full: "Compensation Fit", value: scores.compensation_fit },
    { short: "Location", full: "Location Fit", value: scores.location_fit },
    { short: "Career", full: "Career Trajectory", value: scores.career_trajectory },
    { short: "Culture", full: "Company Fit", value: scores.company_fit },
  ];
}

function scoreColor(value: number): string {
  if (value >= 7) return "#22c55e"; // green-500
  if (value >= 4) return "#eab308"; // yellow-500
  return "#ef4444"; // red-500
}

function useIsNarrow(breakpointPx = 640): boolean {
  const getInitial = () =>
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia(`(max-width: ${breakpointPx - 1}px)`).matches;

  const [isNarrow, setIsNarrow] = useState<boolean>(getInitial);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }
    const mql = window.matchMedia(`(max-width: ${breakpointPx - 1}px)`);
    const handler = (e: MediaQueryListEvent) => setIsNarrow(e.matches);
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, [breakpointPx]);

  return isNarrow;
}

export function ScoreRadarChart({ scores }: ScoreRadarChartProps) {
  const isNarrow = useIsNarrow();

  if (!scores) return null;

  const data = buildData(scores);

  if (isNarrow) {
    return (
      <div data-testid="score-radar-chart" data-mode="bars">
        <ResponsiveContainer width="100%" height={220}>
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 8, right: 24, bottom: 8, left: 24 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis type="number" domain={[0, 10]} />
            <YAxis
              type="category"
              dataKey="short"
              width={70}
              tick={{ fontSize: 12 }}
            />
            <Tooltip
              contentStyle={{
                borderRadius: 8,
                border: "1px solid #e2e8f0",
              }}
              formatter={(value: number, _name, payload) => {
                const full = payload?.payload?.full as string | undefined;
                return [`${value.toFixed(1)} / 10`, full ?? "Score"];
              }}
            />
            <Bar dataKey="value" radius={[0, 4, 4, 0]}>
              {data.map((d) => (
                <Cell key={d.short} fill={scoreColor(d.value)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  return (
    <div data-testid="score-radar-chart" data-mode="radar">
      <ResponsiveContainer width="100%" height={260}>
        <RadarChart data={data} outerRadius="75%">
          <PolarGrid stroke="#e2e8f0" />
          <PolarAngleAxis dataKey="short" tick={{ fontSize: 12 }} />
          <PolarRadiusAxis
            domain={[0, 10]}
            axisLine={false}
            tick={{ fontSize: 10 }}
          />
          <Radar
            dataKey="value"
            stroke={RADAR_FILL}
            fill={RADAR_FILL}
            fillOpacity={0.3}
          />
          <Tooltip
            contentStyle={{
              borderRadius: 8,
              border: "1px solid #e2e8f0",
            }}
            formatter={(value: number, _name, payload) => {
              const full = payload?.payload?.full as string | undefined;
              return [`${value.toFixed(1)} / 10`, full ?? "Score"];
            }}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
