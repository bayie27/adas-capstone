# ADAS Backend

> Last updated: August 10, 2026

FastAPI backend for the ADAS real-time road accident detection system. Handles authentication, the HITL alert workflow, camera management, user management, system health telemetry, reports/exports, backup/restore, the Help Center, and WebSocket broadcasting to the React dashboard.

For the full system overview, see the [root README](../README.md).

---

## Stack

| Layer           | Technology                                                                            |
| --------------- | ------------------------------------------------------------------------------------- |
| Framework       | FastAPI 0.136 on Uvicorn (ASGI)                                                       |
| Database        | SQLite with WAL mode, schema managed by Alembic                                       |
| ORM             | SQLModel (SQLAlchemy + Pydantic)                                                      |
| Auth            | HttpOnly session cookie (JWT via PyJWT) · Argon2id via passlib                        |
| Scheduling      | APScheduler (cooldowns, snoozes, health sampling/rollup, export cleanup)              |
| PDF/CSV         | fpdf2 · stdlib `csv` (streamed)                                                       |
| Real-time       | WebSocket (native FastAPI), versioned event envelope                                  |
| Testing         | pytest — in-memory SQLite for the fast suite, a real file-backed DB for `tests/perf/` |
| Package manager | uv                                                                                    |

---

## Setup

**From the repo root:**

```bash
uv sync
```

**Configure environment** — copy `.env.example` to `.env` in the repo root and fill in all values. The backend reads from `backend/../.env` (i.e., the repo root `.env`). See the root README for the full variable list.

**Initialize the database:**

```bash
uv run python backend/scripts/reseed_dev.py
```

This creates `adas.db` at the repo root, provisions the schema by running `alembic upgrade head` (not a `CREATE TABLE`-equivalent metadata call — see [CONTRIBUTING.md](../CONTRIBUTING.md)'s "Database migrations" section), and seeds the default admin account, six cameras, and sample alerts. See [`backend/scripts/README.md`](scripts/README.md) for the full script reference, including the `perf` profile — the scripts README is comprehensive and should be your first stop for any DB management task.

---

## Running

```bash
# From repo root
uv run fastapi dev backend/app/main.py
```

- API: `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs`
- Liveness probe: `GET http://localhost:8000/healthz/live`
- Readiness probe: `GET http://localhost:8000/healthz/ready`

---

## Project Layout

```
backend/
├── alembic/                 # Schema migrations — see ../CONTRIBUTING.md
│   ├── env.py
│   └── versions/
├── app/
│   ├── main.py               # App factory, lifespan, middleware, WebSocket endpoint
│   ├── models/                # SQLModel tables, one module per domain (user, camera, detection, audit, health, export, help)
│   ├── schemas/                # Pydantic request/response schemas — not ORM models
│   ├── services/                # Business logic: incidents, cameras, snoozes, audit, filters, realtime, reports/, sessions, snapshots
│   ├── maintenance/             # Backup/restore/archive/restart — runnable as `python -m app.maintenance`
│   ├── core/
│   │   ├── config.py         # Pydantic Settings (reads from .env), every setting has a safe default
│   │   ├── db.py             # Engine, WAL/pragma setup, session factory, init_db (revision check + seeding)
│   │   ├── migrations.py     # Alembic startup revision check — refuses stale/missing schema in production
│   │   ├── types.py          # UtcDateTime — the only stored-timestamp SQLAlchemy type in this schema
│   │   ├── security.py       # get_password_hash/verify_password (Argon2id), create_session_token
│   │   ├── scheduler.py      # APScheduler wiring shared by every background job
│   │   ├── monitor.py        # System-health sampling, hourly rollup, raw/hourly retention pruning
│   │   ├── rate_limit.py     # Login rate limiting (IP + username dimensions)
│   │   └── redaction.py      # Secret/credential redaction for logs and audit detail
│   └── api/
│       ├── dependencies.py   # Session-cookie auth, x-api-key auth, RBAC guards
│       └── routes/
│           ├── internal.py          # AI engine bridge — v2 heartbeat + idempotent alert ingestion
│           ├── auth.py              # POST /api/auth/login, POST /api/auth/logout
│           ├── cameras.py           # Camera CRUD, KPI/breakdown response shape
│           ├── alerts.py            # HITL workflow (confirm/dismiss/resolve/snooze) + CSV/PDF export
│           ├── users.py             # User CRUD (Admin) and self-service (Operator)
│           ├── analytics.py         # Dashboard KPIs, AI performance, charts + exports
│           ├── audit.py             # Append-only activity audit viewer + export (Admin only)
│           ├── settings.py          # Per-user alarm settings (sound/volume/snooze duration)
│           ├── exports.py           # Async export jobs + retraining ZIP package
│           ├── help.py              # Help Center articles, role-filtered, FTS5 search
│           ├── events.py            # WebSocket event-schema support routes
│           ├── system.py            # Unauthenticated /healthz/live, /healthz/ready
│           ├── system_health.py     # Authenticated live/historical hardware telemetry
│           └── maintenance.py       # Backup/restore API (Admin only)
├── scripts/                 # Dev and ops utilities — see scripts/README.md
│   ├── README.md
│   ├── _bootstrap.py
│   ├── reset_db.py
│   ├── seed_dev_data.py     # demo / analytics / edge / perf profiles
│   ├── reseed_dev.py
│   ├── offline_restore.sh
│   └── daily_restart.sh
└── tests/
    ├── conftest.py            # Fixtures, seed helpers, auth helpers
    ├── test_*.py               # ~30 files covering every route/service module (see "Testing" below)
    └── perf/                    # Slow, opt-in — real 100,000-row database (see "Testing" below)
```

---

## API Reference

**Auth column:** **S** = valid session cookie · **A** = session + `Admin` role · **K** = `x-api-key` (AI engine only) · **—** = public. Every non-2xx response uses the shared error envelope (`detail`, `code`, and `errors` for 422s) — see `app/schemas/common.py`.

### Authentication — `/api/auth`

| Method | Path               | Auth | Description                                                                                                                                                   |
| ------ | ------------------ | ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST` | `/api/auth/login`  | —    | `application/x-www-form-urlencoded` `username`/`password`. Sets an `HttpOnly` session cookie, returns `{"user": {...}}` — no token in the body. Rate-limited. |
| `POST` | `/api/auth/logout` | S    | Revokes the session, closes its WebSockets, clears the cookie. `204`.                                                                                         |

`GET /api/users/me` (below) is the authenticated profile endpoint the frontend uses to render role-aware UI, since the cookie is `HttpOnly` and JS can't decode it.

### Internal — AI Engine Bridge (`/api/internal`)

Protected by `x-api-key` (the `INTERNAL_API_KEY` from `.env`, compared with `secrets.compare_digest`), never by the session cookie. The v1 poll/PATCH routes were removed by the A3 audit pack (`be_audit/A3_ai_seam.md`, F3) — no caller since PR #67; `be_plan/01_CONTRACTS.md` §6 has the full v2 payload shapes.

| Method | Path                      | Description                                                                                              |
| ------ | ------------------------- | -------------------------------------------------------------------------------------------------------- |
| `POST` | `/api/internal/alert`     | v2 idempotent ingestion — `source_event_id` (idempotent retry key) and `snapshot_key`.                   |
| `POST` | `/api/internal/heartbeat` | Every 3s. Request: per-camera observed state. Response: a complete authoritative desired-state snapshot. |

### Cameras — `/api/cameras`

| Method   | Path                       | Auth | Description                                                                  |
| -------- | -------------------------- | ---- | ---------------------------------------------------------------------------- |
| `GET`    | `/api/cameras/`            | S    | KPI + breakdown + paginated list — see the response shape below.             |
| `POST`   | `/api/cameras/`            | S    | Create. Bumps `config_version`. Duplicate name/channel → `409`, never a 500. |
| `PATCH`  | `/api/cameras/{camera_id}` | S    | Edit. Bumps `config_version` when an AI-relevant field changes.              |
| `DELETE` | `/api/cameras/{camera_id}` | S    | Soft delete; sets `desired_ai_state=Inactive`.                               |

**`GET /api/cameras/` response shape** (`01_CONTRACTS.md` §5.9):

```json
{
  "kpis": { "total": 10, "enabled": 8, "network_connected": 7, "active_detection": 6 },
  "breakdowns": {
    "connection": { "connected": 7, "disconnected": 2, "reconnecting": 1, "unresponsive": 0 },
    "ai": { "active": 6, "paused": 1, "inactive": 3, "unresponsive": 0 }
  },
  "total_filtered": 4,
  "cameras": []
}
```

### Alerts (HITL workflow) — `/api/alerts`

| Method | Path                            | Auth | Description                                                                                                                   |
| ------ | ------------------------------- | ---- | ----------------------------------------------------------------------------------------------------------------------------- |
| `GET`  | `/api/alerts/`                  | S    | Paginated list. Filters: `status[]`, `camera_id[]`, `user_id[]`, `start_date`, `end_date`, `search`, `sort_by`, `sort_order`. |
| `GET`  | `/api/alerts/export`            | S    | `?format=csv\|pdf` (default csv). Streamed CSV; synchronous PDF up to `EXPORT_PDF_MAX_ROWS`.                                  |
| `GET`  | `/api/alerts/{log_id}`          | S    | Full detail.                                                                                                                  |
| `GET`  | `/api/alerts/{log_id}/snapshot` | S    | The incident snapshot JPEG — authenticated, not a public static mount.                                                        |
| `POST` | `/api/alerts/{log_id}/confirm`  | S    | `Unverified → Ongoing`.                                                                                                       |
| `POST` | `/api/alerts/{log_id}/dismiss`  | S    | `Unverified → Dismissed` (60s cooldown) or `Ongoing → Dismissed` (immediate resume).                                          |
| `POST` | `/api/alerts/{log_id}/resolve`  | S    | `Ongoing → Resolved`. Immediate resume.                                                                                       |
| `POST` | `/api/alerts/{log_id}/snooze`   | S    | `Unverified` only. Duration comes from the actor's saved settings, never the request body.                                    |

**Detection status flow** (D-002 — the only canonical version; `Closed` is never a stored value):

```
Unverified ──confirm──► Ongoing ──resolve──► Resolved
     │                     │
     └──dismiss──► Dismissed ◄──dismiss── (correction)
     (60s cooldown)              (immediate resume)
```

Every transition is a conditional `UPDATE ... WHERE detection_status = :expected`, never read-then-write — a lost race returns `409 CONFLICT_STATE` with the winner's identity, not a silent overwrite.

### Users — `/api/users`

| Method   | Path                                  | Auth | Description                                                     |
| -------- | ------------------------------------- | ---- | --------------------------------------------------------------- |
| `GET`    | `/api/users/me`                       | S    | Own profile.                                                    |
| `PATCH`  | `/api/users/me`                       | S    | Update own username/first/last name. Does not accept `role`.    |
| `PATCH`  | `/api/users/me/password`              | S    | Change own password. Revokes every other session for that user. |
| `GET`    | `/api/users/`                         | A    | Paginated, searchable directory.                                |
| `POST`   | `/api/users/`                         | A    | Create. Also creates a default `alarm_settings` row.            |
| `PATCH`  | `/api/users/{user_id}`                | A    | Edit profile/role/active status. Guards the last active admin.  |
| `POST`   | `/api/users/{user_id}/reset-password` | A    | Force-reset. Revokes every session for that user.               |
| `DELETE` | `/api/users/{user_id}`                | A    | Soft delete. Guards self-delete and the last active admin.      |

### Analytics — `/api/analytics`

| Method | Path                                | Auth |
| ------ | ----------------------------------- | ---- |
| `GET`  | `/api/analytics/dashboard`          | S    |
| `GET`  | `/api/analytics/export/dashboard`   | S    |
| `GET`  | `/api/analytics/performance`        | S    |
| `GET`  | `/api/analytics/export/performance` | S    |

Accidents = `Ongoing` + `Resolved`; false positives = `Dismissed`; `Unverified` is excluded from every analytics number. `precision = confirmed / (confirmed + dismissed)`, returning `null` (never `0`) on zero division.

### Settings, audit, exports, help, system — summary

| Area           | Routes                                                                                                                        | Auth                                    |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| Alarm settings | `GET`/`PUT /api/settings/alarm`                                                                                               | S                                       |
| Audit trail    | `GET /api/audit-logs`, `GET /api/audit-logs/export`                                                                           | A                                       |
| Async exports  | `POST /api/exports/jobs`, `GET /api/exports/jobs/{id}`, `GET /api/exports/jobs/{id}/download`, `POST /api/exports/retraining` | S (job owner or Admin) / A (retraining) |
| Help Center    | `GET /api/help/articles`, `GET /api/help/articles/{slug}`                                                                     | S, role-filtered                        |
| System health  | `GET /api/system/health/live`, `GET /api/system/health/history`                                                               | S                                       |
| Backup/restore | `GET`/`POST /api/system/backups`, `POST /api/system/restores`, `GET /api/system/restores/latest`                              | A                                       |
| Probes         | `GET /healthz/live`, `GET /healthz/ready`                                                                                     | —                                       |

Full request/response schemas for all of the above are in `app/schemas/` and documented interactively at `/docs`; `be_plan/01_CONTRACTS.md` is the frozen source of truth this backend was built against.

### WebSocket

```
ws://localhost:8000/ws/alerts
```

Authenticated by the same session cookie as REST — the browser attaches it automatically on the handshake (including in the test suite, once the workaround in `backend/tests/conftest.py::auth_headers` is applied, since httpx's cookie jar doesn't forward to `ws://` automatically). Every server message uses a versioned envelope:

```json
{
  "version": 1,
  "event_id": "8c2a…-uuid",
  "type": "NEW_DETECTION",
  "occurred_at": "2026-08-10T10:30:05+00:00",
  "data": {}
}
```

Event types: `CONNECTION_READY`, `NEW_DETECTION`, `ALERT_STATUS_UPDATE`, `CAMERA_STATUS_UPDATE`, `SNOOZE_ACTIVATED`, `RE_ALARM`. Delivery is at-most-once/best-effort while connected — `event_id` lets the client deduplicate across a reconnect race; REST (`GET /api/alerts/`, `GET /api/cameras/`) is the recovery path after every reconnect.

---

## Data Models

### Detection Status Values

| Value        | Meaning                                              |
| ------------ | ---------------------------------------------------- |
| `Unverified` | AI detected, operator has not acted yet              |
| `Ongoing`    | Operator confirmed — active emergency, camera paused |
| `Dismissed`  | False positive or corrected human error              |
| `Resolved`   | Emergency cleared, camera resumed                    |

### Camera state — desired vs. observed (D-003)

Desired state is backend-owned (only routes and incident transitions write it); observed state is AI-owned (only heartbeat processing writes it). They are independent dimensions — a reconciling camera can briefly show a desired state that differs from its observed one.

| `desired_ai_state` | `desired_state_reason`  | `connection_status` (observed) | `ai_status` (observed) |
| ------------------ | ----------------------- | ------------------------------ | ---------------------- |
| `Active`           | —                       | `Connected`                    | `Active`               |
| `Paused`           | `incident` / `cooldown` | `Disconnected`                 | `Inactive`             |
| `Inactive`         | `disabled`              | `Reconnecting`                 | `Paused`               |
|                    |                         | `Unresponsive`                 | `Unresponsive`         |

### Password Rules

Enforced at the API layer (Pydantic validators), not just the frontend:

- Minimum 8 characters, maximum 128
- Must contain at least one digit

---

## Security

- **Session cookie, not a bearer token.** `HttpOnly`, `Secure` in production, `SameSite=Strict`. Backed by a revocable `auth_session` database row — a correctly signed JWT with a missing/expired/revoked session row is rejected. See `be_decisions_review.md` D-006.
- **Argon2id** — salted password hashing via passlib. Plain-text passwords are never stored, logged, or audited.
- **`INTERNAL_API_KEY`** — static key for AI engine routes, compared with `secrets.compare_digest`. A missing header is `401`, not `422`.
- **RBAC** — injected via FastAPI dependency (`get_current_user`, admin-only routes add a role check). A `403` is returned before any business logic executes, and the denial is audited.
- **Append-only audit trail** — `audit_log` rows commit in the same transaction as the primary action (D-007); SQLite triggers reject `UPDATE`/`DELETE` against that table outright.
- **Soft deletes** — `User` and `Camera` rows are never hard-deleted; `is_active=False` preserves referential integrity for historical incidents.
- **ORM parameterization** — all DB queries go through SQLModel/SQLAlchemy. No raw SQL string interpolation.
- **Origin validation** — cookie-authenticated unsafe methods (`POST`/`PUT`/`PATCH`/`DELETE`) reject a disallowed `Origin` header, as defense in depth alongside `SameSite=Strict`.

---

## Testing

```bash
# From repo root
uv run pytest

# Verbose output
uv run pytest -v

# Single file
uv run pytest backend/tests/test_alerts.py -v

# The slow perf suite (excluded from the default run — see pyproject.toml)
uv run pytest -m slow backend/tests/perf/ -s
```

The default suite uses an in-memory SQLite database via the `session` fixture in `conftest.py` — fresh per test, `SQLModel.metadata.create_all` on setup (the one place that's still appropriate; see `CONTRIBUTING.md`), `drop_all` on teardown. The FastAPI dependency override replaces `get_session`/`get_engine` so routes hit the in-memory DB.

`backend/tests/perf/` is different by design: it seeds a real 100,000-row file-backed database once per session and measures actual latency against it (NFR-04/06/08, D-008) — see `be_plan/EVIDENCE.md` for the numbers this produced.

**Current coverage** (representative, not exhaustive — every route/service module has a corresponding test file):

| File                                     | What it tests                                                                             |
| ---------------------------------------- | ----------------------------------------------------------------------------------------- |
| `test_auth.py`                           | Login/logout, JWT verification, session authority, rate limiting, RBAC, origin validation |
| `test_users.py`                          | Full user CRUD, self-service, last-admin guards, password rules, soft delete              |
| `test_alerts.py`                         | Filtering, pagination, export, every HITL transition and its rejection/race cases         |
| `test_cameras.py`                        | Camera CRUD, KPI/breakdown invariants, desired-state effects                              |
| `test_camera_reconciliation.py`          | Desired-state derivation from incidents/cooldowns, restart durability                     |
| `test_internal.py`                       | AI engine webhook (v1/v2), idempotent ingestion, heartbeat contract                       |
| `test_snoozes.py`                        | Snooze scheduling, expiry, re-snooze, restart recovery                                    |
| `test_audit.py`                          | Append-only enforcement, transaction coupling, redaction, RBAC, filtering, export         |
| `test_analytics.py`                      | Dashboard KPIs, AI performance, precision calibration, export parity                      |
| `test_reports.py`                        | PDF/CSV report contract — headers, pagination, filter summaries, empty states             |
| `test_exports.py`                        | Async export jobs, retraining package, row limits, artifact lifecycle                     |
| `test_help.py`                           | Role-filtered articles, FTS5 search + `LIKE` fallback, idempotent seeding                 |
| `test_system_health.py`                  | Live/historical telemetry, rollup, retention pruning, warning thresholds                  |
| `test_maintenance.py`                    | Backup/restore/rollback, disk-space guards, concurrency locking                           |
| `test_realtime.py` / `test_websocket.py` | Handshake, connection limits, backpressure isolation, envelope/broadcast shape            |
| `test_schema.py`                         | Every DB-level CHECK constraint, FK behavior, and uniqueness rule                         |
| `perf/`                                  | NFR-04/06/08 and D-008, measured against a real 100,000-row database                      |

---

## Recently completed (previously listed here as planned)

`routes/analytics.py`, `routes/system.py` + `routes/system_health.py`, and `core/monitor.py` are all fully implemented with full pytest coverage — this file used to list them as "(planned)", which had gone stale by several months. So is `app/maintenance/` (backup/restore/restart, not present at all when this file last described the layout) and the Help Center (`routes/help.py`).
