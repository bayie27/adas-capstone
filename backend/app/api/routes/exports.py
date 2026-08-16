"""07_PKG_reports.md Step 5/6 — async export jobs and the retraining
package. `/api/exports/jobs*` is available to any authenticated user (a
job's owner or an Admin may read/download it); `/api/exports/retraining`
is Admin only.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlmodel import Session, col, func, select

from app.api.dependencies import get_current_admin, get_current_user, get_export_queue
from app.core.db import get_session
from app.core.errors import AppHTTPException
from app.models import ExportJob, User, UserRole
from app.schemas import (
    ExportJobCreate,
    ExportJobCreateResponse,
    ExportJobListResponse,
    ExportJobRead,
    RetrainingExportRequest,
)
from app.schemas.exports import ExportJobStatus
from app.services.reports.jobs import ExportJobQueue, create_job

router = APIRouter(prefix="/api/exports", tags=["Exports"])


def _job_filters_dict(payload: ExportJobCreate) -> dict:
    return {
        "start_date": payload.start_date.isoformat() if payload.start_date else None,
        "end_date": payload.end_date.isoformat() if payload.end_date else None,
        "status": payload.status or [],
        "camera_id": payload.camera_id or [],
        "user_id": payload.user_id or [],
        "search": payload.search,
        "action": payload.action or [],
        "result": payload.result or [],
        "target_type": payload.target_type or [],
    }


def _job_sort_dict(payload: ExportJobCreate) -> dict | None:
    if payload.sort_by is None and payload.sort_order is None:
        return None
    return {
        "sort_by": payload.sort_by or "detected_at",
        "sort_order": payload.sort_order or "desc",
    }


@router.post("/jobs", response_model=ExportJobCreateResponse, status_code=202)
async def create_export_job(
    payload: ExportJobCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    queue: ExportJobQueue = Depends(get_export_queue),
):
    """Large or heavy exports bypass the synchronous row limits by going
    through here instead of `?format=`. Returns immediately with
    `queued` — the REPORT_EXPORT/AUDIT_EXPORT audit row is written when the
    worker actually finishes (success or failure), not at creation.

    `report_type="audit"` is Admin only, matching the synchronous
    `/api/audit-logs/export` route (`get_current_admin`) — `/api/audit-logs`
    itself is Admin only (01_CONTRACTS.md §5.7), and this async path must
    not become a side door around that for an Operator, who would otherwise
    both create *and*, as the job's owner, download it."""
    if payload.report_type == "audit" and current_user.role != UserRole.ADMIN:
        raise AppHTTPException(
            403,
            "Only an Admin may create an audit-log export job.",
            code="FORBIDDEN",
        )

    job = create_job(
        session,
        requested_by=current_user,
        report_type=payload.report_type,
        format=payload.format,
        filters=_job_filters_dict(payload),
        sort=_job_sort_dict(payload),
    )
    session.commit()
    session.refresh(job)
    await queue.enqueue(job.job_id)
    return ExportJobCreateResponse(job_id=job.job_id, status=job.status)


def _to_export_job_read(job: ExportJob) -> ExportJobRead:
    return ExportJobRead(
        job_id=job.job_id,
        report_type=job.report_type,
        format=job.format,
        status=job.status,
        progress_current=job.progress_current,
        progress_total=job.progress_total,
        failure_category=job.failure_category,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        expires_at=job.expires_at,
    )


@router.get("/jobs", response_model=ExportJobListResponse)
def list_export_jobs(
    status: list[ExportJobStatus] | None = Query(default=None),
    all_users: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """01_CONTRACTS.md §5.10 (P21 Step 4) — own jobs by default for every
    role, including Admin: an admin's own tray answers "where is my
    export?", not the whole system's. `?all_users=true` widens it, Admin
    only — an Operator passing it gets 403. `expired` jobs are included:
    that status is exactly what an operator is investigating when a
    download stops working. Not audited — routine viewing."""
    if all_users and current_user.role != UserRole.ADMIN:
        raise AppHTTPException(
            403,
            "Only an Admin may list every user's export jobs.",
            code="FORBIDDEN",
        )

    query = select(ExportJob)
    if not all_users:
        query = query.where(col(ExportJob.requested_by_id) == current_user.user_id)
    if status:
        query = query.where(col(ExportJob.status).in_(status))
    query = query.order_by(col(ExportJob.created_at).desc())

    total_filtered = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()
    jobs = session.exec(query.offset(offset).limit(limit)).all()

    return ExportJobListResponse(
        total_filtered=total_filtered,
        items=[_to_export_job_read(job) for job in jobs],
    )


def _get_job_or_404(session: Session, job_id: str) -> ExportJob:
    job = session.get(ExportJob, job_id)
    if job is None:
        raise AppHTTPException(404, "Export job not found.", code="NOT_FOUND")
    return job


def _require_owner_or_admin(job: ExportJob, current_user: User) -> None:
    if (
        job.requested_by_id != current_user.user_id
        and current_user.role != UserRole.ADMIN
    ):
        raise AppHTTPException(
            403,
            "Only the requesting user or an Admin may access this export job.",
            code="FORBIDDEN",
        )


@router.get("/jobs/{job_id}", response_model=ExportJobRead)
def get_export_job(
    job_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    job = _get_job_or_404(session, job_id)
    _require_owner_or_admin(job, current_user)
    return _to_export_job_read(job)


@router.get("/jobs/{job_id}/download")
def download_export_job(
    job_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    job = _get_job_or_404(session, job_id)
    _require_owner_or_admin(job, current_user)

    if job.status != "completed" or not job.artifact_path:
        raise AppHTTPException(
            404,
            "This export job has no artifact available for download yet.",
            code="NOT_FOUND",
        )

    artifact_path = Path(job.artifact_path)
    if not artifact_path.exists():
        raise AppHTTPException(
            404, "The export artifact is no longer available.", code="NOT_FOUND"
        )

    media_types = {
        "csv": "text/csv",
        "pdf": "application/pdf",
        "zip": "application/zip",
    }
    filename = f"adas_{job.report_type}_export.{job.format}"
    return FileResponse(
        artifact_path,
        media_type=media_types.get(job.format, "application/octet-stream"),
        filename=filename,
    )


@router.post("/retraining", response_model=ExportJobCreateResponse, status_code=202)
async def create_retraining_export(
    payload: RetrainingExportRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_admin),
    queue: ExportJobQueue = Depends(get_export_queue),
):
    """D-010 — always an async job (never synchronous): the retraining
    package is snapshot-heavy by nature. Admin only."""
    job = create_job(
        session,
        requested_by=current_user,
        report_type="retraining",
        format="zip",
        filters={
            "start_date": payload.start_date.isoformat()
            if payload.start_date
            else None,
            "end_date": payload.end_date.isoformat() if payload.end_date else None,
            "camera_id": payload.camera_id or [],
        },
    )
    session.commit()
    session.refresh(job)
    await queue.enqueue(job.job_id)
    return ExportJobCreateResponse(job_id=job.job_id, status=job.status)
