/**
 * Tests for STAR Stories components and API integration.
 *
 * Covers:
 * - VAL-STAR-001: STAR story CRUD (create, list, view with all 4 sections)
 * - VAL-STAR-002: Skill-to-company relevance mapping
 * - VAL-STAR-003: Story gap identification with create prompt
 */

import {
  render,
  screen,
  fireEvent,
  waitFor,
} from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StarStoriesSection } from "@/components/StarStoriesSection";
import type {
  StarStoryListResponse,
  RecommendedStoriesResponse,
  StoryGapsResponse,
} from "@/api/types";

// ---- mocks ----

const mockFetchStarStories = vi.fn<() => Promise<StarStoryListResponse>>();
const mockCreateStarStory = vi.fn();
const mockDeleteStarStory = vi.fn();
const mockFetchRecommendedStories =
  vi.fn<() => Promise<RecommendedStoriesResponse>>();
const mockFetchStoryGaps = vi.fn<() => Promise<StoryGapsResponse>>();

vi.mock("@/api/starStories", () => ({
  fetchStarStories: (...args: unknown[]) =>
    mockFetchStarStories(...(args as [])),
  fetchStarStory: vi.fn(),
  createStarStory: (...args: unknown[]) =>
    mockCreateStarStory(...(args as [])),
  updateStarStory: vi.fn(),
  deleteStarStory: (...args: unknown[]) =>
    mockDeleteStarStory(...(args as [])),
  fetchRecommendedStories: (...args: unknown[]) =>
    mockFetchRecommendedStories(...(args as [])),
  fetchStoryGaps: (...args: unknown[]) =>
    mockFetchStoryGaps(...(args as [])),
}));

// ---- helpers ----

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

function renderSection(applicationId = 1, profileId = 1) {
  const qc = createQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <StarStoriesSection
        applicationId={applicationId}
        profileId={profileId}
      />
    </QueryClientProvider>,
  );
}

// ---- fixtures ----

const sampleStory = {
  id: 1,
  profile_id: 1,
  title: "Led Kubernetes Migration",
  situation: "Company needed to migrate 200+ microservices.",
  task: "Planned and executed migration across 5 teams.",
  action: "Created phased plan with rollback procedures.",
  result: "Completed 2 weeks ahead with zero downtime.",
  skill_tags: ["Kubernetes", "Program Management"],
  created_at: "2026-03-14T00:00:00Z",
  updated_at: "2026-03-14T00:00:00Z",
};

const emptyStories: StarStoryListResponse = { stories: [], total: 0 };

const storiesWithData: StarStoryListResponse = {
  stories: [sampleStory],
  total: 1,
};

const recommendedResponse: RecommendedStoriesResponse = {
  application_id: 1,
  company: "Stripe",
  role: "Senior TPM",
  recommended_stories: [
    {
      story: sampleStory,
      matching_skills: ["Kubernetes", "Program Management"],
      match_count: 2,
    },
  ],
  total_requirements: 4,
  covered_skills: ["Kubernetes", "Program Management"],
};

const emptyRecommended: RecommendedStoriesResponse = {
  application_id: 1,
  company: "Stripe",
  role: "Senior TPM",
  recommended_stories: [],
  total_requirements: 0,
  covered_skills: [],
};

const gapsResponse: StoryGapsResponse = {
  application_id: 1,
  company: "Stripe",
  role: "Senior TPM",
  story_gaps: [
    {
      skill_name: "Python",
      severity: "nice-to-have",
      required_level: "intermediate",
      has_story: false,
      create_prompt:
        "Create a STAR story demonstrating your Python skills.",
    },
    {
      skill_name: "Docker",
      severity: "critical",
      required_level: "advanced",
      has_story: false,
      create_prompt:
        "Create a STAR story demonstrating your Docker skills.",
    },
  ],
  total_requirements: 4,
  covered_count: 2,
  gap_count: 2,
};

const noGaps: StoryGapsResponse = {
  application_id: 1,
  company: "Stripe",
  role: "Senior TPM",
  story_gaps: [],
  total_requirements: 4,
  covered_count: 4,
  gap_count: 0,
};

// ---- tests ----

describe("StarStoriesSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("VAL-STAR-001: CRUD rendering", () => {
    it("renders STAR Stories header", async () => {
      mockFetchStarStories.mockResolvedValue(emptyStories);
      mockFetchRecommendedStories.mockResolvedValue(emptyRecommended);
      mockFetchStoryGaps.mockResolvedValue(noGaps);

      renderSection();

      await waitFor(() => {
        expect(screen.getByText("STAR Stories")).toBeInTheDocument();
      });
    });

    it("shows empty state when no stories exist", async () => {
      mockFetchStarStories.mockResolvedValue(emptyStories);
      mockFetchRecommendedStories.mockResolvedValue(emptyRecommended);
      mockFetchStoryGaps.mockResolvedValue(noGaps);

      renderSection();

      // Expand "All Stories" section
      await waitFor(() => {
        expect(screen.getByText("All Stories")).toBeInTheDocument();
      });
      fireEvent.click(screen.getByText("All Stories"));

      await waitFor(() => {
        expect(
          screen.getByText(/No STAR stories yet/),
        ).toBeInTheDocument();
      });
    });

    it("shows New Story button", async () => {
      mockFetchStarStories.mockResolvedValue(emptyStories);
      mockFetchRecommendedStories.mockResolvedValue(emptyRecommended);
      mockFetchStoryGaps.mockResolvedValue(noGaps);

      renderSection();

      await waitFor(() => {
        expect(screen.getByText("New Story")).toBeInTheDocument();
      });
    });

    it("opens create form when New Story clicked", async () => {
      mockFetchStarStories.mockResolvedValue(emptyStories);
      mockFetchRecommendedStories.mockResolvedValue(emptyRecommended);
      mockFetchStoryGaps.mockResolvedValue(noGaps);

      renderSection();

      await waitFor(() => {
        expect(screen.getByText("New Story")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("New Story"));

      await waitFor(() => {
        expect(
          screen.getByText("New STAR Story"),
        ).toBeInTheDocument();
        expect(
          screen.getByPlaceholderText("Story title"),
        ).toBeInTheDocument();
        expect(
          screen.getByPlaceholderText("Describe the situation..."),
        ).toBeInTheDocument();
        expect(
          screen.getByPlaceholderText("Describe the task..."),
        ).toBeInTheDocument();
        expect(
          screen.getByPlaceholderText("Describe the action..."),
        ).toBeInTheDocument();
        expect(
          screen.getByPlaceholderText("Describe the result..."),
        ).toBeInTheDocument();
      });
    });

    it("shows stories in All Stories section", async () => {
      mockFetchStarStories.mockResolvedValue(storiesWithData);
      mockFetchRecommendedStories.mockResolvedValue(emptyRecommended);
      mockFetchStoryGaps.mockResolvedValue(noGaps);

      renderSection();

      // Expand "All Stories"
      await waitFor(() => {
        expect(screen.getByText("All Stories")).toBeInTheDocument();
      });
      fireEvent.click(screen.getByText("All Stories"));

      await waitFor(() => {
        expect(
          screen.getByText("Led Kubernetes Migration"),
        ).toBeInTheDocument();
      });
    });
  });

  describe("VAL-STAR-002: Recommended stories", () => {
    it("shows recommended stories with matching skills", async () => {
      mockFetchStarStories.mockResolvedValue(storiesWithData);
      mockFetchRecommendedStories.mockResolvedValue(recommendedResponse);
      mockFetchStoryGaps.mockResolvedValue(noGaps);

      renderSection();

      await waitFor(() => {
        expect(
          screen.getByText("Recommended Stories"),
        ).toBeInTheDocument();
        expect(screen.getByText("(1 matching)")).toBeInTheDocument();
      });
    });

    it("shows empty message when no recommendations", async () => {
      mockFetchStarStories.mockResolvedValue(emptyStories);
      mockFetchRecommendedStories.mockResolvedValue(emptyRecommended);
      mockFetchStoryGaps.mockResolvedValue(noGaps);

      renderSection();

      await waitFor(() => {
        expect(
          screen.getByText(/No matching stories found/),
        ).toBeInTheDocument();
      });
    });
  });

  describe("VAL-STAR-003: Story gaps", () => {
    it("shows story gaps with skill names", async () => {
      mockFetchStarStories.mockResolvedValue(emptyStories);
      mockFetchRecommendedStories.mockResolvedValue(emptyRecommended);
      mockFetchStoryGaps.mockResolvedValue(gapsResponse);

      renderSection();

      await waitFor(() => {
        expect(screen.getByText("Story Gaps")).toBeInTheDocument();
        expect(
          screen.getByText("(2 skills without stories)"),
        ).toBeInTheDocument();
      });

      await waitFor(() => {
        expect(screen.getByText("Python")).toBeInTheDocument();
        expect(screen.getByText("Docker")).toBeInTheDocument();
      });
    });

    it("shows severity badges for gaps", async () => {
      mockFetchStarStories.mockResolvedValue(emptyStories);
      mockFetchRecommendedStories.mockResolvedValue(emptyRecommended);
      mockFetchStoryGaps.mockResolvedValue(gapsResponse);

      renderSection();

      await waitFor(() => {
        expect(screen.getByText("critical")).toBeInTheDocument();
        expect(screen.getByText("nice-to-have")).toBeInTheDocument();
      });
    });

    it("shows create prompt for gaps", async () => {
      mockFetchStarStories.mockResolvedValue(emptyStories);
      mockFetchRecommendedStories.mockResolvedValue(emptyRecommended);
      mockFetchStoryGaps.mockResolvedValue(gapsResponse);

      renderSection();

      await waitFor(() => {
        expect(
          screen.getByText(/demonstrating your Python skills/),
        ).toBeInTheDocument();
      });
    });

    it("shows all covered message when no gaps", async () => {
      mockFetchStarStories.mockResolvedValue(storiesWithData);
      mockFetchRecommendedStories.mockResolvedValue(recommendedResponse);
      mockFetchStoryGaps.mockResolvedValue(noGaps);

      renderSection();

      await waitFor(() => {
        expect(
          screen.getByText(/All required skills are covered/),
        ).toBeInTheDocument();
      });
    });

    it("shows Create Story buttons for each gap", async () => {
      mockFetchStarStories.mockResolvedValue(emptyStories);
      mockFetchRecommendedStories.mockResolvedValue(emptyRecommended);
      mockFetchStoryGaps.mockResolvedValue(gapsResponse);

      renderSection();

      await waitFor(() => {
        const createButtons = screen.getAllByText("Create Story");
        expect(createButtons.length).toBeGreaterThanOrEqual(2);
      });
    });
  });
});
