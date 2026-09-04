---
section: Frameworks and Libraries
page/s: "p. 163; p. 220"
required_revision: Document the in-process daily backup, host-level daily restart, protected external storage with degraded fallback, tiered restore safety, and current archive behavior; correct the NAS storage claim
notes: NFR-16 and NFR-18 remain correct requirement text. The live audit item 1.12 and tracker row 31 still contain the obsolete "both unimplemented" premise. P30 adds explicit protected and local-degraded storage tiers, tier-aware restore selection, a local emergency reserve, and protected-first archive publishing. The 2026-09-04 isolated-clone drill passed protected backup/list/restore/rollback/fallback/catch-up checks; archive publication was blocked by the credential scan, and live tracker/Drive updates remain pending.
status: Not started
assigned_to: Daniboy
synced: false
---

## Where

The live defense Doc still contains the exact scheduler sentence at native Docs tab
t.y7ms6bhlk4qn, range 197040–197178, inside the Backend Layer paragraph
196395–197351. A fresh native PDF export maps it to printed p. 163 (PDF page 164),
not the p. 148 observed in the original snapshot.

The same live Doc has a separate backup-storage claim in the Maintenance and Support
Plan on printed p. 220 (PDF page 221; live range 248561–250173). The live
ADAS_Paper_Audit Doc still has the obsolete §1.12 at tab t.0, heading range
31554–32865, and the canonical
🚩 Action Stream tracker still has the corresponding stale row at A31:H31.

## Changes

### 1. Defense paper — Frameworks and Libraries, Backend Layer (FastAPI)

Page/s: p. 163 (PDF page 164; live Docs range t.y7ms6bhlk4qn:197040–197178; paragraph 196395–197351)

#### OLD

> Background tasks, including the automated hourly aggregation of raw hardware telemetry into historical trends, are managed by apscheduler.

#### NEW

Background tasks, including the automated hourly aggregation of raw hardware telemetry into historical trends and the automated daily database backup, are managed by apscheduler. The daily system restart is scheduled outside the application process by a host-level Windows Scheduled Task (or Linux systemd timer). The administrative maintenance status endpoint exposes the latest and next scheduled backup, protected-backup availability and freshness, and the last recorded restart; when the configured protected target is unavailable, the system continues with a visible local degraded backup.

#### Evidence

The live paragraph contains the exact OLD text at Docs indices 197040–197178 inside paragraph 196395–197351. The current implementation registers daily_backup and daily_backup_catch_up and performs a startup due-check in backend/app/main.py:259-280; the backup service implements the scheduled and catch-up paths in backend/app/services/maintenance_schedule.py:93-158. Protected-target probing and path-free tier/reason handling are implemented in backend/app/maintenance/storage.py:1-384 and backend/app/maintenance/backup.py:475-610. The Windows host scheduler is registered by scripts/register-maintenance-task.ps1:3-24,153-187; the Linux production target uses deploy/systemd/adas-maintenance.timer:1-14 and backend/scripts/daily_restart.sh:1-20,40-63.

GET /api/system/maintenance/status is implemented at backend/app/api/routes/maintenance.py:409-438 and now returns protected_backup_available, protected_backup_reason, protection_state, latest_protected_backup, and protected_backup_overdue alongside the existing backup/restart fields; the schema is in backend/app/schemas/maintenance.py:84-138. The scheduler and status behavior are covered by backend/tests/test_maintenance_schedule.py:298-342, backend/tests/test_maintenance.py:1176-1244,1304-1334, and backend/tests/test_protected_backup_storage.py:1-520.

#### Proposed comment (Defense paper gate)

Previous: Background tasks, including the automated hourly aggregation of raw hardware telemetry into historical trends, are managed by apscheduler.

Codex ID: PS-20260818-SCHEDULER-JOBS-AND-DAILY-RESTART

Done by Codex.

### 2. Defense paper — Maintenance and Support Plan, Disaster Recovery Protocols

Page/s: p. 220 (PDF page 221; live Docs range t.y7ms6bhlk4qn:248561–250173)

#### OLD

> Disaster Recovery Protocols: To guarantee operational resilience against catastrophic hardware failures or severe logical corruption, the Administrators are required to execute a manual "Bi-Annual Restore Drill." This proactive maintenance protocol involves manually download the scheduled database backup and its associated visual snapshots from the air-gapped Network Attached Storage (NAS). Supervisors must then deploy this backup into a secure, localized staging environment entirely isolated from the production network. This drill strictly validates the integrity of the archived data, verifies the efficacy of the "Flag and Restart" restoration architecture, and ensures that agency personnel maintain the technical readiness required to execute a rapid system recovery during a critical emergency.

#### NEW

Disaster Recovery Protocols: To guarantee operational resilience against catastrophic hardware failures or severe logical corruption, the Administrators are required to execute a manual "Bi-Annual Restore Drill." This proactive maintenance protocol involves manually retrieving a validated database backup and its associated visual snapshots from the system's generated maintenance archive, preferring the explicitly configured protected external storage when it is available and using the local degraded archive otherwise. Supervisors must then deploy this backup into a secure, localized staging environment entirely isolated from the production network. This drill strictly validates the integrity of the archived data, verifies the efficacy of the "Flag and Restart" restoration architecture, and ensures that agency personnel maintain the technical readiness required to execute a rapid system recovery during a critical emergency.

#### Evidence

This is an incidental storage-location correction found while tracing the daily backup. The implementation stores database backups under BACKUP_DIR and snapshots under SNAPSHOT_ROOT (backend/app/core/config.py:60-72). backend/app/maintenance/archive.py:1-7,130-309 builds a generated archive from a verified database backup, its manifest, and the snapshots referenced by that backup, using protected-first publication with local degraded fallback; backend/app/maintenance/cli.py:332-382 selects the backup's source tier and reports the archive tier without exposing paths. No code establishes an external NAS integration, so the paper should not present NAS as an implemented storage location. The available P30 configuration is an explicitly mounted path checked by a physical-device probe, not removable-media autodiscovery.

#### Proposed comment (Defense paper gate)

Previous: Disaster Recovery Protocols: To guarantee operational resilience against catastrophic hardware failures or severe logical corruption, the Administrators are required to execute a manual "Bi-Annual Restore Drill." This proactive maintenance protocol involves manually download the scheduled database backup and its associated visual snapshots from the air-gapped Network Attached Storage (NAS). Supervisors must then deploy this backup into a secure, localized staging environment entirely isolated from the production network. This drill strictly validates the integrity of the archived data, verifies the efficacy of the "Flag and Restart" restoration architecture, and ensures that agency personnel maintain the technical readiness required to execute a rapid system recovery during a critical emergency.

Codex ID: PS-20260818-SCHEDULER-JOBS-AND-DAILY-RESTART

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

NFR-16 and NFR-18 are now satisfied. The daily backup is scheduled by the application, while the daily restart is scheduled by the host because it must stop and start the application services. Normal backups prefer the explicitly configured protected physical device and continue under a visible local degraded tier when that target is absent or unsafe; the backup list and restore request identify both the storage tier and backup id. Restore safety keeps control state and a verified pre-restore emergency reserve on the local device, and generated archives follow the same protected-first/degraded-fallback policy. The paper's Frameworks and Libraries description should name these mechanisms and the maintenance status information they expose. This is documentation drift, not an unimplemented-requirement finding.

#### Evidence

backend/app/main.py:259-280 registers the in-process daily backup cron job, its hourly catch-up job, and the lifespan-startup due-check. scripts/register-maintenance-task.ps1:13-24,153-187 registers the Windows task DailyRestart; deploy/systemd/adas-maintenance.timer:1-14 is the Linux production-target timer. The host-level split is intentional because the restart orchestrator must stop and start the backend and AI-engine processes.

The status route returns last_scheduled_backup, next_scheduled_backup_at, backup_overdue, maintenance_hour_local, maintenance_timezone, last_restart, latest_restore, protected-backup availability/reason, protection_state, latest_protected_backup, and protected_backup_overdue (backend/app/api/routes/maintenance.py:409-438,598-732; backend/app/schemas/maintenance.py:84-138). It does not expose a next restart time. Restore state includes the selected tier and the local emergency tier, and the coordinator can leave a durable manual_intervention state when rollback fails (backend/app/maintenance/restore.py:67-112,520-790; backend/app/maintenance/coordinator.py:62-80).

The paper's NFR-16 and NFR-18 text is still correct on printed pp. 74–75 (PDF pages 75–76), and no separate scheduler mechanism is described in Deployment and Implementation. The restore narrative on printed pp. 152–153 (PDF pages 153–154) describes operator-initiated restore orchestration, not the unattended daily restart; the tier-aware selection and local emergency reserve are the P30 additions that should be reflected in the maintenance description. The separate NAS wording is covered by change 2 in this finding.

#### Proposed comment (Audit + tracker gate)

Previous: 1.12 NFR-16 (daily restart) and NFR-18 (daily backup) are both unimplemented

NFR-16 — "the system shall automatically restart every 24 hours … at 3:00 AM, completing memory flush and recovery in under 10 seconds." No such job exists. backend/app/main.py:145-242 registers every scheduled job — cooldown sweep, snooze sweep, expired-session cleanup, five health jobs, export-artifact cleanup, WS session revalidation — and none is a daily restart.

NFR-18 — "The system shall execute automated daily backups of the SQLite database…" Equally unscheduled. There is no backup job in main.py; backups run only via POST /api/system/backups or an external orchestrator calling python -m app.maintenance (backend/app/maintenance/cli.py:316-355, which takes --origin manual|scheduled, i.e. expects to be driven by cron/systemd).

And MAINTENANCE_HOUR_LOCAL (default 3) is dead config — zero references anywhere in app/ outside config.py:117. It looks like the hook for both requirements and was never wired up.

Compounding this, the Maintenance and Support Plan refers to downloading "the scheduled database backup and its associated visual snapshots from the air-gapped Network Attached Storage (NAS)". Neither the schedule nor any NAS integration exists; BACKUP_DIR is var/backups on the server itself (config.py:62).

These are code gaps, not documentation errors. Two honest paths for each: implement the scheduled job (a trigger="cron", hour=MAINTENANCE_HOUR_LOCAL entry alongside the existing jobs, which is a small change given the setting already exists), or restate the requirements as orchestrator-driven with the operational procedure documented. Which is right is a team decision — flagged here so it isn't discovered live.

Codex ID: PS-20260818-SCHEDULER-JOBS-AND-DAILY-RESTART

Done by Codex.

### 4. Tracker Sheet — 🚩 Action Stream!A31:H31

Page/s: 🚩 Action Stream!A31:H31

#### OLD

> Major | NFR-16, NFR-18 | 65 | 1.12 NFR-16 (daily restart) and NFR-18 (daily backup) are both unimplemented | Either implement the scheduled cron jobs, or restate the requirements as orchestrator-driven. | Completed | Daniboy | blank

#### NEW

Major | Frameworks and Libraries, Maintenance and Support Plan, NFR-16, NFR-18 | 74-75, 163, 220 | 1.12 Replace the obsolete unimplemented note; document scheduled restart/backup ownership, protected storage with degraded fallback, tier-aware restore safety, and current archive behavior | NFR-16 and NFR-18 are implemented. Update Frameworks and Libraries p. 163, correct the separate air-gapped NAS storage claim on p. 220, and describe protected-first/local-degraded backup, tiered restore, local emergency reserve, and protected-first archive behavior. ADAS_Paper_Audit §1.12 also needs replacement. | Not started | Daniboy | blank

#### Evidence

The live Sheet metadata identifies 🚩 Action Stream as the canonical tab (sheetId 1620600289). The full row was read from A31:H31 on 2026-09-03; the H-column Reviewed by cell is blank and is preserved. The duplicate Copy of 🚩 Action Stream row 31 was also read but is not targeted because existing paper-sync updates use the canonical 🚩 Action Stream tab.

The proposed page values use the current live rendered pagination: NFR-16/NFR-18 are printed pp. 74–75, the primary scheduler sentence is p. 163, and the separate maintenance-plan sentence is p. 220.

#### Proposed comment (Audit + tracker gate)

Previous: Major | NFR-16, NFR-18 | 65 | 1.12 NFR-16 (daily restart) and NFR-18 (daily backup) are both unimplemented | Either implement the scheduled cron jobs, or restate the requirements as orchestrator-driven. | Completed | Daniboy | blank

Codex ID: PS-20260818-SCHEDULER-JOBS-AND-DAILY-RESTART

Done by Codex.

### 5. ADAS Test Execution Tracker — `Backup & Recovery`!A2:J6

Page/s: `Backup & Recovery`!A2:J6 (sheetId 3000007)

#### OLD

The first five data rows are blank. The header row is `Test ID | Requirement / Objective | Scenario | Preconditions / Steps | Expected Result / Acceptance | Date Executed | Result | Actual Result / Notes | Evidence Link | Defect / Retest Note`. The blank `Result` cells retain the existing validation options `Not Executed`, `Pass`, `Fail`, `Blocked`, and `Retest Required`.

#### NEW

| Test ID   | Requirement / Objective | Scenario                                               | Preconditions / Steps                                                                                                                                                                                       | Expected Result / Acceptance                                                                                                                                                                                                             | Date Executed | Result       | Actual Result / Notes                                                | Evidence Link | Defect / Retest Note |
| --------- | ----------------------- | ------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------- | ------------ | -------------------------------------------------------------------- | ------------- | -------------------- |
| TC-BR-001 | NFR-18                  | Protected backup, combined listing, and validation     | Mount the configured protected target after the separate-physical-device probe passes. Create a backup under normal write load. Inspect its manifest and the combined backup listing.                       | The protected artifact has a Valid manifest; the listing retains protected and local rows with tier labels; no path or device identifier is exposed.                                                                                     | blank         | Not Executed | Automated coverage exists; live physical-device evidence is pending. | blank         | blank                |
| TC-BR-002 | NFR-18                  | External restore and local rollback                    | Select a protected backup by exact storage tier plus backup id. Run separate restore drills with media loss before verification/copy and after the local restore copy. Exercise readiness-failure rollback. | Pre-copy media loss fails without a live-database swap; post-copy loss can finish; readiness failure rolls back from a verified local emergency reserve; rollback failure is durable manual_intervention and never success.              | blank         | Not Executed | Automated coverage exists; live physical-device evidence is pending. | blank         | blank                |
| TC-BR-003 | NFR-18                  | Degraded fallback warning                              | Use a missing, read-only, full, or same-device protected target and run a manual or scheduled backup.                                                                                                       | The local fallback is created and listed as degraded with a path-free reason and visible warning; existing local artifacts remain intact; both-target failure returns failure without lifecycle shutdown.                                | blank         | Not Executed | Automated coverage exists; live physical-device evidence is pending. | blank         | blank                |
| TC-BR-004 | NFR-18                  | Reinsertion, protected catch-up, and scheduled restart | Create a recent degraded scheduled backup while protected storage is unavailable. Reconnect the protected target and run startup/hourly catch-up and the scheduled-restart backup phase.                    | Recent degraded continuity is accepted; protected overdue remains visible and one protected catch-up occurs after reinsertion; restart continues after a valid degraded backup and aborts before service stop only if both targets fail. | blank         | Not Executed | Automated coverage exists; live physical-device evidence is pending. | blank         | blank                |
| TC-BR-005 | NFR-18                  | Protected archive placement and contents               | With a valid backup and referenced snapshots, generate an archive while the protected archive target is available, then repeat with it unavailable.                                                         | Archive publication follows protected-first/degraded-fallback, includes the database, manifest, snapshots, and portable model, excludes credentials, and reports tier/reason without paths.                                              | blank         | Not Executed | Automated coverage exists; live physical-device evidence is pending. | blank         | blank                |

#### Evidence

The read-only pre-write Sheet readback on 2026-09-03 returned only the header in `Backup & Recovery`!A1:J6; rows 2–6 were blank while the `Result` column validation existed. The automated P30 coverage is in backend/tests/test_protected_backup_storage.py:1-643. The 2026-09-04 drill used a separate healthy SanDisk USB disk as D: and an isolated clone of the demo database; the real `adas.db`, existing local backups, and the user's pending tracker changes were not used as drill state. The proposed rows preserve the existing validation and leave Sheet execution/result/evidence fields pending until the separately approved write.

#### Proposed comment (Test tracker gate)

Previous: `Backup & Recovery`!A2:J6 was blank; the `Result` cells retained the existing validation list.

Codex ID: PS-20260818-SCHEDULER-JOBS-AND-DAILY-RESTART

Done by Codex.

### 6. ADAS Test Execution Tracker — `UAT Journeys`!D14, G14 (AD-J04)

Page/s: `UAT Journeys`!D14, G14

#### OLD

`D14`

```text
System Handler
1. Use the isolated UAT environment after all Operator sessions and AD-J01–AD-J03.
2. Check readiness: Invoke-RestMethod http://localhost:8000/healthz/ready
3. Ensure there is no Unverified alert before opening Maintenance.
4. Prepare one known historical incident and the expected camera configuration.
5. Mark the new manual backup created in this stage as the restore target.

Logger
1. Record the known historical incident and expected camera configuration.

Facilitator
1. Keep the Administrator password available only to the assigned participant.
```

`G14`

```text
1. Administrator-specific Help Center guidance is retrievable.
2. Only the Administrator can initiate backup/restore.
3. The newly created backup reaches Valid before selection.
4. The exact same backup is restored, preventing loss of the completed UAT participant accounts, actions, audit evidence, and prepared state.
5. Password and exact-text safeguards work.
6. Service returns Ready; participant understanding is evaluated here, while the strict 60-second NFR-18 measurement remains in the technical Backup & Recovery activity.
7. Any failure/deviation is recorded.
```

#### NEW

`D14`

```text
System Handler
1. Use the isolated UAT environment after all Operator sessions and AD-J01–AD-J03.
2. Check readiness: Invoke-RestMethod http://localhost:8000/healthz/ready
3. Ensure there is no Unverified alert before opening Maintenance.
4. Prepare one known historical incident and the expected camera configuration.
5. Record the new manual backup's exact storage tier and backup id; mark that tier/id as the restore target.

Logger
1. Record the known historical incident and expected camera configuration.

Facilitator
1. Keep the Administrator password available only to the assigned participant.
```

`G14`

```text
1. Administrator-specific Help Center guidance is retrievable.
2. Only the Administrator can initiate backup/restore.
3. The newly created backup reaches Valid before selection and its storage tier is recorded.
4. The exact same storage tier and backup id are restored, preventing loss of the completed UAT participant accounts, actions, audit evidence, and prepared state.
5. Password and exact-text safeguards work.
6. Service returns Ready; participant understanding is evaluated here, while the strict 60-second NFR-18 measurement remains in the technical Backup & Recovery activity.
7. Any failure/deviation is recorded, including a visible degraded-storage warning when the protected target is unavailable.
```

#### Evidence

The exact AD-J04 row was read from `UAT Journeys`!A14:I14 on 2026-09-03. The current journey names the new backup but does not record the required P30 storage tier, so only D14 and G14 are proposed for change. The isolated-clone restore/rollback evidence below supports the intended journey but does not substitute for a dashboard participant run; the `Result`, `Assistance`, `Notes`, and `Evidence` fields are not changed by this local finding.

#### Proposed comment (Test tracker gate)

Previous: D14 — “Mark the new manual backup created in this stage as the restore target.” G14 — “The newly created backup reaches Valid before selection.” and “The exact same backup is restored, preventing loss of the completed UAT participant accounts, actions, audit evidence, and prepared state.”

Codex ID: PS-20260818-SCHEDULER-JOBS-AND-DAILY-RESTART

Done by Codex.

### 7. ADAS Test Execution Tracker — `UAT Traceability`!D38, E38, G38 (NFR-18)

Page/s: `UAT Traceability`!D38, E38, G38

#### OLD

`D38`: `AD-J04; AD-J05; Backup & Recovery`

`E38`: `Execution Log / Session Control; linked evidence`

`G38`: `UAT evaluates understandable backup selection, restoration safeguards, restored state, and fresh post-recovery alerting. The strict 60-second recovery measurement remains in the technical Backup & Recovery activity.`

#### NEW

`D38`: `AD-J04; AD-J05; Backup & Recovery (TC-BR-001–TC-BR-005)`

`E38`: `Backup & Recovery; Execution Log / Session Control; linked evidence`

`G38`: `UAT evaluates understandable tier-labeled backup selection, restoration safeguards, restored state, and fresh post-recovery alerting. Protected-versus-degraded fallback warnings and the local rollback reserve are covered by the technical Backup & Recovery activity; the strict 60-second recovery measurement remains there.`

#### Evidence

The exact NFR-18 row was read from `UAT Traceability`!A38:G38 on 2026-09-03. Its current mapping already includes AD-J04, AD-J05, and Backup & Recovery; the proposed change names the five P30 technical rows and clarifies that tier-aware fallback and rollback evidence belongs to the technical activity. No live Sheet write was made.

#### Proposed comment (Test tracker gate)

Previous: D38 — `AD-J04; AD-J05; Backup & Recovery`. E38 — `Execution Log / Session Control; linked evidence`. G38 — `UAT evaluates understandable backup selection, restoration safeguards, restored state, and fresh post-recovery alerting. The strict 60-second recovery measurement remains in the technical Backup & Recovery activity.`

Codex ID: PS-20260818-SCHEDULER-JOBS-AND-DAILY-RESTART

Done by Codex.

## Live drill evidence — 2026-09-04

The drill ran against a dedicated local clone of the demo database, with process-scoped `DATABASE_URL`, `BACKUP_DIR`, `ARCHIVE_DIR`, `LOG_DIR`, `PROTECTED_BACKUP_DIR`, and `PROTECTED_ARCHIVE_DIR`. The real repository `adas.db`, its existing `var/backups` artifacts, the real `.env`, and the user's modified/untracked paper files were not changed. Windows read-only inventory confirmed disk 0 as the internal Intel NVMe and disk 1 as a healthy SanDisk Cruzer Blade USB device mounted as D:; serial values were verified for separation but were not copied into the finding or archive.

| Drill activity                      | Evidence                                                                                                                                                                                                                                                                                                                       | Result                                      |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------- |
| Protected backup, list, and verify  | Direct protected backup `2e9db8e7924f411cbfdef176c9e4355e`; full verify passed checksum, integrity, and foreign-key checks. Combined listing retained protected and degraded rows.                                                                                                                                             | Pass                                        |
| Scheduler-owned audit               | `73bb56aae18d4f9f9fa6d3a9e09e4ba4` was audited with `trigger=live_drill`, `storage_tier=protected`, `result=success`.                                                                                                                                                                                                          | Pass                                        |
| Protected restore and local reserve | Restore of `73bb56aae18d4f9f9fa6d3a9e09e4ba4` reached `db_restored`; local emergency reserve `df04a2d0d99146779688b567f7811747` was `degraded`. A clone-only marker disappeared after the swap.                                                                                                                                | Pass                                        |
| Readiness-failure rollback          | Rollback reached `rolled_back`, restored the clone-only marker from the local reserve, and wrote a successful `RESTORE_TRIGGER` outcome with `outcome=rolled_back`.                                                                                                                                                            | Pass                                        |
| Protected media-absent fallback     | With only the protected target changed to a non-existent subpath, scheduled backup `b66ff913357e4a95a9d39aa6722dae99` completed as `degraded/missing` and its audit row was successful. This simulated media loss without unmounting or deleting the USB contents.                                                             | Pass with simulation qualification          |
| Protected reinsertion catch-up      | Reconnected D: path reported `protected_due_before=True` at a simulated +25-hour time and created audited protected catch-up backup `83ba83168b7449a4beb14cff0c407296`.                                                                                                                                                        | Pass with simulated-time qualification      |
| Protected archive                   | No completed or temporary archive remained. The archive security scan correctly rejected the database member because its Help Center `body_markdown` contains one RTSP userinfo credential. Both protected and local publication attempts therefore failed safely; no credential value was printed or copied into the finding. | Blocked pending credential-safe source data |

The live run did not perform a sustained concurrent-write measurement, a physical USB unplug/replug, or a dashboard participant restore. The technical restore core was exercised on the clone; the dashboard and physical removal portions remain pending for a controlled demo window. The protected archive result is a genuine safety block, not a fabricated pass: the current demo data cannot satisfy the existing P7 rule that no `rtsp://` credential string appear anywhere in an archive.

## Verified unchanged sites

- NFR-16 and NFR-18 are written as shall requirements and are now met; no defense-paper replacement is proposed for either requirement.
- Use Case 12 already distinguishes scheduled and manual backups, and Use Case 13 plus the restore architecture already describe operator-initiated restore orchestration. These are not the unattended daily scheduler and do not need wording changes for this finding.
- TC-R-303 describes the restart scenario and expected result but does not claim that APScheduler owns the restart; it remains unchanged.
- Deployment and Implementation contains no separate scheduler-ownership sentence. The Frameworks and Libraries replacement is the single primary implementation-narrative site.
- The `Backup & Recovery` tab remains Sheet-write-pending: the protected-device drill now has local evidence, but no live tracker result/evidence cells were changed without the separate test-tracker approval gate.

## Approval / sync ledger

Package ID: `PS-20260818-SCHEDULER-JOBS-AND-DAILY-RESTART`

| Target                                   | Approved scope                                                                                                   | Applied/read back                                                                                                                                                 | Skipped/pending                                                                                                                          | Blocked                                                                                                                |
| ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Defense paper                            | Blocks 1–2 and their attached comments                                                                           | Local exact replacements amended; no live Docs write or readback in this pass                                                                                     | Blocks 1–2 require the defense-paper approval gate                                                                                       | —                                                                                                                      |
| ADAS_Paper_Audit plus `🚩 Action Stream` | Blocks 3–4 and their attached comments                                                                           | Local exact replacements amended; no live Doc/Sheet write or readback in this pass                                                                                | Blocks 3–4 require the combined audit/tracker approval gate                                                                              | —                                                                                                                      |
| ADAS Test Execution Tracker              | Blocks 5–7 and their attached comments; preserve existing `#D9EAD3`, validation, formatting, formulas, and links | Live ranges were read-only verified on 2026-09-03; exact local proposals recorded; no live Sheet write                                                            | Blocks 5–7 require the separate test-tracker approval gate; all five new rows remain `Not Executed` pending physical-device evidence     | —                                                                                                                      |
| Local companion records                  | Amended finding, regenerated `paper_sync/TRACKER.md`, and P30 edge-coverage row                                  | Applied in this Git worktree; tracker regenerated after the finding edit                                                                                          | —                                                                                                                                        | —                                                                                                                      |
| Live protected-device drill              | TC-BR-001 through TC-BR-005 execution/evidence                                                                   | Isolated-clone drill recorded protected backup/list/audit, restore/local reserve, rollback, degraded fallback, and protected catch-up results; D: remained intact | Physical unplug/replug, sustained write-load measurement, dashboard participant restore, and Sheet result/evidence writes remain pending | Protected archive is blocked by the existing credential scan because current demo data contains an RTSP userinfo value |
| Standalone comments                      | None proposed                                                                                                    | —                                                                                                                                                                 | None                                                                                                                                     | —                                                                                                                      |
