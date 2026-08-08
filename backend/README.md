# ADAS Backend

> Last updated: April 26, 2026

FastAPI backend for the ADAS real-time road accident detection system. Handles authentication, the HITL alert workflow, camera management, user management, WebSocket broadcasting, and serves the React dashboard.

For the full system overview, see the [root README](../README.md).

---

## Stack

| Layer           | Technology                         |
| --------------- | ---------------------------------- |
| Framework       | FastAPI 0.136 on Uvicorn (ASGI)    |
| Database        | SQLite with WAL mode               |
| ORM             | SQLModel (SQLAlchemy + Pydantic)   |
| Auth            | JWT via PyJWT · bcrypt via passlib |
| Real-time       | WebSocket (native FastAPI)         |
| Testing         | pytest with in-memory SQLite       |
| Package manager | uv                                 |

---

## Setup

**From the repo root:**

```bash
uv sync
```

**Configure environment** — copy `.env.example` to `.env` in the repo root and fill in all values. The backend reads from `backend/../.env` (i.e., the repo root `.env`). See the root README for the full variable list.

**Initialize the database:**

```bash
python backend/scripts/reseed_dev.py
```

This creates `backend/adas.db`, runs all migrations, seeds the default admin account, three cameras, and sample alerts. See [`backend/scripts/README.md`](scripts/README.md) for the full script reference — the scripts README is comprehensive and should be your first stop for any DB management task.

---

## Running

```bash
# From repo root
uv run --no-sync fastapi dev backend/app/main.py
```

- API: `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs`
- Health check: `GET http://localhost:8000/`

---

## Project Layout

```
backend/
├── app/
│   ├── main.py              # App factory, lifespan, middleware, WebSocket endpoint
│   ├── models.py            # All SQLModel tables and Pydantic schemas
│   ├── ws_manager.py        # ConnectionManager for WebSocket broadcast
│   ├── core/
│   │   ├── config.py        # Pydantic settings (reads from .env)
│   │   ├── db.py            # Engine, WAL setup, session factory, init_db
│   │   ├── security.py      # get_password_hash, verify_password, create_access_token
│   │   └── monitor.py       # (planned) Background hardware telemetry polling
│   └── api/
│       ├── dependencies.py  # verify_internal_api_key, get_current_user, get_current_admin
│       └── routes/
│           ├── internal.py  # AI engine bridge — alert webhook, camera status, camera list
│           ├── auth.py      # POST /api/auth/login
│           ├── cameras.py   # Camera CRUD with live status KPIs
│           ├── alerts.py    # HITL workflow — list, export, confirm, dismiss, resolve
│           ├── users.py     # User CRUD (admin) and self-service (operator)
│           ├── analytics.py # (planned) Dashboard KPIs and trend charts
│           └── system.py    # (planned) System health telemetry endpoints
├── scripts/                 # Dev and ops utilities — see scripts/README.md
│   ├── README.md
│   ├── _bootstrap.py
│   ├── reset_db.py
│   ├── seed_dev_data.py
│   ├── seed_alerts_via_api.py
│   ├── reseed_dev.py
│   └── daily_restart.sh     # (planned) Nightly scheduled restart
└── tests/
    ├── conftest.py           # Fixtures, seed helpers, auth helpers
    ├── test_auth.py          # Login, JWT, RBAC routing
    ├── test_users.py         # User CRUD, self-service, last-admin guards
    └── test_alerts.py        # Alert filtering, export, HITL transitions
```

---

## API Reference

All routes except `/api/auth/login`, `/api/internal/*`, and `/` require a valid Bearer token in the `Authorization` header.

### Authentication

| Method | Path              | Auth | Description                                                                            |
| ------ | ----------------- | ---- | -------------------------------------------------------------------------------------- |
| `POST` | `/api/auth/login` | None | Returns JWT. Body: `application/x-www-form-urlencoded` with `username` and `password`. |

### Internal — AI Engine Bridge

These routes are protected by `x-api-key` header (the `INTERNAL_API_KEY` from `.env`), not JWT. They are called by the AI engine only, not by the dashboard.

| Method  | Path                                       | Description                                                                                                                                                                 |
| ------- | ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST`  | `/api/internal/alert`                      | Receives a collision detection event. Saves the log, marks the camera `Paused` in DB, broadcasts `NEW_DETECTION` and `CAMERA_STATUS_UPDATE` over WebSocket.                 |
| `GET`   | `/api/internal/cameras`                    | Returns all enabled, active cameras with current statuses. The AI engine polls this every 3 seconds to reconcile its state on restart.                                      |
| `PATCH` | `/api/internal/cameras/{camera_id}/status` | AI engine reports connection or AI status changes. Updates DB and broadcasts `CAMERA_STATUS_UPDATE`. Rejects attempts to set `ai_status=Active` while an open alert exists. |

**Alert webhook payload:**

```json
{
  "camera_id": 1,
  "detected_at": "2026-04-26T14:30:00.000Z",
  "snapshot_path": "cam1_20260426_143000.jpg",
  "confidence_score": 0.96
}
```

### Cameras

| Method   | Path                       | Auth      | Description                                                                                                            |
| -------- | -------------------------- | --------- | ---------------------------------------------------------------------------------------------------------------------- |
| `GET`    | `/api/cameras/`            | Operator+ | Paginated camera list with global KPIs. Supports `connection_status`, `ai_status`, `is_enabled`, and `search` filters. |
| `POST`   | `/api/cameras/`            | Operator+ | Add a new camera. Validates no duplicate name or channel ID.                                                           |
| `PATCH`  | `/api/cameras/{camera_id}` | Operator+ | Edit camera name, channel ID, or enabled state.                                                                        |
| `DELETE` | `/api/cameras/{camera_id}` | Operator+ | Soft-delete a camera (sets `is_active=False`).                                                                         |

**GET /api/cameras/ response shape:**

```json
{
  "total_cameras": 6,
  "network_connected": 4,
  "active_detection": 3,
  "total_filtered": 6,
  "cameras": [...]
}
```

### Alerts (HITL Workflow)

| Method | Path                           | Auth      | Description                                                                                                                                               |
| ------ | ------------------------------ | --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET`  | `/api/alerts/`                 | Operator+ | Paginated alert list. Filters: `status`, `camera_id`, `user_id`, `start_date`, `end_date`, `search`.                                                      |
| `GET`  | `/api/alerts/export`           | Operator+ | Streams a CSV of the filtered dataset.                                                                                                                    |
| `GET`  | `/api/alerts/{log_id}`         | Operator+ | Full detail for one detection log including camera name.                                                                                                  |
| `POST` | `/api/alerts/{log_id}/confirm` | Operator+ | `Unverified → Ongoing`. Camera stays `Paused`. Records `verified_by` and `verified_at`.                                                                   |
| `POST` | `/api/alerts/{log_id}/dismiss` | Operator+ | `Unverified → Dismissed` (60s cooldown before camera resumes) or `Ongoing → Dismissed` (camera resumes immediately). Records `closed_by` and `closed_at`. |
| `POST` | `/api/alerts/{log_id}/resolve` | Operator+ | `Ongoing → Resolved`. Camera resumes immediately. Records `closed_by` and `closed_at`.                                                                    |

**Detection status flow:**

```
Unverified ──confirm──► Ongoing ──resolve──► Resolved
     │                     │
     └──dismiss──► Dismissed └──dismiss──► Dismissed
     (60s cooldown)              (immediate resume)
```

### Users

| Method   | Path                                  | Auth       | Description                                                                                          |
| -------- | ------------------------------------- | ---------- | ---------------------------------------------------------------------------------------------------- |
| `GET`    | `/api/users/me`                       | Operator+  | Own profile.                                                                                         |
| `PATCH`  | `/api/users/me`                       | Operator+  | Update own username, first name, or last name.                                                       |
| `PATCH`  | `/api/users/me/password`              | Operator+  | Change own password. Requires current password.                                                      |
| `GET`    | `/api/users/`                         | Admin only | Paginated, searchable user directory.                                                                |
| `POST`   | `/api/users/`                         | Admin only | Create a new user account.                                                                           |
| `PATCH`  | `/api/users/{user_id}`                | Admin only | Edit profile, role, or active status. Guards against demoting or deactivating the last active admin. |
| `POST`   | `/api/users/{user_id}/reset-password` | Admin only | Force-reset any user's password.                                                                     |
| `DELETE` | `/api/users/{user_id}`                | Admin only | Soft-delete a user. Guards against self-deletion and deleting the last active admin.                 |

### WebSocket

```
ws://localhost:8000/ws/alerts
```

No authentication on the WebSocket connection itself — the dashboard sends the JWT after connecting if needed. The server pushes two event types:

**`NEW_DETECTION`** — fired when the AI engine sends a new alert:

```json
{
  "type": "NEW_DETECTION",
  "log_id": 42,
  "camera_id": 1,
  "detected_at": "2026-04-26T14:30:00.000Z",
  "snapshot_path": "cam1_20260426_143000.jpg",
  "confidence_score": 0.96,
  "detection_status": "Unverified"
}
```

**`CAMERA_STATUS_UPDATE`** — fired whenever a camera's connection or AI status changes:

```json
{
  "type": "CAMERA_STATUS_UPDATE",
  "camera_id": 1,
  "connection_status": "Connected",
  "ai_status": "Paused"
}
```

---

## Data Models

### Detection Status Values

| Value        | Meaning                                              |
| ------------ | ---------------------------------------------------- |
| `Unverified` | AI detected, operator has not acted yet              |
| `Ongoing`    | Operator confirmed — active emergency, camera paused |
| `Dismissed`  | False positive or corrected human error              |
| `Resolved`   | Emergency cleared, camera resumed                    |

### Camera Status Values

| `connection_status` | `ai_status`    |
| ------------------- | -------------- |
| `Connected`         | `Active`       |
| `Disconnected`      | `Inactive`     |
| `Reconnecting`      | `Paused`       |
| `Unresponsive`      | `Unresponsive` |

### Password Rules

Enforced at the API layer (Pydantic validators), not just the frontend:

- Minimum 8 characters
- Must contain at least one digit

---

## Security

- **JWT** — 8-hour tokens (one shift), encoded with `HS256`. Payload contains `sub` (username) and `role`.
- **bcrypt** — salted password hashing via passlib. Plain-text passwords are never stored or logged.
- **INTERNAL_API_KEY** — static key for AI engine webhook routes. Compared with `secrets.compare_digest` to prevent timing attacks.
- **RBAC** — injected via FastAPI dependency. Operator routes use `get_current_user`; Admin-only routes use `get_current_admin` which calls `get_current_user` first then checks the role. A 403 is returned before any business logic executes.
- **Soft deletes** — `User` and `Camera` rows are never hard-deleted. `is_active=False` preserves referential integrity of the audit trail in `DetectionLog`.
- **ORM parameterization** — all DB queries go through SQLModel/SQLAlchemy. No raw SQL string interpolation.

---

## Testing

```bash
# From repo root
uv run pytest

# Verbose output
uv run pytest -v

# Single file
uv run pytest backend/tests/test_alerts.py -v
```

Tests use an in-memory SQLite database (`sqlite://`) via a session fixture in `conftest.py`. Each test gets a fresh database — `SQLModel.metadata.create_all` on setup, `drop_all` on teardown. The FastAPI dependency override replaces `get_session` with the test session so routes hit the in-memory DB.

**Current coverage:**

| File             | What it tests                                                                     |
| ---------------- | --------------------------------------------------------------------------------- |
| `test_auth.py`   | Login success/failure, inactive accounts, JWT protection, RBAC routing            |
| `test_users.py`  | Full user CRUD, self-service, last-admin guards, password rules, soft delete      |
| `test_alerts.py` | Filtering, pagination, CSV export, all HITL state transitions and rejection cases |

---

## What Is Planned (Not Yet Implemented)

**`routes/analytics.py`** — Dashboard KPIs and charts:

- Global KPIs: total accidents, ongoing count, resolved count
- Accident frequency by camera/location (horizontal bar chart data)
- Peak accident times over 24h (line chart data)
- Dynamic date range and camera filters
- CSV/PDF export of analytical summaries

**`routes/system.py`** — System health endpoints:

- Live telemetry: CPU, GPU, RAM, GPU temperature, system uptime, inference FPS
- Historical raw telemetry (last 48 hours, 5-minute resolution)
- Hourly aggregated trends (30-day rolling window)
- Critical threshold alerting (>85°C GPU temp, >95% RAM)

**`core/monitor.py`** — Background hardware polling:

- Polls `psutil` and `GPUtil` every 5 minutes, writes to `SystemHealthRaw`
- Aggregates into `SystemHealthHourly` at the top of each hour via `apscheduler`
- Prunes `SystemHealthRaw` rows older than 48 hours

**`scripts/daily_restart.sh`** — Nightly maintenance:

- Scheduled via cron for a low-traffic window (e.g. 3:00 AM)
- Gracefully restarts the FastAPI and AI engine processes
- Target: full recovery in under 10 seconds
