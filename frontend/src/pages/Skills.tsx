import { useState, type ReactNode } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchSkills,
  createSkill,
  updateSkill,
  fetchSkillHistory,
  ingestSkills,
} from "@/api/skills";
import { DEFAULT_PROFILE_ID } from "@/api/applications";
import {
  FileText,
  Brain,
  PlusCircle,
  Search,
  Loader2,
  CheckCircle2,
  Sparkles,
  Pencil,
  History,
  X,
} from "lucide-react";
import type {
  Skill,
  SkillCategory,
  SkillProficiency,
  SkillHistoryEntry,
} from "@/api/types";

const CATEGORY_LABELS: Record<SkillCategory, string> = {
  technical: "Technical",
  domain: "Domain",
  soft: "Soft",
  tools: "Tools",
};

const CATEGORY_COLORS: Record<SkillCategory, string> = {
  technical: "bg-blue-100 text-blue-800",
  domain: "bg-purple-100 text-purple-800",
  soft: "bg-green-100 text-green-800",
  tools: "bg-orange-100 text-orange-800",
};

const PROFICIENCY_LABELS: Record<SkillProficiency, string> = {
  beginner: "Beginner",
  intermediate: "Intermediate",
  advanced: "Advanced",
  expert: "Expert",
};

const PROFICIENCY_COLORS: Record<SkillProficiency, string> = {
  beginner: "bg-gray-100 text-gray-700",
  intermediate: "bg-yellow-100 text-yellow-800",
  advanced: "bg-blue-100 text-blue-800",
  expert: "bg-emerald-100 text-emerald-800",
};

const ALL_CATEGORIES: SkillCategory[] = ["technical", "domain", "soft", "tools"];
const ALL_PROFICIENCIES: SkillProficiency[] = [
  "beginner",
  "intermediate",
  "advanced",
  "expert",
];

// ---------------------------------------------------------------------------
// Add Skill Dialog
// ---------------------------------------------------------------------------

function AddSkillDialog({
  onClose,
  profileId,
}: Readonly<{
  onClose: () => void;
  profileId: number;
}>) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [category, setCategory] = useState<SkillCategory>("technical");
  const [proficiency, setProficiency] = useState<SkillProficiency>("beginner");
  const [evidenceDetail, setEvidenceDetail] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      createSkill({
        profile_id: profileId,
        name,
        category,
        proficiency,
        evidence_source: "manual",
        evidence_detail: evidenceDetail || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["skills"] });
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
          <h2 className="text-lg font-semibold text-gray-900">Add Skill</h2>
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
            if (name.trim()) mutation.mutate();
          }}
          className="mt-4 space-y-4"
        >
          <div>
            <label htmlFor="add-skill-name" className="block text-sm font-medium text-gray-700">
              Name *
            </label>
            <input
              id="add-skill-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Kubernetes"
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              required
            />
          </div>
          <div>
            <label htmlFor="add-skill-category" className="block text-sm font-medium text-gray-700">
              Category
            </label>
            <select
              id="add-skill-category"
              value={category}
              onChange={(e) => setCategory(e.target.value as SkillCategory)}
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              {ALL_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {CATEGORY_LABELS[c]}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="add-skill-proficiency" className="block text-sm font-medium text-gray-700">
              Proficiency
            </label>
            <select
              id="add-skill-proficiency"
              value={proficiency}
              onChange={(e) =>
                setProficiency(e.target.value as SkillProficiency)
              }
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              {ALL_PROFICIENCIES.map((p) => (
                <option key={p} value={p}>
                  {PROFICIENCY_LABELS[p]}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="add-skill-evidence" className="block text-sm font-medium text-gray-700">
              Evidence / Notes
            </label>
            <textarea
              id="add-skill-evidence"
              value={evidenceDetail}
              onChange={(e) => setEvidenceDetail(e.target.value)}
              placeholder="Optional: describe your experience..."
              rows={3}
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
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
              disabled={!name.trim() || mutation.isPending}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {mutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Add Skill"
              )}
            </button>
          </div>
          {mutation.isError && (
            <p className="text-sm text-red-600">
              Failed to create skill. Please try again.
            </p>
          )}
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Edit Skill Dialog
// ---------------------------------------------------------------------------

function EditSkillDialog({
  skill,
  onClose,
  profileId,
}: Readonly<{
  skill: Skill;
  onClose: () => void;
  profileId: number;
}>) {
  const queryClient = useQueryClient();
  const [name, setName] = useState(skill.name);
  const [category, setCategory] = useState<SkillCategory>(skill.category);
  const [proficiency, setProficiency] = useState<SkillProficiency>(
    skill.proficiency
  );
  const [evidenceDetail, setEvidenceDetail] = useState(
    skill.evidence_detail ?? ""
  );

  const mutation = useMutation({
    mutationFn: () =>
      updateSkill(skill.id, profileId, {
        name,
        category,
        proficiency,
        evidence_detail: evidenceDetail.trim() === "" ? null : evidenceDetail,
        reason:
          proficiency !== skill.proficiency
            ? "Manual update via UI"
            : undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["skills"] });
      queryClient.invalidateQueries({
        queryKey: ["skill-history", skill.id],
      });
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
          <h2 className="text-lg font-semibold text-gray-900">Edit Skill</h2>
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
            if (name.trim()) mutation.mutate();
          }}
          className="mt-4 space-y-4"
        >
          <div>
            <label htmlFor="edit-skill-name" className="block text-sm font-medium text-gray-700">
              Name *
            </label>
            <input
              id="edit-skill-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              required
            />
          </div>
          <div>
            <label htmlFor="edit-skill-category" className="block text-sm font-medium text-gray-700">
              Category
            </label>
            <select
              id="edit-skill-category"
              value={category}
              onChange={(e) => setCategory(e.target.value as SkillCategory)}
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              {ALL_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {CATEGORY_LABELS[c]}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="edit-skill-proficiency" className="block text-sm font-medium text-gray-700">
              Proficiency
            </label>
            <select
              id="edit-skill-proficiency"
              value={proficiency}
              onChange={(e) =>
                setProficiency(e.target.value as SkillProficiency)
              }
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              {ALL_PROFICIENCIES.map((p) => (
                <option key={p} value={p}>
                  {PROFICIENCY_LABELS[p]}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="edit-skill-evidence" className="block text-sm font-medium text-gray-700">
              Evidence / Notes
            </label>
            <textarea
              id="edit-skill-evidence"
              value={evidenceDetail}
              onChange={(e) => setEvidenceDetail(e.target.value)}
              rows={3}
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
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
              disabled={!name.trim() || mutation.isPending}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {mutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Save Changes"
              )}
            </button>
          </div>
          {mutation.isError && (
            <p className="text-sm text-red-600">
              Failed to update skill. Please try again.
            </p>
          )}
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Skill History Panel
// ---------------------------------------------------------------------------

function SkillHistoryPanel({
  skill,
  onClose,
  profileId,
}: Readonly<{
  skill: Skill;
  onClose: () => void;
  profileId: number;
}>) {
  const { data: history, isLoading } = useQuery({
    queryKey: ["skill-history", skill.id, profileId],
    queryFn: () => fetchSkillHistory(skill.id, profileId),
  });

  let historyContent: ReactNode;
  if (isLoading) {
    historyContent = (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
      </div>
    );
  } else if (!history || history.length === 0) {
    historyContent = (
      <p className="py-4 text-sm text-gray-500">No history entries.</p>
    );
  } else {
    historyContent = (
      <div className="space-y-3">
        {history.map((entry: SkillHistoryEntry) => (
          <div
            key={entry.id}
            className="rounded-md border border-gray-200 bg-gray-50 p-3"
          >
            <div className="flex items-center gap-2">
              {entry.previous_proficiency ? (
                <>
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                      PROFICIENCY_COLORS[
                        entry.previous_proficiency as SkillProficiency
                      ] ?? "bg-gray-100 text-gray-700"
                    }`}
                  >
                    {PROFICIENCY_LABELS[
                      entry.previous_proficiency as SkillProficiency
                    ] ?? entry.previous_proficiency}
                  </span>
                  <span className="text-gray-400">→</span>
                </>
              ) : (
                <span className="text-xs text-gray-400">Created as</span>
              )}
              <span
                className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                  PROFICIENCY_COLORS[
                    entry.new_proficiency as SkillProficiency
                  ] ?? "bg-gray-100 text-gray-700"
                }`}
              >
                {PROFICIENCY_LABELS[
                  entry.new_proficiency as SkillProficiency
                ] ?? entry.new_proficiency}
              </span>
            </div>
            {entry.reason && (
              <p className="mt-1 text-xs text-gray-600">
                {entry.reason}
              </p>
            )}
            <p className="mt-1 text-xs text-gray-400">
              {new Date(entry.created_at).toLocaleString()}
            </p>
          </div>
        ))}
      </div>
    );
  }

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
        className="relative w-full max-w-lg rounded-lg bg-white p-6 shadow-xl"
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">
            {skill.name} — History
          </h2>
          <button
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:text-gray-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="mt-4 max-h-96 overflow-y-auto">
          {historyContent}
        </div>

        <div className="mt-4 flex justify-end">
          <button
            onClick={onClose}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Skills Page
// ---------------------------------------------------------------------------

export function Skills() {
  const profileId = DEFAULT_PROFILE_ID;
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("");
  const [proficiencyFilter, setProficiencyFilter] = useState<string>("");
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [editingSkill, setEditingSkill] = useState<Skill | null>(null);
  const [historySkill, setHistorySkill] = useState<Skill | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: [
      "skills",
      profileId,
      categoryFilter,
      proficiencyFilter,
      searchQuery,
    ],
    queryFn: () =>
      fetchSkills(profileId, {
        category: categoryFilter || undefined,
        proficiency: proficiencyFilter || undefined,
        q: searchQuery || undefined,
      }),
    enabled: true,
  });

  const ingestMutation = useMutation({
    mutationFn: (sources: string[]) =>
      ingestSkills({ profile_id: profileId, sources }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["skills"] });
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
        <p className="text-red-600">Failed to load skills</p>
      </div>
    );
  }

  const isEmpty = data?.total === 0 && data?.ctas;
  const skills = data?.skills ?? [];

  // Empty state with CTAs
  if (isEmpty) {
    return (
      <section className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">Skills Inventory</h1>
        <div className="rounded-lg border-2 border-dashed border-gray-300 bg-white p-12 text-center">
          <Sparkles className="mx-auto h-12 w-12 text-gray-400" />
          <h2 className="mt-4 text-lg font-semibold text-gray-900">
            No skills yet
          </h2>
          <p className="mt-2 text-sm text-gray-500">
            Get started by importing skills from your existing documents.
          </p>
          <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
            <button
              onClick={() => ingestMutation.mutate(["cv"])}
              disabled={ingestMutation.isPending}
              className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              <FileText className="h-4 w-4" />
              Import from CV
            </button>
            <button
              onClick={() => ingestMutation.mutate(["assessments"])}
              disabled={ingestMutation.isPending}
              className="inline-flex items-center gap-2 rounded-md bg-purple-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50"
            >
              <Brain className="h-4 w-4" />
              Parse assessments
            </button>
            <button
              onClick={() => setShowAddDialog(true)}
              className="inline-flex items-center gap-2 rounded-md bg-gray-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-gray-700"
            >
              <PlusCircle className="h-4 w-4" />
              Add manually
            </button>
          </div>
          {ingestMutation.isPending && (
            <p className="mt-4 text-sm text-gray-500">
              <Loader2 className="mr-1 inline h-4 w-4 animate-spin" />
              Parsing documents...
            </p>
          )}
          {ingestMutation.isSuccess && (
            <p className="mt-4 text-sm text-green-600">
              <CheckCircle2 className="mr-1 inline h-4 w-4" />
              Imported {ingestMutation.data.skills_created} skills from{" "}
              {ingestMutation.data.sources_processed.join(", ")}
            </p>
          )}
        </div>
        {showAddDialog && (
          <AddSkillDialog
            onClose={() => setShowAddDialog(false)}
            profileId={profileId}
          />
        )}
      </section>
    );
  }

  // Skills inventory view
  return (
    <section className="space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">
          Skills Inventory ({data?.total ?? 0})
        </h1>
        <div className="flex gap-2">
          <button
            onClick={() => setShowAddDialog(true)}
            className="inline-flex items-center gap-1.5 rounded-md bg-green-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-green-700"
          >
            <PlusCircle className="h-4 w-4" />
            Add Skill
          </button>
          <button
            onClick={() =>
              ingestMutation.mutate(["cv", "assessments", "profile"])
            }
            disabled={ingestMutation.isPending}
            className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {ingestMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            Re-ingest All
          </button>
        </div>
      </header>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative min-w-[200px] flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search skills..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-md border border-gray-300 py-2 pl-9 pr-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="">All Categories</option>
          {Object.entries(CATEGORY_LABELS).map(([val, label]) => (
            <option key={val} value={val}>
              {label}
            </option>
          ))}
        </select>
        <select
          value={proficiencyFilter}
          onChange={(e) => setProficiencyFilter(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="">All Proficiencies</option>
          {Object.entries(PROFICIENCY_LABELS).map(([val, label]) => (
            <option key={val} value={val}>
              {label}
            </option>
          ))}
        </select>
      </div>

      {/* Skills Grid */}
      {skills.length === 0 ? (
        <div className="rounded-lg border border-gray-200 bg-white p-8 text-center">
          <p className="text-sm text-gray-500">
            No skills match your filters.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {skills.map((skill) => (
            <article
              key={skill.id}
              className="group rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition-shadow hover:shadow-md"
            >
              <div className="flex items-start justify-between">
                <h3 className="font-medium text-gray-900">{skill.name}</h3>
                <div className="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                  <button
                    onClick={() => setEditingSkill(skill)}
                    className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                    title="Edit skill"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={() => setHistorySkill(skill)}
                    className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                    title="View history"
                  >
                    <History className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${CATEGORY_COLORS[skill.category] ?? "bg-gray-100 text-gray-700"}`}
                >
                  {CATEGORY_LABELS[skill.category] ?? skill.category}
                </span>
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${PROFICIENCY_COLORS[skill.proficiency] ?? "bg-gray-100 text-gray-700"}`}
                >
                  {PROFICIENCY_LABELS[skill.proficiency] ?? skill.proficiency}
                </span>
              </div>
              {skill.evidence_detail && (
                <p className="mt-2 text-xs text-gray-500 line-clamp-2">
                  {skill.evidence_detail}
                </p>
              )}
              <p className="mt-2 text-xs text-gray-400">
                Source: {skill.evidence_source}
              </p>
            </article>
          ))}
        </div>
      )}

      {/* Dialogs */}
      {showAddDialog && (
        <AddSkillDialog
          onClose={() => setShowAddDialog(false)}
          profileId={profileId}
        />
      )}
      {editingSkill && (
        <EditSkillDialog
          skill={editingSkill}
          onClose={() => setEditingSkill(null)}
          profileId={profileId}
        />
      )}
      {historySkill && (
        <SkillHistoryPanel
          skill={historySkill}
          onClose={() => setHistorySkill(null)}
          profileId={profileId}
        />
      )}
    </section>
  );
}
