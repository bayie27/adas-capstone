# P7 — Backup, Restore, Restart, and Archival

> **Blocked by:** P2 only. Parallel-safe with P5 and P6.
> **Branch:** `feat/be-p7-backup-ops`
> **Prerequisite reading:** [`01_CONTRACTS.md`](01_CONTRACTS.md) §3.10,
> `be_decisions_review.md` D-011, and `backup_restore_explained.md` (the approved plain-language
> companion — read it, it explains *why* restore must happen offline).
> **Size:** L. Eight steps.

## Why this package exists

NFR-18 requires automated daily SQLite backups that do not interrupt inference or trigger database
locks, plus admin-initiated recovery within a 60-second window. NFR-16 requires a daily restart in a
configurable low-traffic window with under-10-second recovery. `backend/scripts/daily_restart.sh` is
0 bytes and nothing else exists.

**Deployment context:** Windows demo laptop. Everything here works on Windows. The
backup/validate/restore/rollback logic is pure cross-platform Python; systemd and PowerShell are thin
wrappers around the same commands. See [`13_WSL2_LINUX_PATH.md`](13_WSL2_LINUX_PATH.md) if you later
want to actually exercise the Linux path.

---

## The one architectural constraint

**A running FastAPI process cannot replace its own database.** WAL mode means `adas.db` has live
`-wal` and `-shm` sidecars; overwriting the main file while connections are open produces a corrupt
or silently stale database. D-011's answer:

- **Backup happens online**, using SQLite's own `Connection.backup()` API, which is WAL-safe and does
  not block writers.
- **Restore happens offline**, orchestrated by an external process, with the backend and AI engine
  stopped.
- The API only *requests* a restore by writing a flag file. It never replaces the database and never
  gets unrestricted shell execution.

---

## Step 1 — The maintenance core

**File:** new `backend/app/maintenance/` (a package, runnable as `python -m app.maintenance`)

```
app/maintenance/
    __init__.py
    cli.py          # argparse entrypoint: backup | verify | list | restore | rollback | archive | restart
    backup.py
    verify.py
    restore.py
    archive.py
    manifest.py
```

Pure Python, no FastAPI import, cross-platform. **This is the single source of truth** — every
orchestrator (API route, PowerShell, systemd, Scheduled Task) calls into it. Nothing reimplements
file handling.

### Backup

Use `sqlite3.Connection.backup()` — **never** copy `adas.db` with `shutil`, and never require the
external `sqlite3` CLI (the paper mentions `.backup`; D-011 selects the Python API, which is the same
mechanism without a binary dependency).

Sequence, in this order:

1. check available disk space; abort cleanly if insufficient
2. take an exclusive in-process lock so two backups cannot overlap — a concurrent API request gets
   `409 CONFLICT_BUSY`
3. write to a **temporary** path
4. close it, validate it (Step 2)
5. `os.replace` it to its final protected filename — atomic
6. write the sidecar manifest
7. prune only *after* a new valid backup exists

**Never remove an older valid backup because a new backup failed.**

### Manifest

One JSON sidecar per backup: random backup id, safe filename, UTC creation timestamp, origin
(`manual` / `scheduled` / `pre-restore`), application version, Alembic revision (`None` until P9),
file size, SHA-256 checksum, and validation results.

A file is **not listed as a valid restore point** unless its required checks passed.

---

## Step 2 — Validation

| Context | Checks |
|---|---|
| daily / manual backup | `PRAGMA quick_check`, `PRAGMA foreign_key_check`, SHA-256 verification |
| restore candidate, weekly archive | the above **plus** full `PRAGMA integrity_check` |

Run these against the completed backup file, not the live database.

---

## Step 3 — Retention

Configurable defaults: 30 scheduled daily backups, 10 manual backups, and the emergency pre-restore
backup retained until restore success is verified.

Pruning runs only after a new valid backup exists. A selected restore candidate and any active
emergency rollback file are never pruned.

---

## Step 4 — Backup API

**File:** new `backend/app/api/routes/maintenance.py`

> **Do not add these to `routes/system.py`.** That module holds the P1 probes only, and P5 is adding
> `routes/system_health.py` in parallel. Sharing one file is what would make these two packages
> conflict. The URL prefix is still `/api/system/...`; only the module differs.

```
GET  /api/system/backups     Admin only — lists verified restore points
POST /api/system/backups     Admin only — triggers a manual backup
```

`GET` returns backup id, created-at, origin, size, and validation status. It **never** returns
`artifact_path` or any absolute path.

`POST` runs in a bounded background task and returns `202`. A second concurrent request →
`409 CONFLICT_BUSY`. Both write `BACKUP_TRIGGER` audit rows with the result and no filesystem secrets.

Per the paper, an admin can manually trigger an immediate backup before making config changes — say so
in the endpoint description.

---

## Step 5 — Restore request

```
POST /api/system/restores           Admin only -> 202
GET  /api/system/restores/latest    Admin only
```

Authorization is deliberately heavy — this is destructive:

1. active Administrator only
2. **current administrator password** re-submitted in the body
3. explicit confirmation containing the selected backup id
4. the id must map to a manifest-listed file **inside `BACKUP_DIR`**. Never accept a client-supplied
   filesystem path. Validate the id against the manifest index, not by joining it onto a path.

On acceptance the route: revalidates the manifest, writes the restore-request flag file via atomic
rename, audits `RESTORE_TRIGGER`, broadcasts planned maintenance, and returns `202`. It does **not**
touch the database file.

**Restore state is a file, not a table** (`01_CONTRACTS.md` §3.10) — `BACKUP_DIR/restore_state.json`.
This is the detail most likely to be implemented wrong: a restore replaces `adas.db`, so any restore
progress written to the database is destroyed by the restore itself. Likewise the `RESTORE_TRIGGER`
audit row lives in the pre-restore database (and therefore in the emergency backup); after the
restored database is live, record the **outcome** as a fresh `system`-actor audit row.

---

## Step 6 — Offline restore and rollback

**File:** `app/maintenance/restore.py`, invoked by the external orchestrator, never by FastAPI.

D-011's sequence, exactly:

1. stop the AI supervisor
2. stop FastAPI, wait for database connections to close
3. create and verify an **emergency backup** of the current database
4. verify the selected backup: checksum, `integrity_check`, `foreign_key_check`, compatible schema
   revision
5. restore to a temporary database path and validate it again
6. remove obsolete `-wal` and `-shm` sidecars — **only while services are offline**
7. atomically replace the primary database
8. start FastAPI, wait for `GET /healthz/ready`
9. start the AI supervisor, wait for a fresh heartbeat
10. record the final result in `restore_state.json`

**Rollback.** If readiness or any required startup validation fails: stop services, restore the
emergency pre-restore database, restart the original system, and record a rollback outcome. A failed
restore may not leave the system silently half-restored. Every step is timed and logged.

---

## Step 7 — Scheduled backup and daily restart

```
app/maintenance/cli.py restart
```

Default maintenance time is configurable, initially 3:00 AM **deployment-local** (not UTC — this one
is intentionally local, because "low-traffic window" is a wall-clock concept).

Sequence: complete and verify the online daily backup **first**, then broadcast planned maintenance,
gracefully stop AI ingestion, restart backend and AI services, wait for readiness and a fresh
heartbeat, and record measured durations.

**Backup duration is measured separately from restart downtime.** The paper's under-10-second restart
is a benchmark target, not a presumed result — report the laptop's actual model-load, service-ready,
and camera-recovery timings (D-011).

Orchestrators:

| Platform | Mechanism |
|---|---|
| Windows (demo) | `scripts/adas-maintenance.ps1` + a Windows Scheduled Task. Explicit and manual — do not pretend systemd exists |
| Linux (production target) | restricted systemd service + timer units that can invoke **only** the approved ADAS maintenance workflow |

Both call the same Python entrypoint. `backend/scripts/daily_restart.sh` (0 bytes today) becomes the
Linux shim; add the PowerShell equivalent alongside it.

---

## Step 8 — Weekly air-gapped archive

```
app/maintenance/cli.py archive
```

Built from a **verified** database backup, containing:

- the database backup and its manifest
- incident snapshots referenced by that backup
- the portable `.pt` model weights (not `.engine` — it is GPU/driver/TensorRT-specific)
- checksums and a missing-file report

**Never include** `.env`, session or JWT secrets, VMS/RTSP credentials, or any credential-bearing
configuration. Add an explicit test asserting the archive contains no `.env` and no `rtsp://` string.

Copies to a configured mounted destination. Physical NAS administration and security remain the
CDRRMO owner's responsibility (D-001 boundary rule); the demo targets a local or removable directory.

---

## Verification

```bash
uv run pytest backend/tests/test_maintenance.py
```

Manually, and record the timings — they are paper evidence:

1. With the backend running **and under write load** (run `seed_alerts_via_api.py` in a loop),
   `POST /api/system/backups`. It must succeed, and no request may fail with "database is locked".
   This is NFR-18's core claim.
2. `GET /api/system/backups` lists it as a valid restore point.
3. Corrupt a backup file's bytes → it stops being listed and cannot be selected for restore.
4. **Full restore drill.** Note the current incident count, restore an older backup through the
   PowerShell orchestrator, and confirm: services stop, an emergency backup is created, the database
   is replaced, `-wal`/`-shm` are gone, services come back, `/healthz/ready` passes, and the incident
   count matches the backup. **Time it — the target is 60 seconds.**
5. **Rollback drill.** Deliberately break startup (point `DATABASE_URL` at an unwritable path, or feed
   it a valid-but-empty database) and confirm the orchestrator restores the emergency backup and
   brings the original system back.
6. Path-traversal attempt: `POST /api/system/restores` with a backup id of `../../.env` → rejected
   before any filesystem access.
7. Restore attempt as an Operator → 403. As an Admin with a wrong password → 401, no flag file written.
8. Run the archive command; unzip it; confirm the model weights and snapshots are present and **no
   `.env` and no `rtsp://` string** appear anywhere.
9. Run the restart command; record backup duration and restart downtime separately.
10. `pnpm check`.

---

## Tests to write

| Area | Assertions |
|---|---|
| Online backup | succeeds during concurrent writes; produces a valid file; source unmodified |
| Atomicity | an interrupted backup leaves no file at the final path |
| Disk space | insufficient space aborts before starting and leaves prior backups intact |
| Concurrency | a second backup request → `409 CONFLICT_BUSY` |
| Validation | corrupt checksum, failed `integrity_check`, failed `foreign_key_check` each disqualify the restore point |
| Retention | pruning only after a valid new backup; restore candidates and emergency copies never pruned |
| Restore authz | Operator 403; wrong password 401; missing confirmation 422; **no flag file written on any failure** |
| Path safety | `../`, absolute paths, and UNC paths in a backup id are rejected |
| Restore flow | happy path replaces the DB and removes sidecars |
| Rollback | readiness failure triggers restoration of the emergency backup and a recorded rollback outcome |
| Restore state | outcome survives the restore because it is a file, not a table |
| Archive | required contents present; **`.env` and credential strings absent**; missing files reported |
| Audit | `BACKUP_TRIGGER` and `RESTORE_TRIGGER` written with no filesystem secrets |

## Paper test cases covered

NFR-16 (daily restart, under-10-second recovery — measured, reported honestly), NFR-18 (daily backups
without interrupting inference; 60-second admin recovery), TC-R-303 (3:00 AM restart back ingesting
in under 10s), TC-U-402 (WAL concurrency during backup).

The **bi-annual restore drill** procedure (pull the NAS backup into an isolated staging environment
and validate archive integrity plus the flag-and-restart architecture) is a documented manual
procedure, written up in P9's traceability matrix with the deployment owner named.

## Deliberately not in this package

Alembic revision compatibility checking is stubbed here (`revision: None` in the manifest) and
completed in P9, once migrations exist. Report exports are P6 — different concern, different
directory, do not share code with backups.
