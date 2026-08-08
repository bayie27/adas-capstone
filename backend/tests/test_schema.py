"""
Tests for the complete target schema (P1 Step 4 / 01_CONTRACTS.md §3).

Uses a throwaway in-memory engine with the same pragma installer the real
app engine uses, so foreign_keys=ON and the rest of D-005's connection
policy are actually in effect — these constraints only bite when SQLite's
FK enforcement is on.
"""

from datetime import UTC, datetime

import pytest
from app.core.db import install_sqlite_pragmas
from app.models import (
    AuditLog,
    Camera,
    DetectionLog,
    DetectionStatus,
    User,
    UserRole,
)
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    install_sqlite_pragmas(engine)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


def _make_camera(session: Session, **overrides) -> Camera:
    defaults = {"camera_name": "Test Cam", "channel_id": 1}
    defaults.update(overrides)
    camera = Camera(**defaults)
    session.add(camera)
    session.commit()
    session.refresh(camera)
    return camera


def _make_user(session: Session, **overrides) -> User:
    defaults = {
        "username": "admin",
        "first_name": "A",
        "last_name": "B",
        "role": UserRole.ADMIN,
        "password_hash": "x",
    }
    defaults.update(overrides)
    user = User(**defaults)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


class TestForeignKeyEnforcement:
    def test_detection_log_rejects_nonexistent_camera_id(self, db_session):
        log = DetectionLog(
            camera_id=999999,
            detected_at=datetime.now(UTC),
            snapshot_key="a.jpg",
            confidence_score=0.5,
            source_event_id="evt-fk-1",
        )
        db_session.add(log)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_hard_deleting_a_referenced_camera_is_blocked(self, db_session):
        camera = _make_camera(db_session)
        log = DetectionLog(
            camera_id=camera.camera_id,
            detected_at=datetime.now(UTC),
            snapshot_key="a.jpg",
            confidence_score=0.5,
            source_event_id="evt-fk-2",
        )
        db_session.add(log)
        db_session.commit()

        db_session.delete(camera)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_hard_deleting_a_referenced_user_is_blocked(self, db_session):
        user = _make_user(db_session)
        log = DetectionLog(
            camera_id=_make_camera(db_session).camera_id,
            detected_at=datetime.now(UTC),
            snapshot_key="a.jpg",
            confidence_score=0.5,
            source_event_id="evt-fk-3",
            verified_by_id=user.user_id,
        )
        db_session.add(log)
        db_session.commit()

        # A raw DELETE, not session.delete() — the ORM's own cascade would
        # nullify the nullable verified_by_id FK before issuing the DELETE,
        # which never exercises the DB-level ON DELETE RESTRICT this test
        # is actually checking.
        with pytest.raises(IntegrityError):
            db_session.execute(
                text("DELETE FROM user WHERE user_id = :user_id"),
                {"user_id": user.user_id},
            )
            db_session.commit()


class TestCheckConstraints:
    @pytest.mark.parametrize("bad_score", [-0.001, 1.001])
    def test_confidence_score_out_of_range_rejected(self, db_session, bad_score):
        camera = _make_camera(db_session)
        log = DetectionLog(
            camera_id=camera.camera_id,
            detected_at=datetime.now(UTC),
            snapshot_key="a.jpg",
            confidence_score=bad_score,
            source_event_id="evt-conf",
        )
        db_session.add(log)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_bad_role_rejected(self, db_session):
        user = User(
            username="baduser",
            first_name="A",
            last_name="B",
            role="Superuser",
            password_hash="x",
        )
        db_session.add(user)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_bad_detection_status_rejected(self, db_session):
        camera = _make_camera(db_session)
        log = DetectionLog(
            camera_id=camera.camera_id,
            detected_at=datetime.now(UTC),
            snapshot_key="a.jpg",
            confidence_score=0.5,
            source_event_id="evt-status",
            detection_status="Escalated",
        )
        db_session.add(log)
        with pytest.raises(IntegrityError):
            db_session.commit()

    @pytest.mark.parametrize("bad_channel_id", [0, -1])
    def test_non_positive_channel_id_rejected(self, db_session, bad_channel_id):
        camera = Camera(camera_name="Bad Channel Cam", channel_id=bad_channel_id)
        db_session.add(camera)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestPartialUniqueIndexes:
    def test_duplicate_active_camera_name_case_insensitive_rejected(self, db_session):
        _make_camera(db_session, camera_name="North Gate", channel_id=1)
        dup = Camera(camera_name="north gate", channel_id=2)
        db_session.add(dup)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_reusing_a_soft_deleted_cameras_name_succeeds(self, db_session):
        original = _make_camera(db_session, camera_name="Reusable Cam", channel_id=1)
        original.is_active = False
        db_session.add(original)
        db_session.commit()

        replacement = Camera(camera_name="Reusable Cam", channel_id=2)
        db_session.add(replacement)
        db_session.commit()  # must not raise

        assert replacement.camera_id != original.camera_id

    def test_two_soft_deleted_cameras_can_share_a_name(self, db_session):
        first = _make_camera(db_session, camera_name="Dup Name", channel_id=1)
        first.is_active = False
        db_session.add(first)
        db_session.commit()

        second = _make_camera(db_session, camera_name="Dup Name", channel_id=2)
        second.is_active = False
        db_session.add(second)
        db_session.commit()  # must not raise

    def test_duplicate_active_channel_id_rejected(self, db_session):
        _make_camera(db_session, camera_name="Cam One", channel_id=5)
        dup = Camera(camera_name="Cam Two", channel_id=5)
        db_session.add(dup)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_reusing_a_soft_deleted_cameras_channel_id_succeeds(self, db_session):
        original = _make_camera(db_session, camera_name="Chan Cam", channel_id=7)
        original.is_active = False
        db_session.add(original)
        db_session.commit()

        replacement = Camera(camera_name="Chan Cam 2", channel_id=7)
        db_session.add(replacement)
        db_session.commit()  # must not raise


class TestOneOpenIncidentPerCamera:
    @pytest.mark.parametrize(
        "first_status,second_status",
        [
            (DetectionStatus.UNVERIFIED, DetectionStatus.UNVERIFIED),
            (DetectionStatus.UNVERIFIED, DetectionStatus.ONGOING),
            (DetectionStatus.ONGOING, DetectionStatus.ONGOING),
        ],
    )
    def test_second_open_incident_for_same_camera_raises(
        self, db_session, first_status, second_status
    ):
        camera = _make_camera(db_session)
        first = DetectionLog(
            camera_id=camera.camera_id,
            detected_at=datetime.now(UTC),
            snapshot_key="a.jpg",
            confidence_score=0.5,
            source_event_id="evt-open-1",
            detection_status=first_status.value,
        )
        db_session.add(first)
        db_session.commit()

        second = DetectionLog(
            camera_id=camera.camera_id,
            detected_at=datetime.now(UTC),
            snapshot_key="b.jpg",
            confidence_score=0.5,
            source_event_id="evt-open-2",
            detection_status=second_status.value,
        )
        db_session.add(second)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_a_terminal_status_does_not_block_a_new_open_incident(self, db_session):
        camera = _make_camera(db_session)
        resolved = DetectionLog(
            camera_id=camera.camera_id,
            detected_at=datetime.now(UTC),
            snapshot_key="a.jpg",
            confidence_score=0.5,
            source_event_id="evt-closed",
            detection_status=DetectionStatus.RESOLVED.value,
        )
        db_session.add(resolved)
        db_session.commit()

        new_open = DetectionLog(
            camera_id=camera.camera_id,
            detected_at=datetime.now(UTC),
            snapshot_key="b.jpg",
            confidence_score=0.5,
            source_event_id="evt-new-open",
        )
        db_session.add(new_open)
        db_session.commit()  # must not raise

    def test_duplicate_source_event_id_rejected(self, db_session):
        camera = _make_camera(db_session)
        first = DetectionLog(
            camera_id=camera.camera_id,
            detected_at=datetime.now(UTC),
            snapshot_key="a.jpg",
            confidence_score=0.5,
            source_event_id="evt-dup",
            detection_status=DetectionStatus.RESOLVED.value,
        )
        db_session.add(first)
        db_session.commit()

        second_camera = _make_camera(db_session, camera_name="Other Cam", channel_id=2)
        second = DetectionLog(
            camera_id=second_camera.camera_id,
            detected_at=datetime.now(UTC),
            snapshot_key="b.jpg",
            confidence_score=0.5,
            source_event_id="evt-dup",
        )
        db_session.add(second)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestAuditLogImmutability:
    def test_update_raises(self, db_session):
        log = AuditLog(actor_type="system", action="LOGIN_SUCCESS", result="success")
        db_session.add(log)
        db_session.commit()

        with pytest.raises(Exception, match="audit_log is append-only"):
            db_session.execute(text("UPDATE audit_log SET action = 'LOGOUT'"))

    def test_delete_raises(self, db_session):
        log = AuditLog(actor_type="system", action="LOGIN_SUCCESS", result="success")
        db_session.add(log)
        db_session.commit()

        with pytest.raises(Exception, match="audit_log is append-only"):
            db_session.execute(text("DELETE FROM audit_log"))

    def test_bad_action_rejected(self, db_session):
        log = AuditLog(
            actor_type="system", action="NOT_A_REAL_ACTION", result="success"
        )
        db_session.add(log)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_bad_result_rejected(self, db_session):
        log = AuditLog(actor_type="system", action="LOGIN_SUCCESS", result="maybe")
        db_session.add(log)
        with pytest.raises(IntegrityError):
            db_session.commit()
