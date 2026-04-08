interface Props {
  rate: number | null;
}

export function ResponseRate({ rate }: Props) {
  const displayRate = rate !== null ? `${rate.toFixed(1)}%` : "N/A";
  const color =
    rate === null
      ? "text-gray-400"
      : rate >= 50
        ? "text-green-600"
        : rate >= 25
          ? "text-amber-600"
          : "text-red-600";

  return (
    <div
      className="flex h-full flex-col rounded-lg border bg-white p-6"
      data-testid="response-rate"
    >
      <h2 className="text-lg font-semibold text-gray-900">Response Rate</h2>
      <p className="mt-1 text-sm text-gray-500">
        Applications that progressed past applied
      </p>

      <div className="flex flex-1 flex-col items-center justify-center py-8">
        <span className={`text-5xl font-bold ${color}`} data-testid="response-rate-value">
          {displayRate}
        </span>
        <span className="mt-2 text-sm text-gray-500">
          {rate === null
            ? "No applications submitted yet"
            : "of submitted applications got a response"}
        </span>
      </div>
    </div>
  );
}
