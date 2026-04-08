"""Contact service layer — business logic for Networking CRM (M6)."""

import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from career_os.models.contacts import Contact, ContactApplication, ContactInteraction
from career_os.models.models import Application, Profile
from career_os.schemas.contacts import (
    ContactApplicationCreate,
    ContactCreate,
    ContactUpdate,
    InteractionCreate,
)
from career_os.services.activity import log_activity

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ContactNotFoundError(Exception):
    """Raised when a contact is not found or is archived."""


class ProfileNotFoundError(Exception):
    """Raised when the referenced profile does not exist."""


class ApplicationNotFoundError(Exception):
    """Raised when the referenced application does not exist."""


class DuplicateLinkError(Exception):
    """Raised when trying to link a contact to an application that's already linked."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_active_contact(db: Session, contact_id: int, *, profile_id: int | None = None) -> Contact:
    """Fetch a non-archived contact or raise."""
    filters = [Contact.id == contact_id, Contact.archived_at.is_(None)]
    if profile_id is not None:
        filters.append(Contact.profile_id == profile_id)
    contact = db.query(Contact).filter(*filters).first()
    if contact is None:
        raise ContactNotFoundError(f"Contact {contact_id} not found")
    return contact


def _serialize_tags(tags: list[str] | None) -> str | None:
    """Serialize tags list to JSON string for storage."""
    if tags is None:
        return None
    return json.dumps(tags)


# ---------------------------------------------------------------------------
# Contact CRUD
# ---------------------------------------------------------------------------


def create_contact(db: Session, payload: ContactCreate) -> Contact:
    """Create a new contact."""
    profile = db.query(Profile).filter(Profile.id == payload.profile_id).first()
    if profile is None:
        raise ProfileNotFoundError(f"Profile {payload.profile_id} not found")

    contact = Contact(
        profile_id=payload.profile_id,
        name=payload.name,
        company=payload.company,
        role=payload.role,
        email=payload.email,
        linkedin_url=payload.linkedin_url,
        phone=payload.phone,
        relationship_type=payload.relationship_type,
        referral_status=payload.referral_status,
        warmth=payload.warmth,
        notes=payload.notes,
        tags=_serialize_tags(payload.tags),
        source=payload.source,
        next_follow_up=payload.next_follow_up,
    )
    db.add(contact)
    db.flush()

    log_activity(
        db,
        profile_id=payload.profile_id,
        action="contact_created",
        entity_type="contact",
        entity_id=contact.id,
        details=f"Created contact {payload.name}"
        + (f" at {payload.company}" if payload.company else ""),
    )
    db.commit()
    db.refresh(contact)
    return contact


def get_contact(db: Session, contact_id: int, *, profile_id: int | None = None) -> Contact:
    """Get a single non-archived contact."""
    return _get_active_contact(db, contact_id, profile_id=profile_id)


def list_contacts(
    db: Session,
    *,
    profile_id: int,
    company: str | None = None,
    relationship_type: str | None = None,
    warmth: str | None = None,
    needs_follow_up: bool = False,
    search: str | None = None,
) -> tuple[list[Contact], int]:
    """List contacts with optional filters."""
    query = db.query(Contact).filter(
        Contact.profile_id == profile_id,
        Contact.archived_at.is_(None),
    )

    if company:
        query = query.filter(Contact.company.ilike(f"%{company}%"))

    if relationship_type:
        query = query.filter(Contact.relationship_type == relationship_type)

    if warmth:
        query = query.filter(Contact.warmth == warmth)

    if needs_follow_up:
        now = datetime.now(UTC)
        query = query.filter(
            Contact.next_follow_up.isnot(None),
            Contact.next_follow_up <= now,
        )

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            Contact.name.ilike(pattern)
            | Contact.company.ilike(pattern)
            | Contact.notes.ilike(pattern)
        )

    total = query.count()
    contacts = query.order_by(Contact.updated_at.desc()).all()
    return contacts, total


def update_contact(
    db: Session,
    contact_id: int,
    payload: ContactUpdate,
    *,
    profile_id: int | None = None,
) -> Contact:
    """Update a contact with partial data."""
    contact = _get_active_contact(db, contact_id, profile_id=profile_id)
    update_data = payload.model_dump(exclude_unset=True)

    changed_fields = []
    for field, value in update_data.items():
        if field == "tags":
            value = _serialize_tags(value)
        old_val = getattr(contact, field, None)
        if old_val != value:
            changed_fields.append(field)
            setattr(contact, field, value)

    if changed_fields:
        log_activity(
            db,
            profile_id=contact.profile_id,
            action="contact_updated",
            entity_type="contact",
            entity_id=contact.id,
            details=f"Updated fields: {', '.join(changed_fields)}",
        )

    db.commit()
    db.refresh(contact)
    return contact


def archive_contact(db: Session, contact_id: int, *, profile_id: int | None = None) -> Contact:
    """Soft-delete a contact."""
    contact = _get_active_contact(db, contact_id, profile_id=profile_id)
    contact.archived_at = datetime.now(UTC)

    log_activity(
        db,
        profile_id=contact.profile_id,
        action="contact_archived",
        entity_type="contact",
        entity_id=contact.id,
        details=f"Archived contact {contact.name}",
    )
    db.commit()
    db.refresh(contact)
    return contact


# ---------------------------------------------------------------------------
# Interactions
# ---------------------------------------------------------------------------


def create_interaction(
    db: Session,
    contact_id: int,
    payload: InteractionCreate,
    *,
    profile_id: int | None = None,
) -> ContactInteraction:
    """Log an interaction with a contact. Updates last_contacted_at."""
    contact = _get_active_contact(db, contact_id, profile_id=profile_id)

    occurred_at = payload.occurred_at or datetime.now(UTC)

    interaction = ContactInteraction(
        contact_id=contact.id,
        profile_id=contact.profile_id,
        interaction_type=payload.interaction_type,
        direction=payload.direction,
        subject=payload.subject,
        notes=payload.notes,
        occurred_at=occurred_at,
    )
    db.add(interaction)

    # Update last_contacted_at if this interaction is more recent
    # SQLite may strip tzinfo — normalize both sides for comparison
    existing = contact.last_contacted_at
    if existing is not None and existing.tzinfo is None:
        existing = existing.replace(tzinfo=UTC)
    if existing is None or occurred_at > existing:
        contact.last_contacted_at = occurred_at

    log_activity(
        db,
        profile_id=contact.profile_id,
        action="interaction_logged",
        entity_type="contact",
        entity_id=contact.id,
        details=f"{payload.interaction_type} ({payload.direction}) with {contact.name}",
    )
    db.commit()
    db.refresh(interaction)
    return interaction


def list_interactions(
    db: Session, contact_id: int, *, profile_id: int | None = None
) -> list[ContactInteraction]:
    """List interactions for a contact, ordered by occurred_at desc."""
    contact = _get_active_contact(db, contact_id, profile_id=profile_id)
    return (
        db.query(ContactInteraction)
        .filter(ContactInteraction.contact_id == contact.id)
        .order_by(ContactInteraction.occurred_at.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# Contact-Application linking
# ---------------------------------------------------------------------------


def link_contact_to_application(
    db: Session,
    contact_id: int,
    payload: ContactApplicationCreate,
    *,
    profile_id: int | None = None,
) -> ContactApplication:
    """Link a contact to an application."""
    contact = _get_active_contact(db, contact_id, profile_id=profile_id)

    # Verify application exists
    app_filters = [
        Application.id == payload.application_id,
        Application.archived_at.is_(None),
    ]
    if profile_id is not None:
        app_filters.append(Application.profile_id == profile_id)
    app_obj = db.query(Application).filter(*app_filters).first()
    if app_obj is None:
        raise ApplicationNotFoundError(f"Application {payload.application_id} not found")

    # Check for duplicate
    existing = (
        db.query(ContactApplication)
        .filter(
            ContactApplication.contact_id == contact.id,
            ContactApplication.application_id == payload.application_id,
        )
        .first()
    )
    if existing is not None:
        raise DuplicateLinkError(
            f"Contact {contact_id} is already linked to application {payload.application_id}"
        )

    link = ContactApplication(
        contact_id=contact.id,
        application_id=payload.application_id,
        profile_id=contact.profile_id,
        role=payload.role,
        notes=payload.notes,
    )
    db.add(link)

    log_activity(
        db,
        profile_id=contact.profile_id,
        action="contact_linked",
        entity_type="contact",
        entity_id=contact.id,
        application_id=payload.application_id,
        details=f"Linked {contact.name} to application {payload.application_id} as {payload.role}",
    )
    db.commit()
    db.refresh(link)
    return link


def unlink_contact_from_application(
    db: Session,
    contact_id: int,
    application_id: int,
    *,
    profile_id: int | None = None,
) -> None:
    """Remove a contact-application link."""
    contact = _get_active_contact(db, contact_id, profile_id=profile_id)

    link = (
        db.query(ContactApplication)
        .filter(
            ContactApplication.contact_id == contact.id,
            ContactApplication.application_id == application_id,
        )
        .first()
    )
    if link is None:
        raise ContactNotFoundError(
            f"No link between contact {contact_id} and application {application_id}"
        )

    db.delete(link)
    log_activity(
        db,
        profile_id=contact.profile_id,
        action="contact_unlinked",
        entity_type="contact",
        entity_id=contact.id,
        application_id=application_id,
        details=f"Unlinked {contact.name} from application {application_id}",
    )
    db.commit()


def get_contacts_for_application(
    db: Session, application_id: int, *, profile_id: int | None = None
) -> list[dict]:
    """Get all contacts linked to an application (reverse lookup)."""
    query = (
        db.query(Contact, ContactApplication)
        .join(ContactApplication, ContactApplication.contact_id == Contact.id)
        .filter(
            ContactApplication.application_id == application_id,
            Contact.archived_at.is_(None),
        )
    )
    if profile_id is not None:
        query = query.filter(Contact.profile_id == profile_id)

    results = query.all()
    return [
        {"contact": contact, "role": link.role, "notes": link.notes} for contact, link in results
    ]


def get_contacts_by_company(db: Session, company: str, *, profile_id: int) -> list[Contact]:
    """Get all contacts at a specific company."""
    return (
        db.query(Contact)
        .filter(
            Contact.profile_id == profile_id,
            Contact.company.ilike(f"%{company}%"),
            Contact.archived_at.is_(None),
        )
        .order_by(Contact.name)
        .all()
    )
