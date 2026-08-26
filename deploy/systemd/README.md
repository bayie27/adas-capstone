# Linux systemd units — production-target, reviewed-but-unverified

These unit files are the Linux production counterpart to
`scripts/adas-maintenance.ps1` (the Windows demo orchestrator). They are
**reviewed but not exercised on real Linux hardware** as part of this
package — the demo laptop is Windows. Treat them as deployment artifacts
whose live systemd behavior still needs Linux verification.

## Files

- `adas-maintenance.service` — restricted oneshot unit that runs
  `backend/scripts/daily_restart.sh`. Its `ExecStart` can invoke **only**
  that one approved script — this is the "restricted systemd service ...
  that can invoke only the approved ADAS maintenance workflow" the package
  doc calls for, not a general-purpose shell.
- `adas-maintenance.timer` — fires the unit above daily at a **local**-time
  `OnCalendar`, deliberately local rather than UTC, matching D-011's
  "low-traffic window" being a wall-clock concept. `Persistent=true` so a
  missed firing (host was off) catches up once, rather than silently
  skipping a day (edge case 5.11). **Its `OnCalendar=*-*-* 03:00:00` is
  still a hardcoded literal, not read from `MAINTENANCE_HOUR_LOCAL`**
  (`.env`) — a static systemd unit file can't read a live env value
  without a templating/generator step, and building one is out of this
  package's scope (`be_plan/18_PKG_scheduled_maintenance.md` only builds
  the Windows equivalent, `scripts/register-maintenance-task.ps1`).
  Edit the literal by hand if the deployment's restart hour differs from
  3 AM. The _backup_ half is different: `app.main`'s in-app APScheduler
  job reads `MAINTENANCE_HOUR_LOCAL` directly and is genuinely live on
  both platforms, since it's plain Python running inside the backend
  process rather than a static OS unit file.
- `adas-restore-coordinator.service` — the independently supervised
  coordinator. It publishes a heartbeat, claims one durable restore request
  at a time, waits for its grace/expiry rules, and invokes only the fixed
  restore wrapper. It has no `PartOf=` relationship to the backend or AI
  units: an application outage must not take down the coordinator.
- `backend/scripts/restore_requested.sh` — validates exactly one bare backup
  identifier, stops the AI service before the backend, invokes the shared
  offline restore core as `ADAS_SERVICE_USER`, restarts the exact service
  pair, requires readiness and an AI heartbeat, and performs the emergency
  rollback path on failure. It contains no `eval` or user-controlled command
  execution.
- `backend/scripts/daily_restart.sh` — its own backup phase calls
  `python -m app.maintenance backup --origin scheduled`, same as the
  Windows `-Action Restart` backup phase. That command now skips writing
  a redundant backup when the in-app cron job already covered today's
  obligation (`scheduled_backup_is_due`, `18_PKG_scheduled_maintenance.md`
  Step 1) — both platforms get this for free from the one shared command
  they both call, with no dedup logic duplicated in either script.
- `adas-backend.service.example`, `adas-ai-engine.service.example` —
  illustrative application-service templates with ordering on the
  coordinator. The AI unit preserves its backend requirement; copy and adapt
  the user, paths, resource limits, and restart policy for the host.

## Install (sketch, not verified)

```bash
sudo cp deploy/systemd/adas-maintenance.service /etc/systemd/system/
sudo cp deploy/systemd/adas-maintenance.timer /etc/systemd/system/
sudo cp deploy/systemd/adas-restore-coordinator.service /etc/systemd/system/
sudo cp deploy/systemd/adas-backend.service.example /etc/systemd/system/adas-backend.service
sudo cp deploy/systemd/adas-ai-engine.service.example /etc/systemd/system/adas-ai-engine.service
sudo chmod 0750 backend/scripts/restore_requested.sh
sudo systemctl daemon-reload
sudo systemctl enable --now adas-restore-coordinator.service adas-backend.service adas-ai-engine.service adas-maintenance.timer
```

Adjust `WorkingDirectory`, `PYTHONPATH`, `User`/`Group`, and the controlled
service account before installing. Set `ADAS_SERVICE_USER`,
`ADAS_BACKEND_SERVICE`, and `ADAS_AI_SERVICE` only in the coordinator/unit
environment, using the exact unit names deployed on the host. The coordinator
unit remains root-supervised because it controls `systemctl`; the shared
maintenance lease and restore-state directory must remain writable by the
dedicated `adas` service user so the fixed runner can perform database work.

Static validation completed in this repository is limited to source-level
inspection on Windows. Run `bash -n` for both shell scripts and
`systemd-analyze verify` for every unit on the Linux target; live ordering,
permissions, readiness, restore, and rollback remain Linux-unverified.
