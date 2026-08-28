"""Tests for /api/settings/alarm — 01_CONTRACTS.md §5.6, D-004."""

from app.core.config import settings
from app.models import AuditLog
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from .conftest import auth_headers, make_operator


def _headers(client: TestClient, session: Session) -> dict:
    make_operator(session, username="settingsop", password="Operator123")
    return auth_headers(client, "settingsop", "Operator123")


def _expected_options() -> dict:
    """P21 Step 2 — driven from `settings` (alarm_sound_keys, snooze
    bounds), not a second hardcoded copy. volume_min/max have no settings
    entry — 0/100 is the schema's only source for that bound."""
    return {
        "alarm_sound_keys": list(settings.ALARM_SOUND_KEYS),
        "snooze_min_seconds": settings.SNOOZE_MIN_SECONDS,
        "snooze_max_seconds": settings.SNOOZE_MAX_SECONDS,
        "volume_min": 0,
        "volume_max": 100,
    }


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
            "options": _expected_options(),
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
            "options": _expected_options(),
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
            json={
                "alarm_sound": "nonexistent_sound",
                "volume": 50,
                "snooze_duration": 30,
            },
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


class TestAlarmSettingsOptions:
    """P21 Step 2 — every bound is asserted against `settings`, not a
    literal, so a hardcoded test copy can never mask client/server drift."""

    def test_options_present_on_get_and_put_and_match_settings(
        self, client: TestClient, session: Session
    ):
        headers = _headers(client, session)
        get_resp = client.get("/api/settings/alarm", headers=headers)
        put_resp = client.put(
            "/api/settings/alarm",
            headers=headers,
            json={"alarm_sound": "default", "volume": 50, "snooze_duration": 30},
        )
        for resp in (get_resp, put_resp):
            assert resp.status_code == 200, resp.text
            assert resp.json()["options"] == {
                "alarm_sound_keys": list(settings.ALARM_SOUND_KEYS),
                "snooze_min_seconds": settings.SNOOZE_MIN_SECONDS,
                "snooze_max_seconds": settings.SNOOZE_MAX_SECONDS,
                "volume_min": 0,
                "volume_max": 100,
            }

    def test_put_body_ignores_an_unexpected_options_key(
        self, client: TestClient, session: Session
    ):
        """22_FRONTEND_HANDOFF_P21.md §2 — options is read-only/server-owned;
        a client that sends it back must not be rejected."""
        headers = _headers(client, session)
        resp = client.put(
            "/api/settings/alarm",
            headers=headers,
            json={
                "alarm_sound": "default",
                "volume": 50,
                "snooze_duration": 30,
                "options": {"alarm_sound_keys": ["bogus"]},
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["options"]["alarm_sound_keys"] == list(
            settings.ALARM_SOUND_KEYS
        )
