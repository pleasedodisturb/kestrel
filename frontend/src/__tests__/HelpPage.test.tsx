import { screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderWithProviders } from "@/test-utils";
import { HelpPage } from "@/pages/HelpPage";

/* ---------- API-level mocks ---------- */

const mockResetOnboarding = vi.fn();
const mockFetchOnboardingStatus = vi.fn();

vi.mock("@/api/onboarding", () => ({
  fetchOnboardingStatus: (...args: unknown[]) => mockFetchOnboardingStatus(...(args as [])),
  resetOnboarding: (...args: unknown[]) => mockResetOnboarding(...(args as [])),
  patchOnboardingStep: vi.fn().mockResolvedValue({}),
  DEFAULT_PROFILE_ID: 1,
}));

/* ---------- Setup ---------- */

beforeEach(() => {
  vi.clearAllMocks();
  mockResetOnboarding.mockResolvedValue({});
  mockFetchOnboardingStatus.mockResolvedValue({ profile_id: 1, is_complete: false });
});

/* ---------- Helpers ---------- */

function renderHelpPage() {
  return renderWithProviders(<HelpPage />, { route: "/help" });
}

/* ---------- Tests ---------- */

describe("HelpPage", () => {
  it("renders the page", () => {
    renderHelpPage();
    expect(screen.getByTestId("help-page")).toBeInTheDocument();
  });

  it("has the Getting Started title", () => {
    renderHelpPage();
    expect(
      screen.getByText("Getting Started with Kestrel"),
    ).toBeInTheDocument();
  });

  it("explains what a terminal is", () => {
    renderHelpPage();
    expect(screen.getByText("What is a terminal?")).toBeInTheDocument();
  });

  it("shows how to open terminal on macOS", () => {
    renderHelpPage();
    expect(screen.getByText(/macOS/)).toBeInTheDocument();
    expect(screen.getByText(/Spotlight/)).toBeInTheDocument();
  });

  it("shows how to open terminal on Ubuntu", () => {
    renderHelpPage();
    expect(screen.getByText(/Ubuntu \/ Linux/)).toBeInTheDocument();
  });

  it("shows how to open terminal on Windows WSL", () => {
    renderHelpPage();
    expect(screen.getByText(/Windows \(WSL\)/)).toBeInTheDocument();
  });

  it("documents kestrel init command", () => {
    renderHelpPage();
    expect(screen.getByText("kestrel init")).toBeInTheDocument();
  });

  it("documents kestrel doctor command", () => {
    renderHelpPage();
    const doctorElements = screen.getAllByText("kestrel doctor");
    expect(doctorElements.length).toBeGreaterThanOrEqual(1);
  });

  it("documents kestrel pipeline command", () => {
    renderHelpPage();
    expect(screen.getByText("kestrel pipeline")).toBeInTheDocument();
  });

  it("documents kestrel init --skip for power users", () => {
    renderHelpPage();
    expect(screen.getByText("kestrel init --skip")).toBeInTheDocument();
  });

  it("has a pip install command", () => {
    renderHelpPage();
    expect(screen.getByText("pip install kestrel-app")).toBeInTheDocument();
  });

  it("has a back link to Pipeline", () => {
    renderHelpPage();
    const backLink = screen.getByText("Back to Pipeline");
    expect(backLink.closest("a")).toHaveAttribute("href", "/");
  });

  it("mentions the feedback button for getting help", () => {
    renderHelpPage();
    expect(screen.getByText(/feedback button/)).toBeInTheDocument();
  });
});
