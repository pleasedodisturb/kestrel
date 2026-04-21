/**
 * OpenRouterConnect — One-click OpenRouter setup via OAuth PKCE.
 *
 * Shows above the AI Providers integration panel. States:
 * 1. Not connected → "Connect OpenRouter" button
 * 2. Connecting → spinner
 * 3. Connected → balance display + top-up link if low
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { startOAuth, completeOAuth, fetchCredits } from "@/api/openrouter";
import type { OAuthCallbackResponse } from "@/api/openrouter";
import {
  ExternalLink,
  CheckCircle,
  AlertTriangle,
  Loader2,
  Wallet,
} from "lucide-react";

const CALLBACK_PATH = "/settings?openrouter_callback=1";

export function OpenRouterConnect() {
  const queryClient = useQueryClient();
  const [isConnecting, setIsConnecting] = useState(false);
  const [result, setResult] = useState<OAuthCallbackResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: credits } = useQuery({
    queryKey: ["openrouter-credits"],
    queryFn: fetchCredits,
    staleTime: 60_000, // 1 minute
    retry: false,
  });

  const isConnected = credits != null && credits.balance > 0;

  // Handle OAuth callback (code in URL params) — run once on mount
  const callbackHandled = useRef(false);
  useEffect(() => {
    if (callbackHandled.current) return;
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const storedVerifier = sessionStorage.getItem("openrouter_code_verifier");

    if (code && storedVerifier) {
      callbackHandled.current = true;
      sessionStorage.removeItem("openrouter_code_verifier");
      window.history.replaceState({}, "", "/settings");

      completeOAuth(code, storedVerifier)
        .then((res) => {
          setResult(res);
          queryClient.invalidateQueries({ queryKey: ["openrouter-credits"] });
          queryClient.invalidateQueries({ queryKey: ["integrations"] });
        })
        .catch((err) => {
          setError(err instanceof Error ? err.message : "OAuth failed");
        });
    }
  }, [queryClient]);

  const handleConnect = useCallback(async () => {
    setError(null);
    setIsConnecting(true);
    try {
      const callbackUrl = `${window.location.origin}${CALLBACK_PATH}`;
      const { auth_url, code_verifier } = await startOAuth(callbackUrl);
      // Store verifier for the callback
      sessionStorage.setItem("openrouter_code_verifier", code_verifier);
      // Redirect to OpenRouter auth page
      window.location.href = auth_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start OAuth");
      setIsConnecting(false);
    }
  }, []);

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

      {/* Success result */}
      {result?.success && (
        <div className="mt-3 rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">
          <CheckCircle className="mr-1 inline h-4 w-4" />
          {result.message}
          {!result.has_credits && (
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

      {/* Connect button */}
      {!isConnected && !result?.success && (
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
    </div>
  );
}
