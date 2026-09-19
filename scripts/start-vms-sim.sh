#!/usr/bin/env bash
# Start the Linux VMS simulator only: MediaMTX plus its selected FFmpeg publishers.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONFIG_NAME="mediamtx-vms.yml"

usage() {
  printf 'Usage: %s [--config <repo-relative MediaMTX profile>]\n' "$(basename "$0")"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      if [[ $# -lt 2 ]]; then
        printf '[vms-sim] --config requires a profile path\n' >&2
        usage >&2
        exit 2
      fi
      CONFIG_NAME="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      printf '[vms-sim] unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "${CONFIG_NAME}" = /* ]]; then
  CONFIG_PATH="${CONFIG_NAME}"
else
  CONFIG_PATH="${REPO_ROOT}/${CONFIG_NAME}"
fi

for command in ffmpeg mediamtx; do
  if ! command -v "${command}" >/dev/null 2>&1; then
    printf "[vms-sim] required command not found: %s\n" "${command}" >&2
    exit 1
  fi
done

if [[ ! -r "${CONFIG_PATH}" ]]; then
  printf "[vms-sim] MediaMTX profile not found: %s\n" "${CONFIG_PATH}" >&2
  exit 1
fi

cd "${REPO_ROOT}"
printf "[vms-sim] starting MediaMTX with %s\n" "${CONFIG_PATH}"
exec mediamtx "${CONFIG_PATH}"
