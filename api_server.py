#!/usr/bin/env python3
"""
FastAPI server for dots.ocr document parsing.
Returns only markdown output (regular and no-header-footer versions).
"""

import os
import io
import tempfile
import traceback
from typing import Dict, Any
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from PIL import Image

from dots_ocr.parser import DotsOCRParser
from dots_ocr.utils.format_transformer import layoutjson2md


app = FastAPI(
    title="dots.ocr API Server",
    description="Document parsing service returning markdown content",
    version="1.0.0"
)

# Add CORS middleware for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize parser (will use vLLM backend by default)
parser = None

@app.on_event("startup")
async def startup_event():
    """Initialize the DotsOCR parser on startup."""
    global parser
    try:
        # Use vLLM backend (default), not HF
        parser = DotsOCRParser(
            ip='localhost',
            port=8000,
            model_name='model',
            temperature=0.1,
            top_p=1.0,
            max_completion_tokens=16384,
            use_hf=False,  # Use vLLM backend
            output_dir="/tmp/dots_ocr_output"
        )
        print("DotsOCR parser initialized successfully")
    except Exception as e:
        print(f"Failed to initialize DotsOCR parser: {e}")
        traceback.print_exc()
        raise


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "dots.ocr API Server", "status": "running"}


@app.get("/health")
async def health_check():
    """Detailed health check."""
    global parser
    return {
        "status": "healthy" if parser is not None else "unhealthy",
        "parser_initialized": parser is not None,
        "vllm_backend": not parser.use_hf if parser else None
    }


@app.post("/parse")
async def parse_document(
    file: UploadFile = File(...),
    prompt_mode: str = Form(default="prompt_layout_all_en")
) -> Dict[str, Any]:
    """
    Parse an uploaded image and return markdown content.
    
    Args:
        file: Uploaded image file
        prompt_mode: Parsing mode (default: prompt_layout_all_en)
        
    Returns:
        dict: Contains markdown and markdown_nohf fields
    """
    global parser
    
    if parser is None:
        raise HTTPException(status_code=500, detail="Parser not initialized")
    
    # Validate file type
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    try:
        # Read uploaded file
        file_content = await file.read()
        
        # Convert to PIL Image
        image = Image.open(io.BytesIO(file_content))
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Create temporary file for processing
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            image.save(temp_file.name, format='PNG')
            temp_path = temp_file.name
        
        try:
            # Parse the image using existing parser logic
            response = parser._inference_with_vllm(image, 
                parser.get_prompt(prompt_mode, image=image))
            
            # Post-process the response to get layout JSON
            from dots_ocr.utils.layout_utils import post_process_output
            layout_data = post_process_output(response, prompt_mode, image, image)
            
            # Convert to markdown formats
            markdown_regular = ""
            markdown_nohf = ""
            
            if layout_data and 'layout' in layout_data:
                cells = layout_data['layout']
                
                # Regular markdown (with headers/footers)
                markdown_regular = layoutjson2md(
                    image=image, 
                    cells=cells, 
                    text_key='text',
                    no_page_hf=False
                )
                
                # No headers/footers markdown  
                markdown_nohf = layoutjson2md(
                    image=image,
                    cells=cells, 
                    text_key='text',
                    no_page_hf=True
                )
            
            return {
                "status": "success",
                "filename": file.filename,
                "prompt_mode": prompt_mode,
                "markdown": markdown_regular,
                "markdown_nohf": markdown_nohf
            }
            
        finally:
            # Clean up temporary file
            os.unlink(temp_path)
            
    except Exception as e:
        print(f"Error processing file {file.filename}: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"Error processing image: {str(e)}"
        )


@app.post("/parse_pdf")
async def parse_pdf(
    file: UploadFile = File(...),
    prompt_mode: str = Form(default="prompt_layout_all_en"),
    dpi: int = Form(default=200)
) -> Dict[str, Any]:
    """
    Parse an uploaded PDF and return markdown content for all pages.
    
    Args:
        file: Uploaded PDF file
        prompt_mode: Parsing mode (default: prompt_layout_all_en)
        dpi: DPI for PDF to image conversion
        
    Returns:
        dict: Contains pages list with markdown content for each page
    """
    global parser
    
    if parser is None:
        raise HTTPException(status_code=500, detail="Parser not initialized")
    
    # Validate file type
    if not file.content_type == 'application/pdf':
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        # Read uploaded file
        file_content = await file.read()
        
        # Create temporary PDF file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_file.write(file_content)
            temp_pdf_path = temp_file.name
        
        try:
            # Parse PDF using existing parser
            parser.dpi = dpi
            results = parser.parse(temp_pdf_path, prompt_mode=prompt_mode)
            
            pages = []
            for page_result in results:
                pages.append({
                    "page_number": page_result.get("page_idx", 0) + 1,
                    "markdown": page_result.get("md", ""),
                    "markdown_nohf": page_result.get("md_nohf", "")
                })
            
            return {
                "status": "success",
                "filename": file.filename,
                "prompt_mode": prompt_mode,
                "total_pages": len(pages),
                "pages": pages
            }
            
        finally:
            # Clean up temporary file
            os.unlink(temp_pdf_path)
            
    except Exception as e:
        print(f"Error processing PDF {file.filename}: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"Error processing PDF: {str(e)}"
        )


if __name__ == "__main__":
    import argparse
    
    parser_args = argparse.ArgumentParser(description="Start dots.ocr API server")
    parser_args.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser_args.add_argument("--port", type=int, default=8001, help="Port to bind to")
    parser_args.add_argument("--reload", action="store_true", help="Enable auto-reload")
    
    args = parser_args.parse_args()
    
    uvicorn.run(
        "api_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )