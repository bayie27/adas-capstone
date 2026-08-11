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

---

## Summary

| # | Test case(s) | Status |
|---|---|---|
| 1 | TC-R-303 | not yet run |
| 2 | NFR-18 (no single TC id — the 60s restore window) | not yet run |
| 3 | Rollback drill (D-011, no single TC id) | not yet run |
| 4–5 | TC-R-401, TC-R-402 | not yet run |
| 6 | TC-S-203 | not yet run |
| 7 | TC-R-304 | not yet run |
| 8 | TC-S-401 | not yet run |
| 9 | Bi-annual restore drill (deployment-owned) | not yet run |

None of these nine procedures have been executed as of this package
landing — writing the playbook and running it are separate work, and
`TRACEABILITY.md` marks each corresponding test case `pending` for
exactly that reason. This is the honest state, not an oversight.
