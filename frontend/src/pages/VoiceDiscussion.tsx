import { useState, useRef, useEffect, useCallback } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createVoiceSession,
  fetchVoiceSessions,
  fetchVoiceSession,
  sendVoiceMessage,
  completeVoiceSession,
} from "@/api/voice";
import { fetchApplications } from "@/api/applications";
import type { ApplicationListResponse } from "@/api/types";
import type { VoiceMessage, VoiceMode } from "@/api/voice";
import {
  Mic,
  Send,
  Plus,
  MessageSquare,
  FileText,
  GraduationCap,
  Scale,
  Loader2,
  CheckCircle,
  Clock,
  Briefcase,
} from "lucide-react";

const MODE_CONFIG: Record<
  VoiceMode,
  { label: string; description: string; icon: typeof Mic; color: string }
> = {
  cover_letter: {
    label: "Cover Letter Brainstorm",
    description: "Draft a cover letter referencing your profile and target role",
    icon: FileText,
    color: "text-blue-600 bg-blue-50 border-blue-200",
  },
  coaching: {
    label: "Coaching Session",
    description: "Get role-relevant questions and constructive feedback",
    icon: GraduationCap,
    color: "text-purple-600 bg-purple-50 border-purple-200",
  },
  job_evaluation: {
    label: "Job Evaluation",
    description: "Get a scored assessment with pros and cons",
    icon: Scale,
    color: "text-amber-600 bg-amber-50 border-amber-200",
  },
};

export function VoiceDiscussion() {
  const queryClient = useQueryClient();
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [inputText, setInputText] = useState("");
  const [selectedApplicationId, setSelectedApplicationId] = useState<number | undefined>(undefined);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Fetch applications for the picker dropdown
  const { data: applicationsData } = useQuery<ApplicationListResponse>({
    queryKey: ["applications-for-voice"],
    queryFn: () => fetchApplications(),
  });

  // Fetch sessions list
  const { data: sessionsData } = useQuery({
    queryKey: ["voice-sessions"],
    queryFn: () => fetchVoiceSessions(),
  });

  // Fetch active session
  const { data: activeSession } = useQuery({
    queryKey: ["voice-session", activeSessionId],
    queryFn: () => {
      if (activeSessionId === null) throw new Error("No active session");
      return fetchVoiceSession(activeSessionId);
    },
    enabled: !!activeSessionId,
  });

  // Create session mutation
  const createMutation = useMutation({
    mutationFn: (params: { mode: VoiceMode; application_id?: number }) =>
      createVoiceSession(params),
    onSuccess: (session) => {
      setActiveSessionId(session.id);
      queryClient.invalidateQueries({ queryKey: ["voice-sessions"] });
      queryClient.invalidateQueries({
        queryKey: ["voice-session", session.id],
      });
    },
  });

  // Send message mutation with optimistic input clear
  const sendMutation = useMutation({
    mutationFn: (content: string) => {
      if (activeSessionId === null) throw new Error("No active session");
      return sendVoiceMessage(activeSessionId, content);
    },
    onMutate: () => {
      // Clear input immediately for responsive feel
      setInputText("");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["voice-session", activeSessionId],
      });
    },
    onError: (_err, content) => {
      // Restore the message if sending failed
      setInputText(content);
    },
  });

  // Complete session mutation
  const completeMutation = useMutation({
    mutationFn: () => {
      if (activeSessionId === null) throw new Error("No active session");
      return completeVoiceSession(activeSessionId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["voice-sessions"] });
      queryClient.invalidateQueries({
        queryKey: ["voice-session", activeSessionId],
      });
    },
  });

  // Scroll to bottom on new messages
  useEffect(() => {
    if (messagesEndRef.current && typeof messagesEndRef.current.scrollIntoView === "function") {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [activeSession?.messages]);

  // Focus input when session is active
  useEffect(() => {
    if (activeSessionId) {
      inputRef.current?.focus();
    }
  }, [activeSessionId]);

  const handleSend = useCallback(() => {
    const trimmed = inputText.trim();
    if (!trimmed || sendMutation.isPending || !activeSessionId) return;
    sendMutation.mutate(trimmed);
  }, [inputText, sendMutation, activeSessionId]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const sessions = sessionsData?.sessions ?? [];

  return (
    <section className="flex h-[calc(100vh-8rem)] gap-4">
      {/* Sidebar: Session list */}
      <div className="w-72 flex-shrink-0 overflow-y-auto rounded-lg border bg-white p-3">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700">Sessions</h2>
        </div>

        {/* New session buttons */}
        <div className="mb-3 space-y-1">
          {(Object.entries(MODE_CONFIG) as [VoiceMode, (typeof MODE_CONFIG)[VoiceMode]][]).map(
            ([mode, config]) => {
              const Icon = config.icon;
              return (
                <div key={mode}>
                  <button
                    onClick={() => {
                      if (mode === "cover_letter") {
                        createMutation.mutate({
                          mode,
                          application_id: selectedApplicationId,
                        });
                      } else {
                        createMutation.mutate({ mode });
                      }
                    }}
                    disabled={createMutation.isPending || (mode === "cover_letter" && !selectedApplicationId)}
                    className={`flex w-full items-center gap-2 rounded-md border px-3 py-2 text-left text-xs font-medium transition-colors hover:opacity-80 ${config.color} ${mode === "cover_letter" && !selectedApplicationId ? "opacity-50 cursor-not-allowed" : ""}`}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    <span>{config.label}</span>
                    <Plus className="ml-auto h-3 w-3" />
                  </button>
                  {/* Application picker for cover_letter mode */}
                  {mode === "cover_letter" && (
                    <div className="mt-1 px-1">
                      <select
                        data-testid="voice-application-picker"
                        value={selectedApplicationId ?? ""}
                        onChange={(e) =>
                          setSelectedApplicationId(
                            e.target.value ? Number(e.target.value) : undefined,
                          )
                        }
                        className="w-full rounded-md border border-blue-200 bg-blue-50/50 px-2 py-1 text-[11px] text-gray-700 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-300"
                      >
                        <option value="">Select application…</option>
                        {(applicationsData?.applications ?? []).map((app) => (
                          <option key={app.id} value={app.id}>
                            {app.company} — {app.role}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>
              );
            },
          )}
        </div>

        {/* Session history */}
        <div className="space-y-1">
          {sessions.map((session) => {
            const config = MODE_CONFIG[session.mode];
            const isActive = session.id === activeSessionId;
            return (
              <button
                key={session.id}
                onClick={() => setActiveSessionId(session.id)}
                className={`flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-xs transition-colors ${
                  isActive
                    ? "bg-gray-100 text-gray-900"
                    : "text-gray-600 hover:bg-gray-50"
                }`}
              >
                <MessageSquare className="h-3.5 w-3.5 flex-shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium">
                    {session.title ?? config.label}
                  </div>
                  <div className="flex items-center gap-1 text-[10px] text-gray-400">
                    {session.status === "completed" ? (
                      <CheckCircle className="h-2.5 w-2.5 text-green-500" />
                    ) : (
                      <Clock className="h-2.5 w-2.5" />
                    )}
                    <span>
                      {new Date(session.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              </button>
            );
          })}
          {sessions.length === 0 && (
            <p className="px-3 py-4 text-center text-xs text-gray-400">
              No sessions yet. Start a new discussion above!
            </p>
          )}
        </div>
      </div>

      {/* Main chat area */}
      <div className="flex flex-1 flex-col rounded-lg border bg-white">
        {activeSession ? (
          <>
            {/* Header */}
            <div className="flex items-center justify-between border-b px-4 py-3">
              <div>
                <h1 className="text-sm font-semibold text-gray-900">
                  {activeSession.title ?? "Voice Discussion"}
                </h1>
                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <span className="capitalize">
                    {MODE_CONFIG[activeSession.mode]?.label ?? activeSession.mode}
                  </span>
                  {activeSession.application_id && (
                    <span
                      data-testid="voice-application-context"
                      className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-medium text-blue-700"
                    >
                      <Briefcase className="h-2.5 w-2.5" />
                      Application #{activeSession.application_id}
                    </span>
                  )}
                  {activeSession.status === "completed" && (
                    <span className="rounded-full bg-green-100 px-2 py-0.5 text-[10px] font-medium text-green-700">
                      Completed
                    </span>
                  )}
                </div>
              </div>
              {activeSession.status === "active" && (
                <button
                  onClick={() => completeMutation.mutate()}
                  disabled={completeMutation.isPending}
                  className="rounded-md bg-gray-100 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-200"
                >
                  End Session
                </button>
              )}
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-3">
              <div className="space-y-4">
                {activeSession.messages.map((msg) => (
                  <MessageBubble key={msg.id} message={msg} />
                ))}
                {sendMutation.isPending && (
                  <div className="flex items-center gap-2 text-sm text-gray-400">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Thinking...</span>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            </div>

            {/* Input area */}
            {activeSession.status === "active" && (
              <div className="border-t px-4 py-3">
                <div className="flex items-end gap-2">
                  <div className="relative flex-1">
                    <textarea
                      ref={inputRef}
                      value={inputText}
                      onChange={(e) => setInputText(e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder="Type or paste text from any STT tool (SuperWhisper, MacWhisper, system dictation)..."
                      className="w-full resize-none rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-blue-300 focus:outline-none focus:ring-1 focus:ring-blue-300"
                      rows={2}
                      disabled={sendMutation.isPending}
                    />
                  </div>
                  <button
                    onClick={handleSend}
                    disabled={
                      !inputText.trim() || sendMutation.isPending
                    }
                    className="rounded-lg bg-blue-600 p-2 text-white transition-colors hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    title="Send message"
                  >
                    {sendMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                  </button>
                </div>
                <p className="mt-1 flex items-center gap-1 text-[10px] text-gray-400">
                  <Mic className="h-3 w-3" />
                  STT-agnostic — works with SuperWhisper, MacWhisper, or any speech-to-text tool
                </p>
              </div>
            )}
          </>
        ) : (
          /* Empty state */
          <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8">
            <div className="rounded-full bg-gray-100 p-4">
              <Mic className="h-8 w-8 text-gray-400" />
            </div>
            <div className="text-center">
              <h2 className="text-lg font-semibold text-gray-900">
                Voice Discussion Mode
              </h2>
              <p className="mt-1 max-w-md text-sm text-gray-500">
                Start a conversational session for cover letter brainstorming,
                coaching, or job evaluation. Works with any speech-to-text tool
                or direct typing.
              </p>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              {(Object.entries(MODE_CONFIG) as [VoiceMode, (typeof MODE_CONFIG)[VoiceMode]][]).map(
                ([mode, config]) => {
                  const Icon = config.icon;
                  return (
                    <button
                      key={mode}
                      onClick={() => {
                        if (mode === "cover_letter") {
                          createMutation.mutate({
                            mode,
                            application_id: selectedApplicationId,
                          });
                        } else {
                          createMutation.mutate({ mode });
                        }
                      }}
                      disabled={createMutation.isPending || (mode === "cover_letter" && !selectedApplicationId)}
                      className={`flex flex-col items-center gap-2 rounded-lg border p-4 text-center transition-colors hover:opacity-80 ${config.color} ${mode === "cover_letter" && !selectedApplicationId ? "opacity-50 cursor-not-allowed" : ""}`}
                    >
                      <Icon className="h-6 w-6" />
                      <span className="text-sm font-medium">{config.label}</span>
                      <span className="text-xs opacity-70">
                        {config.description}
                      </span>
                    </button>
                  );
                },
              )}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

/** Single message bubble component. */
function MessageBubble({ message }: Readonly<{ message: VoiceMessage }>) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-2.5 text-sm ${
          isUser
            ? "bg-blue-600 text-white"
            : "bg-gray-100 text-gray-800"
        }`}
      >
        <div className="whitespace-pre-wrap">{message.content}</div>
        <div
          className={`mt-1 text-[10px] ${
            isUser ? "text-blue-200" : "text-gray-400"
          }`}
        >
          {new Date(message.created_at).toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}
