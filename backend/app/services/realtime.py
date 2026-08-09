"""04_PKG_realtime.md Steps 2-3 — replaces `app.ws_manager.ConnectionManager`.

The old manager awaited a network send inside a `for` loop over every
connection, so one frozen workstation delayed delivery to every other
operator (directly contradicting NFR-04's two-second alert requirement) and
`connect()` never authenticated anyone. This module fixes both: each
connection gets its own bounded queue and sender task, and `broadcast()`
never awaits a socket — it only ever puts an event onto a queue.

Kept on `app.state.realtime_manager`, not a module global, so tests get a
clean instance per app (see backend/tests/conftest.py's `client` fixture).
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.models import UserRole
from app.schemas.events import EventEnvelope

logger = logging.getLogger("uvicorn.error")


class CloseCode:
    """04_PKG_realtime.md Step 3 — the only close codes this backend assigns
    application-specific meaning to. Kept as plain int constants (not an
    IntEnum) since `WebSocket.close(code=...)` wants a bare int."""

    AUTH_FAILED = 4001
    ORIGIN_REJECTED = 4003
    CONNECTION_LIMIT = 4008
    SESSION_REVOKED = 4009
    SEND_FAILURE = 1011


@dataclass
class Connection:
    connection_id: str
    user_id: int
    session_id: str
    role: UserRole
    socket: WebSocket
    queue: "asyncio.Queue[dict]" = field(repr=False)
    sender_task: "asyncio.Task | None" = field(default=None, repr=False)


class RealtimeManager:
    """Three indexes — by connection, by user, by session — so revocation
    (logout, password change, role change, deactivation) is O(number of that
    user's/session's connections), never a scan of every connection."""

    def __init__(self, *, queue_maxsize: int, send_timeout_seconds: float) -> None:
        self._queue_maxsize = queue_maxsize
        self._send_timeout_seconds = send_timeout_seconds
        self._by_connection: dict[str, Connection] = {}
        self._by_user: dict[int, set[str]] = {}
        self._by_session: dict[str, set[str]] = {}

    def connection_count_for_user(self, user_id: int) -> int:
        return len(self._by_user.get(user_id, ()))

    def total_connection_count(self) -> int:
        return len(self._by_connection)

    def snapshot_connections(self) -> list[Connection]:
        """A stable copy for callers (the revalidation job) that iterate and
        may concurrently trigger disconnects, which mutate the live dicts."""
        return list(self._by_connection.values())

    async def connect(
        self,
        websocket: WebSocket,
        *,
        user_id: int,
        session_id: str,
        role: UserRole,
    ) -> Connection:
        """Registers a connection that has already been `accept()`-ed and
        starts its dedicated sender task. Connection-limit enforcement
        happens in the caller (the handshake), before `accept()`."""
        conn = Connection(
            connection_id=str(uuid.uuid4()),
            user_id=user_id,
            session_id=session_id,
            role=role,
            socket=websocket,
            queue=asyncio.Queue(maxsize=self._queue_maxsize),
        )
        self._by_connection[conn.connection_id] = conn
        self._by_user.setdefault(user_id, set()).add(conn.connection_id)
        self._by_session.setdefault(session_id, set()).add(conn.connection_id)
        conn.sender_task = asyncio.create_task(self._sender(conn))
        return conn

    async def disconnect(self, connection_id: str, *, code: int, reason: str) -> None:
        """Idempotent — deregistering an already-gone connection is a no-op,
        since a send-failure and the read loop's `finally` can both race to
        clean up the same connection."""
        conn = self._by_connection.pop(connection_id, None)
        if conn is None:
            return

        user_conns = self._by_user.get(conn.user_id)
        if user_conns is not None:
            user_conns.discard(connection_id)
            if not user_conns:
                del self._by_user[conn.user_id]

        session_conns = self._by_session.get(conn.session_id)
        if session_conns is not None:
            session_conns.discard(connection_id)
            if not session_conns:
                del self._by_session[conn.session_id]

        current_task = asyncio.current_task()
        if conn.sender_task is not None and conn.sender_task is not current_task:
            conn.sender_task.cancel()

        try:
            if conn.socket.client_state != WebSocketState.DISCONNECTED:
                await conn.socket.close(code=code, reason=reason)
        except Exception:
            logger.debug(
                "close() failed for connection %s (already gone); ignoring.",
                connection_id,
            )

    def broadcast(
        self, event: EventEnvelope, *, roles: set[UserRole] | None = None
    ) -> None:
        """D-008's headline requirement: synchronous and non-blocking. Puts
        the event onto every eligible connection's queue and returns —
        it never awaits a network send. A full queue closes only that
        connection (via a fire-and-forget disconnect task); the event is
        never silently dropped and the broadcaster never blocks."""
        payload = event.model_dump(mode="json")
        for conn in list(self._by_connection.values()):
            if roles is not None and conn.role not in roles:
                continue
            try:
                conn.queue.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning(
                    "WS queue full for connection %s (user_id=%s); closing "
                    "that connection only.",
                    conn.connection_id,
                    conn.user_id,
                )
                asyncio.create_task(
                    self.disconnect(
                        conn.connection_id,
                        code=CloseCode.SEND_FAILURE,
                        reason="queue overflow",
                    )
                )

    async def close_session(self, session_id: str, *, reason: str) -> None:
        """Logout — closes only this session's sockets, leaving the same
        user's other sessions (and their sockets) open."""
        for connection_id in list(self._by_session.get(session_id, ())):
            await self.disconnect(
                connection_id, code=CloseCode.SESSION_REVOKED, reason=reason
            )

    async def close_user(self, user_id: int, *, reason: str) -> None:
        """Password change, role change, deactivation — every session for
        this user was just revoked, so every one of their sockets closes."""
        for connection_id in list(self._by_user.get(user_id, ())):
            await self.disconnect(
                connection_id, code=CloseCode.SESSION_REVOKED, reason=reason
            )

    async def _sender(self, conn: Connection) -> None:
        """One task per connection, draining only that connection's queue.
        A slow or dead socket blocks this task alone — never the broadcaster
        and never another connection's sender."""
        while True:
            event = await conn.queue.get()
            try:
                async with asyncio.timeout(self._send_timeout_seconds):
                    await conn.socket.send_json(event)
            except Exception:
                logger.info(
                    "Send failure on connection %s (user_id=%s); closing.",
                    conn.connection_id,
                    conn.user_id,
                )
                await self.disconnect(
                    conn.connection_id,
                    code=CloseCode.SEND_FAILURE,
                    reason="send failure",
                )
                return
