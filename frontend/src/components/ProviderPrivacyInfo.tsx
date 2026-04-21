/**
 * ProviderPrivacyInfo — Factual privacy disclosures for AI providers.
 *
 * Shows a concise privacy summary for each supported AI provider with
 * source links. Displayed inside the ai_providers IntegrationPanel when
 * expanded. Not fear-mongering — just documented facts with sources.
 */

import { Shield, ExternalLink } from "lucide-react";
import type { ProviderPrivacyEntry } from "@/components/providerPrivacyData";
import { PROVIDER_PRIVACY_DATA } from "@/components/providerPrivacyData";

const TIER_STYLES: Record<ProviderPrivacyEntry["tier"], string> = {
  green: "bg-green-50 text-green-800",
  yellow: "bg-yellow-50 text-yellow-800",
  blue: "bg-blue-50 text-blue-800",
};

const TIER_DOT: Record<ProviderPrivacyEntry["tier"], string> = {
  green: "bg-green-400",
  yellow: "bg-yellow-400",
  blue: "bg-blue-400",
};

function PrivacyRow({ entry }: Readonly<{ entry: ProviderPrivacyEntry }>) {
  return (
    <div
      data-testid={`privacy-entry-${entry.name.toLowerCase().replace(/[.\s]/g, "-")}`}
      className={`flex items-start gap-2 rounded-md px-3 py-2 text-sm ${TIER_STYLES[entry.tier]}`}
    >
      <span
        className={`mt-1.5 h-2 w-2 flex-shrink-0 rounded-full ${TIER_DOT[entry.tier]}`}
        aria-hidden="true"
      />
      <div className="min-w-0 flex-1">
        <span className="font-medium">{entry.name}</span>
        <span className="mx-1">&mdash;</span>
        <span>{entry.summary}</span>
        <a
          href={entry.sourceUrl}
          target="_blank"
          rel="noopener noreferrer"
          data-testid={`privacy-source-${entry.name.toLowerCase().replace(/[.\s]/g, "-")}`}
          className="ml-1.5 inline-flex items-center gap-0.5 underline decoration-current/40 hover:decoration-current"
        >
          {entry.sourceLabel}
          <ExternalLink className="inline h-3 w-3" />
        </a>
      </div>
    </div>
  );
}

export function ProviderPrivacyInfo() {
  return (
    <div data-testid="provider-privacy-info" className="mt-4">
      <div className="flex items-center gap-2 text-sm font-medium text-gray-700">
        <Shield className="h-4 w-4" />
        <span>Provider Privacy Disclosures</span>
      </div>
      <p className="mt-1 text-xs text-gray-500">
        How each provider handles your data. Sources linked for verification.
      </p>
      <div className="mt-2 space-y-1">
        {PROVIDER_PRIVACY_DATA.map((entry) => (
          <PrivacyRow key={entry.name} entry={entry} />
        ))}
      </div>
    </div>
  );
}
