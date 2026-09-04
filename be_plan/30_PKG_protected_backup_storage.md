# P30 — Protected external backup storage with degraded fallback

> **Branch:** `feat/be-p30-protected-backup-storage`  
> **Runs where:** main checkout for the final Windows/USB restore drill.  
> **Size:** XL, maintenance core + frontend + host scripts.  
> **Dependencies:** current main; code-independent from P28/P29.

## Goal and storage model

Database restore points and generated maintenance archives prefer an explicitly configured physical
device different from the live database device. If it is absent or unsafe, the system continues with
a visible same-device degraded backup. Existing local artifacts remain untouched.

Configuration:

```text
BACKUP_DIR=var/backups                  # local fallback + control state
ARCHIVE_DIR=var/archive                 # local fallback archives
PROTECTED_BACKUP_DIR=<absolute path>    # optional explicit external device path
PROTECTED_ARCHIVE_DIR=<absolute path>   # optional explicit external device path
```

Never auto-discover removable devices. Paths and physical identifiers never leave the server.

## Step 0 — architecture and platform probe

Read `CLAUDE.md`, P7/P18 maintenance contracts and code, this package, and edge cases §§1 and 6.
Introduce a small injected storage-target/physical-device provider:

- Windows: resolve the volume for a path and use native volume/disk-extent APIs to identify the
  physical disk. A second partition, junction, SUBST mapping, or folder mount on the DB disk is not
  protected. UNC/network paths are unsupported in this package.
- POSIX: compare the nearest existing ancestors' filesystem device identities.
- Missing, unwritable, full, same-device, or unverifiable protected paths are unavailable with a
  redacted structured reason; tests inject the provider rather than requiring two CI disks.

## Step 1 — dual-root backup and archive publishing

Keep one maintenance lease and all control/coordinator/restore state under local `BACKUP_DIR`.
Separate artifact roots from state roots throughout backup, verify, archive, CLI, route, and scheduler
code. A normal manual/scheduled backup:

1. tries protected storage;
2. cleans any unpublished protected temporary/orphan files on failure;
3. falls back locally and records `degraded` plus a reason;
4. fails only if both roots fail, preserving all existing valid artifacts.

Archives follow the same policy. Audit detail may contain tier/reason, never a path or device id.
Existing local backups are classified as degraded and are not copied or deleted.

## Step 2 — listing, scheduling, and API/UI contract

Scan both available roots. Add `storage_tier: 'protected'|'degraded'` to every backup item and require
`backup_id + storage_tier` in a restore request so duplicate ids cannot be confused. The frontend key
and selection must use both fields.

Maintenance status exposes protected availability/reason, overall protection state, latest protected
backup time, and protected-overdue state. When external media is absent, return fallback rows plus the
warning; never disguise it as an empty backup history.

A recent degraded backup satisfies operational daily continuity but not protected-backup freshness.
Startup/hourly catch-up creates a protected backup as soon as the device returns. Scheduled restart
continues after a valid degraded backup and records the warning; if both targets fail it stops before
services are shut down. Fix PowerShell/.env precedence so Python, the coordinator, and Scheduled Task
resolve the same paths. Update `.env.example` and deployment docs, never the real `.env`.

## Step 3 — restore safety under media loss

Before any swap, create and verify a local degraded emergency reserve. Verify the selected tier/id and
copy the selected database to a local restore temp before stopping/replacing the live database.

- Media lost before verification/copy: fail without touching the live DB.
- Media lost after local copy: continue safely.
- Readiness failure after swap: roll back from the local emergency reserve.
- Local emergency reserve unavailable: do not swap.
- Rollback failure: durable manual-intervention state; never report success.

Bound retention of pre-restore artifacts so they do not accumulate indefinitely.

## Step 4 — automated and live verification

Automated coverage includes same/different/unverifiable physical devices, partitions/junctions/SUBST,
missing/read-only/full media, protected-first/fallback/both-fail, atomic cleanup, duplicate ids,
combined listing, protected catch-up, scheduler decisions, archive tier, PowerShell precedence, media
loss before/after copy/swap, and rollback.

Run:

```powershell
uv run pytest backend/tests/test_maintenance.py backend/tests/test_maintenance_schedule.py backend/tests/test_restore_coordinator.py backend/tests/test_app_factory.py
pnpm --filter frontend test:run
pnpm full:check
```

Then, on a confirmed demo database and USB physical disk, record device identities; create a protected
backup under write load; verify list/audit/tier; perform dashboard restore; exercise automatic rollback;
remove USB to prove degraded fallback; reconnect it to prove protected catch-up; and generate a
protected archive. Record timings/evidence. Never touch a production database or edit `.env` secrets.

## Step 5 — paper sync and test tracker

Run paper sync against live artifacts. Amend the existing pending scheduler/NAS finding rather than
creating a duplicate, adding separate-device protected storage, degraded fallback, tiered restore,
local control/emergency state, and current archive behavior. Regenerate `paper_sync/TRACKER.md`; no
Drive writes before approval.

Prepare a separately approval-gated Test Execution Tracker manifest. The `Backup & Recovery` tab is
currently header-only; write the first five verified blank rows as `TC-BR-001` through `TC-BR-005`
for protected backup/list/validation, external restore/local rollback, degraded fallback warning,
reinsertion/catch-up/restart, and archive placement. Start each as `Not Executed`, preserve the Result
dropdown, and update only after real evidence. Also update AD-J04 and UAT Traceability NFR-18.

Every added/changed content cell gets the existing `#D9EAD3` fill only; preserve all other formatting,
validation, formulas, and links, then read back and visually verify affected ranges and Summary totals.

