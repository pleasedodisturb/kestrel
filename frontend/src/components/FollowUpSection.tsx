/**
 * FollowUpSection — displays existing follow-ups and allows creating new ones.
 * Used on the application detail page.
 */

import { useState, useCallback } from "react";
import { useCreateFollowUp, useCompleteFollowUp } from "@/hooks/useFollowUps";
import type { FollowUpSummary } from "@/api/types";
import { Clock, Plus, Check, Bell, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

interface FollowUpSectionProps {
  readonly applicationId: number;
  readonly followUps: FollowUpSummary[];
}

const FOLLOW_UP_TYPES = [
  { value: "email", label: "Email" },
  { value: "phone", label: "Phone" },
  { value: "linkedin", label: "LinkedIn" },
  { value: "other", label: "Other" },
];

function formatDate(iso: string): string {
  try {
    const date = new Date(iso);
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

function isOverdue(dueDateStr: string): boolean {
  const dueDate = new Date(dueDateStr);
  // For date-only reminders, treat as due through end of local day.
  // Set the due date to end of day (23:59:59.999) in local time
  // so that a follow-up due "today" is not marked overdue until tomorrow.
  const endOfDay = new Date(dueDate);
  endOfDay.setHours(23, 59, 59, 999);
  return endOfDay < new Date();
}

export function FollowUpSection({
  applicationId,
  followUps,
}: FollowUpSectionProps) {
  const [showForm, setShowForm] = useState(false);
  const [dueDate, setDueDate] = useState("");
  const [followUpType, setFollowUpType] = useState("email");
  const [notes, setNotes] = useState("");

  const createMutation = useCreateFollowUp();
  const completeMutation = useCompleteFollowUp();

  const handleCreate = useCallback(() => {
    if (!dueDate) return;

    // For date-only input (YYYY-MM-DD), set due time to end of local day
    // so the reminder is not marked overdue prematurely in UTC comparisons.
    const dueDateObj = new Date(dueDate);
    dueDateObj.setHours(23, 59, 59, 0);

    createMutation.mutate(
      {
        application_id: applicationId,
        due_date: dueDateObj.toISOString(),
        follow_up_type: followUpType,
        notes: notes || undefined,
      },
      {
        onSuccess: () => {
          setShowForm(false);
          setDueDate("");
          setFollowUpType("email");
          setNotes("");
        },
      },
    );
  }, [applicationId, dueDate, followUpType, notes, createMutation]);

  const handleComplete = useCallback(
    (id: number) => {
      completeMutation.mutate(id);
    },
    [completeMutation],
  );

  const pendingFollowUps = followUps.filter((fu) => !fu.completed_at);
  const completedFollowUps = followUps.filter((fu) => fu.completed_at);

  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <Bell className="h-5 w-5" />
          Follow-Ups
        </h2>
        <button
          data-testid="add-follow-up-button"
          onClick={() => setShowForm(!showForm)}
          className="inline-flex items-center gap-1 rounded-md border border-gray-300 bg-white px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50"
        >
          <Plus className="h-3 w-3" />
          Add
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <div
          data-testid="follow-up-form"
          className="mb-4 rounded-md border border-gray-200 bg-gray-50 p-4 space-y-3"
        >
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="follow-up-due-date" className="block text-xs font-medium text-gray-600 mb-1">
                Due Date *
              </label>
              <input
                id="follow-up-due-date"
                data-testid="follow-up-due-date"
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
              />
            </div>
            <div>
              <label htmlFor="follow-up-type" className="block text-xs font-medium text-gray-600 mb-1">
                Type *
              </label>
              <select
                id="follow-up-type"
                data-testid="follow-up-type"
                value={followUpType}
                onChange={(e) => setFollowUpType(e.target.value)}
                className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
              >
                {FOLLOW_UP_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label htmlFor="follow-up-notes" className="block text-xs font-medium text-gray-600 mb-1">
              Notes
            </label>
            <textarea
              id="follow-up-notes"
              data-testid="follow-up-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="e.g. Follow up with recruiter about next steps"
              className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
            />
          </div>
          <div className="flex gap-2 justify-end">
            <button
              data-testid="follow-up-cancel"
              onClick={() => setShowForm(false)}
              className="rounded-md border border-gray-300 bg-white px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              data-testid="follow-up-submit"
              onClick={handleCreate}
              disabled={!dueDate || createMutation.isPending}
              className="rounded-md bg-gray-900 px-3 py-1 text-xs font-medium text-white hover:bg-gray-800 disabled:opacity-50"
            >
              {createMutation.isPending ? "Creating…" : "Create Follow-Up"}
            </button>
          </div>
          {createMutation.isError && (
            <p className="text-xs text-red-600">
              {createMutation.error instanceof Error ? createMutation.error.message : String(createMutation.error)}
            </p>
          )}
        </div>
      )}

      {/* Pending follow-ups */}
      {pendingFollowUps.length === 0 && completedFollowUps.length === 0 && !showForm && (
        <p
          data-testid="follow-ups-empty"
          className="text-sm text-gray-400"
        >
          No follow-ups scheduled
        </p>
      )}

      {pendingFollowUps.length > 0 && (
        <div data-testid="pending-follow-ups" className="space-y-2">
          {pendingFollowUps.map((fu) => {
            const overdue = isOverdue(fu.due_date);
            return (
              <div
                key={fu.id}
                data-testid={`follow-up-${fu.id}`}
                className={cn(
                  "flex items-start gap-3 rounded-md border px-3 py-2",
                  overdue
                    ? "border-red-200 bg-red-50"
                    : "border-gray-200 bg-white",
                )}
              >
                <button
                  data-testid={`complete-follow-up-${fu.id}`}
                  onClick={() => handleComplete(fu.id)}
                  disabled={completeMutation.isPending}
                  className={cn(
                    "mt-0.5 flex-shrink-0 rounded-full border p-0.5",
                    overdue
                      ? "border-red-300 text-red-500 hover:bg-red-100"
                      : "border-gray-300 text-gray-400 hover:bg-gray-100",
                  )}
                >
                  <Check className="h-3 w-3" />
                </button>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium capitalize text-gray-700">
                      {fu.follow_up_type}
                    </span>
                    {overdue && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-1.5 py-0.5 text-xs font-medium text-red-700">
                        <AlertTriangle className="h-3 w-3" />
                        Overdue
                      </span>
                    )}
                  </div>
                  {fu.notes && (
                    <p className="mt-0.5 text-xs text-gray-600 truncate">
                      {fu.notes}
                    </p>
                  )}
                  <div className="mt-1 flex items-center gap-1 text-xs text-gray-400">
                    <Clock className="h-3 w-3" />
                    Due {formatDate(fu.due_date)}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Completed follow-ups */}
      {completedFollowUps.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-medium text-gray-500 mb-1">Completed</p>
          <div className="space-y-1">
            {completedFollowUps.map((fu) => (
              <div
                key={fu.id}
                className="flex items-center gap-2 px-3 py-1 text-xs text-gray-400 line-through"
              >
                <Check className="h-3 w-3 text-green-500 flex-shrink-0" />
                <span className="capitalize">{fu.follow_up_type}</span>
                {fu.notes && <span>— {fu.notes}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
