# Contributing

This is the "what to run before committing" doc. **To get the system actually running, follow the [Quickstart](README.md#quickstart--clone-to-first-detection) in the README** — it is the full ordered path from clone to first detection, including the database seed and the camera streams, which the three commands below do not cover.

## First-time setup (development tooling)

```bash
uv sync --extra ai
pnpm install
cp .env.example .env
```

- `uv sync --extra ai` — installs the backend plus the AI engine's heavy ML deps (torch, ultralytics, opencv). Use plain `uv sync` if you're only touching the backend/frontend and don't need to run the AI engine.
  - **No NVIDIA GPU?** Use `uv sync --extra ai-cpu` instead. The two are mutually exclusive: `ai` pins torch to the CUDA index, `ai-cpu` to PyTorch's CPU index so it pulls no `nvidia-*` packages at all.
  - **TensorRT is not included** in either. It is a speed optimisation nothing currently uses, and its PyPI package downloads several GB inside a build step with no timeout — which hung a dev machine indefinitely, twice. It lives in an opt-in `ai-trt` extra; the GPU works fine without it, since CUDA comes from torch.
- `pnpm install` — **run this at the repo root**, not inside `frontend/`. This is a pnpm workspace, and running install at the root is what triggers husky's `prepare` script and activates the git hooks below. Running it only inside `frontend/` will leave your hooks inert.
- `cp .env.example .env` — then fill in real values. The backend hard-fails on startup if any of the 10 keys are missing.

Also run this once, locally (it's a personal git config, not something that can be committed):

```bash
git config blame.ignoreRevsFile .git-blame-ignore-revs
```

Without it, `git blame` will stop at the repo's one bulk formatting commit (`style: apply ruff and prettier formatting`) instead of the commit that actually introduced a line.

## The one command

`pnpm check` is what pre-push runs, so **you don't need to run it yourself first** — just push. Run `pnpm full:check` before opening a PR; it's everything `pnpm check` does, plus a production build and the E2E suite.

`check` is two independent language lanes run in parallel, because nothing in the Python lane depends on anything in the TypeScript lane. `run-p -l` prefixes each output line with its lane so a failure in either is still readable.

| Script                | Runs                                                                |
| --------------------- | ------------------------------------------------------------------- |
| `pnpm format`         | `prettier --write .` + `uv run ruff format .`                       |
| `pnpm format:check`   | Same, in check mode (no writes)                                     |
| `pnpm lint`           | `pnpm --filter frontend lint` + `uv run ruff check .`               |
| `pnpm lint:fix`       | Same, with `--fix`                                                  |
| `pnpm test:be`        | `uv run pytest -n auto` (xdist, one worker per core)                |
| `pnpm test:fe`        | `pnpm --filter frontend test:run` (Vitest)                          |
| `pnpm test`           | `test:be` then `test:fe`                                            |
| `pnpm test:e2e`       | `playwright test` — boots both servers, CI-only, not in `check`     |
| `pnpm build`          | `pnpm --filter frontend build`                                      |
| `pnpm check:be`       | `format:check:ruff` → `lint:ruff` → `test:be`                       |
| `pnpm check:fe`       | `format:check:prettier` → `lint:frontend` → `typecheck` → `test:fe` |
| **`pnpm check`**      | `check:be` ‖ `check:fe`, in parallel — **what pre-push runs**       |
| **`pnpm full:check`** | `check` → `build` → `test:e2e` — the pre-PR command                 |

**Running the backend suite directly:** `uv run pytest -n auto` for everything, or just `uv run pytest backend/tests/test_alerts.py` for one area — a targeted run skips xdist's worker startup and gives cleaner tracebacks.

## What the hooks do, and when

Hooks live in `.husky/` and only activate after `pnpm install` has run at the repo root (see above).

- **pre-commit** — runs `lint-staged`: Prettier/ESLint/Ruff against only the files you staged. Fast (~1-3s), auto-fixes in place.
- **commit-msg** — runs `commitlint` against your commit message. Rejects anything that isn't [Conventional Commits](https://www.conventionalcommits.org/).
- **pre-push** — runs `pnpm check` (format check, lint, typecheck, both test suites) against the whole repo. This is the real gate. It used to take ~15 minutes; it's now well under two. If it ever creeps back up, profile it (`uv run pytest --durations=20`) rather than deleting checks from it — the last regression was ~900 full-cost Argon2 hashes and 352 redundant `alembic upgrade head` runs hiding inside the `client` fixture, none of which any test was asserting on.

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

**This is currently not enabled**, which means CI is advisory: a red PR can still be merged. Turning it on is what makes CI the real gate rather than the pre-push hook. Settings → Branches → Add branch ruleset, targeting `main`:

- Require a pull request before merging
- Require status checks to pass, selecting: `backend`, `frontend`, `format`, `migration`, `e2e`
- Require branches to be up to date before merging

The `migration` job is the one worth caring about most — the `alembic upgrade head` → `verify_migration_schema.py` → `alembic downgrade base` round-trip is the only check in the whole system that **no local gate covers**. `pnpm check` will never catch a migration that drifts from the models.

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

(`var/` is gitignored — safe scratch space.) Then confirm the migrated schema is identical to what `SQLModel.metadata` describes — the exact check the CI `migration` job runs on every PR, against a fresh checkout:

```bash
uv run python backend/scripts/verify_migration_schema.py
```

It builds two disposable databases (one via your migration, one via `create_all()`) and diffs every table/index/trigger object-by-object, tolerating only constraint-ordering noise. A missing index, a forgotten trigger, or a hand-edit that drifted from the model shows up here as a real failure.

**Startup revision check.** The running app refuses to start in production against a database whose Alembic revision doesn't match the code's head (older, newer, or missing entirely) — see `app/core/migrations.py::check_schema_revision`. In development it only warns, except for a genuinely fresh/uninitialized database, which it provisions automatically. `ordinary application startup never silently changes the production schema` (D-005) — schema changes always come from an explicit `alembic upgrade head`, run by a human or a deploy script, never implicitly by the app booting.

**Post-deployment migration policy**, once a database has real production data:

1. Before running a migration: take and verify a WAL-safe backup (`POST /api/system/backups`, or `(cd backend && uv run python -m app.maintenance backup)`).
2. Run `alembic upgrade head`.
3. After: run `PRAGMA integrity_check` and confirm the recorded Alembic revision matches head. The backup manifest's `schema_revision` field records this automatically for every new backup going forward.
4. If something goes wrong once new-version data has been written, **do not attempt a destructive schema downgrade.** Restore the verified pre-migration backup instead — `app.maintenance.restore` already rejects restoring a backup whose recorded schema revision isn't one this codebase's migration chain recognizes, so a stale/incompatible restore fails loudly instead of silently running the wrong schema.

## Performance evidence suite

`backend/tests/perf/` measures NFR-04 (alert delivery), NFR-06 (export speed), NFR-08 (100,000-row query performance), and D-008 (slow-client isolation) against a real file-backed 100,000-row database — see `be_plan/EVIDENCE.md` for the current recorded numbers and machine spec. It's marked `@pytest.mark.slow` and excluded from the default `pytest` run (`pyproject.toml`'s `addopts = "-q -m \"not slow\""`), since seeding alone takes ~30s.

```bash
uv run pytest -m slow backend/tests/perf/ -s
```

`-s` matters — the tests print their measured numbers (`[PERF] ...` lines), which is the whole point of the suite. In CI, this runs as the `perf` job, `workflow_dispatch`-only (too slow for every PR) — trigger it manually from the Actions tab, results are uploaded as a `perf-results` artifact.

## CI jobs

| Job         | Runs on                                   | What it does                                                                                                           |
| ----------- | ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `backend`   | every PR/push                             | format check, lint, `pytest` (with `--cov` reporting — no coverage gate, per the testing policy)                       |
| `migration` | every PR/push                             | `alembic upgrade head` against a fresh empty DB, asserts it matches `SQLModel.metadata`, then `alembic downgrade base` |
| `frontend`  | every PR/push                             | ESLint, typecheck, Vitest, production build                                                                            |
| `format`    | every PR/push                             | repo-wide Prettier check                                                                                               |
| `e2e`       | every PR/push, after `backend`+`frontend` | Playwright against both real servers                                                                                   |
| `perf`      | manual (`workflow_dispatch`) only         | seeds the 100,000-row `perf` profile, runs `backend/tests/perf/`, uploads timings as an artifact                       |

## Troubleshooting

- **Hooks aren't firing.** You probably ran `pnpm install` inside `frontend/` instead of the repo root. Run it at the root.
- **`ruff` / `uv run ruff ...` says command not found.** Run `uv sync` (or `uv sync --extra ai`) at the repo root first.
- **Playwright says browsers are missing.** Run `pnpm exec playwright install --with-deps chromium`.
- **`pnpm check` fails on files you didn't touch.** `lint`/`format:check` run against the whole repo, not just your change — if `main` already had lint debt when you branched, you'll see it too. Not a bug in your change; fix it or coordinate before landing more on top of it.
