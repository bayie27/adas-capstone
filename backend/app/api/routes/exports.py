"""07_PKG_reports.md Step 5/6 — async export jobs and the retraining
package. `/api/exports/jobs*` is available to any authenticated user (a
job's owner or an Admin may read/download it); `/api/exports/retraining`
is Admin only.
"""

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.api.dependencies import get_current_admin, get_current_user, get_export_queue
from app.core.db import get_session
from app.core.errors import AppHTTPException
from app.models import ExportJob, User, UserRole
from app.schemas import (
    ExportJobCreate,
    ExportJobCreateResponse,
    ExportJobRead,
    RetrainingExportRequest,
)
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
    worker actually finishes (success or failure), not at creation."""
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
