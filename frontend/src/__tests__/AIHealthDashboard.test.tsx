/**
 * Tests for the AI Health Dashboard page.
 *
 * Covers:
 * - VAL-AI-HEALTH-001: Provider connectivity check — shows reachable/unreachable per provider
 * - VAL-AI-HEALTH-002: Credit and rate limit display
 * - VAL-AI-HEALTH-003: Auth failure isolation — one bad key shows error only for that provider
 */

import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { AIHealthDashboard } from "@/pages/AIHealthDashboard";
import type { AIHealthResponse } from "@/api/aiHealth";

// ---- mocks ----

const mockFetchAIHealth = vi.fn<() => Promise<AIHealthResponse>>();

vi.mock("@/api/aiHealth", () => ({
  fetchAIHealth: (...args: unknown[]) => mockFetchAIHealth(...(args as [])),
  fetchProviderHealth: vi.fn(),
}));

vi.mock("@/api/followUps", () => ({
  fetchOverdueCount: vi.fn().mockResolvedValue({ count: 0 }),
}));

// ---- helpers ----

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

function renderDashboard() {
  const qc = createQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AIHealthDashboard />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const MOCK_HEALTH_DATA: AIHealthResponse = {
  providers: [
    {
      name: "mock",
      display_name: "Demo Mode",
      status: "reachable",
      is_default: true,
      error_message: null,
      credits: null,
      rate_limit: null,
      response_time_ms: 0.1,
    },
    {
      name: "openrouter",
      display_name: "OpenRouter",
      status: "reachable",
      is_default: false,
      error_message: null,
      credits: { remaining: 8.5, total: 10.0, unit: "USD" },
      rate_limit: { requests_per_minute: 60, tokens_per_minute: null },
      response_time_ms: 150.3,
    },
    {
      name: "anthropic",
      display_name: "Anthropic",
      status: "not_configured",
      is_default: false,
      error_message: "ANTHROPIC_API_KEY not set",
      credits: null,
      rate_limit: null,
      response_time_ms: null,
    },
    {
      name: "openai",
      display_name: "OpenAI",
      status: "error",
      is_default: false,
      error_message: "Authentication failed (HTTP 401)",
      credits: null,
      rate_limit: null,
      response_time_ms: 200.0,
    },
    {
      name: "gemini",
      display_name: "Google Gemini",
      status: "not_configured",
      is_default: false,
      error_message: "GEMINI_API_KEY not set",
      credits: null,
      rate_limit: null,
      response_time_ms: null,
    },
    {
      name: "together",
      display_name: "Together AI",
      status: "unreachable",
      is_default: false,
      error_message: "Connection timed out",
      credits: null,
      rate_limit: null,
      response_time_ms: null,
    },
    {
      name: "droid_exec",
      display_name: "Droid Exec (Claude MAX)",
      status: "not_configured",
      is_default: false,
      error_message: "Available only in droid execution environment",
      credits: null,
      rate_limit: null,
      response_time_ms: null,
    },
  ],
  default_provider: "mock",
};

// ---- tests ----

describe("AIHealthDashboard", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    sessionStorage.clear();
  });

  it("shows loading state while fetching", () => {
    mockFetchAIHealth.mockReturnValue(new Promise(() => {}));
    renderDashboard();
    expect(screen.getByTestId("ai-health-loading")).toBeInTheDocument();
  });

  it("shows error on fetch failure", async () => {
    mockFetchAIHealth.mockRejectedValue(new Error("Network error"));
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByTestId("ai-health-error")).toBeInTheDocument();
    });
  });

  it("renders all provider cards", async () => {
    mockFetchAIHealth.mockResolvedValue(MOCK_HEALTH_DATA);
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByTestId("provider-card-mock")).toBeInTheDocument();
      expect(screen.getByTestId("provider-card-openrouter")).toBeInTheDocument();
      expect(screen.getByTestId("provider-card-anthropic")).toBeInTheDocument();
      expect(screen.getByTestId("provider-card-openai")).toBeInTheDocument();
      expect(screen.getByTestId("provider-card-gemini")).toBeInTheDocument();
      expect(screen.getByTestId("provider-card-together")).toBeInTheDocument();
      expect(screen.getByTestId("provider-card-droid_exec")).toBeInTheDocument();
    });
  });

  it("shows display names for providers", async () => {
    mockFetchAIHealth.mockResolvedValue(MOCK_HEALTH_DATA);
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText("Demo Mode")).toBeInTheDocument();
      expect(screen.getByText("OpenRouter")).toBeInTheDocument();
      expect(screen.getByText("Anthropic")).toBeInTheDocument();
      expect(screen.getByText("OpenAI")).toBeInTheDocument();
      expect(screen.getByText("Google Gemini")).toBeInTheDocument();
      expect(screen.getByText("Together AI")).toBeInTheDocument();
    });
  });

  it("shows status badges with correct colors", async () => {
    mockFetchAIHealth.mockResolvedValue(MOCK_HEALTH_DATA);
    renderDashboard();
    await waitFor(() => {
      // Reachable = green
      const mockCard = screen.getByTestId("provider-card-mock");
      expect(mockCard.querySelector('[data-testid="status-reachable"]')).toBeInTheDocument();

      // Not configured = gray
      const anthropicCard = screen.getByTestId("provider-card-anthropic");
      expect(
        anthropicCard.querySelector('[data-testid="status-not_configured"]'),
      ).toBeInTheDocument();

      // Error = red
      const openaiCard = screen.getByTestId("provider-card-openai");
      expect(openaiCard.querySelector('[data-testid="status-error"]')).toBeInTheDocument();

      // Unreachable = red
      const togetherCard = screen.getByTestId("provider-card-together");
      expect(
        togetherCard.querySelector('[data-testid="status-unreachable"]'),
      ).toBeInTheDocument();
    });
  });

  it("marks default provider", async () => {
    mockFetchAIHealth.mockResolvedValue(MOCK_HEALTH_DATA);
    renderDashboard();
    await waitFor(() => {
      const mockCard = screen.getByTestId("provider-card-mock");
      expect(mockCard.querySelector('[data-testid="default-badge"]')).toBeInTheDocument();

      // Others should not have default badge
      const orCard = screen.getByTestId("provider-card-openrouter");
      expect(orCard.querySelector('[data-testid="default-badge"]')).not.toBeInTheDocument();
    });
  });

  it("shows credits when available (VAL-AI-HEALTH-002)", async () => {
    mockFetchAIHealth.mockResolvedValue(MOCK_HEALTH_DATA);
    renderDashboard();
    await waitFor(() => {
      const orCard = screen.getByTestId("provider-card-openrouter");
      expect(orCard.querySelector('[data-testid="credits-info"]')).toBeInTheDocument();
      expect(orCard).toHaveTextContent(/8\.5/);
      expect(orCard).toHaveTextContent(/USD/);
    });
  });

  it("shows rate limit when available (VAL-AI-HEALTH-002)", async () => {
    mockFetchAIHealth.mockResolvedValue(MOCK_HEALTH_DATA);
    renderDashboard();
    await waitFor(() => {
      const orCard = screen.getByTestId("provider-card-openrouter");
      expect(orCard.querySelector('[data-testid="rate-limit-info"]')).toBeInTheDocument();
      expect(orCard).toHaveTextContent(/60/);
    });
  });

  it("shows error messages for failed providers (VAL-AI-HEALTH-003)", async () => {
    mockFetchAIHealth.mockResolvedValue(MOCK_HEALTH_DATA);
    renderDashboard();
    await waitFor(() => {
      const openaiCard = screen.getByTestId("provider-card-openai");
      expect(openaiCard).toHaveTextContent("Authentication failed");

      const togetherCard = screen.getByTestId("provider-card-together");
      expect(togetherCard).toHaveTextContent("Connection timed out");
    });
  });

  it("shows response time for reachable providers", async () => {
    mockFetchAIHealth.mockResolvedValue(MOCK_HEALTH_DATA);
    renderDashboard();
    await waitFor(() => {
      const orCard = screen.getByTestId("provider-card-openrouter");
      expect(orCard).toHaveTextContent(/150/);
    });
  });

  it("has a refresh button", async () => {
    mockFetchAIHealth.mockResolvedValue(MOCK_HEALTH_DATA);
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByTestId("refresh-health")).toBeInTheDocument();
    });
  });

  it("has page heading", async () => {
    mockFetchAIHealth.mockResolvedValue(MOCK_HEALTH_DATA);
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText("AI Provider Health")).toBeInTheDocument();
    });
  });
});
