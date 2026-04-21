/**
 * Privacy data for each AI provider Kestrel supports.
 * Based on docs/research/provider-privacy-audit.md (2026-04-21).
 *
 * Separated from the React component to satisfy react-refresh/only-export-components.
 */

export interface ProviderPrivacyEntry {
  /** Provider display name */
  readonly name: string;
  /** One-line privacy summary */
  readonly summary: string;
  /** Privacy tier: green (best), yellow (moderate), blue (local) */
  readonly tier: "green" | "yellow" | "blue";
  /** URL to the provider's official privacy/data policy */
  readonly sourceUrl: string;
  /** Short label for the source link */
  readonly sourceLabel: string;
}

export const PROVIDER_PRIVACY_DATA: readonly ProviderPrivacyEntry[] = [
  {
    name: "OpenRouter",
    summary:
      "Data may be logged; privacy depends on the underlying model provider's policy.",
    tier: "yellow",
    sourceUrl: "https://openrouter.ai/privacy",
    sourceLabel: "OpenRouter Privacy Policy",
  },
  {
    name: "Anthropic",
    summary:
      "Does not train on API data. 7-day retention (shortest major provider). Zero Data Retention available via addendum.",
    tier: "green",
    sourceUrl:
      "https://privacy.claude.com/en/articles/10023548-how-long-do-you-store-my-data",
    sourceLabel: "Anthropic Data Retention",
  },
  {
    name: "OpenAI",
    summary:
      "API data not used for training by default since March 2023. 30-day retention for abuse monitoring.",
    tier: "yellow",
    sourceUrl: "https://platform.openai.com/docs/guides/your-data",
    sourceLabel: "OpenAI Data Controls",
  },
  {
    name: "Together.ai",
    summary:
      "Zero Data Retention (ZDR) — no training on user data, no data stored after response.",
    tier: "green",
    sourceUrl: "https://www.together.ai/privacy",
    sourceLabel: "Together.ai Privacy Policy",
  },
  {
    name: "Ollama",
    summary: "Runs locally on your machine. No data leaves your device.",
    tier: "blue",
    sourceUrl: "https://ollama.com",
    sourceLabel: "Ollama — Local AI",
  },
  {
    name: "Groq",
    summary:
      "Does not train on API data. Processes requests for inference only.",
    tier: "green",
    sourceUrl: "https://groq.com/privacy-policy/",
    sourceLabel: "Groq Privacy Policy",
  },
] as const;
