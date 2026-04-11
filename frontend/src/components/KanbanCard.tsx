/**
 * KanbanCard — a draggable card representing a single application.
 * Shows company, role, fit score, and ghost indicator.
 * Clicking (without dragging) navigates to the detail page.
 */

import { useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Ghost } from "lucide-react";
import type { Application } from "@/api/types";
import { cn, scoreColor } from "@/lib/utils";
import { GradeBadge } from "@/components/GradeBadge";
import { RedFlagBadge } from "@/components/RedFlagBadge";

interface KanbanCardProps {
  readonly application: Application;
}

export function KanbanCard({ application }: KanbanCardProps) {
  const navigate = useNavigate();
  const dragStartPos = useRef<{ x: number; y: number } | null>(null);

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: application.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  // Track mouse down position to distinguish click from drag
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    dragStartPos.current = { x: e.clientX, y: e.clientY };
  }, []);

  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      if (!dragStartPos.current) {
        navigate(`/applications/${application.id}`);
        return;
      }
      const dx = Math.abs(e.clientX - dragStartPos.current.x);
      const dy = Math.abs(e.clientY - dragStartPos.current.y);
      // Only navigate if the mouse didn't move much (not a drag)
      if (dx < 5 && dy < 5) {
        navigate(`/applications/${application.id}`);
      }
      dragStartPos.current = null;
    },
    [navigate, application.id],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        navigate(`/applications/${application.id}`);
      }
    },
    [navigate, application.id],
  );

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      data-testid={`kanban-card-${application.id}`}
      className={cn(
        "cursor-grab rounded-lg border bg-white p-3 shadow-sm transition-shadow hover:shadow-md",
        isDragging && "opacity-50 shadow-lg",
        application.is_ghost && "border-orange-300 bg-orange-50",
      )}
      role="button"
      tabIndex={0}
      onMouseDown={handleMouseDown}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
    >
      <div className="flex items-start justify-between gap-1">
        <p className="text-sm font-semibold text-gray-900 truncate">
          {application.company}
        </p>
        {application.is_ghost && (
          <span
            data-testid={`ghost-indicator-${application.id}`}
            title="Possibly ghosted — no activity for a while"
            className="flex-shrink-0 text-orange-500"
          >
            <Ghost className="h-4 w-4" />
          </span>
        )}
      </div>
      <p className="mt-0.5 text-xs text-gray-600 truncate">{application.role}</p>
      <div className="mt-2 flex items-center gap-1.5">
        <GradeBadge
          score={application.fit_score}
          letterGrade={application.letter_grade}
          testId={`score-badge-${application.id}`}
        />
        <RedFlagBadge
          flags={application.red_flags}
          testId={`red-flags-${application.id}`}
        />
        {application.readiness_score != null && (() => {
          const rounded = Math.round(application.readiness_score);
          return (
            <span
              data-testid={`readiness-badge-${application.id}`}
              title={`Readiness: ${rounded}%`}
              className={cn(
                "inline-block rounded-full px-2 py-0.5 text-xs font-medium",
                scoreColor(rounded, 80, 50),
              )}
            >
              {rounded}%
            </span>
          );
        })()}
        {application.is_ghost && (
          <span className="inline-block rounded-full bg-orange-100 px-2 py-0.5 text-xs font-medium text-orange-700">
            Ghost?
          </span>
        )}
      </div>
    </div>
  );
}
