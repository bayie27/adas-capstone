---
section: Frameworks and Libraries
page/s: "p. 163; p. 220"
required_revision: Document the in-process daily backup and host-level daily restart; correct the NAS storage claim
notes: NFR-16 and NFR-18 remain correct requirement text. The live audit item 1.12 and tracker row 31 still contain the obsolete "both unimplemented" premise. The maintenance status endpoint exposes the next scheduled backup and the last restart, not a next restart.
status: Not started
assigned_to: Daniboy
synced: false
---

## Where

The live defense Doc still contains the exact scheduler sentence at native Docs tab
t.y7ms6bhlk4qn, range 199235–199373, inside the Backend Layer paragraph
198590–199546. A fresh native PDF export on 2026-08-25 maps it to printed p. 163
(PDF page 164), not the p. 148 observed in the original snapshot.

The same live Doc has a separate backup-storage claim in the Maintenance and Support
Plan on printed p. 220 (PDF page 221). The live ADAS_Paper_Audit Doc still has the
obsolete §1.12 at tab t.0, heading range 31414–31490, and the canonical
🚩 Action Stream tracker still has the corresponding stale row at A31:H31.

## Changes

### 1. Defense paper — Frameworks and Libraries, Backend Layer (FastAPI)

Page/s: p. 163 (PDF page 164; live Docs range t.y7ms6bhlk4qn:199235–199373)

#### OLD

> Background tasks, including the automated hourly aggregation of raw hardware telemetry into historical trends, are managed by apscheduler.

#### NEW

Background tasks, including the automated hourly aggregation of raw hardware telemetry into historical trends and the automated daily database backup, are managed by apscheduler. The daily system restart is scheduled outside the application process by a host-level Windows Scheduled Task (or Linux systemd timer), and the administrative maintenance status endpoint exposes the latest and next scheduled backup plus the last recorded restart.

#### Evidence

The live paragraph contains the exact OLD text at Docs indices 199235–199373. The current implementation registers daily_backup and daily_backup_catch_up and performs a startup due-check in backend/app/main.py:259-280; the backup service implements the scheduled and catch-up paths in backend/app/services/maintenance_schedule.py:93-158. The Windows host scheduler is registered by scripts/register-maintenance-task.ps1:3-24,153-187; the Linux production target uses deploy/systemd/adas-maintenance.timer:1-14 and backend/scripts/daily_restart.sh:1-20,40-63.

GET /api/system/maintenance/status is implemented at backend/app/api/routes/maintenance.py:409-438. Its schema has next_scheduled_backup_at and last_restart, but no next-restart field (backend/app/schemas/maintenance.py:84-92). The scheduler and status behavior are covered by backend/tests/test_maintenance_schedule.py:298-342 and backend/tests/test_maintenance.py:1176-1244,1304-1334.

#### Proposed comment (Defense paper gate)

Previous: Background tasks, including the automated hourly aggregation of raw hardware telemetry into historical trends, are managed by apscheduler.

Codex ID: adas-paper-sync-2026-08-25-scheduler-jobs-and-daily-restart-01

Done by Codex.

### 2. Defense paper — Maintenance and Support Plan, Disaster Recovery Protocols

Page/s: p. 220 (PDF page 221; live Docs range t.y7ms6bhlk4qn:251535–252342)

#### OLD

> Disaster Recovery Protocols: To guarantee operational resilience against catastrophic hardware failures or severe logical corruption, the Administrators are required to execute a manual "Bi-Annual Restore Drill." This proactive maintenance protocol involves manually download the scheduled database backup and its associated visual snapshots from the air-gapped Network Attached Storage (NAS). Supervisors must then deploy this backup into a secure, localized staging environment entirely isolated from the production network. This drill strictly validates the integrity of the archived data, verifies the efficacy of the "Flag and Restart" restoration architecture, and ensures that agency personnel maintain the technical readiness required to execute a rapid system recovery during a critical emergency.

#### NEW

Disaster Recovery Protocols: To guarantee operational resilience against catastrophic hardware failures or severe logical corruption, the Administrators are required to execute a manual "Bi-Annual Restore Drill." This proactive maintenance protocol involves manually retrieving a validated database backup and its associated visual snapshots from the system's generated maintenance archive. Supervisors must then deploy this backup into a secure, localized staging environment entirely isolated from the production network. This drill strictly validates the integrity of the archived data, verifies the efficacy of the "Flag and Restart" restoration architecture, and ensures that agency personnel maintain the technical readiness required to execute a rapid system recovery during a critical emergency.

#### Evidence

This is an incidental storage-location correction found while tracing the daily backup. The implementation stores database backups under BACKUP_DIR and snapshots under SNAPSHOT_ROOT (backend/app/core/config.py:60-68). backend/app/maintenance/archive.py:1-7,104-179 builds a generated archive from a verified database backup, its manifest, and the snapshots referenced by that backup; backend/app/maintenance/cli.py:193-214 writes it under the configured archive directory. No code establishes an external NAS integration, so the paper should not present NAS as an implemented storage location.

#### Proposed comment (Defense paper gate)

Previous: Disaster Recovery Protocols: To guarantee operational resilience against catastrophic hardware failures or severe logical corruption, the Administrators are required to execute a manual "Bi-Annual Restore Drill." This proactive maintenance protocol involves manually download the scheduled database backup and its associated visual snapshots from the air-gapped Network Attached Storage (NAS). Supervisors must then deploy this backup into a secure, localized staging environment entirely isolated from the production network. This drill strictly validates the integrity of the archived data, verifies the efficacy of the "Flag and Restart" restoration architecture, and ensures that agency personnel maintain the technical readiness required to execute a rapid system recovery during a critical emergency.

Codex ID: adas-paper-sync-2026-08-25-scheduler-jobs-and-daily-restart-02

Done by Codex.

### 3. ADAS_Paper_Audit — §1.12

Page/s: unconfirmed (live Docs tab t.0; heading range 31414–31490)

#### OLD

> 1.12 NFR-16 (daily restart) and NFR-18 (daily backup) are both unimplemented
>
> NFR-16 — "the system shall automatically restart every 24 hours … at 3:00 AM, completing memory flush and recovery in under 10 seconds." No such job exists. backend/app/main.py:145-242 registers every scheduled job — cooldown sweep, snooze sweep, expired-session cleanup, five health jobs, export-artifact cleanup, WS session revalidation — and none is a daily restart.
>
> NFR-18 — "The system shall execute automated daily backups of the SQLite database…" Equally unscheduled. There is no backup job in main.py; backups run only via POST /api/system/backups or an external orchestrator calling python -m app.maintenance (backend/app/maintenance/cli.py:316-355, which takes --origin manual|scheduled, i.e. expects to be driven by cron/systemd).
>
> And MAINTENANCE_HOUR_LOCAL (default 3) is dead config — zero references anywhere in app/ outside config.py:117. It looks like the hook for both requirements and was never wired up.
>
> Compounding this, the Maintenance and Support Plan refers to downloading "the scheduled database backup and its associated visual snapshots from the air-gapped Network Attached Storage (NAS)". Neither the schedule nor any NAS integration exists; BACKUP_DIR is var/backups on the server itself (config.py:62).
>
> These are code gaps, not documentation errors. Two honest paths for each: implement the scheduled job (a trigger="cron", hour=MAINTENANCE_HOUR_LOCAL entry alongside the existing jobs, which is a small change given the setting already exists), or restate the requirements as orchestrator-driven with the operational procedure documented. Which is right is a team decision — flagged here so it isn't discovered live.

#### NEW

1.12 NFR-16 and NFR-18 are implemented; the paper's maintenance description is incomplete

NFR-16 and NFR-18 are now satisfied. The daily backup is scheduled by the application, while the daily restart is scheduled by the host because it must stop and start the application services. The paper's Frameworks and Libraries description names only hourly telemetry aggregation and should be expanded to name both mechanisms and the maintenance status information they expose. This is documentation drift, not an unimplemented-requirement finding.

#### Evidence

backend/app/main.py:259-280 registers the in-process daily backup cron job, its hourly catch-up job, and the lifespan-startup due-check. scripts/register-maintenance-task.ps1:13-24,153-187 registers the Windows task DailyRestart; deploy/systemd/adas-maintenance.timer:1-14 is the Linux production-target timer. The host-level split is intentional because the restart orchestrator must stop and start the backend and AI-engine processes.

The status route returns last_scheduled_backup, next_scheduled_backup_at, backup_overdue, maintenance_hour_local, maintenance_timezone, last_restart, and latest_restore (backend/app/api/routes/maintenance.py:409-438; backend/app/schemas/maintenance.py:84-92). It does not expose a next restart time.

The paper's NFR-16 and NFR-18 text is still correct on printed pp. 74–75 (PDF pages 75–76), and no separate scheduler mechanism is described in Deployment and Implementation. The restore narrative on printed pp. 152–153 (PDF pages 153–154) describes operator-initiated restore orchestration, not the unattended daily restart. The separate NAS wording is covered by change 2 in this finding.

#### Proposed comment (Audit + tracker gate)

Previous: 1.12 NFR-16 (daily restart) and NFR-18 (daily backup) are both unimplemented

NFR-16 — "the system shall automatically restart every 24 hours … at 3:00 AM, completing memory flush and recovery in under 10 seconds." No such job exists. backend/app/main.py:145-242 registers every scheduled job — cooldown sweep, snooze sweep, expired-session cleanup, five health jobs, export-artifact cleanup, WS session revalidation — and none is a daily restart.

NFR-18 — "The system shall execute automated daily backups of the SQLite database…" Equally unscheduled. There is no backup job in main.py; backups run only via POST /api/system/backups or an external orchestrator calling python -m app.maintenance (backend/app/maintenance/cli.py:316-355, which takes --origin manual|scheduled, i.e. expects to be driven by cron/systemd).

And MAINTENANCE_HOUR_LOCAL (default 3) is dead config — zero references anywhere in app/ outside config.py:117. It looks like the hook for both requirements and was never wired up.

Compounding this, the Maintenance and Support Plan refers to downloading "the scheduled database backup and its associated visual snapshots from the air-gapped Network Attached Storage (NAS)". Neither the schedule nor any NAS integration exists; BACKUP_DIR is var/backups on the server itself (config.py:62).

These are code gaps, not documentation errors. Two honest paths for each: implement the scheduled job (a trigger="cron", hour=MAINTENANCE_HOUR_LOCAL entry alongside the existing jobs, which is a small change given the setting already exists), or restate the requirements as orchestrator-driven with the operational procedure documented. Which is right is a team decision — flagged here so it isn't discovered live.

Codex ID: adas-paper-sync-2026-08-25-scheduler-jobs-and-daily-restart-03

Done by Codex.

### 4. Tracker Sheet — 🚩 Action Stream!A31:H31

Page/s: 🚩 Action Stream!A31:H31

#### OLD

> Major | NFR-16, NFR-18 | 65 | 1.12 NFR-16 (daily restart) and NFR-18 (daily backup) are both unimplemented | Either implement the scheduled cron jobs, or restate the requirements as orchestrator-driven. | Completed | Daniboy | blank

#### NEW

Major | Frameworks and Libraries, Maintenance and Support Plan, NFR-16, NFR-18 | 74-75, 163, 220 | 1.12 Replace the obsolete unimplemented note; document the in-process daily backup and host-level daily restart | NFR-16 and NFR-18 are implemented. Update Frameworks and Libraries p. 163 and correct the separate air-gapped NAS storage claim on p. 220. ADAS_Paper_Audit §1.12 also needs replacement. | Not started | Daniboy | blank

#### Evidence

The live Sheet metadata identifies 🚩 Action Stream as the canonical tab (sheetId 1620600289). The full row was read from A31:H31 on 2026-08-25; the H-column Reviewed by cell is blank and is preserved. The duplicate Copy of 🚩 Action Stream row 31 was also read but is not targeted because existing paper-sync updates use the canonical 🚩 Action Stream tab.

The proposed page values use the current live rendered pagination: NFR-16/NFR-18 are printed pp. 74–75, the primary scheduler sentence is p. 163, and the separate maintenance-plan sentence is p. 220.

#### Proposed comment (Audit + tracker gate)

Previous: Major | NFR-16, NFR-18 | 65 | 1.12 NFR-16 (daily restart) and NFR-18 (daily backup) are both unimplemented | Either implement the scheduled cron jobs, or restate the requirements as orchestrator-driven. | Completed | Daniboy | blank

Codex ID: adas-paper-sync-2026-08-25-scheduler-jobs-and-daily-restart-04

Done by Codex.

## Verified unchanged sites

- NFR-16 and NFR-18 are written as shall requirements and are now met; no defense-paper replacement is proposed for either requirement.
- Use Case 12 already distinguishes scheduled and manual backups, and Use Case 13 plus the restore architecture already describe operator-initiated restore orchestration. These are not the unattended daily scheduler and do not need wording changes for this finding.
- TC-R-303 describes the restart scenario and expected result but does not claim that APScheduler owns the restart; it remains unchanged.
- Deployment and Implementation contains no separate scheduler-ownership sentence. The Frameworks and Libraries replacement is the single primary implementation-narrative site.

## Approval gates

1. **Defense paper** — blocks 1–2 and their attached Previous comments.
2. **ADAS_Paper_Audit plus tracker Sheet** — blocks 3–4 and their attached Previous comments.
3. **Standalone comments** — none proposed.
