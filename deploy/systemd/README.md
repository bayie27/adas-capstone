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
- `adas-maintenance.timer` — fires the unit above daily at 3:00 AM
  **local** time (`MAINTENANCE_HOUR_LOCAL`, `.env`) — deliberately local,
  not UTC, matching D-011's "low-traffic window" being a wall-clock
  concept. `Persistent=true` so a missed firing (host was off) catches up
  once, rather than silently skipping a day (edge case 5.11).
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
