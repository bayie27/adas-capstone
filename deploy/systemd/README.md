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
  skipping a day (edge case 5.11). The unit's calendar is a deployment
  value and must be regenerated/edited when `MAINTENANCE_HOUR_LOCAL` differs
  from 3 AM; the in-app backup job reads the `.env` setting directly.
- `adas-restore-coordinator.service` — the independently supervised
  coordinator. It publishes a heartbeat, claims one durable restore request
  at a time, waits for its grace/expiry rules, and invokes only the fixed
  restore wrapper. It has no `PartOf=` relationship to the backend or AI
  units: an application outage must not take down the coordinator.
- `backend/scripts/restore_requested.sh` — validates one bare backup
  identifier plus its `protected`/`degraded` storage tier, stops the AI
  service before the backend, invokes the shared offline restore core as
  `ADAS_SERVICE_USER`, restarts the exact service pair, requires readiness
  and an AI heartbeat, and performs the local emergency rollback path on
  failure. It contains no `eval` or user-controlled command execution.
- `backend/scripts/daily_restart.sh` — its own backup phase calls
  `python -m app.maintenance backup --origin scheduled`, same as the
  Windows `-Action Restart` backup phase. That command prefers
  `PROTECTED_BACKUP_DIR`, falls back to `BACKUP_DIR` with a visible degraded
  reason, and skips a redundant backup when daily continuity is already
  satisfied. A recent degraded backup does not mask protected overdue state
  once the external device returns.
- `adas-backend.service.example`, `adas-ai-engine.service.example` —
  illustrative application-service templates with ordering on the
  coordinator. The AI unit preserves its backend requirement; copy and adapt
  the user, paths, resource limits, and restart policy for the host.

## Protected storage

Set `PROTECTED_BACKUP_DIR` and `PROTECTED_ARCHIVE_DIR` in the deployment
environment to absolute paths on the explicitly mounted backup device. Keep
`BACKUP_DIR` as the local control/state root: it holds the restore request,
coordinator heartbeat, lease, and local degraded fallback. The Python storage
provider compares physical devices and rejects same-disk partitions, bind or
folder mounts, missing/read-only/full media, and unverifiable targets. No
removable-device discovery is performed. The restore wrapper receives the
selected `protected` or `degraded` tier so media loss cannot change the
restore point during a run.

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
