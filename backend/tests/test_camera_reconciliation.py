"""
Tests for app.services.cameras — desired-state reconciliation (P1 Step 9).
"""

import uuid
from datetime import UTC, datetime, timedelta

from app.core.scheduler import create_scheduler
from app.models import Camera, DetectionLog, DetectionStatus
from app.services.cameras import (
    recompute_desired_state,
    reconcile_camera_desired_states,
    resume_camera_after_cooldown,
    schedule_pending_cooldowns,
)
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool


def _make_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
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
    # Detach with values already loaded so a later commit()'s expire-on-
    # commit (which affects every object still attached to this session)
    # doesn't leave this instance needing a session that may since have
    # closed by the time the caller reads its attributes.
    session.expunge(camera)
    return camera


def _make_open_incident(session: Session, camera: Camera) -> DetectionLog:
    log = DetectionLog(
        camera_id=camera.camera_id,
        detected_at=datetime.now(UTC),
        snapshot_key="a.jpg",
        confidence_score=0.9,
        source_event_id=str(uuid.uuid4()),
        detection_status=DetectionStatus.UNVERIFIED.value,
    )
    session.add(log)
    session.commit()
    return log


class TestRecomputeDesiredState:
    def test_disabled_camera_is_inactive(self):
        camera = Camera(camera_name="C", channel_id=1, is_enabled=False)
        recompute_desired_state(camera, has_open_incident=False, now=datetime.now(UTC))
        assert camera.desired_ai_state == "Inactive"
        assert camera.desired_state_reason == "disabled"
        assert camera.cooldown_until is None

    def test_inactive_camera_is_inactive(self):
        camera = Camera(camera_name="C", channel_id=1, is_active=False)
        recompute_desired_state(camera, has_open_incident=False, now=datetime.now(UTC))
        assert camera.desired_ai_state == "Inactive"
        assert camera.desired_state_reason == "disabled"

    def test_open_incident_pauses_with_reason_incident(self):
        camera = Camera(camera_name="C", channel_id=1)
        recompute_desired_state(camera, has_open_incident=True, now=datetime.now(UTC))
        assert camera.desired_ai_state == "Paused"
        assert camera.desired_state_reason == "incident"
        assert camera.cooldown_until is None

    def test_future_cooldown_pauses_with_reason_cooldown(self):
        now = datetime.now(UTC)
        camera = Camera(
            camera_name="C", channel_id=1, cooldown_until=now + timedelta(seconds=30)
        )
        recompute_desired_state(camera, has_open_incident=False, now=now)
        assert camera.desired_ai_state == "Paused"
        assert camera.desired_state_reason == "cooldown"
        assert camera.cooldown_until == now + timedelta(seconds=30)

    def test_past_cooldown_resumes_to_active(self):
        now = datetime.now(UTC)
        camera = Camera(
            camera_name="C", channel_id=1, cooldown_until=now - timedelta(seconds=1)
        )
        recompute_desired_state(camera, has_open_incident=False, now=now)
        assert camera.desired_ai_state == "Active"
        assert camera.desired_state_reason is None
        assert camera.cooldown_until is None

    def test_cooldown_exactly_now_is_treated_as_expired(self):
        now = datetime.now(UTC)
        camera = Camera(camera_name="C", channel_id=1, cooldown_until=now)
        recompute_desired_state(camera, has_open_incident=False, now=now)
        assert camera.desired_ai_state == "Active"

    def test_no_incident_no_cooldown_is_active(self):
        camera = Camera(camera_name="C", channel_id=1)
        recompute_desired_state(camera, has_open_incident=False, now=datetime.now(UTC))
        assert camera.desired_ai_state == "Active"
        assert camera.desired_state_reason is None

    def test_open_incident_takes_priority_over_future_cooldown(self):
        """Edge case 1.8 — a new incident must keep the camera Paused with
        reason='incident', not let a stale cooldown win."""
        now = datetime.now(UTC)
        camera = Camera(
            camera_name="C", channel_id=1, cooldown_until=now + timedelta(seconds=30)
        )
        recompute_desired_state(camera, has_open_incident=True, now=now)
        assert camera.desired_ai_state == "Paused"
        assert camera.desired_state_reason == "incident"
        assert camera.cooldown_until is None


class TestReconcileCameraDesiredStates:
    def test_zero_cameras_returns_empty(self):
        engine = _make_engine()
        assert reconcile_camera_desired_states(engine) == []

    def test_recomputes_across_all_active_cameras(self):
        engine = _make_engine()
        now = datetime.now(UTC)
        with Session(engine) as session:
            disabled = _make_camera(session, is_enabled=False)
            with_incident = _make_camera(session)
            _make_open_incident(session, with_incident)
            in_cooldown = _make_camera(
                session, cooldown_until=now + timedelta(seconds=45)
            )
            plain = _make_camera(session)
            soft_deleted = _make_camera(session, is_active=False)

            disabled_id = disabled.camera_id
            with_incident_id = with_incident.camera_id
            in_cooldown_id = in_cooldown.camera_id
            plain_id = plain.camera_id
            soft_deleted_id = soft_deleted.camera_id

        pending = reconcile_camera_desired_states(engine)
        assert {c.camera_id for c in pending} == {in_cooldown_id}

        with Session(engine) as session:
            assert session.get(Camera, disabled_id).desired_ai_state == "Inactive"
            assert session.get(Camera, with_incident_id).desired_ai_state == "Paused"
            assert (
                session.get(Camera, with_incident_id).desired_state_reason == "incident"
            )
            assert session.get(Camera, in_cooldown_id).desired_ai_state == "Paused"
            assert (
                session.get(Camera, in_cooldown_id).desired_state_reason == "cooldown"
            )
            assert session.get(Camera, plain_id).desired_ai_state == "Active"
            # Soft-deleted cameras are excluded from reconciliation entirely.
            assert session.get(Camera, soft_deleted_id).desired_ai_state == "Inactive"


class TestResumeCameraAfterCooldown:
    def test_resumes_camera_with_no_new_incident(self):
        engine = _make_engine()
        with Session(engine) as session:
            camera = _make_camera(
                session,
                cooldown_until=datetime.now(UTC) - timedelta(seconds=1),
                desired_ai_state="Paused",
                desired_state_reason="cooldown",
            )
            camera_id = camera.camera_id

        resume_camera_after_cooldown(engine, camera_id)

        with Session(engine) as session:
            camera = session.get(Camera, camera_id)
            assert camera.desired_ai_state == "Active"
            assert camera.desired_state_reason is None
            assert camera.cooldown_until is None

    def test_leaves_camera_paused_if_a_new_incident_opened(self):
        """Edge case 1.8 — the cooldown job fires while a new incident is
        open; it must not resume the camera."""
        engine = _make_engine()
        with Session(engine) as session:
            camera = _make_camera(
                session,
                cooldown_until=datetime.now(UTC) - timedelta(seconds=1),
                desired_ai_state="Paused",
                desired_state_reason="cooldown",
            )
            _make_open_incident(session, camera)
            camera_id = camera.camera_id

        resume_camera_after_cooldown(engine, camera_id)

        with Session(engine) as session:
            camera = session.get(Camera, camera_id)
            assert camera.desired_ai_state == "Paused"
            assert camera.desired_state_reason == "incident"

    def test_missing_camera_is_a_no_op(self):
        engine = _make_engine()
        resume_camera_after_cooldown(engine, 999999)  # must not raise

    def test_soft_deleted_camera_is_untouched(self):
        engine = _make_engine()
        with Session(engine) as session:
            camera = _make_camera(
                session,
                is_active=False,
                cooldown_until=datetime.now(UTC) - timedelta(seconds=1),
                desired_ai_state="Paused",
                desired_state_reason="cooldown",
            )
            camera_id = camera.camera_id

        resume_camera_after_cooldown(engine, camera_id)

        with Session(engine) as session:
            camera = session.get(Camera, camera_id)
            # Unchanged — the job bails out before touching a deleted camera.
            assert camera.desired_ai_state == "Paused"


class TestSchedulePendingCooldowns:
    def test_registers_one_date_triggered_job_per_camera(self):
        engine = _make_engine()
        with Session(engine) as session:
            camera_a = _make_camera(session, cooldown_until=datetime.now(UTC))
            camera_b = _make_camera(session, cooldown_until=datetime.now(UTC))

        scheduler = create_scheduler()
        schedule_pending_cooldowns(scheduler, engine, [camera_a, camera_b])

        job_ids = {job.id for job in scheduler.get_jobs()}
        assert job_ids == {
            f"cooldown:{camera_a.camera_id}",
            f"cooldown:{camera_b.camera_id}",
        }

    def test_skips_cameras_without_a_cooldown_deadline(self):
        engine = _make_engine()
        with Session(engine) as session:
            camera = _make_camera(session)

        scheduler = create_scheduler()
        schedule_pending_cooldowns(scheduler, engine, [camera])

        assert scheduler.get_jobs() == []
