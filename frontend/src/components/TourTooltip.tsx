/**
 * TourTooltip -- positioned tooltip with heading, body, and navigation buttons.
 *
 * Implements D-03 (minimal popover tooltip) and D-05 (WCAG 2.1 AA accessibility):
 * - Focus trap: Tab cycles between Skip and Next/Done buttons
 * - Escape: skips the entire tour
 * - aria-live region announces step changes
 * - Focus managed on step transitions
 *
 * @see 05-UI-SPEC.md Component Inventory > TourTooltip
 */

import { useEffect, useRef, useState } from "react";
import { useTour } from "@/components/TourProvider";

/** Offset from the target element edge (px). */
const TOOLTIP_GAP = 12;
/** Minimum margin from viewport edges (px). */
const VIEWPORT_MARGIN = 16;
/** Tooltip width (matches w-80 = 320px). */
const TOOLTIP_WIDTH = 320;

export function TourTooltip() {
  const {
    isActive,
    currentStep,
    totalSteps,
    currentStepData,
    targetRect,
    next,
    skip,
  } = useTour();

  const tooltipRef = useRef<HTMLDivElement>(null);
  const skipBtnRef = useRef<HTMLButtonElement>(null);
  const [position, setPosition] = useState<{ top: number; left: number }>({
    top: 0,
    left: 0,
  });
  const [opacity, setOpacity] = useState(0);

  /** Track step for aria-live: only announce after the first render. */
  const [announcement, setAnnouncement] = useState("");
  const prevStep = useRef<number>(-1);

  /* ---------- Position calculation ---------- */

  useEffect(() => {
    if (!targetRect || !tooltipRef.current) {
      setOpacity(0);
      return;
    }

    const tooltipHeight = tooltipRef.current.offsetHeight;
    const viewportHeight = window.innerHeight;

    // Prefer below target; fall back to above
    let top: number;
    if (targetRect.bottom + TOOLTIP_GAP + tooltipHeight < viewportHeight) {
      top = targetRect.bottom + TOOLTIP_GAP;
    } else {
      top = targetRect.top - tooltipHeight - TOOLTIP_GAP;
    }

    // Horizontally center on target, clamped to viewport
    let left = targetRect.left + targetRect.width / 2 - TOOLTIP_WIDTH / 2;
    left = Math.max(
      VIEWPORT_MARGIN,
      Math.min(left, window.innerWidth - TOOLTIP_WIDTH - VIEWPORT_MARGIN),
    );

    setPosition({ top, left });
    // Fade in after positioning
    requestAnimationFrame(() => setOpacity(1));
  }, [targetRect, currentStep]);

  /* ---------- Focus management ---------- */

  useEffect(() => {
    if (!isActive) return;
    // Focus the skip button when tooltip appears or step changes
    skipBtnRef.current?.focus();
  }, [isActive, currentStep]);

  /* ---------- Keyboard: focus trap + Escape (D-05) ---------- */

  useEffect(() => {
    if (!isActive) return;

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        skip();
        return;
      }

      if (e.key === "Tab") {
        e.preventDefault();
        const focusables =
          tooltipRef.current?.querySelectorAll<HTMLButtonElement>("button");
        if (!focusables?.length) return;

        const currentIdx = Array.from(focusables).indexOf(
          document.activeElement as HTMLButtonElement,
        );
        const nextIdx = e.shiftKey
          ? (currentIdx - 1 + focusables.length) % focusables.length
          : (currentIdx + 1) % focusables.length;
        focusables[nextIdx].focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isActive, skip]);

  /* ---------- aria-live announcements (Pitfall 5: no mount announce) ---------- */

  useEffect(() => {
    if (!isActive || !currentStepData) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- guard reset on inactive state, not cascading
      setAnnouncement("");
      return;
    }

    // Only announce when step actually changes (not on initial mount)
    if (prevStep.current !== -1 && prevStep.current !== currentStep) {
      setAnnouncement(
        `Step ${currentStep + 1} of ${totalSteps}: ${currentStepData.heading}`,
      );
    }
    prevStep.current = currentStep;
  }, [isActive, currentStep, totalSteps, currentStepData]);

  // Reset prevStep ref when tour deactivates
  useEffect(() => {
    if (!isActive) {
      prevStep.current = -1;
    }
  }, [isActive]);

  /* ---------- Render ---------- */

  if (!isActive || !currentStepData) return null;

  const isLastStep = currentStep === totalSteps - 1;

  return (
    <>
      {/* aria-live region for screen reader announcements */}
      <div aria-live="polite" className="sr-only" data-testid="tour-announcer">
        {announcement}
      </div>

      <div
        ref={tooltipRef}
        className="fixed z-50 w-80 rounded-lg border border-[hsl(var(--border))] bg-white p-4 shadow-lg transition-opacity duration-150"
        style={{ top: position.top, left: position.left, opacity }}
        data-testid="tour-tooltip"
        role="dialog"
        aria-label={currentStepData.heading}
      >
        <p className="text-sm font-semibold text-[hsl(var(--foreground))]">
          {currentStepData.heading}
        </p>
        <p className="mt-1 text-sm text-[hsl(var(--muted-foreground))]">
          {currentStepData.body}
        </p>

        <div className="mt-3 flex items-center justify-between">
          <button
            ref={skipBtnRef}
            onClick={skip}
            className="min-h-[44px] min-w-[44px] text-sm text-[hsl(var(--muted-foreground))] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--ring))]"
            data-testid="tour-skip"
          >
            Skip tour
          </button>

          <span
            className="text-sm text-[hsl(var(--muted-foreground))]"
            aria-hidden="true"
          >
            {currentStep + 1} of {totalSteps}
          </span>

          <button
            onClick={next}
            className="min-h-[44px] min-w-[44px] rounded-md bg-[hsl(var(--primary))] px-3 py-1.5 text-sm font-medium text-[hsl(var(--primary-foreground))] hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--ring))]"
            data-testid="tour-next"
          >
            {isLastStep ? "Done" : "Next"}
          </button>
        </div>
      </div>
    </>
  );
}
