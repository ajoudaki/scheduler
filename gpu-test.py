#!/usr/bin/env python3
import torch
import time
import os
import sys

# Print environment information
print(f"CUDA_VISIBLE_DEVICES: {os.environ.get('CUDA_VISIBLE_DEVICES', 'not set')}")
print(f"Available GPUs: {torch.cuda.device_count()}")

# Check if CUDA is available
if not torch.cuda.is_available():
    print("CUDA is not available. Exiting.")
    sys.exit(1)

# Print GPU information
for i in range(torch.cuda.device_count()):
    print(f"GPU {i}: {torch.cuda.get_device_name(i)}")
    
# Run a simple tensor operation to use some GPU memory
device = torch.device("cuda")
a = torch.randn(10000, 10000, device=device)
b = torch.randn(10000, 10000, device=device)
print("Starting matrix multiplication...")
start_time = time.time()
c = torch.matmul(a, b)
print(f"Matrix multiplication completed in {time.time() - start_time:.2f} seconds")

# Hold GPU memory for a while
print("Holding GPU memory for 30 seconds...")
time.sleep(30)

print("Test completed successfully")