# Contributing

This documents development setup, verification, and the contribution workflow. Testing scope and completion rules live in [CLAUDE.md](CLAUDE.md#verification-policy). **To get the system actually running, follow the [Quickstart](README.md#quickstart--clone-to-first-detection) in the README** — it is the full ordered path from clone to first detection, including the database seed and the camera streams, which the three commands below do not cover.

## First-time setup (development tooling)

These steps are for an unconfigured checkout, not prerequisites to repeat on every task. Run commands from the repo root. Reuse working dependencies and configuration; install only what the task needs.

- Backend tooling: `uv sync`.
- Running the AI engine: `uv sync --extra ai` for NVIDIA GPU support, or `uv sync --extra ai-cpu` without it. The extras are mutually exclusive. Neither includes TensorRT; the optional `ai-trt` extra and its source/pinning constraints are documented in `pyproject.toml`.
- Frontend/root tooling: `pnpm install` at the repo root activates the Husky hooks.
- Create `.env` from `.env.example` only when it is absent; preserve existing values. Fill in the required settings documented by `.env.example` and `backend/app/core/config.py`. Do not display secrets while checking configuration.

For example, in PowerShell:

```powershell
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
```

For the optional P30 protected-storage lane, set `PROTECTED_BACKUP_DIR` and
`PROTECTED_ARCHIVE_DIR` to absolute paths on the explicitly mounted external
device. The backend never discovers removable media; it compares the
physical device with the live database and falls back to `BACKUP_DIR` or
`ARCHIVE_DIR` as a visible degraded tier when the target is unsafe or absent.
The local `BACKUP_DIR` remains the control/state root, including the restore
request and emergency rollback reserve. Do not put credentials or demo
secrets in `.env.example`.

Optional, once per checkout: configure Git blame to skip the bulk formatting commit. This local Git setting is not a prerequisite for development:

```bash
git config blame.ignoreRevsFile .git-blame-ignore-revs
```

Without it, `git blame` will stop at the repo's one bulk formatting commit (`style: apply ruff and prettier formatting`) instead of the commit that actually introduced a line.

## Verification commands

When a push is already authorized, let pre-push run `pnpm check`; do not run it manually beforehand. This instruction does not authorize a push. Run `pnpm full:check` before opening a PR; it includes `check`, a production build, and the E2E suite.

The table is a command reference, not a checklist to execute in full. During implementation, format changed files and run the narrowest relevant checks. Pre-commit handles staged files; pre-push runs `pnpm check`; the pre-PR gate is `pnpm full:check`. Do not add separate full-suite confirmation runs immediately before a gate that includes them. Required gates remain required even when they overlap earlier targeted verification.

`check` is two independent language lanes run in parallel, because nothing in the Python lane depends on anything in the TypeScript lane. `run-p -l` prefixes each output line with its lane so a failure in either is still readable.

| Script                | Runs                                                                                   |
| --------------------- | -------------------------------------------------------------------------------------- |
| `pnpm format`         | `prettier --write .` + `uv run ruff format .`                                          |
| `pnpm format:check`   | Same, in check mode (no writes)                                                        |
| `pnpm lint`           | `pnpm --filter frontend lint` + `uv run ruff check .`                                  |
| `pnpm lint:fix`       | Same, with `--fix`                                                                     |
| `pnpm test:be`        | `uv run pytest -n auto` (xdist, one worker per core)                                   |
| `pnpm test:fe`        | `pnpm --filter frontend test:run` (Vitest)                                             |
| `pnpm test`           | `test:be` then `test:fe`                                                               |
| `pnpm test:e2e`       | `playwright test --project=chromium` — local pre-PR gate and CI; excluded from `check` |
| `pnpm build`          | `pnpm --filter frontend build`                                                         |
| `pnpm check:be`       | `format:check:ruff` → `lint:ruff` → `test:be`                                          |
| `pnpm check:fe`       | `format:check:prettier` → `lint:frontend` → `typecheck` → `test:fe`                    |
| **`pnpm check`**      | `check:be` ‖ `check:fe`, in parallel — **what pre-push runs**                          |
| **`pnpm full:check`** | `check` → `build` → `test:e2e` — the pre-PR command                                    |

**Running the backend suite directly:** `uv run pytest -n auto` for everything, or just `uv run pytest backend/tests/test_alerts.py` for one area — a targeted run skips xdist's worker startup and gives cleaner tracebacks.

## What the hooks do, and when

Hooks live in `.husky/` and only activate after `pnpm install` has run at the repo root (see above).

- **pre-commit** — runs `lint-staged`: Prettier/ESLint/Ruff against only the files you staged. Fast (~1-3s), auto-fixes in place.
- **commit-msg** — runs `commitlint` against your commit message. Rejects anything that isn't [Conventional Commits](https://www.conventionalcommits.org/).
- **pre-push** — runs `pnpm check` (format check, lint, typecheck, both test suites) against the whole repo. If it becomes slow, profile the affected lane (for pytest, `uv run pytest --durations=20`) rather than removing checks. Runtime depends on the machine and selected tests.

## Commit conventions

Conventional Commits, matching the existing history. No fixed scope list — use whatever scope fits (`fix(auth):`, `refactor(modals):`, or no scope at all).

| Type       | Example                                               |
| ---------- | ----------------------------------------------------- |
| `feat`     | `feat: add camera pause/resume endpoint`              |
| `fix`      | `fix(auth): harden session expiry validation`         |
| `refactor` | `refactor(modals): extract form components`           |
| `chore`    | `chore: bump vite to v8`                              |
| `docs`     | `docs: fix broken installation fence in README`       |
| `test`     | `test: add coverage for alert dismissal side effects` |
| `ci`       | `ci: add GitHub Actions workflow`                     |
| `style`    | `style: apply ruff and prettier formatting`           |

## Escape hatch

`git commit --no-verify` and `git push --no-verify` skip hooks. The WIP exception applies to intermediate commits on the contributor's own branch; it does not make them verified or ready to land. Record skipped checks. Do not infer permission to bypass pre-push from the WIP-commit exception. Required landing checks still apply.

## Branch protection

Branch protection is remote repository configuration. Inspect its current state when working on repository governance; do not infer it from this document. Ordinary development does not require changing repository settings. The following is the recommended configuration for `main`, not an instruction to apply it during unrelated work:

- Require a pull request before merging
- Require status checks to pass, selecting: `backend`, `frontend`, `format`, `migration`, `e2e`
- Require branches to be up to date before merging

The `migration` CI job verifies upgrade, schema equivalence, and downgrade. Neither `pnpm check` nor `pnpm full:check` includes that migration-specific verification; run the checks below when changing the schema.

## Database migrations

Application databases must be provisioned and changed through Alembic (D-005). `create_all()` is permitted only in isolated test fixtures and the existing disposable schema-comparison verifier; never use it to provision or repair an application database. Generate, inspect, and test migrations within the authorized implementation task; "reviewed" does not require permission before that preparation. Preserve applicable human review before deployment.

**Resetting your local dev database (separate from migration verification):**

Use fresh disposable databases for verification. The command below deletes existing data in the configured development database and its SQLite sidecars; run it only when that reset is within the user’s authorized scope. Generating and testing a migration does not require resetting the application database.

```bash
uv run python backend/scripts/reset_db.py
```

This deletes the SQLite files and re-provisions the schema by running `alembic upgrade head` automatically (development-only convenience — see `app/core/migrations.py::check_schema_revision`). It is **not** a `create_all()` shortcut; it exercises the same migration a real deployment would.

**Writing a new migration**, once you've changed a model in `backend/app/models/`:

```bash
uv run alembic revision --autogenerate -m "short description"
```

Then **review the generated file line by line** before trusting it. Alembic's SQLite autogenerate reliably misses:

- partial indexes (`sqlite_where=...`)
- expression indexes (e.g. `func.lower(...)`) — these are silently skipped with a warning, not generated incorrectly
- anything attached via a SQLAlchemy `after_create` event rather than declarative metadata (the `audit_log` immutability triggers, the `help_article_fts` virtual table and its sync triggers)

Every one of those needs a hand-written `op.execute(...)`, mirrored in both `upgrade()` and `downgrade()`. `backend/alembic/versions/09e6d3163265_initial_production_schema.py`'s module docstring is a worked example.

Before committing a schema change, test upgrade and downgrade against a fresh disposable file, then run the schema-comparison verifier. The PowerShell example below runs from the repo root, isolates `DATABASE_URL`, checks each exit status, and restores the prior environment value even on failure. The unique scratch directory is under gitignored `var/tmp`; it is retained for inspection.

```powershell
$taskMigrationDir = Join-Path $PWD ("var/tmp/migration-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $taskMigrationDir -ErrorAction Stop | Out-Null
$taskHadDatabaseUrl = Test-Path Env:DATABASE_URL
$taskPreviousDatabaseUrl = $env:DATABASE_URL
try {
    $taskMigrationDb = (Join-Path $taskMigrationDir 'check.db').Replace('\', '/')
    $env:DATABASE_URL = "sqlite:///$taskMigrationDb"
    uv run alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Migration upgrade failed' }
    uv run alembic downgrade base
    if ($LASTEXITCODE -ne 0) { throw 'Migration downgrade failed' }
    uv run python backend/scripts/verify_migration_schema.py
    if ($LASTEXITCODE -ne 0) { throw 'Schema comparison failed' }
} finally {
    if ($taskHadDatabaseUrl) {
        $env:DATABASE_URL = $taskPreviousDatabaseUrl
    } else {
        Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
    }
}
```

It builds two disposable databases (one via your migration, one via `create_all()`) and diffs every table/index/trigger object-by-object, tolerating only constraint-ordering noise. A missing index, a forgotten trigger, or a hand-edit that drifted from the model shows up here as a real failure.

**Startup revision check.** The running app refuses to start in production against a database whose Alembic revision doesn't match the code's head (older, newer, or missing entirely) — see `app/core/migrations.py::check_schema_revision`. In development it only warns, except for a genuinely fresh/uninitialized database, which it provisions automatically. `ordinary application startup never silently changes the production schema` (D-005) — schema changes always come from an explicit `alembic upgrade head`, run by a human or a deploy script, never implicitly by the app booting.

**Post-deployment migration policy**, once a database has real production data: these steps apply to an authorized deployment, not ordinary local migration verification.

1. Before running a migration: take and verify a WAL-safe backup using `POST /api/system/backups`.
2. From the repo root, run `uv run alembic upgrade head` against the intended deployment database.
3. After: run `PRAGMA integrity_check` and confirm the recorded Alembic revision matches head. The backup manifest's `schema_revision` field records this automatically for every new backup going forward.
4. If something goes wrong once new-version data has been written, **do not attempt a destructive schema downgrade.** Restore the verified pre-migration backup instead — `app.maintenance.restore` already rejects restoring a backup whose recorded schema revision isn't one this codebase's migration chain recognizes, so a stale/incompatible restore fails loudly instead of silently running the wrong schema.

## Performance evidence suite

`backend/tests/perf/` measures NFR-04 (alert delivery), NFR-06 (export speed), NFR-08 (100,000-row query performance), and D-008 (slow-client isolation) against a real file-backed 100,000-row database — see `be_plan/EVIDENCE.md` for the current recorded numbers and machine spec. It's marked `@pytest.mark.slow` and excluded from the default `pytest` run (`pyproject.toml`'s `addopts = "-q -m \"not slow\""`), since seeding alone takes ~30s.

```bash
uv run pytest -m slow backend/tests/perf/ -s
```

`-s` matters — the tests print their measured numbers (`[PERF] ...` lines), which is the whole point of the suite. In CI, this runs as the `perf` job, `workflow_dispatch`-only (too slow for every PR) — trigger it manually from the Actions tab, results are uploaded as a `perf-results` artifact.

## CI jobs

| Job         | Runs on                                                                      | What it does                                                                                                           |
| ----------- | ---------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `backend`   | PRs to `main`, pushes to `main`, and manual runs                             | format check, lint, `pytest` (with `--cov` reporting — no coverage gate, per the testing policy)                       |
| `migration` | PRs to `main`, pushes to `main`, and manual runs                             | `alembic upgrade head` against a fresh empty DB, asserts it matches `SQLModel.metadata`, then `alembic downgrade base` |
| `frontend`  | PRs to `main`, pushes to `main`, and manual runs                             | ESLint, typecheck, Vitest, production build                                                                            |
| `format`    | PRs to `main`, pushes to `main`, and manual runs                             | repo-wide Prettier check                                                                                               |
| `e2e`       | PRs to `main`, pushes to `main`, and manual runs, after `backend`+`frontend` | Playwright against both real servers                                                                                   |
| `perf`      | manual (`workflow_dispatch`) only                                            | seeds the 100,000-row `perf` profile, runs `backend/tests/perf/`, uploads timings as an artifact                       |

## Troubleshooting

- **Hooks aren't firing.** You probably ran `pnpm install` inside `frontend/` instead of the repo root. Run it at the root.
- **`ruff` / `uv run ruff ...` says command not found.** Run `uv sync` (or `uv sync --extra ai`) at the repo root first.
- **Playwright says browsers are missing.** Run `pnpm exec playwright install --with-deps chromium`.
- **`pnpm check` fails on files you didn't touch.** `lint`/`format:check` run against the whole repo, not just your change — if `main` already had lint debt when you branched, you'll see it too. Investigate whether the change caused the failure, even when the reported file was untouched. Fix task-related failures. For verified baseline failures, report evidence and continue independent work without silently expanding scope. A required failing gate still blocks landing; report that separately from completed implementation work.
- **The daily restart (NFR-16) didn't fire.** On Windows, confirm the Scheduled Task is actually registered: `scripts\register-maintenance-task.ps1 -Verify` shows the resolved trigger time, `NextRunTime`, `LastRunTime`, and `LastTaskResult`. A `LastTaskResult` other than `0` (success) or `267011` (never run) means the last firing failed — check `var\log\maintenance-<timestamp>.transcript.log` for that run. The task only fires while the registering user is logged on (`LogonType=Interactive`, deliberate — see the script's own header comment); it will not fire if the account is logged out, only if the laptop is merely locked or the lid is closed while logged on.
- **The daily backup (NFR-18) seems to be missing.** `GET /api/system/maintenance/status` (Admin only) reports `last_scheduled_backup`, `next_scheduled_backup_at`, and `backup_overdue`. Unlike the restart, the backup runs inside the backend process itself (`SCHEDULER_ENABLED=true`) — if it's `null`/`overdue`, check the backend's own log rather than the Windows Task Scheduler.
