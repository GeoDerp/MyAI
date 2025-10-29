#!/usr/bin/env bash
set -euo pipefail

CONTAINER=${1:-myai-webui}
LINES=${2:-250}

if ! podman ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  echo "Container '${CONTAINER}' is not running. Current containers:" >&2
  podman ps --format '{{.Names}}' || true
  exit 2
fi

echo "--- Last ${LINES} lines of debug file from ${CONTAINER} ---"
# Prefer MYAI_DEBUG_FILE if set inside the container
podman exec -it "$CONTAINER" sh -c "FILE=\"\${MYAI_DEBUG_FILE:-/tmp/myai_debug.log}\"; echo 'Using debug file: '$FILE; tail -n ${LINES} \"$FILE\" || true"

echo "--- End of debug log ---"
