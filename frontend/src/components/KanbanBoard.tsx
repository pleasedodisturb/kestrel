/**
 * KanbanBoard — the full drag-and-drop pipeline board.
 *
 * Shows 8 status columns. Dragging a card between columns triggers a PATCH
 * request to update the application status. Empty boards show a friendly CTA.
 * Clicking a card navigates to the detail page.
 */

import { useCallback, useMemo, useRef, useState } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
  type DragStartEvent,
  type DragEndEvent,
  type DragOverEvent,
} from "@dnd-kit/core";
import type { Application, ApplicationStatus } from "@/api/types";
import { APPLICATION_STATUSES, normalizeStatus } from "@/api/types";
import { KanbanColumn } from "@/components/KanbanColumn";
import { KanbanCard } from "@/components/KanbanCard";
import { CreateApplicationDialog } from "@/components/CreateApplicationDialog";
import { PipelineFilters, type FilterState } from "@/components/PipelineFilters";
import { OverdueBanner } from "@/components/OverdueBanner";
import { CreditsExhaustedBanner } from "@/components/CreditsExhaustedBanner";
import {
  OnboardingWizard,
  WIZARD_DISMISSED_KEY,
} from "@/components/OnboardingWizard";
import {
  DiscoveryNudge,
  NUDGE_DISMISSED_KEY,
} from "@/components/DiscoveryNudge";
import { useApplications, useUpdateApplication } from "@/hooks/useApplications";
import { Briefcase, Plus } from "lucide-react";

export function KanbanBoard() {
  const [filters, setFilters] = useState<FilterState>({
    status: "",
    search: "",
    sort: "",
    order: "desc",
  });

  const queryParams = useMemo(
    () => ({
      status: filters.status || undefined,
      search: filters.search || undefined,
      sort: filters.sort || undefined,
      order: filters.order || undefined,
    }),
    [filters],
  );

  const { data, isLoading, error } = useApplications(queryParams);
  const updateMutation = useUpdateApplication();
  const [activeApp, setActiveApp] = useState<Application | null>(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showWizard, setShowWizard] = useState(
    () => localStorage.getItem(WIZARD_DISMISSED_KEY) !== "true",
  );
  const [nudgeDismissed, setNudgeDismissed] = useState(
    () => localStorage.getItem(NUDGE_DISMISSED_KEY) === "true",
  );
  // Track which column the dragged card is currently over (needed because
  // closestCorners may resolve over.id to a sibling card's sortable ID
  // instead of the column droppable ID).
  const targetColumnRef = useRef<ApplicationStatus | null>(null);

  // Group applications by status (case-insensitive to handle DB variants)
  const columns = useMemo(() => {
    const grouped: Record<ApplicationStatus, Application[]> = {
      discovered: [],
      interested: [],
      applied: [],
      interviewing: [],
      offer: [],
      accepted: [],
      rejected: [],
      ghosted: [],
    };
    if (data?.applications) {
      for (const app of data.applications) {
        const status = normalizeStatus(app.status);
        if (grouped[status]) {
          grouped[status].push(app);
        }
      }
    }
    return grouped;
  }, [data]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  );

  const findApplication = useCallback(
    (id: number): Application | undefined =>
      data?.applications.find((a) => a.id === id),
    [data],
  );

  const handleDragStart = useCallback(
    (event: DragStartEvent) => {
      targetColumnRef.current = null;
      const app = findApplication(event.active.id as number);
      if (app) setActiveApp(app);
    },
    [findApplication],
  );

  const handleDragOver = useCallback(
    (event: DragOverEvent) => {
      const { over } = event;
      if (!over) return;

      // If hovering directly over a column droppable, record it.
      if (APPLICATION_STATUSES.includes(over.id as ApplicationStatus)) {
        targetColumnRef.current = over.id as ApplicationStatus;
      } else {
        // Hovering over a card — resolve which column it belongs to.
        const overApp = findApplication(over.id as number);
        if (overApp) {
          targetColumnRef.current = normalizeStatus(overApp.status);
        }
      }
    },
    [findApplication],
  );

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      setActiveApp(null);
      const { active, over } = event;
      const trackedColumn = targetColumnRef.current;
      targetColumnRef.current = null;

      if (!over) return;

      // Dropped on itself — no-op
      if (over.id === active.id) return;

      const appId = active.id as number;
      const app = findApplication(appId);
      if (!app) return;

      // Determine the target column. Prefer the column tracked during
      // onDragOver because closestCorners may resolve over.id to a
      // sibling card's sortable ID rather than the column droppable.
      let targetStatus: ApplicationStatus | undefined;
      if (APPLICATION_STATUSES.includes(over.id as ApplicationStatus)) {
        targetStatus = over.id as ApplicationStatus;
      } else if (trackedColumn) {
        targetStatus = trackedColumn;
      } else {
        // Last resort: look up which column the card under the pointer belongs to.
        const overApp = findApplication(over.id as number);
        if (overApp) {
          targetStatus = normalizeStatus(overApp.status);
        }
      }

      // Normalize current app status for comparison (handles migrated rows)
      const currentStatus = normalizeStatus(app.status);
      if (!targetStatus || targetStatus === currentStatus) return;

      // Always send the canonical lowercase status to the backend
      updateMutation.mutate({ id: appId, data: { status: targetStatus } });
    },
    [findApplication, updateMutation],
  );

  // Loading state
  if (isLoading) {
    return (
      <div
        data-testid="kanban-loading"
        className="flex items-center justify-center py-20"
      >
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-gray-900" />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div
        data-testid="kanban-error"
        className="rounded-lg border border-red-200 bg-red-50 p-6 text-center text-red-700"
      >
        <p className="font-medium">Failed to load applications</p>
        <p className="mt-1 text-sm">{error instanceof Error ? error.message : String(error)}</p>
      </div>
    );
  }

  const totalCount = data?.total ?? 0;

  // Discovery nudge: user has added 10+ applications but has never opened
  // the Discovery page (no `lastDiscoveryVisit` key — set by Discovery.tsx
  // on every visit). Once dismissed, never reappears.
  const showDiscoveryNudge =
    !nudgeDismissed &&
    totalCount >= 10 &&
    globalThis.window !== undefined &&
    localStorage.getItem("lastDiscoveryVisit") === null;

  // Empty board CTA
  if (totalCount === 0 && !filters.status && !filters.search && !filters.sort) {
    return (
      <>
        <div data-testid="kanban-empty" className="py-20 text-center">
          <Briefcase className="mx-auto h-12 w-12 text-gray-300" />
          <h2 className="mt-4 text-lg font-semibold text-gray-900">
            No applications yet
          </h2>
          <p className="mt-2 text-sm text-gray-500">
            Start tracking your job search by adding your first application.
          </p>
          <button
            data-testid="kanban-add-cta"
            onClick={() => setShowCreateDialog(true)}
            className="mt-6 inline-flex items-center rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:ring-offset-2"
          >
            Add Application
          </button>
        </div>
        {showWizard && (
          <OnboardingWizard
            onClose={() => setShowWizard(false)}
            onAddApplication={() => setShowCreateDialog(true)}
          />
        )}
        <CreateApplicationDialog
          open={showCreateDialog}
          onClose={() => setShowCreateDialog(false)}
        />
      </>
    );
  }

  return (
    <section>
      {/* Header with total count + add button */}
      <header className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Pipeline</h1>
        <div className="flex items-center gap-3">
          <span
            data-testid="kanban-total-count"
            className="rounded-full bg-gray-100 px-3 py-1 text-sm font-medium text-gray-700"
          >
            {totalCount} application{totalCount === 1 ? "" : "s"}
          </span>
          <button
            data-testid="add-application-button"
            onClick={() => setShowCreateDialog(true)}
            className="inline-flex items-center gap-1 rounded-md bg-gray-900 px-3 py-2 text-sm font-medium text-white shadow-sm hover:bg-gray-800"
          >
            <Plus className="h-4 w-4" />
            Add
          </button>
        </div>
      </header>

      {/* Credits exhausted banner (402/429 from OpenRouter) */}
      <CreditsExhaustedBanner />

      {/* Overdue follow-ups banner */}
      <OverdueBanner />

      {/* Discovery nudge for users who haven't tried Discovery yet */}
      {showDiscoveryNudge && (
        <DiscoveryNudge onDismiss={() => setNudgeDismissed(true)} />
      )}

      {/* Filter and sort controls */}
      <div className="mb-4">
        <PipelineFilters filters={filters} onChange={setFilters} />
      </div>

      {/* Mutation error toast */}
      {updateMutation.isError && (
        <div
          data-testid="kanban-update-error"
          className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700"
        >
          {updateMutation.error instanceof Error ? updateMutation.error.message : String(updateMutation.error)}
        </div>
      )}

      {/* Filtered empty state */}
      {totalCount === 0 && (filters.status || filters.search || filters.sort) && (
        <div data-testid="kanban-filtered-empty" className="py-12 text-center">
          <p className="text-sm text-gray-500">
            No applications match your filters.
          </p>
        </div>
      )}

      {/* Kanban columns */}
      {totalCount > 0 && (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={handleDragStart}
          onDragOver={handleDragOver}
          onDragEnd={handleDragEnd}
        >
          <div
            data-testid="kanban-board"
            className="flex gap-4 overflow-x-auto pb-4"
          >
            {APPLICATION_STATUSES.map((status) => (
              <KanbanColumn
                key={status}
                status={status}
                applications={columns[status]}
              />
            ))}
          </div>

          <DragOverlay>
            {activeApp ? <KanbanCard application={activeApp} /> : null}
          </DragOverlay>
        </DndContext>
      )}

      <CreateApplicationDialog
        open={showCreateDialog}
        onClose={() => setShowCreateDialog(false)}
      />
    </section>
  );
}
