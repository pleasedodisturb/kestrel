/**
 * Tests for the VoiceDiscussion page.
 *
 * Covers:
 * - Empty state rendering with mode selection
 * - Session creation
 * - Message sending and response display
 * - Session list rendering
 * - Navigation link present
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { VoiceDiscussion } from "@/pages/VoiceDiscussion";
import type {
  VoiceSession,
  VoiceSessionListResponse,
  VoiceSendResponse,
} from "@/api/voice";

// ---- mocks ----

const mockFetchVoiceSessions =
  vi.fn<() => Promise<VoiceSessionListResponse>>();
const mockFetchVoiceSession = vi.fn<() => Promise<VoiceSession>>();
const mockCreateVoiceSession = vi.fn<() => Promise<VoiceSession>>();
const mockSendVoiceMessage = vi.fn<() => Promise<VoiceSendResponse>>();
const mockCompleteVoiceSession = vi.fn<() => Promise<VoiceSession>>();

vi.mock("@/api/voice", () => ({
  fetchVoiceSessions: (...args: unknown[]) =>
    mockFetchVoiceSessions(...(args as [])),
  fetchVoiceSession: (...args: unknown[]) =>
    mockFetchVoiceSession(...(args as [])),
  createVoiceSession: (...args: unknown[]) =>
    mockCreateVoiceSession(...(args as [])),
  sendVoiceMessage: (...args: unknown[]) =>
    mockSendVoiceMessage(...(args as [])),
  completeVoiceSession: (...args: unknown[]) =>
    mockCompleteVoiceSession(...(args as [])),
}));

const mockFetchApplications = vi.fn();

vi.mock("@/api/applications", () => ({
  DEFAULT_PROFILE_ID: 1,
  fetchApplications: (...args: unknown[]) =>
    mockFetchApplications(...(args as [])),
}));

// ---- helpers ----

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  });
}

function renderPage() {
  const qc = createQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/voice"]}>
        <VoiceDiscussion />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const NOW = "2026-03-14T12:00:00Z";

function makeSession(
  overrides: Partial<VoiceSession> = {},
): VoiceSession {
  return {
    id: 1,
    profile_id: 1,
    application_id: null,
    mode: "coaching",
    title: "Coaching Session",
    status: "active",
    messages: [
      {
        id: 1,
        session_id: 1,
        role: "assistant",
        content: "Welcome to your coaching session!",
        created_at: NOW,
      },
    ],
    created_at: NOW,
    updated_at: NOW,
    ...overrides,
  };
}

// ---- tests ----

describe("VoiceDiscussion", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchVoiceSessions.mockResolvedValue({ sessions: [], total: 0 });
    mockFetchApplications.mockResolvedValue({
      applications: [
        { id: 1, company: "Acme Corp", role: "Senior TPM", status: "applied" },
        { id: 2, company: "Mistral AI", role: "Product Engineer", status: "interested" },
      ],
      total: 2,
    });
  });

  describe("empty state", () => {
    it("renders the Voice Discussion Mode heading", async () => {
      renderPage();
      await waitFor(() => {
        expect(
          screen.getByText("Voice Discussion Mode"),
        ).toBeInTheDocument();
      });
    });

    it("renders mode selection buttons", async () => {
      renderPage();
      await waitFor(() => {
        // Sidebar + main area each have one — use getAllByText
        expect(
          screen.getAllByText("Cover Letter Brainstorm").length,
        ).toBeGreaterThanOrEqual(1);
        expect(
          screen.getAllByText("Coaching Session").length,
        ).toBeGreaterThanOrEqual(1);
        expect(
          screen.getAllByText("Job Evaluation").length,
        ).toBeGreaterThanOrEqual(1);
      });
    });

    it("shows 'No sessions yet' message in sidebar", async () => {
      renderPage();
      await waitFor(() => {
        expect(
          screen.getByText(/No sessions yet/),
        ).toBeInTheDocument();
      });
    });
  });

  describe("session creation", () => {
    it("creates a coaching session when button clicked", async () => {
      const session = makeSession();
      mockCreateVoiceSession.mockResolvedValue(session);
      mockFetchVoiceSession.mockResolvedValue(session);

      renderPage();

      await waitFor(() => {
        expect(
          screen.getAllByText("Coaching Session").length,
        ).toBeGreaterThanOrEqual(1);
      });

      // Click the first "Coaching Session" button (sidebar)
      const buttons = screen.getAllByText("Coaching Session");
      fireEvent.click(buttons[0]);

      await waitFor(() => {
        expect(mockCreateVoiceSession).toHaveBeenCalledWith({
          mode: "coaching",
        });
      });
    });
  });

  describe("session with messages", () => {
    it("renders session messages when active", async () => {
      const session = makeSession({
        messages: [
          {
            id: 1,
            session_id: 1,
            role: "assistant",
            content: "Welcome to your coaching session!",
            created_at: NOW,
          },
          {
            id: 2,
            session_id: 1,
            role: "user",
            content: "I want interview prep help",
            created_at: NOW,
          },
          {
            id: 3,
            session_id: 1,
            role: "assistant",
            content: "Great, let's focus on interview preparation.",
            created_at: NOW,
          },
        ],
      });
      mockFetchVoiceSessions.mockResolvedValue({
        sessions: [session],
        total: 1,
      });
      mockFetchVoiceSession.mockResolvedValue(session);

      renderPage();

      // Click the session in sidebar (session list item, not the mode button)
      await waitFor(() => {
        const allCoaching = screen.getAllByText("Coaching Session");
        // The session list item is the last one with that text
        fireEvent.click(allCoaching[allCoaching.length - 1]);
      });

      await waitFor(() => {
        expect(
          screen.getByText("Welcome to your coaching session!"),
        ).toBeInTheDocument();
        expect(
          screen.getByText("I want interview prep help"),
        ).toBeInTheDocument();
        expect(
          screen.getByText(
            "Great, let's focus on interview preparation.",
          ),
        ).toBeInTheDocument();
      });
    });

    it("renders text input area", async () => {
      const session = makeSession();
      mockFetchVoiceSessions.mockResolvedValue({
        sessions: [session],
        total: 1,
      });
      mockFetchVoiceSession.mockResolvedValue(session);

      renderPage();

      await waitFor(() => {
        const allCoaching = screen.getAllByText("Coaching Session");
        fireEvent.click(allCoaching[allCoaching.length - 1]);
      });

      await waitFor(() => {
        expect(
          screen.getByPlaceholderText(/Type or paste text/),
        ).toBeInTheDocument();
      });
    });

    it("renders STT-agnostic hint", async () => {
      const session = makeSession();
      mockFetchVoiceSessions.mockResolvedValue({
        sessions: [session],
        total: 1,
      });
      mockFetchVoiceSession.mockResolvedValue(session);

      renderPage();

      await waitFor(() => {
        const allCoaching = screen.getAllByText("Coaching Session");
        fireEvent.click(allCoaching[allCoaching.length - 1]);
      });

      await waitFor(() => {
        expect(screen.getByText(/SuperWhisper/)).toBeInTheDocument();
      });
    });
  });

  describe("session list", () => {
    it("renders multiple sessions in sidebar", async () => {
      const sessions = [
        makeSession({ id: 1, title: "Coaching Session" }),
        makeSession({
          id: 2,
          mode: "cover_letter",
          title: "Cover Letter — Stripe",
        }),
      ];
      mockFetchVoiceSessions.mockResolvedValue({
        sessions,
        total: 2,
      });

      renderPage();

      await waitFor(() => {
        expect(
          screen.getByText("Cover Letter — Stripe"),
        ).toBeInTheDocument();
      });
    });
  });

  describe("application picker for cover_letter mode", () => {
    it("renders application picker dropdown", async () => {
      renderPage();
      await waitFor(() => {
        expect(
          screen.getByTestId("voice-application-picker"),
        ).toBeInTheDocument();
      });
    });

    it("populates picker with applications", async () => {
      renderPage();
      await waitFor(() => {
        const picker = screen.getByTestId("voice-application-picker");
        expect(picker).toBeInTheDocument();
        // Check options are present
        const options = picker.querySelectorAll("option");
        // Default "Select application..." + 2 apps
        expect(options.length).toBe(3);
      });
    });

    it("passes application_id when creating cover_letter session", async () => {
      const session = makeSession({
        mode: "cover_letter",
        application_id: 1,
        title: "Cover Letter — Acme Corp",
      });
      mockCreateVoiceSession.mockResolvedValue(session);
      mockFetchVoiceSession.mockResolvedValue(session);

      renderPage();

      // Wait for applications to load into picker
      await waitFor(() => {
        const picker = screen.getByTestId("voice-application-picker");
        const options = picker.querySelectorAll("option");
        expect(options.length).toBe(3); // default + 2 apps
      });

      // Select an application using fireEvent
      const picker = screen.getByTestId("voice-application-picker");
      fireEvent.change(picker, { target: { value: "1" } });

      // After selection, the sidebar cover letter button should become enabled
      // Find and click it — getAllByText includes sidebar + main area buttons
      await waitFor(() => {
        const allBtns = screen.getAllByText("Cover Letter Brainstorm");
        // The sidebar button is the first one
        const btn = allBtns[0].closest("button");
        if (!btn || btn.disabled) {
          throw new Error("Button still disabled");
        }
      });

      const allBtns = screen.getAllByText("Cover Letter Brainstorm");
      fireEvent.click(allBtns[0]);

      await waitFor(() => {
        expect(mockCreateVoiceSession).toHaveBeenCalledWith({
          mode: "cover_letter",
          application_id: 1,
        });
      });
    });

    it("shows application context in active session header", async () => {
      const session = makeSession({
        mode: "cover_letter",
        application_id: 42,
        title: "Cover Letter — Acme",
      });
      mockFetchVoiceSessions.mockResolvedValue({
        sessions: [session],
        total: 1,
      });
      mockFetchVoiceSession.mockResolvedValue(session);
      mockCreateVoiceSession.mockResolvedValue(session);

      renderPage();

      // Click on the session in the sidebar
      await waitFor(() => {
        expect(screen.getByText("Cover Letter — Acme")).toBeInTheDocument();
      });
      fireEvent.click(screen.getByText("Cover Letter — Acme"));

      await waitFor(() => {
        expect(
          screen.getByTestId("voice-application-context"),
        ).toBeInTheDocument();
        expect(
          screen.getByText(/Application #42/),
        ).toBeInTheDocument();
      });
    });
  });
});

describe("Layout navigation", () => {
  it("renders Voice nav link", async () => {
    const { Layout } = await import("@/components/Layout");
    const qc = createQueryClient();
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/"]}>
          <Layout />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByText("Voice")).toBeInTheDocument();
  });
});
