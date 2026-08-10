# Contributing

This is the "what to run before committing" doc. See [README.md](README.md) for how to run the system itself.

## First-time setup

```bash
uv sync --extra ai
pnpm install
cp .env.example .env
```

- `uv sync --extra ai` — installs the backend plus the AI engine's heavy ML deps (torch, tensorrt, ultralytics, opencv). Use plain `uv sync` if you're only touching the backend/frontend and don't need to run the AI engine.
- `pnpm install` — **run this at the repo root**, not inside `frontend/`. This is a pnpm workspace, and running install at the root is what triggers husky's `prepare` script and activates the git hooks below. Running it only inside `frontend/` will leave your hooks inert.
- `cp .env.example .env` — then fill in real values. The backend hard-fails on startup if any of the 10 keys are missing.

Also run this once, locally (it's a personal git config, not something that can be committed):

```bash
git config blame.ignoreRevsFile .git-blame-ignore-revs
```

Without it, `git blame` will stop at the repo's one bulk formatting commit (`style: apply ruff and prettier formatting`) instead of the commit that actually introduced a line.

## The one command

Run `pnpm check` before pushing. Run `pnpm full:check` before opening a PR — it's everything `pnpm check` does, plus a production build and the E2E suite.

| Script                | Runs                                                                    |
| --------------------- | ----------------------------------------------------------------------- |
| `pnpm format`         | `prettier --write .` + `uv run ruff format .`                           |
| `pnpm format:check`   | Same, in check mode (no writes)                                         |
| `pnpm lint`           | `pnpm --filter frontend lint` + `uv run ruff check .`                   |
| `pnpm lint:fix`       | Same, with `--fix`                                                      |
| `pnpm typecheck`      | `pnpm --filter frontend typecheck` (`tsc --noEmit`)                     |
| `pnpm test:be`        | `uv run pytest`                                                         |
| `pnpm test:fe`        | `pnpm --filter frontend test:run` (Vitest)                              |
| `pnpm test`           | `test:be` then `test:fe`                                                |
| `pnpm test:e2e`       | `playwright test` — boots both servers, CI-only, not in `check`         |
| `pnpm build`          | `pnpm --filter frontend build`                                          |
| **`pnpm check`**      | `format:check` → `lint` → `typecheck` → `test` — **what pre-push runs** |
| **`pnpm full:check`** | `check` → `build` → `test:e2e` — the pre-PR command                     |

## What the hooks do, and when

Hooks live in `.husky/` and only activate after `pnpm install` has run at the repo root (see above).

- **pre-commit** — runs `lint-staged`: Prettier/ESLint/Ruff against only the files you staged. Fast (~1-3s), auto-fixes in place.
- **commit-msg** — runs `commitlint` against your commit message. Rejects anything that isn't [Conventional Commits](https://www.conventionalcommits.org/).
- **pre-push** — runs `pnpm check` (format check, lint, typecheck, both test suites) against the whole repo. Slower; this is the real gate.

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

`git commit --no-verify` / `git push --no-verify` skip the hooks. They exist for genuine WIP commits on your own branch — CI runs the same checks (`pnpm check`-equivalent jobs) on every PR, so skipping locally just defers the failure, it doesn't avoid it. Don't push straight to `main` with `--no-verify` expecting it to slide through unnoticed.

## Branch protection

CI (`.github/workflows/ci.yml`) runs on every PR and push to `main`, but **requiring those checks to pass before merge is a manual GitHub repo setting** (Settings → Branches → branch protection rules) — it can't be committed as a file. `gh` CLI is available if you'd rather script it than click through the UI.

## Database migrations

D-005: the dev database is disposable until the schema is decision-complete; it no longer is. Every schema change now goes through a reviewed Alembic migration — never `SQLModel.metadata.create_all()` against a real file, which is reserved for the fast in-memory unit-test fixture in `backend/tests/conftest.py`.

**Resetting your local dev database:**

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

Test the new migration against a fresh empty file before committing it:

```bash
DATABASE_URL="sqlite:///var/tmp/migration_check.db" uv run alembic upgrade head
DATABASE_URL="sqlite:///var/tmp/migration_check.db" uv run alembic downgrade base
```

(`var/` is gitignored — safe scratch space.)

**Startup revision check.** The running app refuses to start in production against a database whose Alembic revision doesn't match the code's head (older, newer, or missing entirely) — see `app/core/migrations.py::check_schema_revision`. In development it only warns, except for a genuinely fresh/uninitialized database, which it provisions automatically. `ordinary application startup never silently changes the production schema` (D-005) — schema changes always come from an explicit `alembic upgrade head`, run by a human or a deploy script, never implicitly by the app booting.

**Post-deployment migration policy**, once a database has real production data:

1. Before running a migration: take and verify a WAL-safe backup (`POST /api/system/backups`, or `(cd backend && uv run python -m app.maintenance backup)`).
2. Run `alembic upgrade head`.
3. After: run `PRAGMA integrity_check` and confirm the recorded Alembic revision matches head. The backup manifest's `schema_revision` field records this automatically for every new backup going forward.
4. If something goes wrong once new-version data has been written, **do not attempt a destructive schema downgrade.** Restore the verified pre-migration backup instead — `app.maintenance.restore` already rejects restoring a backup whose recorded schema revision isn't one this codebase's migration chain recognizes, so a stale/incompatible restore fails loudly instead of silently running the wrong schema.

## Troubleshooting

- **Hooks aren't firing.** You probably ran `pnpm install` inside `frontend/` instead of the repo root. Run it at the root.
- **`ruff` / `uv run ruff ...` says command not found.** Run `uv sync` (or `uv sync --extra ai`) at the repo root first.
- **Playwright says browsers are missing.** Run `pnpm exec playwright install --with-deps chromium`.
- **`pnpm check` fails on files you didn't touch.** `lint`/`format:check` run against the whole repo, not just your change — if `main` already had lint debt when you branched, you'll see it too. Not a bug in your change; fix it or coordinate before landing more on top of it.
