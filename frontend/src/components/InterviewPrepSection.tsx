/**
 * InterviewPrepSection — interview preparation panel for ApplicationDetail.
 *
 * Shows personalized topics, practice questions, and checklist with progress
 * tracking. Persists completion state across sessions.
 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type {
  InterviewPrepResponse,
  PrepTopic,
  PrepQuestion,
  PrepChecklistItem,
} from "@/api/types";
import {
  BookOpen,
  CheckCircle2,
  Circle,
  Clock,
  MessageSquare,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Color lookup maps for badge / bar styling
// ---------------------------------------------------------------------------

const PROGRESS_BADGE_COLORS: Record<string, string> = {
  complete: "bg-green-100 text-green-700",
  started: "bg-amber-100 text-amber-700",
  default: "bg-gray-100 text-gray-600",
};

const PROGRESS_BAR_COLORS: Record<string, string> = {
  complete: "bg-green-500",
  started: "bg-amber-400",
  default: "bg-gray-300",
};

const RELEVANCE_COLORS: Record<string, string> = {
  high: "bg-red-100 text-red-700",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-gray-100 text-gray-600",
};

const DIFFICULTY_COLORS: Record<string, string> = {
  high: "bg-purple-100 text-purple-700",
  medium: "bg-blue-100 text-blue-700",
  low: "bg-gray-100 text-gray-600",
};

const QUESTION_DIFFICULTY_COLORS: Record<string, string> = {
  high: "bg-purple-100 text-purple-700",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-gray-100 text-gray-600",
};

const PRIORITY_COLORS: Record<string, string> = {
  high: "bg-red-100 text-red-700",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-gray-100 text-gray-600",
};

function progressKey(percentage: number): string {
  if (percentage === 100) return "complete";
  if (percentage > 0) return "started";
  return "default";
}

interface InterviewPrepSectionProps {
  readonly applicationId: number;
  readonly profileId: number;
}

async function fetchInterviewPrep(
  applicationId: number,
  profileId: number,
): Promise<InterviewPrepResponse> {
  const res = await fetch(
    `/api/applications/${applicationId}/interview-prep?profile_id=${profileId}`,
  );
  if (!res.ok) {
    throw new Error(`Failed to load interview prep: ${res.statusText}`);
  }
  return res.json();
}

async function togglePrepItem(
  itemId: number,
  profileId: number,
  completed: boolean,
): Promise<PrepChecklistItem> {
  const res = await fetch(
    `/api/applications/interview-prep/items/${itemId}?profile_id=${profileId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ completed }),
    },
  );
  if (!res.ok) {
    throw new Error(`Failed to update prep item: ${res.statusText}`);
  }
  return res.json();
}

export function InterviewPrepSection({
  applicationId,
  profileId,
}: InterviewPrepSectionProps) {
  const queryClient = useQueryClient();
  const [expandedSections, setExpandedSections] = useState<
    Record<string, boolean>
  >({
    topics: true,
    questions: true,
    checklist: true,
  });

  const {
    data: prep,
    isLoading,
    error,
  } = useQuery<InterviewPrepResponse>({
    queryKey: ["interview-prep", applicationId, profileId],
    queryFn: () => fetchInterviewPrep(applicationId, profileId),
  });

  const toggleMutation = useMutation({
    mutationFn: ({
      itemId,
      completed,
    }: {
      itemId: number;
      completed: boolean;
    }) => togglePrepItem(itemId, profileId, completed),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["interview-prep", applicationId, profileId],
      });
    },
  });

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  if (isLoading) {
    return (
      <div
        data-testid="interview-prep-loading"
        className="rounded-lg border bg-white p-6 shadow-sm"
      >
        <h2 className="mb-4 text-lg font-semibold text-gray-900">
          Interview Prep
        </h2>
        <div className="flex items-center justify-center py-8">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-300 border-t-gray-900" />
          <span className="ml-2 text-sm text-gray-500">
            Generating prep...
          </span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div
        data-testid="interview-prep-error"
        className="rounded-lg border bg-white p-6 shadow-sm"
      >
        <h2 className="mb-4 text-lg font-semibold text-gray-900">
          Interview Prep
        </h2>
        <p className="text-sm text-red-600">
          {error instanceof Error ? error.message : String(error)}
        </p>
      </div>
    );
  }

  if (!prep) return null;

  return (
    <div
      data-testid="interview-prep-section"
      className="space-y-4 rounded-lg border bg-white p-6 shadow-sm"
    >
      {/* Header with progress */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">
          Interview Prep
        </h2>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 text-sm text-gray-500">
            <Clock className="h-4 w-4" />
            {prep.total_prep_minutes} min
          </div>
          <div
            data-testid="prep-progress"
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium",
              PROGRESS_BADGE_COLORS[progressKey(prep.progress_percentage)],
            )}
          >
            {prep.completed_items}/{prep.total_items} done (
            {Math.round(prep.progress_percentage)}%)
          </div>
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100">
        <div
          data-testid="prep-progress-bar"
          className={cn(
            "h-full rounded-full transition-all",
            PROGRESS_BAR_COLORS[progressKey(prep.progress_percentage)],
          )}
          style={{ width: `${prep.progress_percentage}%` }}
        />
      </div>

      {/* Research prompt */}
      {prep.research_prompt && (
        <div
          data-testid="research-prompt"
          className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-3"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-500" />
          <p className="text-sm text-amber-700">{prep.research_prompt}</p>
        </div>
      )}

      {/* Topics */}
      <CollapsibleSection
        title="Topics"
        icon={<BookOpen className="h-4 w-4" />}
        count={prep.topics.length}
        expanded={expandedSections.topics}
        onToggle={() => toggleSection("topics")}
      >
        <div className="space-y-2">
          {prep.topics.map((topic, i) => (
            <TopicCard key={i} topic={topic} />
          ))}
        </div>
      </CollapsibleSection>

      {/* Practice Questions */}
      <CollapsibleSection
        title="Practice Questions"
        icon={<MessageSquare className="h-4 w-4" />}
        count={prep.questions.length}
        expanded={expandedSections.questions}
        onToggle={() => toggleSection("questions")}
      >
        <div className="space-y-3">
          {prep.questions.map((q, i) => (
            <QuestionCard key={i} question={q} index={i + 1} />
          ))}
        </div>
      </CollapsibleSection>

      {/* Checklist */}
      <CollapsibleSection
        title="Prep Checklist"
        icon={<CheckCircle2 className="h-4 w-4" />}
        count={prep.checklist.length}
        expanded={expandedSections.checklist}
        onToggle={() => toggleSection("checklist")}
      >
        <div className="space-y-1">
          {prep.checklist.map((item) => (
            <ChecklistItemRow
              key={item.id}
              item={item}
              onToggle={(completed) =>
                toggleMutation.mutate({
                  itemId: item.id,
                  completed,
                })
              }
              isToggling={toggleMutation.isPending}
            />
          ))}
        </div>
      </CollapsibleSection>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function CollapsibleSection({
  title,
  icon,
  count,
  expanded,
  onToggle,
  children,
}: Readonly<{
  title: string;
  icon: React.ReactNode;
  count: number;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}>) {
  return (
    <div className="border-t pt-3">
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between text-left"
      >
        <div className="flex items-center gap-2 text-sm font-medium text-gray-700">
          {icon}
          {title}
          <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500">
            {count}
          </span>
        </div>
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-gray-400" />
        ) : (
          <ChevronRight className="h-4 w-4 text-gray-400" />
        )}
      </button>
      {expanded && <div className="mt-3">{children}</div>}
    </div>
  );
}

function TopicCard({ topic }: Readonly<{ topic: PrepTopic }>) {
  return (
    <div className="flex items-center justify-between rounded-md border border-gray-100 bg-gray-50 px-3 py-2">
      <span className="text-sm text-gray-800">{topic.topic}</span>
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "rounded px-1.5 py-0.5 text-xs",
            RELEVANCE_COLORS[topic.relevance] ?? RELEVANCE_COLORS.low,
          )}
        >
          {topic.relevance}
        </span>
        <span
          className={cn(
            "rounded px-1.5 py-0.5 text-xs",
            DIFFICULTY_COLORS[topic.difficulty] ?? DIFFICULTY_COLORS.low,
          )}
        >
          {topic.difficulty}
        </span>
      </div>
    </div>
  );
}

function QuestionCard({
  question,
  index,
}: Readonly<{
  question: PrepQuestion;
  index: number;
}>) {
  return (
    <div className="rounded-md border border-gray-100 bg-gray-50 px-3 py-2">
      <div className="flex items-start gap-2">
        <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-gray-200 text-xs font-medium text-gray-600">
          {index}
        </span>
        <div className="flex-1">
          <p className="text-sm text-gray-800">{question.question}</p>
          <div className="mt-1 flex items-center gap-2">
            <span className="rounded bg-blue-50 px-1.5 py-0.5 text-xs text-blue-600">
              {question.category}
            </span>
            <span
              className={cn(
                "rounded px-1.5 py-0.5 text-xs",
                QUESTION_DIFFICULTY_COLORS[question.difficulty] ?? QUESTION_DIFFICULTY_COLORS.low,
              )}
            >
              {question.difficulty}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function ChecklistItemRow({
  item,
  onToggle,
  isToggling,
}: Readonly<{
  item: PrepChecklistItem;
  onToggle: (completed: boolean) => void;
  isToggling: boolean;
}>) {
  return (
    <div
      data-testid={`checklist-item-${item.id}`}
      className={cn(
        "flex items-center gap-3 rounded-md px-3 py-2 transition-colors",
        item.completed ? "bg-green-50" : "hover:bg-gray-50",
      )}
    >
      <button
        data-testid={`checklist-toggle-${item.id}`}
        onClick={() => onToggle(!item.completed)}
        disabled={isToggling}
        className="flex-shrink-0 disabled:opacity-50"
      >
        {item.completed ? (
          <CheckCircle2 className="h-5 w-5 text-green-500" />
        ) : (
          <Circle className="h-5 w-5 text-gray-300 hover:text-gray-400" />
        )}
      </button>
      <span
        className={cn(
          "flex-1 text-sm",
          item.completed
            ? "text-gray-400 line-through"
            : "text-gray-800",
        )}
      >
        {item.item}
      </span>
      <div className="flex items-center gap-2">
        <span className="flex items-center gap-1 text-xs text-gray-400">
          <Clock className="h-3 w-3" />
          {item.time_minutes}m
        </span>
        <span
          className={cn(
            "rounded px-1.5 py-0.5 text-xs",
            PRIORITY_COLORS[item.priority] ?? PRIORITY_COLORS.low,
          )}
        >
          {item.priority}
        </span>
      </div>
    </div>
  );
}
