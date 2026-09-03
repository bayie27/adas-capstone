#!/usr/bin/env bash
# REVIEWED-BUT-UNVERIFIED, PRODUCTION-TARGET — invoked only by
# adas-restore-coordinator.service.  The coordinator validates the request
# before it reaches this fixed wrapper; this second boundary keeps the unit
# safe when called directly by a deployment test.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

SERVICE_USER="${ADAS_SERVICE_USER:-adas}"
BACKEND_SERVICE="${ADAS_BACKEND_SERVICE:-adas-backend.service}"
AI_SERVICE="${ADAS_AI_SERVICE:-adas-ai-engine.service}"
READY_TIMEOUT_SECONDS="${ADAS_READY_TIMEOUT_SECONDS:-60}"
UV_BIN="${ADAS_UV_BIN:-/usr/local/bin/uv}"

if [[ "$#" -ne 2 || ! "$1" =~ ^[0-9a-f]{32}$ || ! "$2" =~ ^(protected|degraded)$ ]]; then
    echo "restore_requested: a valid restore-point identifier and storage tier are required" >&2
    exit 2
fi
if [[ ! "$BACKEND_SERVICE" =~ ^[A-Za-z0-9_.@-]+\.service$ || ! "$AI_SERVICE" =~ ^[A-Za-z0-9_.@-]+\.service$ ]]; then
    echo "restore_requested: uncontrolled systemd service name" >&2
    exit 2
fi
if [[ ! "$SERVICE_USER" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]]; then
    echo "restore_requested: uncontrolled service user" >&2
    exit 2
fi

BACKUP_ID="$1"
STORAGE_TIER="$2"

run_maintenance() {
    runuser -u "$SERVICE_USER" -- env PYTHONPATH="$REPO_ROOT/backend" "$UV_BIN" run python -m app.maintenance "$@"
}

start_services() {
    systemctl start "$BACKEND_SERVICE" && systemctl start "$AI_SERVICE"
}

wait_for_services() {
    run_maintenance restart --phase wait --timeout "$READY_TIMEOUT_SECONDS" --require-heartbeat
}

echo "restore_requested: stopping the controlled services"
systemctl stop "$AI_SERVICE"
systemctl stop "$BACKEND_SERVICE"
if systemctl is-active --quiet "$AI_SERVICE" || systemctl is-active --quiet "$BACKEND_SERVICE"; then
    echo "restore_requested: a service remained active; refusing database work" >&2
    exit 1
fi

echo "restore_requested: applying the selected restore point"
if ! run_maintenance restore "$BACKUP_ID" --storage-tier "$STORAGE_TIER"; then
    echo "restore_requested: database work failed; starting the original services" >&2
    if start_services && wait_for_services; then
        exit 1
    fi
    echo "restore_requested: original services did not recover" >&2
    exit 2
fi

echo "restore_requested: starting the restored services"
if start_services && wait_for_services; then
    if run_maintenance restore --finalize completed; then
        exit 0
    fi
    echo "restore_requested: could not finalize the healthy restore" >&2
fi

echo "restore_requested: readiness failed; rolling back the emergency backup" >&2
systemctl stop "$AI_SERVICE" || true
systemctl stop "$BACKEND_SERVICE" || true
if systemctl is-active --quiet "$AI_SERVICE" || systemctl is-active --quiet "$BACKEND_SERVICE"; then
    echo "restore_requested: a service remained active; refusing rollback database work" >&2
    exit 2
fi
if ! run_maintenance rollback; then
    echo "restore_requested: rollback failed" >&2
    exit 2
fi
if ! start_services || ! wait_for_services; then
    echo "restore_requested: rolled-back services did not become ready" >&2
    exit 2
fi
echo "restore_requested: rollback complete"
exit 1
