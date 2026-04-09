/**
 * CalendarSection — shows upcoming calendar events for an application
 * and provides "Add to Calendar" buttons with iCal download + Google Calendar link.
 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchCalendarEvents,
  createCalendarEvent,
  getICalExportUrl,
  fetchGoogleCalendarUrl,
  deleteCalendarEvent,
} from "@/api/calendar";
import type {
  CalendarEventResponse,
  CalendarEventCreate,
} from "@/api/calendar";
import {
  Calendar,
  Plus,
  Download,
  ExternalLink,
  Clock,
  MapPin,
  Video,
  Trash2,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface CalendarSectionProps {
  readonly applicationId: number;
  readonly profileId: number;
  readonly company: string;
  readonly role: string;
}

type EventFormType = "interview" | "follow_up" | "prep_reminder";

function formatDateTime(iso: string): string {
  try {
    const date = new Date(iso);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function isUpcoming(iso: string): boolean {
  return new Date(iso) > new Date();
}

export function CalendarSection({
  applicationId,
  profileId,
  company,
  role,
}: CalendarSectionProps) {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [formType, setFormType] = useState<EventFormType>("interview");
  const [formTitle, setFormTitle] = useState("");
  const [formStartTime, setFormStartTime] = useState("");
  const [formEndTime, setFormEndTime] = useState("");
  const [formLocation, setFormLocation] = useState("");
  const [formMeetingLink, setFormMeetingLink] = useState("");
  const [formPrepNotes, setFormPrepNotes] = useState("");

  // Fetch events for this application
  const { data: eventsData, isLoading } = useQuery({
    queryKey: ["calendar-events", applicationId],
    queryFn: () =>
      fetchCalendarEvents(profileId, { application_id: applicationId }),
  });

  // Create event mutation
  const createMutation = useMutation({
    mutationFn: (data: CalendarEventCreate) => createCalendarEvent(data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["calendar-events", applicationId],
      });
      resetForm();
    },
  });

  // Delete event mutation
  const deleteMutation = useMutation({
    mutationFn: (eventId: number) =>
      deleteCalendarEvent(eventId, profileId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["calendar-events", applicationId],
      });
    },
  });

  function resetForm() {
    setShowForm(false);
    setFormTitle("");
    setFormStartTime("");
    setFormEndTime("");
    setFormLocation("");
    setFormMeetingLink("");
    setFormPrepNotes("");
    setFormType("interview");
  }

  function handleCreate() {
    if (!formTitle || !formStartTime || !formEndTime) return;

    const data: CalendarEventCreate = {
      profile_id: profileId,
      application_id: applicationId,
      event_type: formType,
      title: formTitle,
      start_time: new Date(formStartTime).toISOString(),
      end_time: new Date(formEndTime).toISOString(),
      company,
      role,
      location: formLocation || undefined,
      meeting_link: formMeetingLink || undefined,
      prep_notes: formPrepNotes || undefined,
      reminder_minutes_before: 1440, // 24h default
    };

    createMutation.mutate(data);
  }

  const events = eventsData?.events ?? [];
  const upcomingEvents = events.filter((e) => isUpcoming(e.start_time));
  const pastEvents = events.filter((e) => !isUpcoming(e.start_time));

  return (
    <div
      data-testid="calendar-section"
      className="rounded-lg border bg-white p-6 shadow-sm"
    >
      <div className="mb-4 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900">
          <Calendar className="h-5 w-5" />
          Calendar
        </h2>
        <button
          data-testid="add-calendar-event-button"
          onClick={() => setShowForm(!showForm)}
          className="inline-flex items-center gap-1 rounded-md border border-gray-300 bg-white px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50"
        >
          <Plus className="h-3 w-3" />
          Add to Calendar
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <div
          data-testid="calendar-event-form"
          className="mb-4 space-y-3 rounded-md border border-gray-200 bg-gray-50 p-4"
        >
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="calendar-event-type" className="mb-1 block text-xs font-medium text-gray-600">
                Event Type
              </label>
              <select
                id="calendar-event-type"
                data-testid="calendar-event-type"
                value={formType}
                onChange={(e) => setFormType(e.target.value as EventFormType)}
                className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
              >
                <option value="interview">Interview</option>
                <option value="follow_up">Follow-up</option>
                <option value="prep_reminder">Prep Reminder</option>
              </select>
            </div>
            <div>
              <label htmlFor="calendar-event-title" className="mb-1 block text-xs font-medium text-gray-600">
                Title *
              </label>
              <input
                id="calendar-event-title"
                data-testid="calendar-event-title"
                type="text"
                value={formTitle}
                onChange={(e) => setFormTitle(e.target.value)}
                placeholder={`${({ interview: "Interview", follow_up: "Follow up", prep: "Prep" } as Record<string, string>)[formType] ?? "Prep"} — ${company}`}
                className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="calendar-event-start" className="mb-1 block text-xs font-medium text-gray-600">
                Start Time *
              </label>
              <input
                id="calendar-event-start"
                data-testid="calendar-event-start"
                type="datetime-local"
                value={formStartTime}
                onChange={(e) => setFormStartTime(e.target.value)}
                className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
              />
            </div>
            <div>
              <label htmlFor="calendar-event-end" className="mb-1 block text-xs font-medium text-gray-600">
                End Time *
              </label>
              <input
                id="calendar-event-end"
                data-testid="calendar-event-end"
                type="datetime-local"
                value={formEndTime}
                onChange={(e) => setFormEndTime(e.target.value)}
                className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="calendar-event-location" className="mb-1 block text-xs font-medium text-gray-600">
                Location
              </label>
              <input
                id="calendar-event-location"
                type="text"
                value={formLocation}
                onChange={(e) => setFormLocation(e.target.value)}
                placeholder="Office / Remote"
                className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
              />
            </div>
            <div>
              <label htmlFor="calendar-event-meeting-link" className="mb-1 block text-xs font-medium text-gray-600">
                Meeting Link
              </label>
              <input
                id="calendar-event-meeting-link"
                type="url"
                value={formMeetingLink}
                onChange={(e) => setFormMeetingLink(e.target.value)}
                placeholder="https://meet.google.com/..."
                className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
              />
            </div>
          </div>
          <div>
            <label htmlFor="calendar-event-prep-notes" className="mb-1 block text-xs font-medium text-gray-600">
              Prep Notes
            </label>
            <textarea
              id="calendar-event-prep-notes"
              value={formPrepNotes}
              onChange={(e) => setFormPrepNotes(e.target.value)}
              rows={2}
              placeholder="Preparation notes for this event..."
              className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
            />
          </div>
          <div className="flex justify-end gap-2">
            <button
              onClick={resetForm}
              className="rounded-md border border-gray-300 bg-white px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              data-testid="calendar-event-submit"
              onClick={handleCreate}
              disabled={
                !formTitle ||
                !formStartTime ||
                !formEndTime ||
                createMutation.isPending
              }
              className="rounded-md bg-gray-900 px-3 py-1 text-xs font-medium text-white hover:bg-gray-800 disabled:opacity-50"
            >
              {createMutation.isPending ? "Creating…" : "Create Event"}
            </button>
          </div>
          {createMutation.isError && (
            <p className="text-xs text-red-600">
              {createMutation.error instanceof Error ? createMutation.error.message : String(createMutation.error)}
            </p>
          )}
        </div>
      )}

      {/* Events list */}
      {isLoading ? (
        <p className="text-sm text-gray-400">Loading events…</p>
      ) : events.length === 0 ? (
        <p
          data-testid="calendar-events-empty"
          className="text-sm text-gray-400"
        >
          No calendar events for this application
        </p>
      ) : (
        <div className="space-y-3">
          {/* Upcoming events */}
          {upcomingEvents.length > 0 && (
            <div data-testid="upcoming-events">
              <p className="mb-2 text-xs font-medium text-gray-500">
                Upcoming
              </p>
              <div className="space-y-2">
                {upcomingEvents.map((event) => (
                  <CalendarEventCard
                    key={event.id}
                    event={event}
                    profileId={profileId}
                    onDelete={(id) => deleteMutation.mutate(id)}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Past events */}
          {pastEvents.length > 0 && (
            <div data-testid="past-events">
              <p className="mb-2 text-xs font-medium text-gray-500">Past</p>
              <div className="space-y-2 opacity-60">
                {pastEvents.map((event) => (
                  <CalendarEventCard
                    key={event.id}
                    event={event}
                    profileId={profileId}
                    onDelete={(id) => deleteMutation.mutate(id)}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** Individual calendar event card with export options. */
function CalendarEventCard({
  event,
  profileId,
  onDelete,
}: Readonly<{
  event: CalendarEventResponse;
  profileId: number;
  onDelete: (id: number) => void;
}>) {
  const [showExport, setShowExport] = useState(false);

  const eventTypeColors: Record<string, string> = {
    interview: "bg-blue-100 text-blue-700",
    follow_up: "bg-amber-100 text-amber-700",
    prep_reminder: "bg-purple-100 text-purple-700",
  };

  const handleGoogleCalendar = async () => {
    try {
      const result = await fetchGoogleCalendarUrl(event.id, profileId);
      window.open(result.url, "_blank");
    } catch {
      // Fall back to iCal download
      window.open(getICalExportUrl(event.id, profileId), "_blank");
    }
  };

  const handleICalDownload = () => {
    window.open(getICalExportUrl(event.id, profileId), "_blank");
  };

  return (
    <div
      data-testid={`calendar-event-${event.id}`}
      className="rounded-md border border-gray-200 p-3"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[10px] font-medium capitalize",
                eventTypeColors[event.event_type] ?? "bg-gray-100 text-gray-700",
              )}
            >
              {event.event_type.replace("_", " ")}
            </span>
            <span className="truncate text-sm font-medium text-gray-900">
              {event.title}
            </span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {formatDateTime(event.start_time)}
            </span>
            {event.location && (
              <span className="flex items-center gap-1">
                <MapPin className="h-3 w-3" />
                {event.location}
              </span>
            )}
            {event.meeting_link && (
              <a
                href={event.meeting_link}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-blue-600 hover:underline"
              >
                <Video className="h-3 w-3" />
                Join
              </a>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            data-testid={`calendar-export-toggle-${event.id}`}
            onClick={() => setShowExport(!showExport)}
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            title="Export options"
          >
            <Download className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => onDelete(event.id)}
            className="rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-600"
            title="Delete event"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Export options */}
      {showExport && (
        <div
          data-testid={`calendar-export-options-${event.id}`}
          className="mt-2 flex gap-2 border-t border-gray-100 pt-2"
        >
          <button
            data-testid={`ical-download-${event.id}`}
            onClick={handleICalDownload}
            className="flex items-center gap-1 rounded-md border border-gray-200 px-2 py-1 text-xs text-gray-600 hover:bg-gray-50"
          >
            <Download className="h-3 w-3" />
            iCal (.ics)
          </button>
          <button
            data-testid={`google-calendar-${event.id}`}
            onClick={handleGoogleCalendar}
            className="flex items-center gap-1 rounded-md border border-gray-200 px-2 py-1 text-xs text-gray-600 hover:bg-gray-50"
          >
            <ExternalLink className="h-3 w-3" />
            Google Calendar
          </button>
        </div>
      )}
    </div>
  );
}
