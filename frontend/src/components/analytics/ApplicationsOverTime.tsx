import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { WeeklyCount } from "@/api/analytics";

interface Props {
  readonly data: WeeklyCount[];
}

export function ApplicationsOverTime({ data }: Props) {
  const hasData = data.length > 0;

  return (
    <div className="rounded-lg border bg-white p-6" data-testid="applications-over-time">
      <h2 className="text-lg font-semibold text-gray-900">
        Applications Over Time
      </h2>
      <p className="mt-1 text-sm text-gray-500">Weekly application counts</p>

      {hasData ? (
        <div className="mt-4 h-48">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={data}
              margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
            >
              <defs>
                <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#818cf8" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#818cf8" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis
                dataKey="week"
                tick={{ fontSize: 11, fill: "#64748b" }}
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
                labelFormatter={(label) => `Week of ${label}`}
                contentStyle={{
                  borderRadius: "8px",
                  border: "1px solid #e2e8f0",
                  fontSize: "13px",
                }}
              />
              <Area
                type="monotone"
                dataKey="count"
                stroke="#818cf8"
                strokeWidth={2}
                fill="url(#colorCount)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="flex items-center justify-center py-12">
          <p className="text-sm text-gray-400" data-testid="over-time-empty">
            No data available
          </p>
        </div>
      )}
    </div>
  );
}
