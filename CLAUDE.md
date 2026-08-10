# ADAS Capstone

Intelligent Real-Time Road Accident Detection & Alert System — a 3-component system: a **Python AI engine** (YOLO inference over RTSP camera feeds), a **FastAPI backend** (DB, HITL alert workflow, auth), and a **React frontend** (operator dashboard). AI engine → backend over an HTTP webhook (`INTERNAL_API_KEY`-authenticated); backend → frontend over WebSocket (`/ws/alerts`) for real-time pushes; frontend → backend over REST for everything else.

## Commands

| Task                              | Command                                                |
| --------------------------------- | ------------------------------------------------------ |
| Install (backend only)            | `uv sync`                                              |
| Install (backend + AI engine)     | `uv sync --extra ai`                                   |
| Install (frontend + root tooling) | `pnpm install` (repo root — activates git hooks)       |
| Run backend                       | `uv run fastapi dev backend/app/main.py`               |
| Run frontend                      | `cd frontend && pnpm dev`                              |
| Run AI engine                     | `uv run python ai_engine/main.py` (needs `--extra ai`) |
| Reset + seed dev DB               | `uv run python backend/scripts/reseed_dev.py`          |
| Backend tests                     | `uv run pytest`                                        |
| Frontend tests                    | `pnpm --filter frontend test:run`                      |
| Full pre-push gate                | `pnpm check`                                           |
| Full pre-PR gate                  | `pnpm full:check` (adds build + E2E)                   |

Full script reference: [CONTRIBUTING.md](CONTRIBUTING.md).

## Hard-won gotchas

- **Run everything from the repo root**, by convention. The FastAPI CLI injects `backend/` into `sys.path` itself (no `backend/__init__.py`); `ai_engine` is not a package and uses flat `from config import ...`-style imports that rely on `ai_engine/` being the running script's own directory.
- **`python` on PATH is 3.14; the project is pinned to 3.12.13.** Always `uv run python`, never bare `python` — a bare invocation silently uses the wrong interpreter.
- **`DATABASE_URL` resolves to an absolute path under the repo root** regardless of CWD (see `backend/app/core/config.py`'s field validator). Don't reintroduce CWD-relative DB path logic.
- **`ai_engine/best.engine` is GPU/driver/TensorRT-version-specific** and won't load on a different machine. `ai_engine/main.py` catches the load failure and falls back to portable `ai_engine/best.pt` automatically — that fallback path is intentional, not a bug to "fix".
- **The self-blindfold pattern**: when the AI engine detects a collision, it immediately pauses its own ingestion for that camera; the backend mirrors this by marking the camera `Paused` and broadcasting over WebSocket before any operator acts. Alert-handling code must preserve this ordering.
- **The HITL state machine**: `Unverified → Ongoing → Resolved` (true positive) or `Unverified → Dismissed` (false positive, 60s cooldown) or `Ongoing → Dismissed` (human correction, resumes immediately). The backend guards against the AI engine overwriting operator-driven pause states — don't loosen those guards without understanding why they're there.
- **`backend/app/core/monitor.py`, `backend/app/api/routes/system.py`, and `backend/scripts/daily_restart.sh` are fully implemented**, not the 0-byte placeholders they used to be. `monitor.py` (P5) is the system-health sampler/rollup/pruning logic; `routes/system.py` (P1) holds the unauthenticated `/healthz/live` and `/healthz/ready` probes, with the authenticated telemetry split into its own `routes/system_health.py` (P5) and backup/restore into `routes/maintenance.py` (P7) — three separate router files by design, so P5 and P7 can evolve without touching the same file; do not consolidate them. `daily_restart.sh` (P7) drives the 3 AM restart window.
- **Reset the dev DB via Alembic now, not by deleting the file and calling `create_all()`.** `backend/scripts/reset_db.py` / `reseed_dev.py` still work the same from the outside, but they now provision schema by running `alembic upgrade head` under the hood (`app/core/migrations.py::check_schema_revision`'s development auto-bootstrap path) — `SQLModel.metadata.create_all()` against a real file is gone from that path entirely, reserved only for the fast in-memory unit-test fixture in `backend/tests/conftest.py`. See `CONTRIBUTING.md`'s "Database migrations" section before touching a model.
- **Services layer**: business logic lives in `backend/app/services/*.py` (incidents, cameras, snoozes, audit, filters, realtime, reports, ...), not inline in route handlers. Routes parse/authorize/call a service/serialize; the service owns the transaction and the domain rules.
- **`UtcDateTime`** (`app/core/types.py`) is the only SQLAlchemy type used for a stored timestamp anywhere in this schema — plain `DateTime(timezone=True)` does not survive SQLite. It raises loudly on a naive `datetime` reaching the DB layer rather than silently corrupting it; `datetime.now(UTC)` always, never `datetime.now()`.
- **Auth is an `HttpOnly` cookie, not a bearer token.** The frontend never stores a session credential in JS-reachable storage; `withCredentials: true` on the API client and the browser attaches the cookie automatically, including on the WebSocket handshake. Session validation (`app/api/dependencies.py`) reads the process-global `app.core.config.settings` singleton directly rather than a per-request `Settings` instance — tests that build an isolated `Settings` for internal/API-key checks need to patch that same global, not just pass their instance around (see `backend/tests/conftest.py`'s `internal_headers()` and `backend/tests/perf/conftest.py`'s copy of the same workaround).
- **Every audited state change is one transaction.** A primary action (an incident transition, a camera update, a user edit, ...) and its `audit_log` row(s) commit together; if the audit insert fails, the primary action rolls back. A `denied`/`failure` audit row is written in a separate short transaction _after_ the primary one has already rolled back. Don't add a route that mutates state without going through the shared audit-aware transaction helpers in `app/services/audit.py`.
- **`ux_detection_open_camera`** is the partial unique index (`WHERE detection_status IN ('Unverified','Ongoing')`) that enforces "at most one open incident per camera" at the database level, not just in Python. Any code that seeds or bulk-generates `detection_log` rows (dev seed scripts, perf fixtures) must respect it or the insert fails — see `backend/scripts/seed_dev_data.py`'s `_enforce_open_camera_limit` for the bulk-row pattern.
- **Ruff is configured to skip Markdown** (`.md` files) — it reformats fenced Python code blocks inside Markdown by default, which would touch untracked working docs at the repo root. Don't remove that exclusion.

## Conventions

- **Python**: Ruff for both lint and format (88 cols, py312 target). No Black/flake8/isort. Absolute `app.*` imports in the backend (not relative).
- **TypeScript**: Prettier (`semi: false` — the codebase's existing house style, no semicolons). ESLint with `eslint-config-prettier` last so the two never fight.
- **Commits**: Conventional Commits, enforced by commitlint on `commit-msg`.
- **Stack is already opinionated** — reach for what's already there before adding a dependency: TanStack Query for server state, Zustand for client state, SQLModel for persistence, Recharts for charts.

## Testing policy

Test when it's needed, don't overdo it. The backend has real pytest coverage (routes, HITL workflow, auth). Frontend coverage is deliberately minimal — a handful of smoke tests on pure utils and simple presentational components, not exhaustive component/integration coverage. Don't chase a coverage number.

"Don't overdo it" is about not re-testing the same happy path from five angles — it is not permission to skip boundaries, races, failure paths, and hostile input, which is where a system that demos perfectly falls over in production. Those categories are explicitly in scope even beyond the paper's 82 test cases; see `be_plan/14_EDGE_CASES.md` for the cross-cutting register every package is walked against before it's called done, and `be_plan/TRACEABILITY.md` for how each paper test case's evidence is tracked.

## Dependencies

Prefer established, well-maintained libraries when they reduce overall complexity or improve reliability. Lean on the dependencies already in the project before writing your own implementation or adding packages. Do not assume a library lacks a capability without checking its documentation and types.
