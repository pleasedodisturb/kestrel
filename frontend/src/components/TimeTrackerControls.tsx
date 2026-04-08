/**
 * TimeTrackerControls — start/stop time tracking buttons for the Analytics page header.
 *
 * Shows a Start button to create a session and a Stop button to end the current one.
 * Displays a running session indicator with elapsed time.
 */

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchRunningSession,
  startTimeSession,
  stopTimeSession,
} from "@/api/timingsapp";
import type { TimeSession } from "@/api/timingsapp";
import { Play, Square, Clock, Loader2 } from "lucide-react";

const CATEGORIES = [
  { value: "applying", label: "Applying" },
  { value: "researching", label: "Researching" },
  { value: "prepping", label: "Prepping" },
  { value: "networking", label: "Networking" },
  { value: "learning", label: "Learning" },
];

function formatElapsed(startedAt: string): string {
  const startMs = new Date(startedAt).getTime();
  const nowMs = Date.now();
  const totalSeconds = Math.max(0, Math.floor((nowMs - startMs) / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) {
    return `${hours}h ${minutes.toString().padStart(2, "0")}m`;
  }
  return `${minutes}m ${seconds.toString().padStart(2, "0")}s`;
}

export function TimeTrackerControls() {
  const queryClient = useQueryClient();
  const [activityName, setActivityName] = useState("Job search");
  const [category, setCategory] = useState("applying");
  const [showStartForm, setShowStartForm] = useState(false);
  const [elapsed, setElapsed] = useState("");

  // Fetch currently running session
  const { data: runningSession } = useQuery<TimeSession | null>({
    queryKey: ["running-session"],
    queryFn: fetchRunningSession,
    refetchInterval: 10000, // refresh every 10 seconds
  });

  // Start session mutation
  const startMutation = useMutation({
    mutationFn: (data: { activity_name: string; category: string }) =>
      startTimeSession(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["running-session"] });
      queryClient.invalidateQueries({ queryKey: ["timeAnalytics"] });
      setShowStartForm(false);
    },
  });

  // Stop session mutation
  const stopMutation = useMutation({
    mutationFn: (sessionId: number) => stopTimeSession(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["running-session"] });
      queryClient.invalidateQueries({ queryKey: ["timeAnalytics"] });
    },
  });

  // Update elapsed time counter — use a ref-based approach to avoid
  // setting state synchronously within the effect body (react-hooks/set-state-in-effect).
  useEffect(() => {
    if (!runningSession?.started_at) {
      // Schedule the state clear outside the synchronous effect body
      const timer = setTimeout(() => setElapsed(""), 0);
      return () => clearTimeout(timer);
    }

    // Initial update via timeout, then interval
    const updateElapsed = () => {
      setElapsed(formatElapsed(runningSession.started_at));
    };
    const initialTimer = setTimeout(updateElapsed, 0);
    const interval = setInterval(updateElapsed, 1000);
    return () => {
      clearTimeout(initialTimer);
      clearInterval(interval);
    };
  }, [runningSession?.started_at]);

  const handleStart = () => {
    if (!activityName.trim()) return;
    startMutation.mutate({
      activity_name: activityName.trim(),
      category,
    });
  };

  const handleStop = () => {
    if (!runningSession) return;
    stopMutation.mutate(runningSession.id);
  };

  return (
    <div data-testid="time-tracker-controls" className="flex items-center gap-3">
      {runningSession ? (
        /* Running session indicator + stop button */
        <div className="flex items-center gap-2">
          <div
            data-testid="running-session-indicator"
            className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-1.5"
          >
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-green-500" />
            </span>
            <span className="text-sm font-medium text-green-700">
              {runningSession.activity_name}
            </span>
            <span className="text-xs text-green-600">
              ({runningSession.category})
            </span>
            <span
              data-testid="running-session-elapsed"
              className="font-mono text-sm font-semibold text-green-800"
            >
              {elapsed}
            </span>
          </div>
          <button
            data-testid="stop-session-button"
            onClick={handleStop}
            disabled={stopMutation.isPending}
            className="inline-flex items-center gap-1.5 rounded-md bg-red-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-red-700 disabled:opacity-50"
          >
            {stopMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Square className="h-4 w-4" />
            )}
            Stop
          </button>
        </div>
      ) : showStartForm ? (
        /* Start form */
        <div
          data-testid="start-session-form"
          className="flex items-center gap-2"
        >
          <input
            data-testid="session-activity-name"
            type="text"
            value={activityName}
            onChange={(e) => setActivityName(e.target.value)}
            placeholder="Activity name"
            className="w-36 rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
          />
          <select
            data-testid="session-category"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
          >
            {CATEGORIES.map((cat) => (
              <option key={cat.value} value={cat.value}>
                {cat.label}
              </option>
            ))}
          </select>
          <button
            data-testid="confirm-start-button"
            onClick={handleStart}
            disabled={!activityName.trim() || startMutation.isPending}
            className="inline-flex items-center gap-1 rounded-md bg-green-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-green-700 disabled:opacity-50"
          >
            {startMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            Start
          </button>
          <button
            onClick={() => setShowStartForm(false)}
            className="rounded-md border border-gray-300 px-2 py-1.5 text-sm text-gray-600 hover:bg-gray-50"
          >
            Cancel
          </button>
        </div>
      ) : (
        /* Start button (collapsed) */
        <button
          data-testid="start-session-button"
          onClick={() => setShowStartForm(true)}
          className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50"
        >
          <Clock className="h-4 w-4" />
          Start Tracking
        </button>
      )}
    </div>
  );
}
