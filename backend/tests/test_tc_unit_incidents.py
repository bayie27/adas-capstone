"""Tracker-bound unit cases for stream construction, cooldown, incident state
and camera configuration versioning.

Binding:
    TC-UNIT-010  RTSP address builder, channel and main stream parameter
    TC-UNIT-031  dismissal cooldown expiry is exactly 60 seconds
    TC-UNIT-034  an Ongoing incident can be terminally dismissed
    TC-UNIT-035  at most one open incident per camera, enforced by the index
    TC-UNIT-043  config_version increments on configuration change

TC-UNIT-043 asserts that every persisted camera configuration change advances
config_version, including a camera rename.
"""

from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import settings
from app.core.redaction import redact_text
from app.models import DetectionLog
from app.models.enums import DetectionStatus
from app.services.cameras import _build_rtsp_url
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from .conftest import auth_headers, make_admin, make_camera, make_detection

# ---------------------------------------------------------------------------
# TC-UNIT-010
# ---------------------------------------------------------------------------


class TestRtspAddressBuilder:
    """The template is operator-configurable, so the case is exercised against
    a realistic Dahua DSS template carrying credentials and the main stream
    selector (subtype=0). 2K is the encoder configuration on that main stream
    rather than a token in the URL, so what the address must prove is that it
    selects the main stream and not the substream.
    """

    TEMPLATE = (
        "rtsp://{dss_username}:{dss_password}@{dss_ip}:{dss_port}"
        "/cam/realmonitor?channel={channel_id}&subtype=0"
    )

    def test_address_targets_gateway_channel_and_main_stream(self, monkeypatch):
        """Acceptance 1."""
        monkeypatch.setattr(settings, "RTSP_URL_TEMPLATE", self.TEMPLATE)
        monkeypatch.setattr(settings, "DSS_IP", "10.0.5.50")
        monkeypatch.setattr(settings, "DSS_PORT", 554)
        monkeypatch.setattr(settings, "DSS_USERNAME", "dssuser")
        monkeypatch.setattr(settings, "DSS_PASS", None)

        url = _build_rtsp_url(12)

        assert "10.0.5.50:554" in url
        assert "channel=12" in url
        assert "subtype=0" in url, "address does not select the main stream"
        assert "subtype=1" not in url, "address selects a substream"

    def test_credential_portion_is_hidden_when_logged_or_persisted(self, monkeypatch):
        """Acceptance 2."""
        monkeypatch.setattr(settings, "RTSP_URL_TEMPLATE", self.TEMPLATE)
        monkeypatch.setattr(settings, "DSS_IP", "10.0.5.50")
        monkeypatch.setattr(settings, "DSS_PORT", 554)
        monkeypatch.setattr(settings, "DSS_USERNAME", "dssuser")

        url = self.TEMPLATE.format(
            dss_username="dssuser",
            dss_password="sekret",
            dss_ip="10.0.5.50",
            dss_port=554,
            channel_id=12,
        )
        redacted = redact_text(url)

        assert "sekret" not in redacted
        assert "dssuser" not in redacted
        assert "://***:***@" in redacted
        # The non-credential portion survives, so the record stays diagnosable.
        assert "channel=12" in redacted
        assert "subtype=0" in redacted


# ---------------------------------------------------------------------------
# TC-UNIT-031
# ---------------------------------------------------------------------------


class TestDismissalCooldown:
    def test_configured_cooldown_is_sixty_seconds(self):
        assert settings.DISMISS_COOLDOWN_SECONDS == 60

    def test_cooldown_until_is_the_dismissal_instant_plus_sixty_seconds(
        self, client: TestClient, session: Session
    ):
        """Acceptance: cooldown_until equals the frozen instant plus 60
        seconds, and desired_state_reason is set to the cooldown reason."""
        make_admin(session, username="tccooldown", password="Admin123")
        headers = auth_headers(client, "tccooldown", "Admin123")
        camera = make_camera(session, name="TC Cooldown Cam", channel_id=312)
        log = make_detection(session, camera, status=DetectionStatus.UNVERIFIED)

        before = datetime.now(UTC)
        resp = client.post(f"/api/alerts/{log.log_id}/dismiss", headers=headers)
        after = datetime.now(UTC)
        assert resp.status_code == 200

        session.refresh(camera)
        assert camera.desired_state_reason == "cooldown"
        assert camera.cooldown_until is not None

        cooldown_until = camera.cooldown_until
        if cooldown_until.tzinfo is None:
            cooldown_until = cooldown_until.replace(tzinfo=UTC)

        # The dismissal instant is bracketed rather than frozen, so the expiry
        # must land 60s after some instant inside that bracket.
        assert before + timedelta(seconds=60) <= cooldown_until
        assert cooldown_until <= after + timedelta(seconds=60)


# ---------------------------------------------------------------------------
# TC-UNIT-034
# ---------------------------------------------------------------------------


class TestOngoingTerminalDismissal:
    def test_ongoing_incident_can_be_dismissed_preserving_verification(
        self, client: TestClient, session: Session
    ):
        """Acceptance 1, 2 and 3."""
        admin = make_admin(session, username="tcongoing", password="Admin123")
        headers = auth_headers(client, "tcongoing", "Admin123")
        camera = make_camera(session, name="TC Ongoing Cam", channel_id=313)
        log = make_detection(session, camera, status=DetectionStatus.UNVERIFIED)

        assert (
            client.post(
                f"/api/alerts/{log.log_id}/confirm", headers=headers
            ).status_code
            == 200
        )
        session.refresh(log)
        assert log.detection_status == DetectionStatus.ONGOING.value
        verified_by = log.verified_by_id
        verified_at = log.verified_at
        assert verified_by == admin.user_id
        assert verified_at is not None

        assert (
            client.post(
                f"/api/alerts/{log.log_id}/dismiss", headers=headers
            ).status_code
            == 200
        )
        session.refresh(log)

        assert log.detection_status == DetectionStatus.DISMISSED.value
        assert log.closed_by_id == admin.user_id
        assert log.closed_at is not None
        assert log.verified_by_id == verified_by
        assert log.verified_at == verified_at


# ---------------------------------------------------------------------------
# TC-UNIT-035
# ---------------------------------------------------------------------------


class TestOneOpenIncidentPerCamera:
    def test_second_concurrent_open_incident_is_rejected(self, session: Session):
        """Acceptance 1: rejected by the partial unique index."""
        camera = make_camera(session, name="TC Index Cam", channel_id=314)
        make_detection(session, camera, status=DetectionStatus.UNVERIFIED)

        duplicate = DetectionLog(
            camera_id=camera.camera_id,
            detected_at=datetime.now(UTC),
            snapshot_key="dup.jpg",
            confidence_score=0.9,
            detection_status=DetectionStatus.UNVERIFIED.value,
            source_event_id="tc-unit-035-duplicate",
        )
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    def test_new_incident_accepted_once_the_first_is_terminal(self, session: Session):
        """Acceptance 2."""
        camera = make_camera(session, name="TC Index Cam 2", channel_id=315)
        first = make_detection(session, camera, status=DetectionStatus.UNVERIFIED)

        first.detection_status = DetectionStatus.DISMISSED.value
        session.add(first)
        session.commit()

        second = DetectionLog(
            camera_id=camera.camera_id,
            detected_at=datetime.now(UTC),
            snapshot_key="second.jpg",
            confidence_score=0.9,
            detection_status=DetectionStatus.UNVERIFIED.value,
            source_event_id="tc-unit-035-second",
        )
        session.add(second)
        session.commit()
        session.refresh(second)
        assert second.log_id is not None


# ---------------------------------------------------------------------------
# TC-UNIT-043
# ---------------------------------------------------------------------------


class TestConfigVersionMonotonicity:
    def test_config_version_increases_on_every_persisted_change(
        self, client: TestClient, session: Session
    ):
        """Acceptance: config_version starts at 1 and increases by at least one
        on every persisted configuration change, and never decreases."""
        make_admin(session, username="tcconfigver", password="Admin123")
        headers = auth_headers(client, "tcconfigver", "Admin123")
        # desired_ai_state is seeded to what the real create route would have
        # derived. Without it the first PATCH performs a first-time
        # desired-state recompute, and that recompute -- not the rename --
        # supplies the version bump, masking the behaviour under test.
        camera = make_camera(
            session,
            name="TC Version Cam",
            channel_id=316,
            desired_ai_state="Active",
        )

        session.refresh(camera)
        assert camera.config_version == 1
        seen = [camera.config_version]

        for payload in (
            {"camera_name": "TC Version Cam Renamed"},
            {"channel_id": 317},
            {"is_enabled": False},
        ):
            resp = client.patch(
                f"/api/cameras/{camera.camera_id}", json=payload, headers=headers
            )
            assert resp.status_code == 200, resp.text
            session.refresh(camera)
            assert camera.config_version > seen[-1], (
                f"config_version did not increase after {payload}"
            )
            seen.append(camera.config_version)

        assert seen == sorted(seen)
