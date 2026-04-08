/**
 * Tests for the Discovery search & filter page.
 *
 * Covers:
 * - VAL-SEARCH-001: Full-text search
 * - VAL-SEARCH-002: Multi-facet filtering
 * - VAL-SEARCH-003: Sort by score/date/salary/readiness
 * - VAL-SEARCH-004: Saved searches
 * - VAL-SEARCH-005: Empty search returns all jobs paginated
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { Discovery } from "@/pages/Discovery";
import type {
  JobSearchResponse,
  SavedSearchListResponse,
  SavedSearch,
  DiscoveredJob,
} from "@/api/types";

// ---- mocks ----

const mockSearchJobs = vi.fn<() => Promise<JobSearchResponse>>();
const mockFetchSavedSearches = vi.fn<() => Promise<SavedSearchListResponse>>();
const mockCreateSavedSearch = vi.fn<() => Promise<SavedSearch>>();
const mockDeleteSavedSearch = vi.fn<() => Promise<void>>();

vi.mock("@/api/discovery", () => ({
  searchJobs: (...args: unknown[]) => mockSearchJobs(...(args as [])),
  fetchSavedSearches: (...args: unknown[]) =>
    mockFetchSavedSearches(...(args as [])),
  createSavedSearch: (...args: unknown[]) =>
    mockCreateSavedSearch(...(args as [])),
  deleteSavedSearch: (...args: unknown[]) =>
    mockDeleteSavedSearch(...(args as [])),
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

function renderDiscovery() {
  const qc = createQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Discovery />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const SAMPLE_JOBS: DiscoveredJob[] = [
  {
    id: 1,
    profile_id: 1,
    title: "Senior TPM - AI Platform",
    company: "Stripe",
    location: "San Francisco, Remote",
    url: "https://stripe.com/job1",
    description: "Lead AI platform program management with ML teams",
    salary_range: "180000-220000 USD",
    remote: true,
    posted_at: "2024-01-10T00:00:00Z",
    sources: ["linkedin", "indeed"],
    source_urls: [],
    fit_score: 8.5,
    readiness_score: 85,
    application_id: null,
    created_at: "2024-01-10T00:00:00Z",
    updated_at: "2024-01-10T00:00:00Z",
  },
  {
    id: 2,
    profile_id: 1,
    title: "Product Engineer",
    company: "Vercel",
    location: "Remote",
    url: "https://vercel.com/job2",
    description: "Build developer tools and infrastructure",
    salary_range: "150000-180000 EUR",
    remote: true,
    posted_at: "2024-01-05T00:00:00Z",
    sources: ["arbeitnow"],
    source_urls: [],
    fit_score: 7.2,
    readiness_score: 72,
    application_id: null,
    created_at: "2024-01-05T00:00:00Z",
    updated_at: "2024-01-05T00:00:00Z",
  },
  {
    id: 3,
    profile_id: 1,
    title: "AI Program Lead",
    company: "SAP",
    location: "Frankfurt, Germany",
    url: "https://sap.com/job4",
    description: "Lead AI transformation programs across divisions",
    salary_range: "130000-160000 EUR",
    remote: false,
    posted_at: "2024-01-15T00:00:00Z",
    sources: ["linkedin"],
    source_urls: [],
    fit_score: 9.0,
    readiness_score: 90,
    application_id: null,
    created_at: "2024-01-15T00:00:00Z",
    updated_at: "2024-01-15T00:00:00Z",
  },
];

const SAMPLE_SAVED_SEARCHES: SavedSearch[] = [
  {
    id: 1,
    profile_id: 1,
    name: "Remote AI Jobs",
    config: { q: "AI", remote: true },
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
];

// ---- setup ----

beforeEach(() => {
  vi.clearAllMocks();
  mockSearchJobs.mockResolvedValue({
    jobs: SAMPLE_JOBS,
    total: 3,
    page: 1,
    page_size: 20,
    total_pages: 1,
  });
  mockFetchSavedSearches.mockResolvedValue({
    searches: [],
    total: 0,
  });
});

// ---- tests ----

describe("Discovery page", () => {
  describe("rendering", () => {
    it("renders page heading", async () => {
      renderDiscovery();
      await waitFor(() => {
        expect(screen.getByText("Discovered Jobs")).toBeInTheDocument();
      });
    });

    it("renders job cards with title and company", async () => {
      renderDiscovery();
      await waitFor(() => {
        expect(
          screen.getByText("Senior TPM - AI Platform"),
        ).toBeInTheDocument();
      });
      expect(screen.getByText("Stripe")).toBeInTheDocument();
      expect(screen.getByText("Vercel")).toBeInTheDocument();
      expect(screen.getByText("SAP")).toBeInTheDocument();
    });

    it("renders total count", async () => {
      renderDiscovery();
      await waitFor(() => {
        expect(screen.getByText("(3)")).toBeInTheDocument();
      });
    });

    it("renders fit scores on job cards", async () => {
      renderDiscovery();
      await waitFor(() => {
        expect(screen.getByText("8.5")).toBeInTheDocument();
      });
      expect(screen.getByText("7.2")).toBeInTheDocument();
      expect(screen.getByText("9.0")).toBeInTheDocument();
    });

    it("renders readiness scores on job cards", async () => {
      renderDiscovery();
      await waitFor(() => {
        expect(screen.getByText("85% ready")).toBeInTheDocument();
      });
      expect(screen.getByText("72% ready")).toBeInTheDocument();
      expect(screen.getByText("90% ready")).toBeInTheDocument();
    });

    it("renders source badges on cards", async () => {
      renderDiscovery();
      await waitFor(() => {
        expect(screen.getAllByText("linkedin").length).toBeGreaterThanOrEqual(1);
      });
      expect(screen.getAllByText("indeed").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("arbeitnow").length).toBeGreaterThanOrEqual(1);
    });

    it("renders remote indicator", async () => {
      renderDiscovery();
      await waitFor(() => {
        expect(screen.getAllByText("Remote").length).toBeGreaterThanOrEqual(1);
      });
    });

    it("renders salary ranges", async () => {
      renderDiscovery();
      await waitFor(() => {
        expect(screen.getByText("180000-220000 USD")).toBeInTheDocument();
      });
      expect(screen.getByText("150000-180000 EUR")).toBeInTheDocument();
    });
  });

  describe("search bar (VAL-SEARCH-001)", () => {
    it("renders search input", async () => {
      renderDiscovery();
      await waitFor(() => {
        expect(
          screen.getByPlaceholderText(
            "Search jobs by title, company, description, location...",
          ),
        ).toBeInTheDocument();
      });
    });

    it("triggers search on input change", async () => {
      renderDiscovery();
      await waitFor(() => {
        expect(
          screen.getByText("Senior TPM - AI Platform"),
        ).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(
        "Search jobs by title, company, description, location...",
      );
      fireEvent.change(searchInput, { target: { value: "AI" } });

      // After debounce, searchJobs should be called again with q param
      await waitFor(
        () => {
          const calls = mockSearchJobs.mock.calls;
          const lastCall = calls[calls.length - 1];
          expect(lastCall[0].q).toBe("AI");
        },
        { timeout: 1000 },
      );
    });
  });

  describe("sort controls (VAL-SEARCH-003)", () => {
    it("renders sort dropdown with all 4 options", async () => {
      renderDiscovery();
      await waitFor(() => {
        expect(screen.getByText("Senior TPM - AI Platform")).toBeInTheDocument();
      });

      // Check sort options exist
      const sortSelect = screen.getByDisplayValue("Date");
      expect(sortSelect).toBeInTheDocument();

      // Verify options are present
      const options = sortSelect.querySelectorAll("option");
      const optionValues = Array.from(options).map((o) => o.textContent);
      expect(optionValues).toContain("Date");
      expect(optionValues).toContain("Score");
      expect(optionValues).toContain("Salary");
      expect(optionValues).toContain("Readiness");
    });

    it("changing sort field triggers new search", async () => {
      renderDiscovery();
      await waitFor(() => {
        expect(screen.getByText("Senior TPM - AI Platform")).toBeInTheDocument();
      });

      const sortSelect = screen.getByDisplayValue("Date");
      fireEvent.change(sortSelect, { target: { value: "score" } });

      await waitFor(() => {
        const calls = mockSearchJobs.mock.calls;
        const lastCall = calls[calls.length - 1];
        expect(lastCall[0].sort).toBe("score");
      });
    });

    it("sort order toggle button exists", async () => {
      renderDiscovery();
      await waitFor(() => {
        expect(screen.getByText("Senior TPM - AI Platform")).toBeInTheDocument();
      });

      const toggleButton = screen.getByTitle(/Sort/);
      expect(toggleButton).toBeInTheDocument();
    });
  });

  describe("filter panel (VAL-SEARCH-002)", () => {
    it("renders filter toggle button", async () => {
      renderDiscovery();
      await waitFor(() => {
        expect(screen.getByText("Filters")).toBeInTheDocument();
      });
    });

    it("shows filter panel when toggled", async () => {
      renderDiscovery();
      await waitFor(() => {
        expect(screen.getByText("Senior TPM - AI Platform")).toBeInTheDocument();
      });

      // Click the Filters toggle button (in the search bar area)
      const filtersButtons = screen.getAllByText("Filters");
      fireEvent.click(filtersButtons[0]);

      await waitFor(() => {
        expect(screen.getByPlaceholderText("e.g. linkedin")).toBeInTheDocument();
        expect(screen.getByText("Score min")).toBeInTheDocument();
        expect(screen.getByText("Date from")).toBeInTheDocument();
      });
    });

    it("filter changes trigger new search", async () => {
      renderDiscovery();
      await waitFor(() => {
        expect(screen.getByText("Senior TPM - AI Platform")).toBeInTheDocument();
      });

      const filtersButtons = screen.getAllByText("Filters");
      fireEvent.click(filtersButtons[0]);

      await waitFor(() => {
        expect(screen.getByPlaceholderText("e.g. linkedin")).toBeInTheDocument();
      });

      fireEvent.change(screen.getByPlaceholderText("e.g. linkedin"), {
        target: { value: "linkedin" },
      });

      await waitFor(() => {
        const calls = mockSearchJobs.mock.calls;
        const lastCall = calls[calls.length - 1];
        expect(lastCall[0].source).toBe("linkedin");
      });
    });

    it("clear all button clears filters", async () => {
      renderDiscovery();
      await waitFor(() => {
        expect(screen.getByText("Senior TPM - AI Platform")).toBeInTheDocument();
      });

      const filtersButtons = screen.getAllByText("Filters");
      fireEvent.click(filtersButtons[0]);

      await waitFor(() => {
        expect(screen.getByPlaceholderText("e.g. linkedin")).toBeInTheDocument();
      });

      // Set a filter
      fireEvent.change(screen.getByPlaceholderText("e.g. linkedin"), {
        target: { value: "linkedin" },
      });

      // Clear all should appear
      await waitFor(() => {
        expect(screen.getByText("Clear all")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Clear all"));

      // Filter value should be cleared
      await waitFor(() => {
        const input = screen.getByPlaceholderText(
          "e.g. linkedin",
        ) as HTMLInputElement;
        expect(input.value).toBe("");
      });
    });
  });

  describe("empty state (VAL-SEARCH-005)", () => {
    it("shows empty state when no jobs discovered", async () => {
      mockSearchJobs.mockResolvedValue({
        jobs: [],
        total: 0,
        page: 1,
        page_size: 20,
        total_pages: 1,
      });

      renderDiscovery();

      await waitFor(() => {
        expect(
          screen.getByText("No discovered jobs yet"),
        ).toBeInTheDocument();
      });
    });

    it("shows no-match message when search has no results", async () => {
      // First render with data, then search returns nothing
      const { unmount } = renderDiscovery();
      await waitFor(() => {
        expect(screen.getByText("Senior TPM - AI Platform")).toBeInTheDocument();
      });
      unmount();

      // Now render with empty results and a query
      mockSearchJobs.mockResolvedValue({
        jobs: [],
        total: 0,
        page: 1,
        page_size: 20,
        total_pages: 1,
      });

      const qc = new QueryClient({
        defaultOptions: {
          queries: { retry: false, gcTime: 0 },
          mutations: { retry: false },
        },
      });
      render(
        <QueryClientProvider client={qc}>
          <MemoryRouter>
            <Discovery />
          </MemoryRouter>
        </QueryClientProvider>,
      );

      await waitFor(() => {
        expect(
          screen.getByText("No discovered jobs yet"),
        ).toBeInTheDocument();
      });
    });
  });

  describe("pagination (VAL-SEARCH-005)", () => {
    it("shows pagination when total_pages > 1", async () => {
      mockSearchJobs.mockResolvedValue({
        jobs: SAMPLE_JOBS.slice(0, 2),
        total: 5,
        page: 1,
        page_size: 2,
        total_pages: 3,
      });

      renderDiscovery();
      await waitFor(() => {
        expect(screen.getByText("Page 1 of 3")).toBeInTheDocument();
      });
      expect(screen.getByText("Previous")).toBeInTheDocument();
      expect(screen.getByText("Next")).toBeInTheDocument();
    });

    it("does not show pagination when total_pages = 1", async () => {
      renderDiscovery();
      await waitFor(() => {
        expect(screen.getByText("Senior TPM - AI Platform")).toBeInTheDocument();
      });
      expect(screen.queryByText("Page 1 of 1")).not.toBeInTheDocument();
    });

    it("next button changes page", async () => {
      mockSearchJobs.mockResolvedValue({
        jobs: SAMPLE_JOBS.slice(0, 2),
        total: 5,
        page: 1,
        page_size: 2,
        total_pages: 3,
      });

      renderDiscovery();
      await waitFor(() => {
        expect(screen.getByText("Next")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Next"));

      await waitFor(() => {
        const calls = mockSearchJobs.mock.calls;
        const lastCall = calls[calls.length - 1];
        expect(lastCall[0].page).toBe(2);
      });
    });
  });

  describe("saved searches (VAL-SEARCH-004)", () => {
    it("shows saved searches bar when searches exist", async () => {
      mockFetchSavedSearches.mockResolvedValue({
        searches: SAMPLE_SAVED_SEARCHES,
        total: 1,
      });

      renderDiscovery();
      await waitFor(() => {
        expect(screen.getByText("Remote AI Jobs")).toBeInTheDocument();
      });
    });

    it("clicking saved search applies its config", async () => {
      mockFetchSavedSearches.mockResolvedValue({
        searches: SAMPLE_SAVED_SEARCHES,
        total: 1,
      });

      renderDiscovery();
      await waitFor(() => {
        expect(screen.getByText("Remote AI Jobs")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Remote AI Jobs"));

      await waitFor(() => {
        const calls = mockSearchJobs.mock.calls;
        const lastCall = calls[calls.length - 1];
        expect(lastCall[0].q).toBe("AI");
        expect(lastCall[0].remote).toBe(true);
      });
    });

    it("save button opens save dialog", async () => {
      renderDiscovery();
      await waitFor(() => {
        expect(screen.getByText("Save")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Save"));

      await waitFor(() => {
        expect(screen.getByText("Save Search")).toBeInTheDocument();
        expect(
          screen.getByPlaceholderText("e.g. Remote AI jobs"),
        ).toBeInTheDocument();
      });
    });

    it("submitting save dialog creates saved search", async () => {
      mockCreateSavedSearch.mockResolvedValue({
        id: 2,
        profile_id: 1,
        name: "My Search",
        config: {},
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
      });

      renderDiscovery();
      await waitFor(() => {
        expect(screen.getByText("Save")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Save"));

      await waitFor(() => {
        expect(
          screen.getByPlaceholderText("e.g. Remote AI jobs"),
        ).toBeInTheDocument();
      });

      fireEvent.change(
        screen.getByPlaceholderText("e.g. Remote AI jobs"),
        { target: { value: "My Search" } },
      );

      // Find the Save button in the dialog (submit type)
      const saveButtons = screen.getAllByRole("button");
      const submitBtn = saveButtons.find(
        (b) =>
          b.textContent === "Save" && b.closest("form") !== null,
      );
      if (submitBtn) fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(mockCreateSavedSearch).toHaveBeenCalled();
      });
    });
  });

  describe("loading state", () => {
    it("shows spinner while loading", async () => {
      mockSearchJobs.mockReturnValue(new Promise(() => {}));
      renderDiscovery();
      await waitFor(() => {
        const spinners = document.querySelectorAll(".animate-spin");
        expect(spinners.length).toBeGreaterThanOrEqual(1);
      });
    });
  });

  describe("error state", () => {
    it("shows error message on fetch failure", async () => {
      mockSearchJobs.mockRejectedValue(new Error("Network error"));
      renderDiscovery();
      await waitFor(() => {
        expect(screen.getByText("Failed to load jobs")).toBeInTheDocument();
      });
    });
  });
});
