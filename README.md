# ADAS — Intelligent Real-Time Road Accident Detection & Alert System

> Last updated: August 10, 2026

A capstone project for De La Salle Lipa, Bachelor of Science in Information Technology, College of Information Technology and Engineering. ADAS automates vehicle-to-vehicle collision detection across a CCTV network, eliminating reliance on manual monitoring and reducing emergency notification latency to seconds.

The system is composed of three independently runnable components that communicate over HTTP and WebSocket on a shared local network:

- **AI Engine** — a Python worker that ingests RTSP camera streams, runs YOLO inference, and fires a webhook to the backend when a collision is detected.
- **Backend** — a FastAPI server that manages the database, handles the Human-in-the-Loop (HITL) alert workflow, and broadcasts real-time updates over WebSocket.
- **Frontend** — a React Single Page Application that operators use to monitor live alerts, manage cameras, review historical logs, and analyze system health and AI performance.

---

## Repository Structure

```
adas-capstone/
├── ai_engine/
│   ├── main.py              # Entry point — multi-camera inference loop
│   ├── camera.py            # Threaded RTSP stream reader with auto-reconnect
│   ├── accident.py          # Accident detection logic and webhook dispatch
│   ├── sync.py              # Background thread that polls the backend for camera state
│   ├── config.py            # AI engine configuration (thresholds, endpoints)
│   ├── best.pt / best.engine # YOLO weights (portable) / TensorRT engine (GPU-specific)
│   └── snapshots/           # Saved incident snapshots (auto-created)
├── backend/
│   ├── alembic/              # Schema migrations — see CONTRIBUTING.md's "Database migrations"
│   ├── app/
│   │   ├── main.py          # FastAPI app, lifespan, middleware, WebSocket
│   │   ├── models/          # SQLModel table definitions, one module per domain
│   │   ├── schemas/         # Pydantic request/response schemas (not ORM models)
│   │   ├── services/        # Business logic — incidents, cameras, snoozes, audit, realtime, reports, ...
│   │   ├── maintenance/     # Backup/restore/archive/restart — also runnable as `python -m app.maintenance`
│   │   ├── core/
│   │   │   ├── config.py     # Settings loaded from .env
│   │   │   ├── db.py         # Engine, WAL setup, session, DB init
│   │   │   ├── migrations.py # Alembic startup revision check
│   │   │   ├── types.py      # UtcDateTime — the only stored-timestamp type in this schema
│   │   │   ├── security.py   # Password hashing (Argon2id) and JWT creation
│   │   │   ├── scheduler.py  # APScheduler wiring (cooldowns, snoozes, health, exports)
│   │   │   └── monitor.py    # System-health sampling, hourly rollup, retention pruning
│   │   └── api/
│   │       ├── dependencies.py          # Auth guards (session cookie, x-api-key, RBAC)
│   │       └── routes/
│   │           ├── internal.py          # AI engine webhook + heartbeat (v1 legacy and v2)
│   │           ├── auth.py              # Login/logout (HttpOnly session cookie)
│   │           ├── cameras.py           # Camera CRUD and management
│   │           ├── alerts.py            # HITL workflow (confirm/dismiss/resolve/snooze) + exports
│   │           ├── users.py             # User CRUD and self-service
│   │           ├── analytics.py         # Dashboard KPIs, AI performance, charts + exports
│   │           ├── audit.py             # Append-only activity audit viewer + export (Admin only)
│   │           ├── settings.py          # Per-user alarm settings
│   │           ├── exports.py           # Async export jobs + retraining package
│   │           ├── help.py              # Help Center articles (role-filtered, FTS5 search)
│   │           ├── events.py            # WebSocket event schema support routes
│   │           ├── system.py            # Unauthenticated `/healthz/live`, `/healthz/ready` probes
│   │           ├── system_health.py     # Authenticated live/historical hardware telemetry
│   │           └── maintenance.py       # Backup/restore API (Admin only)
│   ├── scripts/             # Dev utilities — see backend/scripts/README.md
│   ├── tests/                # Pytest test suite, plus tests/perf/ (slow, opt-in — see CONTRIBUTING.md)
│   └── README.md            # Backend-specific setup and API reference
├── frontend/
│   ├── src/                 # React source (components, pages, hooks, stores)
│   ├── public/
│   └── package.json
├── e2e/                     # Playwright specs (CI-only, spans backend + frontend)
├── mediamtx.yml             # Camera simulation config — see "Simulate camera streams"
├── scripts/start-sim.ps1    # Preflighted wrapper around `mediamtx mediamtx.yml`
├── scripts/adas-maintenance.ps1  # Windows demo orchestrator for backup/restore/restart
├── alembic.ini               # Points at backend/alembic/ — see CONTRIBUTING.md
├── pyproject.toml
├── uv.lock
├── package.json             # Root pnpm workspace — see CONTRIBUTING.md for the script reference
└── .python-version          # 3.12.13
```

---

## Prerequisites

- **Python 3.12.13** (pinned via `.python-version`)
- **uv** — fast Python package manager (`pip install uv` or see [uv docs](https://docs.astral.sh/uv/))
- **Node.js 22+** and **pnpm** — for the frontend and the root pnpm workspace (`package.json` at the repo root drives lint/format/test scripts across both)
- **ffmpeg** — required to broadcast local video files to the RTSP proxy during development
- **MediaMTX** — RTSP media server used to simulate the VMS in development ([download](https://github.com/bluenviron/mediamtx/releases))
- **NVIDIA GPU + CUDA** — required to run the AI engine with the TensorRT engine; the AI engine falls back to portable `.pt` weights (still needs a GPU for reasonable inference speed, but not a matching TensorRT build) if `best.engine` fails to load

---

## Environment Setup

Copy `.env.example` to `.env` in the repo root and fill in all values — it documents every setting with its default, so treat it as the source of truth rather than this abbreviated list:

```env
# Security
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256

# Internal AI Webhook
INTERNAL_API_KEY=your-internal-api-key

# Database
DATABASE_URL=sqlite:///./adas.db
DEFAULT_ADMIN_PASSWORD=ChangeMe123

# Dahua DSS Pro VMS (production only)
DSS_IP=192.168.1.100
DSS_PORT=80
DSS_USERNAME=admin
DSS_PASS=your-vms-password
```

Everything else (session lifetime, rate limiting, snooze/cooldown windows,
health-sampling intervals, export row limits and TTLs, WebSocket connection
limits, backup retention) has a safe default and only needs overriding for
production. Three storage roots are worth knowing about up front since
they're where the backend writes files outside the database:

| Setting         | Default                      | What lives there                                                                                                             |
| --------------- | ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `SNAPSHOT_ROOT` | `<repo>/ai_engine/snapshots` | Incident snapshot JPEGs, served only via the authenticated `GET /api/alerts/{log_id}/snapshot` — never a public static mount |
| `BACKUP_DIR`    | `<repo>/var/backups`         | Verified online backups + `restore_state.json`                                                                               |
| `EXPORT_DIR`    | `<repo>/var/exports`         | Generated CSV/PDF/ZIP export artifacts (expire after `EXPORT_ARTIFACT_TTL_HOURS`)                                            |

`var/` is gitignored — safe scratch space for local backups, exports, and
migration testing.

---

## Installation

**Python dependencies:**

```bash
uv sync
```

`uv sync` alone installs the backend only (fast, no CUDA — this is what CI runs). The AI engine's heavy ML dependencies (torch, tensorrt, ultralytics, opencv) live behind an optional extra, so running the AI engine needs:

```bash
uv sync --extra ai
```

**Node dependencies (frontend + root tooling):**

Run from the **repo root**, not `frontend/` — this is a pnpm workspace, and running it at the root is also what activates the git hooks (see [CONTRIBUTING.md](CONTRIBUTING.md)):

```bash
pnpm install
```

---

## Running the System

All three components run in separate terminals. **Run every command from the repo root.** This is a convention, not a hard requirement anymore — the FastAPI CLI injects `backend/` into `sys.path` itself, and `DATABASE_URL` resolves to an absolute path under the repo root regardless of CWD — but the AI engine's `from config import ...`-style imports still need `ai_engine/` to be the script's own directory (which `uv run python ai_engine/main.py` gives it), so running from the root is simplest across the board.

**1. Start the backend**

```bash
uv run fastapi dev backend/app/main.py
```

API available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

**2. Start the frontend**

```bash
cd frontend
pnpm dev
```

Dashboard available at `http://localhost:5173`.

**3. Simulate camera streams (development)**

The AI engine expects RTSP feeds at `rtsp://localhost:8554/channel1` through `channel5`. There are three ways to produce them; pick whichever fits what you're doing. All three need `ai_engine/sample_vids/` populated first — see [Obtaining the sample clips](#obtaining-the-sample-clips) below.

Channel → clip mapping:

| Path       | Clip                     |
| ---------- | ------------------------ |
| `channel1` | `car_car.mp4`            |
| `channel2` | `car-motor-motor.mp4`    |
| `channel3` | `defour.mp4`             |
| `channel4` | `red-car-motorcycle.mp4` |
| `channel5` | `motor-to-motor.mp4`     |

**Method 1 — `mediamtx.yml` (default, recommended).** One command, all 5 channels, run from the repo root:

```bash
mediamtx mediamtx.yml
```

`runOnInit` starts an `ffmpeg` per channel automatically and restarts it if it dies. One Ctrl+C in the MediaMTX terminal cleans up MediaMTX and every child `ffmpeg` process. `scripts/start-sim.ps1` wraps this with preflight checks (ffmpeg/mediamtx on PATH, `sample_vids/` populated) and clearer errors if something's missing:

```powershell
.\scripts\start-sim.ps1
```

**Method 2 — manual ffmpeg per channel.** One terminal per channel, blocking. Useful if you only need one or two streams up. Run from the repo root (the paths below are root-relative). `-rtsp_transport tcp` matters, not just style — with the default UDP transport, publishing several channels at once over loopback drops RTP packets constantly:

```powershell
ffmpeg -re -stream_loop -1 -i ai_engine\sample_vids\car_car.mp4 -c copy -rtsp_transport tcp -f rtsp rtsp://localhost:8554/channel1
ffmpeg -re -stream_loop -1 -i ai_engine\sample_vids\car-motor-motor.mp4 -c copy -rtsp_transport tcp -f rtsp rtsp://localhost:8554/channel2
ffmpeg -re -stream_loop -1 -i ai_engine\sample_vids\defour.mp4 -c copy -rtsp_transport tcp -f rtsp rtsp://localhost:8554/channel3
ffmpeg -re -stream_loop -1 -i ai_engine\sample_vids\red-car-motorcycle.mp4 -c copy -rtsp_transport tcp -f rtsp rtsp://localhost:8554/channel4
ffmpeg -re -stream_loop -1 -i ai_engine\sample_vids\motor-to-motor.mp4 -c copy -rtsp_transport tcp -f rtsp rtsp://localhost:8554/channel5
```

**Method 3 — OBS Studio via RTMP (interactive playback control).** Use this when you want to scrub/pause/restart a clip live during a demo — Methods 1 and 2 just loop blindly.

1. OBS → Settings → Stream → Service: **Custom...**, Server: `rtmp://localhost:1935/channel1`, Stream Key: leave empty. (Equivalently, Server `rtmp://localhost:1935` + Stream Key `channel1` — MediaMTX's docs recommend putting the path in the server URL.)
2. Add a **Media Source** pointing at a clip in `ai_engine/sample_vids/`, tick **Loop**. The Media Source exposes Restart/Pause/Play hotkeys for interactive control.
3. Click **Start Streaming**. MediaMTX auto-creates the path and republishes it as `rtsp://localhost:8554/channel1` — no AI engine changes needed.

**Limitation:** one OBS instance publishes exactly one stream. Simulating all 5 channels via OBS needs 5 OBS instances/profiles or the `obs-multi-rtmp` plugin — use OBS for an interactive demo of one or two channels, and Method 1 for bulk background simulation.

MediaMTX's default ports: RTSP `8554`, RTMP `1935`, HLS `8888`, WebRTC `8889`, SRT `8890`.

#### Obtaining the sample clips

`.gitignore` excludes `*.mp4`, so `ai_engine/sample_vids/` is not in the repo — a fresh clone has no clips and can't run the simulation until you add them. Expected filenames:

- `car_car.mp4`
- `car-motor-motor.mp4`
- `defour.mp4`
- `red-car-motorcycle.mp4`
- `motor-to-motor.mp4`

> **TODO(team):** paste the shared-drive link for `sample_vids/` here.

**4. Start the AI engine**

Requires `uv sync --extra ai` (see [Installation](#installation)). Run from the repo root:

```bash
uv run python ai_engine/main.py
```

`best.engine` is a TensorRT engine built for one specific GPU + driver + TensorRT version — it will not load on a different machine. The AI engine detects this and falls back to the portable `best.pt` weights automatically; a fallback message on startup is expected on any machine other than the one it was built on.

---

## Development Workflow

**Reset and seed the local database:**

```bash
uv run python backend/scripts/reseed_dev.py
```

Always use `uv run python`, never a bare `python` — the `python` on PATH may be a different, unpinned interpreter (e.g. a system install) rather than the project's pinned 3.12.13. This gives you a fresh DB with an admin account, six cameras, and sample alerts across all detection statuses. Schema is provisioned by running `alembic upgrade head` under the hood, not `CREATE TABLE`-equivalent metadata calls — see [CONTRIBUTING.md](CONTRIBUTING.md)'s "Database migrations" section before changing a model. See [`backend/scripts/README.md`](backend/scripts/README.md) for the full script reference, including the `perf` profile (100,000 incidents, for measuring query/export performance against a realistic dataset size).

**Run the test suite:**

```bash
uv run pytest
```

Tests use an in-memory SQLite database and never touch `adas.db`. This excludes `backend/tests/perf/` by default (slow — seeds a real 100,000-row database); run it explicitly with `uv run pytest -m slow backend/tests/perf/`. For the full pre-push/pre-PR command reference (`pnpm check`, `pnpm full:check`, individual lint/format/typecheck scripts), see [CONTRIBUTING.md](CONTRIBUTING.md).

**Back up or restore the local database:**

```bash
cd backend
uv run python -m app.maintenance backup
uv run python -m app.maintenance list
```

On Windows, `scripts\adas-maintenance.ps1` wraps the full backup/restore/restart lifecycle (stopping and restarting the backend/AI engine processes around the same Python maintenance core) — see that script's own header comment for every `-Action`.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    CCTV / VMS (Dahua DSS Pro)           │
│                    RTSP substreams (720p)                │
└──────────────────────────┬──────────────────────────────┘
                           │ RTSP over TCP
                           ▼
┌──────────────────────────────────────────────────────────┐
│                      AI Engine                           │
│  OpenCV → YOLO inference → AccidentManager               │
│  On detection: saves snapshot, fires POST /api/internal/alert │
└──────────────────────────┬───────────────────────────────┘
                           │ HTTP webhook (INTERNAL_API_KEY)
                           ▼
┌──────────────────────────────────────────────────────────┐
│                    FastAPI Backend                        │
│  SQLite (WAL) · HttpOnly cookie sessions · RBAC · Alembic │
│                                                          │
│  /api/internal/*  ← AI engine only (x-api-key)            │
│  /api/alerts/*    ← HITL workflow + exports               │
│  /api/cameras/*   ← Camera management                    │
│  /api/users/*     ← User management (Admin only)         │
│  /api/audit-logs  ← Append-only activity audit (Admin)    │
│  /api/system/*    ← Hardware telemetry + backup/restore   │
│  /api/exports/*   ← Async export jobs + retraining ZIP    │
│  /api/help/*      ← Role-filtered Help Center             │
│  /ws/alerts       ← Real-time push to dashboard           │
└──────────────────────────┬───────────────────────────────┘
                           │ WebSocket + REST
                           ▼
┌──────────────────────────────────────────────────────────┐
│                   React Dashboard (SPA)                  │
│  React · Zustand · TanStack Query · Recharts · Tailwind  │
│                                                          │
│  Operators: monitor alerts, manage cameras, view logs    │
│  Admins: all of the above + user account management      │
└──────────────────────────────────────────────────────────┘
```

### Key Design Decisions

**Edge-first, no cloud.** Everything runs on a single on-premises server inside the CDRRMO's CCTV VLAN. No external internet dependency during operation.

**Self-blindfold pattern.** When the AI engine detects a collision, it immediately pauses its own ingestion for that camera. The backend mirrors this by marking the camera `Paused` in the DB and broadcasting the state change over WebSocket the moment the webhook arrives — before any operator action.

**HITL state machine.** Detection logs move through `Unverified → Ongoing → Resolved` (true positive) or `Unverified → Dismissed` (false positive, triggers 60-second cooldown) or `Ongoing → Dismissed` (human error correction, resumes immediately). The backend guards against the AI engine overwriting operator-driven pause states.

**WAL mode on SQLite.** Allows the AI engine's high-frequency writes and the dashboard's concurrent reads to coexist without locking errors.

**Cookie-based sessions, not a bearer token.** Login sets an `HttpOnly`, `Secure` (in production) session cookie backed by a revocable `auth_session` database row — the browser attaches it automatically to REST calls and the WebSocket handshake alike, and the frontend never holds a credential in JS-reachable storage. Logout, a password change, a role change, or account deactivation revokes every session for that user immediately.

**Append-only activity audit.** Every security- and operations-relevant action (incident transitions, camera/user changes, exports, backups) writes an `audit_log` row in the same transaction as the primary action; SQLite triggers reject any `UPDATE`/`DELETE` against that table.

**Alembic-managed schema.** One reviewed initial migration (`backend/alembic/versions/`) represents the full production schema; the app refuses to start against a database whose recorded revision doesn't match the code in production, and only warns in development. See [CONTRIBUTING.md](CONTRIBUTING.md)'s "Database migrations" section.

---

## Project Team

Enjey Kashlee M. Alonzo · Sebastian Angelo T. Meer · Daniel Luis P. Sahagun · Jhon Paulo H. Tenorio

De La Salle Lipa — Bachelor of Science in Information Technology, College of Information Technology and Engineering, April 2026
