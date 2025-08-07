#!/usr/bin/env python3
"""
Local client script for testing dots.ocr RunPod deployment.
Uploads images to RunPod FastAPI endpoint and saves returned markdown files.
"""

import os
import sys
import argparse
import requests
from pathlib import Path
from typing import Optional


def upload_image_to_runpod(
    pod_id: str,
    image_path: str,
    prompt_mode: str = "prompt_layout_all_en",
    output_dir: str = "./output"
) -> bool:
    """
    Upload image to RunPod FastAPI endpoint and save markdown results.
    
    Args:
        pod_id: RunPod pod ID 
        image_path: Path to local image file
        prompt_mode: Parsing mode to use
        output_dir: Directory to save output files
        
    Returns:
        bool: True if successful, False otherwise
    """
    
    # Validate image file exists
    if not os.path.exists(image_path):
        print(f"❌ Error: Image file not found: {image_path}")
        return False
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Construct RunPod URL
    base_url = f"https://{pod_id}-8001.proxy.runpod.net"
    parse_url = f"{base_url}/parse"
    
    print(f"🚀 Uploading {image_path} to RunPod...")
    print(f"📡 URL: {parse_url}")
    print(f"🔧 Prompt mode: {prompt_mode}")
    
    try:
        # Prepare files and data for upload
        with open(image_path, 'rb') as f:
            files = {'file': (os.path.basename(image_path), f, 'image/png')}
            data = {'prompt_mode': prompt_mode}
            
            # Make request with extended timeout for RunPod
            response = requests.post(
                parse_url,
                files=files,
                data=data,
                timeout=95  # Just under RunPod's 100-second limit
            )
        
        # Check response
        if response.status_code == 200:
            result = response.json()
            
            if result.get('status') == 'success':
                print("✅ Successfully parsed document!")
                
                # Save markdown files
                base_name = Path(image_path).stem
                
                # Regular markdown
                markdown_file = os.path.join(output_dir, f"{base_name}.md")
                with open(markdown_file, 'w', encoding='utf-8') as f:
                    f.write(result.get('markdown', ''))
                print(f"📄 Saved markdown: {markdown_file}")
                
                # No headers/footers markdown
                markdown_nohf_file = os.path.join(output_dir, f"{base_name}_nohf.md")
                with open(markdown_nohf_file, 'w', encoding='utf-8') as f:
                    f.write(result.get('markdown_nohf', ''))
                print(f"📄 Saved no-hf markdown: {markdown_nohf_file}")
                
                # Print summary
                print(f"\n📊 Summary:")
                print(f"  Filename: {result.get('filename', 'N/A')}")
                print(f"  Prompt mode: {result.get('prompt_mode', 'N/A')}")
                print(f"  Markdown length: {len(result.get('markdown', ''))}")
                print(f"  No-HF markdown length: {len(result.get('markdown_nohf', ''))}")
                
                return True
            else:
                print(f"❌ Parse failed: {result}")
                return False
        else:
            print(f"❌ HTTP Error {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out (>95 seconds). The document might be too complex.")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ Connection error. Check your RunPod pod ID and ensure the service is running.")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def upload_pdf_to_runpod(
    pod_id: str,
    pdf_path: str,
    prompt_mode: str = "prompt_layout_all_en",
    output_dir: str = "./output",
    dpi: int = 200
) -> bool:
    """
    Upload PDF to RunPod FastAPI endpoint and save markdown results.
    
    Args:
        pod_id: RunPod pod ID
        pdf_path: Path to local PDF file
        prompt_mode: Parsing mode to use
        output_dir: Directory to save output files
        dpi: DPI for PDF conversion
        
    Returns:
        bool: True if successful, False otherwise
    """
    
    # Validate PDF file exists
    if not os.path.exists(pdf_path):
        print(f"❌ Error: PDF file not found: {pdf_path}")
        return False
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Construct RunPod URL
    base_url = f"https://{pod_id}-8001.proxy.runpod.net"
    parse_url = f"{base_url}/parse_pdf"
    
    print(f"🚀 Uploading {pdf_path} to RunPod...")
    print(f"📡 URL: {parse_url}")
    print(f"🔧 Prompt mode: {prompt_mode}")
    print(f"🔧 DPI: {dpi}")
    
    try:
        # Prepare files and data for upload
        with open(pdf_path, 'rb') as f:
            files = {'file': (os.path.basename(pdf_path), f, 'application/pdf')}
            data = {'prompt_mode': prompt_mode, 'dpi': dpi}
            
            # Make request with extended timeout
            response = requests.post(
                parse_url,
                files=files,
                data=data,
                timeout=95
            )
        
        # Check response
        if response.status_code == 200:
            result = response.json()
            
            if result.get('status') == 'success':
                print(f"✅ Successfully parsed PDF with {result.get('total_pages', 0)} pages!")
                
                # Save markdown files for each page
                base_name = Path(pdf_path).stem
                pages = result.get('pages', [])
                
                for page in pages:
                    page_num = page.get('page_number', 1)
                    
                    # Regular markdown for this page
                    markdown_file = os.path.join(output_dir, f"{base_name}_page{page_num}.md")
                    with open(markdown_file, 'w', encoding='utf-8') as f:
                        f.write(page.get('markdown', ''))
                    print(f"📄 Saved page {page_num} markdown: {markdown_file}")
                    
                    # No headers/footers markdown for this page
                    markdown_nohf_file = os.path.join(output_dir, f"{base_name}_page{page_num}_nohf.md")
                    with open(markdown_nohf_file, 'w', encoding='utf-8') as f:
                        f.write(page.get('markdown_nohf', ''))
                    print(f"📄 Saved page {page_num} no-hf markdown: {markdown_nohf_file}")
                
                # Create combined files
                combined_md = "\n\n---\n\n".join([p.get('markdown', '') for p in pages])
                combined_nohf = "\n\n---\n\n".join([p.get('markdown_nohf', '') for p in pages])
                
                combined_file = os.path.join(output_dir, f"{base_name}_combined.md")
                with open(combined_file, 'w', encoding='utf-8') as f:
                    f.write(combined_md)
                print(f"📄 Saved combined markdown: {combined_file}")
                
                combined_nohf_file = os.path.join(output_dir, f"{base_name}_combined_nohf.md")
                with open(combined_nohf_file, 'w', encoding='utf-8') as f:
                    f.write(combined_nohf)
                print(f"📄 Saved combined no-hf markdown: {combined_nohf_file}")
                
                print(f"\n📊 Summary:")
                print(f"  Filename: {result.get('filename', 'N/A')}")
                print(f"  Total pages: {result.get('total_pages', 0)}")
                print(f"  Prompt mode: {result.get('prompt_mode', 'N/A')}")
                
                return True
            else:
                print(f"❌ Parse failed: {result}")
                return False
        else:
            print(f"❌ HTTP Error {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out (>95 seconds). The PDF might be too large or complex.")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ Connection error. Check your RunPod pod ID and ensure the service is running.")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def check_runpod_health(pod_id: str) -> bool:
    """Check if the RunPod service is healthy."""
    
    base_url = f"https://{pod_id}-8001.proxy.runpod.net"
    health_url = f"{base_url}/health"
    
    print(f"🔍 Checking RunPod health: {health_url}")
    
    try:
        response = requests.get(health_url, timeout=10)
        if response.status_code == 200:
            health_data = response.json()
            print(f"✅ RunPod service is healthy!")
            print(f"   Status: {health_data.get('status', 'unknown')}")
            print(f"   Parser initialized: {health_data.get('parser_initialized', 'unknown')}")
            print(f"   vLLM backend: {health_data.get('vllm_backend', 'unknown')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Client for dots.ocr RunPod deployment")
    parser.add_argument("pod_id", help="RunPod pod ID")
    parser.add_argument("file_path", help="Path to image or PDF file")
    parser.add_argument("--prompt-mode", default="prompt_layout_all_en", 
                       help="Parsing prompt mode (default: prompt_layout_all_en)")
    parser.add_argument("--output-dir", default="./output", 
                       help="Output directory for markdown files (default: ./output)")
    parser.add_argument("--dpi", type=int, default=200, 
                       help="DPI for PDF conversion (default: 200)")
    parser.add_argument("--health-check-only", action="store_true",
                       help="Only check service health")
    
    args = parser.parse_args()
    
    # Health check
    if args.health_check_only:
        success = check_runpod_health(args.pod_id)
        sys.exit(0 if success else 1)
    
    # Check service health first
    if not check_runpod_health(args.pod_id):
        print("❌ Service health check failed. Aborting upload.")
        sys.exit(1)
    
    # Determine file type and upload
    file_path = args.file_path.lower()
    if file_path.endswith('.pdf'):
        success = upload_pdf_to_runpod(
            args.pod_id, 
            args.file_path, 
            args.prompt_mode, 
            args.output_dir,
            args.dpi
        )
    elif any(file_path.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']):
        success = upload_image_to_runpod(
            args.pod_id, 
            args.file_path, 
            args.prompt_mode, 
            args.output_dir
        )
    else:
        print("❌ Unsupported file type. Supported: .jpg, .jpeg, .png, .bmp, .tiff, .pdf")
        sys.exit(1)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()