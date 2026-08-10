# P3 — Real-Time Delivery and Recovery

> **Blocked by:** P2 (needs `auth_session` and the revocation service).
> **Branch:** `feat/be-p3-realtime`
> **Prerequisite reading:** [`01_CONTRACTS.md`](01_CONTRACTS.md) §9, `be_decisions_review.md` D-008.
> **Size:** M. Seven steps.

## Why this package exists

`backend/app/ws_manager.py` is 50 lines: a plain `list` of sockets and a sequential
`for connection in self.active_connections: await connection.send_json(...)` loop. Three consequences:

- **`manager.connect()` calls `websocket.accept()` unconditionally.** There is no authentication at
  all. Anyone who can reach port 8000 receives every accident alert, camera id, snapshot path, and
  confidence score. `backend/README.md:189` even documents this as intentional. It is the single
  largest security gap in the backend.
- One slow or frozen workstation blocks delivery to every client behind it in the list — directly
  contradicting NFR-04's two-second alert requirement.
- Any exception other than `WebSocketDisconnect` escapes the read loop without calling `disconnect()`,
  leaking the entry until a later broadcast happens to prune it.

Payloads are also hand-built dicts in three different files with no schema and no version field.

---

## Step 1 — Envelope and typed payloads

**File:** new `backend/app/schemas/events.py`

Implement the envelope from `01_CONTRACTS.md` §9.1 and a typed payload model for each of the six
events. One `Event[T]` generic wrapper plus six `data` models:

```python
class EventEnvelope(BaseModel):
    version: int = 1
    event_id: str            # uuid4, for client-side duplicate suppression
    type: EventType
    occurred_at: datetime    # UTC
    data: dict
```

Build envelopes only through a factory (`make_event(type, data)`) so `event_id` and `occurred_at` can
never be forgotten. The six types are `CONNECTION_READY`, `NEW_DETECTION`, `ALERT_STATUS_UPDATE`,
`CAMERA_STATUS_UPDATE`, `SNOOZE_ACTIVATED`, `RE_ALARM`.

Because these models are not attached to a route, FastAPI will not put them in the OpenAPI schema.
Register them under `app.openapi()["components"]["schemas"]` (or expose a documentation-only
`GET /api/events/schema` route) so the frontend has a real contract to generate against — D-008
requires "explicit response models and OpenAPI-adjacent documentation rather than arbitrary
dictionaries".

---

## Step 2 — Connection registry

**File:** rewrite `backend/app/ws_manager.py` → `backend/app/services/realtime.py`

```python
@dataclass
class Connection:
    connection_id: str
    user_id: int
    session_id: str
    role: UserRole
    socket: WebSocket
    queue: asyncio.Queue          # maxsize = WS_QUEUE_MAXSIZE
    sender_task: asyncio.Task
```

The manager keeps three indexes so revocation is O(1): by `connection_id`, by `user_id`, and by
`session_id`. Public surface:

```python
async def connect(...) -> Connection
async def disconnect(connection_id, code, reason) -> None
def broadcast(event: EventEnvelope, *, roles: set[UserRole] | None = None) -> None
async def close_session(session_id, reason) -> None      # logout / revocation
async def close_user(user_id, reason) -> None
```

`broadcast` is **synchronous** and non-blocking: it puts the event into each eligible queue and
returns. It never awaits a network send. Enforce that in review — an `await` here reintroduces the
head-of-line blocking this package exists to remove.

Keep the manager on `app.state`, not as a module global, so tests get a clean instance per app.

---

## Step 3 — Per-connection sender task

Each accepted connection owns one task draining its own bounded queue:

```python
async def _sender(conn: Connection) -> None:
    while True:
        event = await conn.queue.get()
        try:
            async with asyncio.timeout(settings.WS_SEND_TIMEOUT_SECONDS):
                await conn.socket.send_json(event)
        except (TimeoutError, WebSocketDisconnect, RuntimeError):
            await manager.disconnect(conn.connection_id, code=1011, reason="send failure")
            return
```

Queue-full policy: when `queue.put_nowait` raises `QueueFull`, **close that connection** with a
documented policy close code and let the client reconnect and re-sync via REST. Do not drop events
silently, and do not block the broadcaster.

Close codes to use consistently:

| Code | Meaning |
|---|---|
| `4001` | authentication failed / no valid session |
| `4003` | origin rejected |
| `4008` | connection limit exceeded |
| `4009` | session revoked or expired |
| `1011` | send failure or queue overflow |

---

## Step 4 — Authenticated handshake

**File:** `backend/app/main.py` (the `/ws/alerts` route)

Before `accept()`:

1. Validate the handshake `Origin` against `CORS_ORIGINS` → close `4003`.
2. Read the session cookie from `websocket.cookies`. The browser sends it automatically on the
   handshake — this is why D-006 chose a cookie: **a browser cannot set an `Authorization` header on a
   WebSocket**, and D-006 explicitly rejects a token in the query string.
3. Run the same four-step validation as `get_current_user` (JWT → `auth_session` → `User.is_active` →
   role). Failure → close `4001`.
4. Enforce `WS_MAX_CONNECTIONS_PER_USER` and `WS_MAX_CONNECTIONS_TOTAL` → close `4008`. Reject the
   *new* connection; never displace an established operational dashboard.
5. `accept()`, register, start the sender task, send `CONNECTION_READY`.

Then the read loop. Inbound messages are still discarded — clients never mutate state over the socket
(D-008) — but the loop must catch **every** exception and always call `disconnect()` in a `finally`,
which the current implementation does not.

---

## Step 5 — Liveness and revocation

- Protocol-level ping/pong is satisfied at the ASGI-server layer, not the application layer —
  **verified, not built** (`be_audit/A4_realtime_hardening.md` F6, 2026-08-10). `websockets 16.0`
  is installed and `wsproto` is not, so uvicorn's `ws="auto"` resolves to its `websockets`
  implementation, whose `Config` defaults `ws_ping_interval=20.0` / `ws_ping_timeout=20.0`
  (`uvicorn/config.py`). RFC 6455 keepalive is active and reaps a half-open socket in roughly
  20–40s; a redundant app-level ping was **not** added on top of it. Confirmed live for both
  launch paths that matter:
  - `uv run fastapi dev backend/app/main.py` (dev) and `fastapi run` (what
    `scripts/adas-maintenance.ps1 -Action Start/Restart` invokes) — the FastAPI CLI does not
    expose `--ws-ping-interval`/`--ws-ping-timeout` at all (checked against
    `fastapi_cli/cli.py`'s `_run()`, which calls `uvicorn.run()` without those kwargs), so both
    always inherit the uvicorn library default. Started `fastapi dev` live this session and
    confirmed `websockets 16.0` importable, `wsproto` not, in the same venv it runs from.
  - `uv run uvicorn app.main:app --app-dir backend ...` (the direct-uvicorn TLS demo command,
    `be_audit/A1_lan_tls_drill.md` step 2) — this is the one launch path that **can** pin the
    setting explicitly, so it now does: `--ws-ping-interval 20 --ws-ping-timeout 20`. Started live
    this session with those flags; server came up clean on `/healthz/live`.
- Add a scheduler job (`ws_session_revalidation`, every 60s) that re-checks each connection's
  `auth_session` and closes with `4009` any whose session expired, was revoked, or whose user went
  inactive.
- Complete **TC-I-404**: `POST /api/auth/logout` and every `revoke_all_for_user` call site now invoke
  `close_session` / `close_user`. Do this **after** the transaction commits, in the route, not inside
  the service — closing a socket for a rollback that never happened is worse than a late close.

---

## Step 6 — Migrate existing broadcast call sites

Three files currently build event dicts by hand: `routes/internal.py` (×2 event types),
`routes/alerts.py` (×3 call sites). Convert every one to `make_event(...)` + `manager.broadcast(...)`.

While migrating, fix the enum inconsistency that forced the defensive
`getattr(log.detection_status, "value", log.detection_status)` scattered through the broadcasts:
`routes/internal.py` assigns `.value` while `routes/alerts.py` assigns the enum member. Pick the enum
member everywhere and delete the `getattr` calls. It works today only by accident of `StrEnum`.

**Enqueue only after commit.** Every existing call site already sits after its commit — keep it that
way, and add a comment saying why, because it is the kind of thing a later refactor silently breaks.

---

## Step 7 — Recovery support

The recovery sequence in `01_CONTRACTS.md` §9.5 is mostly the frontend's job, but the backend must
make it possible:

- `GET /api/alerts/?status=Unverified&status=Ongoing` must return everything the dashboard needs to
  rebuild alarm state, **including `snoozed_until` and `snoozed_by_id`** (the columns exist from P1;
  P4 populates them). This is NFR-17 / TC-R-304.
- `GET /api/cameras/` returns `config_version` and both desired and observed state so the client can
  discard a stale snapshot.
- `CONNECTION_READY` carries `server_time` so the client can measure clock skew before comparing
  `occurred_at` values.

Document in the route docstrings that `updated_at` (incidents) and `config_version` (cameras) are the
merge keys.

---

## Verification

```bash
uv run pytest backend/tests/test_websocket.py
```

The existing `test_websocket.py` will fail — it connects with no credentials. Update it to log in
first and reuse the cookie jar (`TestClient` carries cookies between `post` and `websocket_connect`
automatically). **Keep every existing assertion about payload content and ordering**; only the
handshake changes.

Manually:

1. `websocat ws://localhost:8000/ws/alerts` with no cookie → closed with `4001`. This is the headline
   fix; confirm it before anything else.
2. Log in in a browser, open the dashboard, trigger a detection through the AI engine → the alert
   arrives.
3. Log out in one tab → the socket closes immediately with `4009` (TC-I-404).
4. **Slow-client isolation:** connect two clients, make one stop reading (a paused debugger or a
   client that never drains), broadcast `WS_QUEUE_MAXSIZE + 1` events. The slow client is closed; the
   healthy client receives everything within two seconds. This is the D-008 acceptance criterion and
   the reason the package exists.
5. `pnpm check`.

---

## Tests to write

| Area | Assertions |
|---|---|
| Handshake | no cookie → 4001; expired session → 4001; revoked session → 4001; foreign `Origin` → 4003; inactive user → 4001 |
| Limits | `WS_MAX_CONNECTIONS_PER_USER + 1` → 4008, and the established connections stay open |
| Envelope | every broadcast carries `version`, a unique `event_id`, correct `type`, tz-aware UTC `occurred_at` |
| Isolation | a full queue closes only that connection; other connections still receive the event |
| Ordering | FIFO within one connection |
| Revocation | logout closes that session's sockets and leaves the same user's other sessions open |
| Scheduler | the revalidation job closes a connection whose session was revoked out of band |
| Leak | a non-`WebSocketDisconnect` exception in the read loop still deregisters the connection |
| Recovery | `GET /api/alerts/?status=Unverified` returns snooze fields |

## Paper test cases covered

TC-I-301 (collision logged then instantly pushed), TC-I-404 (logout closes WebSockets),
TC-R-201 (sub-two-second alert latency — measured properly in P9, but the slow-client isolation test
here is the mechanism that makes it hold), TC-S-401 (three simultaneous detections queue and stack
without dropping alerts), TC-U-205 (payload schema — the envelope's `data` is a superset of the six
required fields).

## Deliberately not in this package

Incident lifecycle changes, snooze, the heartbeat endpoint, camera desired-state fields. P3 only
changes *how* events are delivered; P4 changes *what* is emitted.
