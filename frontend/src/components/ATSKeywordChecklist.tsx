/**
 * ATSKeywordChecklist — categorized checklist of ATS keywords extracted from
 * a job description, with match/unmatch indicators against the candidate
 * profile. Used on the ApplicationDetail page to show which signals the
 * candidate already demonstrates and which still need work.
 */

import { Check, X } from "lucide-react";
import type { ATSKeyword, ATSKeywordCategory } from "@/api/types";

interface ATSKeywordChecklistProps {
  readonly keywords: ATSKeyword[];
}

const CATEGORY_LABELS: Record<ATSKeywordCategory, string> = {
  technical: "Technical",
  soft_skill: "Soft Skills",
  tool: "Tools",
  certification: "Certifications",
  domain: "Domain",
};

const CATEGORY_ORDER: ATSKeywordCategory[] = [
  "technical",
  "tool",
  "certification",
  "domain",
  "soft_skill",
];

export function ATSKeywordChecklist({ keywords }: ATSKeywordChecklistProps) {
  if (!keywords || keywords.length === 0) return null;

  // Group keywords by category
  const groups: Record<ATSKeywordCategory, ATSKeyword[]> = {
    technical: [],
    soft_skill: [],
    tool: [],
    certification: [],
    domain: [],
  };
  for (const kw of keywords) {
    groups[kw.category].push(kw);
  }

  const matchedCount = keywords.filter((k) => k.matched).length;

  return (
    <div data-testid="ats-keyword-checklist" className="space-y-3">
      <div className="text-xs text-gray-500">
        {matchedCount} of {keywords.length} keywords matched
      </div>
      <div className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
        {CATEGORY_ORDER.filter((cat) => groups[cat].length > 0).map((cat) => (
          <div key={cat}>
            <h4 className="mb-1 text-sm font-semibold text-gray-700">
              {CATEGORY_LABELS[cat]}
            </h4>
            <ul className="space-y-1">
              {groups[cat].map((kw) => (
                <li
                  key={`${cat}-${kw.keyword}`}
                  className="flex items-center gap-2 text-sm"
                >
                  {kw.matched ? (
                    <Check
                      className="h-4 w-4 flex-shrink-0 text-green-600"
                      data-testid={`ats-match-${kw.keyword}`}
                    />
                  ) : (
                    <X
                      className="h-4 w-4 flex-shrink-0 text-red-500"
                      data-testid={`ats-miss-${kw.keyword}`}
                    />
                  )}
                  <span
                    className={
                      kw.matched ? "text-gray-900" : "text-gray-500"
                    }
                  >
                    {kw.keyword}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
