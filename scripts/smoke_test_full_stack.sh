#!/bin/bash
# Full-stack smoke test for MyAI production deployment
# Tests: RamaLama (LLM) + Redis (cache) + Web UI (frontend) integration
# Validates: service health, response times, output quality

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
WEBUI_URL="${WEBUI_URL:-http://127.0.0.1:8081}"
RAMALAMA_HOST="${RAMALAMA_HOST:-research-agent}"
RAMALAMA_PORT="${RAMALAMA_PORT:-8080}"
REDIS_HOST="${REDIS_HOST:-myai-redis}"
MAX_REASONABLE_TIME=180  # 3 minutes for CPU-only with 2 iterations
TEST_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="/tmp/myai_smoke_tests_${TEST_TIMESTAMP}"

mkdir -p "$LOG_DIR"

echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}MyAI Full-Stack Smoke Test${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
echo ""
echo "Test configuration:"
echo "  - Web UI: $WEBUI_URL"
echo "  - RamaLama: $RAMALAMA_HOST:$RAMALAMA_PORT"
echo "  - Redis: $REDIS_HOST:6379"
echo "  - Max reasonable time: ${MAX_REASONABLE_TIME}s"
echo "  - Log directory: $LOG_DIR"
echo ""

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Test 1: Check all containers are running
log_info "Test 1: Verifying all required containers are running..."
echo ""

CONTAINERS_OK=true
for container in research-agent myai-redis myai-webui; do
    if podman ps --filter "name=$container" --format "{{.Names}}" | grep -q "^${container}$"; then
        STATUS=$(podman ps --filter "name=$container" --format "{{.Status}}")
        log_success "Container '$container' is running: $STATUS"
    else
        log_error "Container '$container' is NOT running"
        CONTAINERS_OK=false
    fi
done

if [ "$CONTAINERS_OK" = false ]; then
    log_error "Some containers are missing. Please start all required services."
    exit 1
fi
echo ""

# Test 2: Check RamaLama health
log_info "Test 2: Checking RamaLama endpoint..."
RAMALAMA_START=$(date +%s)
RAMALAMA_RESPONSE=$(curl -s -w "\n%{http_code}" http://localhost:${RAMALAMA_PORT}/v1/models 2>&1 || echo "000")
RAMALAMA_END=$(date +%s)
RAMALAMA_TIME=$((RAMALAMA_END - RAMALAMA_START))

HTTP_CODE=$(echo "$RAMALAMA_RESPONSE" | tail -n1)
RAMALAMA_BODY=$(echo "$RAMALAMA_RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "200" ]; then
    MODEL_NAME=$(echo "$RAMALAMA_BODY" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    log_success "RamaLama is healthy (HTTP $HTTP_CODE, ${RAMALAMA_TIME}s)"
    log_info "  Model: $MODEL_NAME"
    echo "$RAMALAMA_BODY" > "$LOG_DIR/ramalama_models.json"
else
    log_error "RamaLama is not responding correctly (HTTP $HTTP_CODE)"
    echo "$RAMALAMA_RESPONSE" > "$LOG_DIR/ramalama_error.log"
    exit 1
fi
echo ""

# Test 3: Check Redis connectivity
log_info "Test 3: Checking Redis connectivity..."
if podman exec myai-redis redis-cli ping | grep -q "PONG"; then
    log_success "Redis is responding to PING"
else
    log_error "Redis is not responding"
    exit 1
fi
echo ""

# Test 4: Check Web UI health endpoint
log_info "Test 4: Checking Web UI health endpoint..."
WEBUI_HEALTH=$(curl -s -w "\n%{http_code}" ${WEBUI_URL}/healthz 2>&1 || echo "000")
WEBUI_HTTP=$(echo "$WEBUI_HEALTH" | tail -n1)

if [ "$WEBUI_HTTP" = "200" ]; then
    log_success "Web UI health check passed (HTTP $WEBUI_HTTP)"
else
    log_error "Web UI health check failed (HTTP $WEBUI_HTTP)"
    exit 1
fi
echo ""

# Test 5: Simple synchronous research question (CPU-only, 2 iterations)
log_info "Test 5: Submitting simple synchronous research question..."
log_info "  Question: 'What is 2+2?'"
log_info "  Iterations: 2 (CPU-only mode)"
log_info "  Expected time: <${MAX_REASONABLE_TIME}s"
echo ""

SYNC_START=$(date +%s)
SYNC_RESPONSE=$(curl -s -w "\n%{http_code}\n%{time_total}" -X POST "${WEBUI_URL}/" \
    -F 'question=What is 2+2?' \
    -F 'max_iterations=2' \
    -F 'use_ramalama=on' \
    -F "ramalama_host=${RAMALAMA_HOST}" \
    -F "ramalama_port=${RAMALAMA_PORT}" \
    2>&1 || echo -e "\n500\n0")

SYNC_END=$(date +%s)
SYNC_ELAPSED=$((SYNC_END - SYNC_START))

# Parse response
SYNC_HTTP=$(echo "$SYNC_RESPONSE" | tail -n2 | head -n1)
SYNC_TIME=$(echo "$SYNC_RESPONSE" | tail -n1)
SYNC_BODY=$(echo "$SYNC_RESPONSE" | head -n-2)

echo "$SYNC_BODY" > "$LOG_DIR/sync_response.html"

# Validate response
if [ "$SYNC_HTTP" != "200" ]; then
    log_error "Synchronous request failed (HTTP $SYNC_HTTP)"
    log_info "Response saved to: $LOG_DIR/sync_response.html"
    exit 1
fi

log_success "Synchronous request completed (HTTP $SYNC_HTTP, ${SYNC_ELAPSED}s)"

# Check if response contains expected structure
if echo "$SYNC_BODY" | grep -q -i "report\|answer\|result"; then
    log_success "Response contains research output"
else
    log_warning "Response may not contain valid research output"
fi

# Validate timing
if [ "$SYNC_ELAPSED" -gt "$MAX_REASONABLE_TIME" ]; then
    log_warning "Request took ${SYNC_ELAPSED}s (exceeds ${MAX_REASONABLE_TIME}s threshold)"
    log_info "This may be expected for CPU-only inference, but check RamaLama logs"
else
    log_success "Request completed in reasonable time (${SYNC_ELAPSED}s < ${MAX_REASONABLE_TIME}s)"
fi

# Check for error indicators
if echo "$SYNC_BODY" | grep -q -i "error\|failed\|timeout\|exception"; then
    log_warning "Response contains error indicators - review output"
    echo "$SYNC_BODY" | grep -i "error\|failed\|timeout" | head -5
fi
echo ""

# Test 6: Background task submission and polling
log_info "Test 6: Submitting background research task..."
log_info "  Question: 'Explain quantum entanglement in one sentence'"
log_info "  Mode: background"
echo ""

BG_START=$(date +%s)
BG_SUBMIT=$(curl -s -w "\n%{http_code}" -X POST "${WEBUI_URL}/" \
    -F 'question=Explain quantum entanglement in one sentence' \
    -F 'max_iterations=2' \
    -F 'background=on' \
    -F 'use_ramalama=on' \
    -F "ramalama_host=${RAMALAMA_HOST}" \
    -F "ramalama_port=${RAMALAMA_PORT}" \
    2>&1)

BG_HTTP=$(echo "$BG_SUBMIT" | tail -n1)
BG_BODY=$(echo "$BG_SUBMIT" | head -n-1)

if [ "$BG_HTTP" != "200" ]; then
    log_error "Background task submission failed (HTTP $BG_HTTP)"
    exit 1
fi

# Extract task ID from response
TASK_ID=$(echo "$BG_BODY" | grep -oP 'Task ID[:\s]+\K[a-f0-9-]+' | head -1)
if [ -z "$TASK_ID" ]; then
    # Try alternative patterns
    TASK_ID=$(echo "$BG_BODY" | grep -oP '/status/\K[a-f0-9-]+' | head -1)
fi

if [ -z "$TASK_ID" ]; then
    log_error "Could not extract task ID from response"
    echo "$BG_BODY" > "$LOG_DIR/bg_submit_response.html"
    exit 1
fi

log_success "Background task submitted successfully"
log_info "  Task ID: $TASK_ID"
echo ""

# Poll task status
log_info "Polling task status (max ${MAX_REASONABLE_TIME}s)..."
POLL_COUNT=0
MAX_POLLS=$((MAX_REASONABLE_TIME / 5))  # Poll every 5 seconds

while [ $POLL_COUNT -lt $MAX_POLLS ]; do
    sleep 5
    POLL_COUNT=$((POLL_COUNT + 1))
    
    STATUS_RESPONSE=$(curl -s -w "\n%{http_code}" "${WEBUI_URL}/status/${TASK_ID}" 2>&1)
    STATUS_HTTP=$(echo "$STATUS_RESPONSE" | tail -n1)
    STATUS_BODY=$(echo "$STATUS_RESPONSE" | head -n-1)
    
    if [ "$STATUS_HTTP" != "200" ]; then
        log_error "Status check failed (HTTP $STATUS_HTTP)"
        break
    fi
    
    # Parse status
    TASK_STATUS=$(echo "$STATUS_BODY" | grep -oP '"status":\s*"\K[^"]+' | head -1)
    
    echo -n "  Poll $POLL_COUNT: status='$TASK_STATUS'"
    
    if [ "$TASK_STATUS" = "completed" ]; then
        echo -e " ${GREEN}✓${NC}"
        BG_END=$(date +%s)
        BG_ELAPSED=$((BG_END - BG_START))
        log_success "Background task completed in ${BG_ELAPSED}s"
        break
    elif [ "$TASK_STATUS" = "failed" ]; then
        echo -e " ${RED}✗${NC}"
        log_error "Background task failed"
        echo "$STATUS_BODY" > "$LOG_DIR/bg_status_failed.json"
        break
    else
        echo " (waiting...)"
    fi
done

if [ "$TASK_STATUS" != "completed" ]; then
    log_warning "Task did not complete within ${MAX_REASONABLE_TIME}s"
    log_info "Final status: $TASK_STATUS"
else
    # Fetch final result
    RESULT_RESPONSE=$(curl -s "${WEBUI_URL}/result/${TASK_ID}")
    echo "$RESULT_RESPONSE" > "$LOG_DIR/bg_result.html"
    
    if echo "$RESULT_RESPONSE" | grep -q -i "report\|answer\|quantum"; then
        log_success "Background task result contains expected content"
    else
        log_warning "Background task result may be incomplete"
    fi
fi
echo ""

# Test 7: Check container resource usage
log_info "Test 7: Checking container resource usage..."
echo ""

podman stats --no-stream research-agent myai-redis myai-webui > "$LOG_DIR/container_stats.txt"
cat "$LOG_DIR/container_stats.txt"
echo ""

# Parse memory usage for RamaLama
RAMALAMA_MEM=$(podman stats --no-stream research-agent --format "{{.MemUsage}}" | cut -d'/' -f1 | sed 's/[^0-9.]//g')
RAMALAMA_MEM_INT=$(echo "$RAMALAMA_MEM" | cut -d'.' -f1)

if [ "$RAMALAMA_MEM_INT" -gt 25000 ]; then
    log_warning "RamaLama using >25GB RAM (${RAMALAMA_MEM}MB) - model loaded fully"
elif [ "$RAMALAMA_MEM_INT" -gt 1000 ]; then
    log_success "RamaLama memory usage appears normal (${RAMALAMA_MEM}MB)"
else
    log_warning "RamaLama memory usage suspiciously low (${RAMALAMA_MEM}MB) - model may not be loaded"
fi
echo ""

# Test 8: Check logs for errors
log_info "Test 8: Checking container logs for errors..."
echo ""

ERROR_COUNT=0
for container in research-agent myai-redis myai-webui; do
    LOG_FILE="$LOG_DIR/${container}_logs.txt"
    podman logs --tail 100 "$container" > "$LOG_FILE" 2>&1 || true
    
    ERROR_LINES=$(grep -i "error\|exception\|failed\|fatal" "$LOG_FILE" | grep -v -i "test\|example\|INFO" | wc -l || echo "0")
    
    if [ "$ERROR_LINES" -gt 0 ]; then
        log_warning "Container '$container' has $ERROR_LINES error-like log lines"
        ERROR_COUNT=$((ERROR_COUNT + ERROR_LINES))
        grep -i "error\|exception\|failed\|fatal" "$LOG_FILE" | grep -v -i "test\|example\|INFO" | head -3
    else
        log_success "Container '$container' logs look clean"
    fi
done

if [ "$ERROR_COUNT" -gt 5 ]; then
    log_warning "Total error count across all containers: $ERROR_COUNT"
fi
echo ""

# Summary
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Smoke Test Summary${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
echo ""
echo "Test Results:"
echo "  ✓ Container health checks: PASSED"
echo "  ✓ RamaLama endpoint: PASSED (${RAMALAMA_TIME}s)"
echo "  ✓ Redis connectivity: PASSED"
echo "  ✓ Web UI health: PASSED"

if [ "$SYNC_HTTP" = "200" ]; then
    echo "  ✓ Synchronous research: PASSED (${SYNC_ELAPSED}s)"
else
    echo "  ✗ Synchronous research: FAILED"
fi

if [ "$TASK_STATUS" = "completed" ]; then
    echo "  ✓ Background task: PASSED (${BG_ELAPSED}s)"
else
    echo "  ⚠ Background task: TIMEOUT or INCOMPLETE"
fi

echo ""
echo "Performance Metrics:"
echo "  - RamaLama response time: ${RAMALAMA_TIME}s"
echo "  - Synchronous request: ${SYNC_ELAPSED}s"
if [ "$TASK_STATUS" = "completed" ]; then
    echo "  - Background task: ${BG_ELAPSED}s"
fi
echo "  - RamaLama memory: ${RAMALAMA_MEM}MB"
echo ""
echo "Logs saved to: $LOG_DIR"
echo ""

# Final verdict
if [ "$SYNC_HTTP" = "200" ] && [ "$SYNC_ELAPSED" -lt "$MAX_REASONABLE_TIME" ]; then
    log_success "All critical tests PASSED - stack is operational"
    exit 0
else
    log_warning "Some tests did not meet thresholds - review logs"
    exit 1
fi
