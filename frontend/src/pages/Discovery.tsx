import { useState, useCallback, useMemo, useEffect } from "react";
import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import {
  searchJobs,
  fetchSavedSearches,
  createSavedSearch,
  deleteSavedSearch,
  fetchLatestDiscoveryRun,
} from "@/api/discovery";
import { DEFAULT_PROFILE_ID } from "@/api/applications";
import type {
  DiscoveredJob,
  SavedSearchConfig,
  JobSearchParams,
} from "@/api/types";
import {
  Search,
  Loader2,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  MapPin,
  Wifi,
  Building2,
  Star,
  ArrowUpDown,
  Bookmark,
  BookmarkPlus,
  X,
  Trash2,
  SlidersHorizontal,
  AlertTriangle,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SORT_OPTIONS = [
  { value: "date", label: "Date" },
  { value: "score", label: "Score" },
  { value: "salary", label: "Salary" },
  { value: "readiness", label: "Readiness" },
];

const PAGE_SIZE = 20;

function scoreColor(score: number | null): string {
  if (score === null) return "text-gray-400";
  if (score >= 8) return "text-green-600";
  if (score >= 5) return "text-yellow-600";
  return "text-red-600";
}

function readinessColor(score: number | null): string {
  if (score === null) return "bg-gray-100 text-gray-500";
  if (score >= 80) return "bg-green-100 text-green-700";
  if (score >= 50) return "bg-yellow-100 text-yellow-700";
  return "bg-red-100 text-red-700";
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString();
}

// ---------------------------------------------------------------------------
// Filter Panel Component
// ---------------------------------------------------------------------------

function FilterPanel({
  filters,
  onFiltersChange,
  onClear,
}: Readonly<{
  filters: SavedSearchConfig;
  onFiltersChange: (f: SavedSearchConfig) => void;
  onClear: () => void;
}>) {
  const hasFilters = Object.values(filters).some(
    (v) => v !== undefined && v !== null && v !== "",
  );

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <SlidersHorizontal className="h-4 w-4 text-gray-500" />
          <h3 className="text-sm font-medium text-gray-700">Filters</h3>
        </div>
        {hasFilters && (
          <button
            onClick={onClear}
            className="text-xs text-blue-600 hover:text-blue-700"
          >
            Clear all
          </button>
        )}
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {/* Source */}
        <div>
          <label htmlFor="filter-source" className="block text-xs font-medium text-gray-500">Source</label>
          <input
            id="filter-source"
            type="text"
            placeholder="e.g. linkedin"
            value={filters.source ?? ""}
            onChange={(e) =>
              onFiltersChange({ ...filters, source: e.target.value || undefined })
            }
            className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>

        {/* Remote */}
        <div>
          <label htmlFor="filter-remote" className="block text-xs font-medium text-gray-500">Remote</label>
          <select
            id="filter-remote"
            value={
              filters.remote === undefined
                ? ""
                : filters.remote
                  ? "true"
                  : "false"
            }
            onChange={(e) =>
              onFiltersChange({
                ...filters,
                remote:
                  e.target.value === ""
                    ? undefined
                    : e.target.value === "true",
              })
            }
            className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
          >
            <option value="">Any</option>
            <option value="true">Remote only</option>
            <option value="false">On-site only</option>
          </select>
        </div>

        {/* Score range */}
        <div>
          <label htmlFor="filter-score-min" className="block text-xs font-medium text-gray-500">Score min</label>
          <input
            id="filter-score-min"
            type="number"
            min={0}
            max={10}
            step={0.5}
            placeholder="0"
            value={filters.score_min ?? ""}
            onChange={(e) =>
              onFiltersChange({
                ...filters,
                score_min: e.target.value ? Number(e.target.value) : undefined,
              })
            }
            className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>
        <div>
          <label htmlFor="filter-score-max" className="block text-xs font-medium text-gray-500">Score max</label>
          <input
            id="filter-score-max"
            type="number"
            min={0}
            max={10}
            step={0.5}
            placeholder="10"
            value={filters.score_max ?? ""}
            onChange={(e) =>
              onFiltersChange({
                ...filters,
                score_max: e.target.value ? Number(e.target.value) : undefined,
              })
            }
            className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>

        {/* Salary min */}
        <div>
          <label htmlFor="filter-salary-min" className="block text-xs font-medium text-gray-500">Salary min</label>
          <input
            id="filter-salary-min"
            type="number"
            min={0}
            step={1000}
            placeholder="e.g. 120000"
            value={filters.salary_min ?? ""}
            onChange={(e) =>
              onFiltersChange({
                ...filters,
                salary_min: e.target.value ? Number(e.target.value) : undefined,
              })
            }
            className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>

        {/* Salary max */}
        <div>
          <label htmlFor="filter-salary-max" className="block text-xs font-medium text-gray-500">Salary max</label>
          <input
            id="filter-salary-max"
            type="number"
            min={0}
            step={1000}
            placeholder="e.g. 200000"
            value={filters.salary_max ?? ""}
            onChange={(e) =>
              onFiltersChange({
                ...filters,
                salary_max: e.target.value ? Number(e.target.value) : undefined,
              })
            }
            className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>

        {/* Company */}
        <div>
          <label htmlFor="filter-company" className="block text-xs font-medium text-gray-500">Company</label>
          <input
            id="filter-company"
            type="text"
            placeholder="Filter by company"
            value={filters.company ?? ""}
            onChange={(e) =>
              onFiltersChange({ ...filters, company: e.target.value || undefined })
            }
            className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>

        {/* Location */}
        <div>
          <label htmlFor="filter-location" className="block text-xs font-medium text-gray-500">Location</label>
          <input
            id="filter-location"
            type="text"
            placeholder="Filter by location"
            value={filters.location ?? ""}
            onChange={(e) =>
              onFiltersChange({ ...filters, location: e.target.value || undefined })
            }
            className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>

        {/* Date range */}
        <div>
          <label htmlFor="filter-date-from" className="block text-xs font-medium text-gray-500">Date from</label>
          <input
            id="filter-date-from"
            type="date"
            value={filters.date_from ?? ""}
            onChange={(e) =>
              onFiltersChange({ ...filters, date_from: e.target.value || undefined })
            }
            className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>
        <div>
          <label htmlFor="filter-date-to" className="block text-xs font-medium text-gray-500">Date to</label>
          <input
            id="filter-date-to"
            type="date"
            value={filters.date_to ?? ""}
            onChange={(e) =>
              onFiltersChange({ ...filters, date_to: e.target.value || undefined })
            }
            className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Job Card Component
// ---------------------------------------------------------------------------

function JobCard({ job }: Readonly<{ job: DiscoveredJob }>) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 transition-shadow hover:shadow-md">
      <div className="flex items-start justify-between">
        <div className="min-w-0 flex-1">
          <h3 className="truncate font-medium text-gray-900">{job.title}</h3>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-gray-500">
            <span className="flex items-center gap-1">
              <Building2 className="h-3.5 w-3.5" />
              {job.company}
            </span>
            {job.location && (
              <span className="flex items-center gap-1">
                <MapPin className="h-3.5 w-3.5" />
                {job.location}
              </span>
            )}
            {job.remote && (
              <span className="flex items-center gap-1 text-green-600">
                <Wifi className="h-3.5 w-3.5" />
                Remote
              </span>
            )}
          </div>
        </div>
        <div className="ml-4 flex flex-col items-end gap-1">
          {job.fit_score !== null && (
            <span
              className={`flex items-center gap-1 text-sm font-semibold ${scoreColor(job.fit_score)}`}
            >
              <Star className="h-3.5 w-3.5" />
              {job.fit_score.toFixed(1)}
            </span>
          )}
          {job.readiness_score !== null && (
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${readinessColor(job.readiness_score)}`}
            >
              {Math.round(job.readiness_score)}% ready
            </span>
          )}
        </div>
      </div>

      {job.description && (
        <p className="mt-2 line-clamp-2 text-sm text-gray-600">
          {job.description}
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {job.salary_range && (
          <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
            {job.salary_range}
          </span>
        )}
        {job.sources.map((source) => (
          <span
            key={source}
            className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600"
          >
            {source}
          </span>
        ))}
        <span className="ml-auto text-xs text-gray-400">
          {formatDate(job.posted_at ?? job.created_at)}
        </span>
        {job.url && (
          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-gray-400 hover:text-blue-600"
            title="Open job posting"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Save Search Dialog
// ---------------------------------------------------------------------------

function SaveSearchDialog({
  config,
  onClose,
}: Readonly<{
  config: SavedSearchConfig;
  onClose: () => void;
}>) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      createSavedSearch({
        profile_id: DEFAULT_PROFILE_ID,
        name,
        config,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["saved-searches"] });
      onClose();
    },
  });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
      onKeyDown={(e) => e.key === 'Escape' && onClose()}
      role="presentation"
    >
      <div
        className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Save Search</h2>
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
            <label htmlFor="save-search-name" className="block text-sm font-medium text-gray-700">
              Search Name *
            </label>
            <input
              id="save-search-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Remote AI jobs"
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              required
              autoFocus
            />
          </div>
          <div className="rounded-md bg-gray-50 p-3">
            <p className="text-xs font-medium text-gray-500">Saved filters:</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {Object.entries(config).map(
                ([key, val]) =>
                  val !== undefined &&
                  val !== null &&
                  val !== "" && (
                    <span
                      key={key}
                      className="rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-700"
                    >
                      {key}: {String(val)}
                    </span>
                  ),
              )}
              {Object.values(config).every(
                (v) => v === undefined || v === null || v === "",
              ) && (
                <span className="text-xs text-gray-400">No filters set</span>
              )}
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
              disabled={!name.trim() || mutation.isPending}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {mutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Save"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Discovery Page
// ---------------------------------------------------------------------------

export function Discovery() {
  const profileId = DEFAULT_PROFILE_ID;
  const queryClient = useQueryClient();

  // Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [filters, setFilters] = useState<SavedSearchConfig>({});
  const [sortField, setSortField] = useState("date");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const [showFilters, setShowFilters] = useState(false);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [creditsExhausted, setCreditsExhausted] = useState(
    () => sessionStorage.getItem("credits_exhausted") === "true",
  );
  const [newMatchesCount, setNewMatchesCount] = useState(0);

  // Check for new matches since last visit
  useEffect(() => {
    fetchLatestDiscoveryRun(DEFAULT_PROFILE_ID).then((run) => {
      if (!run?.completed_at || !run.new_jobs) return;
      const lastVisit = localStorage.getItem("lastDiscoveryVisit");
      if (!lastVisit || new Date(run.completed_at) > new Date(lastVisit)) {
        setNewMatchesCount(run.new_jobs);
      }
    });
    localStorage.setItem("lastDiscoveryVisit", new Date().toISOString());
  }, []);

  // Debounce search input
  const [debounceTimer, setDebounceTimer] = useState<ReturnType<typeof setTimeout> | null>(null);
  const handleSearchChange = useCallback(
    (value: string) => {
      setSearchQuery(value);
      if (debounceTimer) clearTimeout(debounceTimer);
      const timer = setTimeout(() => {
        setDebouncedQuery(value);
        setPage(1);
      }, 300);
      setDebounceTimer(timer);
    },
    [debounceTimer],
  );

  // Build search params
  const searchParams: JobSearchParams = useMemo(
    () => ({
      profile_id: profileId,
      q: debouncedQuery || undefined,
      source: filters.source,
      remote: filters.remote,
      salary_min: filters.salary_min,
      salary_max: filters.salary_max,
      score_min: filters.score_min,
      score_max: filters.score_max,
      date_from: filters.date_from,
      date_to: filters.date_to,
      company: filters.company,
      location: filters.location,
      sort: sortField,
      order: sortOrder,
      page,
      page_size: PAGE_SIZE,
    }),
    [profileId, debouncedQuery, filters, sortField, sortOrder, page],
  );

  // Fetch jobs
  const {
    data: jobsData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["jobs-search", searchParams],
    queryFn: () => searchJobs(searchParams),
  });

  // Fetch saved searches
  const { data: savedSearchesData } = useQuery({
    queryKey: ["saved-searches", profileId],
    queryFn: () => fetchSavedSearches(profileId),
  });

  // Delete saved search mutation
  const deleteMutation = useMutation({
    mutationFn: (searchId: number) => deleteSavedSearch(searchId, profileId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["saved-searches"] });
    },
  });

  // Apply saved search
  const applySavedSearch = useCallback(
    (config: SavedSearchConfig) => {
      setSearchQuery(config.q ?? "");
      setDebouncedQuery(config.q ?? "");
      setFilters({
        source: config.source,
        remote: config.remote,
        salary_min: config.salary_min,
        salary_max: config.salary_max,
        score_min: config.score_min,
        score_max: config.score_max,
        date_from: config.date_from,
        date_to: config.date_to,
        company: config.company,
        location: config.location,
      });
      if (config.sort) setSortField(config.sort);
      if (config.order) setSortOrder(config.order as "asc" | "desc");
      setPage(1);
      setShowFilters(true);
    },
    [],
  );

  // Build current config for saving
  const currentConfig: SavedSearchConfig = useMemo(
    () => ({
      q: debouncedQuery || undefined,
      ...filters,
      sort: sortField,
      order: sortOrder,
    }),
    [debouncedQuery, filters, sortField, sortOrder],
  );

  const clearFilters = useCallback(() => {
    setFilters({});
    setPage(1);
  }, []);

  const handleFiltersChange = useCallback((f: SavedSearchConfig) => {
    setFilters(f);
    setPage(1);
  }, []);

  const toggleSortOrder = useCallback(() => {
    setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"));
    setPage(1);
  }, []);

  const savedSearches = savedSearchesData?.searches ?? [];
  const jobs = jobsData?.jobs ?? [];
  const total = jobsData?.total ?? 0;
  const totalPages = jobsData?.total_pages ?? 1;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">
          Discovered Jobs
          {total > 0 && (
            <span className="ml-2 text-lg font-normal text-gray-500">
              ({total})
            </span>
          )}
        </h1>
      </div>

      {/* Saved searches bar */}
      {savedSearches.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <Bookmark className="h-4 w-4 text-gray-400" />
          {savedSearches.map((ss) => (
            <div key={ss.id} className="group flex items-center gap-1">
              <button
                onClick={() => applySavedSearch(ss.config)}
                className="rounded-full border border-gray-200 bg-white px-3 py-1 text-xs font-medium text-gray-700 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700"
              >
                {ss.name}
              </button>
              <button
                onClick={() => deleteMutation.mutate(ss.id)}
                className="hidden rounded p-0.5 text-gray-300 hover:text-red-500 group-hover:block"
                title="Delete saved search"
              >
                <Trash2 className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Search bar + sort */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[240px] flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search jobs by title, company, description, location..."
            value={searchQuery}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="w-full rounded-md border border-gray-300 py-2 pl-9 pr-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        {/* Sort */}
        <div className="flex items-center gap-1">
          <select
            value={sortField}
            onChange={(e) => {
              setSortField(e.target.value);
              setPage(1);
            }}
            className="rounded-md border border-gray-300 px-2 py-2 text-sm focus:border-blue-500 focus:outline-none"
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <button
            onClick={toggleSortOrder}
            className="rounded-md border border-gray-300 p-2 text-gray-500 hover:bg-gray-50"
            title={`Sort ${sortOrder === "asc" ? "ascending" : "descending"}`}
          >
            <ArrowUpDown className="h-4 w-4" />
          </button>
        </div>

        {/* Filter toggle */}
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={`flex items-center gap-1.5 rounded-md border px-3 py-2 text-sm font-medium ${
            showFilters
              ? "border-blue-300 bg-blue-50 text-blue-700"
              : "border-gray-300 text-gray-700 hover:bg-gray-50"
          }`}
        >
          <SlidersHorizontal className="h-4 w-4" />
          Filters
        </button>

        {/* Save search */}
        <button
          onClick={() => setShowSaveDialog(true)}
          className="flex items-center gap-1.5 rounded-md border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          title="Save current search"
        >
          <BookmarkPlus className="h-4 w-4" />
          Save
        </button>
      </div>

      {/* Filter panel */}
      {showFilters && (
        <FilterPanel
          filters={filters}
          onFiltersChange={handleFiltersChange}
          onClear={clearFilters}
        />
      )}

      {/* Credits exhausted banner */}
      {creditsExhausted && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
          <div className="flex items-start justify-between">
            <div className="flex gap-3">
              <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-600" />
              <div>
                <h3 className="text-sm font-semibold text-amber-800">
                  AI Scoring Stopped
                </h3>
                <p className="mt-1 text-sm text-amber-700">
                  OpenRouter credits have been exhausted. Some jobs may not have
                  scores.{" "}
                  <a
                    href="https://openrouter.ai"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium underline hover:text-amber-900"
                  >
                    Add credits at openrouter.ai
                  </a>
                </p>
              </div>
            </div>
            <button
              onClick={() => {
                setCreditsExhausted(false);
                sessionStorage.removeItem("credits_exhausted");
              }}
              className="ml-4 text-amber-400 hover:text-amber-600"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* New matches banner */}
      {newMatchesCount > 0 && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-4">
          <div className="flex items-start justify-between">
            <div className="flex gap-3">
              <Star className="mt-0.5 h-5 w-5 flex-shrink-0 text-green-600" />
              <div>
                <h3 className="text-sm font-semibold text-green-800">
                  New Matches Found
                </h3>
                <p className="mt-1 text-sm text-green-700">
                  {newMatchesCount} new job{newMatchesCount !== 1 ? "s" : ""}{" "}
                  discovered since your last visit.
                </p>
              </div>
            </div>
            <button
              onClick={() => setNewMatchesCount(0)}
              className="ml-4 text-green-400 hover:text-green-600"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <p className="text-red-600">Failed to load jobs</p>
        </div>
      )}

      {/* Results */}
      {!isLoading && !error && (
        <>
          {jobs.length === 0 ? (
            <div className="rounded-lg border-2 border-dashed border-gray-300 bg-white p-12 text-center">
              <Search className="mx-auto h-12 w-12 text-gray-400" />
              <h2 className="mt-4 text-lg font-semibold text-gray-900">
                {debouncedQuery ||
                Object.values(filters).some(
                  (v) => v !== undefined && v !== null && v !== "",
                )
                  ? "No jobs match your search"
                  : "No discovered jobs yet"}
              </h2>
              <p className="mt-2 text-sm text-gray-500">
                {debouncedQuery ||
                Object.values(filters).some(
                  (v) => v !== undefined && v !== null && v !== "",
                )
                  ? "Try adjusting your search query or filters."
                  : "Run a discovery sweep to find jobs."}
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {jobs.map((job) => (
                <JobCard key={job.id} job={job} />
              ))}
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-gray-200 pt-4">
              <p className="text-sm text-gray-500">
                Showing{" "}
                {Math.min((page - 1) * PAGE_SIZE + 1, total)}–
                {Math.min(page * PAGE_SIZE, total)} of {total} jobs
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage(Math.max(1, page - 1))}
                  disabled={page <= 1}
                  className="flex items-center gap-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                >
                  <ChevronLeft className="h-4 w-4" />
                  Previous
                </button>
                <span className="text-sm text-gray-500">
                  Page {page} of {totalPages}
                </span>
                <button
                  onClick={() => setPage(Math.min(totalPages, page + 1))}
                  disabled={page >= totalPages}
                  className="flex items-center gap-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Save search dialog */}
      {showSaveDialog && (
        <SaveSearchDialog
          config={currentConfig}
          onClose={() => setShowSaveDialog(false)}
        />
      )}
    </div>
  );
}
