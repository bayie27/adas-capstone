#!/usr/bin/env bash
# Linux production-target offline restore + automatic rollback
# (be_plan/08_PKG_backup_ops.md Step 6, D-011). Run manually by an
# administrator (or via a restricted `adas-restore@.service` instance unit,
# not shipped here) — never on a timer.
#
# REVIEWED-BUT-UNVERIFIED, PRODUCTION-TARGET — see daily_restart.sh's header
# for the same caveat: reviewed against the maintenance CLI, never exercised
# against real systemd units on real Linux hardware.
#
# Usage: offline_restore.sh <backup_id>

set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <backup_id>" >&2
    exit 2
fi

BACKUP_ID="$1"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

BACKEND_SERVICE="${ADAS_BACKEND_SERVICE:-adas-backend.service}"
AI_SERVICE="${ADAS_AI_SERVICE:-adas-ai-engine.service}"
READY_TIMEOUT_SECONDS="${ADAS_READY_TIMEOUT_SECONDS:-60}"

log() {
    echo "[offline_restore] $*"
}

run_maintenance() {
    (cd "$REPO_ROOT/backend" && uv run python -m app.maintenance "$@")
}

log "Stopping services for offline restore of backup $BACKUP_ID..."
systemctl stop "$AI_SERVICE" || true
systemctl stop "$BACKEND_SERVICE" || true

log "Running offline restore..."
if ! run_maintenance restore "$BACKUP_ID"; then
    log "ERROR: offline restore failed before touching the primary database. Restarting original services unchanged."
    systemctl start "$BACKEND_SERVICE"
    systemctl start "$AI_SERVICE"
    run_maintenance restart --phase wait --timeout "$READY_TIMEOUT_SECONDS" || true
    exit 1
fi

log "Database swapped. Starting services..."
systemctl start "$BACKEND_SERVICE"
systemctl start "$AI_SERVICE"

if run_maintenance restart --phase wait --timeout "$READY_TIMEOUT_SECONDS"; then
    log "Restore verified healthy. Finalizing."
    run_maintenance restore --finalize completed
    exit 0
fi

log "ERROR: restored system failed to become healthy. Rolling back to the emergency pre-restore backup."
systemctl stop "$AI_SERVICE" || true
systemctl stop "$BACKEND_SERVICE" || true

rollback_ok=0
run_maintenance rollback || rollback_ok=$?

systemctl start "$BACKEND_SERVICE"
systemctl start "$AI_SERVICE"

if [ "$rollback_ok" -ne 0 ] || ! run_maintenance restart --phase wait --timeout "$READY_TIMEOUT_SECONDS"; then
    log "ROLLBACK FAILED or the rolled-back system did not become healthy. Manual intervention required."
    exit 2
fi

log "Rollback complete; original system restored."
exit 1
