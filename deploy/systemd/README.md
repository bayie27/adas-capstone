# Linux systemd units — production-target, reviewed-but-unverified

These unit files are the Linux production counterpart to
`scripts/adas-maintenance.ps1` (the Windows demo orchestrator). They are
**reviewed but not exercised on real Linux hardware** as part of this
package — the demo laptop is Windows. Treat them as a reviewed starting
point for whoever stands up the production host, not a verified deployment
artifact (see `08_PKG_backup_ops.md`'s deployment note).

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
- `backend/scripts/daily_restart.sh` — its own backup phase calls
  `python -m app.maintenance backup --origin scheduled`, same as the
  Windows `-Action Restart` backup phase. That command now skips writing
  a redundant backup when the in-app cron job already covered today's
  obligation (`scheduled_backup_is_due`, `18_PKG_scheduled_maintenance.md`
  Step 1) — both platforms get this for free from the one shared command
  they both call, with no dedup logic duplicated in either script.
- `adas-backend.service.example`, `adas-ai-engine.service.example` —
  illustrative templates for the application services themselves.
  Defining and hardening those (user, working directory, resource limits,
  restart policy) is a broader production deployment concern outside this
  package's scope (D-001 boundary) — copy and adapt, don't use as-is.

## Install (sketch, not verified)

```bash
sudo cp deploy/systemd/adas-maintenance.service /etc/systemd/system/
sudo cp deploy/systemd/adas-maintenance.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now adas-maintenance.timer
```

Adjust `WorkingDirectory`/`User` in the unit file to match the actual
deployment path and service account before installing.
