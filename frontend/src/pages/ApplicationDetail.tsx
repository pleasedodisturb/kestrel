/**
 * ApplicationDetail — full detail page for a single application.
 *
 * Shows all fields (company, role, URL, status, salary, notes, score, dates),
 * edit capability with save, activity log in reverse chronological order,
 * and archive button.
 */

import { useState, useCallback, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import {
  useApplicationDetail,
  useUpdateApplication,
  useArchiveApplication,
} from "@/hooks/useApplications";
import type { ApplicationUpdate, ScoreResponseShape } from "@/api/types";
import { STATUS_LABELS, STATUS_COLORS, normalizeStatus } from "@/api/types";
import {
  ArrowLeft,
  Save,
  Archive,
  ExternalLink,
  Clock,
  Pencil,
  X,
  FileText,
  FolderOpen,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { GradeBadge } from "@/components/GradeBadge";
import { RedFlagBadge } from "@/components/RedFlagBadge";
import { ScoreRadarChart } from "@/components/ScoreRadarChart";
import { ATSKeywordChecklist } from "@/components/ATSKeywordChecklist";
import { CalendarSection } from "@/components/CalendarSection";
import { FollowUpSection } from "@/components/FollowUpSection";
import { InterviewPrepSection } from "@/components/InterviewPrepSection";
import { StarStoriesSection } from "@/components/StarStoriesSection";
import { getApplicationScore } from "@/api/scoring";

export function ApplicationDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const applicationId = Number(id);

  const { data, isLoading, error } = useApplicationDetail(applicationId);
  const updateMutation = useUpdateApplication();
  const archiveMutation = useArchiveApplication();

  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState<ApplicationUpdate>({});
  const [scoreData, setScoreData] = useState<ScoreResponseShape | null>(null);

  // Fetch the latest scoring details (dimensional scores, ATS keywords,
  // red flags) for this application. Falls back to null when the app has
  // not been scored yet — in that case the score-specific UI sections are
  // simply hidden.
  //
  // Note: we intentionally do NOT refetch when the inline `fit_score` edit
  // saves. That override lives on the Application row, not on ScoredJob —
  // the dimensional scores and ATS keywords in `scoreData` are independent
  // of it and would return identical values after the override.
  useEffect(() => {
    if (!data?.profile_id || !data?.id) return;
    // Clear previous application's score data so it doesn't flash during
    // navigation between two applications with different scores.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: reset state when the id changes
    setScoreData(null);
    let cancelled = false;
    getApplicationScore(data.id, data.profile_id)
      .then((resp) => {
        if (!cancelled) setScoreData(resp);
      })
      .catch(() => {
        if (!cancelled) setScoreData(null);
      });
    return () => {
      cancelled = true;
    };
  }, [data?.id, data?.profile_id]);

  // Sync edit data from server data when it changes
  useEffect(() => {
    if (!data) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: sync server data to form state
    setEditData({
      company: data.company,
      role: data.role,
      url: data.url ?? "",
      source: data.source ?? "",
      salary_range: data.salary_range ?? "",
      contact: data.contact ?? "",
      next_step: data.next_step ?? "",
      notes: data.notes ?? "",
      fit_score: data.fit_score ?? undefined,
    });
  }, [data]);

  const handleSave = useCallback(() => {
    if (!data) return;

    // Only send fields that actually changed
    const changes: ApplicationUpdate = {};
    if (editData.company !== data.company) changes.company = editData.company;
    if (editData.role !== data.role) changes.role = editData.role;
    if ((editData.url ?? "") !== (data.url ?? ""))
      changes.url = editData.url;
    if ((editData.source ?? "") !== (data.source ?? ""))
      changes.source = editData.source;
    if ((editData.salary_range ?? "") !== (data.salary_range ?? ""))
      changes.salary_range = editData.salary_range;
    if ((editData.contact ?? "") !== (data.contact ?? ""))
      changes.contact = editData.contact;
    if ((editData.next_step ?? "") !== (data.next_step ?? ""))
      changes.next_step = editData.next_step;
    if ((editData.notes ?? "") !== (data.notes ?? ""))
      changes.notes = editData.notes;
    if (editData.fit_score !== data.fit_score)
      changes.fit_score = editData.fit_score;

    if (Object.keys(changes).length === 0) {
      setIsEditing(false);
      return;
    }

    updateMutation.mutate(
      { id: applicationId, data: changes },
      {
        onSuccess: () => setIsEditing(false),
      },
    );
  }, [data, editData, applicationId, updateMutation]);

  const handleArchive = useCallback(() => {
    archiveMutation.mutate(applicationId, {
      onSuccess: () => navigate("/"),
    });
  }, [applicationId, archiveMutation, navigate]);

  const handleFieldChange = useCallback(
    (field: string, value: string | number | undefined) => {
      setEditData((prev) => ({ ...prev, [field]: value }));
    },
    [],
  );

  if (isLoading) {
    return (
      <div
        data-testid="detail-loading"
        className="flex items-center justify-center py-20"
      >
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-gray-900" />
      </div>
    );
  }

  if (error) {
    const errorMsg = error instanceof Error ? error.message : String(error);
    const isNotFound = errorMsg.toLowerCase().includes("not found");
    return (
      <div data-testid="detail-error" className="py-20 text-center">
        {isNotFound ? (
          <>
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-gray-100">
              <Archive className="h-8 w-8 text-gray-400" />
            </div>
            <p data-testid="detail-removed" className="text-lg font-medium text-gray-700">
              This application has been archived or removed.
            </p>
            <p className="mt-1 text-sm text-gray-500">
              It is no longer available in the pipeline.
            </p>
          </>
        ) : (
          <p className="text-lg font-medium text-red-700">
            {errorMsg}
          </p>
        )}
        <Link
          to="/"
          className="mt-4 inline-flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Pipeline
        </Link>
      </div>
    );
  }

  if (!data) return null;

  // Normalize status to handle migrated rows with non-lowercase casing
  const normalizedStatus = normalizeStatus(data.status);
  const statusColors =
    STATUS_COLORS[normalizedStatus] ?? STATUS_COLORS.discovered;

  return (
    <section data-testid="application-detail" className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            to="/"
            data-testid="back-to-pipeline"
            className="flex items-center gap-1 rounded-md px-2 py-1 text-sm text-gray-600 hover:bg-gray-100 hover:text-gray-900"
          >
            <ArrowLeft className="h-4 w-4" />
            Pipeline
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">
            {data.company} — {data.role}
          </h1>
          <span
            data-testid="detail-status-badge"
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium",
              statusColors.badge,
            )}
          >
            {STATUS_LABELS[normalizedStatus] ?? data.status}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {!isEditing ? (
            <button
              data-testid="edit-button"
              onClick={() => setIsEditing(true)}
              className="inline-flex items-center gap-1 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50"
            >
              <Pencil className="h-4 w-4" />
              Edit
            </button>
          ) : (
            <>
              <button
                data-testid="cancel-edit-button"
                onClick={() => {
                  setIsEditing(false);
                  // Reset edit data
                  if (data) {
                    setEditData({
                      company: data.company,
                      role: data.role,
                      url: data.url ?? "",
                      source: data.source ?? "",
                      salary_range: data.salary_range ?? "",
                      contact: data.contact ?? "",
                      next_step: data.next_step ?? "",
                      notes: data.notes ?? "",
                      fit_score: data.fit_score ?? undefined,
                    });
                  }
                }}
                className="inline-flex items-center gap-1 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50"
              >
                <X className="h-4 w-4" />
                Cancel
              </button>
              <button
                data-testid="save-button"
                onClick={handleSave}
                disabled={updateMutation.isPending}
                className="inline-flex items-center gap-1 rounded-md bg-gray-900 px-3 py-2 text-sm font-medium text-white shadow-sm hover:bg-gray-800 disabled:opacity-50"
              >
                <Save className="h-4 w-4" />
                {updateMutation.isPending ? "Saving…" : "Save"}
              </button>
            </>
          )}
          <button
            data-testid="archive-button"
            onClick={handleArchive}
            disabled={archiveMutation.isPending}
            className="inline-flex items-center gap-1 rounded-md border border-red-300 bg-white px-3 py-2 text-sm font-medium text-red-700 shadow-sm hover:bg-red-50 disabled:opacity-50"
          >
            <Archive className="h-4 w-4" />
            {archiveMutation.isPending ? "Archiving…" : "Archive"}
          </button>
        </div>
      </div>

      {/* Mutation error */}
      {(updateMutation.isError || archiveMutation.isError) && (
        <div
          data-testid="detail-mutation-error"
          className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700"
        >
          {(() => {
            const err = updateMutation.error ?? archiveMutation.error;
            return err instanceof Error ? err.message : "An error occurred";
          })()}
        </div>
      )}

      {/* Main content: fields + activity log */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Fields — 2 cols wide */}
        <div className="space-y-6 lg:col-span-2">
          {/* Core fields */}
          <div className="rounded-lg border bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold text-gray-900">
              Application Details
            </h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FieldRow
                label="Company"
                value={isEditing ? editData.company ?? "" : data.company}
                isEditing={isEditing}
                testId="field-company"
                onChange={(v) => handleFieldChange("company", v)}
              />
              <FieldRow
                label="Role"
                value={isEditing ? editData.role ?? "" : data.role}
                isEditing={isEditing}
                testId="field-role"
                onChange={(v) => handleFieldChange("role", v)}
              />
              <FieldRow
                label="URL"
                value={isEditing ? editData.url ?? "" : data.url ?? ""}
                isEditing={isEditing}
                testId="field-url"
                onChange={(v) => handleFieldChange("url", v)}
                renderDisplay={(val) =>
                  val ? (
                    <a
                      href={val}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-blue-600 hover:underline"
                    >
                      {val.length > 50 ? val.slice(0, 50) + "…" : val}
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  ) : (
                    <span className="text-gray-400">—</span>
                  )
                }
              />
              <FieldRow
                label="Source"
                value={isEditing ? editData.source ?? "" : data.source ?? ""}
                isEditing={isEditing}
                testId="field-source"
                onChange={(v) => handleFieldChange("source", v)}
              />
              <FieldRow
                label="Salary Range"
                value={
                  isEditing
                    ? editData.salary_range ?? ""
                    : data.salary_range ?? ""
                }
                isEditing={isEditing}
                testId="field-salary"
                onChange={(v) => handleFieldChange("salary_range", v)}
              />
              <FieldRow
                label="Contact"
                value={
                  isEditing ? editData.contact ?? "" : data.contact ?? ""
                }
                isEditing={isEditing}
                testId="field-contact"
                onChange={(v) => handleFieldChange("contact", v)}
              />
              <div className="flex items-start gap-2">
                <div className="flex-1">
                  <FieldRow
                    label="Fit Score"
                    value={
                      isEditing
                        ? editData.fit_score != null
                          ? String(editData.fit_score)
                          : ""
                        : data.fit_score != null
                          ? String(data.fit_score)
                          : ""
                    }
                    isEditing={isEditing}
                    testId="field-score"
                    inputType="number"
                    onChange={(v) =>
                      handleFieldChange(
                        "fit_score",
                        v === "" ? undefined : Number(v),
                      )
                    }
                  />
                </div>
                <div className="pt-6">
                  <GradeBadge
                    score={
                      isEditing
                        ? editData.fit_score ?? null
                        : data.fit_score
                    }
                    letterGrade={data.letter_grade}
                    testId="grade-badge-detail"
                  />
                </div>
              </div>
              <FieldRow
                label="Status"
                value={data.status}
                isEditing={false}
                testId="field-status"
              />
            </div>

            {/* Notes — full width */}
            <div className="mt-4">
              <label htmlFor="field-notes-input" className="block text-sm font-medium text-gray-500">
                Notes
              </label>
              {isEditing ? (
                <textarea
                  id="field-notes-input"
                  data-testid="field-notes-input"
                  value={editData.notes ?? ""}
                  onChange={(e) =>
                    handleFieldChange("notes", e.target.value)
                  }
                  rows={4}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
                />
              ) : (
                <p
                  data-testid="field-notes"
                  className="mt-1 whitespace-pre-wrap text-sm text-gray-900"
                >
                  {data.notes || (
                    <span className="text-gray-400">No notes</span>
                  )}
                </p>
              )}
            </div>

            {/* Next Step */}
            <div className="mt-4">
              <label htmlFor="field-next-step-input" className="block text-sm font-medium text-gray-500">
                Next Step
              </label>
              {isEditing ? (
                <input
                  id="field-next-step-input"
                  data-testid="field-next-step-input"
                  type="text"
                  value={editData.next_step ?? ""}
                  onChange={(e) =>
                    handleFieldChange("next_step", e.target.value)
                  }
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
                />
              ) : (
                <p
                  data-testid="field-next-step"
                  className="mt-1 text-sm text-gray-900"
                >
                  {data.next_step || (
                    <span className="text-gray-400">—</span>
                  )}
                </p>
              )}
            </div>

            {/* Red flags (rule-based JD signals) */}
            {data.red_flags && data.red_flags.length > 0 && (
              <div className="mt-4">
                <div className="block text-sm font-medium text-gray-500">
                  Red Flags
                </div>
                <div className="mt-2">
                  <RedFlagBadge
                    flags={data.red_flags}
                    mode="expanded"
                    testId="red-flags-detail"
                  />
                </div>
              </div>
            )}

            {/* Dimensional score breakdown (radar chart) */}
            {scoreData?.dimensional_scores && (
              <div className="mt-4">
                <div className="block text-sm font-medium text-gray-500">
                  Score Breakdown
                </div>
                <div className="mt-2">
                  <ScoreRadarChart scores={scoreData.dimensional_scores} />
                </div>
              </div>
            )}

            {/* ATS keyword checklist */}
            {scoreData?.ats_keywords && scoreData.ats_keywords.length > 0 && (
              <div className="mt-4">
                <div className="block text-sm font-medium text-gray-500">
                  ATS Keywords
                </div>
                <div className="mt-2">
                  <ATSKeywordChecklist keywords={scoreData.ats_keywords} />
                </div>
              </div>
            )}
          </div>

          {/* Dates */}
          <div className="rounded-lg border bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold text-gray-900">
              Timeline
            </h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <DateField
                label="Created"
                value={data.created_at}
                testId="field-created-at"
              />
              <DateField
                label="Updated"
                value={data.updated_at}
                testId="field-updated-at"
              />
              <DateField
                label="Applied"
                value={data.date_applied}
                testId="field-date-applied"
              />
            </div>
          </div>

          {/* Calendar */}
          <CalendarSection
            applicationId={applicationId}
            profileId={data.profile_id}
            company={data.company}
            role={data.role}
          />

          {/* Interview Prep */}
          <InterviewPrepSection
            applicationId={applicationId}
            profileId={data.profile_id}
          />

          {/* STAR Stories */}
          <StarStoriesSection
            applicationId={applicationId}
            profileId={data.profile_id}
          />
        </div>

        {/* Sidebar: Materials + Follow-ups + Activity log */}
        <div className="space-y-6">
          {/* Materials / Application Packages */}
          {(data.packages?.length ?? 0) > 0 && (
            <div data-testid="materials-section" className="rounded-lg border bg-white p-6 shadow-sm">
              <h2 className="mb-4 text-lg font-semibold text-gray-900">
                Materials
              </h2>
              <div data-testid="materials-list" className="space-y-3">
                {data.packages.map((pkg) => (
                  <div
                    key={pkg.id}
                    data-testid={`material-${pkg.id}`}
                    className="flex items-start gap-3 rounded-md border border-gray-200 p-3"
                  >
                    <div className="flex-shrink-0 mt-0.5">
                      {pkg.package_type === "full" ? (
                        <FolderOpen className="h-5 w-5 text-blue-500" />
                      ) : (
                        <FileText className="h-5 w-5 text-gray-400" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {pkg.package_name}
                      </p>
                      <p className="text-xs text-gray-500 truncate">
                        {pkg.file_path}
                      </p>
                      <span className="mt-1 inline-block rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600 capitalize">
                        {pkg.package_type}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Follow-ups */}
          <FollowUpSection
            applicationId={applicationId}
            followUps={data.follow_ups ?? []}
          />

          {/* Activity log */}
          <div className="rounded-lg border bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">
            Activity Log
          </h2>
          {data.activity_log.length === 0 ? (
            <p
              data-testid="activity-log-empty"
              className="text-sm text-gray-400"
            >
              No activity yet
            </p>
          ) : (
            <div
              data-testid="activity-log"
              className="space-y-4"
            >
              {data.activity_log.map((entry) => (
                <div
                  key={entry.id}
                  data-testid={`activity-entry-${entry.id}`}
                  className="border-l-2 border-gray-200 pl-3"
                >
                  <p className="text-sm font-medium text-gray-900 capitalize">
                    {entry.action.replace(/_/g, " ")}
                  </p>
                  {entry.details && (
                    <p className="mt-0.5 text-xs text-gray-600">
                      {entry.details}
                    </p>
                  )}
                  <div className="mt-1 flex items-center gap-1 text-xs text-gray-400">
                    <Clock className="h-3 w-3" />
                    {formatDate(entry.created_at)}
                    {entry.source && (
                      <span className="ml-2 rounded bg-gray-100 px-1.5 py-0.5 text-gray-500">
                        {entry.source}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
          </div>
        </div>
      </div>
    </section>
  );
}

// ---- Helper Components ----

function FieldRow({
  label,
  value,
  isEditing,
  testId,
  inputType = "text",
  onChange,
  renderDisplay,
}: Readonly<{
  label: string;
  value: string;
  isEditing: boolean;
  testId: string;
  inputType?: string;
  onChange?: (value: string) => void;
  renderDisplay?: (value: string) => React.ReactNode;
}>) {
  return (
    <div>
      <label htmlFor={`${testId}-input`} className="block text-sm font-medium text-gray-500">
        {label}
      </label>
      {isEditing && onChange ? (
        <input
          id={`${testId}-input`}
          data-testid={`${testId}-input`}
          type={inputType}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
          step={inputType === "number" ? "0.1" : undefined}
          min={inputType === "number" ? "0" : undefined}
          max={inputType === "number" ? "10" : undefined}
        />
      ) : renderDisplay ? (
        <div data-testid={testId} className="mt-1 text-sm text-gray-900">
          {renderDisplay(value)}
        </div>
      ) : (
        <p data-testid={testId} className="mt-1 text-sm text-gray-900">
          {value || <span className="text-gray-400">—</span>}
        </p>
      )}
    </div>
  );
}

function DateField({
  label,
  value,
  testId,
}: Readonly<{
  label: string;
  value: string | null;
  testId: string;
}>) {
  return (
    <div>
      <span className="block text-sm font-medium text-gray-500">
        {label}
      </span>
      <p data-testid={testId} className="mt-1 text-sm text-gray-900">
        {value ? formatDate(value) : <span className="text-gray-400">—</span>}
      </p>
    </div>
  );
}

function formatDate(iso: string): string {
  try {
    const date = new Date(iso);
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
