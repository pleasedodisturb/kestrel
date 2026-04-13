/**
 * StarStoriesSection — STAR story management panel for ApplicationDetail.
 *
 * Shows recommended stories, story gaps, and allows creating new stories.
 * Integrates with the STAR stories API for CRUD and matching.
 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type {
  StarStory,
  StarStoryCreate,
} from "@/api/types";
import {
  fetchStarStories,
  createStarStory,
  deleteStarStory,
  fetchRecommendedStories,
  fetchStoryGaps,
} from "@/api/starStories";
import {
  BookOpen,
  Plus,
  Trash2,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Tag,
  Star,
} from "lucide-react";
import { cn } from "@/lib/utils";

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-100 text-red-700",
  "nice-to-have": "bg-yellow-100 text-yellow-700",
};
const DEFAULT_SEVERITY_COLOR = "bg-gray-100 text-gray-600";

interface StarStoriesSectionProps {
  readonly applicationId: number;
  readonly profileId: number;
}

// ---------------------------------------------------------------------------
// Create Story Form
// ---------------------------------------------------------------------------

function CreateStoryForm({
  profileId,
  onClose,
}: Readonly<{
  profileId: number;
  onClose: () => void;
}>) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<StarStoryCreate>({
    title: "",
    situation: "",
    task: "",
    action: "",
    result: "",
    skill_tags: [],
  });
  const [tagInput, setTagInput] = useState("");

  const createMutation = useMutation({
    mutationFn: (data: StarStoryCreate) => createStarStory(profileId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["star-stories"] });
      queryClient.invalidateQueries({ queryKey: ["recommended-stories"] });
      queryClient.invalidateQueries({ queryKey: ["story-gaps"] });
      onClose();
    },
  });

  const addTag = () => {
    const tag = tagInput.trim();
    if (tag && !form.skill_tags.includes(tag)) {
      setForm({ ...form, skill_tags: [...form.skill_tags, tag] });
      setTagInput("");
    }
  };

  const removeTag = (tag: string) => {
    setForm({
      ...form,
      skill_tags: form.skill_tags.filter((t) => t !== tag),
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate(form);
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="border rounded-lg p-4 bg-white space-y-3"
    >
      <h4 className="font-semibold text-sm text-gray-700">
        New STAR Story
      </h4>

      <input
        type="text"
        placeholder="Story title"
        value={form.title}
        onChange={(e) => setForm({ ...form, title: e.target.value })}
        className="w-full border rounded px-3 py-2 text-sm"
        required
      />

      {(["situation", "task", "action", "result"] as const).map((field) => (
        <div key={field}>
          <label htmlFor={`star-story-${field}`} className="block text-xs font-medium text-gray-500 uppercase mb-1">
            {field}
          </label>
          <textarea
            id={`star-story-${field}`}
            placeholder={`Describe the ${field}...`}
            value={form[field]}
            onChange={(e) => setForm({ ...form, [field]: e.target.value })}
            className="w-full border rounded px-3 py-2 text-sm"
            rows={2}
            required
          />
        </div>
      ))}

      <div>
        <label htmlFor="star-story-skill-tags" className="block text-xs font-medium text-gray-500 uppercase mb-1">
          Skill Tags
        </label>
        <div className="flex gap-2">
          <input
            id="star-story-skill-tags"
            type="text"
            placeholder="Add skill tag..."
            value={tagInput}
            onChange={(e) => setTagInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addTag();
              }
            }}
            className="flex-1 border rounded px-3 py-2 text-sm"
          />
          <button
            type="button"
            onClick={addTag}
            className="px-3 py-2 bg-gray-100 border rounded text-sm hover:bg-gray-200"
          >
            Add
          </button>
        </div>
        {form.skill_tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {form.skill_tags.map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 text-blue-700 text-xs rounded-full"
              >
                {tag}
                <button
                  type="button"
                  onClick={() => removeTag(tag)}
                  className="text-blue-400 hover:text-blue-600"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="flex gap-2 pt-2">
        <button
          type="submit"
          disabled={createMutation.isPending}
          className="px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {createMutation.isPending ? "Creating..." : "Create Story"}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="px-4 py-2 bg-gray-100 text-gray-700 text-sm rounded hover:bg-gray-200"
        >
          Cancel
        </button>
      </div>

      {createMutation.isError && (
        <p className="text-red-600 text-xs">
          Failed to create story. Please try again.
        </p>
      )}
    </form>
  );
}

// ---------------------------------------------------------------------------
// Story Card
// ---------------------------------------------------------------------------

function StoryCard({
  story,
  profileId,
  matchingSkills,
}: Readonly<{
  story: StarStory;
  profileId: number;
  matchingSkills?: string[];
}>) {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);

  const deleteMutation = useMutation({
    mutationFn: () => deleteStarStory(story.id, profileId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["star-stories"] });
      queryClient.invalidateQueries({ queryKey: ["recommended-stories"] });
      queryClient.invalidateQueries({ queryKey: ["story-gaps"] });
    },
  });

  return (
    <div className="border rounded-lg p-3 bg-white hover:shadow-sm transition-shadow">
      <div className="flex items-start justify-between">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-2 text-left flex-1"
        >
          {expanded ? (
            <ChevronDown className="w-4 h-4 text-gray-400 flex-shrink-0" />
          ) : (
            <ChevronRight className="w-4 h-4 text-gray-400 flex-shrink-0" />
          )}
          <div>
            <h5 className="font-medium text-sm text-gray-900">
              {story.title}
            </h5>
            {story.skill_tags.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-1">
                {story.skill_tags.map((tag) => (
                  <span
                    key={tag}
                    className={cn(
                      "px-1.5 py-0.5 text-xs rounded-full",
                      matchingSkills?.some(
                        (ms) => ms.toLowerCase() === tag.toLowerCase(),
                      )
                        ? "bg-green-50 text-green-700 border border-green-200"
                        : "bg-gray-100 text-gray-600",
                    )}
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        </button>
        <button
          onClick={() => deleteMutation.mutate()}
          disabled={deleteMutation.isPending}
          className="p-1 text-gray-400 hover:text-red-500 flex-shrink-0"
          title="Delete story"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>

      {expanded && (
        <div className="mt-3 space-y-2 pl-6">
          {(
            [
              ["Situation", story.situation],
              ["Task", story.task],
              ["Action", story.action],
              ["Result", story.result],
            ] as const
          ).map(([label, text]) => (
            <div key={label}>
              <span className="text-xs font-semibold text-gray-500 uppercase">
                {label}
              </span>
              <p className="text-sm text-gray-700 mt-0.5">{text}</p>
            </div>
          ))}
        </div>
      )}

      {(matchingSkills?.length ?? 0) > 0 && !expanded && (
        <p className="text-xs text-green-600 mt-1 pl-6">
          Matches: {matchingSkills.join(", ")}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function StarStoriesSection({
  applicationId,
  profileId,
}: StarStoriesSectionProps) {
  const [showCreate, setShowCreate] = useState(false);
  const [expandedSections, setExpandedSections] = useState<
    Record<string, boolean>
  >({
    recommended: true,
    gaps: true,
    all: false,
  });

  const toggleSection = (key: string) =>
    setExpandedSections((prev) => ({ ...prev, [key]: !prev[key] }));

  // Queries
  const {
    data: recommended,
    isLoading: recLoading,
    isError: recError,
  } = useQuery({
    queryKey: ["recommended-stories", applicationId, profileId],
    queryFn: () => fetchRecommendedStories(applicationId, profileId),
  });

  const {
    data: gaps,
    isLoading: gapsLoading,
    isError: gapsError,
  } = useQuery({
    queryKey: ["story-gaps", applicationId, profileId],
    queryFn: () => fetchStoryGaps(applicationId, profileId),
  });

  const {
    data: allStories,
    isLoading: storiesLoading,
    isError: storiesError,
  } = useQuery({
    queryKey: ["star-stories", profileId],
    queryFn: () => fetchStarStories(profileId),
  });

  const isLoading = recLoading || gapsLoading || storiesLoading;

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-3">
        <div className="h-4 bg-gray-200 rounded w-1/3" />
        <div className="h-20 bg-gray-200 rounded" />
      </div>
    );
  }

  let recommendedContent: React.ReactNode;
  if (recError) {
    recommendedContent = (
      <p className="text-sm text-red-500">
        Failed to load recommendations.
      </p>
    );
  } else if (recommended?.recommended_stories.length === 0) {
    recommendedContent = (
      <p className="text-sm text-gray-500 italic">
        No matching stories found. Create stories with skill tags
        matching this role&apos;s requirements.
      </p>
    );
  } else {
    recommendedContent = recommended?.recommended_stories.map((rec) => (
      <StoryCard
        key={rec.story.id}
        story={rec.story}
        profileId={profileId}
        matchingSkills={rec.matching_skills}
      />
    ));
  }

  let gapsContent: React.ReactNode;
  if (gapsError) {
    gapsContent = (
      <p className="text-sm text-red-500">
        Failed to load story gaps.
      </p>
    );
  } else if (gaps?.story_gaps.length === 0) {
    gapsContent = (
      <p className="text-sm text-green-600 italic">
        All required skills are covered by STAR stories!
      </p>
    );
  } else {
    gapsContent = gaps?.story_gaps.map((gap) => (
      <div
        key={gap.skill_name}
        className="flex items-center justify-between p-3 border rounded-lg bg-amber-50/50"
      >
        <div>
          <div className="flex items-center gap-2">
            <Tag className="w-3.5 h-3.5 text-amber-500" />
            <span className="text-sm font-medium text-gray-900">
              {gap.skill_name}
            </span>
            <span
              className={cn(
                "text-xs px-1.5 py-0.5 rounded-full",
                SEVERITY_COLORS[gap.severity] ?? DEFAULT_SEVERITY_COLOR,
              )}
            >
              {gap.severity}
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-0.5">
            {gap.create_prompt}
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="px-2 py-1 text-xs bg-amber-100 text-amber-700 rounded hover:bg-amber-200 flex-shrink-0"
        >
          Create Story
        </button>
      </div>
    ));
  }

  let allStoriesContent: React.ReactNode;
  if (storiesError) {
    allStoriesContent = (
      <p className="text-sm text-red-500">
        Failed to load stories.
      </p>
    );
  } else if (allStories?.stories.length === 0) {
    allStoriesContent = (
      <p className="text-sm text-gray-500 italic">
        No STAR stories yet. Create one to prepare for interviews!
      </p>
    );
  } else {
    allStoriesContent = allStories?.stories.map((story) => (
      <StoryCard
        key={story.id}
        story={story}
        profileId={profileId}
      />
    ));
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <Star className="w-5 h-5 text-amber-500" />
          STAR Stories
        </h3>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="inline-flex items-center gap-1 px-3 py-1.5 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700"
        >
          <Plus className="w-4 h-4" />
          New Story
        </button>
      </div>

      {showCreate && (
        <CreateStoryForm
          profileId={profileId}
          onClose={() => setShowCreate(false)}
        />
      )}

      {/* Recommended Stories */}
      <div className="border rounded-lg overflow-hidden">
        <button
          onClick={() => toggleSection("recommended")}
          className="w-full flex items-center justify-between px-4 py-3 bg-green-50 hover:bg-green-100 transition-colors"
        >
          <span className="flex items-center gap-2 text-sm font-medium text-green-800">
            <CheckCircle2 className="w-4 h-4" />
            Recommended Stories
            {recommended && (
              <span className="text-xs text-green-600">
                ({recommended.recommended_stories.length} matching)
              </span>
            )}
          </span>
          {expandedSections.recommended ? (
            <ChevronDown className="w-4 h-4 text-green-600" />
          ) : (
            <ChevronRight className="w-4 h-4 text-green-600" />
          )}
        </button>

        {expandedSections.recommended && (
          <div className="p-4 space-y-2">
            {recommendedContent}
          </div>
        )}
      </div>

      {/* Story Gaps */}
      <div className="border rounded-lg overflow-hidden">
        <button
          onClick={() => toggleSection("gaps")}
          className="w-full flex items-center justify-between px-4 py-3 bg-amber-50 hover:bg-amber-100 transition-colors"
        >
          <span className="flex items-center gap-2 text-sm font-medium text-amber-800">
            <AlertTriangle className="w-4 h-4" />
            Story Gaps
            {gaps && (
              <span className="text-xs text-amber-600">
                ({gaps.gap_count} skills without stories)
              </span>
            )}
          </span>
          {expandedSections.gaps ? (
            <ChevronDown className="w-4 h-4 text-amber-600" />
          ) : (
            <ChevronRight className="w-4 h-4 text-amber-600" />
          )}
        </button>

        {expandedSections.gaps && (
          <div className="p-4 space-y-2">
            {gapsContent}
          </div>
        )}
      </div>

      {/* All Stories */}
      <div className="border rounded-lg overflow-hidden">
        <button
          onClick={() => toggleSection("all")}
          className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors"
        >
          <span className="flex items-center gap-2 text-sm font-medium text-gray-700">
            <BookOpen className="w-4 h-4" />
            All Stories
            {allStories && (
              <span className="text-xs text-gray-500">
                ({allStories.total} total)
              </span>
            )}
          </span>
          {expandedSections.all ? (
            <ChevronDown className="w-4 h-4 text-gray-500" />
          ) : (
            <ChevronRight className="w-4 h-4 text-gray-500" />
          )}
        </button>

        {expandedSections.all && (
          <div className="p-4 space-y-2">
            {allStoriesContent}
          </div>
        )}
      </div>
    </div>
  );
}
