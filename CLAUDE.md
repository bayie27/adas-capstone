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
| Run frontend                      | `pnpm --filter frontend dev`                                           |
| Run AI engine                     | `uv run python ai_engine/main.py` (needs `--extra ai`)                 |
| Reset + seed dev DB               | `uv run python backend/scripts/reseed_dev.py`                          |
| Backend tests (targeted)          | `uv run pytest backend/tests/test_alerts.py`                           |
| Backend tests (full, parallel)    | `uv run pytest -n auto`                                                |
| Frontend tests                    | `pnpm --filter frontend test:run`                                      |
| Full pre-push gate                | `pnpm check`                                                           |
| Full pre-PR gate                  | `pnpm full:check` (adds build + E2E)                                   |

Script reference, migration workflow, and CI jobs: [CONTRIBUTING.md](CONTRIBUTING.md).

## Live Google Drive resources

These are the team's shared, live artifacts. Treat them separately from local repository files
and verify their current state before relying on or changing them.

| Resource                           | Link                                                                                                                                            |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| Capstone defense document          | [Group 7 Defense Document](https://docs.google.com/document/d/1MkTrdBPrrXpw8JGC4xrS475wbF7Yn-9YCaXIN-xd0aw/edit)                                |
| Test Execution and Validation Plan | [Capstone Test Execution and Validation](https://docs.google.com/document/d/1EAoDetxkq6a3gzihU4iqp8pEXm4LcXfxmb8p5bCnBow/edit)                  |
| Test execution tracker             | [ADAS Test Execution Tracker](https://docs.google.com/spreadsheets/d/1yX-asNF-jsEZwIVSGFDvKyjF0Frh4IjWLY0Svfe82vU/edit?gid=3000003#gid=3000003) |
| Test evidence library              | [ADAS Test Evidence](https://drive.google.com/drive/folders/1oqXolcjA7Aeu_hTSbg7aH7-UX_gbc8a2)                                                  |

## Gotchas

The constraints below define behavior and structure routine changes must preserve. They do not require confirmation for work that preserves them. Investigate referenced code and tests independently. If the requested outcome requires changing a protected constraint, explain the specific conflict and propose that change for review; continue unaffected work.

- **Run everything from the repo root.** The FastAPI CLI injects `backend/` into `sys.path` itself (no `backend/__init__.py`); `ai_engine` is not a package and uses flat `from config import ...` imports that rely on `ai_engine/` being the running script's own directory.
- **Always `uv run python`, never bare `python`** — PATH `python` is 3.14, the project is pinned to 3.12.13, and a bare invocation silently uses the wrong interpreter.
- **`DATABASE_URL` resolves to an absolute path under the repo root** regardless of CWD (see the field validator in `backend/app/core/config.py`). Don't reintroduce CWD-relative DB path logic.
- **Schema changes use Alembic.** Before schema-affecting model changes, read CONTRIBUTING.md’s "Database migrations", generate and inspect the migration, and verify it against disposable databases. Complete this preparation within the authorized implementation task; "reviewed" does not require permission before generating or testing it. Preserve applicable human review before deployment. `create_all()` is permitted only in isolated test fixtures and the existing disposable schema-comparison verifier, never to provision or repair an application database.
- **`UtcDateTime`** (`app/core/types.py`) is the only type used for a stored timestamp anywhere in this schema — plain `DateTime(timezone=True)` does not survive SQLite. It raises loudly when a naive `datetime` reaches the DB layer instead of silently corrupting it; `datetime.now(UTC)` always.
- **Services layer**: business logic lives in `backend/app/services/*.py`, not inline in route handlers. Routes parse/authorize/call a service/serialize; the service owns the transaction and the domain rules.
- **Every audited state change is one transaction.** The primary action and its `audit_log` rows commit together; if the audit insert fails, the action rolls back. A `denied`/`failure` row is written in a separate short transaction _after_ that rollback. Don't add a state-mutating route that bypasses the audit-aware transaction helpers in `app/services/audit.py`.
- **Auth is an `HttpOnly` cookie, not a bearer token** — no session credential in JS-reachable storage; `withCredentials: true` and the browser attaches it, including on the WebSocket handshake. Session validation (`app/api/dependencies.py`) reads the process-global `app.core.config.settings` singleton, so tests that build an isolated `Settings` must patch that global rather than just passing their instance around (see `internal_headers()` in `backend/tests/conftest.py`).
- **`ux_detection_open_camera`** is a partial unique index (`WHERE detection_status IN ('Unverified','Ongoing')`) enforcing "at most one open incident per camera" at the database level, not just in Python. Anything that bulk-seeds `detection_log` rows must respect it — see `_enforce_open_camera_limit` in `backend/scripts/seed_dev_data.py`.
- **`routes/system.py` (unauthenticated `/healthz/*`), `routes/system_health.py` (telemetry), and `routes/maintenance.py` (backup/restore) are three routers by design**, so those packages evolve without touching one file. Don't consolidate them.
- **Model loading:** default to `ai_engine/epoch50.pt`. `AI_MODEL_PATH` resolves from the repo root, must exist, and is logged at startup. Preserve explicit failure: no format fallback or automatic engine export. `capacity.py --model` measures an explicitly selected artifact. See `ai_engine/docs/port-handover.md` for background.
- **TensorRT:** preserve the `<11` pin, NVIDIA index, and all four direct package declarations. Read the evidence in `pyproject.toml` before changing this toolchain.
- **`capacity.py` is an optional inference-only diagnostic.** It times batched detector inference and prints a rough 15/10 FPS estimate. It does not start RTSP streams, MediaMTX, or ffmpeg; write a report; or affect production, which always schedules at its fixed 15 FPS target.
- **Detection confidence:** preserve `DETECTOR_CONF = 0.15`; precision is controlled by temporal accumulation. Threshold changes require a separately reviewed proposal supported by evaluation evidence.
- **`ai_engine/accumulate.py` must not drift in behaviour.** It is formatted and linted normally — byte-identity was deliberately abandoned as the wrong guarantee — but `test_accumulate.py` asserts it emits events identical to the frozen reference. Don't "tighten" its two `zip(..., strict=False)` calls: the reference truncates, and `strict=True` would raise instead.
- **There are four accumulator reset seams, not three.** Reconnect, resume and restart all bump `camera.py`'s `segment_id`; the fourth is a long frame gap (`config.MAX_FRAME_GAP_SECONDS`), which carries no bump because the stream never dropped. Removing it lets a single frame fire an alert with no corroboration — see `ai_engine/docs/port-handover.md`.
- **`ai_engine/adas_transfer/` is frozen** — excluded from Ruff and Prettier. It is the reference the parity gate diffs against; never edit or reformat it.
- **Ruff is configured to skip `*.md`** — it reformats fenced Python blocks inside Markdown, which would rewrite untracked working docs at the repo root. Don't remove that exclusion.

## Domain rules

- **The self-blindfold pattern**: when the AI engine detects a collision it immediately pauses its own ingestion for that camera; the backend mirrors this by marking the camera `Paused` and broadcasting over WebSocket before any operator acts. Alert-handling code must preserve that ordering.
- **The HITL state machine**: `Unverified → Ongoing → Cleared` (true positive), `Unverified → Dismissed` (false positive, 60s cooldown), `Ongoing → Dismissed` (human correction, resumes immediately). The backend guards against the AI engine overwriting operator-driven pause states — don't loosen those guards without understanding why they're there.

## Conventions

- **Python**: Ruff for both lint and format (88 cols, py312 target). No Black/flake8/isort. Absolute `app.*` imports in the backend, not relative.
- **TypeScript**: Prettier with `semi: false` (existing house style). ESLint with `eslint-config-prettier` last so the two never fight.
- **Commits**: Conventional Commits, enforced by commitlint on `commit-msg`.
- **The stack is already opinionated** — reach for what's there before adding a dependency: TanStack Query (server state), Zustand (client state), SQLModel (persistence), Recharts (charts). Check a library's docs and types before concluding it can't do something.

## Testing policy

Test the behavior changed without chasing a coverage percentage. Keep frontend coverage focused: add a component or integration test when it is the smallest reliable way to verify the affected interaction, boundary, race, or failure path. Do not build exhaustive coverage of unrelated components. For prose-only changes, check formatting and references; run generators when their inputs or output text change.

"Don't overdo it" means not re-testing the same happy path from five angles. It is **not** permission to skip boundaries, races, failure paths, and hostile input, which is where a system that demos perfectly falls over in production — those are in scope beyond the paper's 82 test cases. This is a rule about **what gets asserted**, not about how often the whole suite gets re-run — for that, see the verification policy below.

## Verification policy

- **Run the narrowest test scope that covers the change.** One service or route means `uv run pytest backend/tests/test_<area>.py`, or `-k <pattern>` for a single case. Use the full suite (`uv run pytest -n auto`) for cross-cutting changes such as `backend/app/models/`, `backend/app/core/`, `conftest.py`, or the app factory. Do not run a separate full backend suite merely because a PR is next; `pnpm full:check` already includes it.
- **When a push is already authorized, let `.husky/pre-push` run `pnpm check`; do not run it manually beforehand.** This rule does not authorize a push. For local work, use the narrowest relevant checks.
- **`pnpm full:check` is a required pre-PR gate, not a per-change gate.** It includes checks, a production build, and the Chromium E2E project using real backend and frontend servers. CI runs the corresponding checks on PRs.
- **Do not add confirmation runs for passing suites.** Re-run after relevant changes or to investigate a suspected flake. Required lifecycle gates still run at their designated point even when they overlap earlier targeted checks.
- **Separate task failures from baseline failures.** Investigate whether the change caused a failure, including in untouched files. Fix task-related failures and continue independent work while investigating blockers. Report unrelated failures with evidence; do not silently broaden the task to repair them. State which checks passed, failed, or could not run. An unavailable check is not a pass, and required landing gates remain unsatisfied until resolved.
