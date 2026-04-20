"""Application pipeline CRUD API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from career_os.api.constants import DESC_ACTIVE_PROFILE_ID, RESP_404, RESP_404_422
from career_os.database import get_db
from career_os.schemas.applications import (
    ActivityLogResponse,
    ApplicationCreate,
    ApplicationDetailResponse,
    ApplicationListResponse,
    ApplicationPackageSummaryResponse,
    ApplicationResponse,
    ApplicationUpdate,
    FollowUpSummaryResponse,
)
from career_os.schemas.constraints import INT32_MAX
from career_os.services.applications import (
    ApplicationNotFoundError,
    InvalidStatusTransitionError,
    ProfileNotFoundError,
    create_application,
    delete_application,
    get_application,
    list_applications,
    update_application,
)
from career_os.services.follow_ups import (
    get_ghost_applications,
    is_ghost_application,
)
from career_os.services.gap_analysis import get_readiness_score

router = APIRouter(prefix="/api/applications", tags=["applications"])


def _enrich_with_readiness(app_response: ApplicationResponse, db: Session) -> ApplicationResponse:
    """Add readiness_score to an ApplicationResponse if job requirements exist."""
    score = get_readiness_score(db, app_response.id, app_response.profile_id)
    if score is not None:
        app_response.readiness_score = score
    return app_response


def _derive_package_type(pkg) -> str:
    if pkg.cover_letter_path and pkg.cv_path:
        return "full"
    if pkg.cover_letter_path:
        return "cover_letter"
    if pkg.cv_path:
        return "cv"
    return "directory"


def _build_package_summary(pkg) -> ApplicationPackageSummaryResponse:
    pkg_dir = pkg.package_dir or ""
    package_name = pkg_dir.rstrip("/").split("/")[-1] if pkg_dir else "Unknown"
    return ApplicationPackageSummaryResponse(
        id=pkg.id,
        package_name=package_name,
        file_path=pkg_dir,
        package_type=_derive_package_type(pkg),
    )


@router.post("", status_code=201, responses=RESP_404)
async def create(
    payload: ApplicationCreate,
    db: Annotated[Session, Depends(get_db)],
) -> ApplicationResponse:
    """Create a new application.

    The application starts in 'discovered' status.
    An activity log entry is auto-created.
    """
    try:
        app_obj = create_application(db, payload)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApplicationResponse.model_validate(app_obj)


@router.get("")
async def list_apps(
    profile_id: Annotated[
        int, Query(ge=1, le=INT32_MAX, description="Profile to list applications for")
    ],
    db: Annotated[Session, Depends(get_db)],
    status: Annotated[str | None, Query(description="Filter by status")] = None,
    search: Annotated[str | None, Query(description="Search by company name")] = None,
    sort: Annotated[str | None, Query(description="Sort field: 'score' or 'date'")] = None,
    order: Annotated[str, Query(description="Sort order: 'asc' or 'desc'")] = "desc",
    ghost_alert: Annotated[bool, Query(description="Filter to ghost candidates only")] = False,
    applied_threshold: Annotated[
        int, Query(ge=1, le=3650, description="Applied ghost threshold (days)")
    ] = 14,
    interviewing_threshold: Annotated[
        int, Query(ge=1, le=3650, description="Interviewing ghost threshold (days)")
    ] = 7,
) -> ApplicationListResponse:
    """List applications with optional filters and sorting.

    Excludes archived applications.
    When ghost_alert=true, returns only ghost candidates (applications
    past their status-specific inactivity threshold).
    """
    if ghost_alert:
        ghosts = get_ghost_applications(
            db,
            profile_id=profile_id,
            applied_threshold_days=applied_threshold,
            interviewing_threshold_days=interviewing_threshold,
        )
        return ApplicationListResponse(
            applications=[
                _enrich_with_readiness(
                    ApplicationResponse(
                        **ApplicationResponse.model_validate(a).model_dump(
                            exclude={"is_ghost", "readiness_score"}
                        ),
                        is_ghost=True,
                    ),
                    db,
                )
                for a in ghosts
            ],
            total=len(ghosts),
        )

    apps, total = list_applications(
        db,
        profile_id=profile_id,
        status=status,
        search=search,
        sort=sort,
        order=order,
    )
    return ApplicationListResponse(
        applications=[
            _enrich_with_readiness(
                ApplicationResponse(
                    **ApplicationResponse.model_validate(a).model_dump(
                        exclude={"is_ghost", "readiness_score"}
                    ),
                    is_ghost=is_ghost_application(a),
                ),
                db,
            )
            for a in apps
        ],
        total=total,
    )


@router.get("/{application_id}", responses=RESP_404)
async def get_detail(
    application_id: Annotated[int, Path(ge=1, le=INT32_MAX)],
    profile_id: Annotated[int, Query(ge=1, le=INT32_MAX, description=DESC_ACTIVE_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> ApplicationDetailResponse:
    """Get application detail including activity log and follow-ups.

    Returns 404 if the application does not belong to the given profile.
    """
    try:
        app_obj = get_application(db, application_id, profile_id=profile_id)
    except ApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Build activity log in reverse chronological order
    activity_log_sorted = sorted(app_obj.activity_logs, key=lambda x: x.created_at, reverse=True)

    # Include follow-ups sorted by due date
    follow_ups_sorted = sorted(app_obj.follow_ups, key=lambda x: x.due_date)

    packages_list = [_build_package_summary(pkg) for pkg in app_obj.packages]

    # Compute readiness score if requirements exist
    readiness = get_readiness_score(db, app_obj.id, app_obj.profile_id)

    return ApplicationDetailResponse(
        **ApplicationResponse.model_validate(app_obj).model_dump(
            exclude={"is_ghost", "readiness_score"}
        ),
        is_ghost=is_ghost_application(app_obj),
        readiness_score=readiness,
        activity_log=[ActivityLogResponse.model_validate(log) for log in activity_log_sorted],
        follow_ups=[FollowUpSummaryResponse.model_validate(fu) for fu in follow_ups_sorted],
        packages=packages_list,
    )


@router.patch(
    "/{application_id}",
    responses=RESP_404_422,
)
async def update(
    application_id: Annotated[int, Path(ge=1, le=INT32_MAX)],
    payload: ApplicationUpdate,
    profile_id: Annotated[int, Query(ge=1, le=INT32_MAX, description=DESC_ACTIVE_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> ApplicationResponse:
    """Update an application.

    Returns 404 if the application does not belong to the given profile.
    Status changes are validated against the workflow:
    discovered->interested->applied->interviewing->offer->accepted/rejected.
    Any status can transition to ghosted.  Only offer->rejected is valid
    (pre-offer states cannot transition directly to rejected).
    Invalid transitions return 422.  Status values are normalized to
    lowercase (title-cased Kanban DnD values are accepted).
    """
    try:
        app_obj = update_application(db, application_id, payload, profile_id=profile_id)
    except ApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidStatusTransitionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ApplicationResponse.model_validate(app_obj)


@router.delete("/{application_id}", responses=RESP_404)
async def delete(
    application_id: Annotated[int, Path(ge=1, le=INT32_MAX)],
    profile_id: Annotated[int, Query(ge=1, le=INT32_MAX, description=DESC_ACTIVE_PROFILE_ID)],
    db: Annotated[Session, Depends(get_db)],
) -> ApplicationResponse:
    """Soft-delete (archive) an application.

    Returns 404 if the application does not belong to the given profile.
    Sets archived_at timestamp. Does not destroy related data.
    """
    try:
        app_obj = delete_application(db, application_id, profile_id=profile_id)
    except ApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApplicationResponse.model_validate(app_obj)
