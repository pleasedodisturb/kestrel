/**
 * TourProvider -- React Context provider for the interactive guided tour.
 *
 * Manages tour state (step progression, auto-launch, cross-page navigation)
 * and renders TourOverlay + TourTooltip when active.
 *
 * Implements D-01 (auto-launch after onboarding), D-02 (Pipeline -> Discovery -> Scoring path),
 * D-04 (custom implementation, no Shepherd.js), D-06 (backend completion persistence).
 *
 * @see 05-CONTEXT.md for decision rationale
 * @see 05-UI-SPEC.md for tour step definitions and copywriting
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
  useOnboardingStatus,
  usePatchOnboardingStep,
} from "@/hooks/useOnboarding";
import { DEFAULT_PROFILE_ID } from "@/api/onboarding";
import { TourOverlay } from "@/components/TourOverlay";
import { TourTooltip } from "@/components/TourTooltip";

/* ---------- Types ---------- */

export interface TourStep {
  page: string;
  targetSelector: string;
  heading: string;
  body: string;
}

export interface TourContextValue {
  isActive: boolean;
  currentStep: number;
  totalSteps: number;
  currentStepData: TourStep | null;
  targetRect: DOMRect | null;
  next: () => void;
  skip: () => void;
}

/* ---------- Tour Steps (from 05-UI-SPEC.md) ---------- */

// eslint-disable-next-line react-refresh/only-export-components -- co-located constant used by tests and TourTooltip
export const TOUR_STEPS: TourStep[] = [
  {
    page: "/",
    targetSelector: "[data-testid='kanban-board']",
    heading: "Your job pipeline",
    body: "Drag jobs between columns to track your progress. New matches from Discovery land here.",
  },
  {
    page: "/",
    targetSelector: "[data-testid='kanban-card']:first-child",
    heading: "Job cards",
    body: "Each card shows the match score, company, and role. Click any card for the full breakdown.",
  },
  {
    page: "/discovery",
    targetSelector: "input[placeholder*='Search']",
    heading: "Find new opportunities",
    body: "Search by role, location, or company. Kestrel scores every result against your profile.",
  },
  {
    page: "/discovery",
    targetSelector: "[data-testid^='grade-badge-']",
    heading: "Match scores",
    body: "Scores show how well a job fits your profile. A+ means strong alignment across skills, location, and salary.",
  },
  {
    page: "/",
    targetSelector: "[data-testid^='grade-badge-']",
    heading: "Track what matters",
    body: "Focus on high-scoring roles. Your pipeline is your personal shortlist.",
  },
];

/* ---------- Context ---------- */

const TourContext = createContext<TourContextValue | null>(null);

/**
 * Hook to consume tour context. Returns a default inactive state when used
 * outside of TourProvider, so consumers do not need null checks.
 */
// eslint-disable-next-line react-refresh/only-export-components -- co-located hook consumed by TourTooltip
export function useTour(): TourContextValue {
  const ctx = useContext(TourContext);
  if (!ctx) {
    return {
      isActive: false,
      currentStep: 0,
      totalSteps: TOUR_STEPS.length,
      currentStepData: null,
      targetRect: null,
      next: () => {},
      skip: () => {},
    };
  }
  return ctx;
}

/* ---------- Provider ---------- */

interface TourProviderProps {
  children: ReactNode;
}

/** Max number of requestAnimationFrame retries when locating a target element. */
const MAX_RETRIES = 10;
/** Delay between retries (ms). */
const RETRY_INTERVAL = 100;
/** Delay before auto-launching tour after onboarding completion (ms). D-01. */
const AUTO_LAUNCH_DELAY = 500;

export function TourProvider({ children }: TourProviderProps) {
  const [isActive, setIsActive] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null);

  const navigate = useNavigate();
  const location = useLocation();
  const { data: onboardingStatus } = useOnboardingStatus();
  const patchStep = usePatchOnboardingStep();

  /** Ensures auto-launch fires only once per provider mount. */
  const hasAutoLaunched = useRef(false);

  /* ---------- Auto-launch (D-01) ---------- */

  useEffect(() => {
    if (hasAutoLaunched.current) return;
    if (!onboardingStatus) return;
    if (!onboardingStatus.welcome_completed_at) return;
    if (onboardingStatus.tour_completed_at) return;

    hasAutoLaunched.current = true;
    const timer = setTimeout(() => {
      setIsActive(true);
    }, AUTO_LAUNCH_DELAY);

    return () => clearTimeout(timer);
  }, [onboardingStatus]);

  /* ---------- Completion / Skip ---------- */

  const completeTour = useCallback(() => {
    setIsActive(false);
    setCurrentStep(0);
    setTargetRect(null);
    patchStep.mutate({ profileId: DEFAULT_PROFILE_ID, step: "tour_completed" });
  }, [patchStep]);

  const skip = useCallback(() => {
    completeTour();
  }, [completeTour]);

  /* ---------- Next step ---------- */

  const next = useCallback(() => {
    const nextIndex = currentStep + 1;
    if (nextIndex >= TOUR_STEPS.length) {
      completeTour();
      return;
    }

    const nextStepData = TOUR_STEPS[nextIndex];
    const currentStepPage = TOUR_STEPS[currentStep].page;

    if (nextStepData.page !== currentStepPage) {
      navigate(nextStepData.page);
    }

    setCurrentStep(nextIndex);
  }, [currentStep, navigate, completeTour]);

  /* ---------- Target rect calculation with retry loop (T-05-05 mitigation) ---------- */

  useEffect(() => {
    if (!isActive) {
      setTargetRect(null); // eslint-disable-line react-hooks/set-state-in-effect -- guard reset, not cascading
      return;
    }

    const step = TOUR_STEPS[currentStep];
    if (!step) return;

    let attempts = 0;
    let rafId: number | null = null;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    function tryFindTarget() {
      const el = document.querySelector(step.targetSelector);
      if (el) {
        setTargetRect(el.getBoundingClientRect());
        return;
      }

      attempts += 1;
      if (attempts < MAX_RETRIES) {
        timeoutId = setTimeout(() => {
          rafId = requestAnimationFrame(tryFindTarget);
        }, RETRY_INTERVAL);
      } else {
        // Target not found after max retries -- skip this step gracefully
        setTargetRect(null);
      }
    }

    // Small initial delay to let page render after potential navigation
    rafId = requestAnimationFrame(tryFindTarget);

    return () => {
      if (rafId !== null) cancelAnimationFrame(rafId);
      if (timeoutId !== null) clearTimeout(timeoutId);
    };
  }, [isActive, currentStep, location.pathname]);

  /* ---------- Recalculate target rect on scroll/resize ---------- */

  useEffect(() => {
    if (!isActive) return;

    let rafId: number | null = null;

    function recalculate() {
      if (rafId !== null) return; // throttle
      rafId = requestAnimationFrame(() => {
        rafId = null;
        const step = TOUR_STEPS[currentStep];
        if (!step) return;
        const el = document.querySelector(step.targetSelector);
        if (el) {
          setTargetRect(el.getBoundingClientRect());
        }
      });
    }

    window.addEventListener("scroll", recalculate, { passive: true });
    window.addEventListener("resize", recalculate, { passive: true });

    return () => {
      window.removeEventListener("scroll", recalculate);
      window.removeEventListener("resize", recalculate);
      if (rafId !== null) cancelAnimationFrame(rafId);
    };
  }, [isActive, currentStep]);

  /* ---------- Context value ---------- */

  const currentStepData = isActive ? (TOUR_STEPS[currentStep] ?? null) : null;

  const contextValue: TourContextValue = {
    isActive,
    currentStep,
    totalSteps: TOUR_STEPS.length,
    currentStepData,
    targetRect,
    next,
    skip,
  };

  return (
    <TourContext.Provider value={contextValue}>
      {children}
      {isActive && <TourOverlay />}
      {isActive && <TourTooltip />}
    </TourContext.Provider>
  );
}
