"""07_PKG_reports.md Step 5 — the bounded local export-job worker.

D-010 rejects Celery, Redis, any message broker, and cloud storage for
this deployment: one `asyncio.Queue` plus a small, config-driven number of
worker tasks (`EXPORT_JOB_WORKERS`, default 1) process jobs sequentially
against `EXPORT_DIR`. `process_export_job` is a plain synchronous function
so it can be called directly in tests without touching the queue/worker
machinery at all.

Row-shaping helpers are deliberately reused from the synchronous export
routes (`app.api.routes.alerts/analytics/audit`) rather than duplicated —
an async job must produce byte-identical content to what the matching
`?format=` route would have streamed for the same filters.
"""

import asyncio
import json
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, col, func, select

from app.core.config import settings
from app.models import AuditResult, DetectionLog, DetectionStatus, ExportJob, User
from app.services.filters import IncidentFilters, apply_sort
from app.services.formatting import format_user_name
from app.services.reports.common import record_export_attempt
from app.services.reports.csv_writer import UTF8_BOM, stream_csv
from app.services.reports.pdf_writer import (
    build_audit_pdf,
    build_dashboard_pdf,
    build_incident_pdf,
    build_performance_pdf,
)

logger = logging.getLogger("uvicorn.error")


def _requested_by_name(session: Session, job: ExportJob) -> str:
    user = session.get(User, job.requested_by_id)
    if user is None:
        return "Unknown"
    return format_user_name(user) or user.username


def _filters_dict_from_job(job: ExportJob) -> dict:
    return json.loads(job.filters_json) if job.filters_json else {}


def _sort_dict_from_job(job: ExportJob) -> dict:
    return json.loads(job.sort_json) if job.sort_json else {}


def _incident_filters_from_dict(filters: dict) -> IncidentFilters:
    return IncidentFilters(
        start_date=(
            datetime.fromisoformat(filters["start_date"])
            if filters.get("start_date")
            else None
        ),
        end_date=(
            datetime.fromisoformat(filters["end_date"])
            if filters.get("end_date")
            else None
        ),
        statuses=tuple(DetectionStatus(s) for s in filters.get("status") or ()),
        camera_ids=tuple(filters.get("camera_id") or ()),
        user_ids=tuple(filters.get("user_id") or ()),
        search=filters.get("search"),
    )


def _generate_incidents(session: Session, job: ExportJob) -> tuple[bytes, int]:
    from app.api.routes.alerts import (
        ALERT_SORT_FIELDS,
        INCIDENT_CSV_COLUMNS,
        _filters_summary,
        _incident_csv_row,
        _incident_pdf_row,
        _incident_query_stmt,
    )

    filters_dict = _filters_dict_from_job(job)
    sort_dict = _sort_dict_from_job(job)
    sort_by = sort_dict.get("sort_by", "detected_at")
    sort_order = sort_dict.get("sort_order", "desc")
    filters = _incident_filters_from_dict(filters_dict)

    stmt = apply_sort(
        _incident_query_stmt(filters),
        DetectionLog,
        sort_by=sort_by,
        sort_order=sort_order,
        allowed=ALERT_SORT_FIELDS,
        tie_breaker="log_id",
    )
    logs = session.exec(stmt).all()
    requested_by = _requested_by_name(session, job)
    summary = _filters_summary(filters, sort_by=sort_by, sort_order=sort_order)

    if job.format == "pdf":
        content = build_incident_pdf(
            rows=[_incident_pdf_row(log) for log in logs],
            filters_summary=summary,
            requested_by=requested_by,
            generated_at=datetime.now(UTC),
        )
        return content, len(logs)

    text = UTF8_BOM + "".join(
        stream_csv(INCIDENT_CSV_COLUMNS, (_incident_csv_row(log) for log in logs))
    )
    return text.encode("utf-8"), len(logs)


def _generate_dashboard(session: Session, job: ExportJob) -> tuple[bytes, int]:
    from app.api.routes.analytics import (
        _ACCIDENT_STATUSES,
        _compute_dashboard_data,
        _dashboard_filters_summary,
    )
    from app.services.filters import apply_incident_filters

    filters_dict = _filters_dict_from_job(job)
    start_date = (
        datetime.fromisoformat(filters_dict["start_date"])
        if filters_dict.get("start_date")
        else None
    )
    end_date = (
        datetime.fromisoformat(filters_dict["end_date"])
        if filters_dict.get("end_date")
        else None
    )
    camera_id = filters_dict.get("camera_id") or None
    requested_by = _requested_by_name(session, job)
    summary = _dashboard_filters_summary(
        start_date=start_date, end_date=end_date, camera_id=camera_id
    )

    if job.format == "pdf":
        data = _compute_dashboard_data(
            session, start_date=start_date, end_date=end_date, camera_id=camera_id
        )
        content = build_dashboard_pdf(
            kpis=data["kpis"],
            frequency_by_location=data["frequency_by_location"],
            peak_accident_times=data["peak_accident_times"],
            filters_summary=summary,
            requested_by=requested_by,
            generated_at=datetime.now(UTC),
        )
        return content, len(data["frequency_by_location"])

    from sqlalchemy.orm import selectinload
    from sqlmodel import select as sql_select

    filters = IncidentFilters(
        start_date=start_date, end_date=end_date, camera_ids=tuple(camera_id or ())
    )
    # Filtered directly, not via a materialized id list: `WHERE log_id IN
    # (...)` with tens of thousands of entries exceeds SQLite's default
    # bind-variable limit (999) — found live-drilling a 50,000-row export.
    logs_stmt = apply_incident_filters(
        sql_select(DetectionLog)
        .options(
            selectinload(DetectionLog.camera),
            selectinload(DetectionLog.verified_by),
            selectinload(DetectionLog.closed_by),
        )
        .where(
            col(DetectionLog.detection_status).in_(
                [s.value for s in _ACCIDENT_STATUSES]
            )
        )
        .order_by(col(DetectionLog.detected_at).desc()),
        filters,
    )

    def _row(log: DetectionLog) -> list:
        return [
            log.log_id,
            log.detected_at.isoformat(),
            log.camera_id,
            log.camera.camera_name if log.camera else None,
            log.detection_status,
            log.confidence_score,
            log.verified_by_id,
            format_user_name(log.verified_by),
            log.verified_at.isoformat() if log.verified_at else None,
            log.closed_by_id,
            format_user_name(log.closed_by),
            log.closed_at.isoformat() if log.closed_at else None,
        ]

    logs = session.exec(logs_stmt).all()
    text = UTF8_BOM + "".join(
        stream_csv(
            [
                "Log ID",
                "Detected At",
                "Camera ID",
                "Camera Name",
                "Status",
                "Confidence",
                "Verified By ID",
                "Verified By Name",
                "Verified At",
                "Closed By ID",
                "Closed By Name",
                "Closed At",
            ],
            (_row(log) for log in logs),
        )
    )
    return text.encode("utf-8"), len(logs)


def _generate_performance(session: Session, job: ExportJob) -> tuple[bytes, int]:
    from app.api.routes.analytics import _compute_performance_data

    filters_dict = _filters_dict_from_job(job)
    start_date = (
        datetime.fromisoformat(filters_dict["start_date"])
        if filters_dict.get("start_date")
        else None
    )
    end_date = (
        datetime.fromisoformat(filters_dict["end_date"])
        if filters_dict.get("end_date")
        else None
    )
    camera_id = filters_dict.get("camera_id") or None
    search = filters_dict.get("search")
    requested_by = _requested_by_name(session, job)

    data = _compute_performance_data(
        session,
        start_date=start_date,
        end_date=end_date,
        camera_id=camera_id,
        search=search,
    )
    summary = []
    if start_date or end_date:
        summary.append(
            f"Date range: {start_date.isoformat() if start_date else '…'} "
            f"to {end_date.isoformat() if end_date else '…'}"
        )
    if camera_id:
        summary.append("Camera IDs: " + ", ".join(str(c) for c in camera_id))
    if search:
        summary.append(f"Search: {search!r}")

    if job.format == "pdf":
        content = build_performance_pdf(
            global_kpis=data["global_kpis"],
            per_camera=data["per_camera"],
            filters_summary=summary,
            requested_by=requested_by,
            generated_at=datetime.now(UTC),
        )
        return content, len(data["per_camera"])

    rows = (
        [
            row["camera_id"],
            row["camera_name"],
            row["total_accidents"],
            row["total_dismissed"],
            row["precision_score"],
            row["avg_accident_confidence"],
            row["avg_dismissed_confidence"],
        ]
        for row in data["per_camera"]
    )
    text = UTF8_BOM + "".join(
        stream_csv(
            [
                "Camera ID",
                "Camera Name",
                "Total Accidents",
                "Total Dismissed",
                "Precision Score",
                "Avg Accident Confidence",
                "Avg Dismissed Confidence",
            ],
            rows,
        )
    )
    return text.encode("utf-8"), len(data["per_camera"])


def _generate_audit(session: Session, job: ExportJob) -> tuple[bytes, int]:
    from app.api.routes.audit import (
        AUDIT_SORT_FIELDS,
        _apply_audit_filters,
        _audit_filters_summary,
    )
    from app.models import AuditAction, AuditLog

    filters_dict = _filters_dict_from_job(job)
    sort_dict = _sort_dict_from_job(job)
    sort_by = sort_dict.get("sort_by", "created_at")
    sort_order = sort_dict.get("sort_order", "desc")
    requested_by = _requested_by_name(session, job)

    action = (
        [AuditAction(a) for a in filters_dict.get("action") or ()]
        if filters_dict.get("action")
        else None
    )
    result_filter = (
        [AuditResult(r) for r in filters_dict.get("result") or ()]
        if filters_dict.get("result")
        else None
    )
    start_date = (
        datetime.fromisoformat(filters_dict["start_date"])
        if filters_dict.get("start_date")
        else None
    )
    end_date = (
        datetime.fromisoformat(filters_dict["end_date"])
        if filters_dict.get("end_date")
        else None
    )

    from sqlmodel import select as sql_select

    # Same recursion-trap discipline as the synchronous export, and same
    # watermark (not a materialized id list, which breaks past SQLite's
    # bind-variable limit at scale): captured here, before this job's own
    # AUDIT_EXPORT row is created later in process_export_job.
    watermark = session.exec(select(func.max(AuditLog.audit_id))).one() or 0

    stmt = apply_sort(
        _apply_audit_filters(
            sql_select(AuditLog),
            action=action,
            user_id=filters_dict.get("user_id") or None,
            result=result_filter,
            target_type=filters_dict.get("target_type"),
            target_ref=filters_dict.get("target_ref"),
            start_date=start_date,
            end_date=end_date,
            search=filters_dict.get("search"),
        ).where(col(AuditLog.audit_id) <= watermark),
        AuditLog,
        sort_by=sort_by,
        sort_order=sort_order,
        allowed=AUDIT_SORT_FIELDS,
        tie_breaker="audit_id",
    )
    logs = session.exec(stmt).all()

    def _actor(log: AuditLog) -> str | None:
        if log.username is None:
            return None
        return f"{log.username} ({log.role})" if log.role else log.username

    def _target(log: AuditLog) -> str | None:
        if log.target_type is None and log.target_ref is None:
            return None
        return f"{log.target_type or '?'}:{log.target_ref or '?'}"

    summary = _audit_filters_summary(
        filters_dict, sort_by=sort_by, sort_order=sort_order
    )

    if job.format == "pdf":
        content = build_audit_pdf(
            rows=[
                [
                    log.audit_id,
                    log.created_at.isoformat(),
                    _actor(log),
                    log.action,
                    _target(log),
                    log.result,
                    log.detail,
                ]
                for log in logs
            ],
            filters_summary=summary,
            requested_by=requested_by,
            generated_at=datetime.now(UTC),
        )
        return content, len(logs)

    rows = (
        [
            log.audit_id,
            log.created_at.isoformat(),
            _actor(log),
            log.action,
            _target(log),
            log.result,
            log.detail,
        ]
        for log in logs
    )
    text = UTF8_BOM + "".join(
        stream_csv(
            ["Audit ID", "Created At", "Actor", "Action", "Target", "Result", "Detail"],
            rows,
        )
    )
    return text.encode("utf-8"), len(logs)


_RETRAINING_STATUSES = (
    DetectionStatus.ONGOING,
    DetectionStatus.RESOLVED,
    DetectionStatus.DISMISSED,
)
_RETRAINING_LABELS = {
    DetectionStatus.ONGOING.value: "true_positive",
    DetectionStatus.RESOLVED.value: "true_positive",
    DetectionStatus.DISMISSED.value: "false_positive",
}
_RETRAINING_MANIFEST_COLUMNS = [
    "log_id",
    "source_event_id",
    "camera_id",
    "camera_name",
    "detected_at",
    "confidence_score",
    "human_label",
    "snapshot_filename",
    "sha256_checksum",
    "snapshot_available",
    "verified_by_id",
    "verified_by_name",
    "verified_at",
    "closed_by_id",
    "closed_by_name",
    "closed_at",
]


def _generate_retraining(session: Session, job: ExportJob) -> tuple[bytes, int]:
    """07_PKG_reports.md Step 6 — a local ZIP of `manifest.csv` +
    `snapshots/`. Only human-labeled incidents (D-010's mapping table);
    `Unverified` is excluded. A row can outlive its snapshot file — that's
    represented explicitly in the manifest, never silently dropped.

    ZIP entry names are built entirely from `log_id` (an int) and
    `Path.name` (the resolved file's own basename, already stripped of any
    directory component) — never from the raw, client/AI-controlled
    `snapshot_key` — so there is no path-traversal surface here at all.
    """
    import hashlib
    import io
    import zipfile

    from sqlalchemy.orm import selectinload
    from sqlmodel import select as sql_select

    from app.services.filters import apply_incident_filters
    from app.services.snapshots import resolve as resolve_snapshot

    filters_dict = _filters_dict_from_job(job)
    start_date = (
        datetime.fromisoformat(filters_dict["start_date"])
        if filters_dict.get("start_date")
        else None
    )
    end_date = (
        datetime.fromisoformat(filters_dict["end_date"])
        if filters_dict.get("end_date")
        else None
    )
    camera_id = filters_dict.get("camera_id") or None

    filters = IncidentFilters(
        start_date=start_date,
        end_date=end_date,
        camera_ids=tuple(camera_id or ()),
        statuses=_RETRAINING_STATUSES,
    )
    stmt = apply_incident_filters(
        sql_select(DetectionLog).options(
            selectinload(DetectionLog.camera),
            selectinload(DetectionLog.verified_by),
            selectinload(DetectionLog.closed_by),
        ),
        filters,
    ).order_by(col(DetectionLog.log_id).asc())
    logs = session.exec(stmt).all()

    manifest_rows = []
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for log in logs:
            path = resolve_snapshot(
                log.snapshot_key,
                snapshot_root=settings.SNAPSHOT_ROOT,
                legacy_dir=settings.LEGACY_SNAPSHOT_DIR,
            )
            available = path is not None
            checksum = None
            snapshot_filename = None
            if available:
                data = path.read_bytes()
                checksum = hashlib.sha256(data).hexdigest()
                snapshot_filename = f"{log.log_id}_{path.name}"
                zf.writestr(f"snapshots/{snapshot_filename}", data)

            manifest_rows.append(
                [
                    log.log_id,
                    log.source_event_id,
                    log.camera_id,
                    log.camera.camera_name if log.camera else None,
                    log.detected_at.isoformat(),
                    log.confidence_score,
                    _RETRAINING_LABELS.get(log.detection_status, "unknown"),
                    snapshot_filename,
                    checksum,
                    available,
                    log.verified_by_id,
                    format_user_name(log.verified_by),
                    log.verified_at.isoformat() if log.verified_at else None,
                    log.closed_by_id,
                    format_user_name(log.closed_by),
                    log.closed_at.isoformat() if log.closed_at else None,
                ]
            )

        manifest_text = UTF8_BOM + "".join(
            stream_csv(_RETRAINING_MANIFEST_COLUMNS, manifest_rows)
        )
        zf.writestr("manifest.csv", manifest_text)

    return zip_buffer.getvalue(), len(logs)


_GENERATORS: dict[str, Callable[[Session, ExportJob], tuple[bytes, int]]] = {
    "incidents": _generate_incidents,
    "dashboard": _generate_dashboard,
    "performance": _generate_performance,
    "audit": _generate_audit,
    "retraining": _generate_retraining,
}


def create_job(
    session: Session,
    *,
    requested_by: User,
    report_type: str,
    format: str,
    filters: dict,
    sort: dict | None = None,
) -> ExportJob:
    """Adds (does not commit) a new `queued` job. The caller commits."""
    job = ExportJob(
        job_id=str(uuid.uuid4()),
        requested_by_id=requested_by.user_id,
        report_type=report_type,
        format=format,
        filters_json=json.dumps(filters, default=str),
        sort_json=json.dumps(sort) if sort else None,
        status="queued",
    )
    session.add(job)
    return job


def _artifact_filename(job: ExportJob) -> str:
    ext = "zip" if job.format == "zip" else job.format
    return f"adas_{job.report_type}_export_{job.job_id}.{ext}"


def process_export_job(engine: Engine, job_id: str) -> None:
    """The whole job body: generate → write artifact → record the
    REPORT_EXPORT/AUDIT_EXPORT audit attempt → mark completed/failed. A
    plain synchronous function, callable directly (tests do this) or from
    a background worker task via `asyncio.to_thread`.
    """
    with Session(engine) as session:
        job = session.get(ExportJob, job_id)
        if job is None or job.status not in ("queued", "processing"):
            # Already completed/failed/expired, or genuinely gone —
            # replay-safe no-op (10.x idempotency discipline).
            return

        job.status = "processing"
        job.started_at = datetime.now(UTC)
        session.add(job)
        session.commit()

        actor = session.get(User, job.requested_by_id)
        audit_action = "AUDIT_EXPORT" if job.report_type == "audit" else "REPORT_EXPORT"
        filters_dict = _filters_dict_from_job(job)
        sort_dict = _sort_dict_from_job(job) or None

        try:
            generator = _GENERATORS[job.report_type]
            content, row_count = generator(session, job)
        except Exception:
            logger.exception("Export job %s failed during generation", job_id)
            job = session.get(ExportJob, job_id)
            job.status = "failed"
            job.failure_category = "generation_failed"
            job.completed_at = datetime.now(UTC)
            session.add(job)
            if actor is not None:
                record_export_attempt(
                    session,
                    action=audit_action,
                    report_type=job.report_type,
                    format=job.format,
                    actor=actor,
                    filters=filters_dict,
                    sort=sort_dict,
                    row_count=None,
                    mode="job",
                    result=AuditResult.FAILURE,
                    failure_category="generation_failed",
                    job_id=job.job_id,
                )
            session.commit()
            return

        settings.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        artifact_path = settings.EXPORT_DIR / _artifact_filename(job)
        try:
            artifact_path.write_bytes(content)
        except OSError:
            logger.exception("Export job %s failed writing its artifact", job_id)
            # 14_EDGE_CASES.md 6.5 — disk full mid-write must never leave a
            # partial artifact file behind for a later download to find.
            try:
                artifact_path.unlink(missing_ok=True)
            except OSError:
                logger.warning(
                    "Could not remove partial artifact for failed job %s", job_id
                )
            job = session.get(ExportJob, job_id)
            job.status = "failed"
            job.failure_category = "artifact_write_failed"
            job.completed_at = datetime.now(UTC)
            session.add(job)
            if actor is not None:
                record_export_attempt(
                    session,
                    action=audit_action,
                    report_type=job.report_type,
                    format=job.format,
                    actor=actor,
                    filters=filters_dict,
                    sort=sort_dict,
                    row_count=row_count,
                    mode="job",
                    result=AuditResult.FAILURE,
                    failure_category="artifact_write_failed",
                    job_id=job.job_id,
                )
            session.commit()
            return

        job = session.get(ExportJob, job_id)
        now = datetime.now(UTC)
        job.status = "completed"
        job.artifact_path = str(artifact_path)
        job.artifact_bytes = len(content)
        job.progress_total = row_count
        job.progress_current = row_count
        job.completed_at = now
        job.expires_at = now + timedelta(hours=settings.EXPORT_ARTIFACT_TTL_HOURS)
        session.add(job)
        if actor is not None:
            # D-010 — a successful async audit entry means the artifact was
            # generated and made available, not that a browser finished
            # downloading it.
            record_export_attempt(
                session,
                action=audit_action,
                report_type=job.report_type,
                format=job.format,
                actor=actor,
                filters=filters_dict,
                sort=sort_dict,
                row_count=row_count,
                mode="job",
                result=AuditResult.SUCCESS,
                job_id=job.job_id,
            )
        session.commit()


def recover_interrupted_jobs(engine: Engine) -> list[str]:
    """Startup recovery (07_PKG_reports.md Step 5): the in-memory queue
    doesn't survive a restart, so every `queued`/`processing` job is reset
    to `queued` (restarted from the beginning — any partial artifact from
    a crashed run is not trusted) and its id returned for re-enqueuing."""
    with Session(engine) as session:
        stuck = session.exec(
            select(ExportJob).where(col(ExportJob.status).in_(["queued", "processing"]))
        ).all()
        ids = []
        for job in stuck:
            job.status = "queued"
            job.progress_current = 0
            job.started_at = None
            session.add(job)
            ids.append(job.job_id)
        session.commit()
        return ids


def cleanup_expired_artifacts(engine: Engine) -> None:
    """Deletes artifacts past `EXPORT_ARTIFACT_TTL_HOURS` and marks the job
    `expired`. Never touches source incidents or snapshots — this only
    ever unlinks a path under `EXPORT_DIR`. If the file can't be deleted
    right now (e.g. a download has it open), the job is left `completed`
    for the next sweep rather than marked `expired` with a file that's
    still actually there."""
    now = datetime.now(UTC)
    with Session(engine) as session:
        expired = session.exec(
            select(ExportJob).where(
                col(ExportJob.status) == "completed",
                col(ExportJob.expires_at).is_not(None),
                col(ExportJob.expires_at) <= now,
            )
        ).all()
        for job in expired:
            if job.artifact_path:
                try:
                    Path(job.artifact_path).unlink(missing_ok=True)
                except OSError:
                    logger.warning(
                        "Could not delete expired export artifact for job %s "
                        "(will retry on the next sweep)",
                        job.job_id,
                    )
                    continue
            job.status = "expired"
            job.artifact_path = None
            session.add(job)
        session.commit()


class ExportJobQueue:
    """Thin wrapper around an `asyncio.Queue[str]` of job ids plus the
    worker tasks draining it. Lives on `app.state`, same pattern as
    `RealtimeManager`/`HealthStore` — never a module-level singleton, so
    each app instance (real app vs. a test's throwaway app) gets its own.
    """

    def __init__(self) -> None:
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self._tasks: list[asyncio.Task] = []

    async def enqueue(self, job_id: str) -> None:
        await self.queue.put(job_id)

    def start(self, engine: Engine, worker_count: int) -> None:
        async def _worker() -> None:
            while True:
                job_id = await self.queue.get()
                try:
                    await asyncio.to_thread(process_export_job, engine, job_id)
                except Exception:
                    logger.exception(
                        "Export job worker crashed processing job %s", job_id
                    )
                finally:
                    self.queue.task_done()

        for _ in range(max(1, worker_count)):
            self._tasks.append(asyncio.ensure_future(_worker()))

    def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
