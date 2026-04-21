/**
 * OpenRouterConnect — One-click OpenRouter setup via OAuth PKCE.
 *
 * Uses the existing /api/auth/openrouter/* endpoints which handle PKCE
 * server-side with state tokens, rate limiting, and proper storage.
 *
 * Shows above the AI Providers integration panel. States:
 * 1. Not connected → "Connect OpenRouter" button
 * 2. Connecting → spinner
 * 3. Connected → balance display + top-up link if low
 */

import { useState, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { startOAuth, fetchStatus, fetchCredits } from "@/api/openrouter";
import {
  ExternalLink,
  CheckCircle,
  AlertTriangle,
  Loader2,
  Wallet,
} from "lucide-react";

export function OpenRouterConnect() {
  const queryClient = useQueryClient();
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: status } = useQuery({
    queryKey: ["openrouter-status"],
    queryFn: fetchStatus,
    staleTime: 30_000,
    retry: false,
  });

  const { data: credits } = useQuery({
    queryKey: ["openrouter-credits"],
    queryFn: fetchCredits,
    enabled: status?.connected === true,
    staleTime: 60_000,
    retry: false,
  });

  const isConnected = status?.connected === true;

  const handleConnect = useCallback(async () => {
    setError(null);
    setIsConnecting(true);
    try {
      const { auth_url } = await startOAuth();
      // Backend builds callback URL server-side and manages PKCE state.
      // Just redirect the user to OpenRouter.
      window.location.href = auth_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start OAuth");
      setIsConnecting(false);
    }
  }, []);

  // After OAuth callback, backend stores the key and redirects back.
  // Refresh status on mount to pick up newly stored keys.
  const handleRefresh = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["openrouter-status"] });
    queryClient.invalidateQueries({ queryKey: ["openrouter-credits"] });
    queryClient.invalidateQueries({ queryKey: ["integrations"] });
  }, [queryClient]);

  return (
    <div
      data-testid="openrouter-connect"
      className="rounded-lg border border-blue-200 bg-blue-50 p-4"
    >
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <Wallet className="mt-0.5 h-5 w-5 text-blue-600" />
          <div>
            <h3 className="text-sm font-semibold text-blue-900">
              OpenRouter — AI Provider
            </h3>
            <p className="mt-0.5 text-sm text-blue-700">
              One account, 400+ models. Connect to enable AI scoring, research,
              and interview prep.
            </p>
          </div>
        </div>

        {/* Balance display when connected */}
        {credits != null && credits.balance > 0 && (
          <span className="inline-flex items-center gap-1 rounded-full bg-green-50 px-2.5 py-0.5 text-xs font-medium text-green-700">
            <CheckCircle className="h-3 w-3" />${credits.balance.toFixed(2)}{" "}
            balance
          </span>
        )}
      </div>

      {/* Connected success */}
      {isConnected && (
        <div className="mt-3 rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">
          <CheckCircle className="mr-1 inline h-4 w-4" />
          OpenRouter connected.
          {credits?.needs_deposit && (
            <span className="ml-1">
              Add $10 credits to unlock full rate limits.
            </span>
          )}
        </div>
      )}

      {/* Error */}
      {error != null && (
        <div className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Low balance warning */}
      {credits?.needs_deposit && (
        <div className="mt-3 flex items-center gap-2 rounded-md bg-yellow-50 px-3 py-2 text-sm text-yellow-800">
          <AlertTriangle className="h-4 w-4 flex-shrink-0" />
          <span>
            Low balance (${credits.balance.toFixed(2)}). Add credits to keep
            scoring running.
          </span>
          <a
            href="https://openrouter.ai/settings/credits"
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto inline-flex items-center gap-1 whitespace-nowrap text-sm font-medium text-yellow-900 underline hover:text-yellow-700"
          >
            Add credits
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      )}

      {/* Connect / Refresh buttons */}
      {!isConnected && (
        <div className="mt-3">
          <button
            data-testid="openrouter-connect-button"
            onClick={handleConnect}
            disabled={isConnecting}
            className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:opacity-50"
          >
            {isConnecting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ExternalLink className="h-4 w-4" />
            )}
            {isConnecting ? "Connecting..." : "Connect OpenRouter"}
          </button>
          <p className="mt-1.5 text-xs text-blue-600">
            Opens OpenRouter — sign up or log in, then you&apos;ll be redirected
            back automatically.
          </p>
        </div>
      )}

      {isConnected && (
        <button
          data-testid="openrouter-refresh"
          onClick={handleRefresh}
          className="mt-2 text-xs text-blue-600 underline hover:text-blue-800"
        >
          Refresh status
        </button>
      )}
    </div>
  );
}
