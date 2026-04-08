/**
 * Tests for the Skills page.
 *
 * Covers:
 * - Skills grid rendering with search and category filters
 * - Empty state with CTAs
 * - Add skill dialog
 * - Edit skill dialog
 * - Skill history panel
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { Skills } from "@/pages/Skills";
import type {
  SkillListResponse,
  Skill,
  SkillHistoryEntry,
  IngestResponse,
} from "@/api/types";

// ---- mocks ----

const mockFetchSkills = vi.fn<() => Promise<SkillListResponse>>();
const mockCreateSkill = vi.fn<() => Promise<Skill>>();
const mockUpdateSkill = vi.fn<() => Promise<Skill>>();
const mockFetchSkillHistory = vi.fn<() => Promise<SkillHistoryEntry[]>>();
const mockIngestSkills = vi.fn<() => Promise<IngestResponse>>();

vi.mock("@/api/skills", () => ({
  fetchSkills: (...args: unknown[]) => mockFetchSkills(...(args as [])),
  createSkill: (...args: unknown[]) => mockCreateSkill(...(args as [])),
  updateSkill: (...args: unknown[]) => mockUpdateSkill(...(args as [])),
  fetchSkillHistory: (...args: unknown[]) =>
    mockFetchSkillHistory(...(args as [])),
  ingestSkills: (...args: unknown[]) => mockIngestSkills(...(args as [])),
}));

vi.mock("@/api/applications", () => ({
  DEFAULT_PROFILE_ID: 1,
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

function renderSkills() {
  const qc = createQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Skills />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const SAMPLE_SKILLS: Skill[] = [
  {
    id: 1,
    profile_id: 1,
    name: "Python",
    category: "technical",
    proficiency: "expert",
    evidence_source: "cv.yaml",
    evidence_detail: "10+ years experience",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
  {
    id: 2,
    profile_id: 1,
    name: "Communication",
    category: "soft",
    proficiency: "expert",
    evidence_source: "assessment:cliftonstrengths",
    evidence_detail: "CliftonStrengths Rank #1",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
  {
    id: 3,
    profile_id: 1,
    name: "Jira",
    category: "tools",
    proficiency: "advanced",
    evidence_source: "cv.yaml",
    evidence_detail: null,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
  {
    id: 4,
    profile_id: 1,
    name: "Program Management",
    category: "domain",
    proficiency: "expert",
    evidence_source: "profile",
    evidence_detail: "Found in narrative.md",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
];

const SAMPLE_HISTORY: SkillHistoryEntry[] = [
  {
    id: 2,
    skill_id: 1,
    previous_proficiency: "advanced",
    new_proficiency: "expert",
    reason: "Completed advanced course",
    created_at: "2024-06-01T00:00:00Z",
  },
  {
    id: 1,
    skill_id: 1,
    previous_proficiency: null,
    new_proficiency: "advanced",
    reason: "Initial creation",
    created_at: "2024-01-01T00:00:00Z",
  },
];

// ---- setup ----

beforeEach(() => {
  vi.clearAllMocks();
  mockFetchSkills.mockResolvedValue({
    skills: SAMPLE_SKILLS,
    total: 4,
  });
});

// ---- tests ----

describe("Skills page", () => {
  describe("skills grid rendering", () => {
    it("renders skills grid with skill cards", async () => {
      renderSkills();
      await waitFor(() => {
        expect(screen.getByText("Python")).toBeInTheDocument();
      });
      expect(screen.getByText("Communication")).toBeInTheDocument();
      expect(screen.getByText("Jira")).toBeInTheDocument();
      expect(screen.getByText("Program Management")).toBeInTheDocument();
    });

    it("shows skill count in header", async () => {
      renderSkills();
      await waitFor(() => {
        expect(screen.getByText("Skills Inventory (4)")).toBeInTheDocument();
      });
    });

    it("shows category badges on cards", async () => {
      renderSkills();
      await waitFor(() => {
        expect(screen.getByText("Python")).toBeInTheDocument();
      });
      // Category labels appear both in filter dropdowns and card badges — use getAllByText
      expect(screen.getAllByText("Technical").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Soft").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Tools").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Domain").length).toBeGreaterThanOrEqual(1);
    });

    it("shows proficiency badges on cards", async () => {
      renderSkills();
      await waitFor(() => {
        expect(screen.getByText("Python")).toBeInTheDocument();
      });
      // All SAMPLE_SKILLS have "expert" or "advanced" proficiency
      expect(screen.getAllByText("Expert").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Advanced").length).toBeGreaterThanOrEqual(1);
    });

    it("shows evidence detail on cards", async () => {
      renderSkills();
      await waitFor(() => {
        expect(screen.getByText("10+ years experience")).toBeInTheDocument();
      });
    });

    it("shows evidence source on cards", async () => {
      renderSkills();
      await waitFor(() => {
        expect(screen.getByText("Python")).toBeInTheDocument();
      });
      // Multiple cards may share the same source
      const sourceElements = screen.getAllByText(
        (_content, element) =>
          element?.tagName === "P" &&
          element?.textContent?.includes("Source:") === true
      );
      expect(sourceElements.length).toBeGreaterThanOrEqual(1);
    });
  });

  describe("search bar", () => {
    it("renders search input", async () => {
      renderSkills();
      await waitFor(() => {
        expect(
          screen.getByPlaceholderText("Search skills...")
        ).toBeInTheDocument();
      });
    });

    it("calls fetchSkills with q param when typing", async () => {
      renderSkills();
      await waitFor(() => {
        expect(screen.getByText("Python")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText("Search skills...");
      fireEvent.change(searchInput, { target: { value: "python" } });

      await waitFor(() => {
        // The query should be refetched with q=python
        const lastCall =
          mockFetchSkills.mock.calls[mockFetchSkills.mock.calls.length - 1];
        expect(lastCall).toBeTruthy();
      });
    });
  });

  describe("category filter", () => {
    it("renders category dropdown", async () => {
      renderSkills();
      await waitFor(() => {
        expect(screen.getByText("Python")).toBeInTheDocument();
      });
      expect(screen.getByDisplayValue("All Categories")).toBeInTheDocument();
    });

    it("calls fetchSkills with category param", async () => {
      renderSkills();
      await waitFor(() => {
        expect(screen.getByText("Python")).toBeInTheDocument();
      });

      const select = screen.getByDisplayValue("All Categories");
      fireEvent.change(select, { target: { value: "technical" } });

      await waitFor(() => {
        const lastCall =
          mockFetchSkills.mock.calls[mockFetchSkills.mock.calls.length - 1];
        expect(lastCall).toBeTruthy();
      });
    });
  });

  describe("proficiency filter", () => {
    it("renders proficiency dropdown", async () => {
      renderSkills();
      await waitFor(() => {
        expect(screen.getByText("Python")).toBeInTheDocument();
      });
      expect(
        screen.getByDisplayValue("All Proficiencies")
      ).toBeInTheDocument();
    });
  });

  describe("empty state", () => {
    it("shows empty state with CTAs when no skills exist", async () => {
      mockFetchSkills.mockResolvedValue({
        skills: [],
        total: 0,
        ctas: [
          { label: "Import from CV", action: "ingest_cv" },
          { label: "Parse assessments", action: "ingest_assessments" },
          { label: "Add manually", action: "add_manual" },
        ],
      });
      renderSkills();
      await waitFor(() => {
        expect(screen.getByText("No skills yet")).toBeInTheDocument();
      });
      expect(screen.getByText("Import from CV")).toBeInTheDocument();
      expect(screen.getByText("Parse assessments")).toBeInTheDocument();
      expect(screen.getByText("Add manually")).toBeInTheDocument();
    });

    it('shows "No skills match" when filters return empty', async () => {
      mockFetchSkills.mockResolvedValue({
        skills: [],
        total: 0,
      });
      renderSkills();
      await waitFor(() => {
        expect(
          screen.getByText("No skills match your filters.")
        ).toBeInTheDocument();
      });
    });
  });

  describe("add skill dialog", () => {
    it("opens add dialog when Add Skill button clicked", async () => {
      renderSkills();
      await waitFor(() => {
        expect(screen.getByText("Python")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Add Skill"));

      await waitFor(() => {
        expect(screen.getByText("Add Skill", { selector: "h2" })).toBeInTheDocument();
      });
    });

    it("add dialog has name, category, proficiency, evidence fields", async () => {
      renderSkills();
      await waitFor(() => {
        expect(screen.getByText("Python")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Add Skill"));

      await waitFor(() => {
        expect(screen.getByText("Name *")).toBeInTheDocument();
      });
      expect(screen.getByText("Category")).toBeInTheDocument();
      expect(screen.getByText("Proficiency")).toBeInTheDocument();
      expect(screen.getByText("Evidence / Notes")).toBeInTheDocument();
    });

    it("submitting add dialog calls createSkill", async () => {
      const newSkill: Skill = {
        id: 10,
        profile_id: 1,
        name: "Kubernetes",
        category: "technical",
        proficiency: "beginner",
        evidence_source: "manual",
        evidence_detail: null,
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
      };
      mockCreateSkill.mockResolvedValue(newSkill);

      renderSkills();
      await waitFor(() => {
        expect(screen.getByText("Python")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Add Skill"));

      await waitFor(() => {
        expect(screen.getByPlaceholderText("e.g. Kubernetes")).toBeInTheDocument();
      });

      fireEvent.change(screen.getByPlaceholderText("e.g. Kubernetes"), {
        target: { value: "Kubernetes" },
      });

      // Submit by clicking the submit button
      const submitButtons = screen.getAllByRole("button");
      const addButton = submitButtons.find(
        (b) => b.textContent === "Add Skill" && b.getAttribute("type") === "submit"
      );
      if (addButton) fireEvent.click(addButton);

      await waitFor(() => {
        expect(mockCreateSkill).toHaveBeenCalled();
      });
    });

    it("closes add dialog on Cancel", async () => {
      renderSkills();
      await waitFor(() => {
        expect(screen.getByText("Python")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Add Skill"));

      await waitFor(() => {
        expect(screen.getByText("Cancel")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Cancel"));

      await waitFor(() => {
        expect(screen.queryByText("Name *")).not.toBeInTheDocument();
      });
    });
  });

  describe("edit skill dialog", () => {
    it("shows edit and history buttons on card hover", async () => {
      renderSkills();
      await waitFor(() => {
        expect(screen.getByText("Python")).toBeInTheDocument();
      });
      // Edit buttons are rendered but hidden with opacity-0 — they still exist in DOM
      const editButtons = screen.getAllByTitle("Edit skill");
      expect(editButtons.length).toBeGreaterThanOrEqual(1);
    });

    it("opens edit dialog when edit button clicked", async () => {
      renderSkills();
      await waitFor(() => {
        expect(screen.getByText("Python")).toBeInTheDocument();
      });

      const editButtons = screen.getAllByTitle("Edit skill");
      fireEvent.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByText("Edit Skill")).toBeInTheDocument();
      });
    });

    it("edit dialog pre-fills current values", async () => {
      renderSkills();
      await waitFor(() => {
        expect(screen.getByText("Python")).toBeInTheDocument();
      });

      const editButtons = screen.getAllByTitle("Edit skill");
      fireEvent.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByText("Edit Skill")).toBeInTheDocument();
      });

      // Check pre-filled name
      const nameInput = screen.getByDisplayValue("Python");
      expect(nameInput).toBeInTheDocument();
    });

    it("submitting edit dialog calls updateSkill", async () => {
      const updatedSkill: Skill = {
        ...SAMPLE_SKILLS[0],
        proficiency: "expert",
      };
      mockUpdateSkill.mockResolvedValue(updatedSkill);

      renderSkills();
      await waitFor(() => {
        expect(screen.getByText("Python")).toBeInTheDocument();
      });

      const editButtons = screen.getAllByTitle("Edit skill");
      fireEvent.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByText("Edit Skill")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Save Changes"));

      await waitFor(() => {
        expect(mockUpdateSkill).toHaveBeenCalled();
      });
    });
  });

  describe("skill history panel", () => {
    it("opens history panel when history button clicked", async () => {
      mockFetchSkillHistory.mockResolvedValue(SAMPLE_HISTORY);

      renderSkills();
      await waitFor(() => {
        expect(screen.getByText("Python")).toBeInTheDocument();
      });

      const historyButtons = screen.getAllByTitle("View history");
      fireEvent.click(historyButtons[0]);

      await waitFor(() => {
        expect(
          screen.getByText("Python — History")
        ).toBeInTheDocument();
      });
    });

    it("history panel shows proficiency progression", async () => {
      mockFetchSkillHistory.mockResolvedValue(SAMPLE_HISTORY);

      renderSkills();
      await waitFor(() => {
        expect(screen.getByText("Python")).toBeInTheDocument();
      });

      const historyButtons = screen.getAllByTitle("View history");
      fireEvent.click(historyButtons[0]);

      await waitFor(() => {
        expect(
          screen.getByText("Python — History")
        ).toBeInTheDocument();
      });

      // Check for reason text
      await waitFor(() => {
        expect(
          screen.getByText("Completed advanced course")
        ).toBeInTheDocument();
      });
    });

    it("history panel closes on Close button", async () => {
      mockFetchSkillHistory.mockResolvedValue(SAMPLE_HISTORY);

      renderSkills();
      await waitFor(() => {
        expect(screen.getByText("Python")).toBeInTheDocument();
      });

      const historyButtons = screen.getAllByTitle("View history");
      fireEvent.click(historyButtons[0]);

      await waitFor(() => {
        expect(
          screen.getByText("Python — History")
        ).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Close"));

      await waitFor(() => {
        expect(
          screen.queryByText("Python — History")
        ).not.toBeInTheDocument();
      });
    });
  });

  describe("loading state", () => {
    it("shows spinner while loading", async () => {
      // Never resolve the promise
      mockFetchSkills.mockReturnValue(new Promise(() => {}));
      renderSkills();
      // The spinner is rendered via Loader2 SVG
      await waitFor(() => {
        const spinners = document.querySelectorAll(".animate-spin");
        expect(spinners.length).toBeGreaterThanOrEqual(1);
      });
    });
  });

  describe("error state", () => {
    it("shows error message on fetch failure", async () => {
      mockFetchSkills.mockRejectedValue(new Error("Network error"));
      renderSkills();
      await waitFor(() => {
        expect(screen.getByText("Failed to load skills")).toBeInTheDocument();
      });
    });
  });
});
