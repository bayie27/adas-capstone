"""Tests for /api/settings/alarm — 01_CONTRACTS.md §5.6, D-004."""

from app.models import AuditLog
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from .conftest import auth_headers, make_operator


def _headers(client: TestClient, session: Session) -> dict:
    make_operator(session, username="settingsop", password="Operator123")
    return auth_headers(client, "settingsop", "Operator123")


class TestGetAlarmSettings:
    def test_returns_defaults_for_a_fresh_account(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        resp = client.get("/api/settings/alarm", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == {
            "alarm_sound": "default",
            "volume": 80,
            "snooze_duration": 30,
        }

    def test_is_side_effect_free(self, client: TestClient, session: Session):
        headers = _headers(client, session)
        client.get("/api/settings/alarm", headers=headers)
        count = len(session.exec(select(AuditLog)).all())
        client.get("/api/settings/alarm", headers=headers)
        assert len(session.exec(select(AuditLog)).all()) == count

    def test_requires_auth(self, client: TestClient):
        resp = client.get("/api/settings/alarm")
        assert resp.status_code == 401


class TestUpdateAlarmSettings:
    def test_full_replacement_roundtrip(self, client: TestClient, session: Session):
        headers = _headers(client, session)
        resp = client.put(
            "/api/settings/alarm",
            headers=headers,
            json={"alarm_sound": "default", "volume": 55, "snooze_duration": 45},
        )
        assert resp.status_code == 200
        assert resp.json() == {
            "alarm_sound": "default",
            "volume": 55,
            "snooze_duration": 45,
        }

        follow_up = client.get("/api/settings/alarm", headers=headers)
        assert follow_up.json()["volume"] == 55

    def test_writes_audit_row_on_real_change(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        client.put(
            "/api/settings/alarm",
            headers=headers,
            json={"alarm_sound": "default", "volume": 60, "snooze_duration": 20},
        )
        rows = session.exec(
            select(AuditLog).where(AuditLog.action == "ALARM_SETTINGS_UPDATE")
        ).all()
        assert len(rows) == 1

    def test_no_op_save_writes_no_redundant_audit_row(
        self, client: TestClient, session: Session
    ):
        """UC-11 — saving without changing anything must not write a
        redundant audit row."""
        headers = _headers(client, session)
        payload = {"alarm_sound": "default", "volume": 80, "snooze_duration": 30}
        client.put("/api/settings/alarm", headers=headers, json=payload)
        rows_after_first = session.exec(
            select(AuditLog).where(AuditLog.action == "ALARM_SETTINGS_UPDATE")
        ).all()

        client.put("/api/settings/alarm", headers=headers, json=payload)
        rows_after_second = session.exec(
            select(AuditLog).where(AuditLog.action == "ALARM_SETTINGS_UPDATE")
        ).all()

        assert len(rows_after_second) == len(rows_after_first)

    def test_rejects_disallowed_sound(self, client: TestClient, session: Session):
        headers = _headers(client, session)
        resp = client.put(
            "/api/settings/alarm",
            headers=headers,
            json={"alarm_sound": "siren", "volume": 50, "snooze_duration": 30},
        )
        assert resp.status_code == 422

    def test_volume_boundaries(self, client: TestClient, session: Session):
        headers = _headers(client, session)
        assert (
            client.put(
                "/api/settings/alarm",
                headers=headers,
                json={"alarm_sound": "default", "volume": -1, "snooze_duration": 30},
            ).status_code
            == 422
        )
        assert (
            client.put(
                "/api/settings/alarm",
                headers=headers,
                json={"alarm_sound": "default", "volume": 101, "snooze_duration": 30},
            ).status_code
            == 422
        )
        assert (
            client.put(
                "/api/settings/alarm",
                headers=headers,
                json={"alarm_sound": "default", "volume": 0, "snooze_duration": 30},
            ).status_code
            == 200
        )
        assert (
            client.put(
                "/api/settings/alarm",
                headers=headers,
                json={"alarm_sound": "default", "volume": 100, "snooze_duration": 30},
            ).status_code
            == 200
        )

    def test_snooze_duration_boundaries(self, client: TestClient, session: Session):
        headers = _headers(client, session)
        assert (
            client.put(
                "/api/settings/alarm",
                headers=headers,
                json={"alarm_sound": "default", "volume": 50, "snooze_duration": 14},
            ).status_code
            == 422
        )
        assert (
            client.put(
                "/api/settings/alarm",
                headers=headers,
                json={"alarm_sound": "default", "volume": 50, "snooze_duration": 61},
            ).status_code
            == 422
        )
        assert (
            client.put(
                "/api/settings/alarm",
                headers=headers,
                json={"alarm_sound": "default", "volume": 50, "snooze_duration": 15},
            ).status_code
            == 200
        )
        assert (
            client.put(
                "/api/settings/alarm",
                headers=headers,
                json={"alarm_sound": "default", "volume": 50, "snooze_duration": 60},
            ).status_code
            == 200
        )

    def test_requires_auth(self, client: TestClient):
        resp = client.put(
            "/api/settings/alarm",
            json={"alarm_sound": "default", "volume": 50, "snooze_duration": 30},
        )
        assert resp.status_code == 401
