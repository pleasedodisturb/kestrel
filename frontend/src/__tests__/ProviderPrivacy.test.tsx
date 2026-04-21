/**
 * Tests for ProviderPrivacyInfo component.
 *
 * Covers:
 * - Renders privacy info section with heading
 * - Shows privacy entry for each supported provider
 * - Each entry includes a source link with correct href
 * - Tier-based styling applied correctly
 * - Only renders inside ai_providers integration panel
 */

import { render, screen, within } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ProviderPrivacyInfo } from "@/components/ProviderPrivacyInfo";
import { PROVIDER_PRIVACY_DATA } from "@/components/providerPrivacyData";

describe("ProviderPrivacyInfo", () => {
  it("renders the privacy disclosure section with heading", () => {
    render(<ProviderPrivacyInfo />);

    const container = screen.getByTestId("provider-privacy-info");
    expect(container).toBeInTheDocument();
    expect(container).toHaveTextContent("Provider Privacy Disclosures");
    expect(container).toHaveTextContent("How each provider handles your data");
  });

  it("renders an entry for every provider in PROVIDER_PRIVACY_DATA", () => {
    render(<ProviderPrivacyInfo />);

    for (const entry of PROVIDER_PRIVACY_DATA) {
      const testId = `privacy-entry-${entry.name.toLowerCase().replace(/[.\s]/g, "-")}`;
      const el = screen.getByTestId(testId);
      expect(el).toBeInTheDocument();
      expect(el).toHaveTextContent(entry.name);
    }

    // Ensure we have the expected count (not zero)
    expect(PROVIDER_PRIVACY_DATA.length).toBe(6);
  });

  it.each([
    ["OpenRouter", "openrouter", "openrouter.ai/privacy"],
    ["Anthropic", "anthropic", "privacy.claude.com"],
    ["OpenAI", "openai", "platform.openai.com"],
    ["Together.ai", "together-ai", "together.ai/privacy"],
    ["Ollama", "ollama", "ollama.com"],
    ["Groq", "groq", "groq.com/privacy"],
  ])(
    "renders source link for %s pointing to its privacy policy",
    (name, testIdSlug, urlFragment) => {
      render(<ProviderPrivacyInfo />);

      const link = screen.getByTestId(`privacy-source-${testIdSlug}`);
      expect(link).toBeInTheDocument();
      expect(link.tagName).toBe("A");
      expect(link).toHaveAttribute("target", "_blank");
      expect(link).toHaveAttribute("rel", "noopener noreferrer");

      const href = link.getAttribute("href") ?? "";
      expect(href).toContain(urlFragment);
    },
  );

  it("displays the privacy summary text for each provider", () => {
    render(<ProviderPrivacyInfo />);

    for (const entry of PROVIDER_PRIVACY_DATA) {
      const testId = `privacy-entry-${entry.name.toLowerCase().replace(/[.\s]/g, "-")}`;
      const el = screen.getByTestId(testId);
      expect(el).toHaveTextContent(entry.summary);
    }
  });

  it("applies green tier styling to Anthropic entry", () => {
    render(<ProviderPrivacyInfo />);

    const anthropicEntry = screen.getByTestId("privacy-entry-anthropic");
    expect(anthropicEntry.className).toContain("bg-green-50");
    expect(anthropicEntry.className).toContain("text-green-800");
  });

  it("applies yellow tier styling to OpenRouter entry", () => {
    render(<ProviderPrivacyInfo />);

    const openRouterEntry = screen.getByTestId("privacy-entry-openrouter");
    expect(openRouterEntry.className).toContain("bg-yellow-50");
    expect(openRouterEntry.className).toContain("text-yellow-800");
  });

  it("applies blue tier styling to Ollama entry", () => {
    render(<ProviderPrivacyInfo />);

    const ollamaEntry = screen.getByTestId("privacy-entry-ollama");
    expect(ollamaEntry.className).toContain("bg-blue-50");
    expect(ollamaEntry.className).toContain("text-blue-800");
  });

  it("renders exactly 6 provider entries", () => {
    render(<ProviderPrivacyInfo />);

    const container = screen.getByTestId("provider-privacy-info");
    const entries = within(container).getAllByTestId(/^privacy-entry-/);
    expect(entries).toHaveLength(6);
  });
});
