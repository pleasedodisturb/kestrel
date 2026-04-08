import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect } from "vitest";
import { Layout } from "@/components/Layout";

function renderWithRouter(initialEntries: string[] = ["/"]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Layout />
    </MemoryRouter>
  );
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
