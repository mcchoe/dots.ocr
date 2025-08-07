# RunPod Deployment Guide for dots.ocr

This guide explains how to deploy dots.ocr on RunPod using uv for dependency management and return only markdown output.

## Files Created

- `pyproject.toml` - Modern Python project configuration with uv
- `api_server.py` - FastAPI service with `/parse` endpoint 
- `runpod_setup.sh` - Automated RunPod deployment script
- `client.py` - Local client for testing the deployed service

## RunPod Deployment

1. **Create RunPod GPU Pod**
   - Choose a pod with CUDA-compatible GPU (RTX 4090, A100, etc.)
   - Use PyTorch image or Ubuntu with CUDA support
   - Minimum 24GB VRAM recommended for the 1.7B model

2. **Upload and Run Setup Script**
   ```bash
   # Upload files to RunPod or clone your repo
   cd /workspace
   git clone https://github.com/mcchoe/dots.ocr.git
   cd dots.ocr
   
   # Make setup script executable and run
   chmod +x runpod_setup.sh
   ./runpod_setup.sh
   ```

3. **The script will:**
   - Install uv package manager
   - Create Python 3.12 virtual environment with uv
   - Install PyTorch 2.7.0 with CUDA 12.8 support
   - Install dots.ocr and dependencies
   - Download DotsOCR model weights (1.7B parameters)
   - Register model with vLLM 0.9.1
   - Start vLLM server on port 8000
   - Start FastAPI server on port 8001
   - Monitor both services

## API Endpoints

### FastAPI Service (Port 8001)

- **Health Check:** `GET /health`
- **Parse Image:** `POST /parse`
  - Upload image file (multipart/form-data)
  - Optional: `prompt_mode` parameter
  - Returns: JSON with `markdown` and `markdown_nohf` fields
- **Parse PDF:** `POST /parse_pdf` 
  - Upload PDF file (multipart/form-data)
  - Optional: `prompt_mode`, `dpi` parameters
  - Returns: JSON with page-by-page markdown results

### Access URLs (replace POD_ID with your actual pod ID)

- FastAPI Docs: `https://POD_ID-8001.proxy.runpod.net/docs`
- Parse Endpoint: `https://POD_ID-8001.proxy.runpod.net/parse`
- Health Check: `https://POD_ID-8001.proxy.runpod.net/health`

## Local Testing

Use the provided client script to test your deployment:

```bash
# Install requests if not already installed
pip install requests

# Health check
python client.py POD_ID --health-check-only

# Parse an image
python client.py POD_ID demo/demo_image1.jpg

# Parse a PDF with custom settings
python client.py POD_ID document.pdf --prompt-mode prompt_ocr --dpi 300 --output-dir results/

# Different prompt modes
python client.py POD_ID image.jpg --prompt-mode prompt_layout_only_en  # Layout detection only
python client.py POD_ID image.jpg --prompt-mode prompt_ocr             # Text extraction only
```

## Output Files

The client saves two markdown files for each processed document:
- `filename.md` - Complete markdown with headers/footers
- `filename_nohf.md` - Clean markdown without headers/footers

For PDFs:
- Individual page files: `filename_page1.md`, `filename_page1_nohf.md`, etc.
- Combined files: `filename_combined.md`, `filename_combined_nohf.md`

## Troubleshooting

### Check Service Status
```bash
# View logs
tail -f /workspace/logs/vllm.log
tail -f /workspace/logs/fastapi.log

# Check if services are running
curl http://localhost:8000/health  # vLLM server
curl http://localhost:8001/health  # FastAPI server
```

### Common Issues

1. **vLLM Registration Failed**
   - Ensure model directory is named `DotsOCR` (no periods)
   - Check that `sed` command modified vLLM executable correctly

2. **CUDA Out of Memory**
   - Reduce `--gpu-memory-utilization` in runpod_setup.sh
   - Use smaller batch sizes or lower DPI for PDFs

3. **Request Timeouts**
   - RunPod has 100-second HTTP timeout limit
   - Large documents may need preprocessing or chunking

4. **Model Download Failed**
   - Check internet connectivity in RunPod
   - Try `--type modelscope` if HuggingFace is slow

## Dependencies

Key versions used:
- Python 3.12
- PyTorch 2.7.0 (CUDA 12.8)
- vLLM 0.9.1 
- FastAPI + Uvicorn
- Transformers 4.51.3
- Flash Attention 2.8.0.post2

The setup uses uv for dependency management but follows the official installation guide structure.