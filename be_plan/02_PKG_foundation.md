# P1 — Foundation and Schema

> **Blocked by:** nothing. This is the first package.
> **Branch:** `feat/be-p1-foundation`
> **Prerequisite reading:** [`01_CONTRACTS.md`](01_CONTRACTS.md) in full, `be_decisions_review.md` D-005.
> **Size:** XL. Ten steps, each independently committable.

## Why this package exists

Every later package needs infrastructure the backend does not have: a domain layer callable from
scheduler jobs, UTC-safe timestamps, foreign-key enforcement, a scheduler, and a test harness that
does not corrupt the developer's database. This package builds all of it and lands the **complete
target schema in one shot** — D-005's "one clean initial migration" strategy (P9) only works if the
schema stops moving before Alembic arrives.

**No Alembic in this package.** The dev DB is disposable. Break it and reseed.

---

## Step 1 — Configuration

**File:** `backend/app/core/config.py`

Implement the full settings table from `01_CONTRACTS.md` §4. Rules:

- **Give everything a safe default except `SECRET_KEY`, `INTERNAL_API_KEY`, and
  `DEFAULT_ADMIN_PASSWORD`.** Today all ten settings are required, so the app cannot even be imported
  without a complete `.env` — including four `DSS_*` values that nothing reads.
- `DSS_IP`, `DSS_PORT`, `DSS_USERNAME`, `DSS_PASS` become **optional**, consumed only by
  `RTSP_URL_TEMPLATE`.
- `DEFAULT_ADMIN_PASSWORD` becomes `SecretStr` (it is a plain `str` today, so it can leak into a repr
  or traceback).
- **Keep the existing `resolve_sqlite_path` field validator exactly as it is.** It anchors a relative
  SQLite path to the repo root regardless of CWD. `CLAUDE.md` calls this out; do not reintroduce
  CWD-relative logic.
- Path settings (`SNAPSHOT_ROOT`, `BACKUP_DIR`, `EXPORT_DIR`, `ARCHIVE_DIR`) resolve relative values
  against `REPO_ROOT` the same way, and are created on startup (not at import time).
- `CORS_ORIGINS` is a list parsed from a comma-separated env value.
- Add a validator rejecting `SECRET_KEY` shorter than 32 characters when `ENVIRONMENT == "production"`.

Update `.env.example` to match, keeping its existing style: **no inline `#` comments after values**.

---

## Step 2 — SQLite connection policy and the UTC type

**Files:** `backend/app/core/db.py`, new `backend/app/core/types.py`

### 2a. Connection pragmas (D-005)

Replace the current single `journal_mode=WAL` listener with all four required pragmas:

```python
@event.listens_for(engine, "connect")
def _configure_sqlite(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=FULL")
    cursor.execute(f"PRAGMA busy_timeout={settings.SQLITE_BUSY_TIMEOUT_MS}")
    cursor.close()
```

`foreign_keys=ON` is the important one — SQLite defaults it **off**, so none of the existing foreign
keys on `detection_log` are currently enforced.

Guard the SQLite-specific arguments (`check_same_thread`, the pragmas) behind a dialect check so a
non-SQLite `DATABASE_URL` does not blow up at connect time.

Replace `echo=True` with `echo=settings.SQL_ECHO`.

### 2b. `UtcDateTime` (D-005)

```python
class UtcDateTime(TypeDecorator):
    """Stores tz-aware UTC datetimes; returns tz-aware UTC datetimes.

    SQLite does not preserve tzinfo from DateTime(timezone=True), so normalization
    has to happen in Python on both sides of the boundary.
    """
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime reached the database layer")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        return None if value is None else value.replace(tzinfo=UTC)
```

Raising on a naive datetime is deliberate — it turns a silent data corruption into a loud test
failure. Every datetime column in Step 4 uses this type.

Add a `parse_utc_query_datetime()` helper for query parameters: a value with an offset is converted
to UTC; a naive value is *assumed* UTC. This fixes a live bug — `?start_date=2026-01-01T00:00:00+08:00`
currently has its offset stripped and is compared against UTC-stored values, an eight-hour error.

**Also fix:** the `verify_internal_api_key` dependency in `backend/app/api/dependencies.py` uses
`Header(...)`, so a **missing** `x-api-key` returns `422` instead of `401`. Give it a `None` default
and raise `401 AUTH_REQUIRED` explicitly.

---

## Step 3 — Package split

`backend/app/models.py` is 328 lines holding tables *and* Pydantic schemas. Split it:

```
backend/app/models/          # SQLModel tables only
    __init__.py              # re-exports every table + every enum
    enums.py
    user.py                  # User, AuthSession, AlarmSettings
    camera.py                # Camera
    detection.py             # DetectionLog
    audit.py                 # AuditLog
    health.py                # SysHealthRaw, SysHealthHourly
    export.py                # ExportJob
    help.py                  # HelpArticle
backend/app/schemas/         # Pydantic request/response models only
    __init__.py
    common.py                # ApiError, pagination, shared validators
    auth.py  user.py  camera.py  detection.py  audit.py  health.py  export.py  help.py  events.py
backend/app/services/        # domain logic — NEW
    __init__.py
```

`app/services/` is the point of this step. Today every business rule lives inline in a route handler,
which is why the HITL state machine is unreachable from a scheduler job — and D-004's snooze expiry
and D-002's 60-second cooldown are both scheduler jobs. Services take an explicit `Session` and never
import FastAPI.

While splitting, deduplicate what already exists twice:

- `_format_user_name` is copied verbatim into both `alerts.py` and `analytics.py` → `app/services/formatting.py`.
- `_validate_common_filters` exists in both with **different signatures** (`camera_ids` vs `camera_id`,
  and only one has a user-id branch) → one implementation in `app/services/filters.py`. P6 builds on it.

This step is a pure move-and-rename. **The existing test suite must still pass at the end of it**
(imports change; assertions do not).

---

## Step 4 — The complete target schema

Implement every table in `01_CONTRACTS.md` §3, with explicit `__tablename__` values (`detection_log`,
not SQLModel's default `detectionlog`).

Notes an executing agent will otherwise get wrong:

- **CHECK constraints go in `__table_args__`**, alongside the indexes. Pydantic validation is not
  enough — D-005 requires SQLite itself to enforce roles, statuses, ranges, and positive channel IDs.
- **Partial and expression indexes** (`WHERE is_active = 1`, `lower(camera_name)`) are not expressible
  through SQLModel `Field(index=True)`. Declare them as `sqlalchemy.Index(...)` objects in
  `__table_args__`.
- **`ux_detection_open_camera`** is the D-002 "at most one open incident per camera" rule. It will
  make a second concurrent ingestion for the same camera fail with `IntegrityError` — P4 catches that
  and returns `409`. Do not weaken it.
- **The `audit_log` immutability triggers** cannot be expressed in SQLModel. Create them with a
  `DDL` + `event.listen(AuditLog.__table__, "after_create", …)` hook so they exist under both
  `create_all` (now) and Alembic (P9).
- All FKs are `ON DELETE RESTRICT` except `alarm_settings.user_id`, which is `ON DELETE CASCADE`.
- `SysHealthRaw` / `SysHealthHourly` are **reshaped**, not reused — the current columns
  (`gpu_usage`, `peak_gpu_temp`, no CPU temp, no VRAM) do not match D-009.

`init_db()` keeps seeding the bootstrap admin when the `user` table is empty, and now also creates
that admin's `alarm_settings` row.

---

## Step 5 — Logging, request IDs, and the error envelope

**Files:** new `backend/app/core/logging.py`, `backend/app/main.py`

- Configure structured logging (`logging.config.dictConfig`) at `LOG_LEVEL`. Replace every `print()`
  in `main.py` and `core/db.py`.
- Add a middleware that assigns each request a `request_id` (UUID4), exposes it as `X-Request-ID`,
  and binds it into a `ContextVar` so log records and audit rows can pick it up without threading it
  through every function signature. D-007 requires `audit_log.request_id` to correlate with
  operational logs.
- Add a **redacting log filter** that scrubs anything matching the `01_CONTRACTS.md` §1.6 list —
  most importantly `rtsp://user:pass@host`. Unit-test it with a credential-bearing URL.
- Keep the three existing exception handlers and their `ApiError` envelope. Extend them to emit the
  stable `code` values from §1.3 and to include `request_id` in the 500 log line.
- Add a handler for `sqlalchemy.exc.OperationalError` where the message contains `database is locked`
  → `503 TEMPORARILY_UNAVAILABLE`, logged operationally. D-005 requires a lock timeout to return a
  structured error rather than hang.

---

## Step 6 — App factory and the test-harness fix

**This step fixes a live bug that is corrupting local dev state today.**

`backend/tests/conftest.py` overrides the `get_session` dependency but **not** the module-level
`engine`. So `with TestClient(app)` runs the real lifespan, and `init_db()` plus the camera-reset bulk
UPDATE both execute against the developer's actual repo-root `adas.db`. Only `test_main.py`
monkeypatches around it. In CI this is invisible because `cp .env.example .env` produces a throwaway DB.

Fix it structurally:

1. Convert `backend/app/main.py` to an app factory:

   ```python
   def create_app(settings: Settings | None = None) -> FastAPI: ...
   app = create_app()   # the FastAPI CLI entrypoint still works unchanged
   ```

2. Make the engine a resolvable dependency (`get_engine`) rather than a module global that lifespan
   closes over. Lifespan reads it from `app.state`.
3. Update `conftest.py` to build the app with a test settings object pointing at the in-memory engine,
   and override `get_engine` as well as `get_session`.
4. **Move the two import-time side effects out of module scope**: `os.makedirs(SNAPSHOT_DIR)` and the
   `StaticFiles` mount currently run on `import app.main`. Move directory creation into lifespan. The
   static mount is removed entirely in P4 — for now, gate it behind `ENVIRONMENT == "development"`.

**Acceptance for this step:** delete `adas.db`, run `uv run pytest`, and confirm `adas.db` is **not**
recreated. Then reseed and re-run pytest, and confirm the file's mtime is unchanged.

---

## Step 7 — Scheduler

**File:** new `backend/app/core/scheduler.py`. **Dependency:** `apscheduler>=3.11`.

An `AsyncIOScheduler` started and shut down by lifespan, stored on `app.state`. Every later package
registers jobs on it.

Policy required by D-009, applied to every job:

- `timezone=UTC`
- `max_instances=1`
- `coalesce=True`
- a bounded `misfire_grace_time`
- **its own short-lived `Session`** — never a request session, never a session held across an `await`

Expose a small helper so packages register jobs uniformly and jobs get stable IDs (D-004 needs the
identity `snooze:{log_id}` to be replaceable):

```python
def add_job(func, *, job_id: str, replace_existing: bool = True, **trigger_kwargs): ...
```

Add a `SCHEDULER_ENABLED` setting, defaulted `False` in the test settings — otherwise background jobs
race the test suite.

Register one job now to prove the wiring: `expired_session_cleanup`, hourly, marking
`auth_session` rows past `expires_at` with `revocation_reason='expired_cleanup'`.

---

## Step 8 — Health probes

**File:** `backend/app/api/routes/system.py` (currently 0 bytes)

> `CLAUDE.md` says this file is an intentional placeholder that must not be "fixed". This package is
> the explicit instruction to implement it. Update that `CLAUDE.md` bullet in P9.

**This file holds the probes and nothing else.** P5 adds `routes/system_health.py` and P7 adds
`routes/maintenance.py` as separate modules — that separation is what lets those two packages run in
parallel without conflicting. Do not put anything else here.

```
GET /healthz/live   -> 200 {"status": "ok"}                       process responds, no DB touch
GET /healthz/ready  -> 200 {"status": "ready", "checks": {...}}   DB SELECT 1 + init complete
                    -> 503 TEMPORARILY_UNAVAILABLE on failure
```

Both are unauthenticated and expose **no** telemetry or configuration (D-009). P7 gates the restore
restart on `/healthz/ready`, so it must genuinely verify database access.

Keep `GET /` as-is for backward compatibility.

---

## Step 9 — Lifespan camera reconciliation

The current lifespan resets every enabled+active camera to `Disconnected`/`Inactive`. Extend it for
the desired/observed split:

- **Observed** state resets to `Disconnected` / `Inactive` — correct, because no engine has reported
  since the restart.
- **Desired** state is *recomputed*, not reset:
  - `is_active=False` or `is_enabled=False` → `Inactive`, reason `disabled`
  - an open (`Unverified` or `Ongoing`) incident exists → `Paused`, reason `incident`
  - `cooldown_until` is in the future → `Paused`, reason `cooldown`, and a cooldown job is rescheduled
  - `cooldown_until` is in the past → `Active`, reason and deadline cleared
  - otherwise → `Active`

This is what makes the P4 cooldown durable. Today a restart inside the 60-second dismiss window
strands the camera in `Paused` forever, because the cooldown is an `asyncio.create_task` whose handle
is discarded and nothing reconciles it afterwards.

Also add the snooze reconciliation hook (implemented in P4, stubbed here) so the ordering is
established: reschedule unexpired snoozes, atomically clear expired ones.

---

## Step 10 — Seeds and scripts

**Files:** `backend/scripts/seed_dev_data.py` (806 lines), `reset_db.py`, `reseed_dev.py`

Rewrite the seeder for the new schema. Keep everything that already works well:

- the `SEED_PROFILES` / `--profile` structure and the existing `demo` / `analytics` / `edge` profiles
- idempotent `ensure_user` / `ensure_camera` / `ensure_alert` helpers
- `seeded_timestamp()` guaranteeing no future-dated rows
- the six named cameras and four operators
- the closing histogram

Add:

- `alarm_settings` for every seeded user
- `source_event_id` (UUID) on every seeded incident, and `snapshot_key` in the new nested form
- desired-state fields consistent with each camera's incidents — a camera with a seeded open incident
  must be `desired_ai_state=Paused`, reason `incident`, or the seed data will contradict the
  `ux_detection_open_camera` index
- a handful of `audit_log` rows so the P2 viewer has something to page through
- **respect `ux_detection_open_camera`**: at most one `Unverified`/`Ongoing` incident per camera. The
  current seeder does not know about this and will fail on it

`reset_db.py` needs no logic change but must delete `-wal` and `-shm` sidecars (it already does).

---

## Verification

```bash
uv run pytest
```

The existing suite must pass end to end after Step 3, and again after Step 10 with assertions updated
only where a field genuinely moved.

```bash
uv run python backend/scripts/reseed_dev.py --profile demo
```

Then, in order:

1. **The critical check.** Delete `adas.db`, run `uv run pytest`, confirm `adas.db` was **not**
   recreated. This is the Step 6 acceptance criterion and the highest-value fix in the package.
2. Foreign keys are live:
   ```bash
   uv run python -c "from app.core.db import engine; from sqlalchemy import text; print(engine.connect().execute(text('PRAGMA foreign_keys')).scalar())"
   ```
   must print `1`.
3. Audit immutability:
   ```bash
   uv run python -c "from app.core.db import engine; from sqlalchemy import text; engine.connect().execute(text(\"UPDATE audit_log SET action='X'\"))"
   ```
   must raise `audit_log is append-only`.
4. UTC round-trip: write a `+08:00` datetime, read it back, assert it is tz-aware UTC and equal.
5. Start the backend and confirm `/healthz/live` and `/healthz/ready` both return 200, and that
   `SQL_ECHO=false` means no SQL in the logs.
6. **Legacy AI contract still works.** With `mediamtx mediamtx.yml` running, start the backend and
   `uv run python ai_engine/main.py`. The engine must poll `GET /api/internal/cameras` successfully
   and a simulated detection must still create an incident through `POST /api/internal/alert`.
   Run this check at the end of **every** package, not just this one.
7. `pnpm check` passes.

---

## Tests to write

Not exhaustive coverage — these specific behaviours:

| Area | What to assert |
|---|---|
| `UtcDateTime` | naive input raises; offset input normalizes; read-back is tz-aware UTC |
| Query datetime parsing | `+08:00` and naive both produce the correct UTC boundary |
| Pragmas | `foreign_keys=1`, `journal_mode=wal` on a fresh connection |
| FK enforcement | inserting a `detection_log` with a nonexistent `camera_id` raises |
| CHECK constraints | out-of-range `confidence_score`, bad `role`, bad `detection_status`, `channel_id <= 0` |
| Partial unique indexes | duplicate active camera name (case-insensitive) rejected; **reusing a soft-deleted camera's name succeeds** — this is currently a 500 |
| One-open-incident index | a second `Unverified` incident for the same camera raises `IntegrityError` |
| Audit triggers | UPDATE and DELETE both raise |
| Log redaction | a credential-bearing `rtsp://` URL never reaches the log output |
| Probes | `/healthz/ready` returns 503 when the DB is unreachable |
| Test isolation | the suite does not create or modify the repo-root `adas.db` |

## Paper test cases covered

TC-U-401 (`Unverified` default), TC-U-402 (WAL concurrent read/write without "database is locked"),
partial credit toward TC-U-403 (`detected_at` preserved across transitions — completed in P4).

## Deliberately not in this package

Auth changes, audit *writing* (the table and triggers exist; P2 populates it), WebSocket changes,
any lifecycle behavior change, Alembic.
