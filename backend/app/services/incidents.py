"""05_PKG_incidents_cameras.md Step 1 — the one place every incident
transition goes through. No route re-implements the atomic guard.

01_CONTRACTS.md §10.3: a transition is a conditional UPDATE, never a
read-then-write. `rowcount == 0` means the row wasn't in the expected status
at write time — the caller re-reads to tell a missing row (404) apart from a
lost race or an already-terminal incident (409 CONFLICT_STATE, D-002).
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import case, or_
from sqlalchemy import update as sa_update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.core.types import parse_utc_query_datetime
from app.models import (
    AuditAction,
    Camera,
    DesiredAIState,
    DesiredStateReason,
    DetectionLog,
    DetectionStatus,
    User,
)
from app.services.formatting import format_user_name

if TYPE_CHECKING:
    from app.schemas import DetectionLogCreateV2

_OPEN_STATUSES = (DetectionStatus.UNVERIFIED.value, DetectionStatus.ONGOING.value)

# 01_CONTRACTS.md §10 / D-002 — the only four legal transitions.
ALLOWED: dict[tuple[DetectionStatus, DetectionStatus], AuditAction] = {
    (DetectionStatus.UNVERIFIED, DetectionStatus.ONGOING): AuditAction.ALERT_CONFIRM,
    (DetectionStatus.UNVERIFIED, DetectionStatus.DISMISSED): AuditAction.ALERT_DISMISS,
    (DetectionStatus.ONGOING, DetectionStatus.RESOLVED): AuditAction.ALERT_RESOLVE,
    (DetectionStatus.ONGOING, DetectionStatus.DISMISSED): AuditAction.ALERT_CORRECTION,
}


def _describe_handler(
    log: DetectionLog,
) -> tuple[str | None, User | None, datetime | None]:
    """Infers which action actually landed on `log`, purely from its stored
    fields (§10.1's actor table), so a 409 body can name the winner without
    having witnessed the winning request."""
    status = log.detection_status
    if status == DetectionStatus.ONGOING.value:
        return AuditAction.ALERT_CONFIRM.value, log.verified_by, log.verified_at
    if status == DetectionStatus.RESOLVED.value:
        return AuditAction.ALERT_RESOLVE.value, log.closed_by, log.closed_at
    if status == DetectionStatus.DISMISSED.value:
        if log.closed_by_id is not None:
            # Correction (Ongoing -> Dismissed) sets closed_by; an immediate
            # dismiss (Unverified -> Dismissed) never does (D-002).
            return AuditAction.ALERT_CORRECTION.value, log.closed_by, log.closed_at
        return AuditAction.ALERT_DISMISS.value, log.verified_by, log.verified_at
    return None, None, None


class IncidentNotFound(Exception):
    def __init__(self, log_id: int) -> None:
        self.log_id = log_id
        super().__init__(f"Incident {log_id} not found")


class ConflictState(Exception):
    """01_CONTRACTS.md §5.3 — carries everything a route needs to build the
    409 body: the incident's current status and who handled it, with what
    action, and when."""

    def __init__(self, log: DetectionLog) -> None:
        action, handler, handled_at = _describe_handler(log)
        self.log = log
        self.current_status = log.detection_status
        self.handled_action = action
        self.handled_by = format_user_name(handler)
        self.handled_at = handled_at
        super().__init__(f"Incident {log.log_id} already {log.detection_status}")


class PreconditionFailed(Exception):
    """400 PRECONDITION_FAILED (01_CONTRACTS.md §1.3) — a business rule
    rejected the request outright, distinct from a lost race."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class CameraUnavailableForIngest(Exception):
    """The camera is missing, soft-deleted or disabled — a 404 to the
    engine, which should drop the event rather than retry it."""

    def __init__(self, camera_id: int) -> None:
        self.camera_id = camera_id
        super().__init__(
            f"Camera with ID {camera_id} not found, inactive, or disabled."
        )


class OpenIncidentConflict(Exception):
    """ux_detection_open_camera rejected the insert: this camera already has
    an Unverified/Ongoing incident. Carries the incumbent so the route can
    name it in the 409 body."""

    def __init__(self, camera_id: int, existing: DetectionLog | None) -> None:
        self.camera_id = camera_id
        self.existing = existing
        super().__init__(f"Camera {camera_id} already has an open incident.")


@dataclass
class TransitionResult:
    log: DetectionLog
    action: AuditAction
    expected: DetectionStatus


def ingest_detection(
    session: Session,
    payload: "DetectionLogCreateV2",
) -> tuple[DetectionLog, Camera, bool]:
    """01_CONTRACTS.md §6.3 — the v2 idempotent AI-engine ingest path,
    lifted out of routes/internal.py so the dev-tools injector runs the
    real one instead of a reimplementation that would drift from it.

    Returns `(log, camera, created)`. `created` is False for an idempotent
    replay, which the caller maps to 200 and must *not* broadcast for.

    The broadcast deliberately stays with the caller: 01_CONTRACTS.md §9.4
    forbids announcing a row a later rollback could undo, and the ordering
    (commit, then broadcast) is what makes the self-blindfold correct.
    Nothing here changes ordering, status mapping or error codes — this
    seam carries the F20 fix (be_audit/A3_ai_seam.md) and the F23 race fix
    (be_audit/00_FINDINGS.md).
    """
    camera = session.get(Camera, payload.camera_id)
    if not camera or not camera.is_active or not camera.is_enabled:
        raise CameraUnavailableForIngest(payload.camera_id)

    source_event_id = payload.source_event_id
    detected_at = parse_utc_query_datetime(payload.detected_at)
    # Idempotent retry (01_CONTRACTS.md §6.3): a pre-check here is safe
    # (unlike the open-camera check below) because a genuinely
    # concurrent duplicate is still caught by the ux_detection_source_event
    # unique constraint as a backstop.
    existing = session.exec(
        select(DetectionLog).where(DetectionLog.source_event_id == source_event_id)
    ).first()
    if existing is not None:
        return existing, camera, False

    db_alert = DetectionLog(
        camera_id=payload.camera_id,
        detected_at=detected_at,
        snapshot_key=payload.snapshot_key,
        confidence_score=payload.confidence_score,
        source_event_id=source_event_id,
    )
    session.add(db_alert)
    # The self-blindfold: pause this camera the instant the incident is
    # committed. Never pre-checked for an existing open incident — the
    # ux_detection_open_camera partial unique index is what makes this
    # race-proof, not a SELECT before the INSERT.
    #
    # Written as a conditional UPDATE against the row's *live* is_active/
    # is_enabled, not apply_desired_state() on the `camera` object read
    # above — that read can go stale before this commits. A concurrent
    # operator disable (edge case 1.7, be_audit/A5_edge_cases.md) only
    # touches the is_enabled column, so a plain read-then-write here would
    # silently clobber a disabled camera's correct Inactive/disabled state
    # with Paused/incident, using a since-invalidated "is_enabled was true"
    # assumption. The CASE is evaluated by the DB against the row's current
    # value at write time, so whichever request commits last always leaves
    # the row internally consistent, regardless of interleaving (F23,
    # be_audit/00_FINDINGS.md).
    camera_disabled = or_(~Camera.is_active, ~Camera.is_enabled)

    try:
        # Inside the try, not before it: this session.execute() autoflushes
        # the pending DetectionLog insert above, which is exactly where the
        # ux_detection_open_camera / ux_detection_source_event IntegrityError
        # actually raises from — it must land in this except, not escape as
        # an unhandled 500.
        session.execute(
            sa_update(Camera)
            .where(Camera.camera_id == payload.camera_id)
            .values(
                desired_ai_state=case(
                    (camera_disabled, DesiredAIState.INACTIVE.value),
                    else_=DesiredAIState.PAUSED.value,
                ),
                desired_state_reason=case(
                    (camera_disabled, DesiredStateReason.DISABLED.value),
                    else_=DesiredStateReason.INCIDENT.value,
                ),
                cooldown_until=None,
                config_version=Camera.config_version + 1,
            )
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        existing = session.exec(
            select(DetectionLog).where(DetectionLog.source_event_id == source_event_id)
        ).first()
        if existing is not None:
            # A concurrent duplicate committed first — this is the
            # ux_detection_source_event backstop, not the open-camera one.
            return existing, camera, False
        open_alert = session.exec(
            select(DetectionLog).where(
                col(DetectionLog.camera_id) == payload.camera_id,
                col(DetectionLog.detection_status).in_(_OPEN_STATUSES),
            )
        ).first()
        raise OpenIncidentConflict(payload.camera_id, open_alert) from exc

    session.refresh(db_alert)
    session.refresh(camera)
    return db_alert, camera, True


def transition(
    session: Session,
    *,
    log_id: int,
    expected: DetectionStatus,
    new: DetectionStatus,
    actor: User,
    now: datetime | None = None,
) -> TransitionResult:
    """The one atomic conditional UPDATE every legal transition uses.

    Actor semantics (§10.1): a transition out of Unverified (confirm or
    immediate dismiss) stamps the *verification* fields; a transition out of
    Ongoing (resolve or correction) retains verification and stamps the
    *closure* fields instead. Terminal transitions clear snooze state in the
    same UPDATE, which is what makes the in-memory snooze job an
    optimization rather than the correctness mechanism (D-004).
    """
    now = now or datetime.now(UTC)
    action = ALLOWED[(expected, new)]

    values: dict = {
        "detection_status": new.value,
        "snoozed_at": None,
        "snoozed_until": None,
        "snoozed_by_id": None,
        "updated_at": now,
    }
    if expected == DetectionStatus.UNVERIFIED:
        values["verified_by_id"] = actor.user_id
        values["verified_at"] = now
    else:
        values["closed_by_id"] = actor.user_id
        values["closed_at"] = now

    stmt = (
        sa_update(DetectionLog)
        .where(
            DetectionLog.log_id == log_id,
            DetectionLog.detection_status == expected.value,
        )
        .values(**values)
    )
    result = session.execute(stmt)
    if result.rowcount == 0:
        current = session.get(DetectionLog, log_id, populate_existing=True)
        if current is None:
            raise IncidentNotFound(log_id)
        raise ConflictState(current)

    log = session.get(DetectionLog, log_id, populate_existing=True)
    assert log is not None
    return TransitionResult(log=log, action=action, expected=expected)


def dismiss_transition(
    session: Session, *, log_id: int, actor: User, now: datetime | None = None
) -> TransitionResult:
    """Dismiss is the one route with two legal source statuses. The peek
    below only *picks* which atomic attempt to make — correctness still
    comes entirely from `transition()`'s conditional UPDATE, which
    re-validates the row's real status at write time. Peeking a terminal
    status is safe without a race window: Dismissed/Resolved never
    transition again (D-002), so that read is already authoritative.
    """
    current = session.get(DetectionLog, log_id, populate_existing=True)
    if current is None:
        raise IncidentNotFound(log_id)

    if current.detection_status not in (
        DetectionStatus.UNVERIFIED.value,
        DetectionStatus.ONGOING.value,
    ):
        raise ConflictState(current)

    return transition(
        session,
        log_id=log_id,
        expected=DetectionStatus(current.detection_status),
        new=DetectionStatus.DISMISSED,
        actor=actor,
        now=now,
    )
