#!/usr/bin/env python3
"""
GPU Diagnostics Script - Run this as a job to check GPU availability
"""

import os
import torch
import subprocess
import time

def print_separator():
    print("-" * 80)

def main():
    # Print environment variables
    print("=== ENVIRONMENT VARIABLES ===")
    print(f"CUDA_VISIBLE_DEVICES: {os.environ.get('CUDA_VISIBLE_DEVICES', 'Not set')}")
    print_separator()
    
    # Print nvidia-smi output
    print("=== NVIDIA-SMI OUTPUT ===")
    try:
        nvidia_smi = subprocess.check_output(["nvidia-smi"], universal_newlines=True)
        print(nvidia_smi)
    except Exception as e:
        print(f"Error running nvidia-smi: {e}")
    print_separator()
    
    # PyTorch GPU information
    print("=== PYTORCH GPU INFO ===")
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA device count: {torch.cuda.device_count()}")
        for i in range(torch.cuda.device_count()):
            print(f"  Device {i}: {torch.cuda.get_device_name(i)}")
            print(f"  Memory allocated: {torch.cuda.memory_allocated(i) / 1024**2:.2f} MB")
            print(f"  Memory reserved: {torch.cuda.memory_reserved(i) / 1024**2:.2f} MB")
    else:
        print("No CUDA devices available to PyTorch")
    print_separator()
    
    # Try to use each GPU and report results
    print("=== GPU ACCESS TEST ===")
    if torch.cuda.is_available():
        for i in range(torch.cuda.device_count()):
            try:
                print(f"Testing GPU {i}...")
                device = torch.device(f"cuda:{i}")
                # Create a small tensor on this device
                x = torch.rand(1000, 1000, device=device)
                # Do a simple operation
                y = x @ x
                print(f"  Success! Matrix multiplication completed on GPU {i}")
                # Clean up
                del x, y
                torch.cuda.empty_cache()
            except Exception as e:
                print(f"  Error using GPU {i}: {e}")
    print_separator()
    
    # Print process information
    print("=== PROCESS INFORMATION ===")
    try:
        process_info = subprocess.check_output(["ps", "-ef", "|", "grep", "python"], universal_newlines=True, shell=True)
        print(process_info)
    except Exception as e:
        print(f"Error getting process info: {e}")
    
    # Sleep to keep the job running so we can check nvidia-smi externally
    print("\nSleeping for 30 seconds to allow checking nvidia-smi externally...")
    time.sleep(30)

if __name__ == "__main__":
    main()