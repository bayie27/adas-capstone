# Package B — Dev API & In-Process Reseed

> **Blocked by:** Package A. It must be **committed** before this session starts — this package
> imports `app.dev.profiles.PROFILES` and `app.dev.seed.seed_profile()`.
> **Branch:** `feat/dev-seeding-and-tools` (already exists; continue on it).
> **Prerequisite reading:** [`00_OVERVIEW.md`](00_OVERVIEW.md) · [`01_PKG_seed_core.md`](01_PKG_seed_core.md)
> · `CLAUDE.md` (the audit-transaction and services-layer rules) · `be_plan/01_CONTRACTS.md` §§6–7
> **Size:** L. Six steps.
> **Scope:** `backend/` only. No frontend, no `ai_engine/`.

## Why this package exists

`backend/scripts/reset_db.py` deletes the SQLite file and its `-wal`/`-shm` sidecars. It cannot run
while the backend is up — on Windows the `unlink` raises `PermissionError` and the script exits with
"Stop the backend server ... then try again". So today every profile switch is: stop the server,
reseed, restart, log in again.

A dev panel button needs the opposite: wipe and reseed **in-process**, schema intact, server up,
WebSocket connections alive, and the operator still logged in on the same page.

Second gap: nothing in the repo can produce a live incident over HTTP against a running backend.
`backend/tests/perf/test_alert_latency.py` gets closest with an in-process `TestClient` POST, but
it's test-only. Everything else either writes `detection_log` rows directly (no broadcast, no
self-blindfold pause) or needs MediaMTX + ffmpeg + sample clips + an NVIDIA GPU.

---

## Scope

### In

| #   | Change                                                                                   |
| --- | ---------------------------------------------------------------------------------------- |
| 1   | `DEV_TOOLS_ENABLED` setting and conditional router registration                          |
| 2   | Extract the detection-ingest body out of `routes/internal.py` into a service             |
| 3   | `app/dev/wipe.py` — in-process wipe with audit-trigger restoration                       |
| 4   | `app/dev/service.py` — reseed orchestration, scheduler pause, threadpool, WAL checkpoint |
| 5   | `app/api/routes/dev.py` — six endpoints                                                  |
| 6   | Session minting so the caller stays logged in through a wipe                             |

### Out

- **Anything in `frontend/`.** That is Package C.
- **Any Alembic migration.** Nothing here changes the schema.
- **Audit rows for dev actions.** See §4.
- **A new `EventType`.** Reuse `MAINTENANCE_NOTICE`.

---

## Step 1 — Gating

`backend/app/core/config.py`:

```python
DEV_TOOLS_ENABLED: bool | None = None
```

Resolve with a `model_validator(mode="after")`: when `None`, becomes `ENVIRONMENT == "development"`.
An explicit `.env` value always wins, and production defaults to off. Do not add a separate `DEBUG`
field — there isn't one today and this doesn't need one.

`.env.example` gains a `# Dev tools` block, commented out, noting that setting it `true` is what
enables the panel on the LAN demo box. Note that CI does `cp .env.example .env`, so leaving it
commented keeps CI on the development-derived default.

`backend/app/main.py` `create_app()` — register `routes/dev.py` only when the resolved flag is true,
alongside the existing router block. When off, the routes do not exist at all: `GET /api/dev/status`
404s and Package C's button never appears. `backend/tests/test_app_factory.py` is where to assert
both shapes.

### Auth model — read before writing the routes

Because DT-3 lets this flag be on outside development, these routes must not become an auth bypass.

| Route                    | Gate                         | Why                                                                                                                                                                                             |
| ------------------------ | ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /api/dev/status`    | none                         | Returns `{enabled, profiles}` only. No usernames, no camera list, nothing an unauthenticated caller can act on. Package C needs it before login to decide whether to render the button.         |
| `POST /api/dev/login-as` | any authenticated user       | An account **switcher**, not a way in. You log in normally once; after that you can hop between seeded accounts. Unauthenticated, this would be a complete auth bypass whenever the flag is on. |
| everything else          | `Depends(get_current_admin)` | Destructive or state-mutating.                                                                                                                                                                  |

`POST /api/dev/reseed` is the only endpoint that mints a cookie, and only because it just destroyed
the session it authenticated with.

`get_current_admin` is `require_admin(None)` in `app/api/dependencies.py` — the variant that does
**not** write a denied audit row, which is correct here since none of the 26 `AUDIT_ACTIONS` covers
a dev action.

## Step 2 — Extract the ingest service

`POST /api/internal/alert`'s logic is written inline in `backend/app/api/routes/internal.py`:
camera lookup and `is_active`/`is_enabled` checks, the `source_event_id` idempotency short-circuit
(200 on replay, 201 on new), the `IntegrityError` → 409 `CONFLICT_STATE` backstop for
`ux_detection_open_camera`, the commit, `apply_desired_state(camera, has_open_incident=True)`
self-blindfold, and the `NEW_DETECTION` + `CAMERA_STATUS_UPDATE` broadcasts.

That violates CLAUDE.md's services-layer rule, and the dev injector must run **exactly** that path —
a reimplementation would demo a code path that doesn't exist in production.

Extract it into `backend/app/services/incidents.py` (which already holds `transition` and
`dismiss_transition`) as something like:

```python
def ingest_detection(
    session: Session,
    payload: DetectionLogCreateV2,
) -> tuple[DetectionLog, Camera, bool]   # (log, camera, created)
```

`routes/internal.py` becomes a thin caller that maps the result to 200/201 and does the broadcasts.
Keep the broadcast in the route, not the service — CLAUDE.md forbids a WebSocket send inside an
open transaction, and the current ordering (commit, then `apply_desired_state`, then broadcast) is
load-bearing for the self-blindfold pattern.

**This is behaviour-preserving refactoring of a recently audited seam** (`be_audit/A3_ai_seam.md`,
the F20 fix in `e7c80ef`). Do not change ordering, status codes, error codes, or the clock-skew and
engine-identity tripwires. Verify with the existing suites before moving on:

```bash
uv run pytest backend/tests/test_internal.py backend/tests/test_realtime.py backend/tests/test_websocket.py
```

If the extraction turns out to require an ordering change, **stop and report** rather than
adjusting the seam.

## Step 3 — The wipe

`backend/app/dev/wipe.py`:

```python
def wipe_operational_data(engine: Engine, *, snapshot_root: Path) -> dict[str, int]
```

Returns per-table deleted counts.

### Delete order

`PRAGMA foreign_keys=ON` is live (set per-connection in `app/core/db.py`), so order matters:

`detection_log` → `audit_log` → `auth_session` → `alarm_settings` → `export_job` →
`sys_health_raw` → `sys_health_hourly` → `camera` → `user`

Note `audit_log.user_id` is `ondelete="RESTRICT"`, so it genuinely has to go before `user`.

**Preserved**: `help_article` and `help_article_fts` — owned by `init_db()` → `seed_help_articles()`
and content-hash idempotent; FTS5 external-content sync is not worth re-deriving for a dev reset.
And `alembic_version`, obviously. **The schema is never touched** — no file delete, no
`SQLModel.metadata.create_all()`.

### The audit triggers — the part most likely to be got wrong

`audit_log` carries `trg_audit_log_no_update` and `trg_audit_log_no_delete`, attached in
`backend/app/models/audit.py` as raw `DDL` objects via `event.listen(AuditLog.__table__,
"after_create", ...)`. They make `DELETE FROM audit_log` raise `audit_log is append-only`.

In `backend/app/models/audit.py`, promote the two private `DDL` objects to a public tuple and have
the existing listener registrations iterate it:

```python
AUDIT_IMMUTABILITY_TRIGGERS = (_NO_UPDATE_TRIGGER, _NO_DELETE_TRIGGER)

for _trigger in AUDIT_IMMUTABILITY_TRIGGERS:
    event.listen(AuditLog.__table__, "after_create", _trigger)
```

The wipe then does `DROP TRIGGER IF EXISTS` for both names, deletes, and **re-executes the same
`DDL` objects**. Do not re-type the trigger SQL — that creates a second source of truth for an
append-only guarantee NFR-21 depends on.

Wrap it so a failure cannot leave the table mutable:

```python
try:
    drop triggers
    delete rows
finally:
    recreate triggers
```

### Snapshot files

Before deleting `detection_log`, read its `snapshot_key` values and unlink the corresponding files
under `snapshot_root`, then prune the empty `YYYY/MM/DD/camera_{id}/` directories. Otherwise the
`empty` profile isn't empty — the images stay on disk. Route every path through
`services.snapshots.resolve()` so a hostile or malformed key can't make the wipe delete outside the
configured roots; skip anything that doesn't resolve.

## Step 4 — Reseed orchestration

`backend/app/dev/service.py`:

```python
async def reseed(
    engine: Engine,
    *,
    profile: str,
    scheduler: AsyncIOScheduler | None,
    snapshot_root: Path,
) -> SeedResult
```

### Concurrency

APScheduler is running `sweep_expired_cooldowns` every 30 s, the health sampler, and the export
workers (`backend/app/main.py` lifespan). A full wipe while those run risks `database is locked` and
jobs operating on rows that vanish mid-flight. The service must:

1. take a **module-level `asyncio.Lock`** so two reseeds can't overlap;
2. `scheduler.pause()` on entry and `resume()` in a `finally` — `get_scheduler` returns `None` when
   `SCHEDULER_ENABLED=false` (the test suite), so guard for that;
3. run the sync wipe+seed under `run_in_threadpool` (`app.dev.seed` is synchronous, and blocking the
   event loop for the duration would stall the WebSocket heartbeats);
4. issue `PRAGMA wal_checkpoint(TRUNCATE)` at the end so the `-wal` file doesn't keep the old pages.

`SQLITE_BUSY_TIMEOUT_MS` is 5000 and covers the rest. `perf` takes roughly 33 s — the route must not
have a shorter timeout than that, and Package C labels it slow and requires a confirm.

### No audit rows for dev actions

The reseed wipes `audit_log` anyway, and the audit-aware transaction helpers in
`app/services/audit.py` exist to protect real state changes, none of which these are. **This is the
one deliberate exception** to CLAUDE.md's "every audited state change is one transaction" rule —
state it in the module docstring so a future reviewer doesn't read it as an oversight.

### Post-reseed broadcast

Reuse the existing `MAINTENANCE_NOTICE` `EventType` (`app/schemas/events.py`) to tell other
connected clients their view is stale. No new event type, no schema change for existing WS
consumers, and `GET /api/events/schema` stays accurate.

## Step 5 — Routes

`backend/app/api/routes/dev.py`, prefix `/api/dev`, tag `Dev Tools`.

| Route                             | Auth     | Behaviour                                                                                                                                                                                                                                                                                                                                                                     |
| --------------------------------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /status`                     | none     | `{enabled: true, profiles: [{name, description}]}` from `PROFILES`                                                                                                                                                                                                                                                                                                            |
| `POST /reseed`                    | admin    | `{profile, login_as?}` → wipe, seed, mint a session for `login_as` (default: the caller's own username, falling back to `admin`), `set_session_cookie(response, token)`, broadcast `MAINTENANCE_NOTICE`. Returns the `SeedResult` counts plus `{username, role, user_id}`                                                                                                     |
| `POST /login-as`                  | any user | `{username}` → `revoke_session(current sid, reason="admin_revoke")`, `create_session`, `create_session_token`, `set_session_cookie`. 404 if the username isn't a seeded active user                                                                                                                                                                                           |
| `POST /detections`                | admin    | `{camera_id?, confidence?, detected_at?}` → build a `DetectionLogCreateV2` and call `ingest_detection()` from Step 2, then the same broadcasts `routes/internal.py` does. Writes a placeholder snapshot via `app.dev.assets.write_snapshot`. Omit `camera_id` to pick a random enabled camera with no open incident; 409 with a clear message if every camera already has one |
| `POST /cameras/{camera_id}/state` | admin    | `{connection_status?, ai_status?, stale_heartbeat?, clear_cooldown?}` → `services.cameras.apply_observed()`. `stale_heartbeat: true` backdates `last_heartbeat_at` past `HEARTBEAT_STALE_SECONDS` so `presented_statuses()` reports `Unresponsive`                                                                                                                            |
| `POST /health-history`            | admin    | `{days}` → the health generator from Package A Step 5                                                                                                                                                                                                                                                                                                                         |

### Session minting

Do exactly what `backend/app/api/routes/auth.py:107-132` does — `create_session()` from
`app/services/sessions.py`, then `create_session_token()` and `set_session_cookie()` from
`app/core/security.py`. **Write no new cookie logic**, so `SESSION_COOKIE_NAME`, `HttpOnly`,
`SameSite` and `SESSION_COOKIE_SECURE` stay identical to a real login. A hand-rolled `Set-Cookie`
here would silently diverge on the LAN TLS demo, where `SESSION_COOKIE_SECURE=true` matters.

`create_session` takes `user_agent` and `source_ip` — pass them through from the `Request` the same
way the login route does.

## Step 6 — Schemas

Request/response models go in `backend/app/schemas/dev.py`, following the house pattern. Use
`model_config = {"extra": "forbid"}` on the request bodies, as `DetectionLogCreateV2` does.

---

## Verification

```bash
uv run pytest backend/tests/test_dev_tools.py
```

New file. Assert:

1. **Gating** — with `DEV_TOOLS_ENABLED=false` the router is absent (404 on `/api/dev/status`);
   with it true, present. Build the isolated `Settings` the way `backend/tests/conftest.py` already
   does, and remember session validation reads the **process-global**
   `app.core.config.settings` singleton — patch that global, don't just pass an instance around
   (see `internal_headers()` in `conftest.py` and the note in `backend/tests/perf/conftest.py`).
2. **Auth** — non-admin gets 403 on `reseed`; unauthenticated gets 401 on `login-as`;
   unauthenticated gets 200 on `status`.
3. **Reseed round-trip** — wipes, reseeds, returns a `Set-Cookie`, and a follow-up request carrying
   that cookie authenticates as the requested user.
4. **The audit triggers survive** — after a wipe, `UPDATE` and `DELETE` against `audit_log` still
   raise. This is the regression that matters most; assert it explicitly.
5. **`empty` really is empty** — zero cameras, zero detections, zero snapshot files on disk, but
   `help_article` rows intact.
6. **Injection runs the real path** — `POST /api/dev/detections` creates an open incident, flips the
   camera to `Paused` via the self-blindfold, and broadcasts `NEW_DETECTION` +
   `CAMERA_STATUS_UPDATE`. Reuse the broadcast-capture helpers in `backend/tests/test_realtime.py`.
7. **Second injection on the same camera 409s** — `ux_detection_open_camera` still holds.
8. **Reseed is serialized** — two concurrent reseeds don't interleave (the `asyncio.Lock`).
9. **The scheduler is resumed** even when the seed raises.

Plus the Step 2 regression check:

```bash
uv run pytest backend/tests/test_internal.py backend/tests/test_realtime.py backend/tests/test_websocket.py
```

This package touches `app/core/config.py`, `app/models/audit.py`, `app/main.py` and
`app/services/incidents.py` — genuinely cross-cutting. Run the full suite before the PR:

```bash
uv run pytest -n auto
```

### Manual smoke

With the backend running (`uv run fastapi dev backend/app/main.py`) and a session cookie in hand:
reseed to `analytics`, confirm the server does **not** restart, the DB file is not recreated, the
old session is dead but the returned cookie works, and `GET /api/alerts/` reflects the new data.

---

## Report back

- Whether the Step 2 extraction was fully behaviour-preserving, and anything you had to leave in
  the route to keep it so.
- The final request/response shapes for all six endpoints — Package C codes against them.
- Whether `perf` is usable over HTTP or too slow to be worth exposing in the panel.

---

## Executed 2026-08-11 — answers

**Step 2 was fully behaviour-preserving.** No ordering change was needed, so there was nothing to
stop and report. `ingest_detection(session, payload) -> (log, camera, created)` carries the camera
checks, the `source_event_id` short-circuit, the `IntegrityError` → source-event recheck →
open-camera 409 backstop, and the commit → `apply_desired_state` → refresh ordering. It raises
`CameraUnavailableForIngest` / `OpenIncidentConflict`, matching the domain-exception pattern
`transition()` already uses. **Left in the route deliberately:** both broadcasts (a WebSocket send
inside an open transaction is forbidden) and the 200/201 status mapping, since only the `created`
path broadcasts — an idempotent replay stays silent, as before.

**`perf` is usable over HTTP.** Measured through `POST /api/dev/reseed` on the demo laptop:

| profile   | wipe + reseed | detections |
| --------- | ------------- | ---------- |
| empty     | 0.17s         | 0          |
| edge      | 1.00s         | 13         |
| demo      | 1.03s         | 18         |
| analytics | 1.65s         | 62         |
| perf      | **15.21s**    | 100,000    |

Faster than the ~33s this doc assumed, because the wipe leaves an empty table to insert into. One
request, no timeout involvement — it runs under `run_in_threadpool`, so the event loop and the
WebSocket heartbeats are unaffected throughout. Package C should still label it slow and require a
second click, but it is worth exposing.

### Endpoint shapes — Package C codes against these

All request bodies are `extra="forbid"`. Models live in `app/schemas/dev.py`.

| Route                              | Auth  | Request                                                                           | Response                                                                                                                                       |
| ---------------------------------- | ----- | --------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /api/dev/status`              | none  | —                                                                                 | `{enabled: bool, profiles: [{name, description}]}`                                                                                             |
| `POST /api/dev/reseed`             | admin | `{profile: str, login_as?: str}`                                                  | `{profile, users, cameras, detections, audit_rows, health_samples, export_jobs, snapshots, session: {user_id, username, role}}` + `Set-Cookie` |
| `POST /api/dev/login-as`           | any   | `{username: str}`                                                                 | `{session: {user_id, username, role}}` + `Set-Cookie`                                                                                          |
| `POST /api/dev/detections`         | admin | `{camera_id?: int, confidence?: float 0-1, detected_at?: datetime}`               | `DetectionLog`, 201                                                                                                                            |
| `POST /api/dev/cameras/{id}/state` | admin | `{connection_status?, ai_status?, stale_heartbeat?: bool, clear_cooldown?: bool}` | `Camera`                                                                                                                                       |
| `POST /api/dev/health-history`     | admin | `{days: int 1-90}`                                                                | `{rows_written: int}`                                                                                                                          |

Error cases worth handling in the panel: unknown profile → **404**; unknown `login_as` on
`/login-as` → **404**; every enabled camera already has an open incident → **409**
`CONFLICT_STATE`; a second injection on the same camera → **409** `CONFLICT_STATE`.
`/health-history` returns `rows_written: 0` against a profile that already seeded history — its
idempotency guard, not a failure.

### Deviations and findings

1. **`init_db()` runs before the wipe**, not only inside `seed_profile()` after it — the wipe
   DELETEs against tables a never-migrated database does not have.
2. **`MaintenanceNoticeData.backup_id` is now optional.** Reusing the event as specified was
   impossible with it required. That event type had no producer and no consumer anywhere, so
   nothing breaks.
3. **The wipe's `finally` needs its own commit.** pysqlite does not open a transaction until the
   first DML statement, so the `DROP TRIGGER`s autocommit while a recreate issued after a failing
   DELETE rolls back with it — leaving `audit_log` mutable. Reproduced and fixed; both the
   happy path and the injected-failure path are asserted in `test_dev_tools.py`.
4. **`seed_profile()` needs `target_settings`** alongside the engine (F18), which is why `reseed()`
   takes and forwards it.
5. **Pre-existing, left alone:** `GET /api/alerts/{log_id}/snapshot` resolves against the
   process-global `settings.SNAPSHOT_ROOT`, not `app.state.settings`. Harmless in production where
   they are the same object; it means an app built with an isolated root cannot serve snapshots it
   just wrote. The test patches the global and explains why.
