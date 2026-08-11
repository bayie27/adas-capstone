# Package D — Dev Launcher Scripts

> **Blocked by:** nothing. **Runs in parallel with A/B/C.**
> **Branch:** `chore/dev-launcher` (create it off `main`).
> **Prerequisite reading:** [`00_OVERVIEW.md`](00_OVERVIEW.md) · `README.md` §Running the System ·
> `scripts/start-sim.ps1` (the shape to follow) · `be_audit/DEMO_TOPOLOGY.md` §5 (the real demo-day
> bring-up order)
> **Size:** S. Four steps.
> **Scope:** `scripts/`, root `package.json`, `README.md`, `CLAUDE.md`. **Nothing under
> `backend/`, `frontend/` or `ai_engine/`.**

## Why this package exists

There is no single command that starts this system. `README.md` §"Running the System" lists four
manual steps in four terminals, and a seed script makes five:

```
uv run fastapi dev backend/app/main.py
cd frontend && pnpm dev
mediamtx mediamtx.yml
uv run python ai_engine/main.py
uv run python backend/scripts/reseed_dev.py
```

The root `package.json` has no `dev` script and no `concurrently`. The only thing in the repo that
boots more than one process is `playwright.config.ts`'s `webServer` array, and only for e2e.

There is also a Windows-specific trap worth encoding once: **killing the `uv run fastapi` wrapper
PID does not stop the server.** `uv` spawns the real Python process as a child, and the port stays
bound. The reliable way is to resolve the listening PID from `netstat` on port 8000.

---

## Scope

### In

| #   | Change                              |
| --- | ----------------------------------- |
| 1   | `scripts/start-dev.ps1`             |
| 2   | `scripts/stop-dev.ps1`              |
| 3   | Root `package.json` `dev` script    |
| 4   | `README.md` and `CLAUDE.md` updates |

### Out

- **Docker, compose, or a Makefile.** Not how this project runs.
- **`concurrently` / `run-p` for the servers** (DT-4). Four processes of interleaved output is
  unreadable, and MediaMTX and the AI engine don't fit that model — MediaMTX spawns child ffmpeg
  processes per channel and needs Ctrl+C to reach them.
- **A Linux/bash equivalent.** `deploy/systemd/` covers the production-target Linux path;
  development on this project is Windows.
- **Any change under `backend/`, `frontend/` or `ai_engine/`.**

### Non-goal worth stating explicitly

**Do not hardcode the seed profile list in PowerShell.** `-Reseed` takes a string and passes it
straight through to `reseed_dev.py --profile`, letting Python own validation. Package A adds an
`empty` profile on a different branch; a hardcoded `ValidateSet` here would either reject it or
force these two branches to land together. Pass through, let it error naturally.

---

## Step 1 — `scripts/start-dev.ps1`

Follow the shape of the existing `scripts/start-sim.ps1`: a comment-based help block
(`.SYNOPSIS`/`.DESCRIPTION`), resolve the repo root from `$PSScriptRoot`, preflight, then run.

### Parameters

```
-Backend            start the FastAPI server
-Frontend           start the Vite dev server
-Sim                start MediaMTX (delegates to start-sim.ps1)
-Ai                 start the AI engine
-All                all four
-Reseed <profile>   reseed BEFORE starting anything
-NoNewWindow        run in the current terminal instead of spawning windows
```

No switches at all defaults to `-Backend -Frontend` — the everyday case.

### Ordering

`-Reseed` runs first, **before the backend starts**. `reseed_dev.py` deletes the SQLite file, which
only works while nothing holds it open. Fail the whole script if the reseed fails rather than
starting a backend against a half-reset DB.

Then follow `be_audit/DEMO_TOPOLOGY.md`'s bring-up order: MediaMTX → backend → frontend → AI engine.
The engine discovers cameras entirely from the backend's heartbeat response, so starting it before
the backend just means it logs failures until the backend appears.

### Preflight

Fail fast with an actionable message, the way `start-sim.ps1` does for ffmpeg and mediamtx:

- **`.env` missing** — offer to copy `.env.example` (CI does exactly this, so it's a working dev
  config as-is). Warn that `SECRET_KEY`, `INTERNAL_API_KEY` and `DEFAULT_ADMIN_PASSWORD` are
  placeholders.
- **`uv` not on PATH** — point at the install docs.
- **`pnpm` not on PATH**, or `frontend/node_modules` missing — tell them to run `pnpm install` at
  the **repo root** (it's a workspace, and the root install is what activates the git hooks).
- **`-Ai`** — warn that it needs `uv sync --extra ai` and an NVIDIA GPU. Note that
  `ai_engine/best.engine` is GPU/driver/TensorRT-version-specific and the engine falls back to
  `best.pt` on load failure — that's intentional, not an error to report.
- **`-Sim`** — reuse `start-sim.ps1`'s ffmpeg / mediamtx / `ai_engine/sample_vids` checks rather
  than duplicating them. `sample_vids/` is gitignored, so a fresh clone won't have the clips.

### Spawning

`Start-Process pwsh -ArgumentList '-NoExit','-Command', <command>` per process, each with a distinct
window title so the four are tellable apart. Set the working directory to the repo root for every
one of them — the FastAPI CLI injects `backend/` into `sys.path` itself and `ai_engine` uses flat
`from config import ...` imports, both of which assume you launched from the root.

Use `uv run python`, never bare `python` — PATH python is 3.14 and the project is pinned to 3.12.13.

`-NoNewWindow` runs a single process in the current terminal; if more than one process is requested
with that switch, error out rather than trying to multiplex.

### Known wrinkle

`uv run fastapi dev` has been seen to crash on Windows with a `cp1252` codec error when launched
from a Bash-flavoured shell. If it surfaces, set `PYTHONUTF8=1` in the spawned command.

## Step 2 — `scripts/stop-dev.ps1`

Stops what `start-dev.ps1` started.

**The backend must be resolved by port, not by process name or a stored wrapper PID.** Killing the
`uv run fastapi` wrapper leaves the real server bound to 8000. Get the listening PID:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object -ExpandProperty OwningProcess
```

(or parse `netstat -ano | findstr :8000` if `Get-NetTCPConnection` isn't available), then
`Stop-Process` that PID. Same approach for Vite on 5173 and MediaMTX on 8554.

Take the same switches as `start-dev.ps1` so `-Backend` stops only the backend. Report what was
stopped and what wasn't running; stopping nothing is not an error.

Stopping MediaMTX should also take down its child ffmpeg processes — `runOnInit` spawns one per
channel and they don't exit on their own.

## Step 3 — Root `package.json`

```json
"dev": "pwsh -File scripts/start-dev.ps1"
```

Discoverability only — `pnpm dev` is what people try first. Do not add `concurrently` or any other
dependency.

## Step 4 — Docs

`README.md` §"Running the System" — lead with the one-command path, keep the existing four-terminal
instructions below it as the manual fallback (`be_audit/DEMO_TOPOLOGY.md`'s fallback ladder depends
on people knowing them).

While you're in `README.md`: the repo-structure tree still lists `ai_engine/sync.py`, which was
deleted in favour of `supervisor.py`. Fix that.

`CLAUDE.md` command table — add a row:

| Task            | Command                            |
| --------------- | ---------------------------------- |
| Start dev stack | `pwsh -File scripts/start-dev.ps1` |

Keep the existing per-component rows; they're still the right thing for running one piece.

---

## Verification

Manual only — there is no test harness for PowerShell here and adding one isn't worth it.

1. `pwsh -File scripts/start-dev.ps1` — two windows open, both servers come up, `http://localhost:5173`
   loads and can log in.
2. `pwsh -File scripts/start-dev.ps1 -Sim -Ai` — four windows; MediaMTX serves channels and the
   engine connects (or fails cleanly with a readable message if there's no GPU).
3. `pwsh -File scripts/start-dev.ps1 -Reseed demo` — reseeds first, then starts; confirm the seeded
   accounts work.
4. `-Reseed` with a bogus profile name — fails with Python's error, and **no server starts**.
5. `pwsh -File scripts/stop-dev.ps1` — then confirm the port is actually free:

```bash
netstat -ano | findstr :8000
```

This is the check that matters. If the port is still bound, the wrapper-PID trap wasn't handled.

6. Preflight paths: temporarily rename `.env` and confirm the message is actionable; same for a
   missing `frontend/node_modules`.

Run from a clean shell, not one that already has the servers running.

---

## Report back

- Whether `Get-NetTCPConnection` was available or you had to fall back to parsing `netstat`.
- Whether the `PYTHONUTF8=1` workaround was needed.
- Anything in `README.md` you found stale beyond the `sync.py` line.
