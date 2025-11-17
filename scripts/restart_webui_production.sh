#!/bin/bash
# Restart Web UI with production-appropriate timeouts
# This script stops and recreates the myai-webui container with proper environment settings

set -e

echo "Restarting myai-webui with production configuration..."

# Stop and remove existing container
if podman ps -a --filter name=myai-webui --format "{{.Names}}" | grep -q "^myai-webui$"; then
    echo "Stopping existing myai-webui container..."
    podman rm -f myai-webui
fi

# Check if the image exists
if ! podman images --format "{{.Repository}}:{{.Tag}}" | grep -q "^myai-webui:latest$"; then
    echo "Building myai-webui image..."
    podman build -f Dockerfile.webui -t myai-webui /var/home/core/MyAi
fi

# Start with production settings
echo "Starting myai-webui with production timeouts..."
podman run -d \
    --name myai-webui \
    --network myai-net \
    -p 8081:8081 \
    -e PORT=8081 \
    -e HOST=0.0.0.0 \
    -e CPU_ONLY_MODE=1 \
    -e GPU_LAYERS=0 \
    -e MYAI_MAX_RUNTIME_SECONDS=600 \
    -e LLM_TIMEOUT=120 \
    -e LLM_RETRIES=3 \
    -e REDIS_URL=redis://myai-redis:6379/0 \
    -e RAMALAMA_HOST=research-agent \
    -e RAMALAMA_PORT=8080 \
    myai-webui webui

echo "Waiting for Web UI to start..."
sleep 5

# Health check
if curl -s http://localhost:8081/healthz | grep -q "ok\|healthy"; then
    echo "✓ Web UI is healthy at http://localhost:8081"
else
    echo "⚠ Web UI may not be responding correctly"
fi

echo ""
echo "Configuration:"
echo "  - Max runtime per question: 600s (10 minutes)"
echo "  - LLM timeout per call: 120s (2 minutes)"
echo "  - LLM retries: 3"
echo "  - Redis: redis://myai-redis:6379/0"
echo ""
echo "View logs: podman logs -f myai-webui"
