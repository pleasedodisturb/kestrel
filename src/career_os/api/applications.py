"""Application pipeline CRUD API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from career_os.api.constants import DESC_ACTIVE_PROFILE_ID
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


@router.post("", status_code=201)
async def create(
    payload: ApplicationCreate,
    db: Session = Depends(get_db),
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
    profile_id: int = Query(..., description="Profile to list applications for"),
    status: str | None = Query(default=None, description="Filter by status"),
    search: str | None = Query(default=None, description="Search by company name"),
    sort: str | None = Query(default=None, description="Sort field: 'score' or 'date'"),
    order: str = Query(default="desc", description="Sort order: 'asc' or 'desc'"),
    ghost_alert: bool = Query(default=False, description="Filter to ghost candidates only"),
    applied_threshold: int = Query(default=14, description="Applied ghost threshold (days)"),
    interviewing_threshold: int = Query(
        default=7, description="Interviewing ghost threshold (days)"
    ),
    db: Session = Depends(get_db),
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


@router.get("/{application_id}")
async def get_detail(
    application_id: int,
    profile_id: int = Query(..., description=DESC_ACTIVE_PROFILE_ID),
    db: Session = Depends(get_db),
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

    # Build packages list with derived fields
    packages_list = []
    for pkg in app_obj.packages:
        # Derive a readable package_name from the directory path
        pkg_dir = pkg.package_dir or ""
        package_name = pkg_dir.rstrip("/").split("/")[-1] if pkg_dir else "Unknown"
        # Determine package_type from available files
        if pkg.cover_letter_path and pkg.cv_path:
            package_type = "full"
        elif pkg.cover_letter_path:
            package_type = "cover_letter"
        elif pkg.cv_path:
            package_type = "cv"
        else:
            package_type = "directory"
        packages_list.append(
            ApplicationPackageSummaryResponse(
                id=pkg.id,
                package_name=package_name,
                file_path=pkg_dir,
                package_type=package_type,
            )
        )

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


@router.patch("/{application_id}")
async def update(
    application_id: int,
    payload: ApplicationUpdate,
    profile_id: int = Query(..., description=DESC_ACTIVE_PROFILE_ID),
    db: Session = Depends(get_db),
) -> ApplicationResponse:
    """Update an application.

    Returns 404 if the application does not belong to the given profile.
    Status changes are validated against the workflow:
    discovered→interested→applied→interviewing→offer→accepted/rejected.
    Any status can transition to ghosted.  Only offer→rejected is valid
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


@router.delete("/{application_id}")
async def delete(
    application_id: int,
    profile_id: int = Query(..., description=DESC_ACTIVE_PROFILE_ID),
    db: Session = Depends(get_db),
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
