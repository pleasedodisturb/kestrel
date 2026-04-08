"""Unit tests for Contact service layer (M6 Networking CRM) — 20 tests per spec §3.6."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.database import Base
from career_os.models.models import Application, Profile
from career_os.schemas.contacts import (
    ContactApplicationCreate,
    ContactCreate,
    ContactUpdate,
    InteractionCreate,
)
from career_os.services.contacts import (
    ContactNotFoundError,
    DuplicateLinkError,
    archive_contact,
    create_contact,
    create_interaction,
    get_contact,
    get_contacts_by_company,
    get_contacts_for_application,
    link_contact_to_application,
    list_contacts,
    list_interactions,
    unlink_contact_from_application,
    update_contact,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    connection = engine.connect()
    session = sessionmaker(bind=connection, autocommit=False, autoflush=False)()

    # Seed profiles
    session.add(Profile(id=1, name="Test User", email="test@example.com"))
    session.add(Profile(id=2, name="Other User", email="other@example.com"))
    session.commit()

    yield session
    session.close()
    connection.close()
    engine.dispose()


@pytest.fixture
def sample_app(db: Session) -> Application:
    app_obj = Application(profile_id=1, company="Mistral", role="Sr TPM", status="applied")
    db.add(app_obj)
    db.commit()
    db.refresh(app_obj)
    return app_obj


# ---------------------------------------------------------------------------
# 1. create_contact with all fields
# ---------------------------------------------------------------------------


def test_create_contact_all_fields(db: Session):
    contact = create_contact(
        db,
        ContactCreate(
            profile_id=1,
            name="Jane Doe",
            company="Mistral",
            role="Hiring Manager",
            email="jane@mistral.ai",
            linkedin_url="https://linkedin.com/in/jane",
            phone="+49123456",
            relationship_type="referral",
            referral_status="contacted",
            warmth="hot",
            notes="Met at conference",
            tags=["ai", "tpm"],
            source="conference",
        ),
    )
    assert contact.id is not None
    assert contact.name == "Jane Doe"
    assert contact.company == "Mistral"
    assert contact.relationship_type == "referral"
    assert contact.warmth == "hot"
    assert contact.email == "jane@mistral.ai"


# ---------------------------------------------------------------------------
# 2. create_contact minimal fields
# ---------------------------------------------------------------------------


def test_create_contact_minimal(db: Session):
    contact = create_contact(db, ContactCreate(profile_id=1, name="Minimal Contact"))
    assert contact.id is not None
    assert contact.name == "Minimal Contact"
    assert contact.relationship_type == "other"
    assert contact.warmth == "cold"
    assert contact.company is None


# ---------------------------------------------------------------------------
# 3. list_contacts filters by profile_id
# ---------------------------------------------------------------------------


def test_list_contacts_profile_scoped(db: Session):
    create_contact(db, ContactCreate(profile_id=1, name="P1 Contact"))
    create_contact(db, ContactCreate(profile_id=2, name="P2 Contact"))

    contacts, total = list_contacts(db, profile_id=1)
    assert total == 1
    assert contacts[0].name == "P1 Contact"


# ---------------------------------------------------------------------------
# 4. list_contacts filters by company (case-insensitive)
# ---------------------------------------------------------------------------


def test_list_contacts_filter_company(db: Session):
    create_contact(db, ContactCreate(profile_id=1, name="A", company="Mistral AI"))
    create_contact(db, ContactCreate(profile_id=1, name="B", company="Linear"))

    contacts, total = list_contacts(db, profile_id=1, company="mistral")
    assert total == 1
    assert contacts[0].company == "Mistral AI"


# ---------------------------------------------------------------------------
# 5. list_contacts filters by relationship_type
# ---------------------------------------------------------------------------


def test_list_contacts_filter_relationship_type(db: Session):
    create_contact(
        db,
        ContactCreate(profile_id=1, name="Ref", relationship_type="referral"),
    )
    create_contact(
        db,
        ContactCreate(profile_id=1, name="Rec", relationship_type="recruiter"),
    )

    contacts, total = list_contacts(db, profile_id=1, relationship_type="referral")
    assert total == 1
    assert contacts[0].name == "Ref"


# ---------------------------------------------------------------------------
# 6. list_contacts filters by warmth
# ---------------------------------------------------------------------------


def test_list_contacts_filter_warmth(db: Session):
    create_contact(db, ContactCreate(profile_id=1, name="Hot", warmth="hot"))
    create_contact(db, ContactCreate(profile_id=1, name="Cold", warmth="cold"))

    contacts, total = list_contacts(db, profile_id=1, warmth="hot")
    assert total == 1
    assert contacts[0].name == "Hot"


# ---------------------------------------------------------------------------
# 7. list_contacts needs_follow_up
# ---------------------------------------------------------------------------


def test_list_contacts_needs_follow_up(db: Session):
    past = datetime.now(UTC) - timedelta(days=1)
    future = datetime.now(UTC) + timedelta(days=7)

    create_contact(
        db,
        ContactCreate(profile_id=1, name="Overdue", next_follow_up=past),
    )
    create_contact(
        db,
        ContactCreate(profile_id=1, name="Future", next_follow_up=future),
    )
    create_contact(db, ContactCreate(profile_id=1, name="No FU"))

    contacts, total = list_contacts(db, profile_id=1, needs_follow_up=True)
    assert total == 1
    assert contacts[0].name == "Overdue"


# ---------------------------------------------------------------------------
# 8. list_contacts search (name, company, notes)
# ---------------------------------------------------------------------------


def test_list_contacts_search(db: Session):
    create_contact(
        db,
        ContactCreate(profile_id=1, name="Alice Smith", company="Acme"),
    )
    create_contact(
        db,
        ContactCreate(profile_id=1, name="Bob", notes="Met alice at event"),
    )
    create_contact(db, ContactCreate(profile_id=1, name="Charlie"))

    contacts, total = list_contacts(db, profile_id=1, search="alice")
    assert total == 2  # matches name "Alice" and notes "alice"


# ---------------------------------------------------------------------------
# 9. update_contact changes fields
# ---------------------------------------------------------------------------


def test_update_contact(db: Session):
    contact = create_contact(db, ContactCreate(profile_id=1, name="Jane", warmth="cold"))

    updated = update_contact(db, contact.id, ContactUpdate(warmth="hot", company="NewCo"))
    assert updated.warmth == "hot"
    assert updated.company == "NewCo"
    assert updated.name == "Jane"  # unchanged


# ---------------------------------------------------------------------------
# 10. update_contact referral_status validates enum
# ---------------------------------------------------------------------------


def test_update_contact_referral_status(db: Session):
    contact = create_contact(db, ContactCreate(profile_id=1, name="Jane"))

    updated = update_contact(db, contact.id, ContactUpdate(referral_status="cv_sent"))
    assert updated.referral_status == "cv_sent"

    with pytest.raises(Exception):  # Pydantic validation
        ContactUpdate(referral_status="invalid_status")


# ---------------------------------------------------------------------------
# 11. archive_contact
# ---------------------------------------------------------------------------


def test_archive_contact(db: Session):
    contact = create_contact(db, ContactCreate(profile_id=1, name="Jane"))
    archived = archive_contact(db, contact.id)

    assert archived.archived_at is not None

    # Should not appear in list
    contacts, total = list_contacts(db, profile_id=1)
    assert total == 0


# ---------------------------------------------------------------------------
# 12. create_interaction updates last_contacted_at
# ---------------------------------------------------------------------------


def test_create_interaction_updates_last_contacted(db: Session):
    contact = create_contact(db, ContactCreate(profile_id=1, name="Jane"))
    assert contact.last_contacted_at is None

    interaction = create_interaction(
        db,
        contact.id,
        InteractionCreate(interaction_type="email", direction="outbound", notes="Sent CV"),
    )
    db.refresh(contact)

    assert contact.last_contacted_at is not None
    assert interaction.interaction_type == "email"
    assert interaction.direction == "outbound"


# ---------------------------------------------------------------------------
# 13. list_interactions ordered by occurred_at desc
# ---------------------------------------------------------------------------


def test_list_interactions_ordered(db: Session):
    contact = create_contact(db, ContactCreate(profile_id=1, name="Jane"))

    t1 = datetime(2026, 3, 1, tzinfo=UTC)
    t2 = datetime(2026, 3, 10, tzinfo=UTC)

    create_interaction(
        db,
        contact.id,
        InteractionCreate(interaction_type="email", direction="outbound", occurred_at=t1),
    )
    create_interaction(
        db,
        contact.id,
        InteractionCreate(interaction_type="call", direction="inbound", occurred_at=t2),
    )

    interactions = list_interactions(db, contact.id)
    assert len(interactions) == 2
    assert interactions[0].occurred_at > interactions[1].occurred_at


# ---------------------------------------------------------------------------
# 14. link_contact_to_application
# ---------------------------------------------------------------------------


def test_link_contact_to_application(db: Session, sample_app: Application):
    contact = create_contact(db, ContactCreate(profile_id=1, name="Jane", company="Mistral"))

    link = link_contact_to_application(
        db,
        contact.id,
        ContactApplicationCreate(application_id=sample_app.id, role="referrer"),
    )
    assert link.contact_id == contact.id
    assert link.application_id == sample_app.id
    assert link.role == "referrer"


# ---------------------------------------------------------------------------
# 15. link_contact_duplicate raises DuplicateLinkError
# ---------------------------------------------------------------------------


def test_link_contact_duplicate(db: Session, sample_app: Application):
    contact = create_contact(db, ContactCreate(profile_id=1, name="Jane"))

    link_contact_to_application(
        db,
        contact.id,
        ContactApplicationCreate(application_id=sample_app.id, role="referrer"),
    )

    with pytest.raises(DuplicateLinkError):
        link_contact_to_application(
            db,
            contact.id,
            ContactApplicationCreate(application_id=sample_app.id, role="insider"),
        )


# ---------------------------------------------------------------------------
# 16. unlink_contact
# ---------------------------------------------------------------------------


def test_unlink_contact(db: Session, sample_app: Application):
    contact = create_contact(db, ContactCreate(profile_id=1, name="Jane"))

    link_contact_to_application(
        db,
        contact.id,
        ContactApplicationCreate(application_id=sample_app.id, role="referrer"),
    )

    unlink_contact_from_application(db, contact.id, sample_app.id)

    # Verify unlinked
    results = get_contacts_for_application(db, sample_app.id)
    assert len(results) == 0


# ---------------------------------------------------------------------------
# 17. contacts_by_company
# ---------------------------------------------------------------------------


def test_contacts_by_company(db: Session):
    create_contact(db, ContactCreate(profile_id=1, name="A", company="Mistral AI"))
    create_contact(db, ContactCreate(profile_id=1, name="B", company="Mistral AI"))
    create_contact(db, ContactCreate(profile_id=1, name="C", company="Linear"))

    results = get_contacts_by_company(db, "Mistral", profile_id=1)
    assert len(results) == 2


# ---------------------------------------------------------------------------
# 18. contacts_for_application (reverse lookup)
# ---------------------------------------------------------------------------


def test_contacts_for_application(db: Session, sample_app: Application):
    c1 = create_contact(db, ContactCreate(profile_id=1, name="Jane"))
    c2 = create_contact(db, ContactCreate(profile_id=1, name="Bob"))

    link_contact_to_application(
        db,
        c1.id,
        ContactApplicationCreate(application_id=sample_app.id, role="referrer"),
    )
    link_contact_to_application(
        db,
        c2.id,
        ContactApplicationCreate(application_id=sample_app.id, role="insider"),
    )

    results = get_contacts_for_application(db, sample_app.id)
    assert len(results) == 2
    roles = {r["role"] for r in results}
    assert roles == {"referrer", "insider"}


# ---------------------------------------------------------------------------
# 19. contact_not_found
# ---------------------------------------------------------------------------


def test_contact_not_found(db: Session):
    with pytest.raises(ContactNotFoundError):
        get_contact(db, 999)


# ---------------------------------------------------------------------------
# 20. profile_scoping — contact from profile 2 not visible to profile 1
# ---------------------------------------------------------------------------


def test_profile_scoping(db: Session):
    contact = create_contact(db, ContactCreate(profile_id=2, name="P2 Contact"))

    with pytest.raises(ContactNotFoundError):
        get_contact(db, contact.id, profile_id=1)
