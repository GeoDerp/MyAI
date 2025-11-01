#!/bin/bash
# Dynamic RamaLama GPU Configuration Script
# Automatically detects GPU VRAM and configures optimal layer offloading
# Supports: AMD (ROCm), NVIDIA (CUDA), Intel, Apple Silicon, and CPU-only

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== RamaLama Dynamic GPU Configuration ===${NC}"

# Configuration
MODEL="${1:-granite4:small-h}"
PORT="${2:-8080}"
NAME="${3:-research-agent}"
NETWORK="${4:-myai-net}"

# Model memory requirements (approximate, in GB)
# granite4:small-h is ~2B params Q4_K_M quantization
# Actual size: ~1.5GB model file, but needs ~2-4GB VRAM for full GPU offload
# For CPU inference with context, needs ~4-8GB RAM depending on batch size
MODEL_MIN_RAM=4
MODEL_FULL_GPU_VRAM=4

# Detect GPU and VRAM
detect_gpu_vram() {
    local vram_bytes=0
    local gpu_type="cpu"
    
    # Try ROCm for AMD GPUs
    if command -v rocm-smi &> /dev/null; then
        vram_bytes=$(rocm-smi --showmeminfo vram --json 2>/dev/null | grep -o '"VRAM Total Memory (B)": "[0-9]*"' | grep -o '[0-9]*' | head -n1)
        if [ -n "$vram_bytes" ] && [ "$vram_bytes" -gt 0 ] 2>/dev/null; then
            # Also get system RAM for context
            total_ram_kb=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}')
            total_ram_gb=$((total_ram_kb / 1024 / 1024))
            echo "amd:$vram_bytes:$total_ram_gb"
            return
        fi
    fi
    
    # Try nvidia-smi for NVIDIA GPUs
    if command -v nvidia-smi &> /dev/null; then
        vram_mb=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -n 1 | tr -d ' ')
        if [ -n "$vram_mb" ] && [ "$vram_mb" -gt 0 ] 2>/dev/null; then
            vram_bytes=$((vram_mb * 1024 * 1024))
            total_ram_kb=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}')
            total_ram_gb=$((total_ram_kb / 1024 / 1024))
            echo "nvidia:$vram_bytes:$total_ram_gb"
            return
        fi
    fi
    
    # Try for Apple Silicon (M1/M2/M3)
    if [ "$(uname -s)" = "Darwin" ]; then
        # Check for Apple Silicon
        if sysctl -n machdep.cpu.brand_string 2>/dev/null | grep -q "Apple"; then
            # Apple Silicon uses unified memory, estimate 75% of total RAM available for GPU
            total_ram_bytes=$(sysctl -n hw.memsize 2>/dev/null || echo "0")
            if [ "$total_ram_bytes" -gt 0 ]; then
                vram_bytes=$((total_ram_bytes * 75 / 100))
                total_ram_gb=$((total_ram_bytes / 1024 / 1024 / 1024))
                echo "apple:$vram_bytes:$total_ram_gb"
                return
            fi
        fi
    fi
    
    # Try lspci for Intel
    if command -v lspci &> /dev/null && lspci 2>/dev/null | grep -qi "intel.*graphics"; then
        # Intel integrated GPUs share system RAM
        # Check available RAM and estimate 25% for GPU
        total_ram_kb=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}')
        if [ -n "$total_ram_kb" ] && [ "$total_ram_kb" -gt 0 ]; then
            vram_bytes=$((total_ram_kb * 1024 * 25 / 100))
            total_ram_gb=$((total_ram_kb / 1024 / 1024))
            echo "intel:$vram_bytes:$total_ram_gb"
            return
        fi
    fi
    
    # Fallback: CPU-only, but check RAM availability
    total_ram_kb=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}')
    if [ -n "$total_ram_kb" ] && [ "$total_ram_kb" -gt 0 ]; then
        total_ram_gb=$((total_ram_kb / 1024 / 1024))
    else
        total_ram_gb=0
    fi
    echo "cpu:0:${total_ram_gb}"
}

# Calculate optimal GPU layers based on VRAM and RAM
calculate_gpu_layers() {
    local vram_bytes=$1
    local vram_gb=$((vram_bytes / 1073741824))
    local total_ram_gb=${2:-0}
    
    echo -e "${BLUE}Hardware Detection:${NC}" >&2
    echo "  VRAM: ${vram_gb} GB" >&2
    if [ "$total_ram_gb" -gt 0 ]; then
        echo "  System RAM: ${total_ram_gb} GB" >&2
    fi
    echo "" >&2
    
    # For granite4:small-h (2B params, Q4_K_M):
    # - Model file: ~1.5GB
    # - Full GPU offload (41 layers): ~3-4GB VRAM needed
    # - Partial offload scales roughly: ~100MB per layer
    # - CPU inference: ~4-8GB RAM depending on context size
    
    if [ "$vram_gb" -ge 4 ]; then
        # Sufficient VRAM for full offload
        echo -e "${GREEN}✅ GPU has sufficient VRAM for full offload${NC}" >&2
        echo "41"
    elif [ "$vram_gb" -ge 3 ]; then
        # Almost enough, offload most layers
        echo -e "${GREEN}Good GPU - Offload 30 layers${NC}" >&2
        echo "30"
    elif [ "$vram_gb" -ge 2 ]; then
        # Medium VRAM, split workload
        echo -e "${YELLOW}Medium GPU - Offload 20 layers${NC}" >&2
        echo "20"
    elif [ "$vram_gb" -ge 1 ]; then
        # Small VRAM, minimal offload
        echo -e "${YELLOW}Small GPU - Offload 10 layers${NC}" >&2
        echo "10"
    else
        # CPU-only mode
        if [ "$total_ram_gb" -ge "$MODEL_MIN_RAM" ]; then
            echo -e "${YELLOW}Insufficient VRAM - Using CPU-only mode${NC}" >&2
            echo -e "${GREEN}✅ System has ${total_ram_gb}GB RAM (model needs ${MODEL_MIN_RAM}GB minimum)${NC}" >&2
        else
            echo -e "${RED}⚠️  Warning: System has only ${total_ram_gb}GB RAM (model needs ${MODEL_MIN_RAM}GB minimum)${NC}" >&2
            echo -e "${RED}   Performance may be degraded${NC}" >&2
        fi
        echo "0"
    fi
}

# Detect GPU
gpu_info=$(detect_gpu_vram)
gpu_type=$(echo "$gpu_info" | cut -d: -f1)
vram_bytes=$(echo "$gpu_info" | cut -d: -f2)
total_ram_gb=$(echo "$gpu_info" | cut -d: -f3)

echo -e "${BLUE}GPU Type: $gpu_type${NC}"
echo -e "${BLUE}VRAM Bytes: $vram_bytes${NC}"
if [ -n "$total_ram_gb" ] && [ "$total_ram_gb" -gt 0 ]; then
    echo -e "${BLUE}Total RAM: ${total_ram_gb}GB${NC}"
fi
echo ""

# Calculate optimal layers
gpu_layers=$(calculate_gpu_layers "$vram_bytes" "$total_ram_gb")

# Determine image based on GPU type
case "$gpu_type" in
    amd)
        image="quay.io/ramalama/rocm:latest"
        echo -e "${GREEN}Using AMD ROCm runtime${NC}"
        ;;
    nvidia)
        image="quay.io/ramalama/cuda:latest"
        echo -e "${GREEN}Using NVIDIA CUDA runtime${NC}"
        ;;
    intel)
        image="quay.io/ramalama/intel-gpu:latest"
        echo -e "${GREEN}Using Intel GPU runtime${NC}"
        ;;
    apple)
        image="quay.io/ramalama/ramalama:latest"
        echo -e "${GREEN}Using Apple Silicon runtime${NC}"
        ;;
    *)
        image="quay.io/ramalama/ramalama:latest"
        echo -e "${YELLOW}Using CPU-only runtime${NC}"
        ;;
esac

echo -e "${GREEN}Selected image: $image${NC}"
echo -e "${GREEN}GPU layers: $gpu_layers${NC}"
echo ""

# Stop existing container if running
if podman ps -a --format "{{.Names}}" | grep -q "^${NAME}$"; then
    echo -e "${YELLOW}Stopping existing container: $NAME${NC}"
    podman stop "$NAME" 2>/dev/null || true
    podman rm "$NAME" 2>/dev/null || true
fi

# Build ramalama command
if [ "$gpu_layers" -eq 0 ]; then
    # CPU-only mode
    echo -e "${YELLOW}Starting RamaLama in CPU-only mode...${NC}"
    ramalama_cmd="ramalama serve --port $PORT --name $NAME"
    
    # Add network if specified and not empty
    if [ -n "$NETWORK" ] && [ "$NETWORK" != "none" ]; then
        ramalama_cmd="$ramalama_cmd --network=$NETWORK"
    fi
    
    # Use standard image for CPU-only (unless Apple Silicon)
    if [ "$gpu_type" != "apple" ]; then
        ramalama_cmd="$ramalama_cmd --image quay.io/ramalama/ramalama:latest"
    fi
    
    ramalama_cmd="$ramalama_cmd --ngl 0 $MODEL -d"
else
    # GPU mode with specific layer count
    echo -e "${GREEN}Starting RamaLama with GPU acceleration ($gpu_layers layers)...${NC}"
    ramalama_cmd="ramalama serve --port $PORT --name $NAME"
    
    # Add network if specified and not empty
    if [ -n "$NETWORK" ] && [ "$NETWORK" != "none" ]; then
        ramalama_cmd="$ramalama_cmd --network=$NETWORK"
    fi
    
    ramalama_cmd="$ramalama_cmd --image $image --ngl $gpu_layers $MODEL -d"
fi

echo -e "${BLUE}Command: $ramalama_cmd${NC}"
echo ""

# Execute
eval "$ramalama_cmd"

# Wait and verify
sleep 5

if ramalama ps | grep -q "$NAME"; then
    echo -e "${GREEN}✅ RamaLama started successfully!${NC}"
    echo ""
    echo "Container: $NAME"
    echo "Port: $PORT"
    echo "Model: $MODEL"
    echo "GPU Layers: $gpu_layers"
    echo "Image: $image"
    echo ""
    echo "Test with:"
    echo "  curl -s http://localhost:$PORT/v1/models | jq '.data[].id'"
    exit 0
else
    echo -e "${RED}❌ Failed to start RamaLama${NC}"
    echo "Check logs with: podman logs $NAME"
    exit 1
fi
