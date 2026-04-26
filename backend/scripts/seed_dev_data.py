from __future__ import annotations

from datetime import datetime, timedelta, timezone

from _bootstrap import bootstrap_backend

bootstrap_backend()

from sqlmodel import Session, select

from app.core.db import engine, init_db
from app.core.security import get_password_hash
from app.models import (
    AIStatus,
    Camera,
    ConnectionStatus,
    DetectionLog,
    DetectionStatus,
    User,
    UserRole,
)


def ensure_user(
    session: Session,
    *,
    username: str,
    first_name: str,
    last_name: str,
    role: UserRole,
    password: str,
    is_active: bool = True,
) -> User:
    user = session.exec(select(User).where(User.username == username)).first()
    if user:
        return user

    user = User(
        username=username,
        first_name=first_name,
        last_name=last_name,
        role=role,
        password_hash=get_password_hash(password),
        is_active=is_active,
        password_changed_at=datetime.now(timezone.utc),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    print(f"Created user {username}")
    return user


def ensure_camera(
    session: Session,
    *,
    camera_name: str,
    channel_id: int,
    connection_status: ConnectionStatus,
    ai_status: AIStatus,
    is_enabled: bool = True,
    is_active: bool = True,
) -> Camera:
    camera = session.exec(select(Camera).where(Camera.camera_name == camera_name)).first()
    if camera:
        return camera

    camera = Camera(
        camera_name=camera_name,
        channel_id=channel_id,
        connection_status=connection_status.value,
        ai_status=ai_status.value,
        is_enabled=is_enabled,
        is_active=is_active,
    )
    session.add(camera)
    session.commit()
    session.refresh(camera)
    print(f"Created camera {camera_name}")
    return camera


def ensure_alert(
    session: Session,
    *,
    camera_id: int,
    snapshot_path: str,
    detected_at: datetime,
    confidence_score: float,
    detection_status: DetectionStatus,
    verified_by_id: int | None = None,
    verified_at: datetime | None = None,
    closed_by_id: int | None = None,
    closed_at: datetime | None = None,
) -> DetectionLog:
    alert = session.exec(
        select(DetectionLog).where(DetectionLog.snapshot_path == snapshot_path)
    ).first()
    if alert:
        return alert

    alert = DetectionLog(
        camera_id=camera_id,
        snapshot_path=snapshot_path,
        detected_at=detected_at,
        confidence_score=confidence_score,
        detection_status=detection_status.value,
        verified_by_id=verified_by_id,
        verified_at=verified_at,
        closed_by_id=closed_by_id,
        closed_at=closed_at,
    )
    session.add(alert)
    session.commit()
    session.refresh(alert)
    print(f"Created alert {snapshot_path}")
    return alert


def seed_sample_cameras(session: Session) -> tuple[Camera, Camera, Camera, Camera, Camera, Camera]:
    camera_1 = ensure_camera(
        session,
        camera_name="Ayala Highway Cam",
        channel_id=1,
        connection_status=ConnectionStatus.CONNECTED,
        ai_status=AIStatus.ACTIVE,
    )
    camera_2 = ensure_camera(
        session,
        camera_name="Southbound Entry Cam",
        channel_id=2,
        connection_status=ConnectionStatus.RECONNECTING,
        ai_status=AIStatus.PAUSED,
    )
    camera_3 = ensure_camera(
        session,
        camera_name="North Exit Cam",
        channel_id=3,
        connection_status=ConnectionStatus.DISCONNECTED,
        ai_status=AIStatus.INACTIVE,
        is_enabled=False,
    )
    camera_4 = ensure_camera(
        session,
        camera_name="Inosluban Intersection",
        channel_id=4,
        connection_status=ConnectionStatus.CONNECTED,
        ai_status=AIStatus.ACTIVE,
    )
    camera_5 = ensure_camera(
        session,
        camera_name="Tambo Highway Cam",
        channel_id=5,
        connection_status=ConnectionStatus.CONNECTED,
        ai_status=AIStatus.ACTIVE,
    )
    camera_6 = ensure_camera(
        session,
        camera_name="Dagatan Entry Cam",
        channel_id=6,
        connection_status=ConnectionStatus.CONNECTED,
        ai_status=AIStatus.ACTIVE,
    )
    return camera_1, camera_2, camera_3, camera_4, camera_5, camera_6


def seed_cameras_only() -> None:
    init_db()
    with Session(engine) as session:
        seed_sample_cameras(session)
    print("Camera seeding complete.")


def seed_dev_data() -> None:
    init_db()

    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        admin = session.exec(select(User).where(User.username == "admin")).first()
        if not admin:
            raise RuntimeError("Expected default admin to exist after init_db().")

        operator_1 = ensure_user(
            session,
            username="dsahagun",
            first_name="Daniel Luis",
            last_name="Sahagun",
            role=UserRole.OPERATOR,
            password="operator123",
        )
        operator_2 = ensure_user(
            session,
            username="ealonzo",
            first_name="Enjey Kashlee",
            last_name="Alonzo",
            role=UserRole.OPERATOR,
            password="operator123",
        )
        operator_3 = ensure_user(
            session,
            username="smeer",
            first_name="Sebastian Angelo",
            last_name="Meer",
            role=UserRole.OPERATOR,
            password="operator123",
        )
        operator_4 = ensure_user(
            session,
            username="jtenorio",
            first_name="Jhon Paulo",
            last_name="Tenorio",
            role=UserRole.OPERATOR,
            password="operator123",
        )

        camera_1, camera_2, camera_3, camera_4, camera_5, camera_6 = seed_sample_cameras(session)

        def make_snapshot(cam_id: int, dt: datetime) -> str:
            return f"cam{cam_id}_{dt.strftime('%Y%m%d_%H%M%S')}.jpg"
        
        dt1 = now - timedelta(minutes=15)
        ensure_alert(
            session,
            camera_id=camera_1.camera_id,
            snapshot_path=make_snapshot(camera_1.camera_id, dt1),
            detected_at=dt1,
            confidence_score=0.96,
            detection_status=DetectionStatus.UNVERIFIED,
        )

        dt2 = now - timedelta(minutes=40)
        ensure_alert(
            session,
            camera_id=camera_1.camera_id,
            snapshot_path=make_snapshot(camera_1.camera_id, dt2),
            detected_at=dt2,
            confidence_score=0.91,
            detection_status=DetectionStatus.ONGOING,
            verified_by_id=operator_1.user_id,
            verified_at=now - timedelta(minutes=35),
        )

        dt3 = now - timedelta(hours=2)
        ensure_alert(
            session,
            camera_id=camera_2.camera_id,
            snapshot_path=make_snapshot(camera_2.camera_id, dt3),
            detected_at=dt3,
            confidence_score=0.88,
            detection_status=DetectionStatus.RESOLVED,
            verified_by_id=operator_2.user_id,
            verified_at=dt3 + timedelta(minutes=5),
            closed_by_id=operator_2.user_id,
            closed_at=dt3 + timedelta(minutes=15),
        )
        
        dt4 = now - timedelta(hours=4)
        ensure_alert(
            session,
            camera_id=camera_3.camera_id,
            snapshot_path=make_snapshot(camera_3.camera_id, dt4),
            detected_at=dt4,
            confidence_score=0.73,
            detection_status=DetectionStatus.DISMISSED,
            verified_by_id=operator_3.user_id,
            verified_at=dt4 + timedelta(minutes=2),
            closed_by_id=operator_3.user_id,
            closed_at=dt4 + timedelta(minutes=10),
        )

        dt5 = now - timedelta(minutes=5)
        ensure_alert(
            session,
            camera_id=camera_5.camera_id,
            snapshot_path=make_snapshot(camera_5.camera_id, dt5),
            detected_at=dt5,
            confidence_score=0.82,
            detection_status=DetectionStatus.UNVERIFIED,
        )

        dt6 = now - timedelta(hours=1)
        ensure_alert(
            session,
            camera_id=camera_6.camera_id,
            snapshot_path=make_snapshot(camera_6.camera_id, dt6),
            detected_at=dt6,
            confidence_score=0.94,
            detection_status=DetectionStatus.RESOLVED,
            verified_by_id=operator_4.user_id,
            verified_at=dt6 + timedelta(minutes=3),
            closed_by_id=operator_4.user_id,
            closed_at=dt6 + timedelta(minutes=45),
        )

        print("Dev data seeding complete.")
        print("Users:")
        print("  admin / DEFAULT_ADMIN_PASSWORD from .env")
        print("  dsahagun / operator123")
        print("  ealonzo / operator123")
        print("  smeer / operator123")
        print("  ptenorio / operator123")


def main() -> None:
    seed_dev_data()


if __name__ == "__main__":
    main()
