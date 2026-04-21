/**
 * FeedbackButton -- persistent feedback button visible on all pages.
 *
 * Implements D-09 (pre-filled GitHub issue URL) and D-10 (small circular
 * icon button, bottom-right, tooltip on hover) from 05-CONTEXT.md.
 *
 * Opens a new GitHub issue with pre-filled template including system info.
 */

import { MessageCircle } from "lucide-react";
import { useTour } from "@/components/TourProvider";

/** GitHub repo for issue creation */
const GITHUB_REPO = "pocketflow-ai/kestrel";

/**
 * Build a pre-filled GitHub new issue URL with system info.
 * Collects browser info (OS, Kestrel version from meta tag if available).
 */
function buildFeedbackUrl(): string {
  const os = navigator.platform || "Unknown OS";
  const browser = navigator.userAgent
    ? `${navigator.userAgent.split(" ").slice(-1)[0]}`
    : "Unknown browser";
  const currentPage = window.location.pathname;

  const body = [
    "## Feedback",
    "",
    "_Describe your feedback, suggestion, or issue here._",
    "",
    "---",
    "## System Info (auto-filled)",
    "",
    `- **Page:** ${currentPage}`,
    `- **OS:** ${os}`,
    `- **Browser:** ${browser}`,
    `- **Timestamp:** ${new Date().toISOString()}`,
  ].join("\n");

  const params = new URLSearchParams({
    title: "[Feedback] ",
    body,
    labels: "feedback",
  });

  return `https://github.com/${GITHUB_REPO}/issues/new?${params.toString()}`;
}

export function FeedbackButton() {
  const { isActive } = useTour();

  // Hide feedback button during active tour to avoid z-index conflicts (Pitfall 4)
  if (isActive) return null;

  return (
    <a
      href={buildFeedbackUrl()}
      target="_blank"
      rel="noopener noreferrer"
      className="group fixed bottom-6 right-6 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-gray-900 text-white shadow-lg transition-transform hover:scale-105 hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:ring-offset-2"
      aria-label="Send feedback"
      data-testid="feedback-button"
    >
      <MessageCircle className="h-5 w-5" />
      {/* Tooltip on hover */}
      <span className="pointer-events-none absolute bottom-full right-0 mb-2 whitespace-nowrap rounded bg-gray-900 px-3 py-1.5 text-xs text-white opacity-0 shadow-md transition-opacity group-hover:opacity-100">
        Send feedback
      </span>
    </a>
  );
}
