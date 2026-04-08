/**
 * PipelineFilters — filter and sort controls for the pipeline list view.
 *
 * Supports: filter by status, search by company, sort by score/date.
 */

import { Search, ArrowUpDown, Filter } from "lucide-react";
import { APPLICATION_STATUSES, STATUS_LABELS, type ApplicationStatus } from "@/api/types";

export interface FilterState {
  status: string;
  search: string;
  sort: string;
  order: string;
}

interface PipelineFiltersProps {
  filters: FilterState;
  onChange: (filters: FilterState) => void;
}

export function PipelineFilters({ filters, onChange }: PipelineFiltersProps) {
  return (
    <div
      data-testid="pipeline-filters"
      className="flex flex-wrap items-center gap-3"
    >
      {/* Search by company */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input
          data-testid="filter-search"
          type="text"
          value={filters.search}
          onChange={(e) => onChange({ ...filters, search: e.target.value })}
          placeholder="Search company…"
          className="w-48 rounded-md border border-gray-300 py-2 pl-9 pr-3 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
        />
      </div>

      {/* Filter by status */}
      <div className="relative flex items-center gap-1">
        <Filter className="h-4 w-4 text-gray-400" />
        <select
          data-testid="filter-status"
          value={filters.status}
          onChange={(e) => onChange({ ...filters, status: e.target.value })}
          className="rounded-md border border-gray-300 py-2 pl-2 pr-8 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
        >
          <option value="">All statuses</option>
          {APPLICATION_STATUSES.map((s: ApplicationStatus) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))}
        </select>
      </div>

      {/* Sort by */}
      <div className="relative flex items-center gap-1">
        <ArrowUpDown className="h-4 w-4 text-gray-400" />
        <select
          data-testid="filter-sort"
          value={filters.sort}
          onChange={(e) => onChange({ ...filters, sort: e.target.value })}
          className="rounded-md border border-gray-300 py-2 pl-2 pr-8 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
        >
          <option value="">Sort by…</option>
          <option value="date">Date</option>
          <option value="score">Score</option>
        </select>
      </div>

      {/* Sort order */}
      {filters.sort && (
        <button
          data-testid="filter-order"
          onClick={() =>
            onChange({
              ...filters,
              order: filters.order === "desc" ? "asc" : "desc",
            })
          }
          className="rounded-md border border-gray-300 px-2 py-2 text-sm text-gray-700 hover:bg-gray-50"
          title={`Sort ${filters.order === "desc" ? "descending" : "ascending"}`}
        >
          {filters.order === "desc" ? "↓ Newest" : "↑ Oldest"}
        </button>
      )}

      {/* Clear filters */}
      {(filters.status || filters.search || filters.sort) && (
        <button
          data-testid="filter-clear"
          onClick={() =>
            onChange({ status: "", search: "", sort: "", order: "desc" })
          }
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          Clear filters
        </button>
      )}
    </div>
  );
}
