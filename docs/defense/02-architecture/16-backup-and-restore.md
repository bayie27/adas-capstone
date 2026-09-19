# 16 — Backup and Restore

> **One-liner:** ADAS makes a consistent online SQLite backup, verifies it, and publishes it as a restore point; a separately supervised coordinator performs any database replacement while the application services are stopped.
> **Panel risk:** high — the design combines live database copying, storage failure, authorization, process control, atomic replacement, rollback, and restart readiness in one maintenance path.

## 1. What it is

Backup and restore is the system's recovery boundary. It protects the local SQLite database that holds operational state such as users, cameras, incidents, audit records, and telemetry.

A **backup** is a new, independently readable database artifact. It is made while ADAS is running, so detection and normal database writes can continue. The online copy is made through SQLite's own backup API, page by page, rather than by copying the live database file byte for byte.

A **restore** is different. It replaces the active database, so it is an offline operation. The web API accepts and records a request, but does not replace `adas.db`. A separately supervised coordinator asks the host to stop the backend and AI engine, creates an emergency copy of the current database, verifies the selected restore point, swaps the database, and starts the services again.

The distinction is the key architectural idea:

- **Backup:** safe to perform online because SQLite provides a consistent page-level snapshot while the source remains available to writers.
- **Restore:** unsafe against a live process, so the API writes a durable request and the host-level coordinator owns the stop, swap, restart, and rollback lifecycle.

The paper's reliability requirement is **NFR-18 — Data Redundancy & Recovery**: the system backs up automatically every day without interrupting detection, and an Administrator can restore it with alerts working again within 60 seconds. The paper also assigns backup and restoration administration to the Administrator and describes the workflow as **Flag and Restart**.

The implementation adds several protections around that requirement:

- a disk-space check before a backup writes anything;
- SQLite checks and a SHA-256 checksum for each artifact;
- an atomic database publication and an atomic manifest publication;
- separate scheduled, manual, and pre-restore retention handling;
- a protected storage tier with a local degraded fallback;
- one maintenance lease shared by API, scheduler, CLI, and coordinator;
- administrator authorization, password re-verification, and an exact confirmation phrase for a destructive restore;
- a durable request file outside the database being replaced;
- verify-then-replace, an emergency reserve, automatic rollback, and a readiness gate before a restore is declared complete.

The recovery target is the system state represented by the selected database. It is not a promise that a restore preserves changes made after that restore point. Those later changes are precisely what selecting an older point rolls back.

## 2. Where it lives

### In the paper

- **Chapter 3, Requirements Analysis, Table 6 — Reliability Requirements, NFR-18:** daily backup without interrupting detection, Administrator restore, and alert recovery within 60 seconds.
- **Chapter 3, Requirements Analysis, Table 2 — Functional Requirements, FR-20:** important maintenance actions and their outcomes belong in the activity audit trail.
- **Chapter 3, System Architecture and Design, “Database”:** SQLite is the local edge database and uses WAL to support concurrent reads and writes.
- **Chapter 3, System Architecture and Design, Level 1 DFD, Figure 6:** D6 is the logical data store for reports and recovery artifacts; process 6.0 is the maintenance and reliability boundary.
- **Chapter 3, System Architecture and Design, “Database Maintenance and Restoration”:** the Administrator initiates the operation, while the external orchestrator performs the offline lifecycle.
- **Chapter 3, “System Maintenance and Database Restoration Architecture,” p. 160:** the paper names the concurrency problem, Flag and Restart, service stopping, the pre-restore snapshot, database replacement, sidecar cleanup, integrity verification, rollback, service resumption, and audit logging.
- **Chapter 3, Use Case — “Trigger and Manage Database Backups”:** the panel shows the backup list, manual trigger, background execution, validation status, and busy rejection.
- **Chapter 3, Use Case — “Restore the System from a Backup”:** the panel shows Administrator authorization, password re-entry, exact confirmation, identifier validation, atomic flag creation, service stop, safety snapshot, replacement, integrity checks, restart, and rollback on failure.
- **Chapter 4, Results and Discussion, Activity 7 — Backup and recovery testing:** the paper summarizes the tracker results, including the live scheduled-backup overlap, restore recovery timing, rollback evidence, and the simulated interrupted-restore qualification.
- **Definition of Terms, “Flag and Restart” Restoration:** the state flag is outside the live database so an external host orchestrator can recover the database safely.

### In the code

**Online backup and publication**

- `backend/app/maintenance/backup.py:282` performs the disk-space precheck.
- `backend/app/maintenance/backup.py:377` opens the live database read-only and calls `sqlite3.Connection.backup()` into a temporary destination.
- `backend/app/maintenance/backup.py:400` validates, hashes, and atomically publishes a completed artifact; `backend/app/maintenance/manifest.py:166` publishes its JSON manifest atomically as well.
- `backend/app/maintenance/backup.py:476` and `backend/app/maintenance/backup.py:508` select protected storage or the degraded local fallback.

**Validation and identity**

- `backend/app/maintenance/verify.py:12` computes SHA-256 in chunks.
- `backend/app/maintenance/verify.py:26` runs `quick_check`, while `backend/app/maintenance/verify.py:40` runs the full SQLite integrity check and `backend/app/maintenance/verify.py:54` runs the foreign-key check.
- `backend/app/maintenance/manifest.py:38` defines the allowed origins and identifier format; `backend/app/maintenance/manifest.py:74` validates every identifier before path construction.
- `backend/app/maintenance/manifest.py:97` defines the manifest and its validity rule; `backend/app/maintenance/backup.py:661` rechecks listed files against their recorded size, name, and checksum.

**Storage and retention**

- `backend/app/maintenance/storage.py:25` defines the protected and degraded tiers and the stable, path-free reasons for fallback.
- `backend/app/maintenance/storage.py:232` probes writability, free space, and physical-device identity; a target on the same physical device as the live database is not treated as protected.
- `backend/app/maintenance/backup.py:523` keeps the emergency pre-restore copy local; `backend/app/maintenance/backup.py:818` prunes scheduled and manual points only after a valid new point exists.
- `backend/app/maintenance/backup.py:872` bounds the pre-restore reserve after the restore outcome is terminal.

**API, request file, and audit**

- `backend/app/api/routes/maintenance.py:158` lists backup candidates without exposing filesystem paths; `backend/app/api/routes/maintenance.py:187` accepts a manual backup and returns while the job runs in the background.
- `backend/app/api/routes/maintenance.py:233` is the restore request route. It performs the role, password, phrase, identifier, coordinator, and busy checks, then writes only a restore request.
- `backend/app/schemas/maintenance.py:13` defines the exact confirmation phrase as `RESTORE DATABASE`.
- `backend/app/maintenance/restore.py:153` stores state in `restore_state.json`; `backend/app/maintenance/restore.py:291` writes a validated request with an atomic rename and never touches `adas.db`.
- `backend/app/api/routes/maintenance.py:494` audits an accepted request; denied and completed outcomes are also recorded by the maintenance path.

**Offline restore and supervision**

- `backend/app/maintenance/restore.py:397` re-verifies the selected manifest, checksum, integrity, foreign keys, and schema revision.
- `backend/app/maintenance/restore.py:495` performs the offline copy, sidecar cleanup, temporary validation, and atomic database swap.
- `backend/app/maintenance/restore.py:671` restores the emergency reserve when the replacement or restart gate fails; `backend/app/maintenance/restore.py:749` finalizes a healthy result.
- `backend/app/maintenance/coordinator.py:207` reports coordinator availability; `backend/app/maintenance/coordinator.py:311` claims one durable request; `backend/app/maintenance/coordinator.py:383` builds the only fixed host runner commands.
- `backend/app/maintenance/coordinator.py:518` supervises the request, emits heartbeats, starts the runner, and fail-closes when state is stale or unreadable.
- `scripts/adas-maintenance.ps1:263` implements the scheduled backup and restart sequence; `scripts/adas-maintenance.ps1:377` implements the offline restore, readiness wait, and rollback branches.
- `backend/app/api/routes/system.py:20` defines the readiness probe used by the restart gate; `backend/app/main.py:248` schedules daily backup and catch-up work.

**Focused test evidence**

- `backend/tests/test_maintenance.py:169` covers online backup, space checks, atomicity, retention, checksum, SQLite checks, restore, rollback, and the route guards.
- `backend/tests/test_maintenance.py:1376` covers the cross-operation lock in both directions.
- `backend/tests/test_protected_backup_storage.py:220` covers protected-first publication, degraded fallback, media loss, and local emergency reserves.
- `backend/tests/test_restore_coordinator.py:43` covers fail-closed coordinator availability, durable claim, runner supervision, and stale or malformed state.

## 3. How it works

The timing and outcome statements in this section use **Tracker, Backup & Recovery!A1:J17**; the paper's requirement and acceptance framing remains authoritative for NFR-18.

### First, what actually happens, in order, in ordinary words

There are two stories to learn: **making a backup** and **using one to restore**.

#### Making a backup

1. A scheduled job or an Administrator asks for a backup.
2. ADAS takes the shared maintenance lock. If another backup or restore owns it, the new request is rejected as busy; it is not queued.
3. The system checks that the target volume has enough free space before it creates a temporary artifact.
4. SQLite copies a consistent view of the live database into that temporary artifact through its backup API. Detection and ordinary writes continue.
5. ADAS opens the completed temporary database read-only and runs the required SQLite and foreign-key checks. It also computes a SHA-256 digest.
6. Only after those checks pass does it rename the temporary database to its final backup name. A reader never sees the final name pointing at a half written file.
7. ADAS writes a manifest beside it. The manifest says which backup this is, when it was made, where it came from, how large it is, what schema revision it contains, which checks passed, and what checksum to expect.
8. The dashboard lists the point with a validation result and a storage tier. Later listings recheck the artifact instead of trusting an old status.
9. Old scheduled and manual points are pruned by their own retention rules, while a restore point currently selected by an active request is protected.

#### Restoring a backup

1. An Administrator selects a currently valid restore point and storage tier.
2. The API rechecks the Administrator's role, current password, exact phrase, safe identifier, coordinator availability, and maintenance lock.
3. The API writes an atomic `restore_state.json` request and returns an accepted response. The active database is unchanged at this moment.
4. The independent coordinator notices the durable request, waits for its short grace period, claims it, and starts the fixed host runner.
5. The host runner stops the backend and AI engine and proves that the controlled services are offline before database work begins.
6. The restore worker makes a verified local emergency backup of the current database. This is the rollback source, and it exists before the selected point can replace anything.
7. The worker rechecks the selected artifact, copies it to a temporary restore path, verifies the temporary copy, removes obsolete SQLite sidecars, and atomically replaces the primary database.
8. The durable state becomes `db_restored`. The runner starts the backend and AI engine, then waits for database readiness and a fresh AI heartbeat.
9. If both checks pass, the state becomes `completed`, the outcome is audited, and the emergency reserve becomes eligible for bounded cleanup.
10. If the replacement or readiness gate fails, the runner stops services again, verifies the emergency reserve, swaps it back, restarts the original services, and records `rolled_back`.
11. If rollback itself cannot be completed safely, the durable state is `manual_intervention`. The system never labels that branch successful.

The API never performs steps five through ten. That is intentional: the process receiving the HTTP request cannot safely stop itself, replace the file it is using, and then restart itself. The external coordinator can supervise that lifecycle because it remains alive while the backend and AI engine are stopped.

### Online backup: why the database stays usable

The source is opened read-only with SQLite's URI read-only mode. The destination is a separate temporary SQLite connection. `source.backup(destination)` copies database pages using SQLite's supported online backup mechanism.

This matters because the live database uses WAL and continues to serve reads and writes. A raw file copy could capture a main file without the relevant WAL state, or observe the file while it is changing. The database-owned backup API coordinates the snapshot at the SQLite page level.

The backup code also normalizes the destination after the copy. It checkpoints any copied WAL content and switches the temporary artifact to a self-contained journal mode before publication. The final restore point is therefore one database file rather than an unexplained collection of leftover sidecars.

The test tracker directly exercises the important property. **TC-BR-008** records a valid backup during concurrent writes with no broken write path. **TC-BR-010** records a scheduled protected backup running during active detection: the backup took **4.686 seconds**, a detection recorded during the window reached the dashboard in **1.986 seconds**, and the ten-channel sample stayed connected at **17.11–19.92 FPS**. These are the tracker measurements, not a general promise for every host.

### The precheck and the validation chain

The disk-space check runs before the temporary artifact is created. It uses the source database size as the basis for a safety cushion and checks the volume where the artifact will be written. The protected-storage probe independently checks free space before protected publication.

If the precheck fails, the operation stops before writing a new backup. A failure is reported with a stable reason such as `full`; a raw absolute path or operating-system message is not sent to the dashboard.

Creation validation has layers:

- **Hashability:** SHA-256 can read the whole artifact and produce a digest.
- **Quick SQLite check:** the database can be opened read-only and SQLite's quick structural check returns `ok`.
- **Foreign-key check:** SQLite reports no orphaned or otherwise invalid foreign-key relationships.
- **Full integrity check:** restore candidates and archival validation run the more complete SQLite integrity check.
- **Recorded checksum comparison:** after publication, listing and restore paths compute the digest again and compare it with the manifest value.
- **Size and filename identity:** the file still has the name and size recorded in the manifest.

The checksum answers, “Are these bytes the same bytes we recorded?” It does not by itself answer, “Does the database make sense?” That is why the checksum is combined with SQLite integrity and foreign-key checks.

If a listed artifact is corrupted later, the listing keeps it inspectable but marks it invalid. **TC-BR-015** records that the corrupted artifact was refused before service interruption and the active database was untouched.

### Atomic publication and the manifest

The database is first written as `adas_backup_<id>.tmp`. Validation and hashing happen against that temporary path. The code then uses an atomic replacement to publish `adas_backup_<id>.db`; the final database name is never exposed for an incomplete attempt.

The manifest is also written to a temporary JSON name and atomically replaced into its final name. A database file without its manifest is not considered a published restore point. If any step fails, the current attempt's temporary file, sidecars, final file, and manifest are cleaned up while older valid points remain.

The manifest carries the backup identifier, filename, UTC creation time, origin, application version, schema revision, file size, SHA-256, validation checks, storage tier, and a safe storage reason. The identifier is a bare lowercase UUID hex value. It is generated by the server and validated every time it comes from an API body, CLI argument, manifest, or restore state.

### Protected and degraded storage

The normal policy is protected-first. A configured protected root is accepted only when the provider can show that it is an absolute writable directory with space and a different physical-device identity from the live database.

If the protected device is missing, read-only, full, unverifiable, on the same device, or fails during publication, the system makes one verified local fallback. That point is labeled **degraded**, and the dashboard shows a path-free reason and warning. Existing local artifacts are preserved.

If both the protected attempt and the local fallback fail, the backup reports a failure rather than silently claiming that redundancy was achieved.

The two tiers have different meanings:

- **Protected:** the artifact is on the configured, independently checked storage target.
- **Degraded:** the artifact is valid but remains on the local storage path, so it does not protect against loss of the host's storage device.

The emergency pre-restore copy is deliberately local. It must still be available if the selected protected device disappears during the restore. The restore state records the selected tier and the emergency tier separately.

### Retention without deleting the safety net

Scheduled and manual backups have separate retention buckets. Pruning runs only after a new backup is valid, so a failed attempt cannot cause cleanup to remove the last good point.

Pre-restore emergency points are managed separately. The active selected point and the active emergency point are protected from pruning while the restore is `requested`, `in_progress`, or `db_restored`. Once the outcome is terminal, old emergency points can be bounded by their configured reserve policy.

The implementation has separate configuration values for scheduled, manual, and pre-restore retention in `backend/app/core/config.py:126-135`. Treat the exact current counts as deployment configuration and verify the live environment before quoting them to a panel.

### The shared maintenance lock

The lock has two layers. A process-local thread lock gives immediate exclusion inside the FastAPI process. A file lock held on `maintenance.lock` extends the lease across processes, including the scheduled runner and the external coordinator.

The manual-backup route acquires the lease synchronously before adding its background task. This is why a second request receives an immediate `409 CONFLICT_BUSY` instead of joining a queue that the operator cannot see.

Restore publication uses the same lease. The route checks the coordinator and acquires the lease again immediately before publishing the request, because state can change between an initial status read and the write.

There is also a durable-state guard for the small handoff where the coordinator has claimed a request and is about to launch the host runner. A backup may not enter once the restore is `in_progress` or `db_restored`, even if it wins a file-lock race in that handoff.

The tracker records both directions in **TC-BR-009**: a second backup or restore request is rejected, no second artifact is queued, and the rejection is audited. The focused cross-operation tests exercise backup-held/restore and restore-held/backup cases.

### Restore guards before any database change

The restore route is intentionally stricter than a normal read or routine maintenance action:

1. **Administrator role:** the route uses the Administrator guard. Operators cannot trigger a restore.
2. **Password re-verification:** the Administrator submits the current password again; the server verifies it against the stored password hash.
3. **Exact phrase:** the body must contain exactly `RESTORE DATABASE`. The phrase is a deliberate friction step for a destructive action.
4. **Identifier validation:** the selected identifier must match the server's bare UUID-hex format before it is joined to any backup directory. A client cannot submit an arbitrary path.
5. **Current artifact validation:** the manifest, checksum, size, SQLite checks, and selected storage tier are checked again under the maintenance lease.
6. **Coordinator availability:** a stale, missing, uncontrolled, or errored coordinator causes a fail-closed response.
7. **Busy conflict:** an active backup, active restore, or executing coordinator produces `409 CONFLICT_BUSY`; it does not overwrite the existing request.

Wrong passwords, phrase mismatches, invalid identifiers, invalid restore points, unavailable coordination, and busy conflicts are recorded as denied maintenance attempts without exposing passwords, confirmation strings, or filesystem paths.

### Durable request and supervised offline swap

The restore request is a JSON state file because the active database may be the thing being replaced. If the request were stored only in a database table, the restore would erase the request while performing the restore.

The state file is atomically replaced and carries the selected backup ID, storage tier, requester, request ID, timestamps, emergency backup ID, steps, errors, and terminal status. The coordinator treats malformed state as an error, not as an empty queue.

The coordinator has its own singleton lock and publishes a heartbeat. It claims one matching request while holding the maintenance lease, validates the request age and execution time, and launches one fixed platform command. The only variable inputs are a validated backup identifier and a validated storage tier; the runner command is not arbitrary shell text from the browser.

The host runner must prove the controlled backend and AI processes are stopped, the application port is free, and the managed process records are gone before the database is touched. This is the operational reason that the API cannot do the swap itself.

### Emergency backup, verify-then-replace, and rollback

The first database operation in the offline phase is an online-style SQLite copy of the **current** database into the local `pre-restore` reserve. That reserve is then fully verified. The selected restore point is independently re-read from the requested storage tier and its checksum, integrity, foreign keys, and compatible schema revision are checked.

The selected file is copied to a temporary path next to the live database. The temporary file is checked again before it can become the primary database. WAL and shared-memory sidecars are removed from both the old primary and temporary paths, and `os.replace` performs the final swap.

The state changes to `db_restored` only after the swap. It is not yet `completed`; service restart and health evidence still have to pass.

If a check fails before the swap, the original primary remains in place. If the post-swap database or restart gate fails, the runner stops the services, re-verifies the local emergency point, and atomically swaps it back. A failed rollback leaves a durable `manual_intervention` outcome so operators do not mistake an unsafe state for success.

### Restart readiness and alert recovery

`/healthz/ready` is not a constant success response. It requires backend startup initialization to have completed and executes `SELECT 1` through the database session. The maintenance runner also waits for a fresh AI heartbeat before it finalizes a restore.

This separation matters. A backend can answer a readiness probe while the AI engine is still absent. The live tracker rollback drill intentionally removed the AI process: readiness was true but the fresh-heartbeat condition was false, so the system rolled back to the emergency reserve. The host then restarted the original services, and readiness plus the AI heartbeat returned true with final integrity `ok` and zero foreign-key violations (**TC-BR-004**).

For an accepted restore, connected dashboards receive a typed maintenance notice before the socket is expected to drop. The services are offline during the swap, so new detection processing is paused during that planned window. After the readiness gate, the backend and AI engine resume and dashboards reconnect to the restored state.

The recovery requirement is about alerting being usable again. **TC-BR-014** records that a fresh alert appeared **57.04 seconds after restore completion** and rendered in **0.67 seconds**, within the paper's 60-second NFR-18 window. The same result returned the database to its known pre-backup state and ended with zero foreign-key violations.

## 4. Why it was built this way

### Why use SQLite's backup API?

The live database is a WAL-mode SQLite database with active reads and writes. The database engine knows how to produce a coherent page-level snapshot while the application continues operating. A raw file copy does not provide that coordination and can separate the main file from its journal state.

The tracker confirms the operational reason for the choice: scheduled backup continued during active detection, and a detection in the backup window still reached the dashboard within the tested alert-delivery requirement.

### Why write a request instead of restoring in the route?

Replacing a database underneath a running FastAPI process and AI engine risks open handles, concurrent writes, stale ORM sessions, and WAL sidecars belonging to the old file. The API process also cannot safely stop and restart itself.

The paper therefore assigns initiation to the Administrator-facing API and execution to an external orchestrator. The durable file bridges those two lifetimes. It survives the API response and can be observed by a coordinator that remains alive while the services are stopped.

### Why verify twice?

The artifact can change or disappear after it was listed. The request path revalidates it before publication, and the offline path revalidates it after services stop. The temporary restore copy is checked before the primary swap. This turns a stale dashboard row or a damaged file into a refusal before the live database is changed.

### Why use both checksum and SQLite checks?

The checksum detects byte changes and helps identify whether the file is the same artifact described by the manifest. SQLite quick/integrity checks assess database structure, and foreign-key checks assess relational references. Each answers a different failure question, so the system records them separately.

### Why protected plus degraded storage?

An external, separately identified target protects against loss of the live host's storage. Requiring a physical-device comparison avoids calling a second directory on the same disk a true independent backup.

The local degraded tier keeps recovery useful when the protected device is missing or unusable. The warning is explicit, and a backup is called a failure when both targets fail. This makes degraded operation visible instead of silently overstating redundancy.

### Why keep the emergency copy local?

The emergency point is the rollback path for the current restore. If the protected device disappears while the selected artifact is being used, the rollback source must still be on the host that is performing the swap.

### Why atomic rename and a manifest?

The temporary name prevents readers from treating an incomplete copy as a restore point. Atomic rename gives publication a clear boundary. The manifest binds the ID, file name, size, checksum, checks, origin, and schema revision together, so the listing and restore path can inspect the artifact without trusting an unverified filename.

### Why one lock for backup and restore?

Both operations read or publish maintenance artifacts, and restore changes the database that backup is trying to snapshot. Separate locks would permit a backup to capture a transition or a restore request to be published while a backup is still writing. The shared in-process and cross-process lease makes the conflict explicit and gives the API a deterministic busy response.

### Why a readiness gate instead of “the process started”?

Process creation does not prove that the restored database is initialized or that the AI engine is receiving the desired camera configuration. The readiness probe checks the database, and the heartbeat proves that the second runtime component has returned. Only then is the state finalized as completed.

## 5. What changed since the 28 April defense

Use the following as the update answer when the panel asks what is new in this area:

- Backup and restore now have a dedicated `backend/app/maintenance/` package with separate backup, manifest, verification, storage, restore, and coordinator modules.
- The current system makes an online page-level copy through SQLite's backup API and publishes it only after validation and checksum creation.
- Backup artifacts now have manifest identity, origin, schema information, validation checks, and storage-tier labels that the maintenance UI can show.
- Protected storage is probed for writability, space, and separate physical device identity, with a visible degraded local fallback when it is unusable.
- Manual and scheduled backup requests share a cross-process maintenance lease, so an overlap is rejected with a busy result rather than queued.
- Restore is now a dashboard-triggered but externally supervised Flag and Restart flow. The API writes `restore_state.json`; the coordinator and host runner own service stop, swap, restart, readiness, and rollback.
- Restore now rechecks the Administrator's password, the exact confirmation phrase, the safe backup identifier, the selected storage tier, and current coordinator state before publication.
- Every restore creates a local emergency reserve before replacement and can roll back automatically when the restored database or restart readiness fails.
- The current test tracker contains **16 Backup & Recovery cases**, all marked Pass, covering backup concurrency, protected/degraded storage, restore initiation, offline replacement, corruption, rollback, and alert recovery.

The tracker also records qualifications. The interrupted-power case is an accepted simulation, and some media-loss or failed-rollback branches use disposable fixtures; include those qualifications in the spoken answer.

## 6. Limits and honest caveats

- NFR-18 is a paper requirement. The tracker evidence comes from the isolated demonstration environment, not the live CDRRMO production database or the full citywide camera network.
- The backup and restore lifecycle was exercised on researcher-controlled hardware and test data. It does not establish production-scale storage, multi-host failover, or a cloud backup service.
- The interrupted-restore case (**TC-BR-016**) is explicitly a simulated drill; no physical host power cut was performed.
- **TC-BR-005** and **TC-BR-004** cover protected-storage loss, fallback, and rollback branches; the tracker qualifies post-copy media loss and failed rollback as disposable-fixture coverage.
- The successful rollback drill had a real readiness failure induced by losing the AI process. It passed the safety gates and returned the original services, but it is still a controlled test scenario.
- The fresh post-restore alert appeared **57.04 seconds** after restore completion against a **60-second** requirement. That is a pass with little margin, not evidence of a large timing buffer.
- The Backup & Recovery sheet does not report one canonical user-facing downtime duration for the offline restore window. Do not substitute the scheduled-restart timing for it.
- The tracker does report a separate scheduled-restart run: **22.69 seconds** of downtime, backend readiness in **5.09 seconds**, fresh AI heartbeat in **11.14 seconds**, and **10/10** camera recovery (**TC-BR-006**). Label those as restart figures, not restore downtime.
- A valid checksum cannot prove that the data is the correct business point in time. It proves byte identity; the selected restore point's timestamp and origin still require an Administrator's judgment.
- A degraded backup is valid but remains on local storage. It is not equivalent to a protected copy on a separate physical device.
- Restore intentionally discards changes made after the selected restore point. The emergency reserve protects the pre-restore state if the operation fails; it does not merge both histories.
- During the offline swap, the application services are stopped. A planned maintenance notice is sent first, and alert processing resumes only after the readiness and heartbeat gate.
- The exact configured retention counts are environment settings, not a paper or tracker result. Quote them only after verification.

## 7. Likely panel questions

### “What if the power cuts in the middle of a restore?”

The request and restore state are durable outside the database. On the next host recovery run, the residual request state is inspected; the runner either finishes safely or uses the verified local emergency reserve to roll back. The tracker marks this behavior Pass as an accepted simulation, not a physical power-cut result.

### “Can you back up while the system is running and detecting?”

Yes. The backup uses SQLite's online backup API and keeps the live source available to readers and writers. In TC-BR-010, a scheduled protected backup ran for 4.686 seconds during active detection, and the detection in that window reached the dashboard in 1.986 seconds.

### “Who can trigger a restore, and what stops a mistake?”

Only an Administrator can reach the restore route. The system also requires the current password again, the exact phrase `RESTORE DATABASE`, a validated backup identifier, a currently valid manifest, and an idle coordinator. A wrong or busy request is denied and audited before any database replacement.

### “How do you know a backup isn't corrupt?”

Creation and restore use multiple checks: SHA-256, SQLite quick or full integrity checks, foreign-key checks, file size, and manifest identity. The listing recomputes the checksum, and restore re-verifies the selected artifact before copying it to a temporary path. A mismatch is refused before services are stopped.

### “Why not just copy the database file?”

An online raw copy can separate the SQLite main file from its active WAL state. The SQLite backup API creates a coherent page-level snapshot while the live system continues writing. A file copy is used only for an already verified restore point after services are stopped and the destination is checked.

### “How long is the system down during a restore?”

The tracker does not provide one canonical restore-downtime number, so I would not invent one. It records the recovery requirement and a fresh alert at 57.04 seconds after restore completion; the separate 22.69-second figure is for a scheduled restart, not the restore swap.

### “What happens to alerts that arrive during a restore?”

The system sends a maintenance notice, then stops the backend and AI engine before touching the database, so new detection processing is paused during the planned offline window. After the restored database passes readiness and the AI heartbeat gate, the services resume and alerting becomes available again.

### “What if the protected drive disappears?”

If it disappears before the selected file is copied, validation fails and the live database is not swapped. If it disappears after a local restore copy has been made, the restore can still finish; the emergency rollback reserve is always local. The tracker records the live pre-copy and readiness-failure branches, with later media-loss branches qualified as disposable-fixture tests.

### “Can a scheduled backup race a manual backup or restore?”

No. All paths share the in-process and cross-process maintenance lease. The second request gets a busy response, is not queued, and is audited. Durable restore state also blocks a backup during the coordinator's claim-to-run handoff.

### “Why is the restore request stored outside the database?”

The restore replaces the database. A request row inside that database could be destroyed by the replacement itself. `restore_state.json` survives the swap, lets the coordinator resume or fail closed, and retains the emergency ID and outcome for the post-restart audit.

### “What if the selected backup ID is a path traversal string?”

The API validates the identifier against a bare lowercase UUID-hex pattern before any path helper runs. The path helpers validate again, so values containing slashes, `..`, or drive syntax never become filesystem input.

### “What if rollback also fails?”

The coordinator records `manual_intervention` and keeps the failure visible; it does not report success. The tracker includes failed-rollback handling in its disposable-fixture coverage, while the live rollback drill passed with the emergency reserve.

## 8. Cram summary

- NFR-18 requires daily backup without interrupting detection and alert recovery within 60 seconds after restore.
- Backup is online; restore is offline.
- Online backup uses SQLite's page-level backup API, not a raw live-file copy.
- The source remains usable for detection and normal writes during backup.
- A disk-space precheck runs before a new artifact is written.
- The artifact is written to a temporary name first.
- SQLite checks, foreign-key checks, and SHA-256 validate the artifact.
- Listing and restore recompute the checksum against the manifest.
- Atomic rename publishes the database only after validation.
- Atomic manifest publication binds ID, size, origin, schema, checks, and hash.
- Protected storage must be writable, have space, and be on another physical device; otherwise a verified local degraded fallback is used.
- Both tiers expose stable reasons and no filesystem paths to the dashboard.
- Scheduled, manual, and pre-restore points have separate retention handling.
- Active restore and emergency IDs are protected from pruning.
- One maintenance lease covers API, scheduler, CLI, and coordinator.
- A conflict returns `409 CONFLICT_BUSY`; no second operation is queued.
- Restore is Administrator-only and requires password re-verification.
- The exact destructive confirmation phrase is `RESTORE DATABASE`.
- The ID is validated before any path is built; the manifest is revalidated.
- The API writes `restore_state.json`; it never replaces `adas.db`.
- The coordinator stops services before database work and creates a local emergency reserve first.
- The selected artifact and temporary restore copy are verified before swap.
- `os.replace` performs the primary database swap; obsolete sidecars are purged.
- Readiness checks database initialization and `SELECT 1`; a fresh AI heartbeat is also required.
- Readiness or heartbeat failure triggers rollback from the local emergency reserve; failed rollback becomes `manual_intervention`.
- Tracker results: all 16 Backup & Recovery cases Pass; scheduled backup ran during detection; post-restore alert recovery was 57.04 seconds after completion against the 60-second requirement.
