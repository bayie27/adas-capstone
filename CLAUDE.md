# ADAS Capstone

Intelligent Real-Time Road Accident Detection & Alert System. Three components: a **Python AI engine** (YOLO over RTSP feeds), a **FastAPI backend** (DB, HITL alert workflow, auth), and a **React frontend** (operator dashboard). AI engine → backend over an HTTP webhook (`INTERNAL_API_KEY`-authenticated); backend → frontend over WebSocket (`/ws/alerts`); frontend → backend over REST for everything else.

## Commands

| Task                              | Command                                                                |
| --------------------------------- | ---------------------------------------------------------------------- |
| Install (backend only)            | `uv sync`                                                              |
| Install (backend + AI engine)     | `uv sync --extra ai` (`--extra ai-cpu` without a GPU)                  |
| Install (frontend + root tooling) | `pnpm install` (repo root — activates git hooks)                       |
| Start dev stack                   | `pwsh -File scripts/start-dev.ps1`                                     |
| Start LAN/TLS demo stack          | `pwsh -File scripts/start-dev.ps1 -Lan` ([LAN_SETUP.md](LAN_SETUP.md)) |
| Run backend                       | `uv run fastapi dev backend/app/main.py`                               |
| Run frontend                      | `cd frontend && pnpm dev`                                              |
| Run AI engine                     | `uv run python ai_engine/main.py` (needs `--extra ai`)                 |
| Reset + seed dev DB               | `uv run python backend/scripts/reseed_dev.py`                          |
| Backend tests (targeted)          | `uv run pytest backend/tests/test_alerts.py`                           |
| Backend tests (full, parallel)    | `uv run pytest -n auto`                                                |
| Frontend tests                    | `pnpm --filter frontend test:run`                                      |
| Full pre-push gate                | `pnpm check`                                                           |
| Full pre-PR gate                  | `pnpm full:check` (adds build + E2E)                                   |

Script reference, migration workflow, and CI jobs: [CONTRIBUTING.md](CONTRIBUTING.md).

## Gotchas

- **Run everything from the repo root.** The FastAPI CLI injects `backend/` into `sys.path` itself (no `backend/__init__.py`); `ai_engine` is not a package and uses flat `from config import ...` imports that rely on `ai_engine/` being the running script's own directory.
- **Always `uv run python`, never bare `python`** — PATH `python` is 3.14, the project is pinned to 3.12.13, and a bare invocation silently uses the wrong interpreter.
- **`DATABASE_URL` resolves to an absolute path under the repo root** regardless of CWD (see the field validator in `backend/app/core/config.py`). Don't reintroduce CWD-relative DB path logic.
- **Schema changes go through a reviewed Alembic migration**, never `SQLModel.metadata.create_all()` against a real file — that's reserved for the in-memory fixture in `backend/tests/conftest.py`. `reset_db.py` / `reseed_dev.py` run `alembic upgrade head` under the hood. Read CONTRIBUTING.md's "Database migrations" before touching a model: SQLite autogenerate silently misses partial indexes, expression indexes, and anything attached via `after_create`.
- **`UtcDateTime`** (`app/core/types.py`) is the only type used for a stored timestamp anywhere in this schema — plain `DateTime(timezone=True)` does not survive SQLite. It raises loudly when a naive `datetime` reaches the DB layer instead of silently corrupting it; `datetime.now(UTC)` always.
- **Services layer**: business logic lives in `backend/app/services/*.py`, not inline in route handlers. Routes parse/authorize/call a service/serialize; the service owns the transaction and the domain rules.
- **Every audited state change is one transaction.** The primary action and its `audit_log` rows commit together; if the audit insert fails, the action rolls back. A `denied`/`failure` row is written in a separate short transaction _after_ that rollback. Don't add a state-mutating route that bypasses the audit-aware transaction helpers in `app/services/audit.py`.
- **Auth is an `HttpOnly` cookie, not a bearer token** — no session credential in JS-reachable storage; `withCredentials: true` and the browser attaches it, including on the WebSocket handshake. Session validation (`app/api/dependencies.py`) reads the process-global `app.core.config.settings` singleton, so tests that build an isolated `Settings` must patch that global rather than just passing their instance around (see `internal_headers()` in `backend/tests/conftest.py`).
- **`ux_detection_open_camera`** is a partial unique index (`WHERE detection_status IN ('Unverified','Ongoing')`) enforcing "at most one open incident per camera" at the database level, not just in Python. Anything that bulk-seeds `detection_log` rows must respect it — see `_enforce_open_camera_limit` in `backend/scripts/seed_dev_data.py`.
- **`routes/system.py` (unauthenticated `/healthz/*`), `routes/system_health.py` (telemetry), and `routes/maintenance.py` (backup/restore) are three routers by design**, so those packages evolve without touching one file. Don't consolidate them.
- **The default weights are `ai_engine/epoch50.pt`, loaded directly, with no fallback.** `best.pt` and `best.engine` were deleted during the detection core port — `best.pt` lost checkpoint selection in all three training runs and `main.py` had been _preferring_ a stale TensorRT build of it, silently running the wrong model. **`AI_MODEL_PATH` in `.env` selects a different artifact** (a TensorRT engine or ONNX export); it resolves from the repo root, is **fatal if missing**, and `main.py` prints which artifact loaded on every start. Don't reintroduce an `.engine` → `.pt` fallback — the invisibility was the bug, not the format. Nothing builds an engine automatically; export is out of band and `capacity.py --model` measures one.
- **TensorRT is pinned `<11` and sourced from NVIDIA's index, not PyPI.** Both constraints are load-bearing and documented with evidence in `pyproject.toml`: PyPI's `tensorrt-cu13-libs` is a stub whose PEP 517 build downloads gigabytes from NVIDIA with no timeout and hung twice, and ultralytics 8.4.41 calls `NetworkDefinitionCreationFlag.EXPLICIT_BATCH`, which TensorRT 11 removed. All four tensorrt packages must stay declared directly — `[tool.uv.sources]` binds only the project's own dependencies, so pinning the top level alone lets the transitive `-libs` fall back to the PyPI stub.
- **`ai_engine/machine_profile.json` is machine-specific and gitignored.** Produced by `uv run python ai_engine/capacity.py`, which reports how many cameras the machine can carry at 10 and at 15 FPS. Absence is not an error — the engine falls back to a conservative one camera and says so on startup.
- **`DETECTOR_CONF = 0.15` is a closed lever, not a tuning knob.** False positives score _higher_ than genuine detections (0.869/0.844/0.649 versus 0.536/0.459/0.741), so any threshold that removes false alarms deletes real crashes first. Precision comes from the temporal accumulator, not from the threshold.
- **`ai_engine/accumulate.py` must not drift in behaviour.** It is formatted and linted normally — byte-identity was deliberately abandoned as the wrong guarantee — but `test_accumulate.py` asserts it emits events identical to the frozen reference. Don't "tighten" its two `zip(..., strict=False)` calls: the reference truncates, and `strict=True` would raise instead.
- **There are four accumulator reset seams, not three.** Reconnect, resume and restart all bump `camera.py`'s `segment_id`; the fourth is a long frame gap (`config.MAX_FRAME_GAP_SECONDS`), which carries no bump because the stream never dropped. Removing it lets a single frame fire an alert with no corroboration — see `ai_engine/docs/port-handover.md`.
- **`ai_engine/adas_transfer/` is frozen** — excluded from Ruff and Prettier. It is the reference the parity gate diffs against; never edit or reformat it.
- **Ruff is configured to skip `*.md`** — it reformats fenced Python blocks inside Markdown, which would rewrite untracked working docs at the repo root. Don't remove that exclusion.

## Domain rules

- **The self-blindfold pattern**: when the AI engine detects a collision it immediately pauses its own ingestion for that camera; the backend mirrors this by marking the camera `Paused` and broadcasting over WebSocket before any operator acts. Alert-handling code must preserve that ordering.
- **The HITL state machine**: `Unverified → Ongoing → Resolved` (true positive), `Unverified → Dismissed` (false positive, 60s cooldown), `Ongoing → Dismissed` (human correction, resumes immediately). The backend guards against the AI engine overwriting operator-driven pause states — don't loosen those guards without understanding why they're there.

## Conventions

- **Python**: Ruff for both lint and format (88 cols, py312 target). No Black/flake8/isort. Absolute `app.*` imports in the backend, not relative.
- **TypeScript**: Prettier with `semi: false` (existing house style). ESLint with `eslint-config-prettier` last so the two never fight.
- **Commits**: Conventional Commits, enforced by commitlint on `commit-msg`.
- **The stack is already opinionated** — reach for what's there before adding a dependency: TanStack Query (server state), Zustand (client state), SQLModel (persistence), Recharts (charts). Check a library's docs and types before concluding it can't do something.

## Testing policy

Test when it's needed, don't overdo it. The backend has real pytest coverage (routes, HITL workflow, auth). Frontend coverage is deliberately minimal — smoke tests on pure utils and simple presentational components, not exhaustive component/integration coverage. Don't chase a coverage number.

"Don't overdo it" means not re-testing the same happy path from five angles. It is **not** permission to skip boundaries, races, failure paths, and hostile input, which is where a system that demos perfectly falls over in production — those are in scope beyond the paper's 82 test cases. This is a rule about **what gets asserted**, not about how often the whole suite gets re-run — for that, see the verification policy below.

## Verification policy

- **Run the narrowest test scope that covers the change.** One service or route means `uv run pytest backend/tests/test_<area>.py`, or `-k <pattern>` for a single case. Reach for the full suite (`uv run pytest -n auto`) only when the change is genuinely cross-cutting — `app/models.py`, `app/core/`, `conftest.py`, the app factory — or right before opening a PR.
- **Never run `pnpm check` manually before pushing.** `.husky/pre-push` already runs it on every push. Running it first just doubles the wait for identical signal — if you want the gate, push.
- **`pnpm full:check` is a pre-PR gate, not a per-change gate.** It boots a real FastAPI server and a Vite dev server to run one Playwright spec. CI runs the same thing on every PR.
- **Don't re-run a suite to "confirm" a passing result.** Re-run only after changing something, or to chase a suspected flake.
