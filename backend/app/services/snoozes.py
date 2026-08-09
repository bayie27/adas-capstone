"""05_PKG_incidents_cameras.md Step 6 — shared incident snooze (D-004).

`snoozed_until` in SQLite is authoritative; the scheduler job is an
optimization, not the correctness mechanism. Expiry is an atomic
conditional UPDATE, and only the process whose UPDATE actually clears a row
may broadcast RE_ALARM — a duplicate or obsolete job updates zero rows and
stays silent (01_CONTRACTS.md §11).
"""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import update as sa_update
from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select

from app.models import DetectionLog, DetectionStatus, User
from app.services.events import re_alarm_event
from app.services.incidents import ConflictState, IncidentNotFound, PreconditionFailed
from app.services.realtime import RealtimeManager

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Must match AlarmSettings.snooze_duration's own column default
# (app/models/user.py) — used only when an actor somehow has no settings row.
_DEFAULT_SNOOZE_DURATION_SECONDS = 30


def snooze_incident(
    session: Session, *, log_id: int, actor: User, now: datetime | None = None
) -> DetectionLog:
    """01_CONTRACTS.md §11. Only `Unverified` may be snoozed:

    - never `Unverified` at all when peeked (already terminal, or Ongoing)
      -> 400 PRECONDITION_FAILED (§1.3's explicit "snooze on a
      non-Unverified incident" case). Safe to decide from a plain read: a
      terminal or Ongoing incident cannot become Unverified again, so there
      is no race window to close.
    - was `Unverified` when peeked but changed before the atomic UPDATE
      fired (a genuine race, edge case 1.3) -> 409 CONFLICT_STATE, the same
      body as a lost transition race, so the frontend reuses one code path.
    """
    now = now or datetime.now(UTC)
    current = session.get(DetectionLog, log_id, populate_existing=True)
    if current is None:
        raise IncidentNotFound(log_id)

    if current.detection_status != DetectionStatus.UNVERIFIED.value:
        raise PreconditionFailed("Only an 'Unverified' incident can be snoozed.")

    duration = (
        actor.alarm_settings.snooze_duration
        if actor.alarm_settings is not None
        else _DEFAULT_SNOOZE_DURATION_SECONDS
    )
    snoozed_until = now + timedelta(seconds=duration)

    stmt = (
        sa_update(DetectionLog)
        .where(
            DetectionLog.log_id == log_id,
            DetectionLog.detection_status == DetectionStatus.UNVERIFIED.value,
        )
        .values(
            snoozed_at=now,
            snoozed_until=snoozed_until,
            snoozed_by_id=actor.user_id,
            updated_at=now,
        )
    )
    result = session.execute(stmt)
    if result.rowcount == 0:
        current = session.get(DetectionLog, log_id, populate_existing=True)
        if current is None:
            raise IncidentNotFound(log_id)
        raise ConflictState(current)

    log = session.get(DetectionLog, log_id, populate_existing=True)
    assert log is not None
    return log


def clear_expired_snooze(
    session: Session, *, log_id: int, now: datetime | None = None
) -> DetectionLog | None:
    """The atomic conditional UPDATE at the heart of D-004's re-alarm
    guarantee. Returns the cleared log only if THIS call is the one that
    actually cleared it; the caller commits and broadcasts RE_ALARM only
    then. A duplicate job, a delayed job, or a job racing a Confirm/Dismiss
    updates zero rows and gets None back.
    """
    now = now or datetime.now(UTC)
    stmt = (
        sa_update(DetectionLog)
        .where(
            DetectionLog.log_id == log_id,
            DetectionLog.detection_status == DetectionStatus.UNVERIFIED.value,
            col(DetectionLog.snoozed_until).is_not(None),
            col(DetectionLog.snoozed_until) <= now,
        )
        .values(snoozed_at=None, snoozed_until=None, snoozed_by_id=None, updated_at=now)
    )
    result = session.execute(stmt)
    if result.rowcount == 0:
        return None
    return session.get(DetectionLog, log_id, populate_existing=True)


def expire_snooze(
    engine: Engine, log_id: int, manager: RealtimeManager | None = None
) -> None:
    """Scheduler job fired at a snooze's deadline (also reused by the
    periodic sweep for a lost job)."""
    with Session(engine) as session:
        log = clear_expired_snooze(session, log_id=log_id)
        if log is None:
            return
        session.commit()
        session.refresh(log)

    if manager is not None:
        manager.broadcast(re_alarm_event(log))


def schedule_snooze_job(
    scheduler: "AsyncIOScheduler",
    engine: Engine,
    log: DetectionLog,
    manager: RealtimeManager | None = None,
) -> None:
    """Registers the `snooze:{log_id}` job, replacing any prior one — the
    stable id an unlimited re-snooze relies on (D-004)."""
    from app.core.scheduler import add_job

    if log.log_id is None or log.snoozed_until is None:
        return
    add_job(
        scheduler,
        lambda log_id=log.log_id: expire_snooze(engine, log_id, manager),
        job_id=f"snooze:{log.log_id}",
        trigger="date",
        run_date=log.snoozed_until,
    )


def schedule_pending_snoozes(
    scheduler: "AsyncIOScheduler",
    engine: Engine,
    logs: list[DetectionLog],
    manager: RealtimeManager | None = None,
) -> None:
    for log in logs:
        schedule_snooze_job(scheduler, engine, log, manager)


def sweep_expired_snoozes(
    engine: Engine, manager: RealtimeManager | None = None
) -> int:
    """Periodic safety net (every 30s) for a due snooze whose scheduler job
    was lost. Returns the number of incidents swept."""
    now = datetime.now(UTC)
    with Session(engine) as session:
        due_log_ids = session.exec(
            select(DetectionLog.log_id).where(
                col(DetectionLog.detection_status) == DetectionStatus.UNVERIFIED.value,
                col(DetectionLog.snoozed_until).is_not(None),
                col(DetectionLog.snoozed_until) <= now,
            )
        ).all()

    for log_id in due_log_ids:
        expire_snooze(engine, log_id, manager)
    return len(due_log_ids)


def reconcile_snoozes(engine: Engine) -> list[DetectionLog]:
    """Startup (P1 Step 9's stub, filled in here): atomically clears expired
    `Unverified` snoozes so those incidents become alarm-active again, then
    returns the still-pending (unexpired) snoozed incidents so the caller
    can reschedule their resume jobs once the scheduler exists — mirrors
    reconcile_camera_desired_states() + schedule_pending_cooldowns()."""
    now = datetime.now(UTC)
    with Session(engine) as session:
        candidates = session.exec(
            select(DetectionLog).where(
                col(DetectionLog.detection_status) == DetectionStatus.UNVERIFIED.value,
                col(DetectionLog.snoozed_until).is_not(None),
            )
        ).all()

        pending: list[DetectionLog] = []
        for log in candidates:
            if log.snoozed_until is not None and log.snoozed_until <= now:
                clear_expired_snooze(session, log_id=log.log_id, now=now)
            else:
                pending.append(log)

        session.commit()
        for log in pending:
            session.refresh(log)
        return pending
