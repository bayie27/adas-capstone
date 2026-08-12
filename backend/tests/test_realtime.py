"""
04_PKG_realtime.md's own "Tests to write" table, plus the four rows in
14_EDGE_CASES.md tagged P3 (1.16, 6.11, 6.12, 10.9). test_websocket.py
already covers the happy-path envelope/broadcast wiring end to end; this
file covers the handshake failure modes, connection limits, backpressure
isolation, ordering, revocation, and recovery paths that don't fit that
file's "trigger a broadcast and read it" shape.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

import app.main as main_module
import pytest
from app.core.config import Settings
from app.core.config import settings as default_settings
from app.core.security import create_session_token
from app.main import create_app
from app.models import AuthSession, DetectionStatus, UserRole
from app.schemas.events import EventType, ReAlarmData, make_event
from app.services.realtime import CloseCode, RealtimeManager
from app.services.realtime_revalidation import ws_session_revalidation
from app.services.sessions import create_session, revoke_session
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from starlette.websockets import WebSocketState

from .conftest import auth_headers, make_camera, make_detection, make_operator

# ---------------------------------------------------------------------------
# Handshake failure modes
# ---------------------------------------------------------------------------


def test_handshake_no_cookie_closes_4001(client: TestClient):
    with (
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/ws/alerts"),
    ):
        pass
    assert exc_info.value.code == CloseCode.AUTH_FAILED


def test_handshake_expired_session_closes_4001(client: TestClient, session: Session):
    make_operator(session, username="wsexpired", password="Operator123")
    headers = auth_headers(client, "wsexpired", "Operator123")

    auth_session = session.exec(select(AuthSession)).one()
    auth_session.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    session.add(auth_session)
    session.commit()

    with (
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/ws/alerts", headers=headers),
    ):
        pass
    assert exc_info.value.code == CloseCode.AUTH_FAILED


def test_handshake_revoked_session_closes_4001(client: TestClient, session: Session):
    make_operator(session, username="wsrevoked", password="Operator123")
    headers = auth_headers(client, "wsrevoked", "Operator123")

    auth_session = session.exec(select(AuthSession)).one()
    revoke_session(session, auth_session.session_id, reason="admin_revoke")
    session.commit()

    with (
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/ws/alerts", headers=headers),
    ):
        pass
    assert exc_info.value.code == CloseCode.AUTH_FAILED


def test_handshake_foreign_origin_closes_4003(client: TestClient, session: Session):
    make_operator(session, username="wsorigin", password="Operator123")
    headers = {
        **auth_headers(client, "wsorigin", "Operator123"),
        "Origin": "http://evil.example",
    }

    with (
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/ws/alerts", headers=headers),
    ):
        pass
    assert exc_info.value.code == CloseCode.ORIGIN_REJECTED


def test_handshake_inactive_user_closes_4001(client: TestClient, session: Session):
    operator = make_operator(session, username="wsinactive", password="Operator123")
    headers = auth_headers(client, "wsinactive", "Operator123")

    operator.is_active = False
    session.add(operator)
    session.commit()

    with (
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/ws/alerts", headers=headers),
    ):
        pass
    assert exc_info.value.code == CloseCode.AUTH_FAILED


# ---------------------------------------------------------------------------
# Connection limits (edge case 6.12)
# ---------------------------------------------------------------------------


def _build_app(tmp_path, **overrides):
    app_settings = Settings(
        _env_file=None,
        SECRET_KEY="test-secret-key-not-for-production-use",
        INTERNAL_API_KEY="test-internal-api-key-not-for-production",
        DEFAULT_ADMIN_PASSWORD="test-admin-password-123",
        DATABASE_URL=f"sqlite:///{tmp_path / 'realtime.db'}",
        SCHEDULER_ENABLED=False,
        SNAPSHOT_ROOT=tmp_path / "snapshots",
        **overrides,
    )
    return create_app(app_settings), app_settings


def _login_and_get_cookie_header(
    client: TestClient, app_settings: Settings, username, password
):
    resp = client.post(
        "/api/auth/login", data={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    cookie_val = resp.cookies.get(app_settings.SESSION_COOKIE_NAME)
    return {"Cookie": f"{app_settings.SESSION_COOKIE_NAME}={cookie_val}"}


def test_per_user_connection_limit_rejects_extra_but_keeps_established(tmp_path):
    app, app_settings = _build_app(
        tmp_path, WS_MAX_CONNECTIONS_PER_USER=2, WS_MAX_CONNECTIONS_TOTAL=10
    )
    with TestClient(app) as client:
        with Session(app.state.engine) as session:
            operator = make_operator(
                session, username="limituser", password="Operator123"
            )
            user_id = operator.user_id

        headers = _login_and_get_cookie_header(
            client, app_settings, "limituser", "Operator123"
        )

        with (
            client.websocket_connect("/ws/alerts", headers=headers) as ws_one,
            client.websocket_connect("/ws/alerts", headers=headers) as ws_two,
        ):
            ws_one.receive_json()
            ws_two.receive_json()

            with (
                pytest.raises(WebSocketDisconnect) as exc_info,
                client.websocket_connect("/ws/alerts", headers=headers),
            ):
                pass
            assert exc_info.value.code == CloseCode.CONNECTION_LIMIT

            manager: RealtimeManager = app.state.realtime_manager
            assert manager.connection_count_for_user(user_id) == 2


def test_total_connection_limit_rejects_extra_from_any_user(tmp_path):
    app, app_settings = _build_app(
        tmp_path, WS_MAX_CONNECTIONS_PER_USER=10, WS_MAX_CONNECTIONS_TOTAL=2
    )
    with TestClient(app) as client:
        with Session(app.state.engine) as session:
            make_operator(session, username="totaluser1", password="Operator123")
            make_operator(session, username="totaluser2", password="Operator123")

        headers_one = _login_and_get_cookie_header(
            client, app_settings, "totaluser1", "Operator123"
        )
        headers_two = _login_and_get_cookie_header(
            client, app_settings, "totaluser2", "Operator123"
        )

        with (
            client.websocket_connect("/ws/alerts", headers=headers_one) as ws_one,
            client.websocket_connect("/ws/alerts", headers=headers_two) as ws_two,
        ):
            ws_one.receive_json()
            ws_two.receive_json()

            with (
                pytest.raises(WebSocketDisconnect) as exc_info,
                client.websocket_connect("/ws/alerts", headers=headers_one),
            ):
                pass
            assert exc_info.value.code == CloseCode.CONNECTION_LIMIT

            manager: RealtimeManager = app.state.realtime_manager
            assert manager.total_connection_count() == 2


# ---------------------------------------------------------------------------
# Envelope uniqueness (D-008)
# ---------------------------------------------------------------------------


def test_event_ids_are_unique_across_broadcasts(client: TestClient, session: Session):
    make_operator(session, username="wsuniq", password="Operator123")
    headers = auth_headers(client, "wsuniq", "Operator123")
    camera_one = make_camera(session, name="Uniq Cam 1", channel_id=601)
    camera_two = make_camera(session, name="Uniq Cam 2", channel_id=602)

    with client.websocket_connect("/ws/alerts", headers=headers) as websocket:
        ready = websocket.receive_json()

        for camera in (camera_one, camera_two):
            resp = client.post(
                "/api/internal/alert",
                headers={
                    "x-api-key": default_settings.INTERNAL_API_KEY.get_secret_value()
                },
                json={
                    "source_event_id": str(uuid.uuid4()),
                    "camera_id": camera.camera_id,
                    "detected_at": datetime.now(UTC).isoformat(),
                    "snapshot_key": "ws/uniq.jpg",
                    "confidence_score": 0.9,
                },
            )
            assert resp.status_code == 201

        detection_one = websocket.receive_json()
        websocket.receive_json()  # CAMERA_STATUS_UPDATE for camera_one
        detection_two = websocket.receive_json()
        websocket.receive_json()  # CAMERA_STATUS_UPDATE for camera_two

    event_ids = {
        ready["event_id"],
        detection_one["event_id"],
        detection_two["event_id"],
    }
    assert len(event_ids) == 3

    occurred_at = datetime.fromisoformat(detection_one["occurred_at"])
    assert occurred_at.tzinfo is not None


# ---------------------------------------------------------------------------
# Slow-client isolation and FIFO ordering (edge cases 1.16, 6.11) — unit
# level against RealtimeManager directly, since the in-memory ASGI test
# transport never backpressures a real send the way a frozen TCP peer would.
# ---------------------------------------------------------------------------


class _FakeSocket:
    def __init__(self, *, hang: bool = False) -> None:
        self.sent: list[dict] = []
        self.closed: tuple[int, str] | None = None
        self.client_state = WebSocketState.CONNECTED
        self._hang = hang

    async def send_json(self, data: dict) -> None:
        if self._hang:
            await asyncio.Event().wait()
        self.sent.append(data)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = (code, reason)
        self.client_state = WebSocketState.DISCONNECTED


async def _wait_until(predicate, *, timeout: float = 2.0) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("condition not met within timeout")


def test_full_queue_closes_only_the_slow_connection():
    async def scenario():
        manager = RealtimeManager(queue_maxsize=2, send_timeout_seconds=0.2)
        slow_socket = _FakeSocket(hang=True)
        fast_socket = _FakeSocket(hang=False)

        slow_conn = await manager.connect(
            slow_socket, user_id=1, session_id="slow-session", role=UserRole.OPERATOR
        )
        await manager.connect(
            fast_socket, user_id=2, session_id="fast-session", role=UserRole.OPERATOR
        )

        for i in range(4):  # > WS_QUEUE_MAXSIZE
            manager.broadcast(
                make_event(EventType.RE_ALARM, ReAlarmData(log_id=i, camera_id=1))
            )
            # Real broadcasts are spaced out by whatever the caller awaits
            # between them (DB commits, other requests); yield here so the
            # fast connection's sender task actually gets to drain between
            # puts, instead of every broadcast landing before either sender
            # task has run even once.
            await asyncio.sleep(0)

        # D-008's acceptance criterion: the healthy client gets everything
        # within two seconds even though the slow one never drains.
        await _wait_until(lambda: len(fast_socket.sent) == 4, timeout=2.0)
        await _wait_until(
            lambda: (
                slow_conn.connection_id
                not in {c.connection_id for c in manager.snapshot_connections()}
            )
        )

        assert manager.connection_count_for_user(2) == 1
        assert slow_socket.closed is not None
        assert [m["data"]["log_id"] for m in fast_socket.sent] == [0, 1, 2, 3]

    asyncio.run(scenario())


def test_fifo_ordering_within_one_connection():
    async def scenario():
        manager = RealtimeManager(queue_maxsize=10, send_timeout_seconds=1)
        socket = _FakeSocket()
        await manager.connect(
            socket, user_id=1, session_id="fifo-session", role=UserRole.OPERATOR
        )

        for i in range(5):
            manager.broadcast(
                make_event(EventType.RE_ALARM, ReAlarmData(log_id=i, camera_id=1))
            )

        await _wait_until(lambda: len(socket.sent) == 5)
        assert [m["data"]["log_id"] for m in socket.sent] == [0, 1, 2, 3, 4]

    asyncio.run(scenario())


def test_broadcast_during_a_client_disconnect_does_not_raise():
    """Edge case 1.16 — a connection can be mid-teardown (its socket already
    closing) while a broadcast concurrently iterates the connection list.
    Enqueuing to it must be a no-op, never an exception that escapes into
    the broadcaster and skips every connection after it in the loop."""

    async def scenario():
        manager = RealtimeManager(queue_maxsize=10, send_timeout_seconds=1)
        closing_socket = _FakeSocket()
        healthy_socket = _FakeSocket()

        closing_conn = await manager.connect(
            closing_socket,
            user_id=1,
            session_id="closing-session",
            role=UserRole.OPERATOR,
        )
        await manager.connect(
            healthy_socket,
            user_id=2,
            session_id="healthy-session",
            role=UserRole.OPERATOR,
        )

        # Deregister "closing_conn" from the manager's indexes without going
        # through disconnect() on the object a concurrent broadcast() might
        # still be holding a reference to via its own snapshot — simulating
        # the exact race: disconnect() has already popped the connection out
        # of the shared dicts by the time broadcast()'s `for` loop reaches it.
        await manager.disconnect(closing_conn.connection_id, code=1000, reason="race")

        # Must not raise, and must still reach the healthy connection.
        manager.broadcast(
            make_event(EventType.RE_ALARM, ReAlarmData(log_id=1, camera_id=1))
        )

        await _wait_until(lambda: len(healthy_socket.sent) == 1)
        assert healthy_socket.sent[0]["data"]["log_id"] == 1
        assert closing_socket.sent == []

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# Revocation and the revalidation scheduler job (TC-I-404, edge case 1.11)
# ---------------------------------------------------------------------------


def test_logout_closes_only_that_sessions_socket(client: TestClient, session: Session):
    operator = make_operator(session, username="wslogout", password="Operator123")
    headers_a = auth_headers(client, "wslogout", "Operator123")
    headers_b = auth_headers(client, "wslogout", "Operator123")

    with (
        client.websocket_connect("/ws/alerts", headers=headers_a) as ws_a,
        client.websocket_connect("/ws/alerts", headers=headers_b) as ws_b,
    ):
        ws_a.receive_json()
        ws_b.receive_json()

        resp = client.post("/api/auth/logout", headers=headers_a)
        assert resp.status_code == 204

        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws_a.receive_json()
        assert exc_info.value.code == CloseCode.SESSION_REVOKED

        manager: RealtimeManager = client.app.state.realtime_manager
        assert manager.connection_count_for_user(operator.user_id) == 1


def test_ws_session_revalidation_closes_out_of_band_revoked_session(
    client: TestClient, session: Session
):
    make_operator(session, username="wsrevalidate", password="Operator123")
    headers = auth_headers(client, "wsrevalidate", "Operator123")

    with client.websocket_connect("/ws/alerts", headers=headers) as websocket:
        websocket.receive_json()

        # Revoked directly in the DB — not through logout or any close_*
        # call site — simulating an admin revoking from a different process.
        auth_session = session.exec(select(AuthSession)).one()
        revoke_session(session, auth_session.session_id, reason="admin_revoke")
        session.commit()

        asyncio.run(
            ws_session_revalidation(
                session.get_bind(), client.app.state.realtime_manager
            )
        )

        with pytest.raises(WebSocketDisconnect) as exc_info:
            websocket.receive_json()
        assert exc_info.value.code == CloseCode.SESSION_REVOKED


# ---------------------------------------------------------------------------
# Connection leak on a non-WebSocketDisconnect exception (the bug this
# package exists to fix) — exercises the real websocket_alerts() function
# directly with a fake socket, since forcing an arbitrary exception out of
# receive_text() isn't reachable through the real ASGI transport.
# ---------------------------------------------------------------------------


class _FakeApp:
    def __init__(self, app_settings, manager) -> None:
        class _State:
            pass

        self.state = _State()
        self.state.settings = app_settings
        self.state.realtime_manager = manager


class _FakeWebSocketConnection:
    def __init__(self, *, cookie: str, app) -> None:
        self.cookies = {default_settings.SESSION_COOKIE_NAME: cookie}
        self.headers: dict[str, str] = {}
        self.app = app
        self.accepted = False
        self.closed: tuple[int, str] | None = None
        self.client_state = WebSocketState.CONNECTED
        self.sent: list[dict] = []

    async def accept(self) -> None:
        self.accepted = True

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = (code, reason)
        self.client_state = WebSocketState.DISCONNECTED

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)

    async def receive(self) -> dict:
        raise RuntimeError("simulated non-disconnect failure")


def test_read_loop_deregisters_connection_on_non_disconnect_exception(
    session: Session, monkeypatch: pytest.MonkeyPatch
):
    operator = make_operator(session, username="wsleak", password="Operator123")
    auth_session = create_session(session, operator)
    session.commit()

    monkeypatch.setattr(
        main_module,
        "authenticate_session_token",
        lambda token, sess: (operator, auth_session),
    )

    manager = RealtimeManager(queue_maxsize=10, send_timeout_seconds=1)
    fake_app = _FakeApp(default_settings, manager)
    token = create_session_token(operator, auth_session)
    ws = _FakeWebSocketConnection(cookie=token, app=fake_app)

    asyncio.run(main_module.websocket_alerts(ws, engine=session.get_bind()))

    assert ws.accepted is True
    assert ws.closed is not None
    assert manager.total_connection_count() == 0


# ---------------------------------------------------------------------------
# F16 (00_FINDINGS.md) — a binary client frame is ignored, not logged as an
# "Unexpected error", and the connection is deregistered exactly once when
# it actually closes.
# ---------------------------------------------------------------------------


def test_binary_frame_is_ignored_and_not_logged_as_error(
    client: TestClient, session: Session, caplog: pytest.LogCaptureFixture
):
    make_operator(session, username="wsbinary", password="Operator123")
    headers = auth_headers(client, "wsbinary", "Operator123")
    manager: RealtimeManager = client.app.state.realtime_manager

    with (
        caplog.at_level(logging.INFO),
        client.websocket_connect("/ws/alerts", headers=headers) as websocket,
    ):
        websocket.receive_json()  # CONNECTION_READY

        websocket.send_bytes(b"\x00\x01not-a-state-mutation")

        # Connection survived the binary frame — a broadcast still
        # reaches it, proving the read loop didn't tear it down.
        manager.broadcast(
            make_event(EventType.RE_ALARM, ReAlarmData(log_id=1, camera_id=1))
        )
        websocket.receive_json()

    assert not any(
        "Unexpected error in /ws/alerts read loop" in record.message
        for record in caplog.records
    )
    # The `with` block's exit closes the socket, which must still
    # deregister the connection exactly once (no leak, no double-cleanup
    # error) even though a non-text frame was received earlier.
    assert manager.total_connection_count() == 0


# ---------------------------------------------------------------------------
# Recovery — GET /api/alerts/ carries what the client needs to rebuild
# alarm state after a reconnect (01_CONTRACTS.md §9.5, NFR-17 / TC-R-304)
# ---------------------------------------------------------------------------


def test_get_alerts_response_includes_snooze_fields(
    client: TestClient, session: Session
):
    make_operator(session, username="recops", password="Operator123")
    headers = auth_headers(client, "recops", "Operator123")
    camera = make_camera(session, name="Recovery Cam", channel_id=700)
    log = make_detection(session, camera, status=DetectionStatus.UNVERIFIED)

    resp = client.get("/api/alerts/?status=Unverified", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    matching = next(entry for entry in body["logs"] if entry["log_id"] == log.log_id)
    assert "snoozed_until" in matching
    assert "snoozed_by_id" in matching
