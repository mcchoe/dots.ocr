#!/usr/bin/env python3
"""
Simple script to combine all _NOHF.md files in output subfolders into one aggregated file.
"""

import os
import re
from pathlib import Path
from typing import List, Tuple

OUTPUT_BASE_DIR = "./output"


def natural_sort_key(filename: str) -> List[Tuple[str, int]]:
    """Natural sorting for filenames with numbers."""
    return [(text, int(num)) if num.isdigit() else (text, 0) 
            for text, num in re.findall(r'([^0-9]*)([0-9]*)', filename)]


def combine_folder_md(folder_path: str) -> str:
    """Combine all _NOHF.md files in a folder."""
    md_files = []
    
    # Find all _NOHF.md files
    for file in os.listdir(folder_path):
        if file.endswith('_NOHF.md'):
            md_files.append(os.path.join(folder_path, file))
    
    # Sort naturally
    md_files.sort(key=lambda x: natural_sort_key(os.path.basename(x)))
    
    # Combine content
    combined_content = []
    folder_name = os.path.basename(folder_path)
    
    combined_content.append(f"# {folder_name}\n")
    
    for i, md_file in enumerate(md_files, 1):
        filename = Path(md_file).stem.replace('_NOHF', '')
        
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                
            if content:
                combined_content.append(f"## Page {i}: {filename}\n")
                combined_content.append(content)
                combined_content.append("\n---\n")
            else:
                combined_content.append(f"## Page {i}: {filename}\n")
                combined_content.append("*[Empty content]*")
                combined_content.append("\n---\n")
                
        except Exception as e:
            combined_content.append(f"## Page {i}: {filename}\n")
            combined_content.append(f"*[Error reading file: {e}]*")
            combined_content.append("\n---\n")
    
    return '\n'.join(combined_content)


def main():
    if not os.path.exists(OUTPUT_BASE_DIR):
        print(f"❌ Output directory not found: {OUTPUT_BASE_DIR}")
        return
    
    # Get all subfolders
    subfolders = [f for f in os.listdir(OUTPUT_BASE_DIR) 
                 if os.path.isdir(os.path.join(OUTPUT_BASE_DIR, f))]
    
    if not subfolders:
        print(f"❌ No subfolders found in: {OUTPUT_BASE_DIR}")
        return
    
    print(f"📁 Found {len(subfolders)} subfolders to process")
    
    for subfolder in sorted(subfolders):
        folder_path = os.path.join(OUTPUT_BASE_DIR, subfolder)
        
        # Count _NOHF.md files
        md_files = [f for f in os.listdir(folder_path) if f.endswith('_NOHF.md')]
        
        if not md_files:
            print(f"⚠️  No _NOHF.md files in: {subfolder}")
            continue
        
        print(f"📄 Combining {len(md_files)} files from: {subfolder}")
        
        # Combine content
        combined_content = combine_folder_md(folder_path)
        
        # Save combined file
        output_filename = f"{subfolder}_combined.md"
        output_path = os.path.join(OUTPUT_BASE_DIR, output_filename)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(combined_content)
        
        print(f"✅ Saved: {output_filename}")
    
    print(f"\n🎉 All folders processed!")


if __name__ == "__main__":
    main()