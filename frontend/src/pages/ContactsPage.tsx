/**
 * Contacts page — Networking CRM (M6).
 * List contacts with filters, add/edit/detail, interaction logging.
 */

import { useEffect, useState } from "react";
import { useContacts, useCreateContact, useArchiveContact, useLogInteraction } from "@/hooks/useContacts";
import type {
  Contact,
  ContactCreate,
  RelationshipType,
  Warmth,
  InteractionType,
} from "@/api/types";
import {
  RELATIONSHIP_TYPES,
  RELATIONSHIP_LABELS,
  WARMTH_LEVELS,
  WARMTH_COLORS,
} from "@/api/types";

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function WarmthBadge({ warmth }: Readonly<{ warmth: Warmth }>) {
  const colors = WARMTH_COLORS[warmth];
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${colors.badge}`}
    >
      {warmth}
    </span>
  );
}

function ContactCard({
  contact,
  onSelect,
}: Readonly<{
  contact: Contact;
  onSelect: (c: Contact) => void;
}>) {
  return (
    <button
      type="button"
      className="cursor-pointer rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition-shadow hover:shadow-md text-left w-full"
      onClick={() => onSelect(contact)}
      data-testid={`contact-card-${contact.id}`}
    >
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-gray-900">{contact.name}</h3>
          {contact.company && (
            <p className="text-sm text-gray-600">{contact.company}</p>
          )}
          {contact.role && (
            <p className="text-xs text-gray-500">{contact.role}</p>
          )}
        </div>
        <WarmthBadge warmth={contact.warmth} />
      </div>

      <div className="mt-3 flex items-center gap-2">
        <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
          {RELATIONSHIP_LABELS[contact.relationship_type] ?? contact.relationship_type}
        </span>
        {contact.referral_status != null && contact.referral_status !== "none" && (
          <span className="inline-flex items-center rounded-full bg-purple-100 px-2 py-0.5 text-xs text-purple-700">
            {contact.referral_status.replace("_", " ")}
          </span>
        )}
      </div>

      {(contact.tags?.length ?? 0) > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {contact.tags!.map((tag) => (
            <span
              key={tag}
              className="rounded bg-gray-50 px-1.5 py-0.5 text-xs text-gray-500"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {contact.last_contacted_at && (
        <p className="mt-2 text-xs text-gray-400">
          Last contact: {new Date(contact.last_contacted_at).toLocaleDateString()}
        </p>
      )}
    </button>
  );
}

function ContactDetail({
  contact,
  onClose,
  onLogInteraction,
  onArchive,
}: Readonly<{
  contact: Contact;
  onClose: () => void;
  onLogInteraction: (contactId: number) => void;
  onArchive: (contactId: number) => void;
}>) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      aria-hidden="true"
      data-testid="contact-detail-overlay"
    >
      <button
        type="button"
        className="absolute inset-0 cursor-default"
        onClick={onClose}
        aria-label="Close dialog"
        tabIndex={-1}
      />
      <dialog
        open
        className="relative mx-4 w-full max-w-lg rounded-xl bg-white p-6 shadow-xl"
        aria-modal="true"
      >
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 className="text-xl font-bold text-gray-900">{contact.name}</h2>
            {contact.company && (
              <p className="text-gray-600">{contact.company}</p>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            &times;
          </button>
        </div>

        <div className="space-y-2 text-sm">
          {contact.role && <p><span className="font-medium">Role:</span> {contact.role}</p>}
          {contact.email && <p><span className="font-medium">Email:</span> {contact.email}</p>}
          {contact.linkedin_url && (
            <p>
              <span className="font-medium">LinkedIn:</span>{" "}
              <a
                href={contact.linkedin_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                Profile
              </a>
            </p>
          )}
          {contact.phone && <p><span className="font-medium">Phone:</span> {contact.phone}</p>}
          <p><span className="font-medium">Type:</span> {RELATIONSHIP_LABELS[contact.relationship_type]}</p>
          <p><span className="font-medium">Warmth:</span> <WarmthBadge warmth={contact.warmth} /></p>
          {contact.referral_status != null && contact.referral_status !== "none" && (
            <p><span className="font-medium">Referral:</span> {contact.referral_status.replace("_", " ")}</p>
          )}
          {contact.source && <p><span className="font-medium">Source:</span> {contact.source}</p>}
          {contact.notes && (
            <div>
              <span className="font-medium">Notes:</span>
              <p className="mt-1 text-gray-600">{contact.notes}</p>
            </div>
          )}
        </div>

        <div className="mt-4 flex gap-2">
          <button
            onClick={() => onLogInteraction(contact.id)}
            className="rounded-md bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
          >
            Log Interaction
          </button>
          <button
            onClick={() => onArchive(contact.id)}
            className="rounded-md bg-red-50 px-3 py-1.5 text-sm text-red-700 hover:bg-red-100"
          >
            Archive
          </button>
        </div>
      </dialog>
    </div>
  );
}

function AddContactDialog({
  onClose,
  onSubmit,
}: Readonly<{
  onClose: () => void;
  onSubmit: (data: ContactCreate) => void;
}>) {
  const [name, setName] = useState("");
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [email, setEmail] = useState("");
  const [type, setType] = useState<RelationshipType>("other");
  const [warmth, setWarmth] = useState<Warmth>("cold");
  const [source, setSource] = useState("");
  const [notes, setNotes] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    onSubmit({
      name: name.trim(),
      company: company.trim() || undefined,
      role: role.trim() || undefined,
      email: email.trim() || undefined,
      relationship_type: type,
      warmth,
      source: source.trim() || undefined,
      notes: notes.trim() || undefined,
    });
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      aria-hidden="true"
      data-testid="add-contact-dialog"
    >
      <button
        type="button"
        className="absolute inset-0 cursor-default"
        onClick={onClose}
        aria-label="Close dialog"
        tabIndex={-1}
      />
      <dialog
        open
        className="relative mx-4 w-full max-w-md rounded-xl bg-white p-6 shadow-xl"
        aria-modal="true"
      >
        <h2 className="mb-4 text-lg font-bold">Add Contact</h2>
        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            placeholder="Name *"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-md border px-3 py-2 text-sm"
            data-testid="contact-name-input"
            required
          />
          <input
            placeholder="Company"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            className="w-full rounded-md border px-3 py-2 text-sm"
          />
          <input
            placeholder="Role/Title"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="w-full rounded-md border px-3 py-2 text-sm"
          />
          <input
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-md border px-3 py-2 text-sm"
            type="email"
          />
          <div className="flex gap-3">
            <select
              value={type}
              onChange={(e) => setType(e.target.value as RelationshipType)}
              className="flex-1 rounded-md border px-3 py-2 text-sm"
              data-testid="contact-type-select"
            >
              {RELATIONSHIP_TYPES.map((t) => (
                <option key={t} value={t}>
                  {RELATIONSHIP_LABELS[t]}
                </option>
              ))}
            </select>
            <select
              value={warmth}
              onChange={(e) => setWarmth(e.target.value as Warmth)}
              className="flex-1 rounded-md border px-3 py-2 text-sm"
              data-testid="contact-warmth-select"
            >
              {WARMTH_LEVELS.map((w) => (
                <option key={w} value={w}>
                  {w.charAt(0).toUpperCase() + w.slice(1)}
                </option>
              ))}
            </select>
          </div>
          <input
            placeholder="Source (e.g., conference, linkedin)"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            className="w-full rounded-md border px-3 py-2 text-sm"
          />
          <textarea
            placeholder="Notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className="w-full rounded-md border px-3 py-2 text-sm"
            rows={2}
          />
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md px-4 py-2 text-sm text-gray-600 hover:bg-gray-100"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
              data-testid="contact-submit-btn"
            >
              Add Contact
            </button>
          </div>
        </form>
      </dialog>
    </div>
  );
}

function LogInteractionDialog({
  contactId,
  onClose,
  onSubmit,
}: Readonly<{
  contactId: number;
  onClose: () => void;
  onSubmit: (data: {
    contactId: number;
    data: { interaction_type: string; direction: string; subject?: string; notes?: string };
  }) => void;
}>) {
  const [interactionType, setInteractionType] = useState<InteractionType>("email");
  const [direction, setDirection] = useState<"inbound" | "outbound">("outbound");
  const [subject, setSubject] = useState("");
  const [notes, setNotes] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      contactId,
      data: {
        interaction_type: interactionType,
        direction,
        subject: subject.trim() || undefined,
        notes: notes.trim() || undefined,
      },
    });
  };

  const interactionTypes: InteractionType[] = [
    "email", "call", "coffee", "linkedin_message", "intro", "referral_submission",
  ];

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      aria-hidden="true"
      data-testid="log-interaction-dialog"
    >
      <button
        type="button"
        className="absolute inset-0 cursor-default"
        onClick={onClose}
        aria-label="Close dialog"
        tabIndex={-1}
      />
      <dialog
        open
        className="relative mx-4 w-full max-w-md rounded-xl bg-white p-6 shadow-xl"
        aria-modal="true"
      >
        <h2 className="mb-4 text-lg font-bold">Log Interaction</h2>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="flex gap-3">
            <select
              value={interactionType}
              onChange={(e) => setInteractionType(e.target.value as InteractionType)}
              className="flex-1 rounded-md border px-3 py-2 text-sm"
            >
              {interactionTypes.map((t) => (
                <option key={t} value={t}>
                  {t.replace("_", " ")}
                </option>
              ))}
            </select>
            <select
              value={direction}
              onChange={(e) => setDirection(e.target.value as "inbound" | "outbound")}
              className="flex-1 rounded-md border px-3 py-2 text-sm"
            >
              <option value="outbound">Outbound</option>
              <option value="inbound">Inbound</option>
            </select>
          </div>
          <input
            placeholder="Subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            className="w-full rounded-md border px-3 py-2 text-sm"
          />
          <textarea
            placeholder="Notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className="w-full rounded-md border px-3 py-2 text-sm"
            rows={3}
          />
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md px-4 py-2 text-sm text-gray-600 hover:bg-gray-100"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
            >
              Log
            </button>
          </div>
        </form>
      </dialog>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ContactsPage() {
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [warmthFilter, setWarmthFilter] = useState<string>("");
  const [companyFilter, setCompanyFilter] = useState("");
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [logInteractionForId, setLogInteractionForId] = useState<number | null>(null);

  const { data, isLoading, error } = useContacts({
    search: search || undefined,
    relationship_type: typeFilter || undefined,
    warmth: warmthFilter || undefined,
    company: companyFilter || undefined,
  });

  const createMutation = useCreateContact();
  const archiveMutation = useArchiveContact();
  const logMutation = useLogInteraction();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20" data-testid="contacts-loading">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-10 text-center text-red-600" data-testid="contacts-error">
        Failed to load contacts: {error instanceof Error ? error.message : String(error)}
      </div>
    );
  }

  const contacts = data?.contacts ?? [];

  return (
    <section>
      {/* Header */}
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Contacts</h1>
          <p className="text-sm text-gray-500">
            {data?.total ?? 0} contacts in your network
          </p>
        </div>
        <button
          onClick={() => setShowAddDialog(true)}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          data-testid="add-contact-btn"
        >
          + Add Contact
        </button>
      </header>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap gap-3">
        <input
          placeholder="Search contacts..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="rounded-md border px-3 py-1.5 text-sm"
          data-testid="contacts-search"
        />
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="rounded-md border px-3 py-1.5 text-sm"
          data-testid="contacts-type-filter"
        >
          <option value="">All types</option>
          {RELATIONSHIP_TYPES.map((t) => (
            <option key={t} value={t}>
              {RELATIONSHIP_LABELS[t]}
            </option>
          ))}
        </select>
        <select
          value={warmthFilter}
          onChange={(e) => setWarmthFilter(e.target.value)}
          className="rounded-md border px-3 py-1.5 text-sm"
        >
          <option value="">All warmth</option>
          {WARMTH_LEVELS.map((w) => (
            <option key={w} value={w}>
              {w.charAt(0).toUpperCase() + w.slice(1)}
            </option>
          ))}
        </select>
        <input
          placeholder="Filter by company..."
          value={companyFilter}
          onChange={(e) => setCompanyFilter(e.target.value)}
          className="rounded-md border px-3 py-1.5 text-sm"
        />
      </div>

      {/* Grid */}
      {contacts.length === 0 ? (
        <div className="py-16 text-center" data-testid="contacts-empty">
          <p className="text-lg text-gray-500">No contacts yet</p>
          <p className="mt-1 text-sm text-gray-400">
            Start building your network by adding your first contact.
          </p>
          <button
            onClick={() => setShowAddDialog(true)}
            className="mt-4 rounded-md bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
          >
            Add your first contact
          </button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" data-testid="contacts-grid">
          {contacts.map((contact) => (
            <ContactCard
              key={contact.id}
              contact={contact}
              onSelect={setSelectedContact}
            />
          ))}
        </div>
      )}

      {/* Dialogs */}
      {showAddDialog && (
        <AddContactDialog
          onClose={() => setShowAddDialog(false)}
          onSubmit={(data) => {
            createMutation.mutate(data, {
              onSuccess: () => setShowAddDialog(false),
            });
          }}
        />
      )}

      {selectedContact && (
        <ContactDetail
          contact={selectedContact}
          onClose={() => setSelectedContact(null)}
          onLogInteraction={(id) => {
            setSelectedContact(null);
            setLogInteractionForId(id);
          }}
          onArchive={(id) => {
            archiveMutation.mutate(id, {
              onSuccess: () => setSelectedContact(null),
            });
          }}
        />
      )}

      {logInteractionForId !== null && (
        <LogInteractionDialog
          contactId={logInteractionForId}
          onClose={() => setLogInteractionForId(null)}
          onSubmit={(payload) => {
            logMutation.mutate(payload, {
              onSuccess: () => setLogInteractionForId(null),
            });
          }}
        />
      )}
    </section>
  );
}
