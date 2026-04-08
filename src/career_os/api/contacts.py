"""API routes for Networking CRM (M6) — contacts, interactions, linking."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from career_os.database import get_db
from career_os.schemas.contacts import (
    ContactApplicationCreate,
    ContactApplicationResponse,
    ContactCreate,
    ContactDetailResponse,
    ContactListResponse,
    ContactResponse,
    ContactUpdate,
    InteractionCreate,
    InteractionListResponse,
    InteractionResponse,
)
from career_os.services.contacts import (
    ApplicationNotFoundError,
    ContactNotFoundError,
    DuplicateLinkError,
    ProfileNotFoundError,
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

router = APIRouter(prefix="/api", tags=["contacts"])


# ---------------------------------------------------------------------------
# Contact CRUD
# ---------------------------------------------------------------------------


@router.post("/contacts", response_model=ContactResponse, status_code=201)
async def create(
    payload: ContactCreate,
    db: Session = Depends(get_db),
) -> ContactResponse:
    """Create a new contact."""
    try:
        contact = create_contact(db, payload)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ContactResponse.model_validate(contact)


@router.get("/contacts", response_model=ContactListResponse)
async def list_all(
    profile_id: int = Query(..., description="Profile to list contacts for"),
    company: str | None = Query(default=None, description="Filter by company"),
    relationship_type: str | None = Query(default=None, description="Filter by type"),
    warmth: str | None = Query(default=None, description="Filter by warmth"),
    needs_follow_up: bool = Query(default=False, description="Show overdue follow-ups only"),
    search: str | None = Query(default=None, description="Search name/company/notes"),
    db: Session = Depends(get_db),
) -> ContactListResponse:
    """List contacts with optional filters."""
    contacts, total = list_contacts(
        db,
        profile_id=profile_id,
        company=company,
        relationship_type=relationship_type,
        warmth=warmth,
        needs_follow_up=needs_follow_up,
        search=search,
    )
    return ContactListResponse(
        contacts=[ContactResponse.model_validate(c) for c in contacts],
        total=total,
    )


@router.get("/contacts/by-company/{company}", response_model=ContactListResponse)
async def contacts_at_company(
    company: str,
    profile_id: int = Query(..., description="Active profile ID"),
    db: Session = Depends(get_db),
) -> ContactListResponse:
    """Get all contacts at a company."""
    contacts = get_contacts_by_company(db, company, profile_id=profile_id)
    return ContactListResponse(
        contacts=[ContactResponse.model_validate(c) for c in contacts],
        total=len(contacts),
    )


@router.get("/contacts/{contact_id}", response_model=ContactDetailResponse)
async def get_detail(
    contact_id: int,
    profile_id: int = Query(..., description="Active profile ID"),
    db: Session = Depends(get_db),
) -> ContactDetailResponse:
    """Get contact detail with interactions and linked applications."""
    try:
        contact = get_contact(db, contact_id, profile_id=profile_id)
    except ContactNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    interactions = list_interactions(db, contact_id, profile_id=profile_id)
    from career_os.models.contacts import ContactApplication

    links = (
        db.query(ContactApplication)
        .filter(ContactApplication.contact_id == contact_id)
        .all()
    )

    return ContactDetailResponse(
        **ContactResponse.model_validate(contact).model_dump(),
        interactions=[InteractionResponse.model_validate(i) for i in interactions],
        linked_applications=[ContactApplicationResponse.model_validate(l) for l in links],
    )


@router.patch("/contacts/{contact_id}", response_model=ContactResponse)
async def update(
    contact_id: int,
    payload: ContactUpdate,
    profile_id: int = Query(..., description="Active profile ID"),
    db: Session = Depends(get_db),
) -> ContactResponse:
    """Update a contact."""
    try:
        contact = update_contact(db, contact_id, payload, profile_id=profile_id)
    except ContactNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ContactResponse.model_validate(contact)


@router.delete("/contacts/{contact_id}", status_code=204)
async def delete(
    contact_id: int,
    profile_id: int = Query(..., description="Active profile ID"),
    db: Session = Depends(get_db),
) -> None:
    """Soft-delete a contact."""
    try:
        archive_contact(db, contact_id, profile_id=profile_id)
    except ContactNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Interactions
# ---------------------------------------------------------------------------


@router.post(
    "/contacts/{contact_id}/interactions",
    response_model=InteractionResponse,
    status_code=201,
)
async def log_interaction(
    contact_id: int,
    payload: InteractionCreate,
    profile_id: int = Query(..., description="Active profile ID"),
    db: Session = Depends(get_db),
) -> InteractionResponse:
    """Log an interaction with a contact."""
    try:
        interaction = create_interaction(db, contact_id, payload, profile_id=profile_id)
    except ContactNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return InteractionResponse.model_validate(interaction)


@router.get(
    "/contacts/{contact_id}/interactions",
    response_model=InteractionListResponse,
)
async def get_interactions(
    contact_id: int,
    profile_id: int = Query(..., description="Active profile ID"),
    db: Session = Depends(get_db),
) -> InteractionListResponse:
    """List interactions for a contact."""
    try:
        interactions = list_interactions(db, contact_id, profile_id=profile_id)
    except ContactNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return InteractionListResponse(
        interactions=[InteractionResponse.model_validate(i) for i in interactions],
        total=len(interactions),
    )


# ---------------------------------------------------------------------------
# Contact-Application linking
# ---------------------------------------------------------------------------


@router.post(
    "/contacts/{contact_id}/applications",
    response_model=ContactApplicationResponse,
    status_code=201,
)
async def link_application(
    contact_id: int,
    payload: ContactApplicationCreate,
    profile_id: int = Query(..., description="Active profile ID"),
    db: Session = Depends(get_db),
) -> ContactApplicationResponse:
    """Link a contact to an application."""
    try:
        link = link_contact_to_application(db, contact_id, payload, profile_id=profile_id)
    except ContactNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DuplicateLinkError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ContactApplicationResponse.model_validate(link)


@router.get("/contacts/{contact_id}/applications")
async def get_linked_applications(
    contact_id: int,
    profile_id: int = Query(..., description="Active profile ID"),
    db: Session = Depends(get_db),
):
    """List applications linked to a contact."""
    try:
        get_contact(db, contact_id, profile_id=profile_id)
    except ContactNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    from career_os.models.contacts import ContactApplication

    links = (
        db.query(ContactApplication)
        .filter(ContactApplication.contact_id == contact_id)
        .all()
    )
    return [ContactApplicationResponse.model_validate(l) for l in links]


@router.delete(
    "/contacts/{contact_id}/applications/{application_id}", status_code=204
)
async def unlink_application(
    contact_id: int,
    application_id: int,
    profile_id: int = Query(..., description="Active profile ID"),
    db: Session = Depends(get_db),
) -> None:
    """Unlink a contact from an application."""
    try:
        unlink_contact_from_application(db, contact_id, application_id, profile_id=profile_id)
    except ContactNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Reverse lookups
# ---------------------------------------------------------------------------


@router.get("/applications/{application_id}/contacts")
async def get_application_contacts(
    application_id: int,
    profile_id: int = Query(..., description="Active profile ID"),
    db: Session = Depends(get_db),
):
    """Get contacts linked to an application (reverse lookup)."""
    results = get_contacts_for_application(db, application_id, profile_id=profile_id)
    return [
        {
            "contact": ContactResponse.model_validate(r["contact"]).model_dump(),
            "role": r["role"],
            "notes": r["notes"],
        }
        for r in results
    ]
