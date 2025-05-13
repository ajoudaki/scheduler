#!/usr/bin/env python3
"""
Simple GPU experiment test for the GPU scheduler
"""

import torch
import time
import os
import datetime

def main():
    # Print experiment info
    print(f"=== GPU Experiment Test ===")
    print(f"Start time: {datetime.datetime.now()}")
    print(f"CUDA_VISIBLE_DEVICES: {os.environ.get('CUDA_VISIBLE_DEVICES', 'not set')}")
    print(f"Working directory: {os.getcwd()}")
    
    # Check if CUDA is available
    if not torch.cuda.is_available():
        print("CUDA is not available! Experiment will run on CPU.")
        device = torch.device("cpu")
    else:
        device = torch.device("cuda")
        print(f"CUDA is available! Using device: {device}")
        
        # Print GPU information
        for i in range(torch.cuda.device_count()):
            print(f"GPU {i}: {torch.cuda.get_device_name(i)}")
            print(f"  Memory: {torch.cuda.get_device_properties(i).total_memory / 1e9:.2f} GB")
            
    # Create tensors to use memory
    print("\nAllocating tensors...")
    a = torch.randn(5000, 5000, device=device)
    b = torch.randn(5000, 5000, device=device)
    
    # Perform some operations
    print("Performing matrix multiplication...")
    start_time = time.time()
    c = torch.matmul(a, b)
    torch.cuda.synchronize() if device.type == "cuda" else None
    print(f"Matrix multiplication completed in {time.time() - start_time:.2f} seconds")
    print(f"Result shape: {c.shape}, Sum: {c.sum().item()}")
    
    # Simulating longer experiment
    print("\nSimulating work for 30 seconds...")
    for i in range(30):
        # Perform some calculation every second to show progress
        torch.matmul(a[:100, :100], b[:100, :100])
        torch.cuda.synchronize() if device.type == "cuda" else None
        
        # Print progress
        if i % 5 == 0:
            print(f"Progress: {i+1}/30 seconds")
        
        time.sleep(1)
    
    print("\nExperiment completed successfully!")
    print(f"End time: {datetime.datetime.now()}")

if __name__ == "__main__":
    main()