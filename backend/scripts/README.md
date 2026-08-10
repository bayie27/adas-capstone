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

Includes:

- default admin from `.env`
- four operator accounts
- six cameras in different connection/AI states
- profile-driven alert presets
- mixed verifier/closer combinations for exports and alert details
- recent and historical timestamps spread across hours and days for analytics

Usage:

```powershell
uv run python scripts\seed_dev_data.py
uv run python scripts\seed_dev_data.py --profile analytics
uv run python scripts\seed_dev_data.py --profile edge
uv run python scripts\seed_dev_data.py --profile perf
uv run python scripts\seed_dev_data.py --profile perf --count 20000
```

Profiles:

- `demo`: balanced manual-testing dataset
- `analytics`: denser, chart-friendly dataset with many more alerts across 14 days
- `edge`: smaller dataset focused on unusual workflow combinations
- `perf`: **100,000** `detection_log` rows (NFR-08), bulk-inserted via batched
  SQLAlchemy Core `insert()` calls rather than 100,000 ORM objects — measured
  at ~33s on the demo laptop (see `be_plan/EVIDENCE.md`). Spread over ~18
  months across the six seeded cameras, with a realistic
  Resolved/Dismissed/Ongoing/Unverified mix that still respects
  `ux_detection_open_camera` (at most one open incident per camera survives;
  every other open candidate is demoted to `Resolved`). Snapshot files are
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
```

Use this when you want to reset everything and start from a known state.
This is the easiest way to switch profiles cleanly.

### `seed_alerts_via_api.py`

Creates sample alerts through the real internal API route:

- `POST /api/internal/alert`

This is useful when you want to exercise the application path instead of
inserting alert rows directly into SQLite.

Usage:

```powershell
uv run python scripts\seed_alerts_via_api.py
uv run python scripts\seed_alerts_via_api.py --camera-id 1 --camera-id 2
uv run python scripts\seed_alerts_via_api.py --base-url http://127.0.0.1:8000
```

Notes:

- the backend server must already be running
- the target camera IDs must already exist
- the script uses `INTERNAL_API_KEY` from `.env`

## Suggested Workflow

### Fresh local DB for frontend/manual testing

```powershell
uv run python scripts\reseed_dev.py
```

### Add more alerts through the real API

Start the backend, then run:

```powershell
uv run python scripts\seed_alerts_via_api.py --camera-id 1 --camera-id 2
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
