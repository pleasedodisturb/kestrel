import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Briefcase } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";

describe("EmptyState", () => {
  it("renders heading and description", () => {
    render(
      <EmptyState
        icon={Briefcase}
        heading="No items yet"
        description="Start by adding your first item."
        ctaLabel="Add item"
      />,
    );
    expect(screen.getByText("No items yet")).toBeInTheDocument();
    expect(
      screen.getByText("Start by adding your first item."),
    ).toBeInTheDocument();
  });

  it("renders the icon with aria-hidden", () => {
    render(
      <EmptyState
        icon={Briefcase}
        heading="Empty"
        description="Nothing here."
        ctaLabel="Add"
      />,
    );
    const wrapper = screen.getByTestId("empty-state");
    const svg = wrapper.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveAttribute("aria-hidden", "true");
  });

  it("renders CTA button with onClick handler", () => {
    const onClick = vi.fn();
    render(
      <EmptyState
        icon={Briefcase}
        heading="Empty"
        description="Nothing here."
        ctaLabel="Add Item"
        onCtaClick={onClick}
      />,
    );
    const button = screen.getByTestId("empty-state-cta");
    expect(button).toHaveTextContent("Add Item");
    expect(button.tagName).toBe("BUTTON");
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("renders CTA as link when ctaHref is provided", () => {
    render(
      <EmptyState
        icon={Briefcase}
        heading="Empty"
        description="Nothing here."
        ctaLabel="Go to Discovery"
        ctaHref="/discovery"
      />,
    );
    const link = screen.getByTestId("empty-state-cta");
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", "/discovery");
    expect(link).toHaveTextContent("Go to Discovery");
  });

  it("applies custom className", () => {
    render(
      <EmptyState
        icon={Briefcase}
        heading="Empty"
        description="Nothing."
        ctaLabel="Do it"
        className="my-custom-class"
      />,
    );
    const wrapper = screen.getByTestId("empty-state");
    expect(wrapper.className).toContain("my-custom-class");
  });

  it("uses CSS variable theming (no gray-N classes)", () => {
    const { container } = render(
      <EmptyState
        icon={Briefcase}
        heading="Empty"
        description="Nothing."
        ctaLabel="Go"
      />,
    );
    const html = container.innerHTML;
    expect(html).toContain("hsl(var(--");
    expect(html).not.toMatch(/text-gray-\d/);
  });
});
