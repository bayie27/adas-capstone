# ADAS — Intelligent Real-Time Road Accident Detection & Alert System

> Last updated: August 12, 2026

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
├── mediamtx.yml             # Camera simulation — see "Simulate camera streams"
├── scripts/start-sim.ps1    # Preflighted wrapper around `mediamtx mediamtx.yml`
├── scripts/adas-maintenance.ps1  # Windows demo orchestrator for backup/restore/restart
├── scripts/register-maintenance-task.ps1  # Registers the Windows Scheduled Task for the daily restart (NFR-16)
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
- **NVIDIA GPU + CUDA** — needed for detection at a usable frame rate. The engine runs without one (see `uv sync --extra ai-cpu` under [Installation](#installation)) and is useful that way for integration work, but a CPU-only machine is not a detection platform and no measured claim may come from it

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
production. Four storage roots are worth knowing about up front since
they're where the backend writes files outside the database:

| Setting         | Default                      | What lives there                                                                                                                                       |
| --------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `SNAPSHOT_ROOT` | `<repo>/ai_engine/snapshots` | Incident snapshot JPEGs, served only via the authenticated `GET /api/alerts/{log_id}/snapshot` — never a public static mount                           |
| `BACKUP_DIR`    | `<repo>/var/backups`         | Verified online backups + `restore_state.json`                                                                                                         |
| `EXPORT_DIR`    | `<repo>/var/exports`         | Generated CSV/PDF/ZIP export artifacts (expire after `EXPORT_ARTIFACT_TTL_HOURS`)                                                                      |
| `LOG_DIR`       | `<repo>/var/log`             | `scripts\adas-maintenance.ps1`'s transcripts, per-component stdout/stderr, and `maintenance-runs.jsonl` (read by `GET /api/system/maintenance/status`) |

`var/` is gitignored — safe scratch space for local backups, exports, and
migration testing.

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

TensorRT is a further optional extra for NVIDIA machines that want a faster inference backend. It is **not** required — the engine runs on the PyTorch checkpoint either way, and the GPU is used regardless, since CUDA comes from torch:

```bash
uv sync --extra ai --extra ai-trt
```

An engine built from it is selected with `AI_MODEL_PATH` (see [Start the AI engine](#4-start-the-ai-engine)). It is tied to the GPU, driver and TensorRT version that built it, so it must be built on the machine that will run it and is never committed.

**Node dependencies (frontend + root tooling):**

Run from the **repo root**, not `frontend/` — this is a pnpm workspace, and running it at the root is also what activates the git hooks (see [CONTRIBUTING.md](CONTRIBUTING.md)):

```bash
pnpm install
```

---

## Running the System

The system has two ways to run it: a **one-command launcher** for everyday use, and a **manual, component-by-component path** for when you need one piece in isolation or the launcher doesn't fit your setup. Both end up in the same place. Read the launcher section even if you plan to run things manually — it explains the dev panel, which is the fastest way to get a working demo without touching MediaMTX, ffmpeg, or a GPU at all.

**Run every command in this whole section from the repo root.** For the backend and frontend this is a convention rather than a hard requirement — the FastAPI CLI injects `backend/` into `sys.path` itself, and `DATABASE_URL` resolves to an absolute path under the repo root regardless of CWD — but the AI engine's `from config import ...`-style imports need `ai_engine/` to be the running script's own directory, which only `uv run python ai_engine/main.py` from the root gives it.

### The fast path: `scripts/start-dev.ps1`

```powershell
pwsh -File scripts/start-dev.ps1
```

No switches starts the everyday case — backend + frontend, each in its own titled window (`ADAS - Backend`, `ADAS - Frontend`, ...). `pnpm dev` at the repo root runs the identical command.

| Flag                | What it does                                                                                                                                                                                              |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `-Backend`          | `uv run fastapi dev backend/app/main.py`                                                                                                                                                                  |
| `-Frontend`         | `cd frontend && pnpm dev`                                                                                                                                                                                 |
| `-Sim`              | MediaMTX + one ffmpeg per channel, by delegating to `scripts/start-sim.ps1` (see [Simulate camera streams](#3-simulate-camera-streams-development))                                                       |
| `-Ai`               | The AI engine (`uv run python ai_engine/main.py`) — needs `uv sync --extra ai` and ideally a GPU (see [Start the AI engine](#4-start-the-ai-engine))                                                      |
| `-All`              | Shorthand for all four                                                                                                                                                                                    |
| `-Reseed <profile>` | Reseeds the dev DB **before** anything starts, via `backend/scripts/reseed_dev.py --profile <value>`. Fails the whole script (nothing starts) on a bad profile name — see [Seed profiles](#seed-profiles) |
| `-NoNewWindow`      | Runs a single requested component in the current terminal instead of a new window; errors if combined with more than one component                                                                        |

Preflights fail fast with an actionable message rather than a cryptic crash three steps later: missing `.env` (offers to copy `.env.example`), `uv`/`pnpm` not on PATH, missing `frontend/node_modules`, and — for `-Ai` — a reminder about `--extra ai`/GPU, that `ai_engine/epoch50.pt` has no fallback and is a hard failure if missing, and that a missing `machine_profile.json` is expected (not an error) until you run `ai_engine/capacity.py`.

Tear everything down with:

```powershell
pwsh -File scripts/stop-dev.ps1
```

Same flags, no flags stops everything. It resolves each process by the port it's actually listening on (8000/5173/8554), not by a stored PID or process name — `uv run fastapi dev` and `uv run python ai_engine/main.py` don't exec-replace themselves on Windows, so `uv` stays alive as a parent and the wrapper PID isn't the one holding the port. Stopping something that isn't running just says so; it's not an error, which is why running it with no arguments is a safe default when you don't remember exactly what you started.

Run `Get-Help scripts/start-dev.ps1 -Full` (or open the script) for the full comment-based help, or see [`dev_plan/04_PKG_launcher.md`](dev_plan/04_PKG_launcher.md) for the design rationale behind both scripts.

**A note on Windows PATH staleness.** If `start-dev.ps1` reports `pnpm not found on PATH` or `-Sim` reports `mediamtx not found on PATH` immediately after you've just installed one of them, the tool is almost always actually there — Windows snapshots `PATH` when a process starts, so a terminal (or terminal-hosting app) that was already open won't see a PATH change until it's restarted. Closing a tab isn't enough if you're in Windows Terminal or VS Code's integrated terminal — those cache the environment at the _application's_ launch, and every new tab inherits that same stale snapshot. Fully quit and relaunch the terminal application, not just the window.

### The dev panel — reseed, fire incidents, and switch accounts without restarting anything

Once the backend and frontend are up, log in at `http://localhost:5173` and press **`Ctrl+Shift+D`** (or click the small terminal icon bottom-right). This opens a drawer that talks to five backend routes under `/api/dev/*`, gated behind the `DEV_TOOLS_ENABLED` setting (on by default when `ENVIRONMENT=development`; an explicit `.env` value always wins, which is what lets it stay on for a LAN demo box running a production build). If the trigger doesn't appear, either the flag is off or the backend isn't reachable — it's a runtime probe against `GET /api/dev/status`, not a build-time flag, so it also works in a `pnpm build` bundle.

**Data — reseed without restarting the server.** This is the in-process equivalent of `reseed_dev.py`: it wipes every operational table, reseeds the chosen profile, and mints a fresh session cookie in the same response so you stay logged in — no restart, no re-login, and every other connected dashboard's WebSocket reconnects onto the new session automatically. See [Seed profiles](#seed-profiles) below for what each one contains.

**Simulate — fire a detection with no AI engine, RTSP feed, or GPU involved.** "Inject a detection" runs the exact same ingest path a real webhook from the AI engine would (`services/incidents.ingest_detection`) — the camera self-blindfolds, the WebSocket broadcasts to every connected dashboard, the alarm modal pops and the siren plays, all for real. Pick a camera ID or let it choose a free one, set a confidence, and watch the full HITL pipeline fire without touching MediaMTX or a GPU. "Make stale" / "Clear cooldown" push a camera's heartbeat state directly, for exercising the `Unresponsive` presentation or an operator's post-incident cooldown window on demand.

**Session — switch accounts instantly.** Click any seeded username to become that user immediately, no password, no page reload. This requires only _some_ existing authenticated session, by design — it's an account switcher for hopping between seeded demo accounts once you're in, not a way to authenticate without credentials in the first place.

Full endpoint reference and the reasoning behind each design choice: [`dev_plan/02_PKG_dev_api.md`](dev_plan/02_PKG_dev_api.md) and [`dev_plan/03_PKG_dev_panel.md`](dev_plan/03_PKG_dev_panel.md).

#### Seed profiles

Both `-Reseed <profile>` and the dev panel's Data section take one of these (also listed by `GET /api/dev/status`, and enforced by `reseed_dev.py --profile` itself, so an unrecognized name fails loudly rather than silently seeding the wrong thing):

| Profile     | What it seeds                                                                                                                                                                                                |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `demo`      | **Default.** A balanced dataset for manual testing and demos — 8 cameras, 7 users, 18 alerts across every detection status, 7 days of health history, 5 export jobs.                                         |
| `analytics` | Denser, chart-friendly data across 14 days — same camera/user roster as `demo`, 62 alerts, 30 days of health history.                                                                                        |
| `edge`      | Unusual workflow combinations and boundary values — confidence scores at 0.0/1.0, cameras mid-cooldown, disabled/soft-deleted accounts, every audit action at least once.                                    |
| `empty`     | Schema and the default admin account only. Nothing else — the first-run/empty-states case.                                                                                                                   |
| `perf`      | 100,000 incidents over ~18 months (NFR-08), for measuring query/export performance against a realistic dataset size. Slow (~30s) — both the launcher and the dev panel ask you to confirm before running it. |

Full seed-data reference, including exactly which audit actions and health-sample shapes each profile produces: [`backend/scripts/README.md`](backend/scripts/README.md).

### Quickstart — clone to first detection

The whole path, in order, using the fast path throughout.

**One-time, in this order:**

```bash
uv sync --extra ai                              # --extra ai-cpu if no NVIDIA GPU
pnpm install                                    # at the ROOT — this activates git hooks
cp .env.example .env                            # then fill in all 10 keys
```

Populate `ai_engine/eval/clips/` — no video ships in a clone. See [Obtaining the clips](#obtaining-the-clips).

```bash
uv run python ai_engine/capacity.py             # once per machine
```

**Then one command:**

```powershell
pwsh -File scripts/start-dev.ps1 -Reseed demo -All
```

This reseeds `demo` (which is the default profile, but stating it explicitly is clearer on a first run), then brings up all four components in the bring-up order MediaMTX → backend → frontend → AI engine. Log in at `http://localhost:5173` as `admin` with the `DEFAULT_ADMIN_PASSWORD` from your `.env`.

**What a working run looks like:** of `demo`'s 8 cameras, 5 sit on the simulation's real channels (`channel1`–`channel5`); the other 3 structurally can't (see [Camera and seed-data behaviour](#camera-and-seed-data-behaviour--what-to-expect) below). Of those 5: four alert within a loop or two of their clip, and **one stays silent** — it serves the crash-free negative-control clip, and a camera that never alerts is as much a result as one that does. The engine log reads:

```
[SYSTEM] Machine profile: 0 · capacity 8 camera(s) @ 15 FPS
[SYSTEM] Resuming AI ingestion for Channel 4...
[ALERT] Channel 4: accident detected (peak 0.76, 2.2s of evidence).
```

No GPU, or don't want to populate the clips yet? Drop `-Ai` (and `-Sim`) and use the dev panel's "Inject a detection" instead — it exercises the identical downstream pipeline (self-blindfold, WebSocket broadcast, alarm modal, siren) without either.

---

### Running components manually

The fast path above replaces everything in this subsection; use it when you want one component in isolation.

#### 1. Start the backend

```bash
uv run fastapi dev backend/app/main.py
```

API available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

#### 2. Start the frontend

```bash
cd frontend
pnpm dev
```

Dashboard available at `http://localhost:5173`.

#### 3. Simulate camera streams (development)

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

#### 4. Start the AI engine

Requires `uv sync --extra ai` (see [Installation](#installation)). Run from the repo root:

```bash
uv run python ai_engine/main.py
```

The engine loads `ai_engine/epoch50.pt` directly. There is no longer a `best.engine`/`best.pt` pair or a fallback between them — both files were removed when the detection core was ported, because `best.pt` lost checkpoint selection in all three training runs and `main.py` had been _preferring_ the stale TensorRT build of it.

To run a different build, set `AI_MODEL_PATH` in `.env` (see `.env.example`):

```bash
AI_MODEL_PATH=ai_engine/epoch50.engine
```

The lesson from `best.engine` is kept rather than undone: the path is **fatal if it does not exist** — never a silent fall back to the checkpoint — and `main.py` prints which artifact it loaded on every start. Relative paths resolve from the repo root, not the working directory.

Before running it on a new machine, calibrate:

```bash
uv run python ai_engine/capacity.py
```

This reports how many cameras the machine can carry at 10 and at 15 FPS and writes a gitignored `machine_profile.json`. Pass `--model ai_engine/epoch50.engine` to measure a built artifact instead of the checkpoint; the profile records whichever was benchmarked, and `main.py` warns at startup when that is not the one being loaded. See [`ai_engine/eval/README.md`](ai_engine/eval/README.md).

#### Camera and seed-data behaviour — what to expect

**A camera's connection/AI status is computed at read time, not stored.** `presented_statuses()` overrides whatever's in the database based on how long it's been since the camera last heartbeated: no heartbeat ever → `Reconnecting`; a heartbeat older than `HEARTBEAT_STALE_SECONDS` (10s by default) → `Unresponsive` for both dimensions, regardless of the stored value; a disabled camera is exempt and always shows its raw stored value. Heartbeats come from the AI engine while it's actively watching a stream — with `-Backend -Frontend` only (no `-Ai`), every seeded camera will drift to `Unresponsive` within about 10 seconds of being seeded, and that's the system correctly reporting "nothing is watching this camera," not a bug.

**Only 5 RTSP channels exist** in both simulation configs (`mediamtx.yml` and `start-sim.ps1`), but the `demo`/`analytics` camera roster has 8 entries. `channel1`–`channel5` map to the 5 cameras in the [clip table](#3-simulate-camera-streams-development) above; the other 3 — Dagatan Entry Cam, Silang Junction Cam, and the disabled/soft-deleted Retired Depot Cam — have no channel at all and will sit `Unresponsive`/`Disconnected` forever no matter how correctly everything else is configured. This isn't a bug to fix; it's a 5-clip simulation intentionally covering a larger camera roster so the UI has something realistic to show for a camera that's actually down.

**Self-blindfold: any camera with an open (`Unverified` or `Ongoing`) incident pauses itself.** This is deliberate — an unresolved incident means the camera shouldn't be re-alerting on the same scene, and it puts the operator in control of when a camera goes back online rather than the engine flooding them the moment it starts. `demo` and `analytics` seed a realistic mix of open and closed incidents (not every camera), so expect some — not necessarily all — of the 5 real-feed cameras to start paused. Resolve or dismiss the open incident in the dashboard (or via the dev panel) and that camera resumes within seconds. To force every seeded camera active at once for a demo:

```bash
uv run python -c "import sqlite3; d=sqlite3.connect('adas.db'); d.execute(\"UPDATE detection_log SET detection_status='Resolved' WHERE detection_status IN ('Unverified','Ongoing')\"); d.execute(\"UPDATE camera SET desired_ai_state='Active', desired_state_reason=NULL WHERE is_active=1\"); d.commit()"
```

The engine reports `Connected` on a paused camera and then deliberately runs no inference on it, so it can look broken if you don't know to expect `Stream dropped ... while paused` in its log instead of anything about detection.

#### Other things worth knowing on a first run

- **Start the backend first.** The engine holds no camera configuration of its own — it heartbeats the backend and is told which cameras exist and where to reach them. It cannot run standalone.
- **`RTSP_URL_TEMPLATE` changes need a backend restart.** Settings load once at startup.
- **`UnicodeEncodeError` starting the backend on Windows, running it manually.** The FastAPI CLI prints an emoji and the console codepage can't encode it; this bites when output is redirected to a file, or when launched from a Bash-flavoured shell. Prefix with `PYTHONUTF8=1` (or `PYTHONIOENCODING=utf-8`). `start-dev.ps1` sets this automatically for you — this only matters if you're running `uv run fastapi dev` by hand.

---

## Development Workflow

**Reset and seed the local database:**

```bash
uv run python backend/scripts/reseed_dev.py
```

Always use `uv run python`, never a bare `python` — the `python` on PATH may be a different, unpinned interpreter (e.g. a system install) rather than the project's pinned 3.12.13. This deletes the SQLite file and reseeds the `demo` profile by default (see [Seed profiles](#seed-profiles)) — an admin account, cameras, operator accounts, and sample alerts across all detection statuses. It cannot run while the backend holds the database file open; if you just need to switch profiles without stopping anything, use the dev panel's reseed instead (`Ctrl+Shift+D` in the running dashboard), which is the in-process equivalent. Schema is provisioned by running `alembic upgrade head` under the hood, not `CREATE TABLE`-equivalent metadata calls — see [CONTRIBUTING.md](CONTRIBUTING.md)'s "Database migrations" section before changing a model. See [`backend/scripts/README.md`](backend/scripts/README.md) for the full script reference.

**This is a required first-run step, not just a reset.** Starting the backend creates the tables and an admin account but no cameras at all, so the AI engine has nothing to work with until you seed. See the [Quickstart](#quickstart--clone-to-first-detection) for where it belongs in the order.

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

On Windows, `scripts\adas-maintenance.ps1` wraps the full backup/restore/restart lifecycle (stopping and restarting the backend/AI engine processes around the same Python maintenance core) — see that script's own header comment for every `-Action`. Every run is captured under `var\log\` (transcript, per-component stdout/stderr, and one JSON line per `-Action Restart` run in `maintenance-runs.jsonl`) instead of a console window that vanishes when closed.

**Automate the daily restart (NFR-16):**

```powershell
scripts\register-maintenance-task.ps1              # register (idempotent), reads MAINTENANCE_HOUR_LOCAL from .env
scripts\register-maintenance-task.ps1 -Verify       # show trigger, next/last run, last result
scripts\register-maintenance-task.ps1 -Unregister   # remove
```

Registers a Windows Scheduled Task (`\ADAS\DailyRestart`) that fires `adas-maintenance.ps1 -Action Restart` daily at the configured local hour. The daily _backup_ (NFR-18) needs no separate registration — it's an in-app APScheduler cron job (`app.main`, gated on `SCHEDULER_ENABLED`) that runs inside the backend process itself, with an hourly catch-up job and a startup due-check so a laptop that was off at 3 AM still gets that day's backup once it's back on.

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
