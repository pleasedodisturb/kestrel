/**
 * TourOverlay -- full-viewport overlay with CSS clip-path cutout.
 *
 * Renders a semi-transparent scrim over the entire page with a rectangular
 * hole around the target element. Clicking the overlay advances the tour.
 *
 * Implements D-03 (minimal tooltips with highlight on target).
 *
 * @see 05-RESEARCH.md Pattern 2 for clip-path calculation
 */

import { useTour } from "@/components/TourProvider";

/**
 * Calculate a CSS clip-path polygon that covers the entire viewport
 * EXCEPT for a rectangular cutout around the target element.
 */
function calculateClipPath(targetRect: DOMRect, padding: number = 4): string {
  const { innerWidth: vw, innerHeight: vh } = window;
  const t = targetRect.top - padding;
  const r = targetRect.right + padding;
  const b = targetRect.bottom + padding;
  const l = targetRect.left - padding;

  return `polygon(
    0px 0px, 0px ${vh}px, ${l}px ${vh}px, ${l}px ${t}px,
    ${r}px ${t}px, ${r}px ${b}px, ${l}px ${b}px, ${l}px ${vh}px,
    ${vw}px ${vh}px, ${vw}px 0px
  )`;
}

export function TourOverlay() {
  const { targetRect, next } = useTour();

  const overlayStyle: React.CSSProperties = {
    backgroundColor: "rgba(0, 0, 0, 0.4)",
    pointerEvents: "auto",
    ...(targetRect ? { clipPath: calculateClipPath(targetRect) } : {}),
  };

  return (
    <>
      {/* Scrim with cutout */}
      <div
        className="fixed inset-0 z-40 transition-[clip-path] duration-200"
        style={overlayStyle}
        onClick={next}
        data-testid="tour-overlay"
        aria-hidden="true"
      />

      {/* Highlight ring around target */}
      {targetRect && (
        <div
          className="pointer-events-none fixed z-40 rounded-sm border-2 border-[hsl(var(--primary))]"
          style={{
            top: targetRect.top - 4,
            left: targetRect.left - 4,
            width: targetRect.width + 8,
            height: targetRect.height + 8,
          }}
          aria-hidden="true"
        />
      )}
    </>
  );
}
