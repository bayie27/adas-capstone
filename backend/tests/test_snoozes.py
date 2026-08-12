"""Tests for app.services.snoozes — 01_CONTRACTS.md §11, D-004.

Route-level snooze behavior lives in test_alerts.py's TestSnooze and
TestConcurrency; this file covers the service functions that back startup
recovery and the periodic sweep.
"""

import uuid
from datetime import UTC, datetime, timedelta

from app.core.scheduler import create_scheduler
from app.models import Camera, DetectionLog, DetectionStatus, User, UserRole
from app.services.snoozes import (
    clear_expired_snooze,
    reconcile_snoozes,
    schedule_pending_snoozes,
    snooze_incident,
    sweep_expired_snoozes,
)
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool


def _make_engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _make_camera(session: Session, **overrides) -> Camera:
    defaults = {
        "camera_name": f"Cam {uuid.uuid4().hex[:6]}",
        "channel_id": uuid.uuid4().int % 100000 + 1,
    }
    defaults.update(overrides)
    camera = Camera(**defaults)
    session.add(camera)
    session.commit()
    session.refresh(camera)
    session.expunge(camera)
    return camera


def _make_log(session: Session, camera: Camera, **overrides) -> DetectionLog:
    defaults = {
        "camera_id": camera.camera_id,
        "detected_at": datetime.now(UTC),
        "snapshot_key": "a.jpg",
        "confidence_score": 0.9,
        "source_event_id": str(uuid.uuid4()),
        "detection_status": DetectionStatus.UNVERIFIED.value,
    }
    defaults.update(overrides)
    log = DetectionLog(**defaults)
    session.add(log)
    session.commit()
    session.refresh(log)
    session.expunge(log)
    return log


class TestClearExpiredSnooze:
    def test_clears_a_due_snooze(self):
        engine = _make_engine()
        with Session(engine) as session:
            camera = _make_camera(session)
            log = _make_log(
                session,
                camera,
                snoozed_at=datetime.now(UTC) - timedelta(seconds=31),
                snoozed_until=datetime.now(UTC) - timedelta(seconds=1),
                snoozed_by_id=None,
            )

        with Session(engine) as session:
            cleared = clear_expired_snooze(session, log_id=log.log_id)
            session.commit()
            assert cleared is not None
            assert cleared.snoozed_until is None

    def test_not_yet_due_is_a_no_op(self):
        engine = _make_engine()
        with Session(engine) as session:
            camera = _make_camera(session)
            log = _make_log(
                session,
                camera,
                snoozed_at=datetime.now(UTC),
                snoozed_until=datetime.now(UTC) + timedelta(seconds=30),
            )

        with Session(engine) as session:
            cleared = clear_expired_snooze(session, log_id=log.log_id)

        assert cleared is None

    def test_server_clock_stepping_backwards_does_not_fire_early(self):
        """Edge case 5.12 — a snooze deadline in the future stays pending
        rather than firing repeatedly (or firing at all) if the server
        clock steps backwards. clear_expired_snooze() is stateless (a
        plain `now() <= snoozed_until` comparison via `now`, no cached
        prior observation), so this mainly locks that property in against
        a future change that introduced any kind of elapsed-time state."""
        engine = _make_engine()
        with Session(engine) as session:
            camera = _make_camera(session)
            deadline = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
            log = _make_log(
                session,
                camera,
                snoozed_at=deadline - timedelta(minutes=15),
                snoozed_until=deadline,
            )

        # The clock steps backwards to well before the snooze was even
        # created — the most extreme version of "backwards," not just a
        # few seconds.
        with Session(engine) as session:
            stepped_back_now = deadline - timedelta(hours=1)
            cleared = clear_expired_snooze(
                session, log_id=log.log_id, now=stepped_back_now
            )
        assert cleared is None

        # Once real time actually reaches the deadline, it still fires
        # normally — the earlier backward step left no stuck state.
        with Session(engine) as session:
            cleared = clear_expired_snooze(session, log_id=log.log_id, now=deadline)
        assert cleared is not None
        assert cleared.snoozed_until is None

    def test_duplicate_call_after_clearing_is_a_no_op(self):
        """D-004 — only the process whose UPDATE actually clears a row may
        broadcast RE_ALARM; a second call must update zero rows."""
        engine = _make_engine()
        with Session(engine) as session:
            camera = _make_camera(session)
            log = _make_log(
                session,
                camera,
                snoozed_at=datetime.now(UTC) - timedelta(seconds=31),
                snoozed_until=datetime.now(UTC) - timedelta(seconds=1),
            )

        with Session(engine) as session:
            first = clear_expired_snooze(session, log_id=log.log_id)
            session.commit()
        with Session(engine) as session:
            second = clear_expired_snooze(session, log_id=log.log_id)

        assert first is not None
        assert second is None

    def test_does_not_clear_a_non_unverified_incident(self):
        """A snooze field left dangling on an Ongoing row (shouldn't happen
        given transitions clear it, but defense in depth) must not be
        touched by expiry."""
        engine = _make_engine()
        with Session(engine) as session:
            camera = _make_camera(session)
            log = _make_log(
                session,
                camera,
                detection_status=DetectionStatus.ONGOING.value,
                snoozed_until=datetime.now(UTC) - timedelta(seconds=1),
            )

        with Session(engine) as session:
            cleared = clear_expired_snooze(session, log_id=log.log_id)

        assert cleared is None

    def test_deadline_exactly_now_is_due(self):
        """Edge case 2.13 — snoozed_until == now fires (the comparison is
        <=, not <)."""
        engine = _make_engine()
        now = datetime.now(UTC)
        with Session(engine) as session:
            camera = _make_camera(session)
            log = _make_log(
                session,
                camera,
                snoozed_at=now - timedelta(seconds=30),
                snoozed_until=now,
            )

        with Session(engine) as session:
            cleared = clear_expired_snooze(session, log_id=log.log_id, now=now)
            assert cleared is not None

    def test_re_snooze_racing_the_previous_deadline_finds_it_moved(self):
        """Edge case 1.4 — a job that wakes for the *original* deadline
        must find the re-snoozed (later) deadline still in the future and
        do nothing. Zero RE_ALARM, not two."""
        engine = _make_engine()
        original_now = datetime.now(UTC)
        with Session(engine) as session:
            camera = _make_camera(session)
            log = _make_log(
                session,
                camera,
                snoozed_at=original_now - timedelta(seconds=15),
                snoozed_until=original_now + timedelta(seconds=1),
            )

        # Re-snooze extends the deadline further into the future.
        with Session(engine) as session:
            actor = User(
                username="resnoozer",
                first_name="Re",
                last_name="Snoozer",
                role=UserRole.OPERATOR,
                password_hash="x",
            )
            session.add(actor)
            session.commit()
            session.refresh(actor)
            snooze_incident(
                session,
                log_id=log.log_id,
                actor=actor,
                now=original_now + timedelta(seconds=1),
            )
            session.commit()

        # The job scheduled for the *original* deadline wakes up late-ish
        # but still before the re-snoozed deadline — must be a no-op.
        with Session(engine) as session:
            cleared = clear_expired_snooze(
                session, log_id=log.log_id, now=original_now + timedelta(seconds=2)
            )

        assert cleared is None


class TestSweepExpiredSnoozes:
    def test_sweeps_all_due_snoozes(self):
        engine = _make_engine()
        with Session(engine) as session:
            camera = _make_camera(session)
            due = _make_log(
                session,
                camera,
                snoozed_at=datetime.now(UTC) - timedelta(seconds=31),
                snoozed_until=datetime.now(UTC) - timedelta(seconds=1),
            )
            camera2 = _make_camera(session)
            not_due = _make_log(
                session,
                camera2,
                snoozed_at=datetime.now(UTC),
                snoozed_until=datetime.now(UTC) + timedelta(seconds=30),
            )

        swept = sweep_expired_snoozes(engine)
        assert swept == 1

        with Session(engine) as session:
            assert session.get(DetectionLog, due.log_id).snoozed_until is None
            assert session.get(DetectionLog, not_due.log_id).snoozed_until is not None


class TestReconcileSnoozes:
    def test_clears_expired_and_returns_pending(self):
        """Edge case 6.16 — restart with active snoozes: unexpired
        rescheduled, expired cleared and alarm-active."""
        engine = _make_engine()
        with Session(engine) as session:
            expired_camera = _make_camera(session)
            expired_log = _make_log(
                session,
                expired_camera,
                snoozed_at=datetime.now(UTC) - timedelta(seconds=31),
                snoozed_until=datetime.now(UTC) - timedelta(seconds=1),
            )
            pending_camera = _make_camera(session)
            pending_log = _make_log(
                session,
                pending_camera,
                snoozed_at=datetime.now(UTC),
                snoozed_until=datetime.now(UTC) + timedelta(seconds=20),
            )

        pending = reconcile_snoozes(engine)

        assert {log.log_id for log in pending} == {pending_log.log_id}

        with Session(engine) as session:
            assert session.get(DetectionLog, expired_log.log_id).snoozed_until is None
            assert (
                session.get(DetectionLog, pending_log.log_id).snoozed_until is not None
            )

    def test_no_snoozed_incidents_returns_empty(self):
        engine = _make_engine()
        assert reconcile_snoozes(engine) == []


class TestSchedulePendingSnoozes:
    def test_registers_one_job_per_log(self):
        engine = _make_engine()
        with Session(engine) as session:
            camera = _make_camera(session)
            log = _make_log(
                session,
                camera,
                snoozed_at=datetime.now(UTC),
                snoozed_until=datetime.now(UTC) + timedelta(seconds=20),
            )

        scheduler = create_scheduler()
        schedule_pending_snoozes(scheduler, engine, [log])

        job_ids = {job.id for job in scheduler.get_jobs()}
        assert job_ids == {f"snooze:{log.log_id}"}
