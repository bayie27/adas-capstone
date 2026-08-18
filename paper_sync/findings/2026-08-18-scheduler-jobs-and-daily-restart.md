---
section: Frameworks and Libraries
page/s: unconfirmed
required_revision: Name the daily backup job and the host-level daily restart, not only telemetry aggregation
notes: NFR-16 and NFR-18 requirement text needs no change — both are now implemented and met. Check whether Deployment & Implementation describes the restart mechanism.
status: Not started
assigned_to: Daniboy
synced: false
---

## Where

Frameworks and Libraries, observed p. 148 on 2026-08-18. Not yet verified against the live Doc — confirm the quote before applying.

## OLD

> Background tasks, including the automated hourly aggregation of raw hardware telemetry into historical trends, are managed by apscheduler.

## NEW

Background tasks are managed by apscheduler, which runs the automated hourly aggregation of raw hardware telemetry into historical trends and the automated daily database backup. The daily system restart runs outside the application process, as a host-level scheduled task, since a restart must stop and start the application services themselves. Both the daily backup and the restart report their last and next run through an administrative maintenance status endpoint.

## Justification

The sentence names telemetry aggregation as the scheduler's work at a point when it was the only scheduled job. Two more mechanisms have since shipped, and the sentence now understates the system rather than describing it wrongly.

- `backend/app/main.py:259-267` registers the `daily_backup` cron job at `MAINTENANCE_HOUR_LOCAL`; `backend/app/main.py:268-271` registers `daily_backup_catch_up`. Both call `run_daily_backup` in `backend/app/services/maintenance_schedule.py:93`.
- The daily restart is **not** an apscheduler job. `scripts/register-maintenance-task.ps1:68` registers a Windows Scheduled Task at path `\ADAS\DailyRestart`, which drives `scripts/adas-maintenance.ps1`. It has to live outside the process because it stops and starts that process.
- `backend/app/api/routes/maintenance.py:401` serves `GET /api/system/maintenance/status`, returning `last_scheduled_backup`, `next_scheduled_backup_at`, and `backup_overdue` (`backend/app/schemas/maintenance.py:85-88`).

NFR-16 (p. 68) and NFR-18 (p. 69) are written as `shall` requirements and are now satisfied, so **their text needs no change** — this is a description gap in the implementation narrative, not a false requirement.

This supersedes the premise of the old tracker row 1.12, which read "NFR-16 (daily restart) and NFR-18 (daily backup) are both unimplemented" and offered "either implement the scheduled cron jobs, or restate the requirements". They were implemented; that row is void.

## Propagation

- **Frameworks and Libraries, p. 148** — the sentence quoted above. Primary site.
- **Deployment & Implementation** — check whether it describes the restart mechanism at all. A search of the snapshot found no mention of Task Scheduler, systemd timers, or cron outside the restore orchestration narrative on pp. 139–140, which is a different mechanism (operator-initiated restore, not the unattended daily restart).
- **NFR-16 (p. 68), NFR-18 (p. 69)** — verified correct, no change needed. Recorded so neither is re-raised.
- **TC-U-405 (p. 169)** — calls the rollup an "hourly cron job". Consistent with apscheduler in substance; only worth touching if the surrounding text is being edited anyway.
