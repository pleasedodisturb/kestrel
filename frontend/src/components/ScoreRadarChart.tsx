import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import type { DimensionalScores } from "@/api/types";
import { useEffect, useState } from "react";

interface ScoreRadarChartProps {
  readonly dimensionalScores: DimensionalScores | null | undefined;
}

const AXIS_LABELS: Record<keyof DimensionalScores, string> = {
  technical_fit: "Technical",
  seniority_alignment: "Seniority",
  compensation_fit: "Compensation",
  location_fit: "Location",
  career_trajectory: "Career Path",
  company_fit: "Company",
};

function barColor(value: number): string {
  if (value >= 7) return "#22c55e";
  if (value >= 4) return "#eab308";
  return "#ef4444";
}

export default function ScoreRadarChart({ dimensionalScores }: ScoreRadarChartProps) {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 640);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  if (!dimensionalScores) return null;

  const data = (Object.keys(AXIS_LABELS) as (keyof DimensionalScores)[]).map((key) => ({
    axis: AXIS_LABELS[key],
    value: dimensionalScores[key],
  }));

  if (isMobile) {
    return (
      <div className="w-full">
        <h4 className="mb-2 text-sm font-medium text-gray-700">Score Dimensions</h4>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data} layout="vertical" margin={{ top: 5, right: 20, left: 60, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis type="number" domain={[0, 10]} tick={{ fontSize: 11 }} />
            <YAxis type="category" dataKey="axis" tick={{ fontSize: 11 }} width={55} />
            <Tooltip
              formatter={(v: number) => [v.toFixed(1), "Score"]}
              contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0" }}
            />
            <Bar dataKey="value" fill="#22c55e" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  return (
    <div className="w-full">
      <h4 className="mb-2 text-sm font-medium text-gray-700">Score Dimensions</h4>
      <ResponsiveContainer width="100%" height={260}>
        <RadarChart data={data} cx="50%" cy="50%" outerRadius="75%">
          <PolarGrid stroke="#e2e8f0" />
          <PolarAngleAxis dataKey="axis" tick={{ fontSize: 11, fill: "#64748b" }} />
          <PolarRadiusAxis domain={[0, 10]} tick={{ fontSize: 10 }} axisLine={false} />
          <Radar
            dataKey="value"
            stroke="#16a34a"
            fill="#22c55e"
            fillOpacity={0.3}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
