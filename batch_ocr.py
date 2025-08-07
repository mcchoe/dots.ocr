#!/usr/bin/env python3
"""
Batch OCR processing script for M&A PE Resources folder.
Processes images in numerical order and saves only _NOHF.md files.
"""

import os
import sys
import requests
import time
import re
from pathlib import Path
from typing import List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# Hardcoded configuration
POD_ID = "9b569wf87rta65-8002"  # Update with your actual pod ID
TARGET_FOLDER = "/Volumes/Storage/document/Kirkland & Ellis/M&A - PE Resources/50-50 Deals/Deadlock Resolutions in 50-50 Transactions"
OUTPUT_BASE_DIR = "./output"


def natural_sort_key(filename: str) -> List[Tuple[str, int]]:
    """
    Generate a key for natural sorting of filenames with numbers.
    E.g., 'image (1).png', 'image (2).png', ..., 'image (10).png'
    """
    return [(text, int(num)) if num.isdigit() else (text, 0) 
            for text, num in re.findall(r'([^0-9]*)([0-9]*)', filename)]


def get_image_files(folder_path: str) -> List[str]:
    """Get all image files from folder, sorted naturally."""
    image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif'}
    
    image_files = []
    for file in os.listdir(folder_path):
        if any(file.lower().endswith(ext) for ext in image_extensions):
            image_files.append(os.path.join(folder_path, file))
    
    # Sort naturally (handles numbers correctly)
    image_files.sort(key=lambda x: natural_sort_key(os.path.basename(x)))
    
    return image_files


def process_single_image(
    image_path: str,
    output_dir: str,
    prompt_mode: str = "prompt_layout_all_en",
    max_retries: int = 3
) -> bool:
    """Process a single image and save only the _NOHF.md file."""
    
    base_url = f"https://{POD_ID}.proxy.runpod.net"
    parse_url = f"{base_url}/parse"
    
    filename = Path(image_path).stem
    
    for attempt in range(max_retries):
        try:
            print(f"📷 Processing: {filename} (attempt {attempt + 1}/{max_retries})")
            
            start_time = time.time()
            
            with open(image_path, 'rb') as f:
                files = {'file': (os.path.basename(image_path), f, 'image/png')}
                data = {'prompt_mode': prompt_mode}
                
                response = requests.post(
                    parse_url,
                    files=files,
                    data=data,
                    timeout=95
                )
            
            end_time = time.time()
            response_time = end_time - start_time
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('status') == 'success':
                    # Save only the _NOHF.md file
                    nohf_file = os.path.join(output_dir, f"{filename}_NOHF.md")
                    with open(nohf_file, 'w', encoding='utf-8') as f:
                        f.write(result.get('markdown_nohf', ''))
                    
                    print(f"✅ {filename} → {os.path.basename(nohf_file)} ({response_time:.1f}s)")
                    return True
                else:
                    print(f"❌ Parse failed for {filename}: {result}")
                    
            else:
                print(f"❌ HTTP {response.status_code} for {filename}: {response.text}")
                
        except requests.exceptions.Timeout:
            print(f"⏰ Timeout for {filename} (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(2)  # Brief pause before retry
            
        except Exception as e:
            print(f"❌ Error processing {filename}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
    
    print(f"❌ Failed to process {filename} after {max_retries} attempts")
    return False


def process_folder(
    folder_path: str,
    prompt_mode: str = "prompt_layout_all_en",
    max_workers: int = 3
):
    """Process all images in a folder."""
    
    if not os.path.exists(folder_path):
        print(f"❌ Folder not found: {folder_path}")
        return
    
    # Get all image files sorted naturally
    image_files = get_image_files(folder_path)
    
    if not image_files:
        print(f"❌ No image files found in: {folder_path}")
        return
    
    # Create output directory based on folder name
    folder_name = os.path.basename(folder_path.rstrip('/'))
    output_dir = os.path.join(OUTPUT_BASE_DIR, folder_name)
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"🚀 Starting batch processing:")
    print(f"   📁 Source: {folder_path}")
    print(f"   📁 Output: {output_dir}")
    print(f"   📊 Images: {len(image_files)}")
    print(f"   🔧 Workers: {max_workers}")
    print(f"   🔧 Prompt: {prompt_mode}")
    print(f"   📡 Pod ID: {POD_ID}")
    print()
    
    # Health check
    health_url = f"https://{POD_ID}.proxy.runpod.net/health"
    try:
        response = requests.get(health_url, timeout=10)
        if response.status_code != 200:
            print(f"❌ Health check failed: {response.status_code}")
            return
        print("✅ RunPod service is healthy")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return
    
    # Process images with thread pool
    successful = 0
    failed = 0
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_file = {
            executor.submit(
                process_single_image,
                image_path,
                output_dir,
                prompt_mode
            ): image_path for image_path in image_files
        }
        
        # Process completed tasks
        for future in as_completed(future_to_file):
            image_path = future_to_file[future]
            try:
                if future.result():
                    successful += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"❌ Unexpected error for {os.path.basename(image_path)}: {e}")
                failed += 1
    
    # Summary
    total_time = time.time() - start_time
    print(f"\n📊 Processing Summary:")
    print(f"   ✅ Successful: {successful}")
    print(f"   ❌ Failed: {failed}")
    print(f"   📁 Output: {output_dir}")
    print(f"   ⏱️  Total time: {total_time:.1f}s")
    print(f"   ⚡ Avg per image: {total_time/len(image_files):.1f}s")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Batch OCR processing for specific folder")
    parser.add_argument("--prompt-mode", default="prompt_layout_all_en",
                       help="Parsing prompt mode (default: prompt_layout_all_en)")
    parser.add_argument("--workers", type=int, default=1,
                       help="Number of concurrent workers (default: 1)")
    
    args = parser.parse_args()
    
    # Process images directly in the target folder
    process_folder(TARGET_FOLDER, args.prompt_mode, args.workers)


if __name__ == "__main__":
    main()