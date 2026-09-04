#!/usr/bin/env bash
#
# Publishes one positive UAT clip, then returns the RTSP path to the
# non-alerting airbase feed.
#
# UAT positive clips must trigger once per profile activation. Publishing a
# positive clip with `-stream_loop -1` creates another accident after the
# operator resolves the first one, while letting FFmpeg exit leaves the
# simulated camera disconnected. This helper performs the positive pass once,
# makes a brief publisher handover, and then retries only the silent feed for
# the rest of the MediaMTX run.
#
# MediaMTX owns this process through runOnInit. Stopping MediaMTX tree-stops
# the helper and its current FFmpeg child.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

POSITIVE_CLIP=""
SILENT_CLIP=""
RTSP_URL=""
VALIDATE_ONLY=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Options:
  --positive-clip, -PositiveClip <path>   Path to positive clip
  --silent-clip, -SilentClip <path>       Path to silent clip
  --rtsp-url, -RtspUrl <url>              RTSP destination URL (rtsp://...)
  --validate-only, -ValidateOnly          Validate parameters and exit
  --help, -h                              Show this help message
EOF
}

# Parse options (supports --flag, -Flag, and positional where appropriate)
while [[ $# -gt 0 ]]; do
  case "$1" in
    --positive-clip|-PositiveClip|-p)
      POSITIVE_CLIP="$2"
      shift 2
      ;;
    --silent-clip|-SilentClip|-s)
      SILENT_CLIP="$2"
      shift 2
      ;;
    --rtsp-url|-RtspUrl|-r)
      RTSP_URL="$2"
      shift 2
      ;;
    --validate-only|-ValidateOnly|-v)
      VALIDATE_ONLY=1
      shift 1
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Error: Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "${POSITIVE_CLIP}" || -z "${SILENT_CLIP}" || -z "${RTSP_URL}" ]]; then
  echo "Error: --positive-clip, --silent-clip, and --rtsp-url are all required." >&2
  usage >&2
  exit 1
fi

if [[ "${RTSP_URL}" != rtsp://* ]]; then
  echo "Error: RtspUrl must start with rtsp://" >&2
  exit 1
fi

resolve_clip() {
  local clip_path="$1"
  if [[ "${clip_path}" = /* ]]; then
    echo "${clip_path}"
  else
    echo "${REPO_ROOT}/${clip_path#./}"
  fi
}

RESOLVED_POSITIVE="$(resolve_clip "${POSITIVE_CLIP}")"
RESOLVED_SILENT="$(resolve_clip "${SILENT_CLIP}")"

if [[ ! -f "${RESOLVED_POSITIVE}" ]]; then
  echo "Error: Positive UAT clip is not a file: ${RESOLVED_POSITIVE}" >&2
  exit 1
fi

if [[ ! -f "${RESOLVED_SILENT}" ]]; then
  echo "Error: Silent UAT clip is not a file: ${RESOLVED_SILENT}" >&2
  exit 1
fi

if ! command -v ffmpeg &>/dev/null; then
  echo "Error: ffmpeg command not found in PATH." >&2
  exit 1
fi

if [[ "${VALIDATE_ONLY}" -eq 1 ]]; then
  echo "[uat-publisher] ffmpeg: $(command -v ffmpeg)"
  echo "[uat-publisher] positive: ${RESOLVED_POSITIVE}"
  echo "[uat-publisher] silent: ${RESOLVED_SILENT}"
  echo "[uat-publisher] destination: ${RTSP_URL}"
  exit 0
fi

# Cleanup child processes on exit/interrupt
CHILD_PID=""
cleanup() {
  local exit_code="${1:-0}"
  trap - EXIT INT TERM
  if [[ -n "${CHILD_PID}" ]] && kill -0 "${CHILD_PID}" 2>/dev/null; then
    kill -TERM "${CHILD_PID}" 2>/dev/null || true
    wait "${CHILD_PID}" 2>/dev/null || true
  fi
  exit "${exit_code}"
}

trap 'cleanup 0' EXIT
trap 'cleanup 130' INT
trap 'cleanup 143' TERM

echo "[uat-publisher] Publishing positive clip once: ${RESOLVED_POSITIVE}"
ffmpeg \
  -hide_banner -loglevel warning \
  -re -i "${RESOLVED_POSITIVE}" \
  -c copy -rtsp_transport tcp -f rtsp "${RTSP_URL}" &
CHILD_PID=$!
if ! wait "${CHILD_PID}"; then
  exit_code=$?
  if [[ ${exit_code} -eq 130 || ${exit_code} -eq 143 ]]; then
    exit 0
  fi
  echo "Error: Positive UAT publisher exited with code ${exit_code}" >&2
  exit "${exit_code}"
fi
CHILD_PID=""

echo "[uat-publisher] Positive clip completed; switching permanently to silent feed."
while true; do
  ffmpeg \
    -hide_banner -loglevel warning \
    -re -stream_loop -1 -i "${RESOLVED_SILENT}" \
    -c copy -rtsp_transport tcp -f rtsp "${RTSP_URL}" &
  CHILD_PID=$!
  if ! wait "${CHILD_PID}"; then
    silent_code=$?
    if [[ ${silent_code} -eq 130 || ${silent_code} -eq 143 ]]; then
      exit 0
    fi
    echo "[uat-publisher] Warning: Silent UAT publisher exited with code ${silent_code}; retrying silent feed in 1s." >&2
  fi
  CHILD_PID=""
  sleep 1 &
  CHILD_PID=$!
  wait "${CHILD_PID}" || exit 0
  CHILD_PID=""
done
