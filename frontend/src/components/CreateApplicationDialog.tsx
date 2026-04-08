/**
 * CreateApplicationDialog — modal dialog for creating a new application.
 *
 * Validates required fields (company, role) before submission.
 * Returns 422 from API on invalid input → shown as inline errors.
 */

import { useState, useCallback } from "react";
import { useCreateApplication } from "@/hooks/useApplications";
import { X, Plus } from "lucide-react";

interface CreateApplicationDialogProps {
  open: boolean;
  onClose: () => void;
}

export function CreateApplicationDialog({
  open,
  onClose,
}: CreateApplicationDialogProps) {
  const createMutation = useCreateApplication();

  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [url, setUrl] = useState("");
  const [source, setSource] = useState("");
  const [salaryRange, setSalaryRange] = useState("");
  const [notes, setNotes] = useState("");
  const [fitScore, setFitScore] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});

  const resetForm = useCallback(() => {
    setCompany("");
    setRole("");
    setUrl("");
    setSource("");
    setSalaryRange("");
    setNotes("");
    setFitScore("");
    setErrors({});
    createMutation.reset();
  }, [createMutation]);

  const validate = useCallback((): boolean => {
    const newErrors: Record<string, string> = {};
    if (!company.trim()) newErrors.company = "Company is required";
    if (!role.trim()) newErrors.role = "Role is required";
    if (fitScore && (isNaN(Number(fitScore)) || Number(fitScore) < 0 || Number(fitScore) > 10)) {
      newErrors.fit_score = "Score must be between 0 and 10";
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [company, role, fitScore]);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (!validate()) return;

      createMutation.mutate(
        {
          company: company.trim(),
          role: role.trim(),
          url: url.trim() || undefined,
          source: source.trim() || undefined,
          salary_range: salaryRange.trim() || undefined,
          notes: notes.trim() || undefined,
          fit_score: fitScore ? Number(fitScore) : undefined,
        },
        {
          onSuccess: () => {
            resetForm();
            onClose();
          },
        },
      );
    },
    [company, role, url, source, salaryRange, notes, fitScore, validate, createMutation, resetForm, onClose],
  );

  const handleClose = useCallback(() => {
    resetForm();
    onClose();
  }, [resetForm, onClose]);

  if (!open) return null;

  return (
    <div
      data-testid="create-dialog-overlay"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={(e) => {
        if (e.target === e.currentTarget) handleClose();
      }}
    >
      <div
        data-testid="create-dialog"
        className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">
            New Application
          </h2>
          <button
            data-testid="create-dialog-close"
            onClick={handleClose}
            className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* API error */}
        {createMutation.isError && (
          <div
            data-testid="create-dialog-error"
            className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
          >
            {createMutation.error instanceof Error ? createMutation.error.message : String(createMutation.error)}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <FormField
            label="Company *"
            testId="create-company"
            value={company}
            onChange={setCompany}
            error={errors.company}
          />
          <FormField
            label="Role *"
            testId="create-role"
            value={role}
            onChange={setRole}
            error={errors.role}
          />
          <FormField
            label="URL"
            testId="create-url"
            value={url}
            onChange={setUrl}
            type="url"
          />
          <FormField
            label="Source"
            testId="create-source"
            value={source}
            onChange={setSource}
            placeholder="e.g., LinkedIn, referral, direct"
          />
          <FormField
            label="Salary Range"
            testId="create-salary"
            value={salaryRange}
            onChange={setSalaryRange}
            placeholder="e.g., 120-140k EUR"
          />
          <FormField
            label="Fit Score (0-10)"
            testId="create-score"
            value={fitScore}
            onChange={setFitScore}
            type="number"
            error={errors.fit_score}
          />
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Notes
            </label>
            <textarea
              data-testid="create-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              data-testid="create-cancel"
              onClick={handleClose}
              className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              data-testid="create-submit"
              disabled={createMutation.isPending}
              className="inline-flex items-center gap-1 rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-gray-800 disabled:opacity-50"
            >
              <Plus className="h-4 w-4" />
              {createMutation.isPending ? "Creating…" : "Create Application"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function FormField({
  label,
  testId,
  value,
  onChange,
  type = "text",
  placeholder,
  error,
}: {
  label: string;
  testId: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
  error?: string;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700">
        {label}
      </label>
      <input
        data-testid={testId}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        step={type === "number" ? "0.1" : undefined}
        min={type === "number" ? "0" : undefined}
        max={type === "number" ? "10" : undefined}
        className={cn(
          "mt-1 w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-1",
          error
            ? "border-red-300 focus:border-red-500 focus:ring-red-500"
            : "border-gray-300 focus:border-gray-500 focus:ring-gray-500",
        )}
      />
      {error && (
        <p data-testid={`${testId}-error`} className="mt-1 text-xs text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}

function cn(...classes: (string | boolean | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}
