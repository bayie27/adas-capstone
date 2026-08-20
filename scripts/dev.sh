#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# dev.sh — Production-ready ADAS development environment launcher
#
# Usage:
#   ./scripts/dev.sh              # Standard mode
#   ./scripts/dev.sh --logs       # Keep logs visible (no background)
#   ./scripts/dev.sh --verbose    # Trace all commands
#   ./scripts/dev.sh --clean      # Kill ports and exit
#
# Features:
#   ✓ Dependency validation (uv, pnpm, curl)
#   ✓ Health checks for both servers
#   ✓ Environment setup (.env, PYTHONPATH, NODE_ENV)
#   ✓ Graceful port cleanup (SIGTERM, then SIGKILL if stubborn)
#   ✓ Persistent logs for debugging
#   ✓ Graceful shutdown with timeout, safe against double-trap firing
#   ✓ Exits promptly if either server crashes (bash 3.2-compatible polling loop)
#   ✓ Cross-platform support (macOS incl. bash 3.2, Linux, WSL)
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Global Config ────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
readonly ROOT_DIR
readonly LOGS_DIR="${ROOT_DIR}/.logs"
readonly BACKEND_LOG="${LOGS_DIR}/backend.log"
readonly FRONTEND_LOG="${LOGS_DIR}/frontend.log"

readonly BACKEND_PORT="${BACKEND_PORT:-8000}"
readonly FRONTEND_PORT="${FRONTEND_PORT:-5173}"
readonly BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
readonly HEALTH_CHECK_TIMEOUT="${HEALTH_CHECK_TIMEOUT:-30}"
readonly SHUTDOWN_TIMEOUT="${SHUTDOWN_TIMEOUT:-10}"
readonly PORT_KILL_GRACE="${PORT_KILL_GRACE:-1}"   # seconds to wait after SIGTERM before SIGKILL

# ── Flags ────────────────────────────────────────────────────────────────────
VERBOSE=0
KEEP_LOGS=0
CLEAN_ONLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --verbose)  VERBOSE=1 ;;
    --logs)     KEEP_LOGS=1 ;;
    --clean)    CLEAN_ONLY=1 ;;
    *)          echo "Unknown option: $1"; exit 1 ;;
  esac
  shift
done

[[ $VERBOSE -eq 1 ]] && set -x

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
BOLD='\033[1m'
RESET='\033[0m'

# ── Logging / Output Functions ───────────────────────────────────────────────
log_info()    { echo -e "${CYAN}ℹ ${RESET}$*" >&2; }
log_success() { echo -e "${GREEN}✓ ${RESET}$*" >&2; }
log_warn()    { echo -e "${YELLOW}⚠ ${RESET}$*" >&2; }
log_error()   { echo -e "${RED}✗ ${RESET}$*" >&2; }
log_debug()   { [[ $VERBOSE -eq 1 ]] && echo -e "${BLUE}◆ ${RESET}$*" >&2 || true; }

# ── Ensure project root ──────────────────────────────────────────────────────
if [[ "$PWD" != "$ROOT_DIR" ]]; then
  log_warn "Not in project root. Changing to: $ROOT_DIR"
  cd "$ROOT_DIR"
fi

# ── Setup logging ────────────────────────────────────────────────────────────
mkdir -p "$LOGS_DIR"
log_debug "Logs directory: $LOGS_DIR"

# ── Platform detection ───────────────────────────────────────────────────────
detect_platform() {
  local os
  os=$(uname -s)
  case "$os" in
    Darwin)  echo "macos" ;;
    Linux)   echo "linux" ;;
    *)       echo "unknown" ;;
  esac
}

PLATFORM=$(detect_platform)
readonly PLATFORM
# NOTE: ${PLATFORM^^} (bash 4+ case conversion) breaks on stock macOS, which
# ships bash 3.2 by default. Use tr for portability instead.
PLATFORM_UPPER=$(echo "$PLATFORM" | tr '[:lower:]' '[:upper:]')
readonly PLATFORM_UPPER
log_debug "Detected platform: $PLATFORM"

# ── Dependency checks ────────────────────────────────────────────────────────
check_command() {
  local cmd="$1"
  local install_hint="${2:-Please install it first}"
  if ! command -v "$cmd" &>/dev/null; then
    log_error "Required command '$cmd' not found."
    log_error "$install_hint"
    return 1
  fi
  log_debug "✓ Found: $cmd ($(command -v "$cmd"))"
}

log_info "Validating dependencies..."
check_command "uv" "Install: https://docs.astral.sh/uv/getting-started/" || exit 1
check_command "pnpm" "Install: https://pnpm.io/installation" || exit 1
check_command "curl" "Required for health checks" || exit 1

log_success "All dependencies available"

# ── Port management ──────────────────────────────────────────────────────────
get_pids_on_port() {
  local port="$1"
  if [[ "$PLATFORM" == "macos" ]] || [[ "$PLATFORM" == "linux" ]]; then
    lsof -ti :"$port" 2>/dev/null || true
  else
    log_warn "Cannot check port $port on this platform"
    return 0
  fi
}

# Graceful-then-forceful port cleanup: SIGTERM first so processes can release
# resources cleanly, then SIGKILL only if they're still hanging around.
free_port() {
  local port="$1"
  local pids
  pids=$(get_pids_on_port "$port")

  if [[ -z "$pids" ]]; then
    log_debug "Port $port is free"
    return 0
  fi

  # NOTE: `xargs -r` (skip if input is empty) is GNU-only; BSD xargs on macOS
  # lacks -r, so guard emptiness with an explicit [[ -n ]] check instead of
  # relying on the flag.
  log_warn "Port $port in use (PID: $pids). Sending SIGTERM..."
  [[ -n "$pids" ]] && echo "$pids" | xargs kill 2>/dev/null || true
  sleep "$PORT_KILL_GRACE"

  local stubborn_pids
  stubborn_pids=$(get_pids_on_port "$port")
  if [[ -n "$stubborn_pids" ]]; then
    log_warn "Port $port still in use (PID: $stubborn_pids). Forcing SIGKILL..."
    echo "$stubborn_pids" | xargs kill -9 2>/dev/null || true
    sleep 0.5
  fi

  local remaining
  remaining=$(get_pids_on_port "$port")
  if [[ -n "$remaining" ]]; then
    log_error "Failed to free port $port (still held by: $remaining)"
    return 1
  fi

  log_debug "Port $port is free"
  return 0
}

# ── Health checks ────────────────────────────────────────────────────────────
wait_for_service() {
  local name="$1"
  local url="$2"
  local timeout="$3"
  local elapsed=0
  local interval=1

  log_info "Checking $name at $url..."

  while [[ $elapsed -lt $timeout ]]; do
    if curl -sf "$url" >/dev/null 2>&1; then
      log_success "$name is healthy"
      return 0
    fi

    log_debug "  $name not ready ($elapsed/${timeout}s)..."
    sleep "$interval"
    elapsed=$((elapsed + interval))
  done

  log_error "$name failed to start within ${timeout}s"
  return 1
}

# ── Environment setup ────────────────────────────────────────────────────────
setup_environment() {
  log_info "Setting up environment..."

  # Load .env if it exists. `allexport` ensures plain KEY=VALUE lines are
  # exported to child processes (uv, pnpm) even if the file doesn't use
  # explicit `export` statements itself.
  if [[ -f "$ROOT_DIR/.env" ]]; then
    log_debug "Loading .env"
    set -o allexport
    # shellcheck source=/dev/null
    source "$ROOT_DIR/.env"
    set +o allexport
  fi

  # Ensure critical env vars
  export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH:-}"
  export NODE_ENV="${NODE_ENV:-development}"

  log_debug "PYTHONPATH=$PYTHONPATH"
  log_debug "NODE_ENV=$NODE_ENV"
}

# ── Signal handlers ──────────────────────────────────────────────────────────
BACKEND_PID=""
FRONTEND_PID=""
SERVERS_STARTED=0  # only print "stopped" message if servers actually started
CLEANED_UP=0       # guards against cleanup running twice (trap fires on both the
                   # signal AND the EXIT that cleanup's own `exit` call triggers)

cleanup() {
  local exit_code=$?

  if [[ $CLEANED_UP -eq 1 ]]; then
    return
  fi
  CLEANED_UP=1

  echo ""

  if [[ $SERVERS_STARTED -eq 1 ]]; then
    log_warn "Shutting down servers (timeout: ${SHUTDOWN_TIMEOUT}s)..."

    local pids=()
    [[ -n "$BACKEND_PID" ]]  && pids+=("$BACKEND_PID")
    [[ -n "$FRONTEND_PID" ]] && pids+=("$FRONTEND_PID")

    # Send SIGTERM first.
    # FIX: Use ${arr[@]+"${arr[@]}"} instead of ${arr[@]} — with set -u, bash 3.2
    # raises "unbound variable" when expanding an empty array, unlike bash 4.4+.
    for pid in "${pids[@]+"${pids[@]}"}"; do
      kill "$pid" 2>/dev/null || true
    done

    # Wait with timeout.
    # FIX: sleep duration (1s) must match the elapsed increment (1) or
    # SHUTDOWN_TIMEOUT silently becomes a fraction of its configured value.
    local elapsed=0
    while [[ ${#pids[@]} -gt 0 ]] && [[ $elapsed -lt $SHUTDOWN_TIMEOUT ]]; do
      local alive=()
      for pid in "${pids[@]+"${pids[@]}"}"; do
        if kill -0 "$pid" 2>/dev/null; then
          alive+=("$pid")
        fi
      done
      pids=("${alive[@]+"${alive[@]}"}")

      if [[ ${#pids[@]} -gt 0 ]]; then
        sleep 1
        elapsed=$((elapsed + 1))
      fi
    done

    # Force kill any stragglers
    for pid in "${pids[@]+"${pids[@]}"}"; do
      kill -9 "$pid" 2>/dev/null || true
    done

    log_success "All servers stopped"
    log_info "Logs saved to: $LOGS_DIR"
  fi

  exit "$exit_code"
}

trap cleanup SIGINT SIGTERM EXIT

# ── Main flow ────────────────────────────────────────────────────────────────
print_banner() {
  echo ""
  echo -e "${BOLD}${CYAN}╔════════════════════════════════════════════════╗${RESET}"
  echo -e "${BOLD}${CYAN}║   ADAS Development Environment (${PLATFORM_UPPER})       ║${RESET}"
  echo -e "${BOLD}${CYAN}╚════════════════════════════════════════════════╝${RESET}"
  echo ""
}

main() {
  print_banner

  # Clean mode: just kill ports and exit
  if [[ $CLEAN_ONLY -eq 1 ]]; then
    log_info "Cleaning up ports..."
    free_port "$BACKEND_PORT" || true
    free_port "$FRONTEND_PORT" || true
    log_success "Done"
    exit 0
  fi

  # Setup
  setup_environment

  log_info "Freeing ports ${BACKEND_PORT} and ${FRONTEND_PORT}..."
  free_port "$BACKEND_PORT" || exit 1
  free_port "$FRONTEND_PORT" || exit 1

  # Start backend
  log_info "Starting FastAPI backend on ${BACKEND_HOST}:${BACKEND_PORT}..."
  if [[ $KEEP_LOGS -eq 1 ]]; then
    uv run fastapi dev backend/app/main.py &
  else
    uv run fastapi dev backend/app/main.py >> "$BACKEND_LOG" 2>&1 &
  fi
  BACKEND_PID=$!
  log_debug "Backend PID: $BACKEND_PID"

  # Wait for backend health
  if ! wait_for_service "Backend" "http://${BACKEND_HOST}:${BACKEND_PORT}/docs" "$HEALTH_CHECK_TIMEOUT"; then
    log_error "Backend failed to start."
    if [[ $KEEP_LOGS -eq 0 ]] && [[ -s "$BACKEND_LOG" ]]; then
      log_error "Last 30 lines of log:"
      tail -n 30 "$BACKEND_LOG" >&2
    elif [[ $KEEP_LOGS -eq 1 ]]; then
      log_error "Running with --logs: check the terminal output above for details."
    fi
    exit 1
  fi

  # Start frontend
  log_info "Starting Vite frontend on localhost:${FRONTEND_PORT}..."
  if [[ $KEEP_LOGS -eq 1 ]]; then
    pnpm --filter frontend dev &
  else
    pnpm --filter frontend dev >> "$FRONTEND_LOG" 2>&1 &
  fi
  FRONTEND_PID=$!
  log_debug "Frontend PID: $FRONTEND_PID"

  # Wait for frontend health
  if ! wait_for_service "Frontend" "http://localhost:${FRONTEND_PORT}/" "$HEALTH_CHECK_TIMEOUT"; then
    log_error "Frontend failed to start."
    if [[ $KEEP_LOGS -eq 0 ]] && [[ -s "$FRONTEND_LOG" ]]; then
      log_error "Last 30 lines of log:"
      tail -n 30 "$FRONTEND_LOG" >&2
    elif [[ $KEEP_LOGS -eq 1 ]]; then
      log_error "Running with --logs: check the terminal output above for details."
    fi
    exit 1
  fi

  # Mark servers as started — cleanup will now print the shutdown message
  SERVERS_STARTED=1

  # Status
  echo ""
  echo -e "${GREEN}${BOLD}✓ All systems operational!${RESET}"
  echo ""
  echo -e "  ${BOLD}Backend API:${RESET}  http://${BACKEND_HOST}:${BACKEND_PORT}"
  echo -e "  ${BOLD}API Docs:${RESET}     http://${BACKEND_HOST}:${BACKEND_PORT}/docs"
  echo -e "  ${BOLD}Frontend:${RESET}     http://localhost:${FRONTEND_PORT}"
  echo -e "  ${BOLD}Logs:${RESET}         ${LOGS_DIR}"
  echo ""
  echo -e "${YELLOW}Press CTRL+C to stop all servers.${RESET}"
  echo ""

  # Wait for EITHER process to exit. `wait -n` (bash 4.3+) would be the
  # natural tool here, but macOS ships bash 3.2 by default, which doesn't
  # support -n at all. Poll instead so this works everywhere.
  while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
    sleep 1
  done

  # One of the two has exited. Reap it with `wait` to get its real exit
  # status (safe here since we haven't waited on either PID yet), and
  # report which one it was. Guard against `set -e` since `wait` on a
  # nonzero-exit child returns nonzero.
  local wait_status=0
  local crashed=""
  if kill -0 "$BACKEND_PID" 2>/dev/null; then
    crashed="Frontend"
    wait "$FRONTEND_PID" || wait_status=$?
  else
    crashed="Backend"
    wait "$BACKEND_PID" || wait_status=$?
  fi

  if [[ $wait_status -ne 0 ]]; then
    log_error "$crashed exited unexpectedly (status $wait_status). Shutting down..."
  else
    log_info "$crashed exited. Shutting down..."
  fi
  # `cleanup` runs automatically via the EXIT trap once main/script returns.
  exit "$wait_status"
}

main "$@"
