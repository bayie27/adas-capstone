# Manual Test Playbook

> **10_PKG_migration_evidence.md Step 5.** Step-by-step procedures for
> everything in `be_plan/TRACEABILITY.md` marked `manual` — cases that
> genuinely cannot be automated (real clock time, real hardware thermals,
> a real browser, a real 24-hour window) rather than cases that merely
> haven't been automated yet.
>
> **Every procedure below is unexecuted as of this package landing** — the
> result blanks are empty. Running them is separate work from writing
> them; `TRACEABILITY.md` marks each of these test cases `pending` for
> exactly that reason. Fill in a copy of this file (or note results
> directly below, since it's tracked in git and diffs are the record) each
> time a drill actually runs.
>
> All timings are **demo-validated on the laptop** described in
> `be_plan/EVIDENCE.md`'s machine spec — not the production-target 8×L4
> Linux edge server (D-009).

---

## 1. TC-R-303 — 3:00 AM automated restart drill

**Target:** NFR-16 — memory flush and recovery in under 10 seconds, backup
completing without interrupting active AI inference (NFR-18's daily-backup
half).

**Prerequisites:**
- Backend and AI engine both running via `scripts\adas-maintenance.ps1 -Action Start`.
- At least one camera actively streaming (MediaMTX + a sample video looping).
- A terminal free to watch logs.

**Procedure:**

1. Note the wall-clock time. Trigger the restart manually rather than
   waiting for the real 3 AM window:
   ```powershell
   scripts\adas-maintenance.ps1 -Action Restart
   ```
2. This runs two phases — **time them separately**, not as one combined
   number:
   - **Backup phase** (`app.maintenance restart --phase backup`): a
     verified online backup of the live database, taken *before* anything
     is stopped.
   - **Wait phase** (`app.maintenance restart --phase wait`): stop →
     start → poll `/healthz/ready` (and `heartbeat_confirmed` once a
     heartbeat writer exists — currently reported for visibility only,
     see `cli.py`'s own comment) until ready or `--timeout` (default 60s)
     elapses.
3. Once ready, confirm the AI engine reconnected to its camera(s) — check
   for `Connected`/`Active` in `GET /api/cameras/` or the dashboard.
4. Record:

| Measurement | Result |
|---|---|
| Date/time of drill | |
| Backup phase duration | |
| Downtime (stop → `/healthz/ready` true) | |
| Model-load time (AI engine's own startup log, first frame processed) | |
| Camera(s) re-ingesting confirmed? (Y/N, which cameras) | |
| Total restart-to-recovered wall time | |
| Under the NFR-16 <10s (downtime only) budget? | |
| Anything unexpected in logs? | |

### Results — 2026-08-11 (`be_audit/A6_manual_evidence.md`)

Executed on the demo laptop (see `be_plan/EVIDENCE.md` machine spec), operator: this audit
session, against the real stack — mediamtx + 5 ffmpeg feeds, backend, AI engine with the real
TensorRT model, triggered manually (not the real 3 AM window) via
`scripts\adas-maintenance.ps1 -Action Restart` after adopting a manually-started stack with
`-Action Start` first (so PID files existed for the drill to track).

| Measurement | Result |
|---|---|
| Date/time of drill | 2026-08-11, started ~01:34:23 UTC |
| Backup phase duration | 0.14s (`backup --origin scheduled`, `duration_seconds` in its own JSON output) |
| Downtime (stop → `/healthz/ready` true) | 8.13s (script-reported: "Restart downtime: 8.1338753 seconds") |
| Model-load time (AI engine's own startup log, first frame processed) | **Not captured** — `adas-maintenance.ps1` launches the AI engine in its own `-WindowStyle Minimized` console with no persistent log file, so nothing outside that window can read its stdout after the fact. Real gap in this orchestrator's evidence-capture story, not a defect in the restart mechanism itself — see the new finding this raised. |
| Camera(s) re-ingesting confirmed? (Y/N, which cameras) | Y — cameras 1, 2, 4, 5 (the fed, enabled cameras) read `Connected` within ~3s of the wait phase completing. Camera 6 stayed `Reconnecting` (no feed configured in `mediamtx.yml` for that channel — known, not a defect, matches A3's prior notes). Camera 3 stayed `Disconnected` (disabled, expected). Cameras 1 and 4 correctly stayed `ai_status: Paused` across the restart, since both had a genuinely open incident from before the drill — the desired-state persistence survived the restart correctly, not a bug. |
| Total restart-to-recovered wall time | `ready_duration_seconds`: 2.578s; `heartbeat_duration_seconds`: 2.672s (both measured from the start of the wait phase, which itself starts after the stop+start sequence); overall script-measured downtime 8.13s |
| Under the NFR-16 <10s (downtime only) budget? | **Yes** — 8.13s < 10s |
| Anything unexpected in logs? | No errors. The only observation worth recording is the log-capture gap noted above. |

### Results — 2026-08-16 (`be_plan/18_PKG_scheduled_maintenance.md` Step 8)

Executed against the real stack (mediamtx + 5 ffmpeg feeds, backend, AI engine with the real
TensorRT model) on the demo laptop. Unlike the 2026-08-11 pass, this one covers the actual
**unattended** trigger (`scripts\register-maintenance-task.ps1`, task `\ADAS\DailyRestart`), not
just a manually-invoked `-Action Restart` — and it found two real, previously-undiscovered bugs
that only a genuine unattended firing could surface.

**Methodology note on timing.** `register-maintenance-task.ps1` only supports hour-granularity
triggers (`MAINTENANCE_HOUR_LOCAL`, matching NFR-16's own "3:00 AM" framing) — there is no way to
schedule a trigger "two minutes from now" as this procedure's drill-1 instruction literally says.
With the drill starting at 14:30 local, `MAINTENANCE_HOUR_LOCAL` was set to `15` (the next hour
boundary, a ~30-minute real wait) rather than the system clock being touched to fake a closer
trigger. The value was restored and the task re-registered at the real default (`3`) immediately
after.

**Unattended trigger, attempt 1 (2026-08-16, 15:00:00 local) — FAILED.** The task fired exactly on
schedule with nobody touching it (`-Verify` showed `NextRunTime`/`LastRunTime` both `15:00:00`) —
but the backend crashed before reaching `/healthz/ready`, and `-Action Restart` exited 1.
`var\log\backend-20260816-150048.err.log` showed a real, reproducible `UnicodeEncodeError`:
FastAPI CLI's startup banner (`Starting production server \U0001f680`) couldn't be encoded by the
`cp1252` codepage the backend's stdout inherited once `-RedirectStandardOutput` detached it from a
real console — the codepage a Task-Scheduler-launched process inherits differs from whatever an
already-open interactive terminal may have customized, which is exactly why none of this pack's
earlier manual `-Action Restart` drills (same day, same machine) had hit it. Fixed by setting
`$env:PYTHONUTF8 = "1"` in `adas-maintenance.ps1` before spawning either child process.

**A second, independent bug found in the same investigation:** the AI engine's own log file
(`var\log\ai_engine-*.log`) came back empty on the *first* post-Step-5 restart, despite
`-RedirectStandardOutput` being wired up correctly — Python block-buffers stdout when it isn't a
real console, and `ai_engine/main.py`'s plain `print()` startup lines (never modified — `ai_engine/`
is off-limits) never flushed while the process kept running. Fixed with `$env:PYTHONUNBUFFERED = "1"`,
also set before spawning either child.

**A third, unrelated bug found while transcript-reviewing the failed run:** `Write-Error` under this
script's own `$ErrorActionPreference = "Stop"` is a *terminating* call, which was silently discarding
every `exit N`/`$exitCode = N` statement written immediately after it — including the rollback
path's `exit 2` ("manual intervention required"), which could never actually fire. Pre-existing
since P7, provable only now that Step 5 gives the run a transcript to see it happen in. Fixed by
adding `-ErrorAction Continue` to all six `Write-Error` call sites; verified the fix in isolation
(`exit 2` after a fixed `Write-Error` now genuinely produces exit code 2, confirmed both broken and
fixed behavior with a standalone `pwsh -Command` repro).

**Unattended trigger, attempt 2 (2026-08-16, 15:06:49 local, via `Start-ScheduledTask` on-demand —
genuinely re-invoked through Task Scheduler, not this session's own interactive shell) — PASSED.**
`LastTaskResult: 0`. `var\log\backend-20260816-150658.log` shows the same `\U0001f680` banner
printing cleanly with no crash, confirming the `PYTHONUTF8` fix under the real launch context that
broke the first attempt.

| Measurement | Result |
|---|---|
| Date/time of drill | 2026-08-16, unattended fire at 15:00:00 local (attempt 1, failed); on-demand re-verification 15:06:49 local via `Start-ScheduledTask` (attempt 2, passed) |
| Backup phase duration | Attempt 1: 24.314s (anomalously slow for a dedup-skip check — `BACKUP_DIR` sits inside the OneDrive-synced tree, F17; not chased further). Attempt 2: 1.691s. Both **skipped** (Step 9's dedup: a valid scheduled backup already existed from this session's earlier manual drills) |
| Downtime (stop → `/healthz/ready` true) | Attempt 1: 72.33s, but the run never reached ready — this is time-to-give-up, not a real recovery time. Attempt 2: 32.60s |
| Model-load time (AI engine's own startup log, first frame processed) | Content now **survives** (closes F22) — `var\log\ai_engine-*.log` shows `"Detector ready on device '0'"` live, mid-run. Still not a precise *duration*: `ai_engine/main.py`'s `print()` output carries no timestamps of its own and `ai_engine/` is off-limits to add them, so this is as far as this fix can honestly take the measurement |
| Camera(s) re-ingesting confirmed? (Y/N, which cameras) | Y, on the passing attempt — cameras 2, 4, 5 read `Connected` shortly after the wait phase completed, matching the established pattern from every prior drill this session |
| Total restart-to-recovered wall time | Attempt 2: `ready_duration_seconds` 3.094s (backend), `heartbeat_duration_seconds` 16.297s |
| Under the NFR-16 <10s (downtime only) budget? | **No, on both passing attempts this session** — see the note below |
| Anything unexpected in logs? | Yes — the two real bugs above, both found and fixed live, not simulated |

**On the >10s downtimes.** Every restart timed *today* (both drill 1's and drill 2's runs — see
below) measured well over the 10s NFR-16 budget (19.8s–72.3s), a sharp contrast with the 2026-08-11
pass's clean 8.13s. The likely cause matches F21's already-documented pattern exactly: this
session ran MediaMTX + 5 ffmpeg transcodes + a live GPU inference engine + this session's own
background PowerShell drill-1 wait-loop simultaneously, on the same machine, for the full ~35
minutes these drills span — real resource contention from the *drilling session itself*, not a
regression in the restart mechanism. Recorded honestly rather than re-run quietly on a quieter
machine until a number under budget appeared; a real demo-day restart (no concurrent drilling
session competing for the GPU and 5 transcodes) should look like 2026-08-11's number, not this
one, but that is inference from the two data points available, not a claim this pass re-verified
on a quiet machine.

---

## 2. NFR-18 — 60-second restore drill

**Target:** NFR-18 — restoring the database and resuming automated alerts
within a 60-second operational window.

**Prerequisites:**
- At least one valid backup exists: `(cd backend && uv run python -m app.maintenance list)`
  (run from `backend/`, or via `scripts\adas-maintenance.ps1`).
- Backend and AI engine stopped (`scripts\adas-maintenance.ps1 -Action Stop`)
  — restore only ever runs offline (D-011).

**Procedure:**

1. Note the wall-clock time immediately before starting.
2. ```powershell
   scripts\adas-maintenance.ps1 -Action Restore -BackupId <backup_id>
   ```
   This performs the full D-011 Steps 3–7 sequence (emergency backup of
   the *current* pre-restore state, re-verify the selected backup,
   restore to temp, swap, restart services, poll readiness).
3. Confirm the database reflects the restored backup's state (spot-check
   a known incident/camera row that should — or shouldn't — be present).
4. Record:

| Measurement | Result |
|---|---|
| Date/time of drill | |
| Backup id restored | |
| Emergency (pre-restore) backup id created | |
| DB-file swap duration | |
| Total time: restore request → `/healthz/ready` true | |
| Under the NFR-18 <60s budget? | |
| Database state confirmed matches the restored backup? | |

### Results — 2026-08-11 (`be_audit/A6_manual_evidence.md`)

Executed against the real stack, same session as drill 1. Methodology: to prove the restore
genuinely rolled back DB *content* (not just that the server came back up), a marker alert
(`log_id 58`, camera 1, `Unverified`) was dismissed to `Dismissed` **after** taking the backup
that was then restored — so a successful restore-to-content-before-the-change is directly
observable as that row reverting.

| Measurement | Result |
|---|---|
| Date/time of drill | 2026-08-11, started ~01:35:41 UTC |
| Backup id restored | `2465f157ef8f499abd79fa248622e3af` (taken 01:34:32, before the marker change) |
| Emergency (pre-restore) backup id created | `72ab5610671b428086f974a2c9dc0548` |
| DB-file swap duration | 2.53ms (`swap_primary_database` step) |
| Total time: restore request → `/healthz/ready` true | ~26s (stop+restore steps completed by 01:35:56.7; `ready_duration_seconds` 2.625s + `heartbeat_duration_seconds` 9.781s from there; finalize shortly after — well inside 60s) |
| Under the NFR-18 <60s budget? | **Yes** — ~26s vs 60s budget |
| Database state confirmed matches the restored backup? | **Yes** — `log_id 58` read back as `Unverified` (its state at backup time), not `Dismissed` (the change made after the backup but before the restore), proving the restore genuinely replaced DB content and not just restarted the process. |

### Results — 2026-08-16 (`be_plan/18_PKG_scheduled_maintenance.md` Step 8, drill 4 — regression)

Re-run to confirm Step 2's `-wal`/`-shm` sidecar-cleanup changes to `backup.py`/`restore.py` didn't
disturb this flow. Same marker-row technique as 2026-08-11: `log_id 68` (camera 5, `Unverified`,
created earlier this session by drill 3's write-load test) was dismissed to `Dismissed` immediately
after taking the backup that was then restored.

| Measurement | Result |
|---|---|
| Date/time of drill | 2026-08-16, started ~06:39:06 UTC |
| Backup id restored | `5c3c0844820b40ff95adc924bba168e7` (taken 06:39:06, before the marker change) |
| Emergency (pre-restore) backup id created | (not separately noted — `perform_offline_restore`'s own emergency-backup step, per its JSON step output) |
| DB-file swap duration | 2.03ms (`swap_primary_database` step) |
| Total time: restore request → `/healthz/ready` true | ~38s (stop+restore completed by 06:39:33; `ready_duration_seconds` 4.187s + `heartbeat_duration_seconds` 21.265s from there — well inside 60s) |
| Under the NFR-18 <60s budget? | **Yes** — ~38s vs 60s budget |
| Database state confirmed matches the restored backup? | **Yes** — `log_id 68` read back as `Unverified` (its state at backup time), not `Dismissed`. No orphaned `-wal`/`-shm` sidecars observed on any backup artifact touched by this drill — Step 2's fix holds under a real restore, not just the unit tests. |

---

## 3. Rollback drill — deliberate startup failure

**Target:** D-011's automatic-rollback guarantee — a failed post-restore
readiness check must never leave the system silently half-restored.

**Prerequisites:** Same as drill 2, plus a way to force a genuine startup
failure (e.g., temporarily point `DATABASE_URL` at an invalid path, or
corrupt a non-critical config value) — **not** a fake/simulated failure;
P7's own completion report used a real broken `DATABASE_URL` for this
exact drill.

**Procedure:**

1. Perform drill 2's restore, but arrange for the post-restore
   `/healthz/ready` check (or the orchestrator's readiness gate) to fail
   genuinely.
2. Confirm the orchestrator automatically calls the rollback path rather
   than leaving the system in the failed restored state:
   ```powershell
   scripts\adas-maintenance.ps1 -Action Restore -BackupId <backup_id>
   # on readiness failure, the orchestrator should invoke rollback —
   # confirm this happens automatically, or invoke it explicitly if the
   # orchestration doesn't yet do so unattended:
   (cd backend && uv run python -m app.maintenance rollback)
   ```
3. Fix the injected failure and confirm the system comes back up against
   the **emergency backup** (the pre-restore state), not the failed
   restore target.
4. Record:

| Measurement | Result |
|---|---|
| Date/time of drill | |
| Failure injected (what, exactly) | |
| Rollback triggered automatically? (Y/N) | |
| Rollback DB-file swap duration | |
| System confirmed back on the pre-restore (emergency) state? | |
| Any manual intervention required beyond fixing the injected failure? | |

### Results — 2026-08-11 (`be_audit/A6_manual_evidence.md`)

**Methodology note first, since it deviates from a single `-Action Restore` invocation
deliberately:** the failure needs to land *after* the restore's file-swap succeeds but *before*
the freshly-started backend becomes ready — a window inside the single all-in-one PowerShell
command with no hook to inject a break at that exact point. `DATABASE_URL` broken *before*
calling `-Action Restore` breaks the restore step itself (it also reads `DATABASE_URL` to find
the current live DB for its own pre-restore emergency backup), which is a different, real, but
not-the-one-this-drill-asks-for failure mode. So this drill ran the underlying
`python -m app.maintenance` commands directly, one per step, to control exactly when the break
was introduced — the actual `perform_rollback()` code path exercised is the identical function
`-Action Restore`'s automatic-rollback branch calls; only the outer trigger was manual rather
than the PowerShell script's own automatic call.

Same marker-row technique as drill 2, applied to a second alert (`log_id 57`, camera 4):
dismissed to `Dismissed` immediately before the restore attempt, so the emergency backup taken
at that moment captures the "Dismissed" state — and a correct rollback must land back on
`Dismissed`, not on the failed restore target's `Unverified`.

| Measurement | Result |
|---|---|
| Date/time of drill | 2026-08-11, ~01:39:30–01:41:07 UTC |
| Failure injected (what, exactly) | `.env`'s `DATABASE_URL` temporarily repointed to `sqlite:///./var/nonexistent_rollback_drill/adas.db` (a directory that does not exist) after a successful restore's DB swap, then a fresh `fastapi run` backend process started against it. Genuine, not simulated: the process crashed with `sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file` and "Application startup failed. Exiting." — `/healthz/ready` returned connection-refused for the full observation window. |
| Rollback triggered automatically? (Y/N) | **N (this session) / mechanism confirmed real** — triggered explicitly via `uv run python -m app.maintenance rollback` because the failure had to be injected as a discrete step (see methodology note above); the code path is the same `perform_rollback()` the orchestrator's own automatic branch calls on a genuine `Wait-Ready` failure. |
| Rollback DB-file swap duration | 1.25ms (`rollback_swap_primary_database` step) |
| System confirmed back on the pre-restore (emergency) state? | **Yes** — after fixing `DATABASE_URL` back, running rollback, and restarting cleanly, `log_id 57` read back as `Dismissed` (its state at the moment of the restore attempt, captured in the emergency backup) — not `Unverified` (the failed restore's target state). This is exactly the distinction D-011 exists to guarantee: a failed restore must not leave the system on the failed target. |
| Any manual intervention required beyond fixing the injected failure? | Restoring `.env`'s `DATABASE_URL` to its original value (the only thing this drill deliberately broke) and re-running `-Action Start`; no other manual DB surgery was needed — `perform_rollback()` handled the actual data recovery unattended once invoked. |

### Results — 2026-08-16 (`be_plan/18_PKG_scheduled_maintenance.md` Step 8, drill 4 — regression)

Re-run to confirm Step 2's sidecar-cleanup changes didn't disturb the rollback path either. Same
methodology as 2026-08-11 (raw `python -m app.maintenance` commands, not a single `-Action Restore`
call, to control exactly when the break lands), same marker-row technique — `log_id 68` (camera 5)
dismissed immediately before the restore attempt, restore target an older backup taken before
`log_id 68` existed, so a correct rollback must bring `log_id 68` back at all (not just in the
right status) while a failed-and-stuck-on-target restore would show it missing entirely.

| Measurement | Result |
|---|---|
| Date/time of drill | 2026-08-16, ~06:40:48–06:42:08 UTC |
| Failure injected (what, exactly) | `.env`'s `DATABASE_URL` temporarily repointed to `sqlite:///./var/nonexistent_rollback_drill/adas.db` after the restore's own DB swap, then a fresh `fastapi run` backend started against it. Genuine: `sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file`, `Application startup failed. Exiting.`, exit code 3. |
| Rollback triggered automatically? (Y/N) | **N (this session) / mechanism confirmed real** — same reasoning as 2026-08-11: triggered explicitly via `uv run python -m app.maintenance rollback` since the failure had to land at a precise point no single `-Action Restore` invocation can hook; identical `perform_rollback()` code path. |
| Rollback DB-file swap duration | 1.52ms (`rollback_swap_primary_database` step) |
| System confirmed back on the pre-restore (emergency) state? | **Yes** — after fixing `DATABASE_URL` and restarting, `log_id 68` read back as `Dismissed` (its state at the moment of the restore attempt), not absent (what the failed restore's older target would show, since that backup predates `log_id 68`). |
| Any manual intervention required beyond fixing the injected failure? | Restoring `DATABASE_URL` and re-running `-Action Start`; no other manual DB surgery needed. |

---

## 4 & 5. TC-R-401 / TC-R-402 — 24-hour endurance

**Target:** NFR-13 (99.9% uptime, no gradual degradation) — flat RAM (no
leak), GPU thermals within safe limits, VRAM locked (no creep).

**Prerequisites:**
- Backend + AI engine running continuously for the full 24 hours against
  at least 3 simulated concurrent camera streams (matching the paper's
  TC-R-401/402 pre-conditions).
- A way to sample RAM/GPU telemetry at fixed intervals without relying on
  the system being tested (e.g., an external `nvidia-smi` / Task Manager
  logging loop, or `GET /api/system/health/live` polled from a separate
  machine/process so the endurance test doesn't depend on its own subject).

**Procedure:**

1. Start the full stack, note the start timestamp.
2. Record readings at **start, 6h, 12h, 18h (optional), and 24h**:

| Time | System RAM used | GPU temp | GPU VRAM used | Backend process RAM | Notes |
|---|---|---|---|---|---|
| Start (0h) | | | | | |
| 6h | | | | | |
| 12h | | | | | |
| 18h | | | | | |
| 24h | | | | | |

3. At 24h, confirm:

| Check | Result |
|---|---|
| RAM trend flat (no continuous upward creep)? | |
| GPU temp stayed within `GPU_TEMP_CRITICAL_C` (85°C default)? | |
| No thermal throttling observed? | |
| VRAM allocation stable (no creep across the 24h)? | |
| Any crash, restart, or `Unresponsive` camera during the window? | |
| Daily restart (drill 1) fired correctly during this window? | |

### Results — 2026-08-11 (`be_audit/A6_manual_evidence.md`)

**Not executed this pass — a deliberate scope decision, not an oversight.** This procedure
requires a genuine, continuous 24-hour run; the owner was asked directly whether to (a) actually
run it in real time across this session via scheduled check-ins, (b) run a short window as an
explicitly-labelled proxy, or (c) leave it unexecuted and record that honestly, matching this
file's own existing framing for its as-yet-unrun procedures. The owner chose **(c)**. This is
therefore still owed, exactly as it was before this pass — the status below is unchanged from
"not yet run," not silently marked otherwise. `00_FINDINGS.md` F13 remains open for this
half; see that row for the honest state and the reasoning.

---

## 6. TC-S-203 — four-hour idle session

**Target:** NFR-19 — a persistent session receives WebSocket pushes at
hour 4 without requiring re-authentication.

**Prerequisites:** A browser logged into the dashboard, left genuinely
idle (no requests) for 4 hours. `SESSION_LIFETIME_MINUTES` defaults to
480 (8h), so 4h sits inside the window by construction — this drill
confirms that holds in practice, not just in the config value.

**Procedure:**

1. Log in, note the login timestamp.
2. Leave the dashboard tab open and genuinely idle for 4 hours (no
   interaction, no requests).
3. At hour 4, trigger a test alert (`seed_alerts_via_api.py`, or a live
   detection) targeting a camera visible on that dashboard.
4. Confirm the WebSocket push arrives and the alert renders, without any
   re-authentication prompt.
5. Record:

| Measurement | Result |
|---|---|
| Login timestamp | |
| Alert fired at (should be ~4h after login) | |
| Alert received without re-auth? (Y/N) | |
| Any WebSocket reconnect observed during the idle window? (check browser devtools) | |
| Session still valid per `GET /api/users/me`? | |

### Results — 2026-08-11 (`be_audit/A6_manual_evidence.md`)

**Not executed this pass — same owner decision as drill 4 & 5 above.** A genuine 4-hour idle
window was weighed against a shortened proxy or leaving it honestly unrun; the owner chose to
leave it unrun rather than accept a proxy that wouldn't actually close this out. Still owed.
`00_FINDINGS.md` F13 covers this half too.

---

## 7. TC-R-304 — browser crash / force-close recovery

**Target:** NFR-17 — reopening the browser after a crash repopulates all
`Unverified` alerts with zero data loss.

**Procedure:**

1. Trigger an alert so it's active and `Unverified` on the dashboard.
2. Force-close the browser tab/window (not a graceful logout — kill it).
3. Reopen the browser, navigate to the dashboard, log in if the session
   cookie didn't survive (it should, per D-006).
4. Confirm the previously `Unverified` alert repopulates automatically
   (the frontend's reconnect sequence: `CONNECTION_READY` →
   `GET /api/alerts/?status=Unverified,Ongoing` → `GET /api/cameras/` —
   `01_CONTRACTS.md` §9.5).
5. Record:

| Measurement | Result |
|---|---|
| Alert was still `Unverified` before the crash? | |
| Alert reappeared after reopening? (Y/N) | |
| Any data loss (missing fields, wrong status)? | |
| Time from reopen to alert visible | |

### Results — 2026-08-11 (`be_audit/A6_manual_evidence.md`)

**Methodology note:** the tooling available this session drives a browser pane, not a literal OS
process kill. To still test the thing this procedure actually cares about — session-cookie
persistence and the frontend's reconnect sequence after the previous tab is simply gone, not a
graceful logout — the previous tab was closed outright (not logged out) and a **new** tab opened
against the same origin, which is the closest faithful analog available: a genuinely separate
page load with no in-memory app state carried over, same cookie jar. Run jointly with drill 8
below — the 5 alerts open at crash time include the 3 fired for that drill.

| Measurement | Result |
|---|---|
| Alert was still `Unverified` before the crash? | Yes — 5 alerts `Unverified` (`log_id` 60, 61, 62, 63, 64), most recently `log_id 64`. |
| Alert reappeared after reopening? (Y/N) | **Y** — the reopened tab landed on the dashboard already authenticated (no login prompt: the session cookie survived), and the same `alertdialog` ("Accident Detected", `log_id 64`, "+4 more alerts queued") rendered immediately. |
| Any data loss (missing fields, wrong status)? | None — timestamp, camera name, and confidence score on the re-rendered modal matched the pre-crash values exactly. |
| Time from reopen to alert visible | Effectively immediate — the alert queue was already present in the very first page read after navigation completed (sub-second; not separately instrumented beyond that). |

---

## 8. TC-S-401 — three simultaneous cameras

**Target:** NFR-15 / D-008 — three cameras detecting at the same instant;
alerts queue and stack in the UI, none dropped.

**Prerequisites:** At least 3 camera feeds available (MediaMTX simulation
supports `channel{1..6}`) with sample videos that can be triggered to
"detect" close together in time, or `seed_alerts_via_api.py --camera-id
1 --camera-id 2 --camera-id 3` fired in rapid succession against a live
backend with a dashboard connected.

**Procedure:**

1. Connect a dashboard, confirm `CONNECTION_READY`.
2. Fire detections on 3 different cameras as close together as possible
   (ideally the same millisecond — in practice, back-to-back requests).
3. Confirm all 3 alerts appear, stacked, with no dropped alert and no UI
   crash.
4. Record:

| Measurement | Result |
|---|---|
| Number of cameras fired | |
| All 3 alerts received? (Y/N, which if not) | |
| UI remained stable (no crash/freeze)? | |
| Alerts correctly attributed to the right camera? | |
| Backend-side: any `409`s from the concurrency backstop (expected only if two events target the *same* camera, not 3 different ones)? | |

### Results — 2026-08-11 (`be_audit/A6_manual_evidence.md`)

**Methodology note:** `seed_alerts_via_api.py` (this procedure's suggested traffic-generation
tool) was deleted by the A3 audit pack (F3/F19 in `00_FINDINGS.md`) — its only caller was the
now-removed v1 route branch. Per F19's own suggested substitute, three direct
`POST /api/internal/alert` v2-shaped payloads were fired in rapid succession (three parallel
`curl` calls, ~0.9s spread from first to last) against cameras 2, 5, and 6 — chosen specifically
because neither of those cameras' feeds spontaneously re-trigger the live model (unlike cameras
1 and 4, whose looping demo clips do), keeping this a clean, isolated 3-camera burst rather than
racing the live AI engine.

| Measurement | Result |
|---|---|
| Number of cameras fired | 3 (camera IDs 2, 5, 6) |
| All 3 alerts received? (Y/N, which if not) | **Y, all 3** — `log_id` 62 (camera 2), 63 (camera 5), 64 (camera 6), each `201 Created`. |
| UI remained stable (no crash/freeze)? | Yes — the dashboard's alert modal correctly showed the most recent (`log_id 64`) plus "+4 more alerts queued" (the 3 from this drill plus 2 concurrently open from the live AI engine on cameras 1/4), no crash. |
| Alerts correctly attributed to the right camera? | Yes — verified via `GET /api/alerts/?status=Unverified`, each `log_id` maps to its intended `camera_id`. |
| Backend-side: any `409`s from the concurrency backstop (expected only if two events target the *same* camera, not 3 different ones)? | None — all three targeted distinct cameras, and all three returned `201`, as expected. |

Test data cleanup: all 5 open alerts from this drill and drill 7 (`log_id` 60–64) were
confirmed → resolved afterward; nothing was left `Unverified`/`Ongoing` on the dev DB.

---

## 9. Bi-annual restore drill (deployment-owned)

**Target:** D-011's archive/restore architecture, validated end-to-end in
an isolated environment — not a claim this package can execute, since it
requires physical/deployment infrastructure out of scope per D-001.

**Owner:** deployment. **Interface:** `ARCHIVE_DIR` (weekly air-gapped
archive staging, `(cd backend && uv run python -m app.maintenance archive)`) and the
restore procedure in drill 2 above, run against a completely separate
staging environment.

**Procedure (for the deployment owner to execute against real
infrastructure, not simulated here):**

1. Pull the latest archive from `ARCHIVE_DIR` (or its off-site copy) into
   an isolated staging environment — not the production edge server.
2. Run the full restore procedure (drill 2) against that staging copy.
3. Confirm the "flag-and-restart architecture" (the `restore_state.json`
   flag file + orchestrator restart sequence, `01_CONTRACTS.md` §3.10)
   behaves identically in staging as it does on the demo laptop.
4. Record:

| Measurement | Result |
|---|---|
| Date of drill | |
| Archive pulled from | |
| Staging environment description | |
| Restore succeeded in staging? | |
| Any staging-specific issues (paths, permissions, missing config)? | |

### Results — 2026-08-11 (`be_audit/A6_manual_evidence.md`)

**Not executed — confirmed out of scope for this package, not merely deferred.** This procedure's
own text names its owner as "deployment" and requires a separate staging environment outside
D-001's boundary for this backend package; there is no staging infrastructure to run it against.
Recorded as `blocked` (owner: deployment), not `pending`, since running it isn't something a
future backend-focused session can pick up either — it needs deployment infrastructure decisions
this package doesn't own.

---

## Summary

| # | Test case(s) | Status |
|---|---|---|
| 1 | TC-R-303 | 2026-08-11 **pass** (8.13s downtime, budget 10s). 2026-08-16 (P18 Step 8, the real *unattended* trigger): attempt 1 **failed** (genuine `UnicodeEncodeError` crash, found and fixed live — `PYTHONUTF8`), attempt 2 **passed** functionally (`LastTaskResult: 0`) but **over the 10s downtime budget** (19.8s–72.3s across this session's runs) under this session's own heavy concurrent resource load — see the 2026-08-16 results block for the full accounting |
| 2 | NFR-18 (no single TC id — the 60s restore window) | **pass** — 2026-08-11 (~26s) and 2026-08-16 regression re-run (~38s), both well inside the 60s budget |
| 3 | Rollback drill (D-011, no single TC id) | **pass** — 2026-08-11 and 2026-08-16 regression re-run, both with a genuine failure injected and rollback verified via a marker row |
| 4–5 | TC-R-401, TC-R-402 | not yet run — owner decision 2026-08-11, see results above |
| 6 | TC-S-203 | not yet run — owner decision 2026-08-11, see results above |
| 7 | TC-R-304 | **pass** — 2026-08-11, session + alert queue both survived a tab close/reopen |
| 8 | TC-S-401 | **pass** — 2026-08-11, 3/3 alerts received, correctly attributed, no drops |
| 9 | Bi-annual restore drill (deployment-owned) | **blocked** (deployment, no staging environment) — see results above |

Six of nine procedures executed 2026-08-11 as part of `be_audit/A6_manual_evidence.md`, all
passing. The three not run are a deliberate scope decision (the two real-time-duration drills)
or a genuine out-of-package-scope block (the bi-annual drill), not an oversight — see each
procedure's Results section above for the specific reasoning. P18 (2026-08-16) re-ran drills 1–3
against the real unattended trigger and the sidecar-fix regression: two real bugs found and fixed
live (backend `UnicodeEncodeError` under a redirected console codepage; AI-engine stdout
block-buffering), one pre-existing bug found and fixed as a side effect (`Write-Error` silently
discarding intended exit codes under `$ErrorActionPreference = "Stop"`), and the restart downtime
budget missed on every run this session under self-inflicted concurrent load (recorded honestly,
not re-run quietly until a passing number appeared) — see `be_audit/00_FINDINGS.md`'s F22
resolution-log entry for the full account. `be_plan/TRACEABILITY.md` and `be_audit/00_FINDINGS.md`
reflect this same state.
