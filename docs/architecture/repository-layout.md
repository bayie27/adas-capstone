# Repository layout

```
adas-capstone/
├── ai_engine/
│   ├── main.py              # Entry point — wire-up only
│   ├── pipeline.py          # Fixed-cadence batched multi-camera tick loop
│   ├── detector.py          # Model ownership, grayscale, class filtering
│   ├── accumulate.py        # Temporal evidence accumulator (fires the event)
│   ├── gpu_camera.py        # Optional NVDEC stream reader
│   ├── gpu_preprocess.py    # GPU conversion and preprocessing
│   ├── frames.py            # Frame representations
│   ├── camera.py            # Threaded RTSP stream reader with auto-reconnect
│   ├── accident.py          # Event → annotated snapshot → outbox entry
│   ├── supervisor.py        # Reconciles engine state against the backend
│   ├── capacity.py          # Optional inference-only capacity diagnostic
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
│   │           ├── internal.py          # AI engine idempotent alert ingestion and heartbeat
│   │           ├── auth.py              # Login/logout (HttpOnly session cookie)
│   │           ├── cameras.py           # Camera CRUD and management
│   │           ├── alerts.py            # HITL workflow (confirm/dismiss/clear/snooze) + exports
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
├── e2e/                     # Playwright specs (local and CI; backend + frontend)
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

Shared guides live under `docs/`; historical plans live under `docs/archive/`. Component READMEs cover current details. See [architecture](README.md) and [operations](../operations/README.md).
