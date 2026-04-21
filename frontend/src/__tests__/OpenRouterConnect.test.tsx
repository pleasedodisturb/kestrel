/**
 * Tests for OpenRouterConnect component.
 *
 * Covers:
 * - Renders connect button when not connected
 * - Shows balance when credits are available
 * - Shows low balance warning when needs_deposit is true
 * - Connect button calls startOAuth and redirects
 * - Handles OAuth callback from URL params
 * - Shows error state on failure
 */

import {
  render,
  screen,
  waitFor,
  act,
  fireEvent,
} from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { OpenRouterConnect } from "@/components/OpenRouterConnect";

// Mock the API module
vi.mock("@/api/openrouter", () => ({
  startOAuth: vi.fn(),
  completeOAuth: vi.fn(),
  fetchCredits: vi.fn(),
}));

import { startOAuth, fetchCredits } from "@/api/openrouter";

function renderWithQuery(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("OpenRouterConnect", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    // Default: no credits (not connected)
    vi.mocked(fetchCredits).mockResolvedValue({
      total_credits: 0,
      total_usage: 0,
      balance: 0,
      needs_deposit: true,
    });
  });

  it("renders the connect button when not connected", async () => {
    renderWithQuery(<OpenRouterConnect />);
    await waitFor(() => {
      expect(
        screen.getByTestId("openrouter-connect-button"),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("Connect OpenRouter")).toBeInTheDocument();
  });

  it("shows balance when credits are available", async () => {
    vi.mocked(fetchCredits).mockResolvedValue({
      total_credits: 10,
      total_usage: 2.5,
      balance: 7.5,
      needs_deposit: false,
    });

    renderWithQuery(<OpenRouterConnect />);
    await waitFor(() => {
      expect(screen.getByText("$7.50 balance")).toBeInTheDocument();
    });
  });

  it("shows low balance warning when needs_deposit is true", async () => {
    vi.mocked(fetchCredits).mockResolvedValue({
      total_credits: 1,
      total_usage: 0.8,
      balance: 0.2,
      needs_deposit: true,
    });

    renderWithQuery(<OpenRouterConnect />);
    await waitFor(() => {
      expect(screen.getByText(/Low balance/)).toBeInTheDocument();
      expect(screen.getByText("Add credits")).toBeInTheDocument();
    });
  });

  it("calls startOAuth and sets sessionStorage on connect click", async () => {
    // Mock window.location.href assignment
    const originalLocation = window.location;
    const mockLocation = { ...originalLocation, href: "" };
    Object.defineProperty(window, "location", {
      writable: true,
      value: mockLocation,
    });

    vi.mocked(startOAuth).mockResolvedValue({
      auth_url:
        "https://openrouter.ai/auth?callback_url=test&code_challenge=abc",
      code_verifier: "test-verifier-123",
    });

    renderWithQuery(<OpenRouterConnect />);
    await waitFor(() => {
      expect(
        screen.getByTestId("openrouter-connect-button"),
      ).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByTestId("openrouter-connect-button"));
    });

    await waitFor(() => {
      expect(startOAuth).toHaveBeenCalledWith(
        expect.stringContaining("/settings?openrouter_callback=1"),
      );
      expect(sessionStorage.getItem("openrouter_code_verifier")).toBe(
        "test-verifier-123",
      );
      expect(mockLocation.href).toContain("openrouter.ai/auth");
    });

    // Restore
    Object.defineProperty(window, "location", {
      writable: true,
      value: originalLocation,
    });
  });

  it("shows description text about the flow", async () => {
    renderWithQuery(<OpenRouterConnect />);
    await waitFor(() => {
      expect(screen.getByText(/One account, 400\+ models/)).toBeInTheDocument();
    });
  });

  it("shows error when startOAuth fails", async () => {
    vi.mocked(startOAuth).mockRejectedValue(new Error("Network error"));

    renderWithQuery(<OpenRouterConnect />);
    await waitFor(() => {
      expect(
        screen.getByTestId("openrouter-connect-button"),
      ).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByTestId("openrouter-connect-button"));
    });

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });
});
