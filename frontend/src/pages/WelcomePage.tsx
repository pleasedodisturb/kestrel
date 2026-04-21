/**
 * WelcomePage -- full-page onboarding flow with three screens:
 *   1. Welcome intro with "Get Started" CTA
 *   2. Six Typeform-style profile questions (one per screen)
 *   3. Post-onboarding summary with checklist, AI nudge, and Pipeline CTA
 *
 * Implements decisions D-01 through D-08 from 04-CONTEXT.md.
 * Uses backend onboarding status API for resume-from-last-step (D-05).
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Check, Circle, Pencil } from "lucide-react";
import { StepProgress } from "@/components/StepProgress";
import { useOnboardingStatus } from "@/hooks/useOnboarding";
import { useProfile } from "@/hooks/useProfiles";
import { DEFAULT_PROFILE_ID, patchOnboardingStep, resetOnboarding } from "@/api/onboarding";
import { updateProfile } from "@/api/profiles";
import { createSkill } from "@/api/skills";

// ---------------------------------------------------------------------------
// Step definitions (PROF-04 -- same questions as CLI wizard)
// ---------------------------------------------------------------------------

const WELCOME_STEPS = [
  {
    key: "name",
    field: "name",
    question: "What's your name?",
    helper: null,
    type: "text" as const,
  },
  {
    key: "location",
    field: "location",
    question: "Where are you based?",
    helper: null,
    type: "text" as const,
  },
  {
    key: "job_family",
    field: "job_family",
    question: "What roles are you targeting?",
    helper: "Separate multiple roles with commas",
    type: "text" as const,
  },
  {
    key: "salary_range",
    field: "salary_range",
    question: "What's your target salary range?",
    helper: null,
    type: "salary" as const,
  },
  {
    key: "skills",
    field: "skills",
    question: "What are your key skills?",
    helper: "Separate skills with commas",
    type: "text" as const,
  },
  {
    key: "experience_level",
    field: "experience_level",
    question: "What's your experience level?",
    helper: null,
    type: "radio" as const,
  },
] as const;

const EXPERIENCE_OPTIONS = ["Entry", "Mid", "Senior", "Lead/Principal"];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

type Screen = "welcome" | "step" | "summary";

export function WelcomePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: status } = useOnboardingStatus();
  const { data: profile } = useProfile(DEFAULT_PROFILE_ID);

  // Core state
  const [screen, setScreen] = useState<Screen>("welcome");
  const [stepIndex, setStepIndex] = useState(0);
  const [fieldValue, setFieldValue] = useState("");
  const [salaryMin, setSalaryMin] = useState("");
  const [salaryMax, setSalaryMax] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [completedSteps, setCompletedSteps] = useState<Record<string, string>>(
    {},
  );
  const [skippedSteps, setSkippedSteps] = useState<Set<string>>(new Set());
  const skipResumeRef = useRef(false);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [editSaving, setEditSaving] = useState(false);

  // Focus management (accessibility)
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    inputRef.current?.focus();
  }, [stepIndex]);

  // ---------------------------------------------------------------------------
  // Resume logic (D-05): determine initial screen from backend status
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!status) return;
    if (skipResumeRef.current) return;

    if (status.welcome_completed_at) {
      setScreen("summary");
    } else if (status.profile_started_at) {
      // Resume at the first step whose profile field is empty (D-05).
      // If a user skipped a field, they'll see it again (one-click re-skip).
      if (profile) {
        const profileData: Record<string, unknown> = profile;
        const resumeIndex = WELCOME_STEPS.findIndex((step) => {
          const val = profileData[step.field];
          return val === null || val === undefined || val === "";
        });
        // If all fields are filled, go to last step (it will finish onboarding)
        setStepIndex(resumeIndex >= 0 ? resumeIndex : WELCOME_STEPS.length - 1);
      }
      setScreen("step");
    }
    // Otherwise stay on welcome screen
  }, [status, profile]);

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  const currentStep = WELCOME_STEPS[stepIndex];

  const markProfileStarted = useCallback(async () => {
    try {
      await patchOnboardingStep(DEFAULT_PROFILE_ID, "profile_started");
    } catch {
      // Non-blocking: step tracking is best-effort
    }
  }, []);

  const finishOnboarding = useCallback(async () => {
    try {
      await patchOnboardingStep(DEFAULT_PROFILE_ID, "profile_completed");
      await patchOnboardingStep(DEFAULT_PROFILE_ID, "demo_seeded");
      await patchOnboardingStep(DEFAULT_PROFILE_ID, "welcome_completed");
      await queryClient.invalidateQueries({
        queryKey: ["onboarding-status"],
      });
    } catch {
      // Non-blocking: step tracking is best-effort
    }
    setScreen("summary");
  }, [queryClient]);

  const handleNext = useCallback(async () => {
    setSaving(true);
    setError(null);

    try {
      // Determine the value to save
      let value = "";
      if (currentStep.type === "salary") {
        if (salaryMin || salaryMax) {
          value = `${salaryMin}-${salaryMax}`;
        }
      } else {
        value = fieldValue.trim();
      }

      // Save the field value
      if (value) {
        if (currentStep.key === "skills") {
          // Skills go to the skills table as individual records
          const skillNames = value
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean);
          for (const skillName of skillNames) {
            await createSkill({
              profile_id: DEFAULT_PROFILE_ID,
              name: skillName,
              category: "technical",
              evidence_source: "onboarding",
            });
          }
        } else {
          await updateProfile(DEFAULT_PROFILE_ID, {
            [currentStep.field]: value,
          });
        }

        setCompletedSteps((prev) => ({ ...prev, [currentStep.key]: value }));
      } else {
        // Empty value treated as skip
        setSkippedSteps((prev) => new Set(prev).add(currentStep.key));
      }

      // Advance or finish
      if (stepIndex === WELCOME_STEPS.length - 1) {
        await finishOnboarding();
      } else {
        setStepIndex((prev) => prev + 1);
        setFieldValue("");
        setSalaryMin("");
        setSalaryMax("");
      }
    } catch {
      setError(
        "Couldn't save your answer. Check your connection and try again.",
      );
    } finally {
      setSaving(false);
    }
  }, [
    currentStep,
    fieldValue,
    salaryMin,
    salaryMax,
    stepIndex,
    finishOnboarding,
  ]);

  const handleSkip = useCallback(async () => {
    setSkippedSteps((prev) => new Set(prev).add(currentStep.key));

    if (stepIndex === WELCOME_STEPS.length - 1) {
      await finishOnboarding();
    } else {
      setStepIndex((prev) => prev + 1);
      setFieldValue("");
      setSalaryMin("");
      setSalaryMax("");
    }
  }, [currentStep, stepIndex, finishOnboarding]);

  const handleBack = useCallback(() => {
    if (stepIndex > 0) {
      const prevStep = WELCOME_STEPS[stepIndex - 1];
      const saved = completedSteps[prevStep.key] ?? "";
      if (prevStep.type === "salary" && saved.includes("-")) {
        const [min, max] = saved.split("-");
        setSalaryMin(min ?? "");
        setSalaryMax(max ?? "");
        setFieldValue("");
      } else {
        setFieldValue(saved);
        setSalaryMin("");
        setSalaryMax("");
      }
      setStepIndex((prev) => prev - 1);
      setError(null);
    }
  }, [stepIndex, completedSteps]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !saving) {
        void handleNext();
      }
    },
    [handleNext, saving],
  );

  // ---------------------------------------------------------------------------
  // Welcome screen (D-01, D-02)
  // ---------------------------------------------------------------------------

  if (screen === "welcome") {
    return (
      <div
        className="flex min-h-screen flex-col items-center justify-center bg-[hsl(var(--background))]"
        data-testid="welcome-page"
      >
        <h1 className="text-3xl font-semibold text-[hsl(var(--foreground))]">
          Welcome to Kestrel
        </h1>
        <p className="mt-4 max-w-md text-center text-base text-[hsl(var(--muted-foreground))]">
          Let&apos;s set up your profile so Kestrel can score jobs that match
          you. Takes about 2 minutes.
        </p>
        <button
          onClick={() => {
            setScreen("step");
            void markProfileStarted();
          }}
          className="mt-8 rounded-md bg-[hsl(var(--primary))] px-6 py-3 text-sm font-medium text-[hsl(var(--primary-foreground))] hover:opacity-90"
          data-testid="get-started-btn"
        >
          Get Started
        </button>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Summary screen (D-06, D-07, D-08)
  // ---------------------------------------------------------------------------

  if (screen === "summary") {
    return (
      <div
        className="flex min-h-screen flex-col items-center justify-center bg-[hsl(var(--background))]"
        data-testid="welcome-page"
      >
        <div className="w-full max-w-[480px] px-4">
          <h1 className="text-2xl font-semibold text-[hsl(var(--foreground))]">
            You&apos;re all set
          </h1>
          <p className="mt-2 text-base text-[hsl(var(--muted-foreground))]">
            Here&apos;s what we configured. You can update anything later in
            Settings.
          </p>

          <ul className="mt-6 space-y-3" data-testid="summary-checklist">
            {WELCOME_STEPS.map((step) => {
              const label = step.question
                .replace("What's your ", "")
                .replace("What are your ", "")
                .replace("Where are you ", "")
                .replace("?", "");
              const value = completedSteps[step.key];
              const isSkipped = skippedSteps.has(step.key) || !value;
              const isEditing = editingKey === step.key;

              if (isEditing) {
                return (
                  <li key={step.key} className="flex items-start gap-3">
                    <Pencil className="mt-1.5 h-4 w-4 shrink-0 text-[hsl(var(--primary))]" />
                    <div className="flex-1">
                      <p className="mb-1 text-xs font-medium text-[hsl(var(--muted-foreground))]">{label}</p>
                      {step.type === "radio" ? (
                        <div className="flex flex-wrap gap-2">
                          {EXPERIENCE_OPTIONS.map((opt) => (
                            <button
                              key={opt}
                              onClick={() => setEditValue(opt)}
                              className={`rounded-md border px-3 py-1.5 text-sm ${editValue === opt ? "border-[hsl(var(--primary))] bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]" : "border-[hsl(var(--border))] text-[hsl(var(--foreground))] hover:bg-[hsl(var(--secondary))]"}`}
                            >
                              {opt}
                            </button>
                          ))}
                        </div>
                      ) : (
                        <input
                          autoFocus
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Escape") setEditingKey(null);
                          }}
                          className="w-full rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-1.5 text-sm text-[hsl(var(--foreground))] focus:outline-none focus:ring-2 focus:ring-[hsl(var(--ring))]"
                        />
                      )}
                      <div className="mt-2 flex gap-2">
                        <button
                          disabled={editSaving}
                          onClick={async () => {
                            const trimmed = editValue.trim();
                            if (!trimmed) return;
                            setEditSaving(true);
                            try {
                              if (step.key === "skills") {
                                const names = trimmed.split(",").map((s) => s.trim()).filter(Boolean);
                                for (const name of names) {
                                  await createSkill({ profile_id: DEFAULT_PROFILE_ID, name, category: "technical", evidence_source: "onboarding" });
                                }
                              } else {
                                await updateProfile(DEFAULT_PROFILE_ID, { [step.field]: trimmed });
                              }
                              setCompletedSteps((prev) => ({ ...prev, [step.key]: trimmed }));
                              setSkippedSteps((prev) => { const next = new Set(prev); next.delete(step.key); return next; });
                              setEditingKey(null);
                            } finally {
                              setEditSaving(false);
                            }
                          }}
                          className="rounded-md bg-[hsl(var(--primary))] px-3 py-1 text-xs font-medium text-[hsl(var(--primary-foreground))] hover:opacity-90 disabled:opacity-50"
                        >
                          {editSaving ? "Saving..." : "Save"}
                        </button>
                        <button
                          onClick={() => setEditingKey(null)}
                          className="rounded-md border border-[hsl(var(--border))] px-3 py-1 text-xs font-medium text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--secondary))]"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  </li>
                );
              }

              return (
                <li
                  key={step.key}
                  className="group flex cursor-pointer items-start gap-3 rounded-md px-2 py-1.5 transition-colors hover:bg-[hsl(var(--secondary))]"
                  onClick={() => { setEditingKey(step.key); setEditValue(value ?? ""); }}
                >
                  {isSkipped ? (
                    <Circle className="mt-0.5 h-5 w-5 shrink-0 text-[hsl(var(--muted-foreground))]" />
                  ) : (
                    <Check className="mt-0.5 h-5 w-5 shrink-0 text-green-600" />
                  )}
                  <span className={`flex-1 text-sm ${isSkipped ? "text-[hsl(var(--muted-foreground))]" : "text-[hsl(var(--foreground))]"}`}>
                    {label}{value ? `: ${value}` : " — skipped"}
                  </span>
                  <Pencil className="mt-0.5 h-4 w-4 shrink-0 text-[hsl(var(--muted-foreground))] opacity-0 transition-opacity group-hover:opacity-100" />
                </li>
              );
            })}
          </ul>

          {/* AI Provider Nudge Card (D-07 -- summary screen only) */}
          <div
            className="mt-8 rounded-lg border border-[hsl(var(--border))] p-6"
            data-testid="ai-provider-nudge"
          >
            <h2 className="text-base font-semibold text-[hsl(var(--foreground))]">
              Unlock full AI scoring
            </h2>
            <p className="mt-2 text-sm text-[hsl(var(--muted-foreground))]">
              Connect an AI provider to get personalized job scores. Kestrel
              works with OpenRouter, Together.ai, and local models via Ollama.
            </p>
            <a
              href="/settings"
              className="mt-3 inline-block text-sm text-[hsl(var(--muted-foreground))] underline"
            >
              Configure in Settings
            </a>
          </div>

          {/* Primary CTA (D-08) */}
          <button
            onClick={() => navigate("/")}
            className="mt-8 w-full rounded-md bg-[hsl(var(--primary))] px-6 py-3 text-sm font-medium text-[hsl(var(--primary-foreground))] hover:opacity-90"
            data-testid="see-results-cta"
          >
            See your scored results
          </button>

          {/* End-of-onboarding feedback prompt (D-11) */}
          <p
            className="mt-4 text-center text-sm text-[hsl(var(--muted-foreground))]"
            data-testid="onboarding-feedback-prompt"
          >
            How was setup?{" "}
            <a
              href="https://github.com/pocketflow-ai/kestrel/issues/new?title=%5BOnboarding+Feedback%5D&labels=feedback&body=%23%23+Onboarding+Feedback%0A%0AHow+was+the+setup+experience%3F+What+could+be+better%3F"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-[hsl(var(--foreground))]"
            >
              Share your feedback
            </a>
          </p>

          {/* Restart onboarding (keeps profile data) */}
          <button
            onClick={async () => {
              skipResumeRef.current = true;
              await resetOnboarding(DEFAULT_PROFILE_ID);
              await queryClient.invalidateQueries({ queryKey: ["onboarding-status"] });
              setScreen("welcome");
              setStepIndex(0);
              setFieldValue("");
              setCompletedSteps({});
              setSkippedSteps(new Set());
            }}
            className="mt-2 text-sm text-[hsl(var(--muted-foreground))] underline hover:text-[hsl(var(--foreground))]"
            data-testid="restart-onboarding"
          >
            Restart onboarding
          </button>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Step screen (D-03, D-04)
  // ---------------------------------------------------------------------------

  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center bg-[hsl(var(--background))]"
      data-testid="welcome-page"
    >
      <StepProgress current={stepIndex + 1} total={WELCOME_STEPS.length} />

      <div className="mt-16 w-full max-w-[480px] px-4">
        <h1 className="text-2xl font-semibold text-[hsl(var(--foreground))]">
          {currentStep.question}
        </h1>
        {currentStep.helper && (
          <p className="mt-2 text-sm text-[hsl(var(--muted-foreground))]">
            {currentStep.helper}
          </p>
        )}

        <div className="mt-8">
          {currentStep.type === "text" && (
            <input
              ref={inputRef}
              type="text"
              value={fieldValue}
              onChange={(e) => setFieldValue(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] px-4 py-3 text-base text-[hsl(var(--foreground))] focus:outline-none focus:ring-2 focus:ring-[hsl(var(--primary))]"
              autoFocus
            />
          )}

          {currentStep.type === "salary" && (
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <label className="mb-1 block text-sm text-[hsl(var(--muted-foreground))]">
                  Min ($)
                </label>
                <input
                  ref={inputRef}
                  type="number"
                  placeholder="60000"
                  value={salaryMin}
                  onChange={(e) => setSalaryMin(e.target.value)}
                  onKeyDown={handleKeyDown}
                  className="w-full rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] px-4 py-3 text-base text-[hsl(var(--foreground))] focus:outline-none focus:ring-2 focus:ring-[hsl(var(--primary))]"
                  autoFocus
                />
              </div>
              <span className="mt-6 text-[hsl(var(--muted-foreground))]">
                &ndash;
              </span>
              <div className="flex-1">
                <label className="mb-1 block text-sm text-[hsl(var(--muted-foreground))]">
                  Max ($)
                </label>
                <input
                  type="number"
                  placeholder="120000"
                  value={salaryMax}
                  onChange={(e) => setSalaryMax(e.target.value)}
                  onKeyDown={handleKeyDown}
                  className="w-full rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] px-4 py-3 text-base text-[hsl(var(--foreground))] focus:outline-none focus:ring-2 focus:ring-[hsl(var(--primary))]"
                />
              </div>
            </div>
          )}

          {currentStep.type === "radio" && (
            <div className="space-y-3">
              {EXPERIENCE_OPTIONS.map((opt) => (
                <label
                  key={opt}
                  className={`flex cursor-pointer items-center gap-3 rounded-md border px-4 py-3 transition-colors ${
                    fieldValue === opt
                      ? "border-[hsl(var(--primary))] bg-[hsl(var(--secondary))]"
                      : "border-[hsl(var(--border))] hover:bg-[hsl(var(--secondary))]"
                  }`}
                >
                  <input
                    type="radio"
                    name="experience_level"
                    value={opt}
                    checked={fieldValue === opt}
                    onChange={(e) => setFieldValue(e.target.value)}
                    className="h-4 w-4 accent-[hsl(var(--primary))]"
                  />
                  <span className="text-base text-[hsl(var(--foreground))]">
                    {opt}
                  </span>
                </label>
              ))}
            </div>
          )}
        </div>

        {error && (
          <p
            className="mt-2 text-sm text-red-600"
            aria-live="polite"
            role="alert"
          >
            {error}
          </p>
        )}

        <div className="mt-8 flex items-center justify-between">
          <button
            onClick={handleBack}
            disabled={stepIndex === 0}
            className="rounded-md border border-[hsl(var(--border))] px-5 py-2.5 text-sm font-medium text-[hsl(var(--muted-foreground))] transition-colors hover:bg-[hsl(var(--secondary))] disabled:opacity-40"
          >
            Back
          </button>
          <button
            onClick={() => void handleSkip()}
            className="rounded-md border border-[hsl(var(--border))] px-5 py-2.5 text-sm font-medium text-[hsl(var(--muted-foreground))] transition-colors hover:bg-[hsl(var(--secondary))]"
          >
            Skip
          </button>
          <button
            onClick={() => void handleNext()}
            disabled={saving}
            className="rounded-md bg-[hsl(var(--primary))] px-6 py-2.5 text-sm font-medium text-[hsl(var(--primary-foreground))] transition-colors hover:opacity-90 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Next"}
          </button>
        </div>
      </div>
    </div>
  );
}
