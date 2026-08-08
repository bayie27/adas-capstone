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
- **`backend/app/core/monitor.py`, `backend/app/api/routes/system.py`, and `backend/scripts/daily_restart.sh` are intentional 0-byte placeholders**, not accidentally-empty files. Don't "fix" them by deleting or stubbing them differently unless asked to actually implement the feature.
- **Ruff is configured to skip Markdown** (`.md` files) — it reformats fenced Python code blocks inside Markdown by default, which would touch untracked working docs at the repo root. Don't remove that exclusion.

## Conventions

- **Python**: Ruff for both lint and format (88 cols, py312 target). No Black/flake8/isort. Absolute `app.*` imports in the backend (not relative).
- **TypeScript**: Prettier (`semi: false` — the codebase's existing house style, no semicolons). ESLint with `eslint-config-prettier` last so the two never fight.
- **Commits**: Conventional Commits, enforced by commitlint on `commit-msg`.
- **Stack is already opinionated** — reach for what's already there before adding a dependency: TanStack Query for server state, Zustand for client state, SQLModel for persistence, Recharts for charts.

## Testing policy

Test when it's needed, don't overdo it. The backend has real pytest coverage (routes, HITL workflow, auth). Frontend coverage is deliberately minimal — a handful of smoke tests on pure utils and simple presentational components, not exhaustive component/integration coverage. Don't chase a coverage number.

## Dependencies

Prefer established, well-maintained libraries when they reduce overall complexity or improve reliability. Lean on the dependencies already in the project before writing your own implementation or adding packages. Do not assume a library lacks a capability without checking its documentation and types.
