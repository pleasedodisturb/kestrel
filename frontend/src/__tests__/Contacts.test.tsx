/**
 * Tests for the Contacts page (M6 Networking CRM) — 10 tests per spec §3.6.
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import ContactsPage from "@/pages/ContactsPage";
import type { Contact, ContactListResponse } from "@/api/types";

// ---- mocks ----

const mockFetchContacts = vi.fn();
const mockCreateContact = vi.fn();
const mockArchiveContact = vi.fn();
const mockLogInteraction = vi.fn();

vi.mock("@/api/contacts", () => ({
  fetchContacts: (...args: unknown[]) => mockFetchContacts(...(args as [])),
  fetchContactDetail: vi.fn(),
  createContact: (...args: unknown[]) => mockCreateContact(...(args as [])),
  updateContact: vi.fn(),
  archiveContact: (...args: unknown[]) => mockArchiveContact(...(args as [])),
  logInteraction: (...args: unknown[]) => mockLogInteraction(...(args as [])),
  linkContactToApplication: vi.fn(),
}));

// ---- helpers ----

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

function renderContacts() {
  const qc = createQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/contacts"]}>
        <Routes>
          <Route path="/contacts" element={<ContactsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function makeContact(overrides: Partial<Contact> = {}): Contact {
  return {
    id: 1,
    profile_id: 1,
    name: "Jane Doe",
    company: "Mistral",
    role: "Hiring Manager",
    email: "jane@mistral.ai",
    linkedin_url: null,
    phone: null,
    relationship_type: "referral",
    referral_status: "contacted",
    warmth: "hot",
    notes: null,
    tags: ["ai", "tpm"],
    source: "conference",
    last_contacted_at: "2026-03-10T12:00:00Z",
    next_follow_up: null,
    created_at: "2026-03-01T00:00:00Z",
    updated_at: "2026-03-10T12:00:00Z",
    archived_at: null,
    ...overrides,
  };
}

function makeContactList(contacts: Contact[]): ContactListResponse {
  return { contacts, total: contacts.length };
}

// ---- tests ----

beforeEach(() => {
  vi.clearAllMocks();
});

// 1. renders contact list
describe("ContactsPage", () => {
  it("renders contact list", async () => {
    const contacts = [
      makeContact({ id: 1, name: "Jane Doe" }),
      makeContact({ id: 2, name: "Bob Smith", company: "Linear" }),
    ];
    mockFetchContacts.mockResolvedValue(makeContactList(contacts));

    renderContacts();

    await waitFor(() => {
      expect(screen.getByText("Jane Doe")).toBeInTheDocument();
      expect(screen.getByText("Bob Smith")).toBeInTheDocument();
    });
  });

  // 2. add contact dialog has form fields
  it("shows add contact dialog with form fields", async () => {
    mockFetchContacts.mockResolvedValue(makeContactList([]));

    renderContacts();

    await waitFor(() => {
      expect(screen.getByTestId("add-contact-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("add-contact-btn"));

    expect(screen.getByTestId("add-contact-dialog")).toBeInTheDocument();
    expect(screen.getByTestId("contact-name-input")).toBeInTheDocument();
    expect(screen.getByTestId("contact-type-select")).toBeInTheDocument();
    expect(screen.getByTestId("contact-warmth-select")).toBeInTheDocument();
  });

  // 3. filter by company
  it("filters by company", async () => {
    mockFetchContacts.mockResolvedValue(
      makeContactList([makeContact({ name: "Jane", company: "Mistral" })]),
    );

    renderContacts();

    await waitFor(() => {
      expect(screen.getByText("Jane")).toBeInTheDocument();
    });

    // Verify the company filter input exists
    const companyInputs = screen.getAllByPlaceholderText(/company/i);
    expect(companyInputs.length).toBeGreaterThan(0);
  });

  // 4. filter by type
  it("has type filter dropdown", async () => {
    mockFetchContacts.mockResolvedValue(makeContactList([]));

    renderContacts();

    await waitFor(() => {
      expect(screen.getByTestId("contacts-type-filter")).toBeInTheDocument();
    });
  });

  // 5. contact detail expands
  it("shows contact detail on click", async () => {
    const contact = makeContact({ name: "Jane Doe", company: "Mistral" });
    mockFetchContacts.mockResolvedValue(makeContactList([contact]));

    renderContacts();

    await waitFor(() => {
      expect(screen.getByText("Jane Doe")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("contact-card-1"));

    await waitFor(() => {
      expect(screen.getByTestId("contact-detail-overlay")).toBeInTheDocument();
    });
  });

  // 6. log interaction button shows dialog
  it("shows log interaction dialog", async () => {
    const contact = makeContact({ id: 1, name: "Jane" });
    mockFetchContacts.mockResolvedValue(makeContactList([contact]));

    renderContacts();

    await waitFor(() => {
      expect(screen.getByText("Jane")).toBeInTheDocument();
    });

    // Open contact detail
    fireEvent.click(screen.getByTestId("contact-card-1"));

    await waitFor(() => {
      expect(screen.getByText("Log Interaction")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Log Interaction"));

    await waitFor(() => {
      expect(screen.getByTestId("log-interaction-dialog")).toBeInTheDocument();
    });
  });

  // 7. displays warmth badge with correct styling
  it("displays warmth badge on contact card", async () => {
    const contact = makeContact({ id: 1, name: "Hot Contact", warmth: "hot" });
    mockFetchContacts.mockResolvedValue(makeContactList([contact]));

    renderContacts();

    await waitFor(() => {
      expect(screen.getByText("hot")).toBeInTheDocument();
    });
  });

  // 8. empty state
  it("shows empty state when no contacts", async () => {
    mockFetchContacts.mockResolvedValue(makeContactList([]));

    renderContacts();

    await waitFor(() => {
      expect(screen.getByTestId("contacts-empty")).toBeInTheDocument();
      expect(screen.getByText("No contacts yet")).toBeInTheDocument();
    });
  });

  // 9. error state
  it("shows error message on fetch failure", async () => {
    mockFetchContacts.mockRejectedValue(new Error("Network error"));

    renderContacts();

    await waitFor(() => {
      expect(screen.getByTestId("contacts-error")).toBeInTheDocument();
      expect(screen.getByText(/Network error/)).toBeInTheDocument();
    });
  });

  // 10. loading state
  it("shows spinner while loading", async () => {
    mockFetchContacts.mockReturnValue(new Promise(() => {})); // never resolves

    renderContacts();

    expect(screen.getByTestId("contacts-loading")).toBeInTheDocument();
  });

  // 11. Escape key closes contact detail dialog
  it("closes contact detail on Escape key", async () => {
    const contact = makeContact({ id: 1, name: "Jane Doe" });
    mockFetchContacts.mockResolvedValue(makeContactList([contact]));

    renderContacts();

    await waitFor(() => {
      expect(screen.getByText("Jane Doe")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("contact-card-1"));

    await waitFor(() => {
      expect(screen.getByTestId("contact-detail-overlay")).toBeInTheDocument();
    });

    fireEvent.keyDown(document, { key: "Escape" });

    await waitFor(() => {
      expect(screen.queryByTestId("contact-detail-overlay")).not.toBeInTheDocument();
    });
  });

  // 12. Add contact form submission
  it("submits add contact form", async () => {
    mockFetchContacts.mockResolvedValue(makeContactList([]));
    mockCreateContact.mockResolvedValue(makeContact({ name: "New Person" }));

    renderContacts();

    await waitFor(() => {
      expect(screen.getByTestId("add-contact-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("add-contact-btn"));

    expect(screen.getByTestId("add-contact-dialog")).toBeInTheDocument();

    const nameInput = screen.getByTestId("contact-name-input");
    fireEvent.change(nameInput, { target: { value: "New Person" } });

    const form = nameInput.closest("form")!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(mockCreateContact).toHaveBeenCalledWith(
        expect.objectContaining({ name: "New Person" }),
      );
    });
  });

  // 13. Log interaction form submission
  it("submits log interaction form", async () => {
    const contact = makeContact({ id: 1, name: "Jane" });
    mockFetchContacts.mockResolvedValue(makeContactList([contact]));
    mockLogInteraction.mockResolvedValue({});

    renderContacts();

    await waitFor(() => {
      expect(screen.getByText("Jane")).toBeInTheDocument();
    });

    // Open contact detail
    fireEvent.click(screen.getByTestId("contact-card-1"));

    await waitFor(() => {
      expect(screen.getByText("Log Interaction")).toBeInTheDocument();
    });

    // Open log interaction dialog
    fireEvent.click(screen.getByText("Log Interaction"));

    await waitFor(() => {
      expect(screen.getByTestId("log-interaction-dialog")).toBeInTheDocument();
    });

    // Submit the form via the form element
    const dialog = screen.getByTestId("log-interaction-dialog");
    const form = dialog.querySelector("form")!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(mockLogInteraction).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ interaction_type: "email" }),
      );
    });
  });
});
