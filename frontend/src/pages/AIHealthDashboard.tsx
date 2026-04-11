/**
 * AI Provider Health Dashboard page.
 *
 * Covers:
 * - VAL-AI-HEALTH-001: Provider connectivity check — shows reachable/unreachable per provider
 * - VAL-AI-HEALTH-002: Credit and rate limit display where API exposes them
 * - VAL-AI-HEALTH-003: Auth failure isolation — one bad key shows error only for that provider
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchAIHealth } from "@/api/aiHealth";
import type { ProviderHealthStatus } from "@/api/aiHealth";
import { CreditsExhaustedBanner } from "@/components/CreditsExhaustedBanner";
import {
  RefreshCw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  CircleDashed,
  Zap,
  CreditCard,
  Clock,
  Star,
} from "lucide-react";

export function AIHealthDashboard() {
  const queryClient = useQueryClient();
  const { data, isLoading, error, isFetching } = useQuery({
    queryKey: ["ai-health"],
    queryFn: fetchAIHealth,
    staleTime: 30 * 1000, // 30s
  });

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ["ai-health"] });
  };

  if (isLoading) {
    return (
      <div
        data-testid="ai-health-loading"
        className="flex items-center justify-center py-20"
      >
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-gray-900" />
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="ai-health-error" className="py-20 text-center">
        <XCircle className="mx-auto h-12 w-12 text-red-400" />
        <p className="mt-4 text-lg font-medium text-red-700">
          {error instanceof Error ? error.message : String(error)}
        </p>
      </div>
    );
  }

  const providers = data?.providers ?? [];

  // Summary counts
  const reachableCount = providers.filter((p) => p.status === "reachable").length;
  const errorCount = providers.filter(
    (p) => p.status === "error" || p.status === "unreachable",
  ).length;
  const notConfiguredCount = providers.filter(
    (p) => p.status === "not_configured",
  ).length;

  return (
    <section data-testid="ai-health-dashboard" className="space-y-6">
      <CreditsExhaustedBanner />

      {/* Header */}
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            AI Provider Health
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Connectivity status, credits, and rate limits for all configured AI
            providers.
          </p>
        </div>
        <button
          data-testid="refresh-health"
          onClick={handleRefresh}
          disabled={isFetching}
          className="inline-flex items-center gap-2 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 disabled:opacity-50"
        >
          <RefreshCw
            className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`}
          />
          Refresh
        </button>
      </header>

      {/* Summary bar */}
      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-lg border bg-green-50 p-4">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-green-600" />
            <span className="text-sm font-medium text-green-800">
              {reachableCount} Reachable
            </span>
          </div>
        </div>
        <div className="rounded-lg border bg-red-50 p-4">
          <div className="flex items-center gap-2">
            <XCircle className="h-5 w-5 text-red-600" />
            <span className="text-sm font-medium text-red-800">
              {errorCount} Error / Unreachable
            </span>
          </div>
        </div>
        <div className="rounded-lg border bg-gray-50 p-4">
          <div className="flex items-center gap-2">
            <CircleDashed className="h-5 w-5 text-gray-500" />
            <span className="text-sm font-medium text-gray-700">
              {notConfiguredCount} Not Configured
            </span>
          </div>
        </div>
      </div>

      {/* Provider cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {providers.map((provider) => (
          <ProviderCard key={provider.name} provider={provider} />
        ))}
      </div>
    </section>
  );
}

// ---- Status Badge Component ----

function StatusBadge({ status }: Readonly<{ status: string }>) {
  const config: Record<string, { label: string; className: string; Icon: typeof CheckCircle2 }> = {
    reachable: {
      label: "Reachable",
      className: "bg-green-100 text-green-800",
      Icon: CheckCircle2,
    },
    unreachable: {
      label: "Unreachable",
      className: "bg-red-100 text-red-800",
      Icon: XCircle,
    },
    error: {
      label: "Error",
      className: "bg-red-100 text-red-800",
      Icon: AlertTriangle,
    },
    not_configured: {
      label: "Not Configured",
      className: "bg-gray-100 text-gray-600",
      Icon: CircleDashed,
    },
  };

  const { label, className, Icon } = config[status] ?? config.not_configured;

  return (
    <span
      data-testid={`status-${status}`}
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${className}`}
    >
      <Icon className="h-3 w-3" />
      {label}
    </span>
  );
}

// ---- Provider Card Component ----

function ProviderCard({ provider }: Readonly<{ provider: ProviderHealthStatus }>) {
  const borderColorMap: Record<string, string> = {
    reachable: "border-green-200",
    error: "border-red-200",
    unreachable: "border-red-200",
  };
  const borderColor = borderColorMap[provider.status] ?? "border-gray-200";

  return (
    <div
      data-testid={`provider-card-${provider.name}`}
      className={`rounded-lg border ${borderColor} bg-white p-5 shadow-sm`}
    >
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-gray-900">
            {provider.display_name}
          </h3>
          {provider.is_default && (
            <span
              data-testid="default-badge"
              className="inline-flex items-center gap-0.5 rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-800"
            >
              <Star className="h-3 w-3" />
              Default
            </span>
          )}
        </div>
        <StatusBadge status={provider.status} />
      </div>

      {/* Error message */}
      {provider.error_message &&
        provider.status !== "not_configured" && (
          <p className="mt-2 text-xs text-red-600">{provider.error_message}</p>
        )}

      {/* Details */}
      <div className="mt-3 space-y-2">
        {/* Response time */}
        {provider.response_time_ms != null && provider.status === "reachable" && (
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <Clock className="h-3 w-3" />
            <span>{Math.round(provider.response_time_ms)}ms</span>
          </div>
        )}

        {/* Credits */}
        {provider.credits && (
          <div data-testid="credits-info" className="flex items-center gap-2 text-xs text-gray-600">
            <CreditCard className="h-3 w-3" />
            <span>
              {provider.credits.remaining != null
                ? `${provider.credits.remaining} / ${provider.credits.total ?? "∞"} ${provider.credits.unit}`
                : `${provider.credits.unit} (usage tracked)`}
            </span>
          </div>
        )}

        {/* Rate limits */}
        {provider.rate_limit && (
          <div data-testid="rate-limit-info" className="flex items-center gap-2 text-xs text-gray-600">
            <Zap className="h-3 w-3" />
            <span>
              {provider.rate_limit.requests_per_minute != null
                ? `${provider.rate_limit.requests_per_minute} RPM`
                : ""}
              {provider.rate_limit.tokens_per_minute != null
                ? ` / ${provider.rate_limit.tokens_per_minute} TPM`
                : ""}
            </span>
          </div>
        )}

        {/* Not configured hint */}
        {provider.status === "not_configured" && (
          <p className="text-xs text-gray-400">
            {provider.error_message ?? "Configure API key in Settings → Integrations"}
          </p>
        )}
      </div>
    </div>
  );
}
