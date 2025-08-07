#!/bin/bash

# RunPod deployment script for dots.ocr with uv
# This script sets up the entire environment and starts both vLLM and FastAPI servers

set -e  # Exit on any error

echo "🚀 Starting RunPod dots.ocr deployment..."

# Update system packages
echo "📦 Updating system packages..."
apt-get update && apt-get install -y curl git wget

# Install uv package manager
echo "📦 Installing uv package manager..."
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add uv to PATH for current session (uv installs to ~/.local/bin)
export PATH="$HOME/.local/bin:$PATH"

# Verify uv installation
echo "✅ uv version: $(uv --version)"

# Clone or update repository (if not already present)
if [ ! -d "/workspace/dots.ocr" ]; then
    echo "📥 Cloning dots.ocr repository..."
    cd /workspace
    git clone https://github.com/rednote-hilab/dots.ocr.git
    cd dots.ocr
else
    echo "📥 Repository already exists, updating..."
    cd /workspace/dots.ocr
    git pull
fi

# Create virtual environment with uv
echo "🔧 Creating virtual environment with uv..."
uv venv --python 3.12

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Install PyTorch with pip (CUDA support)
echo "📦 Installing PyTorch with uv pip..."
uv pip install torch==2.7.0 torchvision==0.22.0 torchaudio==2.7.0 --index-url https://download.pytorch.org/whl/cu128

# Install all other dependencies with uv pip (after PyTorch is available)
echo "📦 Installing other dependencies with uv pip..."
uv pip install \
    transformers==4.51.3 \
    accelerate \
    flash-attn==2.8.0.post2 \
    vllm==0.9.1 \
    PyMuPDF \
    qwen_vl_utils \
    fastapi \
    "uvicorn[standard]" \
    python-multipart \
    huggingface_hub \
    modelscope \
    openai \
    httpx \
    tqdm \
    numpy \
    pillow \
    requests \
    gradio \
    gradio_image_annotation

# Download model weights
echo "⬇️ Downloading model weights..."
python3 tools/download_model.py --type modelscope

# Verify model directory structure
echo "🔍 Verifying model directory..."
if [ ! -d "./weights/DotsOCR" ]; then
    echo "❌ Error: Model directory ./weights/DotsOCR not found!"
    exit 1
fi

# Set environment variables for vLLM
export hf_model_path=./weights/DotsOCR
export PYTHONPATH=$(dirname "$hf_model_path"):$PYTHONPATH

# Register DotsOCR model with vLLM (critical step)
echo "🔧 Registering DotsOCR model with vLLM..."
VLLM_PATH=$(which vllm)
if [ -z "$VLLM_PATH" ]; then
    echo "❌ Error: vLLM not found in PATH!"
    exit 1
fi

# Backup original vllm file
cp "$VLLM_PATH" "${VLLM_PATH}.backup"

# Add DotsOCR import to vLLM
sed -i '/^from vllm\.entrypoints\.cli\.main import main$/a\
from DotsOCR import modeling_dots_ocr_vllm' "$VLLM_PATH"

echo "✅ vLLM registration complete"

# Create log directories
mkdir -p /workspace/logs

# Function to start vLLM server
start_vllm_server() {
    echo "🚀 Starting vLLM server on port 8000..."
    
    # Start vLLM server in background
    CUDA_VISIBLE_DEVICES=0 vllm serve ${hf_model_path} \
        --tensor-parallel-size 1 \
        --gpu-memory-utilization 0.95 \
        --chat-template-content-format string \
        --served-model-name model \
        --trust-remote-code \
        --host 0.0.0.0 \
        --port 8000 \
        > /workspace/logs/vllm.log 2>&1 &
    
    VLLM_PID=$!
    echo "vLLM server PID: $VLLM_PID"
    
    # Wait for vLLM server to be ready
    echo "⏳ Waiting for vLLM server to be ready..."
    for i in {1..60}; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo "✅ vLLM server is ready!"
            break
        fi
        echo "Waiting for vLLM server... ($i/60)"
        sleep 5
    done
    
    if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "❌ vLLM server failed to start. Check logs:"
        tail -50 /workspace/logs/vllm.log
        exit 1
    fi
}

# Function to start FastAPI server
start_fastapi_server() {
    echo "🚀 Starting FastAPI server on port 8001..."
    
    # Start FastAPI server in background
    python3 api_server.py --host 0.0.0.0 --port 8001 \
        > /workspace/logs/fastapi.log 2>&1 &
    
    FASTAPI_PID=$!
    echo "FastAPI server PID: $FASTAPI_PID"
    
    # Wait for FastAPI server to be ready
    echo "⏳ Waiting for FastAPI server to be ready..."
    for i in {1..30}; do
        if curl -s http://localhost:8001/health > /dev/null 2>&1; then
            echo "✅ FastAPI server is ready!"
            break
        fi
        echo "Waiting for FastAPI server... ($i/30)"
        sleep 2
    done
    
    if ! curl -s http://localhost:8001/health > /dev/null 2>&1; then
        echo "❌ FastAPI server failed to start. Check logs:"
        tail -50 /workspace/logs/fastapi.log
        exit 1
    fi
}

# Function to cleanup on exit
cleanup() {
    echo "🧹 Cleaning up..."
    if [ ! -z "$VLLM_PID" ]; then
        kill $VLLM_PID 2>/dev/null || true
    fi
    if [ ! -z "$FASTAPI_PID" ]; then
        kill $FASTAPI_PID 2>/dev/null || true
    fi
}

# Set trap for cleanup
trap cleanup EXIT INT TERM

# Start both servers
start_vllm_server
start_fastapi_server

# Print access information
echo ""
echo "🎉 dots.ocr deployment complete!"
echo ""
echo "📊 Service Status:"
echo "  vLLM server:    http://localhost:8000 (PID: $VLLM_PID)"
echo "  FastAPI server: http://localhost:8001 (PID: $FASTAPI_PID)"
echo ""
echo "🌐 RunPod Access URLs (replace POD_ID with your actual pod ID):"
echo "  FastAPI Docs:   https://POD_ID-8001.proxy.runpod.net/docs"
echo "  Parse Endpoint: https://POD_ID-8001.proxy.runpod.net/parse"
echo "  Health Check:   https://POD_ID-8001.proxy.runpod.net/health"
echo ""
echo "📝 Log Files:"
echo "  vLLM logs:      tail -f /workspace/logs/vllm.log"
echo "  FastAPI logs:   tail -f /workspace/logs/fastapi.log"
echo ""

# Keep the script running to maintain the servers
echo "🔄 Servers are running. Press Ctrl+C to stop."

# Monitor both processes
while true; do
    # Check if vLLM is still running
    if ! kill -0 $VLLM_PID 2>/dev/null; then
        echo "❌ vLLM server died! Check logs:"
        tail -20 /workspace/logs/vllm.log
        exit 1
    fi
    
    # Check if FastAPI is still running
    if ! kill -0 $FASTAPI_PID 2>/dev/null; then
        echo "❌ FastAPI server died! Check logs:"
        tail -20 /workspace/logs/fastapi.log
        exit 1
    fi
    
    sleep 10
done