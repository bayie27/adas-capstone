# ADAS — Intelligent Real-Time Road Accident Detection & Alert System

> Last updated: April 26, 2026

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
│   ├── manager.py           # Accident detection logic and webhook dispatch
│   ├── config.py            # AI engine configuration (thresholds, endpoints)
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
│   │           ├── analytics.py         # (planned) Dashboard KPIs and charts
│   │           └── system.py            # (planned) System health telemetry
│   ├── scripts/             # Dev utilities — see backend/scripts/README.md
│   ├── tests/               # Pytest test suite
│   └── README.md            # Backend-specific setup and API reference
├── frontend/
│   ├── src/                 # React source (components, pages, hooks, stores)
│   ├── public/
│   ├── package.json
│   └── dashboard.html       # Standalone WebSocket alert feed (dev/debug only)
├── pyproject.toml
├── uv.lock
└── .python-version          # 3.12.13
```

---

## Prerequisites

- **Python 3.12.13** (pinned via `.python-version`)
- **uv** — fast Python package manager (`pip install uv` or see [uv docs](https://docs.astral.sh/uv/))
- **Node.js 18+** and **pnpm** — for the React frontend
- **ffmpeg** — required to broadcast local video files to the RTSP proxy during development
- **MediaMTX** — RTSP media server used to simulate the VMS in development ([download](https://github.com/bluenviron/mediamtx/releases))
- **NVIDIA GPU + CUDA** — required for TensorRT inference in production; CPU fallback works for development

---

## Environment Setup

Copy `.env.example` to `.env` in the repo root and fill in all values:

```env
# Security
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480

# Internal AI Webhook
INTERNAL_API_KEY=your-internal-api-key

# Database
DATABASE_URL=sqlite:///adas.db
DEFAULT_ADMIN_PASSWORD=ChangeMe123

# Dahua DSS Pro VMS (production only)
DSS_IP=192.168.1.100
DSS_PORT=80
DSS_USERNAME=admin
DSS_PASS=your-vms-password
```

---

## Installation

**Python dependencies (backend + AI engine):**

```bash
uv sync

**Frontend dependencies:**

```bash
cd frontend
pnpm install
```

---

## Running the System

All three components run in separate terminals.

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

Start MediaMTX, then broadcast the sample videos:

```bash
ffmpeg -re -stream_loop -1 -i "ai_engine\sample_vids\car_car.mp4" -c copy -rtsp_transport tcp -f rtsp rtsp://localhost:8554/channel1
ffmpeg -re -stream_loop -1 -i "ai_engine\sample_vids\car-motor-motor.mp4" -c copy -rtsp_transport tcp -f rtsp rtsp://localhost:8554/channel2
ffmpeg -re -stream_loop -1 -i "ai_engine\sample_vids\defour.mp4" -c copy -rtsp_transport tcp -f rtsp rtsp://localhost:8554/channel3
ffmpeg -re -stream_loop -1 -i "ai_engine\sample_vids\red-car-motorcycle.mp4" -c copy -rtsp_transport tcp -f rtsp rtsp://localhost:8554/channel4
ffmpeg -re -stream_loop -1 -i "ai_engine\sample_vids\motor-to-motor.mp4" -c copy -rtsp_transport tcp -f rtsp rtsp://localhost:8554/channel5
```

**4. Start the AI engine**

```bash
cd ai_engine
uv run python main.py
```

---

## Development Workflow

**Reset and seed the local database:**

```bash
python backend/scripts/reseed_dev.py
```

This gives you a fresh DB with an admin account, three cameras, and sample alerts across all detection statuses. See [`backend/scripts/README.md`](backend/scripts/README.md) for the full script reference.

**Run the test suite:**

```bash
uv run pytest
```

Tests use an in-memory SQLite database and never touch `adas.db`.

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

- `backend/app/api/routes/analytics.py` — dashboard KPIs, accident frequency charts, peak time charts
- `backend/app/api/routes/system.py` — hardware telemetry (CPU, GPU, RAM, temperature) endpoints
- `backend/app/core/monitor.py` — background process that polls hardware metrics and writes to `sys_health_raw`
- `backend/scripts/daily_restart.sh` — scheduled nightly restart script

---

## Project Team

Enjey Kashlee M. Alonzo · Sebastian Angelo T. Meer · Daniel Luis P. Sahagun · Jhon Paulo H. Tenorio

De La Salle Lipa — Bachelor of Science in Information Technology, College of Information Technology and Engineering, April 2026
