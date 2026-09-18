"""Tracker-bound unit cases for the alarm settings validator.

test_settings.py::TestUpdateAlarmSettings already asserts the rejecting and
accepting ends of both ranges. These cover the conditions the tracker cases
state that it does not reach: the mid-range values, and the requirement that a
rejected value never reaches the stored alarm settings record.

Binding:
    TC-UNIT-025  snooze duration validator, 15 to 60 second bounds
    TC-UNIT-026  alarm volume validator, 0 to 100 bounds
"""

from app.models import AlarmSettings
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from .conftest import auth_headers, make_operator


def _headers(client: TestClient, session: Session) -> dict:
    make_operator(session, username="tcsettingsop", password="Operator123")
    return auth_headers(client, "tcsettingsop", "Operator123")


def _put(client: TestClient, headers: dict, **overrides):
    body = {"alarm_sound": "default", "volume": 50, "snooze_duration": 30}
    body.update(overrides)
    return client.put("/api/settings/alarm", headers=headers, json=body)


def _stored(session: Session) -> AlarmSettings | None:
    session.expire_all()
    return session.exec(select(AlarmSettings)).first()


class TestSnoozeDurationValidator:
    """TC-UNIT-025."""

    def test_mid_range_value_is_accepted(self, client: TestClient, session: Session):
        """Acceptance 1 names 15, 30, and 60. The existing test covers 15 and
        60; 30 is asserted here."""
        headers = _headers(client, session)
        assert _put(client, headers, snooze_duration=30).status_code == 200
        assert _stored(session).snooze_duration == 30

    def test_rejected_values_are_not_written_to_the_record(
        self, client: TestClient, session: Session
    ):
        """Acceptance 3: no rejected value is written to the alarm settings
        record."""
        headers = _headers(client, session)
        assert _put(client, headers, snooze_duration=30).status_code == 200
        assert _stored(session).snooze_duration == 30

        for rejected in (14, 61):
            assert _put(client, headers, snooze_duration=rejected).status_code == 422
            assert _stored(session).snooze_duration == 30, (
                f"rejected snooze_duration {rejected} reached the record"
            )


class TestAlarmVolumeValidator:
    """TC-UNIT-026."""

    def test_mid_range_value_is_accepted(self, client: TestClient, session: Session):
        """Acceptance 1 names 0, 80, and 100. The existing test covers 0 and
        100; 80 is asserted here."""
        headers = _headers(client, session)
        assert _put(client, headers, volume=80).status_code == 200
        assert _stored(session).volume == 80

    def test_rejected_values_are_not_written_to_the_record(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        assert _put(client, headers, volume=80).status_code == 200
        assert _stored(session).volume == 80

        for rejected in (-1, 101):
            assert _put(client, headers, volume=rejected).status_code == 422
            assert _stored(session).volume == 80, (
                f"rejected volume {rejected} reached the record"
            )
