# WSL2 / Linux Verification Lane — Optional

> **Status:** written, **not scheduled**. This exists so the option is costed and ready if the team
> decides to take it. Nothing in packages P1–P9 depends on it.
> **Relevant decisions:** D-009 (demo vs production-target evidence), D-011 (demo vs production
> orchestration).

---

## The question this answers

*"Should we demo in Docker or WSL? Would it only work there and not on the laptop?"*

**No, and no.**

**Do not demo in a container.** The AI engine needs the RTX 3050 Ti. WSL2 GPU passthrough works, but
it means matching the Windows driver to the WSL CUDA runtime, rebuilding the TensorRT engine inside
WSL (`best.engine` is compiled for one specific GPU + driver + TensorRT combination), and getting RTSP
across the WSL network boundary. That is a lot of new failure surface for zero benefit on demo day.

**Nothing becomes Linux-only.** The architecture already prevents that. Per D-011, backup, integrity
validation, restore, emergency rollback, WAL/SHM cleanup, and atomic file replacement are **pure
cross-platform Python** (`sqlite3.Connection.backup()`, `PRAGMA integrity_check`, `os.replace`).
systemd and PowerShell are ~100-line wrappers that invoke the same `python -m app.maintenance`
commands. The logic is shared; only the trigger differs.

So: **demo natively on Windows.** WSL2 is useful for exactly one thing.

---

## What WSL2 would actually buy you

One sentence in the paper.

Without it, P7's systemd units, the 3 AM restart timer, and the offline restore orchestration ship as
*"written and reviewed, unverified on Linux — production-target."* With a few hours in WSL2 they
become *"verified in WSL2 Ubuntu 24.04, pending production-hardware acceptance."*

That matters for **NFR-16** (daily restart, <10s recovery) and **NFR-18** (60-second admin recovery),
which are otherwise the two NFRs with the weakest evidence. It also flushes out the genuinely
platform-specific bugs — path separators, file locking semantics, permission bits, service ordering —
that a Windows-only test run cannot find.

**What it does not buy:** anything about GPU behavior, inference throughput, camera capacity, thermals,
or VRAM. Those need the real 8× L4 server and stay `Needs Evidence` regardless (D-009).

---

## Scope, if you do it

**Backend and SQLite only. No AI engine, no GPU, no RTSP.**

That is what makes it cheap: no CUDA in WSL, no TensorRT rebuild, no driver matching. The AI engine is
mocked with a script that POSTs heartbeats and detections over HTTP — the backend cannot tell the
difference, and the systemd units are what you are testing, not the model.

---

## Setup outline

### 1. Environment

```bash
wsl --install -d Ubuntu-24.04
```

Inside WSL: install `uv`, clone the repo (into the **WSL filesystem**, `~/adas-capstone`, not
`/mnt/c/…` — 9p filesystem performance and file-locking semantics on `/mnt/c` are different enough to
invalidate the SQLite results), then `uv sync` and `cp .env.example .env`.

Enable systemd if it is not already on:

```ini
# /etc/wsl.conf
[boot]
systemd=true
```

Then `wsl --shutdown` and reopen.

### 2. Install the units

The units P7 writes, plus a restricted maintenance unit:

```
/etc/systemd/system/adas-backend.service
/etc/systemd/system/adas-maintenance.service     # oneshot: python -m app.maintenance restart
/etc/systemd/system/adas-maintenance.timer       # daily at MAINTENANCE_HOUR_LOCAL
/etc/systemd/system/adas-restore.service         # oneshot: python -m app.maintenance restore
```

D-011 requires these to be **restricted** — able to perform only the approved ADAS maintenance
workflow, never arbitrary commands. Use `ExecStart` with a fixed argument list (no shell), a dedicated
non-root `User=`, `ProtectSystem=strict` with an explicit `ReadWritePaths=` covering only the database,
backup, and export directories, `NoNewPrivileges=yes`, and `PrivateTmp=yes`.

The restore unit is the one that matters architecturally: it is what runs **while FastAPI is stopped**,
which is the entire reason restore is offline (a running process cannot safely replace its own WAL-mode
database).

### 3. Fake the AI engine

A ~40-line script posting a heartbeat every 3 seconds and an occasional detection, so cameras report
`Connected`/`Active` and the restart drill can measure "time until a fresh heartbeat arrives" — one of
the timings NFR-16 asks for.

---

## Drills to run and record

| Drill | Measures | Records |
|---|---|---|
| **Daily restart** (`systemctl start adas-maintenance`) | NFR-16, TC-R-303 | backup duration **separately from** restart downtime; time to `/healthz/ready`; time to first fresh heartbeat |
| **Restore** (`POST /api/system/restores` → flag file → `adas-restore.service`) | NFR-18 | total time from request to serving traffic again; target **60 seconds** |
| **Rollback** (break startup deliberately, e.g. an unwritable `DATABASE_URL`) | D-011 | that the emergency pre-restore backup is restored and the original system comes back |
| **Online backup under write load** | NFR-18, TC-U-402 | that no request fails with "database is locked" while a backup runs |
| **Timer firing** | NFR-16 | set `MAINTENANCE_HOUR_LOCAL` to a minute from now and confirm the timer actually fires |

Write the results into `be_plan/EVIDENCE.md` (created in P9) alongside the Windows numbers, clearly
labeled **WSL2 Ubuntu 24.04, not production hardware**.

---

## Honest limitations to state in the paper

WSL2 is not a Linux server. Say so rather than overclaiming:

- **The filesystem is not the target's.** WSL2 uses ext4 on a virtual disk. RAID 1 NVMe behavior,
  `fsync` latency, and therefore `synchronous=FULL` cost are all different.
- **Timekeeping drifts** across Windows sleep/resume, which can make a timer fire late in a way real
  hardware would not.
- **systemd in WSL2 is a supported but non-standard PID 1 arrangement.** Service ordering and
  dependency handling are close to a real Linux boot, not identical to it.
- **No GPU, no RTSP, no AI engine.** Nothing here says anything about inference.

The honest claim is: *"The maintenance orchestration, service ordering, offline restore, and rollback
path were verified on Linux under WSL2. Timing figures are indicative; production-hardware acceptance
remains pending."* That is a materially stronger statement than "written but untested", and it is true.

---

## Cost estimate

Roughly half a day: environment setup, writing the fake AI heartbeat script, installing and debugging
the units, running the five drills, recording results.

The most likely time sink is the restricted-unit hardening (`ProtectSystem=strict` +
`ReadWritePaths=`), which will fail a few times before the paths are right. That failure is itself
useful — it is exactly the class of bug that would otherwise surface on the real edge server.

---

## If you skip it

Everything still works. P7 ships:

- the cross-platform Python maintenance core — **fully tested** on Windows
- the PowerShell orchestrator and Windows Scheduled Task — **fully tested**
- the systemd units — reviewed, labeled *production-target, unverified*

The paper reports Windows-measured timings for NFR-16 and NFR-18 and labels the Linux artifacts as
pending. That is a defensible position given the deployment reality, as long as it is stated plainly
rather than glossed over.
