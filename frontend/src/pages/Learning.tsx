import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchGapRecommendations,
  createRecommendation,
  updateLearningStatus,
} from "@/api/learning";
import { DEFAULT_PROFILE_ID } from "@/api/applications";
import {
  BookOpen,
  PlusCircle,
  Loader2,
  CheckCircle2,
  Play,
  Clock,
  ExternalLink,
  X,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import type {
  LearningResource,
  LearningStatus,
  ResourceType,
  Difficulty,
  GapItem,
  GapAnalysisResponse,
  TemplateRecommendation,
} from "@/api/types";

const STATUS_LABELS: Record<LearningStatus, string> = {
  not_started: "Not Started",
  in_progress: "In Progress",
  completed: "Completed",
};

const STATUS_COLORS: Record<LearningStatus, string> = {
  not_started: "bg-gray-100 text-gray-700",
  in_progress: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
};

const TYPE_LABELS: Record<ResourceType, string> = {
  free_course: "Free Course",
  paid_course: "Paid Course",
  hands_on_project: "Hands-on Project",
};

const TYPE_COLORS: Record<ResourceType, string> = {
  free_course: "bg-emerald-100 text-emerald-800",
  paid_course: "bg-purple-100 text-purple-800",
  hands_on_project: "bg-orange-100 text-orange-800",
};

const DIFFICULTY_LABELS: Record<Difficulty, string> = {
  beginner: "Beginner",
  intermediate: "Intermediate",
  advanced: "Advanced",
  expert: "Expert",
};

const ALL_TYPES: ResourceType[] = [
  "free_course",
  "paid_course",
  "hands_on_project",
];
const ALL_DIFFICULTIES: Difficulty[] = [
  "beginner",
  "intermediate",
  "advanced",
  "expert",
];

// ---------------------------------------------------------------------------
// Add Resource Dialog
// ---------------------------------------------------------------------------

function AddResourceDialog({
  gapId,
  onClose,
}: Readonly<{
  gapId: number;
  onClose: () => void;
}>) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("");
  const [resourceType, setResourceType] = useState<ResourceType>("free_course");
  const [estimatedHours, setEstimatedHours] = useState("");
  const [difficulty, setDifficulty] = useState<Difficulty>("beginner");
  const [provider, setProvider] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      createRecommendation(gapId, {
        profile_id: DEFAULT_PROFILE_ID,
        title,
        url: url || undefined,
        resource_type: resourceType,
        estimated_hours: estimatedHours ? Number.parseFloat(estimatedHours) : undefined,
        difficulty,
        provider: provider || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["gap-recommendations", gapId] });
      onClose();
    },
  });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
    >
      <button
        type="button"
        className="absolute inset-0 h-full w-full cursor-default bg-black/50"
        onClick={onClose}
        onKeyDown={(e) => { if (e.key === 'Escape') onClose(); }}
        aria-label="Close dialog"
        tabIndex={-1}
        aria-hidden="true"
      />
      <div
        className="relative w-full max-w-md rounded-lg bg-white p-6 shadow-xl"
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">
            Add Learning Resource
          </h2>
          <button
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:text-gray-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (title.trim()) mutation.mutate();
          }}
          className="mt-4 space-y-4"
        >
          <div>
            <label htmlFor="add-resource-title" className="block text-sm font-medium text-gray-700">
              Title *
            </label>
            <input
              id="add-resource-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Kubernetes Deep Dive"
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              required
            />
          </div>
          <div>
            <label htmlFor="add-resource-url" className="block text-sm font-medium text-gray-700">
              URL
            </label>
            <input
              id="add-resource-url"
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://..."
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="add-resource-type" className="block text-sm font-medium text-gray-700">
                Type
              </label>
              <select
                id="add-resource-type"
                value={resourceType}
                onChange={(e) => setResourceType(e.target.value as ResourceType)}
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                {ALL_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {TYPE_LABELS[t]}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="add-resource-difficulty" className="block text-sm font-medium text-gray-700">
                Difficulty
              </label>
              <select
                id="add-resource-difficulty"
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value as Difficulty)}
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                {ALL_DIFFICULTIES.map((d) => (
                  <option key={d} value={d}>
                    {DIFFICULTY_LABELS[d]}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="add-resource-hours" className="block text-sm font-medium text-gray-700">
                Estimated Hours
              </label>
              <input
                id="add-resource-hours"
                type="number"
                value={estimatedHours}
                onChange={(e) => setEstimatedHours(e.target.value)}
                placeholder="e.g. 20"
                min="0"
                step="0.5"
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
            <div>
              <label htmlFor="add-resource-provider" className="block text-sm font-medium text-gray-700">
                Provider
              </label>
              <input
                id="add-resource-provider"
                type="text"
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                placeholder="e.g. Coursera"
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!title.trim() || mutation.isPending}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {mutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Add Resource"
              )}
            </button>
          </div>
          {mutation.isError && (
            <p className="text-sm text-red-600">
              Failed to add resource. Please try again.
            </p>
          )}
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Resource Card
// ---------------------------------------------------------------------------

function ResourceCard({
  resource,
  onStatusChange,
}: Readonly<{
  resource: LearningResource;
  onStatusChange: (id: number, status: LearningStatus) => void;
}>) {
  let nextStatus: LearningStatus | null;
  if (resource.status === "not_started") {
    nextStatus = "in_progress";
  } else if (resource.status === "in_progress") {
    nextStatus = "completed";
  } else {
    nextStatus = null;
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h4 className="truncate font-medium text-gray-900">
              {resource.title}
            </h4>
            {resource.url && (
              <a
                href={resource.url}
                target="_blank"
                rel="noopener noreferrer"
                className="shrink-0 text-blue-500 hover:text-blue-700"
              >
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            )}
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                TYPE_COLORS[resource.resource_type] ??
                "bg-gray-100 text-gray-700"
              }`}
            >
              {TYPE_LABELS[resource.resource_type] ??
                resource.resource_type}
            </span>
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                STATUS_COLORS[resource.status] ?? "bg-gray-100 text-gray-700"
              }`}
            >
              {STATUS_LABELS[resource.status] ?? resource.status}
            </span>
            {resource.difficulty && (
              <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
                {DIFFICULTY_LABELS[resource.difficulty] ?? resource.difficulty}
              </span>
            )}
          </div>
          <div className="mt-2 flex items-center gap-3 text-xs text-gray-500">
            {resource.estimated_hours !== null && (
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {resource.estimated_hours}h
              </span>
            )}
            {resource.provider && <span>{resource.provider}</span>}
          </div>
        </div>
        {nextStatus && (
          <button
            onClick={() => onStatusChange(resource.id, nextStatus)}
            className={`shrink-0 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              nextStatus === "in_progress"
                ? "bg-blue-50 text-blue-700 hover:bg-blue-100"
                : "bg-green-50 text-green-700 hover:bg-green-100"
            }`}
          >
            {nextStatus === "in_progress" ? (
              <span className="flex items-center gap-1">
                <Play className="h-3 w-3" />
                Start
              </span>
            ) : (
              <span className="flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3" />
                Complete
              </span>
            )}
          </button>
        )}
        {resource.status === "completed" && (
          <CheckCircle2 className="h-5 w-5 shrink-0 text-green-500" />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Gap Recommendations Section – helpers
// ---------------------------------------------------------------------------

function getDistanceBarColor(distance: number): string {
  if (distance >= 3) return "bg-red-400";
  if (distance >= 2) return "bg-yellow-400";
  return "bg-blue-400";
}

function getReadinessStyle(score: number): string {
  if (score >= 80) return "bg-green-100 text-green-800";
  if (score >= 50) return "bg-yellow-100 text-yellow-800";
  return "bg-red-100 text-red-800";
}

// ---------------------------------------------------------------------------
// Gap Recommendations Section
// ---------------------------------------------------------------------------

function GapSection({
  gap,
  applicationId,
}: Readonly<{
  gap: GapItem & { id: number };
  applicationId: number;
}>) {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(true);
  const [showAddDialog, setShowAddDialog] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["gap-recommendations", gap.id],
    queryFn: () => fetchGapRecommendations(gap.id, DEFAULT_PROFILE_ID),
    enabled: expanded,
  });

  const statusMutation = useMutation({
    mutationFn: ({
      resourceId,
      status,
    }: {
      resourceId: number;
      status: LearningStatus;
    }) =>
      updateLearningStatus(resourceId, {
        profile_id: DEFAULT_PROFILE_ID,
        status,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["gap-recommendations", gap.id],
      });
      queryClient.invalidateQueries({
        queryKey: ["gap-analysis", applicationId],
      });
      queryClient.invalidateQueries({ queryKey: ["skills"] });
    },
  });

  const severityColorMap: Record<string, string> = {
    critical: "text-red-600 bg-red-50",
    "nice-to-have": "text-yellow-600 bg-yellow-50",
  };
  const severityColor = severityColorMap[gap.severity] ?? "text-gray-600 bg-gray-50";

  const distanceBar = (
    <div className="flex items-center gap-1">
      {[1, 2, 3].map((level) => (
        <div
          key={level}
          className={`h-2 w-4 rounded-sm ${
            level <= gap.distance
              ? getDistanceBarColor(gap.distance)
              : "bg-gray-200"
          }`}
        />
      ))}
    </div>
  );

  return (
    <div className="rounded-lg border border-gray-200 bg-white">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between p-4 text-left hover:bg-gray-50"
      >
        <div className="flex items-center gap-3">
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-gray-400" />
          ) : (
            <ChevronRight className="h-4 w-4 text-gray-400" />
          )}
          <div>
            <span className="font-medium text-gray-900">{gap.skill_name}</span>
            <div className="mt-1 flex items-center gap-2">
              <span
                className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${severityColor}`}
              >
                {gap.severity}
              </span>
              {distanceBar}
              <span className="text-xs text-gray-500">
                {gap.current_level ?? "missing"} → {gap.required_level}
              </span>
            </div>
          </div>
        </div>
        <span className="text-xs text-gray-400">
          {(data?.recommendations?.length ?? 0) + (data?.template_recommendations?.length ?? 0)} resources
        </span>
      </button>

      {expanded && (
        <div className="border-t border-gray-100 p-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
            </div>
          ) : (data?.recommendations?.length ?? 0) > 0 ? (
            <div className="space-y-3">
              {data.recommendations.map((resource) => (
                <ResourceCard
                  key={resource.id}
                  resource={resource}
                  onStatusChange={(id, status) =>
                    statusMutation.mutate({ resourceId: id, status })
                  }
                />
              ))}
              <button
                onClick={() => setShowAddDialog(true)}
                className="flex w-full items-center justify-center gap-1.5 rounded-md border border-dashed border-gray-300 py-2 text-sm text-gray-500 hover:border-gray-400 hover:text-gray-600"
              >
                <PlusCircle className="h-4 w-4" />
                Add resource
              </button>
            </div>
          ) : data?.template_recommendations &&
            data.template_recommendations.length > 0 ? (
            <div className="space-y-3">
              <p className="text-xs font-medium text-gray-500">
                Suggested learning resources:
              </p>
              {data.template_recommendations.map(
                (tmpl: TemplateRecommendation, idx: number) => (
                  <div
                    key={idx}
                    className="rounded-lg border border-gray-200 bg-gray-50 p-4 shadow-sm"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <h4 className="truncate font-medium text-gray-900">
                            {tmpl.title}
                          </h4>
                          {tmpl.url && (
                            <a
                              href={tmpl.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="shrink-0 text-blue-500 hover:text-blue-700"
                            >
                              <ExternalLink className="h-3.5 w-3.5" />
                            </a>
                          )}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          <span
                            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                              TYPE_COLORS[
                                tmpl.resource_type
                              ] ?? "bg-gray-100 text-gray-700"
                            }`}
                          >
                            {TYPE_LABELS[
                              tmpl.resource_type
                            ] ?? tmpl.resource_type}
                          </span>
                          {tmpl.difficulty && (
                            <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
                              {DIFFICULTY_LABELS[
                                tmpl.difficulty as Difficulty
                              ] ?? tmpl.difficulty}
                            </span>
                          )}
                        </div>
                        <div className="mt-2 flex items-center gap-3 text-xs text-gray-500">
                          {tmpl.estimated_hours !== null && (
                            <span className="flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {tmpl.estimated_hours}h
                            </span>
                          )}
                          {tmpl.provider && <span>{tmpl.provider}</span>}
                        </div>
                      </div>
                    </div>
                  </div>
                ),
              )}
              <button
                onClick={() => setShowAddDialog(true)}
                className="flex w-full items-center justify-center gap-1.5 rounded-md border border-dashed border-gray-300 py-2 text-sm text-gray-500 hover:border-gray-400 hover:text-gray-600"
              >
                <PlusCircle className="h-4 w-4" />
                Add your own resource
              </button>
            </div>
          ) : (
            <div className="rounded-lg border-2 border-dashed border-gray-200 py-6 text-center">
              <BookOpen className="mx-auto h-8 w-8 text-gray-300" />
              <p className="mt-2 text-sm text-gray-500">
                No recommendations available.
              </p>
              <button
                onClick={() => setShowAddDialog(true)}
                className="mt-3 inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
              >
                <PlusCircle className="h-4 w-4" />
                Add your own
              </button>
            </div>
          )}
        </div>
      )}

      {showAddDialog && (
        <AddResourceDialog
          gapId={gap.id}
          onClose={() => setShowAddDialog(false)}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Learning Page
// ---------------------------------------------------------------------------

export function Learning() {
  const [applicationId, setApplicationId] = useState<number | null>(null);

  // Fetch applications to select from
  const { data: appsData, isLoading: appsLoading } = useQuery({
    queryKey: ["applications-for-learning"],
    queryFn: async () => {
      const resp = await fetch(
        `/api/applications?profile_id=${DEFAULT_PROFILE_ID}`,
      );
      if (!resp.ok) throw new Error("Failed to fetch applications");
      return resp.json();
    },
  });

  // Fetch gap analysis for selected application
  const { data: gapData, isLoading: gapsLoading } = useQuery<GapAnalysisResponse>({
    queryKey: ["gap-analysis", applicationId],
    queryFn: async () => {
      const resp = await fetch(
        `/api/applications/${applicationId}/gaps?profile_id=${DEFAULT_PROFILE_ID}`,
      );
      if (!resp.ok) throw new Error("Failed to fetch gaps");
      return resp.json();
    },
    enabled: applicationId !== null,
  });

  // Fetch job requirements to get gap IDs
  const { data: requirementsData } = useQuery<
    { id: number; skill_name: string }[]
  >({
    queryKey: ["job-requirements", applicationId],
    queryFn: async () => {
      const resp = await fetch(
        `/api/applications/${applicationId}/requirements?profile_id=${DEFAULT_PROFILE_ID}`,
      );
      if (!resp.ok) return [];
      return resp.json();
    },
    enabled: applicationId !== null,
  });

  const applications = appsData?.applications ?? [];
  const gaps = gapData?.gaps ?? [];

  // Map gap items to include the requirement ID (gap_id)
  const gapsWithIds = gaps
    .filter((g: GapItem) => g.distance > 0)
    .map((g: GapItem) => {
      const req = requirementsData?.find(
        (r) => r.skill_name.toLowerCase() === g.skill_name.toLowerCase(),
      );
      return { ...g, id: req?.id ?? 0 };
    })
    .filter((g) => g.id > 0);

  if (appsLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <section className="space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Learning Paths</h1>
      </header>

      {/* Application selector */}
      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <label htmlFor="learning-application-select" className="block text-sm font-medium text-gray-700">
          Select an application to view skill gaps and learning recommendations
        </label>
        <select
          id="learning-application-select"
          value={applicationId ?? ""}
          onChange={(e) =>
            setApplicationId(e.target.value ? Number.parseInt(e.target.value) : null)
          }
          className="mt-2 w-full max-w-md rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="">Choose an application...</option>
          {applications.map(
            (app: { id: number; company: string; role: string }) => (
              <option key={app.id} value={app.id}>
                {app.company} — {app.role}
              </option>
            ),
          )}
        </select>
      </div>

      {/* No application selected */}
      {!applicationId && (
        <div className="rounded-lg border-2 border-dashed border-gray-300 bg-white py-12 text-center">
          <BookOpen className="mx-auto h-12 w-12 text-gray-400" />
          <h2 className="mt-4 text-lg font-semibold text-gray-900">
            Select an Application
          </h2>
          <p className="mt-2 text-sm text-gray-500">
            Choose an application above to see skill gaps and add learning
            resources.
          </p>
        </div>
      )}

      {/* Loading gaps */}
      {applicationId && gapsLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
        </div>
      )}

      {/* Readiness score */}
      {gapData && (
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-gray-900">
                {gapData.company} — {gapData.role}
              </h2>
              <p className="text-sm text-gray-500">
                {gapData.gaps_count} skill gaps out of{" "}
                {gapData.total_requirements} requirements
              </p>
            </div>
            {(() => {
              const rounded = Math.round(gapData.readiness_score);
              return (
                <div
                  className={`rounded-lg px-4 py-2 text-center ${getReadinessStyle(rounded)}`}
                >
                  <div className="text-2xl font-bold">
                    {rounded}
                  </div>
                  <div className="text-xs">Readiness</div>
                </div>
              );
            })()}
          </div>
        </div>
      )}

      {/* Gaps with learning resources */}
      {applicationId && gapData && gapsWithIds.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Skill Gaps & Learning Resources
          </h2>
          {gapsWithIds.map((gap) => (
            <GapSection
              key={gap.id}
              gap={gap}
              applicationId={applicationId}
            />
          ))}
        </div>
      )}

      {/* No requirements parsed yet */}
      {applicationId && gapData?.total_requirements === 0 && (
        <div className="rounded-lg border-2 border-dashed border-gray-300 bg-white py-8 text-center">
          <BookOpen className="mx-auto h-10 w-10 text-gray-400" />
          <h2 className="mt-3 text-lg font-semibold text-gray-900">
            No Job Requirements Found
          </h2>
          <p className="mt-2 max-w-md mx-auto text-sm text-gray-500">
            This application doesn't have any parsed job requirements yet.
            Add requirements from the application detail page or run
            discovery scoring to auto-parse them.
          </p>
        </div>
      )}

      {/* All requirements met */}
      {applicationId && gapData?.total_requirements > 0 && gapsWithIds.length === 0 && (
        <div className="rounded-lg border-2 border-dashed border-gray-300 bg-white py-8 text-center">
          <CheckCircle2 className="mx-auto h-10 w-10 text-green-500" />
          <h2 className="mt-3 text-lg font-semibold text-gray-900">
            All Requirements Met!
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            You meet all the requirements for this position.
          </p>
        </div>
      )}
    </section>
  );
}
