import torch
import time
import sys

job_name = sys.argv[1] if len(sys.argv) > 1 else 'test'
mem_usage_mb = int(sys.argv[2]) if len(sys.argv) > 2 else 500
run_time_sec = int(sys.argv[3]) if len(sys.argv) > 3 else 60

print(f"Starting job {job_name} with {mem_usage_mb}MB memory usage for {run_time_sec} seconds")

# Check if GPU is available
if torch.cuda.is_available():
    device = torch.device('cuda')
    print(f"Using GPU: {torch.cuda.get_device_name(0)}")
    print(f"GPU Device Count: {torch.cuda.device_count()}")
    print(f"CUDA_VISIBLE_DEVICES: {torch.cuda.device_count()}")
    
    # Allocate tensor to use specified memory
    num_elements = mem_usage_mb * 1024 * 1024 // 4  # 4 bytes per float32
    tensor = torch.ones(num_elements, device=device)
    
    # Keep the job running for specified time
    start_time = time.time()
    while time.time() - start_time < run_time_sec:
        # Perform some operations to use GPU
        tensor = tensor * 1.01
        time.sleep(1)
        print(f"Job {job_name} running for {int(time.time() - start_time)} seconds")
        
    print(f"Job {job_name} completed successfully")
else:
    print("No GPU available!")
