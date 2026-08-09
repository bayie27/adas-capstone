#!/usr/bin/env bash
# Linux production-target daily restart shim (be_plan/08_PKG_backup_ops.md
# Step 7, D-011). Invoked by adas-maintenance.timer -> adas-maintenance.service
# (see deploy/systemd/), never run directly by an operator on the demo laptop.
#
# REVIEWED-BUT-UNVERIFIED, PRODUCTION-TARGET: written to the same contract as
# the Windows demo script (scripts/adas-maintenance.ps1) and exercised
# locally against the maintenance CLI, but never run against real systemd
# unit files on real Linux hardware as part of this package. Treat the
# systemctl calls and paths below as a reviewed starting point for whoever
# stands up the production host, not a verified deployment artifact.
#
# Sequence, matching D-011 Step 7 exactly:
#   1. online backup (services stay up)
#   2. systemd restarts the backend + AI engine services natively
#   3. wait for /healthz/ready and a fresh AI heartbeat, timed separately
#      from the backup

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

BACKEND_SERVICE="${ADAS_BACKEND_SERVICE:-adas-backend.service}"
AI_SERVICE="${ADAS_AI_SERVICE:-adas-ai-engine.service}"
READY_TIMEOUT_SECONDS="${ADAS_READY_TIMEOUT_SECONDS:-60}"

log() {
    echo "[daily_restart] $*"
}

run_maintenance() {
    (cd "$REPO_ROOT/backend" && uv run python -m app.maintenance "$@")
}

log "Phase 1/2: online backup."
if ! run_maintenance backup --origin scheduled; then
    log "ERROR: scheduled backup failed; aborting restart without touching running services."
    exit 1
fi

log "Phase 2/2: restart downtime."
restart_start=$(date +%s)

# systemd owns process supervision here — restarting the unit is the
# native equivalent of the demo script's Stop-Process/Start-Process pair,
# and gets systemd's own crash/restart guarantees for free.
systemctl restart "$AI_SERVICE"
systemctl restart "$BACKEND_SERVICE"

if run_maintenance restart --phase wait --timeout "$READY_TIMEOUT_SECONDS"; then
    restart_end=$(date +%s)
    log "Restart downtime: $((restart_end - restart_start)) seconds."
    exit 0
else
    restart_end=$(date +%s)
    log "ERROR: restart did not reach ready+heartbeat within ${READY_TIMEOUT_SECONDS}s (waited $((restart_end - restart_start))s). Investigate before relying on this instance."
    exit 1
fi
