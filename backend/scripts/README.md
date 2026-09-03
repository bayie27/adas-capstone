# Backend Scripts

These scripts are for local development and manual testing with the SQLite
database in `backend/adas.db`.

## Quick Start

From the repo root:

```powershell
uv run python backend\scripts\reseed_dev.py
uv run python backend\scripts\reseed_dev.py --profile analytics
```

From the `backend` directory:

```powershell
uv run python scripts\reseed_dev.py
uv run python scripts\reseed_dev.py --profile edge
```

That will:

1. delete the current local SQLite files
2. recreate the schema
3. seed a predictable set of users, cameras, and alerts

## Script List

### `reset_db.py`

Deletes the local SQLite files:

- `adas.db`
- `adas.db-wal`
- `adas.db-shm`

Then recreates tables and the default admin account.

Usage:

```powershell
uv run python scripts\reset_db.py
uv run python scripts\reset_db.py --no-init
```

Notes:

- stop the backend server before running this
- `--no-init` deletes the DB files without recreating them

### `seed_dev_data.py`

Seeds a predictable local dataset for UI testing and demos.

**The logic lives in `backend/app/dev/`, not here.** `backend/scripts/` is
not a package, so nothing but a CLI entrypoint could import it — the app
itself could not, and `backend/tests/perf/conftest.py` had to inject
`backend/scripts/` onto `sys.path` to reuse the row generators. These
scripts are now thin argparse front-ends over `app.dev.seed_profile()` and
`app.dev.seed_perf_data()`, which take an explicit engine.

Includes:

- default admin from `.env`
- four operator accounts, plus (on `demo`/`analytics`/`edge`) a second
  admin, a disabled account and one that must change its password
- six cameras in different connection/AI states, with observed telemetry;
  `demo`/`analytics` add an unresponsive and a soft-deleted camera
- profile-driven alert presets
- mixed verifier/closer combinations for exports and alert details
- recent and historical timestamps spread across hours and days for analytics
- health history, export jobs and full audit-action coverage where the
  profile asks for them
- a placeholder JPEG per detection, so `GET /api/alerts/{log_id}/snapshot`
  resolves instead of 404ing

Usage:

```powershell
uv run python scripts\seed_dev_data.py
uv run python scripts\seed_dev_data.py --profile analytics
uv run python scripts\seed_dev_data.py --profile edge
uv run python scripts\seed_dev_data.py --profile perf
uv run python scripts\seed_dev_data.py --profile perf --count 20000
```

Profiles:

- `demo`: balanced manual-testing dataset, plus 7 days of health history,
  one export job in each of the five statuses, and all 26 `AUDIT_ACTIONS`
- `analytics`: denser, chart-friendly dataset with many more alerts across
  14 days, and 30 days of health history
- `edge`: smaller dataset focused on unusual workflow combinations, plus
  column boundaries (`confidence_score` at exactly 0.0 and 1.0) and a
  camera holding a `cooldown_until`
- `empty`: schema and the default admin only — zero cameras, zero
  detections. For demoing first-run and empty states, which otherwise
  cannot be shown without hand-deleting rows
- `perf`: **100,000** `detection_log` rows (NFR-08), bulk-inserted via batched
  SQLAlchemy Core `insert()` calls rather than 100,000 ORM objects — measured
  at ~33s on the demo laptop (see `be_plan/EVIDENCE.md`). Spread over ~18
  months across the six seeded cameras, with a realistic
  Cleared/Dismissed/Ongoing/Unverified mix that still respects
  `ux_detection_open_camera` (at most one open incident per camera survives;
  every other open candidate is demoted to `Cleared`). Snapshot files are
  not generated — a handful of reused fake keys exercise the
  missing-snapshot-file path. `--count` overrides the row target for a
  faster smoke run. This is what `backend/tests/perf/` seeds itself with a
  fresh copy of, but the CLI profile is also useful on its own for manually
  poking at `GET /api/alerts/` or the export routes against a realistically
  sized dataset.

Seeded operator accounts:

- `dsahagun / operator123`
- `ealonzo / operator123`
- `smeer / operator123`
- `jtenorio / operator123`

Admin account:

- `admin / DEFAULT_ADMIN_PASSWORD` from `.env`

### `reseed_dev.py`

Convenience command for a fully fresh local DB.

Usage:

```powershell
uv run python scripts\reseed_dev.py
uv run python scripts\reseed_dev.py --profile analytics
uv run python scripts\reseed_dev.py --profile empty
uv run python scripts\reseed_dev.py --profile perf --count 20000
```

Use this when you want to reset everything and start from a known state.
This is the easiest way to switch profiles cleanly.

`--count` is passed through to the `perf` profile. It used to be dropped
here, so `reseed_dev.py --profile perf` always seeded the full 100,000 rows
(~33s) with no way to ask for fewer.

Note that this deletes the SQLite file, so it cannot run while the backend
holds it open — on Windows the delete fails outright. Package B's
`POST /api/dev/reseed` is the in-process equivalent that keeps the server
up.

## Snapshot placeholders

Every seeded detection gets a placeholder JPEG written under
`SNAPSHOT_ROOT`, so the alert detail view has an image instead of a 404.
The default is a small embedded grey placeholder — deliberately obvious, so
nobody mistakes one for real evidence.

Dropping real `.jpg` frames into `backend/app/dev/assets/snapshots/` makes
a better-looking demo: they are used round-robin in place of the
placeholder. That directory is gitignored, and its absence is not an error.

## Suggested Workflow

### Fresh local DB for frontend/manual testing

```powershell
uv run python scripts\reseed_dev.py
```

### Wipe the DB completely

```powershell
uv run python scripts\reset_db.py --no-init
```

## Why `_bootstrap.py` Exists

The scripts can be run from either:

- repo root
- `backend`

`_bootstrap.py` makes sure `app...` imports work regardless of which one, by
putting `backend/` on `sys.path`. It does **not** change the working
directory anymore — `DATABASE_URL` is anchored to the repo root by
`Settings`'s own field validator (`backend/app/core/config.py`), so relative
SQLite paths resolve correctly without a `chdir`. (An earlier version of
this script did normalize the CWD; that responsibility moved into `Settings`
itself during the DX cleanup package, and this doc had gone stale describing
the old behavior.)
