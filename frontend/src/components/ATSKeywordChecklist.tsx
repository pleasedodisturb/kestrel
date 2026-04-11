import { Check, X } from "lucide-react";
import type { ATSKeyword } from "@/api/types";

interface ATSKeywordChecklistProps {
  readonly keywords: ATSKeyword[] | null | undefined;
}

const CATEGORY_LABELS: Record<string, string> = {
  technical: "Technical Skills",
  soft_skill: "Soft Skills",
  tool: "Tools & Platforms",
  certification: "Certifications",
  domain: "Domain Knowledge",
};

export default function ATSKeywordChecklist({ keywords }: ATSKeywordChecklistProps) {
  if (!keywords || keywords.length === 0) return null;

  const grouped = keywords.reduce<Record<string, ATSKeyword[]>>((acc, kw) => {
    const cat = kw.category || "technical";
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(kw);
    return acc;
  }, {});

  const matchedCount = keywords.filter((k) => k.matched).length;

  return (
    <div className="w-full">
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-sm font-medium text-gray-700">ATS Keywords</h4>
        <span className="text-xs text-gray-500">
          {matchedCount}/{keywords.length} matched
        </span>
      </div>
      <div className="space-y-3">
        {Object.entries(grouped).map(([category, kws]) => (
          <div key={category}>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-400">
              {CATEGORY_LABELS[category] ?? category}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {kws.map((kw) => (
                <span
                  key={kw.keyword}
                  className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs ${
                    kw.matched
                      ? "bg-green-50 text-green-700"
                      : "bg-red-50 text-red-600"
                  }`}
                >
                  {kw.matched ? (
                    <Check className="h-3 w-3" />
                  ) : (
                    <X className="h-3 w-3" />
                  )}
                  {kw.keyword}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
