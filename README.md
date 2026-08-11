# ADAS — Intelligent Real-Time Road Accident Detection & Alert System

> Last updated: August 8, 2026

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
│   ├── main.py              # Entry point — wire-up only
│   ├── pipeline.py          # Fixed-cadence batched multi-camera tick loop
│   ├── detector.py          # Model ownership, grayscale, class filtering
│   ├── accumulate.py        # Temporal evidence accumulator (fires the event)
│   ├── camera.py            # Threaded RTSP stream reader with auto-reconnect
│   ├── accident.py          # Event → annotated snapshot → outbox entry
│   ├── supervisor.py        # Reconciles engine state against the backend
│   ├── capacity.py          # How many cameras can this machine run?
│   ├── machine_profile.py   # Read/write/validate machine_profile.json
│   ├── config.py            # AI engine configuration (thresholds, endpoints)
│   ├── epoch50.pt           # YOLO weights (the adopted checkpoint)
│   ├── eval/                # Measurement harness — see eval/README.md
│   └── snapshots/           # Saved incident snapshots (auto-created)
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app, lifespan, middleware, WebSocket
│   │   ├── models.py        # SQLModel table definitions and Pydantic schemas
│   │   ├── ws_manager.py    # WebSocket connection manager
│   │   ├── core/
│   │   │   ├── config.py    # Settings loaded from .env
│   │   │   ├── db.py        # Engine, WAL setup, session, DB init
│   │   │   └── security.py  # Password hashing and JWT creation
│   │   └── api/
│   │       ├── dependencies.py          # Auth guards (JWT, API key, RBAC)
│   │       └── routes/
│   │           ├── internal.py          # AI engine webhook and camera status
│   │           ├── auth.py              # Login
│   │           ├── cameras.py           # Camera CRUD and management
│   │           ├── alerts.py            # HITL workflow (confirm/dismiss/resolve)
│   │           ├── users.py             # User CRUD and self-service
│   │           ├── analytics.py         # Dashboard KPIs and charts
│   │           └── system.py            # (not yet implemented) System health telemetry
│   ├── scripts/             # Dev utilities — see backend/scripts/README.md
│   ├── tests/               # Pytest test suite
│   └── README.md            # Backend-specific setup and API reference
├── frontend/
│   ├── src/                 # React source (components, pages, hooks, stores)
│   ├── public/
│   └── package.json
├── e2e/                     # Playwright specs (CI-only, spans backend + frontend)
├── mediamtx.yml             # Camera simulation — see "Simulate camera streams"
├── scripts/start-sim.ps1    # Preflighted wrapper around `mediamtx mediamtx.yml`
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
- **NVIDIA GPU + CUDA** — needed for detection at a usable frame rate. The engine runs without one (see `uv sync --extra ai-cpu` under [Installation](#installation)) and is useful that way for integration work, but a CPU-only machine is not a detection platform and no measured claim may come from it

---

## Environment Setup

Copy `.env.example` to `.env` in the repo root and fill in all values:

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

---

## Installation

**Python dependencies:**

```bash
uv sync
```

`uv sync` alone installs the backend only (fast, no CUDA — this is what CI runs). The AI engine's heavy ML dependencies (torch, ultralytics, opencv) live behind an optional extra, so running the AI engine needs:

```bash
uv sync --extra ai
```

On a machine without an NVIDIA GPU, use the CPU install instead — the `ai` extra pulls CUDA-specific PyTorch wheels that are a large download and of no use there:

```bash
uv sync --extra ai-cpu
```

The two are mutually exclusive; pick one. `ai-cpu` resolves torch from PyTorch's CPU index, so it pulls **no** `nvidia-*` packages at all. (Simply omitting the CUDA index would not be enough — on Linux the default PyPI torch wheel bundles the CUDA runtime anyway.) It also resolves a newer torch than the CUDA extra, since the two indexes carry different builds; that is fine precisely because no measured claim may come from a CPU machine.

The engine detects the absence of a GPU and falls back automatically. It will run and connect, which is useful for integration work, but it is not a detection platform — run `uv run python ai_engine/capacity.py` and it will tell you so.

**Node dependencies (frontend + root tooling):**

Run from the **repo root**, not `frontend/` — this is a pnpm workspace, and running it at the root is also what activates the git hooks (see [CONTRIBUTING.md](CONTRIBUTING.md)):

```bash
pnpm install
```

---

## Running the System

All three components run in separate terminals. **Run every command from the repo root.** This is a convention, not a hard requirement anymore — the FastAPI CLI injects `backend/` into `sys.path` itself, and `DATABASE_URL` resolves to an absolute path under the repo root regardless of CWD — but the AI engine's `from config import ...`-style imports still need `ai_engine/` to be the script's own directory (which `uv run python ai_engine/main.py` gives it), so running from the root is simplest across the board.

### Quickstart — clone to first detection

The whole path, in order. Each step is verified; the detailed sections below explain the parts.

**One-time, in this order:**

```bash
uv sync --extra ai                              # --extra ai-cpu if no NVIDIA GPU
pnpm install                                    # at the ROOT — this activates git hooks
cp .env.example .env                            # then fill in all 10 keys
```

Populate `ai_engine/eval/clips/` — no video ships in a clone. See [Obtaining the clips](#obtaining-the-clips).

```bash
uv run python backend/scripts/reseed_dev.py     # REQUIRED — creates the cameras
uv run python ai_engine/capacity.py             # once per machine
```

> **`reseed_dev.py` is not optional.** Starting the backend creates the tables and an admin account, but **no cameras**. Without seeding, the engine connects, is told there are zero cameras, and does nothing — which looks exactly like it is broken.

**Then four terminals, in this order:**

```bash
mediamtx mediamtx.yml                           # 1. streams
uv run fastapi dev backend/app/main.py          # 2. backend — must precede the engine
cd frontend && pnpm dev                         # 3. dashboard at :5173
uv run python ai_engine/main.py                 # 4. engine
```

Log in at `http://localhost:5173` as `admin` with the `DEFAULT_ADMIN_PASSWORD` from your `.env`.

**Last step: release a camera.** Every seeded camera is paused by an open alert — deliberately, see [below](#cameras-start-paused-after-seeding--this-is-deliberate). Resolve or dismiss one in the dashboard and that camera starts detecting within seconds.

**What a working run looks like:** four cameras alert within a loop or two, and **camera 5 stays silent** — it serves the crash-free clip. A camera that never alerts is as much a result as one that does. The engine log reads:

```
[SYSTEM] Machine profile: 0 · capacity 8 camera(s) @ 15 FPS
[SYSTEM] Resuming AI ingestion for Channel 4...
[ALERT] Channel 4: accident detected (peak 0.76, 2.2s of evidence).
```

---

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

The AI engine expects RTSP feeds at `rtsp://localhost:8554/channel1` through `channel5`. There are three ways to produce them; pick whichever fits what you're doing. All three need `ai_engine/eval/clips/` populated first — see [Obtaining the clips](#obtaining-the-clips) below.

Channel → clip mapping. The first four are clips `ai_engine/eval/baseline_epoch50.json` records as **detected**, so the engine alerts on each within a loop or two. Channel 5 is the crash-free negative and **must stay silent** — a camera that never alerts is as much a result as one that does:

| Path       | Clip                    | Expected              |
| ---------- | ----------------------- | --------------------- |
| `channel1` | `dekwatro.mp4`          | detects               |
| `channel2` | `tric-motor-car.mp4`    | detects               |
| `channel3` | `red-car-motor.mp4`     | detects               |
| `channel4` | `motor-motor-night.mp4` | detects               |
| `channel5` | `airbase.mp4`           | **silent** (no crash) |

**Method 1 — `mediamtx.yml` (default, recommended).** One command, all 5 channels, run from the repo root:

```bash
mediamtx mediamtx.yml
```

`runOnInit` starts an `ffmpeg` per channel automatically and restarts it if it dies. One Ctrl+C in the MediaMTX terminal cleans up MediaMTX and every child `ffmpeg` process. `scripts/start-sim.ps1` wraps this with preflight checks (ffmpeg and mediamtx on PATH, and the five clips present by name) and clearer errors if something's missing:

```powershell
.\scripts\start-sim.ps1
```

MediaMTX writes `auto.crt` and `auto.key` into whatever directory it starts from. Both are gitignored — never commit the key.

**Method 2 — manual ffmpeg per channel.** One terminal per channel, blocking. Useful if you only need one or two streams up. Run from the repo root (the paths below are root-relative). `-rtsp_transport tcp` matters, not just style — with the default UDP transport, publishing several channels at once over loopback drops RTP packets constantly:

```powershell
ffmpeg -re -stream_loop -1 -i ai_engine\eval\clips\dekwatro.mp4 -c copy -rtsp_transport tcp -f rtsp rtsp://localhost:8554/channel1
ffmpeg -re -stream_loop -1 -i ai_engine\eval\clips\tric-motor-car.mp4 -c copy -rtsp_transport tcp -f rtsp rtsp://localhost:8554/channel2
ffmpeg -re -stream_loop -1 -i ai_engine\eval\clips\red-car-motor.mp4 -c copy -rtsp_transport tcp -f rtsp rtsp://localhost:8554/channel3
ffmpeg -re -stream_loop -1 -i ai_engine\eval\clips\motor-motor-night.mp4 -c copy -rtsp_transport tcp -f rtsp rtsp://localhost:8554/channel4
ffmpeg -re -stream_loop -1 -i ai_engine\eval\clips\airbase.mp4 -c copy -rtsp_transport tcp -f rtsp rtsp://localhost:8554/channel5
```

**Method 3 — OBS Studio via RTMP (interactive playback control).** Use this when you want to scrub/pause/restart a clip live during a demo — Methods 1 and 2 just loop blindly.

1. OBS → Settings → Stream → Service: **Custom...**, Server: `rtmp://localhost:1935/channel1`, Stream Key: leave empty. (Equivalently, Server `rtmp://localhost:1935` + Stream Key `channel1` — MediaMTX's docs recommend putting the path in the server URL.)
2. Add a **Media Source** pointing at a clip in `ai_engine/eval/clips/`, tick **Loop**. The Media Source exposes Restart/Pause/Play hotkeys for interactive control.
3. Click **Start Streaming**. MediaMTX auto-creates the path and republishes it as `rtsp://localhost:8554/channel1` — no AI engine changes needed.

**Limitation:** one OBS instance publishes exactly one stream. Simulating all 5 channels via OBS needs 5 OBS instances/profiles or the `obs-multi-rtmp` plugin — use OBS for an interactive demo of one or two channels, and Method 1 for bulk background simulation.

MediaMTX's default ports: RTSP `8554`, RTMP `1935`, HLS `8888`, WebRTC `8889`, SRT `8890`.

#### Obtaining the clips

`.gitignore` excludes `*.mp4`, so no video ships in the repo — a fresh clone can't run the simulation until you add some. They live in **one place**: `ai_engine/eval/clips/`, which is also where the evaluation harness and the `-m clips` tests look.

Populate it from the frozen research package:

```bash
cp ai_engine/adas_transfer/clips/*.mp4 ai_engine/eval/clips/
```

See [`ai_engine/eval/README.md`](ai_engine/eval/README.md) for what the 17 clips are and which ones the measured baseline expects to fire.

**The clips are test-only, permanently.** They carry no public licence and show identifiable people, vehicles and locations. Never publish them, never train on them, and never use their ordinary-traffic frames as negatives.

> **Historical note.** Earlier revisions of this README described a second directory, `ai_engine/sample_vids/`, with five differently-named clips and a `TODO` where its download link should have been. That directory never had a documented source, four of its five filenames existed nowhere, and both `mediamtx.yml` and `start-sim.ps1` pointed at it — so the "default, recommended" path could not work on any machine. It has been retired in favour of the single location above.

**4. Start the AI engine**

Requires `uv sync --extra ai` (see [Installation](#installation)). Run from the repo root:

```bash
uv run python ai_engine/main.py
```

The engine loads `ai_engine/epoch50.pt` directly. There is no longer a `best.engine`/`best.pt` pair or a fallback between them — both files were removed when the detection core was ported, because `best.pt` lost checkpoint selection in all three training runs and `main.py` had been _preferring_ the stale TensorRT build of it.

Before running it on a new machine, calibrate:

```bash
uv run python ai_engine/capacity.py
```

This reports how many cameras the machine can carry at 10 and at 15 FPS and writes a gitignored `machine_profile.json`. See [`ai_engine/eval/README.md`](ai_engine/eval/README.md).

#### Cameras start paused after seeding — this is deliberate

`reseed_dev.py` seeds sample alerts across every detection status, and any camera with an open (`Unverified` or `Ongoing`) alert is **self-blindfolded** — `desired_ai_state = Paused, reason = incident`. On a freshly seeded database that is _every_ camera.

**That is the self-blindfold invariant working correctly, not a bug.** An unresolved incident means the camera should not be re-alerting on the same scene, and it means the operator decides when each camera goes live rather than being flooded the moment the engine starts.

The only catch is discoverability: the engine reports `Connected` and then deliberately runs no inference, so it can look broken. The log shows repeated `Stream dropped ... while paused` rather than anything about detection. That is what to expect.

Clear an alert to release its camera — resolve or dismiss it in the dashboard, which is also how you exercise the HITL workflow. To bring everything online at once for a demo:

```bash
uv run python -c "import sqlite3; d=sqlite3.connect('adas.db'); d.execute(\"UPDATE detection_log SET detection_status='Resolved' WHERE detection_status IN ('Unverified','Ongoing')\"); d.execute(\"UPDATE camera SET desired_ai_state='Active', desired_state_reason=NULL WHERE is_active=1\"); d.commit()"
```

Within a few seconds the engine logs `Resuming AI ingestion` and starts alerting.

#### Other things worth knowing on a first run

- **Start the backend first.** The engine holds no camera configuration of its own — it heartbeats the backend and is told which cameras exist and where to reach them. It cannot run standalone.
- **`RTSP_URL_TEMPLATE` changes need a backend restart.** Settings load once at startup.
- **`UnicodeEncodeError` starting the backend on Windows.** The FastAPI CLI prints an emoji and the console codepage cannot encode it; this bites when output is redirected to a file. Prefix with `PYTHONIOENCODING=utf-8`.
- **Only 5 RTSP channels exist** in both simulation configs, but `reseed_dev.py` seeds 6 cameras. The sixth has nothing to connect to and will sit reconnecting — deactivate it, or ignore it.

---

## Development Workflow

**Reset and seed the local database:**

```bash
uv run python backend/scripts/reseed_dev.py
```

Always use `uv run python`, never a bare `python` — the `python` on PATH may be a different, unpinned interpreter (e.g. a system install) rather than the project's pinned 3.12.13. This gives you a fresh DB with an admin account, **six cameras**, operator accounts, and sample alerts across all detection statuses. See [`backend/scripts/README.md`](backend/scripts/README.md) for the full script reference.

**This is a required first-run step, not just a reset.** Starting the backend creates the tables and an admin account but no cameras at all, so the AI engine has nothing to work with until you seed. See the [Quickstart](#quickstart--clone-to-first-detection) for where it belongs in the order.

**Run the test suite:**

```bash
uv run pytest
```

Tests use an in-memory SQLite database and never touch `adas.db`. For the full pre-push/pre-PR command reference (`pnpm check`, `pnpm full:check`, individual lint/format/typecheck scripts), see [CONTRIBUTING.md](CONTRIBUTING.md).

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
│  SQLite (WAL) · JWT auth · RBAC · WebSocket manager      │
│                                                          │
│  /api/internal/*  ← AI engine only                       │
│  /api/alerts/*    ← HITL workflow (confirm/dismiss/resolve) │
│  /api/cameras/*   ← Camera management                    │
│  /api/users/*     ← User management (Admin only)         │
│  /ws/alerts       ← Real-time push to dashboard          │
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

---

## What Is Not Yet Implemented

- `backend/app/api/routes/system.py` — hardware telemetry (CPU, GPU, RAM, temperature) endpoints (intentional 0-byte placeholder)
- `backend/app/core/monitor.py` — background process that polls hardware metrics and writes to `sys_health_raw` (intentional 0-byte placeholder)
- `backend/scripts/daily_restart.sh` — scheduled nightly restart script (intentional 0-byte placeholder)

`backend/app/api/routes/analytics.py` is implemented (dashboard KPIs, accident frequency and peak-time charts) with a full pytest suite — it used to be listed here as planned, which was stale.

---

## Project Team

Enjey Kashlee M. Alonzo · Sebastian Angelo T. Meer · Daniel Luis P. Sahagun · Jhon Paulo H. Tenorio

De La Salle Lipa — Bachelor of Science in Information Technology, College of Information Technology and Engineering, April 2026
