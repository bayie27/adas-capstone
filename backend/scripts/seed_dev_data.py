from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from _bootstrap import bootstrap_backend

bootstrap_backend()

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
from sqlmodel import Session, select

DEFAULT_SEED_PROFILE = "demo"
SEED_PROFILES = ("demo", "analytics", "edge")


@dataclass(frozen=True)
class SeedAlertSpec:
    label: str
    camera_key: str
    detected_at: datetime
    confidence_score: float
    detection_status: DetectionStatus
    verified_by_key: str | None = None
    verified_after_minutes: int | None = None
    closed_by_key: str | None = None
    closed_after_minutes: int | None = None


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
        password_changed_at=datetime.now(UTC),
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
    camera = session.exec(
        select(Camera).where(Camera.camera_name == camera_name)
    ).first()
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


def seeded_timestamp(
    now: datetime,
    *,
    days_ago: int = 0,
    hour: int | None = None,
    minute: int = 0,
    minutes_ago: int | None = None,
) -> datetime:
    """Create stable dev timestamps without accidentally seeding future rows."""
    if minutes_ago is not None:
        return (now - timedelta(minutes=minutes_ago)).replace(second=0, microsecond=0)

    if hour is None:
        raise ValueError("`hour` is required when `minutes_ago` is not provided.")

    candidate = (now - timedelta(days=days_ago)).replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )
    if candidate > now:
        candidate -= timedelta(days=1)
    return candidate


def seed_sample_cameras(
    session: Session,
) -> tuple[Camera, Camera, Camera, Camera, Camera, Camera]:
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


def build_demo_alert_specs(now: datetime) -> list[SeedAlertSpec]:
    return [
        SeedAlertSpec(
            label="ayala_recent_unverified",
            camera_key="ayala",
            detected_at=seeded_timestamp(now, minutes_ago=12),
            confidence_score=0.97,
            detection_status=DetectionStatus.UNVERIFIED,
        ),
        SeedAlertSpec(
            label="ayala_ongoing_morning",
            camera_key="ayala",
            detected_at=seeded_timestamp(now, days_ago=0, hour=8, minute=12),
            confidence_score=0.93,
            detection_status=DetectionStatus.ONGOING,
            verified_by_key="dsahagun",
            verified_after_minutes=3,
        ),
        SeedAlertSpec(
            label="ayala_resolved_evening",
            camera_key="ayala",
            detected_at=seeded_timestamp(now, days_ago=1, hour=19, minute=40),
            confidence_score=0.95,
            detection_status=DetectionStatus.RESOLVED,
            verified_by_key="ealonzo",
            verified_after_minutes=4,
            closed_by_key="jtenorio",
            closed_after_minutes=28,
        ),
        SeedAlertSpec(
            label="ayala_resolved_weekend",
            camera_key="ayala",
            detected_at=seeded_timestamp(now, days_ago=7, hour=10, minute=30),
            confidence_score=0.89,
            detection_status=DetectionStatus.RESOLVED,
            verified_by_key="smeer",
            verified_after_minutes=5,
            closed_by_key="ealonzo",
            closed_after_minutes=14,
        ),
        SeedAlertSpec(
            label="southbound_recent_unverified",
            camera_key="southbound",
            detected_at=seeded_timestamp(now, minutes_ago=33),
            confidence_score=0.79,
            detection_status=DetectionStatus.UNVERIFIED,
        ),
        SeedAlertSpec(
            label="southbound_resolved_peak",
            camera_key="southbound",
            detected_at=seeded_timestamp(now, days_ago=0, hour=14, minute=5),
            confidence_score=0.88,
            detection_status=DetectionStatus.RESOLVED,
            verified_by_key="ealonzo",
            verified_after_minutes=5,
            closed_by_key="ealonzo",
            closed_after_minutes=18,
        ),
        SeedAlertSpec(
            label="southbound_dismissed_false_positive",
            camera_key="southbound",
            detected_at=seeded_timestamp(now, days_ago=2, hour=11, minute=35),
            confidence_score=0.41,
            detection_status=DetectionStatus.DISMISSED,
            closed_by_key="smeer",
            closed_after_minutes=7,
        ),
        SeedAlertSpec(
            label="north_exit_dismissed_human_correction",
            camera_key="north_exit",
            detected_at=seeded_timestamp(now, days_ago=3, hour=6, minute=50),
            confidence_score=0.73,
            detection_status=DetectionStatus.DISMISSED,
            verified_by_key="smeer",
            verified_after_minutes=2,
            closed_by_key="dsahagun",
            closed_after_minutes=10,
        ),
        SeedAlertSpec(
            label="inosluban_ongoing_evening",
            camera_key="inosluban",
            detected_at=seeded_timestamp(now, days_ago=0, hour=17, minute=20),
            confidence_score=0.90,
            detection_status=DetectionStatus.ONGOING,
            verified_by_key="jtenorio",
            verified_after_minutes=6,
        ),
        SeedAlertSpec(
            label="inosluban_resolved_crossover",
            camera_key="inosluban",
            detected_at=seeded_timestamp(now, days_ago=4, hour=9, minute=10),
            confidence_score=0.86,
            detection_status=DetectionStatus.RESOLVED,
            verified_by_key="dsahagun",
            verified_after_minutes=3,
            closed_by_key="jtenorio",
            closed_after_minutes=25,
        ),
        SeedAlertSpec(
            label="inosluban_dismissed_false_positive",
            camera_key="inosluban",
            detected_at=seeded_timestamp(now, days_ago=1, hour=7, minute=45),
            confidence_score=0.38,
            detection_status=DetectionStatus.DISMISSED,
            closed_by_key="dsahagun",
            closed_after_minutes=6,
        ),
        SeedAlertSpec(
            label="tambo_recent_unverified",
            camera_key="tambo",
            detected_at=seeded_timestamp(now, minutes_ago=5),
            confidence_score=0.82,
            detection_status=DetectionStatus.UNVERIFIED,
        ),
        SeedAlertSpec(
            label="tambo_ongoing_midday",
            camera_key="tambo",
            detected_at=seeded_timestamp(now, days_ago=3, hour=12, minute=5),
            confidence_score=0.91,
            detection_status=DetectionStatus.ONGOING,
            verified_by_key="smeer",
            verified_after_minutes=3,
        ),
        SeedAlertSpec(
            label="tambo_resolved_longtail",
            camera_key="tambo",
            detected_at=seeded_timestamp(now, days_ago=6, hour=20, minute=25),
            confidence_score=0.84,
            detection_status=DetectionStatus.RESOLVED,
            verified_by_key="jtenorio",
            verified_after_minutes=5,
            closed_by_key="ealonzo",
            closed_after_minutes=40,
        ),
        SeedAlertSpec(
            label="tambo_dismissed_false_positive",
            camera_key="tambo",
            detected_at=seeded_timestamp(now, days_ago=2, hour=15, minute=55),
            confidence_score=0.52,
            detection_status=DetectionStatus.DISMISSED,
            closed_by_key="ealonzo",
            closed_after_minutes=8,
        ),
        SeedAlertSpec(
            label="dagatan_ongoing_pre_dawn",
            camera_key="dagatan",
            detected_at=seeded_timestamp(now, days_ago=0, hour=5, minute=55),
            confidence_score=0.92,
            detection_status=DetectionStatus.ONGOING,
            verified_by_key="ealonzo",
            verified_after_minutes=4,
        ),
        SeedAlertSpec(
            label="dagatan_resolved_night",
            camera_key="dagatan",
            detected_at=seeded_timestamp(now, days_ago=1, hour=22, minute=10),
            confidence_score=0.94,
            detection_status=DetectionStatus.RESOLVED,
            verified_by_key="jtenorio",
            verified_after_minutes=3,
            closed_by_key="jtenorio",
            closed_after_minutes=45,
        ),
        SeedAlertSpec(
            label="dagatan_dismissed_human_correction",
            camera_key="dagatan",
            detected_at=seeded_timestamp(now, days_ago=5, hour=13, minute=15),
            confidence_score=0.68,
            detection_status=DetectionStatus.DISMISSED,
            verified_by_key="dsahagun",
            verified_after_minutes=2,
            closed_by_key="smeer",
            closed_after_minutes=20,
        ),
    ]


def build_analytics_alert_specs(now: datetime) -> list[SeedAlertSpec]:
    specs = list(build_demo_alert_specs(now))
    operator_keys = ["dsahagun", "ealonzo", "smeer", "jtenorio"]

    for day in range(14):
        verifier = operator_keys[day % len(operator_keys)]
        closer = operator_keys[(day + 1) % len(operator_keys)]
        correction_verifier = operator_keys[(day + 2) % len(operator_keys)]
        correction_closer = operator_keys[(day + 3) % len(operator_keys)]

        specs.append(
            SeedAlertSpec(
                label=f"analytics_ayala_resolved_day_{day + 1}",
                camera_key="ayala",
                detected_at=seeded_timestamp(
                    now,
                    days_ago=day,
                    hour=8,
                    minute=10 + (day % 3) * 7,
                ),
                confidence_score=0.96 - (day % 5) * 0.02,
                detection_status=DetectionStatus.RESOLVED,
                verified_by_key=verifier,
                verified_after_minutes=3 + (day % 3),
                closed_by_key=closer,
                closed_after_minutes=18 + (day % 4) * 6,
            )
        )
        specs.append(
            SeedAlertSpec(
                label=f"analytics_inosluban_dismissed_day_{day + 1}",
                camera_key="inosluban",
                detected_at=seeded_timestamp(
                    now,
                    days_ago=day,
                    hour=17,
                    minute=5 + (day % 4) * 6,
                ),
                confidence_score=0.57 - (day % 4) * 0.04,
                detection_status=DetectionStatus.DISMISSED,
                verified_by_key=correction_verifier if day % 2 == 0 else None,
                verified_after_minutes=2 if day % 2 == 0 else None,
                closed_by_key=correction_closer,
                closed_after_minutes=9 + (day % 3) * 4,
            )
        )

        if day % 2 == 0:
            specs.append(
                SeedAlertSpec(
                    label=f"analytics_tambo_ongoing_day_{day + 1}",
                    camera_key="tambo",
                    detected_at=seeded_timestamp(
                        now,
                        days_ago=day,
                        hour=12,
                        minute=20 + (day % 2) * 10,
                    ),
                    confidence_score=0.90 - (day % 3) * 0.02,
                    detection_status=DetectionStatus.ONGOING,
                    verified_by_key=operator_keys[(day + 1) % len(operator_keys)],
                    verified_after_minutes=4,
                )
            )

        if day % 3 == 0:
            specs.append(
                SeedAlertSpec(
                    label=f"analytics_dagatan_resolved_day_{day + 1}",
                    camera_key="dagatan",
                    detected_at=seeded_timestamp(
                        now,
                        days_ago=day,
                        hour=5,
                        minute=40 + (day % 3) * 5,
                    ),
                    confidence_score=0.93 - (day % 4) * 0.01,
                    detection_status=DetectionStatus.RESOLVED,
                    verified_by_key=operator_keys[(day + 2) % len(operator_keys)],
                    verified_after_minutes=3,
                    closed_by_key=operator_keys[(day + 2) % len(operator_keys)],
                    closed_after_minutes=26,
                )
            )

        if day % 4 == 0:
            specs.append(
                SeedAlertSpec(
                    label=f"analytics_southbound_unverified_day_{day + 1}",
                    camera_key="southbound",
                    detected_at=seeded_timestamp(
                        now,
                        days_ago=day,
                        hour=21,
                        minute=15 + (day % 2) * 10,
                    ),
                    confidence_score=0.74 - (day % 3) * 0.03,
                    detection_status=DetectionStatus.UNVERIFIED,
                )
            )

    return specs


def build_edge_alert_specs(now: datetime) -> list[SeedAlertSpec]:
    return [
        SeedAlertSpec(
            label="edge_ayala_unverified_recent",
            camera_key="ayala",
            detected_at=seeded_timestamp(now, minutes_ago=3),
            confidence_score=0.99,
            detection_status=DetectionStatus.UNVERIFIED,
        ),
        SeedAlertSpec(
            label="edge_ayala_dismissed_closed_only",
            camera_key="ayala",
            detected_at=seeded_timestamp(now, days_ago=0, hour=9, minute=5),
            confidence_score=0.44,
            detection_status=DetectionStatus.DISMISSED,
            closed_by_key="dsahagun",
            closed_after_minutes=5,
        ),
        SeedAlertSpec(
            label="edge_ayala_ongoing_verified_only",
            camera_key="ayala",
            detected_at=seeded_timestamp(now, days_ago=0, hour=9, minute=40),
            confidence_score=0.87,
            detection_status=DetectionStatus.ONGOING,
            verified_by_key="ealonzo",
            verified_after_minutes=2,
        ),
        SeedAlertSpec(
            label="edge_southbound_resolved_same_user",
            camera_key="southbound",
            detected_at=seeded_timestamp(now, days_ago=1, hour=14, minute=15),
            confidence_score=0.91,
            detection_status=DetectionStatus.RESOLVED,
            verified_by_key="smeer",
            verified_after_minutes=3,
            closed_by_key="smeer",
            closed_after_minutes=16,
        ),
        SeedAlertSpec(
            label="edge_southbound_resolved_different_users",
            camera_key="southbound",
            detected_at=seeded_timestamp(now, days_ago=1, hour=15, minute=5),
            confidence_score=0.89,
            detection_status=DetectionStatus.RESOLVED,
            verified_by_key="dsahagun",
            verified_after_minutes=4,
            closed_by_key="jtenorio",
            closed_after_minutes=22,
        ),
        SeedAlertSpec(
            label="edge_north_exit_dismissed_after_verification",
            camera_key="north_exit",
            detected_at=seeded_timestamp(now, days_ago=2, hour=6, minute=25),
            confidence_score=0.67,
            detection_status=DetectionStatus.DISMISSED,
            verified_by_key="jtenorio",
            verified_after_minutes=2,
            closed_by_key="ealonzo",
            closed_after_minutes=12,
        ),
        SeedAlertSpec(
            label="edge_inosluban_resolved_long_close",
            camera_key="inosluban",
            detected_at=seeded_timestamp(now, days_ago=3, hour=19, minute=10),
            confidence_score=0.85,
            detection_status=DetectionStatus.RESOLVED,
            verified_by_key="ealonzo",
            verified_after_minutes=5,
            closed_by_key="dsahagun",
            closed_after_minutes=55,
        ),
        SeedAlertSpec(
            label="edge_tambo_unverified_older",
            camera_key="tambo",
            detected_at=seeded_timestamp(now, days_ago=4, hour=11, minute=45),
            confidence_score=0.78,
            detection_status=DetectionStatus.UNVERIFIED,
        ),
        SeedAlertSpec(
            label="edge_dagatan_dismissed_closed_only",
            camera_key="dagatan",
            detected_at=seeded_timestamp(now, days_ago=5, hour=13, minute=5),
            confidence_score=0.49,
            detection_status=DetectionStatus.DISMISSED,
            closed_by_key="smeer",
            closed_after_minutes=6,
        ),
        SeedAlertSpec(
            label="edge_dagatan_ongoing_recent",
            camera_key="dagatan",
            detected_at=seeded_timestamp(now, minutes_ago=48),
            confidence_score=0.93,
            detection_status=DetectionStatus.ONGOING,
            verified_by_key="jtenorio",
            verified_after_minutes=4,
        ),
    ]


PROFILE_BUILDERS = {
    "demo": build_demo_alert_specs,
    "analytics": build_analytics_alert_specs,
    "edge": build_edge_alert_specs,
}


def build_alert_specs(profile: str, now: datetime) -> list[SeedAlertSpec]:
    try:
        return PROFILE_BUILDERS[profile](now)
    except KeyError as exc:
        valid_profiles = ", ".join(SEED_PROFILES)
        raise ValueError(
            f"Unknown seed profile '{profile}'. Expected one of: {valid_profiles}."
        ) from exc


def seed_cameras_only() -> None:
    init_db()
    with Session(engine) as session:
        seed_sample_cameras(session)
    print("Camera seeding complete.")


def seed_dev_data(*, profile: str = DEFAULT_SEED_PROFILE) -> None:
    init_db()

    now = datetime.now(UTC)

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

        camera_1, camera_2, camera_3, camera_4, camera_5, camera_6 = (
            seed_sample_cameras(session)
        )

        operators = {
            "dsahagun": operator_1,
            "ealonzo": operator_2,
            "smeer": operator_3,
            "jtenorio": operator_4,
        }
        cameras = {
            "ayala": camera_1,
            "southbound": camera_2,
            "north_exit": camera_3,
            "inosluban": camera_4,
            "tambo": camera_5,
            "dagatan": camera_6,
        }
        alert_specs = build_alert_specs(profile, now)

        def make_snapshot(cam_id: int, dt: datetime, label: str) -> str:
            return f"cam{cam_id}_{dt.strftime('%Y%m%d_%H%M%S')}_{label}.jpg"

        status_counts: Counter[str] = Counter()
        camera_counts: Counter[str] = Counter()
        verifier_counts: Counter[str] = Counter()
        closer_counts: Counter[str] = Counter()

        for spec in alert_specs:
            try:
                camera = cameras[spec.camera_key]
            except KeyError as exc:
                raise RuntimeError(
                    f"Unknown camera key in seed spec: {spec.camera_key}"
                ) from exc

            if camera.camera_id is None:
                raise RuntimeError(
                    f"Camera {camera.camera_name} was expected to have a database ID."
                )

            verified_by = (
                operators.get(spec.verified_by_key) if spec.verified_by_key else None
            )
            closed_by = (
                operators.get(spec.closed_by_key) if spec.closed_by_key else None
            )

            if spec.verified_after_minutes is not None and verified_by is None:
                raise RuntimeError(
                    f"Alert {spec.label} has a verification offset but no verifier."
                )
            if spec.closed_after_minutes is not None and closed_by is None:
                raise RuntimeError(
                    f"Alert {spec.label} has a closure offset but no closer."
                )

            ensure_alert(
                session,
                camera_id=camera.camera_id,
                snapshot_path=make_snapshot(
                    camera.camera_id, spec.detected_at, spec.label
                ),
                detected_at=spec.detected_at,
                confidence_score=spec.confidence_score,
                detection_status=spec.detection_status,
                verified_by_id=verified_by.user_id if verified_by else None,
                verified_at=(
                    spec.detected_at + timedelta(minutes=spec.verified_after_minutes)
                    if spec.verified_after_minutes is not None
                    else None
                ),
                closed_by_id=closed_by.user_id if closed_by else None,
                closed_at=(
                    spec.detected_at + timedelta(minutes=spec.closed_after_minutes)
                    if spec.closed_after_minutes is not None
                    else None
                ),
            )
            status_counts[spec.detection_status.value] += 1
            camera_counts[camera.camera_name] += 1
            if verified_by:
                verifier_counts[verified_by.username] += 1
            if closed_by:
                closer_counts[closed_by.username] += 1

        print(f"Dev data seeding complete for profile '{profile}'.")
        print(f"Total alerts seeded: {len(alert_specs)}")
        print("Seeded alert mix:")
        for status in DetectionStatus:
            print(f"  {status.value}: {status_counts.get(status.value, 0)}")
        print("Alerts by camera:")
        for camera_name, count in sorted(
            camera_counts.items(),
            key=lambda item: (-item[1], item[0].lower()),
        ):
            print(f"  {camera_name}: {count}")
        print("Verified by operator:")
        if verifier_counts:
            for username, count in sorted(
                verifier_counts.items(),
                key=lambda item: (-item[1], item[0].lower()),
            ):
                print(f"  {username}: {count}")
        else:
            print("  (none)")
        print("Closed by operator:")
        if closer_counts:
            for username, count in sorted(
                closer_counts.items(),
                key=lambda item: (-item[1], item[0].lower()),
            ):
                print(f"  {username}: {count}")
        else:
            print("  (none)")
        print("Users:")
        print("  admin / DEFAULT_ADMIN_PASSWORD from .env")
        print("  dsahagun / operator123")
        print("  ealonzo / operator123")
        print("  smeer / operator123")
        print("  jtenorio / operator123")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed predictable local dev data for demos, analytics, or edge-case testing."
    )
    parser.add_argument(
        "--profile",
        choices=SEED_PROFILES,
        default=DEFAULT_SEED_PROFILE,
        help=(
            "Seed profile to load: "
            "'demo' for a balanced dataset, "
            "'analytics' for denser chart-friendly data, "
            "or 'edge' for tricky workflow combinations."
        ),
    )
    args = parser.parse_args()

    seed_dev_data(profile=args.profile)


if __name__ == "__main__":
    main()
