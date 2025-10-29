#!/usr/bin/env bash
set -euo pipefail

# Simple helper to create a podman network, optionally start RamaLama,
# build the webui image and run it on the network.
# Usage:
#   ./scripts/run_demo.sh            # build + run web UI only (assumes research-agent already running)
#   ./scripts/run_demo.sh --start-ramalama   # also attempt to start a RamaLama container (may pull large images)
#
# Notes:
# - Starting RamaLama with models may require large downloads and GPU resources.
# - Prefer starting RamaLama manually when you control which model and image are used.

ROOT_DIR="$(dirname "$(dirname "$0")")"
NETWORK=myai-net
WEBUI_IMAGE=myai-webui
WEBUI_CONTAINER=myai-webui
RAMALAMA_NAME=research-agent
RAMALAMA_PORT=8080
RAMALAMA_IMAGE=quay.io/ramalama/intel-gpu:latest
START_RAMALAMA=false

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --start-ramalama) START_RAMALAMA=true; shift ;;
    --help|-h) echo "Usage: $0 [--start-ramalama]"; exit 0 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

echo "[run_demo] Ensuring network '$NETWORK' exists..."
podman network create "$NETWORK" || true

if [ "$START_RAMALAMA" = true ]; then
  echo "[run_demo] Starting RamaLama container (this may take time and download large images)..."
  podman rm -f "$RAMALAMA_NAME" || true || true
  podman run -d --name "$RAMALAMA_NAME" --network "$NETWORK" -p ${RAMALAMA_PORT}:8080 \
    "$RAMALAMA_IMAGE" ramalama serve --ngl 0 --image "$RAMALAMA_IMAGE" --port 8080 --name "$RAMALAMA_NAME" granite4:small-h
  echo "[run_demo] RamaLama started as container '$RAMALAMA_NAME' (if the image needs pulling this may take a while)."
else
  echo "[run_demo] Skipping RamaLama startup. If you need RamaLama, run it separately and attach to network '$NETWORK'."
fi

# Build the web UI image
echo "[run_demo] Building web UI image '$WEBUI_IMAGE'..."
podman build -f Dockerfile.webui -t "$WEBUI_IMAGE" .

# Run the web UI container
echo "[run_demo] Stopping any existing container named '$WEBUI_CONTAINER'..."
podman rm -f "$WEBUI_CONTAINER" || true

echo "[run_demo] Running web UI container on network '$NETWORK' (host port 8081 -> container 8081)..."
podman run -d --name "$WEBUI_CONTAINER" --network "$NETWORK" -p 8081:8081 "$WEBUI_IMAGE"

cat <<EOF

Done.
- Web UI: http://localhost:8081
- If you started RamaLama here, it should be reachable at: http://$RAMALAMA_NAME:$RAMALAMA_PORT/v1 (inside containers)

Notes:
- To inspect logs for the web UI container: podman logs -f $WEBUI_CONTAINER
- To inspect debug traces inside the web UI container: podman exec -it $WEBUI_CONTAINER cat /tmp/myai_debug.log
- To stop everything started by this script:
    podman rm -f $WEBUI_CONTAINER || true
    podman rm -f $RAMALAMA_NAME || true

EOF
