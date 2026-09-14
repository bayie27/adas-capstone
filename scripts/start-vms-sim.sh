#!/usr/bin/env bash
# Start the Linux VMS simulator only: MediaMTX plus its five FFmpeg publishers.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONFIG_PATH="${REPO_ROOT}/mediamtx-vms.yml"

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
