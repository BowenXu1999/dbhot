#!/usr/bin/env python3
"""
Simple runner script for the KOL batch processor.
This script provides an easy way to run the batch processing workflow.
"""

import os
import sys
from pathlib import Path
from batch_kol_processor import BatchKOLProcessor

def main():
    """Run the batch processor with simple configuration."""
    
    print("🚀 KOL Batch Processor")
    print("=" * 50)
    
    # Default input file path (adjust this to your actual file path)
    default_input_file = "/Users/xubowen/Downloads/filtered KOL ID.csv"
    
    # Get input file path
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = input(f"Enter path to KOL ID CSV file (default: {default_input_file}): ").strip()
        if not input_file:
            input_file = default_input_file
    
    # Check if file exists
    if not os.path.exists(input_file):
        print(f"❌ Error: File not found: {input_file}")
        print("Please make sure the file path is correct.")
        return
    
    # Configuration
    output_dir = "batch_outputs"
    batch_size = 1000
    
    print(f"📁 Input file: {input_file}")
    print(f"📁 Output directory: {output_dir}")
    print(f"📦 Batch size: {batch_size}")
    print()
    
    # Confirm before starting
    response = input("Do you want to proceed? (y/N): ").strip().lower()
    if response not in ['y', 'yes']:
        print("Operation cancelled.")
        return
    
    try:
        # Create processor and run
        processor = BatchKOLProcessor(
            input_csv_path=input_file,
            output_dir=output_dir,
            batch_size=batch_size
        )
        
        print("\n🔄 Starting batch processing...")
        final_file = processor.run()
        
        if final_file:
            print(f"\n🎉 SUCCESS!")
            print(f"Final output file: {final_file}")
            print(f"Batch files saved in: {output_dir}/")
        else:
            print("\n❌ FAILED! Check the logs above for error details.")
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Operation cancelled by user.")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("Check your database connection and file permissions.")

if __name__ == "__main__":
    main()
