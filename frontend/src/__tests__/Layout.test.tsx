import { screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Layout } from "@/components/Layout";
import { renderWithProviders } from "@/test-utils";

vi.mock("@/api/onboarding", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/onboarding")>();
  return {
    ...actual,
    fetchOnboardingStatus: vi.fn().mockResolvedValue({
      completed_at: new Date().toISOString(),
      welcome_completed_at: new Date().toISOString(),
    }),
    patchOnboardingStep: vi.fn().mockResolvedValue({}),
  };
});

function renderWithRouter(initialEntries: string[] = ["/"]) {
  return renderWithProviders(<Layout />, {
    route: initialEntries[0],
    routerProps: { initialEntries },
  });
}

describe("Layout", () => {
  it("renders the Career OS branding", () => {
    renderWithRouter();
    expect(screen.getByText("Career OS")).toBeInTheDocument();
  });

  it("renders Pipeline navigation link", () => {
    renderWithRouter();
    expect(screen.getByText("Pipeline")).toBeInTheDocument();
  });

  it("renders Analytics navigation link", () => {
    renderWithRouter();
    expect(screen.getByText("Analytics")).toBeInTheDocument();
  });

  it("renders Follow-Ups navigation link", () => {
    renderWithRouter();
    expect(screen.getByText("Follow-Ups")).toBeInTheDocument();
  });

  it("renders Settings navigation link", () => {
    renderWithRouter();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("highlights active nav item", () => {
    renderWithRouter(["/"]);
    const pipelineLink = screen.getByText("Pipeline").closest("a");
    expect(pipelineLink).toHaveClass("bg-gray-100");
  });
});
