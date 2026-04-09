/**
 * KanbanColumn — a single status column in the Kanban board.
 * Renders its applications as draggable cards.
 * Shows a placeholder when empty.
 */

import { useDroppable } from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import type { Application, ApplicationStatus } from "@/api/types";
import { STATUS_LABELS, STATUS_COLORS } from "@/api/types";
import { KanbanCard } from "@/components/KanbanCard";
import { cn } from "@/lib/utils";

interface KanbanColumnProps {
  readonly status: ApplicationStatus;
  readonly applications: Application[];
}

export function KanbanColumn({ status, applications }: KanbanColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id: status });
  const colors = STATUS_COLORS[status];

  const itemIds = applications.map((a) => a.id);

  return (
    <div
      ref={setNodeRef}
      data-testid={`kanban-column-${status}`}
      className={cn(
        "flex w-64 shrink-0 flex-col rounded-lg border",
        colors.border,
        colors.bg,
        isOver && "ring-2 ring-blue-400",
      )}
    >
      {/* Column header */}
      <div className="flex items-center justify-between border-b px-3 py-2">
        <h3 className={cn("text-sm font-semibold", colors.text)}>
          {STATUS_LABELS[status]}
        </h3>
        <span
          data-testid={`column-count-${status}`}
          className={cn(
            "rounded-full px-2 py-0.5 text-xs font-medium",
            colors.badge,
          )}
        >
          {applications.length}
        </span>
      </div>

      {/* Cards area */}
      <SortableContext items={itemIds} strategy={verticalListSortingStrategy}>
        <div className="flex flex-1 flex-col gap-2 overflow-y-auto p-2 min-h-[120px]">
          {applications.length === 0 ? (
            <p
              data-testid={`column-empty-${status}`}
              className="py-8 text-center text-xs text-gray-400"
            >
              No applications
            </p>
          ) : (
            applications.map((app) => (
              <KanbanCard key={app.id} application={app} />
            ))
          )}
        </div>
      </SortableContext>
    </div>
  );
}
