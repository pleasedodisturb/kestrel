import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { ScoreBucket } from "@/api/analytics";

const BUCKET_COLORS = [
  "#ef4444", // 0-2 red
  "#f97316", // 2-4 orange
  "#eab308", // 4-6 yellow
  "#22c55e", // 6-8 green
  "#16a34a", // 8-10 dark green
];

interface Props {
  readonly data: ScoreBucket[];
}

export function ScoreDistribution({ data }: Props) {
  const hasData = data.some((b) => b.count > 0);

  return (
    <div className="rounded-lg border bg-white p-6" data-testid="score-distribution">
      <h2 className="text-lg font-semibold text-gray-900">
        Score Distribution
      </h2>
      <p className="mt-1 text-sm text-gray-500">
        Fit score distribution across applications
      </p>

      {hasData ? (
        <div className="mt-4 h-48">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data}
              margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis
                dataKey="range"
                tick={{ fontSize: 12, fill: "#64748b" }}
                tickLine={false}
                axisLine={{ stroke: "#e2e8f0" }}
              />
              <YAxis
                tick={{ fontSize: 12, fill: "#64748b" }}
                tickLine={false}
                axisLine={{ stroke: "#e2e8f0" }}
                allowDecimals={false}
              />
              <Tooltip
                formatter={(value) => [`${value}`, "Applications"]}
                contentStyle={{
                  borderRadius: "8px",
                  border: "1px solid #e2e8f0",
                  fontSize: "13px",
                }}
              />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {data.map((_, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={BUCKET_COLORS[index % BUCKET_COLORS.length]}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="flex items-center justify-center py-12">
          <p className="text-sm text-gray-400" data-testid="score-empty">
            No scored applications yet
          </p>
        </div>
      )}
    </div>
  );
}
