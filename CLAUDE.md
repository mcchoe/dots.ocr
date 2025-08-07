# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

dots.ocr is a multilingual document layout parsing system built on a 1.7B parameter vision-language model. It performs unified layout detection and content recognition for documents, supporting text extraction, formula recognition, table parsing, and multilingual documents. The system can be deployed using either vLLM for production inference or Hugging Face transformers for local development.

## Development Commands

### Environment Setup
```bash
# Create conda environment
conda create -n dots_ocr python=3.12
conda activate dots_ocr

# Install PyTorch (adjust CUDA version as needed)
pip install torch==2.7.0 torchvision==0.22.0 torchaudio==2.7.0 --index-url https://download.pytorch.org/whl/cu128

# Install package in development mode
pip install -e .
```

### Model Download
```bash
# Download model weights (default: Hugging Face)
python3 tools/download_model.py

# Download with ModelScope (alternative)
python3 tools/download_model.py --type modelscope
```

### vLLM Server Deployment
```bash
# Setup and launch vLLM server
./demo/launch_model_vllm.sh

# Or manually:
export hf_model_path=./weights/DotsOCR
export PYTHONPATH=$(dirname "$hf_model_path"):$PYTHONPATH
sed -i '/^from vllm\.entrypoints\.cli\.main import main$/a\from DotsOCR import modeling_dots_ocr_vllm' `which vllm`
CUDA_VISIBLE_DEVICES=0 vllm serve ${hf_model_path} --tensor-parallel-size 1 --gpu-memory-utilization 0.95 --chat-template-content-format string --served-model-name model --trust-remote-code
```

### Document Parsing
```bash
# Parse all layout information (detection + recognition)
python3 dots_ocr/parser.py demo/demo_image1.jpg

# Parse PDF with threading
python3 dots_ocr/parser.py demo/demo_pdf1.pdf --num_thread 64

# Layout detection only
python3 dots_ocr/parser.py demo/demo_image1.jpg --prompt prompt_layout_only_en

# Text extraction only (excluding headers/footers)
python3 dots_ocr/parser.py demo/demo_image1.jpg --prompt prompt_ocr

# Grounding OCR (extract text from specific bounding box)
python3 dots_ocr/parser.py demo/demo_image1.jpg --prompt prompt_grounding_ocr --bbox 163 241 1536 705

# Use Hugging Face transformers instead of vLLM
python3 dots_ocr/parser.py demo/demo_image1.jpg --use_hf true
```

### Demo Applications
```bash
# Interactive Gradio demo
python demo/demo_gradio.py

# Grounding OCR annotation demo
python demo/demo_gradio_annotion.py

# Streamlit demo
python demo/demo_streamlit.py

# vLLM API demo
python3 ./demo/demo_vllm.py --prompt_mode prompt_layout_all_en

# Hugging Face demo
python3 demo/demo_hf.py
```

## Architecture

### Core Components

- **`DotsOCRParser`** (`dots_ocr/parser.py`): Main parsing class that handles both images and PDFs
  - Supports vLLM and Hugging Face inference backends
  - Handles multi-threaded PDF processing
  - Configurable DPI, threading, and model parameters

- **Inference Module** (`dots_ocr/model/inference.py`): 
  - `inference_with_vllm()`: vLLM server communication using OpenAI-compatible API
  - Handles image encoding and prompt formatting for vLLM

- **Utilities** (`dots_ocr/utils/`):
  - `prompts.py`: Defines different parsing prompts for various tasks
  - `layout_utils.py`: Layout detection post-processing and visualization
  - `image_utils.py`: Image processing, resizing, and encoding
  - `doc_utils.py`: PDF handling using PyMuPDF
  - `format_transformer.py`: Converts layout JSON to Markdown
  - `output_cleaner.py`: Post-processing for model outputs

### Parsing Modes

The system supports different parsing modes controlled by prompts:

- **`prompt_layout_all_en`**: Full layout parsing (detection + recognition) with JSON output
- **`prompt_layout_only_en`**: Layout detection only (bounding boxes + categories)  
- **`prompt_ocr`**: Text extraction only (excludes headers/footers)
- **`prompt_grounding_ocr`**: Extract text from specific bounding box coordinates

### Output Formats

- **JSON**: Structured layout data with bounding boxes, categories, and extracted text
- **Markdown**: Formatted text content with proper reading order
- **Markdown (no headers/footers)**: Clean text output for benchmarking
- **Annotated Images**: Original images with detected layout bounding boxes drawn

### Deployment Options

1. **vLLM Server** (Recommended for production):
   - High throughput inference
   - Multi-threading support  
   - OpenAI-compatible API
   - Requires model registration with vLLM

2. **Hugging Face Transformers**:
   - Local development and testing
   - Single-threaded processing
   - Direct model loading
   - Lower throughput

### Model Requirements

- **Model Path**: `./weights/DotsOCR` (directory name without periods)
- **Base Model**: Built on Qwen2.5-VL architecture  
- **Input**: Images up to 11,289,600 pixels, PDF DPI 200 recommended
- **Languages**: Supports 100+ languages including low-resource languages
- **Categories**: 11 layout categories (Caption, Footnote, Formula, List-item, Page-footer, Page-header, Picture, Section-header, Table, Text, Title)

## RunPod Deployment

### FastAPI Production Service

The repository includes production-ready deployment scripts for RunPod:

- **`api_server.py`**: FastAPI service with `/parse` endpoint that returns only markdown output
- **`runpod_setup.sh`**: Automated deployment script for RunPod GPU pods
- **`client.py`**: Local client with timing and health check capabilities

### RunPod-Specific Considerations

1. **Port Configuration**: 
   - vLLM server: Port 8000
   - FastAPI server: Port 8002 (Port 8001 reserved by RunPod's nginx)
   - HTTP Ports setting: `8000,8002`

2. **Dependency Management**:
   - Use system Python (no virtual environment needed with RunPod PyTorch template)
   - Install PyTorch first, then other dependencies, then flash-attn last
   - Use pip for all installations (faster than uv on RunPod)

3. **Model Integration**:
   - Uses original `DotsOCRParser._parse_single_image()` method for full compatibility
   - Proper image preprocessing and markdown conversion pipeline
   - Returns both regular and no-headers-footers markdown versions

### Quick RunPod Deployment

```bash
# Clone repository
git clone https://github.com/mcchoe/dots.ocr.git
cd dots.ocr

# Deploy (takes ~5 minutes)
chmod +x runpod_setup.sh && ./runpod_setup.sh

# Test from local machine
python client.py POD_ID-8002 /path/to/image.jpg
```