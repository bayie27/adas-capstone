# Backend Scripts

These scripts are for local development and manual testing with the SQLite
database in `backend/adas.db`.

## Quick Start

From the repo root:

```powershell
python backend\scripts\reseed_dev.py
python backend\scripts\reseed_dev.py --profile analytics
```

From the `backend` directory:

```powershell
python scripts\reseed_dev.py
python scripts\reseed_dev.py --profile edge
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
python scripts\reset_db.py
python scripts\reset_db.py --no-init
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
python scripts\seed_dev_data.py
python scripts\seed_dev_data.py --profile analytics
python scripts\seed_dev_data.py --profile edge
```

Profiles:

- `demo`: balanced manual-testing dataset
- `analytics`: denser, chart-friendly dataset with many more alerts across 14 days
- `edge`: smaller dataset focused on unusual workflow combinations

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
python scripts\reseed_dev.py
python scripts\reseed_dev.py --profile analytics
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
python scripts\seed_alerts_via_api.py
python scripts\seed_alerts_via_api.py --camera-id 1 --camera-id 2
python scripts\seed_alerts_via_api.py --base-url http://127.0.0.1:8000
```

Notes:

- the backend server must already be running
- the target camera IDs must already exist
- the script uses `INTERNAL_API_KEY` from `.env`

## Suggested Workflow

### Fresh local DB for frontend/manual testing

```powershell
python scripts\reseed_dev.py
```

### Add more alerts through the real API

Start the backend, then run:

```powershell
python scripts\seed_alerts_via_api.py --camera-id 1 --camera-id 2
```

### Wipe the DB completely

```powershell
python scripts\reset_db.py --no-init
```

## Why `_bootstrap.py` Exists

The scripts can be run from either:

- repo root
- `backend`

`_bootstrap.py` makes sure:

- `app...` imports work
- the working directory is normalized to `backend`
- relative SQLite paths still point to the correct `adas.db`

Without that, running the same script from different folders could create or
target the wrong SQLite file.
